"""Constants for the XMV Controller integration."""

DOMAIN = "xmv_controller"

# Special value from the amplifier that indicates "Muted"
AMP_MUTE_VALUE = -13801

# Reconnection constants
RECONNECT_DELAY_INITIAL = 5  # seconds
RECONNECT_DELAY_MAX = 60    # 60 secs

# Default values for configuration
DEFAULT_HOST = "192.168.1.5"
DEFAULT_PORT = 49280
DEFAULT_CHANNELS = "4:Zone1,6:Zone2"
# User-friendly dB values for the UI
DEFAULT_MIN_DB = -80
DEFAULT_MAX_DB = 0

# Configuration keys used in config_flow and __init__
CONF_HOST = "host"
CONF_PORT = "port"
CONF_CHANNELS = "channels"
CONF_MIN_DB = "min_db"
CONF_MAX_DB = "max_db"