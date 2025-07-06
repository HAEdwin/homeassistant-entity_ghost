"""Coordinator for Entity Ghost Receiver integration."""

import asyncio
import json
import logging
import socket
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_UDP_PORT,
    CONF_BROADCASTER_NAME,
    DEFAULT_BROADCASTER_NAME,
)

_LOGGER = logging.getLogger(__name__)


class EntityReceiverCoordinator:
    """Coordinator to manage UDP listener and entity data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self.entry = entry
        self.port = entry.options.get(CONF_UDP_PORT, entry.data[CONF_UDP_PORT])
        self.broadcaster_name = entry.options.get(
            CONF_BROADCASTER_NAME,
            entry.data.get(CONF_BROADCASTER_NAME, DEFAULT_BROADCASTER_NAME),
        )

        self._socket: Optional[socket.socket] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._entities: Dict[str, Dict[str, Any]] = {}
        self._last_seen: Dict[str, datetime] = {}
        self._entity_removed_callbacks = []
        self._entity_updated_callbacks = []
        self._entity_added_callbacks = []
        self._status_changed_callbacks = []
        self._enabled = True  # Default to enabled

    @property
    def entities(self) -> Dict[str, Dict[str, Any]]:
        """Return current entities."""
        return self._entities

    @property
    def is_listening(self) -> bool:
        """Return True if the coordinator is actively listening for UDP messages."""
        return (
            self._enabled
            and self._socket is not None
            and self._socket.fileno() != -1
            and self._listen_task is not None
            and not self._listen_task.done()
        )

    @property
    def is_enabled(self) -> bool:
        """Return True if the coordinator is enabled."""
        return self._enabled

    async def async_enable(self) -> None:
        """Enable the UDP listener."""
        was_enabled = self._enabled
        if not self._enabled:
            self._enabled = True
            await self.async_start()

        # Always notify status change to ensure UI updates
        if not was_enabled or not self.is_listening:
            self._notify_status_changed()

    async def async_disable(self) -> None:
        """Disable the UDP listener."""
        was_enabled = self._enabled
        if self._enabled:
            self._enabled = False
            await self.async_stop()

        # Always notify status change to ensure UI updates
        if was_enabled:
            self._notify_status_changed()

    async def async_set_enabled(self, enabled: bool) -> None:
        """Set the enabled state of the UDP listener."""
        if enabled and not self._enabled:
            await self.async_enable()
        elif not enabled and self._enabled:
            await self.async_disable()

    async def async_start(self) -> None:
        """Start the UDP listener."""
        if not self._enabled:
            _LOGGER.debug("Coordinator is disabled, not starting UDP listener")
            return

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.setblocking(False)
            self._socket.bind(("", self.port))

            self._listen_task = asyncio.create_task(self._listen_for_messages())
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_entities())
            _LOGGER.info(
                "Started Entity Ghost Receiver UDP listener on port %s", self.port
            )

            # Notify status change
            self._notify_status_changed()

        except Exception as err:
            _LOGGER.error("Failed to start UDP listener: %s", err)
            raise

    async def async_stop(self) -> None:
        """Stop the UDP listener."""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        if self._socket:
            self._socket.close()
            self._socket = None

        _LOGGER.info("Stopped Entity Ghost Receiver UDP listener")

        # Notify status change
        self._notify_status_changed()

    async def _listen_for_messages(self) -> None:
        """Listen for UDP messages."""
        while True:
            try:
                # Use asyncio to avoid blocking
                loop = asyncio.get_event_loop()
                data, addr = await loop.sock_recvfrom(self._socket, 4096)

                # Process the message immediately when received
                await self._process_message(data, addr)

            except asyncio.CancelledError:
                break
            except OSError as err:
                _LOGGER.error("Error receiving UDP message: %s", err)
                await asyncio.sleep(1)  # Brief pause before retrying

    async def _process_message(self, data: bytes, addr: tuple) -> None:
        """Process received UDP message."""
        try:
            # Decode JSON message
            message = json.loads(data.decode("utf-8"))

            # Extract entity information
            entity_id = message.get("entity_id")
            if not entity_id or not isinstance(entity_id, str) or not entity_id.strip():
                _LOGGER.warning(
                    "Received message with invalid entity_id from %s: %s",
                    addr[0],
                    entity_id,
                )
                return

            # Check if this is a new entity
            is_new_entity = entity_id not in self._entities

            # Store entity data
            self._entities[entity_id] = {
                "entity_id": entity_id,
                "state": message.get("state"),
                "attributes": message.get("attributes", {}),
                "broadcaster_name": message.get("broadcaster_name", "Unknown"),
                "source_ip": addr[0],
                "last_updated": datetime.now(),
            }

            self._last_seen[entity_id] = datetime.now()

            # Notify listeners immediately
            if is_new_entity:
                for cb in self._entity_added_callbacks:
                    try:
                        cb(entity_id)
                    except RuntimeError as err:
                        _LOGGER.error("Error in entity added callback: %s", err)
            else:
                for cb in self._entity_updated_callbacks:
                    try:
                        cb(entity_id)
                    except RuntimeError as err:
                        _LOGGER.error("Error in entity updated callback: %s", err)

            _LOGGER.debug(
                "Received entity update: %s = %s from %s (callbacks: %d added, %d updated)",
                entity_id,
                message.get("state"),
                addr[0],
                len(self._entity_added_callbacks),
                len(self._entity_updated_callbacks),
            )

        except json.JSONDecodeError as err:
            _LOGGER.warning("Failed to decode JSON from %s: %s", addr[0], err)
        except (OSError, ValueError) as err:
            _LOGGER.error("Error processing message from %s: %s", addr[0], err)

    async def _cleanup_stale_entities(self) -> None:
        """Periodically cleanup old entities."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                now = datetime.now()
                cutoff = now - timedelta(
                    minutes=10
                )  # Remove entities not seen for 10 minutes

                # Remove old entities
                old_entities = [
                    entity_id
                    for entity_id, last_seen in self._last_seen.items()
                    if last_seen < cutoff
                ]

                for entity_id in old_entities:
                    self._entities.pop(entity_id, None)
                    self._last_seen.pop(entity_id, None)
                    _LOGGER.debug("Removed stale entity: %s", entity_id)

                    # Notify callbacks about removed entities
                    for cb in self._entity_removed_callbacks:
                        cb(entity_id)

            except asyncio.CancelledError:
                break
            except (OSError, ValueError) as err:
                _LOGGER.error("Error during entity cleanup: %s", err)

    def add_entity_added_callback(self, cb):
        """Add callback for when new entities are added."""
        self._entity_added_callbacks.append(cb)

    def add_entity_updated_callback(self, cb):
        """Add callback for when entities are updated."""
        self._entity_updated_callbacks.append(cb)

    def add_entity_removed_callback(self, cb):
        """Add callback for when entities are removed."""
        self._entity_removed_callbacks.append(cb)

    def add_status_changed_callback(self, cb):
        """Add callback for when status changes."""
        self._status_changed_callbacks.append(cb)

    def remove_status_changed_callback(self, cb):
        """Remove a status change callback."""
        if cb in self._status_changed_callbacks:
            self._status_changed_callbacks.remove(cb)

    def remove_entity_updated_callback(self, cb):
        """Remove an entity updated callback."""
        if cb in self._entity_updated_callbacks:
            self._entity_updated_callbacks.remove(cb)

    def _notify_status_changed(self):
        """Notify all status change callbacks."""
        for cb in self._status_changed_callbacks:
            try:
                cb()
            except RuntimeError as err:
                _LOGGER.error("Error in status changed callback: %s", err)

    @callback
    def get_entity_data(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific entity."""
        return self._entities.get(entity_id)
