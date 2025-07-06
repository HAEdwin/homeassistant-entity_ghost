"""The Entity Ghost integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import (
    DOMAIN,
    MODE_BROADCASTER,
    MODE_RECEIVER,
    CONF_MODE,
    CONF_ENTITIES,
    CONF_UDP_PORT,
    CONF_NAME,
    CONF_BROADCASTER_NAME,
)
from .broadcaster import EntityBroadcaster
from .coordinator import EntityReceiverCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Entity Ghost from a config entry."""
    _LOGGER.debug("Setting up Entity Ghost with config: %s", entry.data)

    mode = entry.data[CONF_MODE]
    hass.data.setdefault(DOMAIN, {})

    if mode == MODE_BROADCASTER:
        return await _setup_broadcaster(hass, entry)
    elif mode == MODE_RECEIVER:
        return await _setup_receiver(hass, entry)
    else:
        _LOGGER.error("Unknown mode: %s", mode)
        return False


async def _setup_broadcaster(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up broadcaster mode."""
    # Extract configuration
    entities = entry.data.get(CONF_ENTITIES, [])
    udp_port = entry.data.get(CONF_UDP_PORT)
    name = entry.data.get(CONF_NAME, "Entity Ghost Broadcaster")

    # Create and setup the broadcaster
    broadcaster = EntityBroadcaster(hass, entities, udp_port, name)

    if not await broadcaster.async_setup():
        _LOGGER.error("Failed to setup Entity Ghost Broadcaster")
        return False

    # Store the broadcaster instance
    hass.data[DOMAIN][entry.entry_id] = {
        "mode": MODE_BROADCASTER,
        "broadcaster": broadcaster,
        "config": entry.data,
    }

    # Set up update listener for config changes
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def _setup_receiver(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up receiver mode."""
    # Create coordinator
    coordinator = EntityReceiverCoordinator(hass, entry)

    # Start the UDP listener
    await coordinator.async_start()

    # Store the coordinator instance
    hass.data[DOMAIN][entry.entry_id] = {
        "mode": MODE_RECEIVER,
        "coordinator": coordinator,
        "config": entry.data,
    }

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for config entry options."""
    data = hass.data[DOMAIN][entry.entry_id]
    mode = data["mode"]

    if mode == MODE_BROADCASTER:
        broadcaster = data["broadcaster"]

        # Get updated configuration from options or data
        entities = entry.options.get(CONF_ENTITIES) or entry.data.get(CONF_ENTITIES, [])
        udp_port = entry.options.get(CONF_UDP_PORT) or entry.data.get(CONF_UDP_PORT)

        # Update broadcaster with new configuration
        await broadcaster.async_update_entities(entities)
        await broadcaster.async_update_port(udp_port)

        _LOGGER.info("Updated Entity Ghost Broadcaster configuration")

    elif mode == MODE_RECEIVER:
        # For receiver mode, the coordinator handles options updates internally
        _LOGGER.info("Entity Ghost Receiver configuration updated")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Entity Ghost config entry: %s", entry.entry_id)

    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return True

    mode = data["mode"]

    if mode == MODE_BROADCASTER:
        # Shutdown the broadcaster
        if "broadcaster" in data:
            await data["broadcaster"].async_shutdown()

    elif mode == MODE_RECEIVER:
        # Stop the coordinator
        if "coordinator" in data:
            await data["coordinator"].async_stop()

        # Unload platforms
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

        if not unload_ok:
            return False

    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
