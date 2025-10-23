"""API for Yamaha XMV Amplifier."""
import asyncio
import logging
from typing import Callable, Dict, Optional

from .const import AMP_MUTE_VALUE, RECONNECT_DELAY_INITIAL, RECONNECT_DELAY_MAX

_LOGGER = logging.getLogger(__name__)

HANDSHAKE_RESPONSE = 'OK devstatus runmode "normal"'
PATH_ID_POWER = "60003"
PATH_ID_VOLUME = "60002"

class AmplifierClient:
    """A client to communicate with a Yamaha XMV amplifier."""

    @staticmethod
    async def test_connection(host: str, port: int) -> bool:
        """Test the connection to the amplifier."""
        _LOGGER.debug("Testing connection to %s:%s", host, port)
        reader, writer = None, None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            writer.write(b"devstatus runmode\n")
            await writer.drain()
            response = await asyncio.wait_for(reader.readline(), timeout=5.0)
            return response.decode("ascii").strip() == HANDSHAKE_RESPONSE
        except Exception as e:
            _LOGGER.debug("Test connection failed: %s", e)
            return False
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()

    def __init__(self, host: str, port: int, min_db: int, max_db: int):
        """Initialize the client."""
        self._host = host
        self._port = port
        self._min_db_100 = min_db * 100
        self._max_db_100 = max_db * 100
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._manager_task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, list[Callable]] = {}
        self._lock = asyncio.Lock()
        self._is_connected = False
        self._keep_alive_task: Optional[asyncio.Task] = None
        self._keep_alive_channel_id: Optional[str] = None


    def start(self):
        """Start the connection manager and keep-alive task."""
        if not self._manager_task:
            self._manager_task = asyncio.create_task(self._connection_manager())
        if not self._keep_alive_task:
            self._keep_alive_task = asyncio.create_task(self._keep_alive_manager())

    async def disconnect(self):
        """Disconnect from the amplifier and stop the manager."""
        if self._manager_task:
            self._manager_task.cancel()
            self._manager_task = None
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            self._keep_alive_task = None
        
        await self._close_connection()
        _LOGGER.info("Client permanently disconnected.")

    async def _close_connection(self):
        """Close the active connection and listener."""
        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

        self._reader = None
        self._writer = None
        if self._is_connected:
            self._is_connected = False
            self._notify_availability(False)

    # --- THIS IS THE CORRECTED CONNECTION MANAGER ---
    async def _connection_manager(self):
        """Manage the connection with exponential backoff."""
        reconnect_delay = RECONNECT_DELAY_INITIAL
        while True:
            try:
                # This outer loop is the reconnection manager.
                if not self._is_connected:
                    _LOGGER.info("Attempting to connect to %s:%s", self._host, self._port)
                    if await self._connect_and_handshake():
                        _LOGGER.info("Connection successful. Resetting reconnect delay.")
                        reconnect_delay = RECONNECT_DELAY_INITIAL
                        
                        # We are connected. Start the listener.
                        self._listen_task = asyncio.create_task(self._listen())
                        
                        # Now, wait for the listener to stop for any reason.
                        try:
                            await self._listen_task
                        except asyncio.CancelledError:
                            # This is expected if _close_connection was called.
                            # We just let it loop again.
                            _LOGGER.debug("Listen task was cancelled, loop will retry.")
                            pass
                    else:
                        # Connection failed, wait and increase backoff
                        _LOGGER.warning(
                            "Connection failed. Will retry in %d seconds.",
                            reconnect_delay,
                        )
                        await asyncio.sleep(reconnect_delay)
                        reconnect_delay = min(reconnect_delay * 2, RECONNECT_DELAY_MAX)
                else:
                    # This state should not be possible, but as a safeguard.
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                # This is a REAL cancellation of the manager itself.
                _LOGGER.info("Connection manager cancelled.")
                break
            except Exception as e:
                # Catch-all for unexpected errors in the manager loop
                _LOGGER.exception("Unhandled error in connection manager: %s", e)
                await asyncio.sleep(reconnect_delay) # Wait before retrying


    async def _connect_and_handshake(self) -> bool:
        """Establish connection and perform handshake."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=5.0
            )
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
            _LOGGER.debug("Connection attempt failed during open: %s", e)
            return False

        try:
            handshake_cmd = "devstatus runmode\n"
            self._writer.write(handshake_cmd.encode("ascii"))
            await self._writer.drain()

            response = await asyncio.wait_for(self._reader.readline(), timeout=5.0)
            if response.decode("ascii").strip() == HANDSHAKE_RESPONSE:
                self._is_connected = True
                _LOGGER.info("Handshake successful. Notifying entities and querying state.")
                self._notify_availability(True)
                for channel_id in self._callbacks:
                    await self.async_query_channel_state(channel_id)
                return True
            else:
                _LOGGER.warning("Handshake failed with unexpected response.")
                await self._close_connection()
                return False
        except (asyncio.TimeoutError, OSError, BrokenPipeError) as e:
            _LOGGER.warning("Connection attempt failed during handshake: %s", e)
            await self._close_connection()
            return False

    def _notify_availability(self, available: bool):
        """Notify all registered channels of connection status."""
        _LOGGER.debug("Notifying availability: %s", available)
        for channel_id in self._callbacks:
            for callback in self._callbacks[channel_id]:
                callback({"available": available})

    async def _listen(self):
        """Listen for incoming data from the amplifier."""
        _LOGGER.info("Starting listener for amplifier messages.")
        while self._is_connected and self._reader:
            try:
                data = await self._reader.readline()
                if not data:
                    _LOGGER.warning("Connection lost.")
                    await self._close_connection()
                    break

                message = data.decode("ascii").strip()
                _LOGGER.debug("Received: %s", message)

                if message.startswith(("OK get", "OK set", "NOTIFY set")):
                    self._process_message(message)

            except (asyncio.CancelledError, ConnectionResetError):
                _LOGGER.info("Listener stopped.")
                # Don't call _close_connection here, just let the task die.
                # The manager will see it exit and handle the state.
                break
            except Exception as e:
                _LOGGER.exception("Error in listener task: %s", e)
                await self._close_connection()
                break
    
    # --- THIS IS THE NEW KEEP-ALIVE TASK ---
    async def _keep_alive_manager(self):
        """Periodically send a command to ensure the connection is alive."""
        while True:
            await asyncio.sleep(60) # Ping every 60 seconds
            try:
                if self._is_connected and self._keep_alive_channel_id:
                    _LOGGER.debug("Sending keep-alive ping.")
                    command = f"get MTX:mem_512/{PATH_ID_POWER}/0/{self._keep_alive_channel_id}/0/0/0 0 0\n"
                    # Use _send_command directly, as it has the error handling
                    await self._send_command(command)
            except asyncio.CancelledError:
                _LOGGER.info("Keep-alive manager cancelled.")
                break
            except Exception as e:
                # Log errors but don't stop the keep-alive loop
                _LOGGER.error("Error in keep-alive manager: %s", e)

    async def register_callback(self, channel_id: str, callback: Callable):
        """Register a callback for a specific channel's updates."""
        if channel_id not in self._callbacks:
            self._callbacks[channel_id] = []
        self._callbacks[channel_id].append(callback)
        _LOGGER.debug("Registered callback for channel %s", channel_id)

        if not self._keep_alive_channel_id:
            self._keep_alive_channel_id = channel_id
            _LOGGER.info("Using channel %s for keep-alive pings.", channel_id)

        if self._is_connected:
            _LOGGER.debug("API already connected, updating new entity %s", channel_id)
            callback({"available": True})
            await self.async_query_channel_state(channel_id)

    def _process_message(self, message: str):
        """Parse a message and trigger callbacks."""
        try:
            parts = message.split()
            address_path = parts[2].split('/')
            command_id = address_path[1]
            channel_id = address_path[3]

            if channel_id not in self._callbacks: return

            update_data = {}
            value = int(parts[5])

            if command_id == PATH_ID_POWER:
                update_data["power"] = value == 1
            elif command_id == PATH_ID_VOLUME:
                if value == AMP_MUTE_VALUE:
                    update_data["mute"] = True
                else:
                    update_data["mute"] = False
                    db_range = self._max_db_100 - self._min_db_100
                    ha_volume = (value - self._min_db_100) / db_range if db_range != 0 else 1.0
                    update_data["volume"] = max(0.0, min(1.0, ha_volume))
            else: return

            if update_data:
                for callback in self._callbacks[channel_id]:
                    callback(update_data)

        except (IndexError, ValueError) as e:
            _LOGGER.warning("Could not parse message: '%s' - Error: %s", message, e)

    async def _send_command(self, command: str):
        """Send a command to the amplifier if connected."""
        if not self._is_connected or not self._writer:
            _LOGGER.warning("Cannot send command, not connected: %s", command.strip())
            return
        
        async with self._lock:
            _LOGGER.debug("Sending command: %s", command.strip())
            try:
                self._writer.write(command.encode("ascii"))
                await self._writer.drain()
            except (OSError, ConnectionResetError) as e:
                _LOGGER.error("Failed to send command, connection lost: %s", e)
                await self._close_connection()

    async def async_query_channel_state(self, channel_id: str):
        """Send 'get' commands to fetch the current state of a channel."""
        commands = [
            f"get MTX:mem_512/{PATH_ID_POWER}/0/{channel_id}/0/0/0 0 0\n",
            f"get MTX:mem_512/{PATH_ID_VOLUME}/0/{channel_id}/0/0/0 0 0\n",
        ]
        for cmd in commands:
            await self._send_command(cmd)
            await asyncio.sleep(0.1)

    async def async_set_power(self, channel_id: str, is_on: bool):
        value = 1 if is_on else 0
        command = f"set MTX:mem_512/{PATH_ID_POWER}/0/{channel_id}/0/0/0 0 0 {value}\n"
        await self._send_command(command)

    async def async_set_mute(self, channel_id: str, is_muted: bool):
        if not is_muted: return
        command = f"set MTX:mem_512/{PATH_ID_VOLUME}/0/{channel_id}/0/0/0 0 0 {AMP_MUTE_VALUE}\n"
        await self._send_command(command)

    async def async_set_volume(self, channel_id: str, ha_volume: float):
        db_range = self._max_db_100 - self._min_db_100
        amp_volume = int(self._min_db_100 + (ha_volume * db_range))
        command = f"set MTX:mem_512/{PATH_ID_VOLUME}/0/{channel_id}/0/0/0 0 0 {amp_volume}\n"
        await self._send_command(command)