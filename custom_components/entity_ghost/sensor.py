"""Sensor platform for Entity Ghost Receiver integration."""

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, MODE_RECEIVER
from .coordinator import EntityReceiverCoordinator

_LOGGER = logging.getLogger(__name__)


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
                sensor = ReceivedEntitySensor(coordinator, entry, entity_id)
                async_add_entities([sensor])
                # Track this entity ID as having a sensor
                existing_sensors.add(entity_id)
                hass.data[DOMAIN][
                    f"{entry.entry_id}_sensor_tracking"
                ] = existing_sensors

                # Trigger immediate state update for the new sensor
                sensor.async_write_ha_state()

    # Callback for when entities are removed from coordinator
    @callback
    def async_remove_entity_sensor(entity_id: str):
        """Remove entity from sensor tracking when coordinator removes it."""
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
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._entity_id = entity_id
        self._entry = entry
        self._update_callback = None
        self._status_callback = None

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
            sw_version="1.0.0",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._entity_id in self.coordinator.entities

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the received entity."""
        entity_data = self.coordinator.get_entity_data(self._entity_id)
        if entity_data:
            return entity_data.get("state")
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
            return entity_data.get("attributes", {}).get("device_class")
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

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        # Remove update callback using public method
        if self._update_callback:
            self.coordinator.remove_entity_updated_callback(self._update_callback)
        await super().async_will_remove_from_hass()
