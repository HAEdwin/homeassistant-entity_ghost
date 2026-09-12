"""Switch platform for Entity Ghost Receiver integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback, EntityPlatform
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, MODE_RECEIVER
from .coordinator import EntityReceiverCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Entity Ghost Receiver switch from a config entry."""
    # Only setup switch for receiver mode
    data = hass.data[DOMAIN][entry.entry_id]
    if data["mode"] != MODE_RECEIVER:
        return

    coordinator = data["coordinator"]
    _platform = entity_platform.async_get_current_platform()

    # Add the listener enable/disable switch
    async_add_entities([EntityReceiverListenerSwitch(coordinator, entry)])

    @callback
    def async_add_entity_switch(entity_id: str) -> None:
        """Add a ghost switch when a remote switch is received."""
        entity_data = coordinator.get_entity_data(entity_id)
        if not entity_data or entity_data.get("domain") != "switch":
            return

        tracking_key = f"{entry.entry_id}_switch_tracking"
        existing_switches = hass.data[DOMAIN].setdefault(tracking_key, set())
        if entity_id in existing_switches:
            return

        async_add_entities([ReceivedEntitySwitch(coordinator, entry, entity_id, _platform)])
        existing_switches.add(entity_id)

    hass.data[DOMAIN][f"{entry.entry_id}_switch_tracking"] = set()
    coordinator.add_entity_added_callback(async_add_entity_switch)

    # Handle entities that arrived before the platform callback was registered.
    for entity_id in coordinator.entities:
        async_add_entity_switch(entity_id)


class EntityReceiverListenerSwitch(SwitchEntity):
    """Switch to enable/disable the Entity Ghost Receiver UDP listener."""

    def __init__(
        self, coordinator: EntityReceiverCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the switch."""
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_listener_enabled"
        self._attr_name = f"Entity Ghost Receiver switch for (Port {coordinator.port})"
        self._status_callback = None

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
    def is_on(self) -> bool:
        """Return True if the listener is enabled."""
        return self.coordinator.is_enabled

    @property
    def available(self) -> bool:
        """Return True if the switch is available."""
        return True

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        if self.is_on:
            return "mdi:ghost"
        return "mdi:ghost-off"

    def turn_on(self, **kwargs: Any) -> None:
        """Synchronously turn on the UDP listener."""
        # Schedule the async version
        self.hass.async_create_task(self.async_turn_on(**kwargs))

    def turn_off(self, **kwargs: Any) -> None:
        """Synchronously turn off the UDP listener."""
        # Schedule the async version
        self.hass.async_create_task(self.async_turn_off(**kwargs))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the UDP listener."""
        try:
            await self.coordinator.async_enable()
            # Status change callback will update the state automatically
        except RuntimeError as err:
            _LOGGER.error("Failed to enable UDP listener: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the UDP listener."""
        try:
            await self.coordinator.async_disable()
            # Status change callback will update the state automatically
        except RuntimeError as err:
            _LOGGER.error("Failed to disable UDP listener: %s", err)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Set up callback for status changes
        @callback
        def status_callback():
            self.async_write_ha_state()

        self._status_callback = status_callback
        self.coordinator.add_status_changed_callback(status_callback)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        # Remove callback
        if self._status_callback and hasattr(
            self.coordinator, "remove_status_changed_callback"
        ):
            self.coordinator.remove_status_changed_callback(self._status_callback)
        await super().async_will_remove_from_hass()


class ReceivedEntitySwitch(SwitchEntity):
    """Switch representing a remote switch entity."""

    def __init__(
        self,
        coordinator: EntityReceiverCoordinator,
        entry: ConfigEntry,
        entity_id: str,
        platform: EntityPlatform,
    ) -> None:
        """Initialize the received switch."""
        self.coordinator = coordinator
        self._entry = entry
        self._entity_id = entity_id
        self._platform = platform
        safe_entity_id = entity_id.replace(".", "_").replace("-", "_")
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{safe_entity_id}_switch"
        self._attr_name = f"Received {entity_id}"
        self._update_callback = None
        self._remove_callback = None

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
        """Return whether the remote switch is available."""
        return self._entity_id in self.coordinator.entities

    @property
    def is_on(self) -> bool:
        """Return the remote switch state."""
        entity_data = self.coordinator.get_entity_data(self._entity_id)
        return bool(entity_data and entity_data.get("state") == "on")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Request that the sender turns on the remote switch."""
        await self.coordinator.async_send_command(self._entity_id, "turn_on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Request that the sender turns off the remote switch."""
        await self.coordinator.async_send_command(self._entity_id, "turn_off")

    async def async_added_to_hass(self) -> None:
        """Register for remote state changes."""
        await super().async_added_to_hass()

        @callback
        def update_callback(entity_id: str) -> None:
            if entity_id == self._entity_id:
                self.async_write_ha_state()

        self._update_callback = update_callback
        self.coordinator.add_entity_updated_callback(update_callback)

        @callback
        def remove_callback(entity_id: str) -> None:
            if entity_id == self._entity_id:
                self.hass.data[DOMAIN].get(
                    f"{self._entry.entry_id}_switch_tracking", set()
                ).discard(entity_id)
                self.async_write_ha_state()
                self.hass.async_create_task(self._async_remove_stale())

        self._remove_callback = remove_callback
        self.coordinator.add_entity_removed_callback(remove_callback)

    async def _async_remove_stale(self) -> None:
        """Remove a stale switch and purge its history."""
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
                    "Failed to purge history for stale switch %s", entity_id
                )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from remote state changes."""
        if self._update_callback:
            self.coordinator.remove_entity_updated_callback(self._update_callback)
        if self._remove_callback:
            self.coordinator.remove_entity_removed_callback(self._remove_callback)
        await super().async_will_remove_from_hass()