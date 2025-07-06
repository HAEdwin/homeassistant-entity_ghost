"""Constants for the Entity Ghost integration."""

DOMAIN = "entity_ghost"

# Mode types
MODE_BROADCASTER = "broadcaster"
MODE_RECEIVER = "receiver"

# Configuration keys
CONF_MODE = "mode"
CONF_ENTITIES = "entities"
CONF_UDP_PORT = "udp_port"
CONF_NAME = "name"
CONF_BROADCASTER_NAME = "broadcaster_name"

# Default values
DEFAULT_UDP_PORT = 8888
MIN_UDP_PORT = 1024
MAX_UDP_PORT = 65535
DEFAULT_BROADCASTER_NAME = "Remote Home Assistant"

# Entity registry
ENTITY_REGISTRY_KEY = "entities"
