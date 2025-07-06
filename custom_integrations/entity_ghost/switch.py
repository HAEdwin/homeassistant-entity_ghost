"""Switch platform for Entity Ghost Receiver integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Entity Ghost Receiver switch from a config entry."""
    # Only setup switch for receiver mode
    data = hass.data[DOMAIN][entry.entry_id]
    if data["mode"] != MODE_RECEIVER:
        return

    coordinator = data["coordinator"]

    # Add the listener enable/disable switch
    async_add_entities([EntityReceiverListenerSwitch(coordinator, entry)])


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
