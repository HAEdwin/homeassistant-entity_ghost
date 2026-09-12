"""Sensor platform for Entity Ghost Receiver integration."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback, EntityPlatform
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, MODE_RECEIVER
from .coordinator import EntityReceiverCoordinator

_LOGGER = logging.getLogger(__name__)

_DEVICE_CLASS_UNITS = {
    "power": {"W", "kW", "mW", "MW", "GW", "TW"},
    "energy": {"Wh", "kWh", "MWh", "GWh", "TWh", "mWh"},
    "current": {"A", "mA"},
    "voltage": {"V", "mV", "kV"},
    "frequency": {"Hz", "kHz", "MHz", "GHz"},
    "temperature": {"°C", "°F", "K"},
    "pressure": {"Pa", "hPa", "kPa", "bar", "cbar", "mbar", "psi"},
    "humidity": {"%"},
    "illuminance": {"lx"},
    "signal_strength": {"dB", "dBm"},
    "speed": {"m/s", "km/h", "mph", "ft/s", "kn"},
    "precipitation": {"mm", "cm", "in"},
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Entity Ghost Receiver sensors from a config entry."""
    # Only setup sensors for receiver mode
    data = hass.data[DOMAIN][entry.entry_id]
    if data["mode"] != MODE_RECEIVER:
        return

    coordinator = data["coordinator"]
    _platform = entity_platform.async_get_current_platform()

    # Initialize sensor tracking
    hass.data[DOMAIN][f"{entry.entry_id}_sensor_tracking"] = set()

    # Listen for new entities and add them dynamically
    @callback
    def async_add_entity_sensors(entity_id: str):
        """Add sensor for new entity."""
        # Track existing sensors by their original entity IDs
        existing_sensors = hass.data[DOMAIN].get(
            f"{entry.entry_id}_sensor_tracking", set()
        )

        if entity_id not in existing_sensors:
            if entity_id:  # Ensure entity_id is not None or empty
                sensor = ReceivedEntitySensor(coordinator, entry, entity_id, _platform)
                async_add_entities([sensor])
                # Track this entity ID as having a sensor
                existing_sensors.add(entity_id)
                hass.data[DOMAIN][
                    f"{entry.entry_id}_sensor_tracking"
                ] = existing_sensors


# Callback for when entities are removed from coordinator
    @callback
    def async_remove_entity_sensor(entity_id: str):
        """Clear tracking so a returning entity is created fresh."""
        tracking_key = f"{entry.entry_id}_sensor_tracking"
        if tracking_key in hass.data[DOMAIN]:
            hass.data[DOMAIN][tracking_key].discard(entity_id)

    # Set up the listeners
    coordinator.add_entity_added_callback(async_add_entity_sensors)
    coordinator.add_entity_removed_callback(async_remove_entity_sensor)


class ReceivedEntitySensor(SensorEntity):
    """Sensor representing a received entity from the broadcaster."""

    def __init__(
        self,
        coordinator: EntityReceiverCoordinator,
        entry: ConfigEntry,
        entity_id: str,
        platform: EntityPlatform,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._entity_id = entity_id
        self._entry = entry
        self._platform = platform
        self._update_callback = None
        self._remove_callback = None

        # Validate entity_id
        if not entity_id:
            raise ValueError("entity_id cannot be None or empty")

        # Create a safe entity ID for Home Assistant
        safe_entity_id = entity_id.replace(".", "_").replace("-", "_")
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{safe_entity_id}"

        # Get entity data to set initial name
        entity_data = coordinator.get_entity_data(entity_id)
        if entity_data and entity_data.get("attributes", {}).get("friendly_name"):
            self._attr_name = f"Received {entity_data['attributes']['friendly_name']}"
        else:
            self._attr_name = f"Received {entity_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Entity Ghost Receiver (Port {self.coordinator.port})",
            manufacturer="HAEdwin",
            model="Entity Ghost Receiver",
            sw_version="2.0.0",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._entity_id in self.coordinator.entities

    @property
    def native_value(self) -> Any:
        """Return the state of the received entity."""
        entity_data = self.coordinator.get_entity_data(self._entity_id)
        if entity_data:
            state = entity_data.get("state")
            if state in ("unknown", "unavailable"):
                return None
            device_class = entity_data.get("attributes", {}).get("device_class")
            if device_class in ("timestamp", "uptime") and isinstance(state, str):
                try:
                    return datetime.fromisoformat(state)
                except ValueError:
                    return None
            return state
        return None

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement."""
        entity_data = self.coordinator.get_entity_data(self._entity_id)
        if entity_data:
            return entity_data.get("attributes", {}).get("unit_of_measurement")
        return None

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class."""
        entity_data = self.coordinator.get_entity_data(self._entity_id)
        if entity_data:
            attributes = entity_data.get("attributes", {})
            device_class = attributes.get("device_class")
            unit = attributes.get("unit_of_measurement")
            valid_units = _DEVICE_CLASS_UNITS.get(device_class)
            if valid_units is not None and unit not in valid_units:
                return None
            return device_class
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        entity_data = self.coordinator.get_entity_data(self._entity_id)
        if not entity_data:
            return {}

        attributes = entity_data.get("attributes", {}).copy()

        # Add receiver-specific attributes
        attributes.update(
            {
                "original_entity_id": self._entity_id,
                "original_domain": entity_data.get("domain"),
                "broadcaster_name": entity_data.get("broadcaster_name"),
                "source_ip": entity_data.get("source_ip"),
                "last_updated": entity_data.get("last_updated"),
            }
        )

        return attributes

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        entity_data = self.coordinator.get_entity_data(self._entity_id)
        if entity_data:
            # Try to get icon from attributes
            icon = entity_data.get("attributes", {}).get("icon")
            if icon:
                return icon

        # Default icon based on entity type
        if "temperature" in self._entity_id.lower():
            return "mdi:thermometer"
        elif "humidity" in self._entity_id.lower():
            return "mdi:water-percent"
        elif "light" in self._entity_id.lower():
            return "mdi:lightbulb"
        elif "switch" in self._entity_id.lower():
            return "mdi:toggle-switch"
        else:
            return "mdi:ghost"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Set up callback for entity updates
        @callback
        def update_callback(entity_id: str):
            if entity_id == self._entity_id:
                self.async_write_ha_state()

        self._update_callback = update_callback
        self.coordinator.add_entity_updated_callback(update_callback)

        @callback
        def remove_callback(entity_id: str):
            if entity_id == self._entity_id:
                self.async_write_ha_state()
                self.hass.async_create_task(self._async_remove_stale())

        self._remove_callback = remove_callback
        self.coordinator.add_entity_removed_callback(remove_callback)

    async def _async_remove_stale(self) -> None:
        """Remove a stale entity and purge its history."""
        entity_id = self.entity_id
        await self._platform.async_remove_entity(entity_id)
        if "recorder" in self.hass.config.components:
            try:
                await self.hass.services.async_call(
                    "recorder",
                    "purge_entities",
                    {"entity_id": [entity_id]},
                    blocking=False,
                )
            except Exception:
                _LOGGER.exception(
                    "Failed to purge history for stale entity %s", entity_id
                )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        # Remove update callback using public method
        if self._update_callback:
            self.coordinator.remove_entity_updated_callback(self._update_callback)
        if self._remove_callback:
            self.coordinator.remove_entity_removed_callback(self._remove_callback)
        await super().async_will_remove_from_hass()
