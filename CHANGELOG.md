# Changelog

All notable changes to the Entity Ghost integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-09-12

### Added
- Integration-based entity scope: the broadcaster selects integration domains
  instead of individual entity IDs; new and removed entities are picked up
  dynamically.
- Ghost entities for every received entity: each received entity is mirrored
  as a sensor ghost, and received `switch` entities also get a controllable
  ghost switch.
- Ghost-switch commands are validated on the sender: only `switch` entities in
  scope and only `turn_on` / `turn_off` are accepted.
- Options flow for both modes — broadcaster: integrations, UDP port and name;
  receiver: UDP port, broadcaster name and stale timeout.
- Options are applied without a restart: broadcaster port, name and
  integrations, and receiver stale timeout and broadcaster name take effect
  immediately.
- Stale-entity cleanup: ghosts are marked `unavailable` after a configurable
  timeout, then removed together with their recorded history; leftover
  registry entries from earlier sessions are cleaned automatically.
- Single device (`Entity Ghost Receiver (Port <port>)`) grouping all ghosts
  plus a switch to enable/disable the UDP listener.
- A safe metadata subset per entity is broadcast: `friendly_name`,
  `device_class`, `unit_of_measurement`, `state_class`, `icon` and
  `entity_category`; a registry icon takes precedence over the state icon.
- Oversized payloads are skipped with a warning instead of blocking further
  broadcasts.

### Changed
- Entity selection is by integration instead of by individual entity IDs; the
  legacy per-entity key remains temporarily supported for migration.

### Fixed
- Changing the broadcaster UDP port through the options flow now rebinds the
  listener immediately; the socket is only swapped after the new one is bound.
- The broadcaster name set through the options flow is applied live.
- Received messages that carry a broadcaster name now use it as the label,
  falling back to the configured broadcaster name.

## [1.0.0] - 2025-07-06

### Added
- Initial release combining Entity Broadcaster and Entity Receiver functionality
- Broadcaster mode for sending entity states via UDP
- Receiver mode for receiving entity states via UDP  
- Configuration flow with mode selection (broadcaster or receiver)
- Dynamic entity selection for broadcaster mode
- Real-time entity updates in receiver mode
- Switch entity to enable/disable UDP listener in receiver mode
- Automatic cleanup of stale entities in receiver mode
- Device grouping for all entities
- Comprehensive error handling and logging

### Features
- **Dual Mode Operation**: Choose between broadcaster or receiver mode during setup
- **Entity Broadcasting**: Select specific entities to broadcast their state changes
- **Entity Receiving**: Automatically create sensors for received entities
- **Real-time Updates**: Immediate state synchronization
- **Network Discovery**: UDP broadcasting with localhost fallback
- **Configuration UI**: Full Home Assistant configuration flow support
- **Device Management**: Proper device information and grouping
