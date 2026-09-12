"""Entity state broadcaster for UDP transmission."""

from __future__ import annotations

import json
import logging
import socket
import asyncio
from typing import Any

from homeassistant.core import EVENT_STATE_CHANGED, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

_STATE_ATTRIBUTE_KEYS = {
    "friendly_name",
    "device_class",
    "unit_of_measurement",
    "state_class",
    "icon",
    "entity_category",
}
_MAX_UDP_PAYLOAD = 65507


class EntityBroadcaster:
    """Handle broadcasting entity state changes via UDP."""

    def __init__(
        self,
        hass: HomeAssistant,
        integrations: list[str],
        udp_port: int,
        name: str,
    ) -> None:
        """Initialize the broadcaster."""
        self.hass = hass
        self.integrations = set(integrations)
        self.entities: set[str] = set()
        self.udp_port = udp_port
        self.name = name
        self._socket: socket.socket | None = None
        self._command_socket: socket.socket | None = None
        self._command_task: asyncio.Task | None = None
        self._unsub_track_state = None
        self._setup_complete = False

    async def async_setup(self) -> bool:
        """Set up the broadcaster."""
        try:
            # Create UDP socket for broadcasting
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            await self._async_refresh_entities()

            self._command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._command_socket.setblocking(False)
            self._command_socket.bind(("", self.udp_port))
            self._command_task = self.hass.async_create_task(
                self._listen_for_commands()
            )

            # Track all state changes and filter against the current registry.
            self._unsub_track_state = self.hass.bus.async_listen(
                EVENT_STATE_CHANGED, self._handle_state_change
            )

            self._setup_complete = True
            _LOGGER.debug(
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
            if self._command_socket:
                self._command_socket.close()
                self._command_socket = None
            return False

    async def _broadcast_initial_states(self) -> None:
        """Broadcast initial state of all tracked entities."""
        for entity_id in self.entities:
            state = self.hass.states.get(entity_id)
            if state:
                await self._broadcast_state_change(
                    entity_id, state.state, state.attributes
                )

    async def _async_refresh_entities(self) -> None:
        """Refresh entities belonging to the selected integrations."""
        registry = er.async_get(self.hass)
        config_entry_domains = {
            entry.entry_id: entry.domain
            for integration in self.integrations
            for entry in self.hass.config_entries.async_entries(integration)
        }
        self.entities = {
            entity.entity_id
            for entity in registry.entities.values()
            if (
                config_entry_domains.get(entity.config_entry_id) in self.integrations
                or entity.entity_id.split(".", 1)[0] in self.integrations
            )
        }

    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Handle state change events."""
        if not self._setup_complete:
            return

        self.hass.async_create_task(self._async_handle_state_change(event))

    async def _async_handle_state_change(self, event: Event) -> None:
        """Refresh integration entities and broadcast a changed state."""
        await self._async_refresh_entities()

        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        if new_state and entity_id in self.entities:
            await self._broadcast_state_change(
                entity_id, new_state.state, new_state.attributes
            )

    async def _listen_for_commands(self) -> None:
        """Listen for commands from receivers."""
        if not self._command_socket:
            return

        while True:
            try:
                data, addr = await self.hass.loop.sock_recvfrom(
                    self._command_socket, 4096
                )
                _LOGGER.debug(
                    "Received UDP command datagram from %s:%s (%d bytes)",
                    addr[0],
                    addr[1],
                    len(data),
                )
                await self._process_command(data, addr)
            except asyncio.CancelledError:
                return
            except OSError as err:
                if self._command_socket:
                    _LOGGER.error("Error receiving Entity Ghost command: %s", err)
                return

    async def _process_command(self, data: bytes, addr: tuple[str, int]) -> None:
        """Validate and execute a command from a receiver."""
        try:
            message = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _LOGGER.warning("Ignored malformed Entity Ghost command from %s", addr[0])
            return

        if message.get("message_type") != "command":
            return

        entity_id = message.get("entity_id")
        action = message.get("action")
        if not isinstance(entity_id, str) or not isinstance(action, str):
            _LOGGER.warning("Ignored incomplete Entity Ghost command from %s", addr[0])
            return

        await self._async_refresh_entities()
        if entity_id not in self.entities:
            _LOGGER.warning(
                "Ignored command for non-selected Entity Ghost entity %s from %s",
                entity_id,
                addr[0],
            )
            return

        if entity_id.split(".", 1)[0] != "switch" or action not in (
            "turn_on",
            "turn_off",
        ):
            _LOGGER.warning(
                "Ignored unsupported Entity Ghost command %s for %s from %s",
                action,
                entity_id,
                addr[0],
            )
            return

        _LOGGER.debug(
            "Executing validated UDP command from %s:%s: %s for %s",
            addr[0],
            addr[1],
            action,
            entity_id,
        )
        await self.hass.services.async_call(
            "switch",
            action,
            {"entity_id": entity_id},
            blocking=False,
        )

    async def _broadcast_state_change(
        self, entity_id: str, state: str, attributes: dict[str, Any]
    ) -> None:
        """Broadcast entity state change via UDP."""
        if not self._socket:
            return

        try:
            filtered_attributes = {
                key: value
                for key, value in attributes.items()
                if key in _STATE_ATTRIBUTE_KEYS
            }
            registry_entity = er.async_get(self.hass).async_get(entity_id)
            if registry_entity and registry_entity.icon:
                filtered_attributes["icon"] = registry_entity.icon

            # Create broadcast message
            message = {
                "message_type": "state",
                "broadcaster_name": self.name,
                "entity_id": entity_id,
                "domain": entity_id.split(".", 1)[0],
                "state": state,
                "attributes": filtered_attributes,
                "timestamp": self.hass.loop.time(),
            }

            # Convert to JSON and encode
            json_message = json.dumps(message, default=str)
            data = json_message.encode("utf-8")
            if len(data) > _MAX_UDP_PAYLOAD:
                _LOGGER.warning(
                    "Skipped oversized Entity Ghost state for %s (%d bytes)",
                    entity_id,
                    len(data),
                )
                return

            # Broadcast to local network
            _LOGGER.debug(
                "Sending UDP state message for %s to broadcast:%s (%d bytes)",
                entity_id,
                self.udp_port,
                len(data),
            )
            _LOGGER.debug(
                "Sending UDP state message for %s to 127.0.0.1:%s (%d bytes)",
                entity_id,
                self.udp_port,
                len(data),
            )
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

    async def async_update_integrations(self, integrations: list[str]) -> None:
        """Update the integrations whose entities are broadcast."""
        old_entities = self.entities
        self.integrations = set(integrations)
        await self._async_refresh_entities()

        _LOGGER.debug(
            "Updated integrations for Entity Ghost Broadcaster '%s': %d integrations, %d entities",
            self.name,
            len(self.integrations),
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

    async def async_update_name(self, name: str) -> None:
        """Update the broadcaster name."""
        if self.name == name:
            return

        old_name = self.name
        self.name = name

        _LOGGER.debug(
            "Updated Entity Ghost Broadcaster name: %s -> %s",
            old_name,
            self.name,
        )

    async def async_update_port(self, udp_port: int) -> bool:
        """Update the UDP port and rebind the command socket."""
        if self.udp_port == udp_port:
            return True

        # Bind the new socket first so a failure leaves the broadcaster intact.
        try:
            new_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            new_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            new_socket.setblocking(False)
            new_socket.bind(("", udp_port))
        except OSError as err:
            _LOGGER.error(
                "Failed to bind Entity Ghost command socket to port %s: %s",
                udp_port,
                err,
            )
            return False

        old_port = self.udp_port
        self.udp_port = udp_port

        if self._command_task:
            self._command_task.cancel()
            try:
                await self._command_task
            except asyncio.CancelledError:
                pass
        if self._command_socket:
            self._command_socket.close()

        self._command_socket = new_socket
        self._command_task = self.hass.async_create_task(self._listen_for_commands())

        _LOGGER.debug(
            "Updated UDP port for Entity Ghost Broadcaster '%s': %d -> %d",
            self.name,
            old_port,
            udp_port,
        )

        return True

    async def async_shutdown(self) -> None:
        """Shutdown the broadcaster."""
        if self._command_task:
            self._command_task.cancel()
            try:
                await self._command_task
            except asyncio.CancelledError:
                pass
            self._command_task = None

        if self._unsub_track_state:
            self._unsub_track_state()
            self._unsub_track_state = None

        if self._socket:
            self._socket.close()
            self._socket = None

        if self._command_socket:
            self._command_socket.close()
            self._command_socket = None

        self._setup_complete = False

        _LOGGER.debug("Entity Ghost Broadcaster '%s' shutdown complete", self.name)
