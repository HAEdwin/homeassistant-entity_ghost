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
CONF_STALE_ENTITY_POLICY = "stale_entity_policy"
CONF_STALE_ENTITY_MINUTES = "stale_entity_minutes"

# Stale entity policy options
STALE_POLICY_KEEP_FOREVER = "keep_forever"
STALE_POLICY_UNAVAILABLE_IMMEDIATELY = "unavailable_immediately"
STALE_POLICY_UNAVAILABLE_AFTER_X = "unavailable_after_x"

# Default values
DEFAULT_UDP_PORT = 8888
MIN_UDP_PORT = 1024
MAX_UDP_PORT = 65535

DEFAULT_BROADCASTER_NAME = "Remote Home Assistant"
DEFAULT_STALE_POLICY = STALE_POLICY_UNAVAILABLE_AFTER_X
DEFAULT_STALE_MINUTES = 10

# Entity registry
ENTITY_REGISTRY_KEY = "entities"
