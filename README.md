**Home Assistant - Yamaha XMV MTX Controller** v1.0

This is a custom component for Home Assistant to control Yamaha XMV series AV processors / amplifiers over an IP network.  These processors/amps are usually located in commercial settings e.g. Theatres, Restaurants etc and can be controlled remotely via various methods.  This has all been tested with a XMV-MTX3 Matrix processor.

It creates a media_player entity for each configured output zone, allowing you to independently control channel state (ON OR OFF), volume, and mute for each one. The component maintains a persistent, real-time connection to the amplifier, so any changes made from other sources (like a wall panel) will be instantly reflected in Home Assistant.

**Features**

- Multi-Zone Control: Creates a separate media_player entity for each output zone you define.
- Power Control: Turn channels on and off.
- Volume Control: Adjust volume with a fader.
- Mute Control: Mute and unmute channels.
- Real-Time Status: A persistent listener instantly updates Home Assistant if the amp's state is changed externally.
- Robust Reconnection: Automatically handles network disconnections or amplifier reboots, with an exponential backoff to avoid flooding your network.
- Keep-Alive: Proactively checks the connection to detect and recover from "stale" or "zombie" connections.
- Configurable Volume: Map the amplifier's decibel (dB) range to Home Assistant's 0.0 (min) to 1.0 (max) slider.
- UI Configuration: All setup and changes are done via the Home Assistant frontend.

**Installation**
Manual Installation

1. Navigate to your Home Assistant config directory.
2. If it doesn't already exist, create a custom_components directory.
3. Copy the entire xmv_controller folder (containing all 7 files: __init__.py, api.py, const.py, config_flow.py, media_player.py, manifest.json, and strings.json) into the custom_components directory.

Your final directory structure should look like this:

<pre>
xmv_control
├── __init__.py
├── api.py
├── config_flow.py
├── const.py
├── manifest.json
├── media_player.py
└── strings.json
</pre>
6. Restart Home Assistant. This is a crucial step for it to find and load the new component.

**Configuration**
All configuration is handled in the Home Assistant UI.

1. Go to Settings > Devices & Services.
2. Click the + Add Integration button in the bottom-right corner.
3. Search for "XMV Controller" and select it.
4. A configuration form will appear.
5. Configuration Fields
6. IP Address: The IP address of your Yamaha XMV amplifier (e.g., 192.168.1.100).
7. Port: The control port for the amplifier. The default is 49280.
8. Channels / Zones (e.g., 0:Zone1, 4:Kitchen): This is the most important field. You must provide a comma-separated list of ID:Name pairs.
9. ID: The internal channel ID the amplifier uses for a fader. This is the Xpos value from the Yamaha protocol (e.g., 0, 4).
10. Name: The "friendly name" you want to see for this channel in Home Assistant (e.g., "Living Room", "Kitchen").
Example: 0:Living Room, 1:Kitchen, 4:Patio   ... Please note, Output Zone 1 on the yamaha is 0  so, 0:Zone1, 1:Zone2, 2:Zone3 etc.  My amp has 8 output zones available but some models have 16.
12. Minimum Volume (dB): The decibel value you want to map to the bottom (silent) of the Home Assistant slider. Default: -80.
13. Maximum Volume (dB): The decibel value you want to map to the top (max) of the Home Assistant slider. Default: 0.
14. After submitting the form, the integration will connect. You can find the new media_player entities under the "XMV Controller" device.

**Reconfiguring**
You can change these settings at any time without removing the integration.

1. Go to Settings > Devices & Services.
2. Find the "XMV Controller" integration card.
3. Click Configure.

You can update the IP, port, channel list, and volume range. The integration will automatically reload with the new settings.

**Debugging**
To enable debug logging, add the following to your configuration.yaml file and restart Home Assistant:

<pre>
logger:
  default: info
  logs:
    custom_components.xmv_controller: debug
</pre>

**Future enhancemenets**

Nearly all of the functions of the XMV series can be controlled over IP.  I've just concentrated on turning a zone output channel on or off and altering the volume level of output zones, as that's all I wanted to do!
The component can easily be extended to control other faders e.g. Inputs, Outputs, Matrix, recalling and storing presets etc etc.
