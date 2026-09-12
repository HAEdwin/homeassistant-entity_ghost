"""Constants for the Entity Ghost integration."""

DOMAIN = "entity_ghost"

# Mode types
MODE_BROADCASTER = "broadcaster"
MODE_RECEIVER = "receiver"

# Configuration keys
CONF_MODE = "mode"
CONF_INTEGRATIONS = "integrations"
CONF_UDP_PORT = "udp_port"
CONF_NAME = "name"
CONF_BROADCASTER_NAME = "broadcaster_name"
CONF_STALE_TIMEOUT = "stale_timeout_minutes"

# Default values
DEFAULT_UDP_PORT = 8888
MIN_UDP_PORT = 1024
MAX_UDP_PORT = 65535
DEFAULT_BROADCASTER_NAME = "Remote Home Assistant"
DEFAULT_STALE_TIMEOUT = 10
STALE_TIMEOUT_MIN = 0
STALE_TIMEOUT_MAX = 120

