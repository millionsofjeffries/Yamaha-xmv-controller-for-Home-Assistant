"""Media player platform for XMV Controller."""
from __future__ import annotations
import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AmplifierClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the XMV media player entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api_client: AmplifierClient = data["api_client"]
    channels = data["channels"]
    
    entities = [
        XmvMediaPlayer(api_client, channel_id, name, entry)
        for channel_id, name in channels.items()
    ]
    async_add_entities(entities)

class XmvMediaPlayer(MediaPlayerEntity):
    """A Yamaha XMV Output channel (zone) represented as a Media Player."""
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, api_client: AmplifierClient, channel_id: str, name: str, entry: ConfigEntry
    ) -> None:
        """Initialize the media player."""
        self._api = api_client
        self._channel_id = channel_id
        
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{channel_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"XMV Amplifier ({entry.data['host']})",
            manufacturer="Yamaha",
            model="XMV Series",
        )
        
        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_MUTE
        )
        
        self._attr_available = False
        self._attr_state = None
        self._attr_volume_level = None
        self._attr_is_volume_muted = None
        self._pre_mute_volume: float | None = None

    @callback
    def _handle_update(self, update_data: dict) -> None:
        """Handle an update from the API client."""
        _LOGGER.debug("Update for channel %s: %s", self._channel_id, update_data)
        updated = False
        if "available" in update_data:
            self._attr_available = update_data["available"]
            updated = True
        if "power" in update_data:
            self._attr_state = MediaPlayerState.ON if update_data["power"] else MediaPlayerState.OFF
            updated = True
        if "volume" in update_data:
            self._attr_volume_level = update_data["volume"]
            updated = True
        if "mute" in update_data:
            self._attr_is_volume_muted = update_data["mute"]
            updated = True
        
        if updated:
            self.async_write_ha_state()

    # --- MODIFIED: This method is now async ---
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        # We now await the registration
        await self._api.register_callback(self._channel_id, self._handle_update)
        # The state query is removed from here, as the register_callback
        # or the _connect_and_handshake methods now handle it.

    async def async_turn_on(self) -> None:
        await self._api.async_set_power(self._channel_id, True)

    async def async_turn_off(self) -> None:
        await self._api.async_set_power(self._channel_id, False)

    async def async_set_volume_level(self, volume: float) -> None:
        await self._api.async_set_volume(self._channel_id, volume)

    async def async_mute_volume(self, mute: bool) -> None:
        if mute:
            self._pre_mute_volume = self._attr_volume_level
            await self._api.async_set_mute(self._channel_id, True)
        else:
            volume_to_restore = self._pre_mute_volume or 0.5
            await self.async_set_volume_level(volume_to_restore)