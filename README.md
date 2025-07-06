# Entity Ghost

A Home Assistant custom integration that combines entity broadcasting and receiving capabilities. This integration allows you to send entity states from one Home Assistant instance to another via UDP, or receive entity states from remote instances.

## Features

### Broadcaster Mode
- **Entity Selection**: Choose specific entities to broadcast
- **UDP Broadcasting**: Sends entity state changes via UDP
- **Real-time Updates**: Broadcasts state changes immediately
- **Configuration UI**: Easy setup through Home Assistant's configuration interface

### Receiver Mode
- **UDP Listener**: Listens for entity state broadcasts on a configurable UDP port
- **Dynamic Entity Creation**: Automatically creates sensors for received entities
- **Real-time Updates**: Updates entity states in real-time as broadcasts are received
- **Entity Management**: Automatically removes stale entities that haven't been updated
- **Device Information**: Groups all received entities under a single device

## Installation

1. Copy the `entity_ghost` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to Configuration → Integrations
4. Click "Add Integration" and search for "Entity Ghost"
5. Choose between Broadcaster or Receiver mode
6. Configure the settings based on your chosen mode

## Configuration

### Broadcaster Mode
- **Entities**: Select the entities you want to broadcast
- **UDP Port**: The port to broadcast on (1024-65535)
- **Broadcaster Name**: A friendly name for this broadcaster

### Receiver Mode
- **UDP Port**: The port to listen on for entity broadcasts (1024-65535)
- **Broadcaster Name**: A friendly name for the broadcasting Home Assistant instance

## Usage

### Broadcaster Mode
Once configured, the integration will automatically broadcast state changes for the selected entities whenever they change.

### Receiver Mode
Once configured, the integration will:
1. Listen for UDP broadcasts on the specified port
2. Automatically create sensors for each received entity
3. Update sensor states in real-time
4. Provide a switch to enable/disable the UDP listener

## Entity Format

The component expects/sends JSON messages in the following format:

```json
{
  "broadcaster_name": "Remote Home Assistant",
  "entity_id": "sensor.temperature",
  "state": "23.5",
  "attributes": {
    "friendly_name": "Living Room Temperature",
    "unit_of_measurement": "°C",
    "device_class": "temperature"
  },
  "timestamp": 1234567890.123
}
```

## Use Case

This integration is particularly useful when you have multiple Home Assistant instances and want to share entity states between them. For example:
- A production instance with physical sensors
- A development instance that needs access to real sensor data
- Remote monitoring setups
- Testing environments

## Troubleshooting

- Ensure the UDP port is not blocked by firewall
- Check that the broadcaster is sending to the correct IP and port
- Verify network connectivity between Home Assistant instances
- Check the logs for any error messages

## License

MIT License - see LICENSE file for details.
