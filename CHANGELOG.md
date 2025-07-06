# Changelog

All notable changes to the Entity Ghost integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
