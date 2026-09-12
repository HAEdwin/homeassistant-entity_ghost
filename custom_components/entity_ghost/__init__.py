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
    CONF_INTEGRATIONS,
    CONF_UDP_PORT,
    CONF_NAME,
    CONF_BROADCASTER_NAME,
    CONF_STALE_TIMEOUT,
    DEFAULT_BROADCASTER_NAME,
    DEFAULT_STALE_TIMEOUT,
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
    integrations = entry.data.get(CONF_INTEGRATIONS, [])
    if not integrations:
        legacy_entities = entry.data.get("entities", [])
        if legacy_entities:
            integrations = sorted(
                {
                    entity_id.split(".", 1)[0]
                    for entity_id in legacy_entities
                    if isinstance(entity_id, str) and "." in entity_id
                }
            )
            if integrations:
                hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_INTEGRATIONS: integrations}
                )
    udp_port = entry.data.get(CONF_UDP_PORT)
    name = entry.data.get(CONF_NAME, "Entity Ghost Broadcaster")

    # Create and setup the broadcaster
    broadcaster = EntityBroadcaster(hass, integrations, udp_port, name)

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

    # Set up update listener for config changes
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for config entry options."""
    data = hass.data[DOMAIN][entry.entry_id]
    mode = data["mode"]

    if mode == MODE_BROADCASTER:
        broadcaster = data["broadcaster"]

        # Get updated configuration from options or data
        integrations = entry.options.get(CONF_INTEGRATIONS) or entry.data.get(
            CONF_INTEGRATIONS, []
        )
        udp_port = entry.options.get(CONF_UDP_PORT) or entry.data.get(CONF_UDP_PORT)
        name = entry.options.get(CONF_NAME) or entry.data.get(
            CONF_NAME, "Entity Ghost Broadcaster"
        )

        # Update broadcaster with new configuration
        await broadcaster.async_update_port(udp_port)
        await broadcaster.async_update_name(name)
        await broadcaster.async_update_integrations(integrations)

        _LOGGER.info("Updated Entity Ghost Broadcaster configuration")

    elif mode == MODE_RECEIVER:
        coordinator = data["coordinator"]
        stale_timeout = entry.options.get(
            CONF_STALE_TIMEOUT,
            entry.data.get(CONF_STALE_TIMEOUT, DEFAULT_STALE_TIMEOUT),
        )
        coordinator.broadcaster_name = entry.options.get(
            CONF_BROADCASTER_NAME,
            entry.data.get(CONF_BROADCASTER_NAME, DEFAULT_BROADCASTER_NAME),
        )
        await coordinator.async_set_stale_timeout(stale_timeout)
        _LOGGER.info("Updated Entity Ghost Receiver configuration")


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
