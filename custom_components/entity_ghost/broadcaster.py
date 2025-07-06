"""Entity state broadcaster for UDP transmission."""

from __future__ import annotations

import json
import logging
import socket
from typing import Any

from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)


class EntityBroadcaster:
    """Handle broadcasting entity state changes via UDP."""

    def __init__(
        self,
        hass: HomeAssistant,
        entities: list[str],
        udp_port: int,
        name: str,
    ) -> None:
        """Initialize the broadcaster."""
        self.hass = hass
        self.entities = set(entities)
        self.udp_port = udp_port
        self.name = name
        self._socket: socket.socket | None = None
        self._unsub_track_state = None
        self._setup_complete = False

    async def async_setup(self) -> bool:
        """Set up the broadcaster."""
        try:
            # Create UDP socket for broadcasting
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Start tracking state changes for selected entities
            self._unsub_track_state = async_track_state_change_event(
                self.hass, list(self.entities), self._handle_state_change
            )

            self._setup_complete = True
            _LOGGER.info(
                "Entity Ghost Broadcaster '%s' started on UDP port %s, tracking %d entities",
                self.name,
                self.udp_port,
                len(self.entities),
            )

            # Send initial state for all tracked entities
            await self._broadcast_initial_states()

            return True

        except OSError as err:
            _LOGGER.error(
                "Failed to setup Entity Ghost Broadcaster '%s': %s", self.name, err
            )
            if self._socket:
                self._socket.close()
                self._socket = None
            return False

    async def _broadcast_initial_states(self) -> None:
        """Broadcast initial state of all tracked entities."""
        for entity_id in self.entities:
            state = self.hass.states.get(entity_id)
            if state:
                await self._broadcast_state_change(
                    entity_id, state.state, state.attributes
                )

    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Handle state change events."""
        if not self._setup_complete:
            return

        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")

        if entity_id in self.entities and new_state:
            # Schedule the broadcast in the event loop
            self.hass.async_create_task(
                self._broadcast_state_change(
                    entity_id, new_state.state, new_state.attributes
                )
            )

    async def _broadcast_state_change(
        self, entity_id: str, state: str, attributes: dict[str, Any]
    ) -> None:
        """Broadcast entity state change via UDP."""
        if not self._socket:
            return

        try:
            # Create broadcast message
            message = {
                "broadcaster_name": self.name,
                "entity_id": entity_id,
                "state": state,
                "attributes": attributes,
                "timestamp": self.hass.loop.time(),
            }

            # Convert to JSON and encode
            json_message = json.dumps(message, default=str)
            data = json_message.encode("utf-8")

            # Broadcast to local network
            await self.hass.async_add_executor_job(self._send_broadcast, data)

            _LOGGER.debug(
                "Broadcasted state change for %s: %s (port %s)",
                entity_id,
                state,
                self.udp_port,
            )

        except OSError as err:
            _LOGGER.error("Failed to broadcast state change for %s: %s", entity_id, err)

    def _send_broadcast(self, data: bytes) -> None:
        """Send UDP broadcast message."""
        try:
            # Broadcast to local network
            self._socket.sendto(data, ("<broadcast>", self.udp_port))

            # Also send to localhost for testing
            self._socket.sendto(data, ("127.0.0.1", self.udp_port))

        except OSError as err:
            _LOGGER.error("Failed to send UDP broadcast: %s", err)

    async def async_update_entities(self, entities: list[str]) -> None:
        """Update the list of entities to track."""
        old_entities = self.entities
        self.entities = set(entities)

        _LOGGER.info(
            "Updated entity list for Entity Ghost Broadcaster '%s': %d entities",
            self.name,
            len(self.entities),
        )

        # Broadcast initial states for newly added entities
        new_entities = self.entities - old_entities
        for entity_id in new_entities:
            state = self.hass.states.get(entity_id)
            if state:
                await self._broadcast_state_change(
                    entity_id, state.state, state.attributes
                )

    async def async_update_port(self, udp_port: int) -> bool:
        """Update the UDP port."""
        if self.udp_port == udp_port:
            return True

        old_port = self.udp_port
        self.udp_port = udp_port

        _LOGGER.info(
            "Updated UDP port for Entity Ghost Broadcaster '%s': %d -> %d",
            self.name,
            old_port,
            udp_port,
        )

        return True

    async def async_shutdown(self) -> None:
        """Shutdown the broadcaster."""
        if self._unsub_track_state:
            self._unsub_track_state()
            self._unsub_track_state = None

        if self._socket:
            self._socket.close()
            self._socket = None

        self._setup_complete = False

        _LOGGER.info("Entity Ghost Broadcaster '%s' shutdown complete", self.name)
