"""Config flow for Entity Ghost integration."""

from __future__ import annotations

import logging
import socket
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    MODE_BROADCASTER,
    MODE_RECEIVER,
    CONF_MODE,
    CONF_ENTITIES,
    CONF_UDP_PORT,
    CONF_NAME,
    CONF_BROADCASTER_NAME,
    DEFAULT_UDP_PORT,
    MIN_UDP_PORT,
    MAX_UDP_PORT,
    DEFAULT_BROADCASTER_NAME,
)

_LOGGER = logging.getLogger(__name__)


class EntityGhostConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entity Ghost."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._mode: str = ""
        self._entities: list[str] = []
        self._udp_port: int = DEFAULT_UDP_PORT
        self._name: str = ""
        self._broadcaster_name: str = DEFAULT_BROADCASTER_NAME

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose mode."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._mode = user_input[CONF_MODE]

            if self._mode == MODE_BROADCASTER:
                return await self.async_step_broadcaster()
            elif self._mode == MODE_RECEIVER:
                return await self.async_step_receiver()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MODE): vol.In(
                    {
                        MODE_BROADCASTER: "Broadcaster (Send entity states)",
                        MODE_RECEIVER: "Receiver (Receive entity states)",
                    }
                )
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_broadcaster(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle broadcaster configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._entities = user_input.get(CONF_ENTITIES, [])
            self._udp_port = user_input[CONF_UDP_PORT]
            self._name = user_input[CONF_NAME]

            # Validate entities are selected
            if not self._entities:
                errors[CONF_ENTITIES] = "no_entities_selected"

            # Validate port is not in use
            if not errors:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("", self._udp_port))
                    sock.close()
                except OSError:
                    errors[CONF_UDP_PORT] = "port_in_use"

            if not errors:
                # Create unique ID
                await self.async_set_unique_id(f"{DOMAIN}_broadcaster_{self._udp_port}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Entity Ghost Broadcaster - {self._name}",
                    data={
                        CONF_MODE: MODE_BROADCASTER,
                        CONF_ENTITIES: self._entities,
                        CONF_UDP_PORT: self._udp_port,
                        CONF_NAME: self._name,
                    },
                )

        # Get available entities
        entity_registry = async_get_entity_registry(self.hass)
        entity_options = {}

        for entity in entity_registry.entities.values():
            if entity.entity_id.startswith(
                ("sensor.", "binary_sensor.", "switch.", "light.")
            ):
                friendly_name = entity.original_name or entity.entity_id
                entity_options[entity.entity_id] = (
                    f"{entity.entity_id} ({friendly_name})"
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ENTITIES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": entity_id, "label": name}
                            for entity_id, name in sorted(entity_options.items())
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_UDP_PORT, default=DEFAULT_UDP_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_UDP_PORT, max=MAX_UDP_PORT)
                ),
                vol.Required(CONF_NAME, default="Entity Ghost Broadcaster"): cv.string,
            }
        )

        return self.async_show_form(
            step_id="broadcaster",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle receiver configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._udp_port = user_input[CONF_UDP_PORT]
            self._broadcaster_name = user_input[CONF_BROADCASTER_NAME]

            # Validate port is not in use
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("", self._udp_port))
                sock.close()
            except OSError:
                errors[CONF_UDP_PORT] = "port_in_use"

            if not errors:
                # Create unique ID
                await self.async_set_unique_id(f"{DOMAIN}_receiver_{self._udp_port}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Entity Ghost Receiver (Port {self._udp_port})",
                    data={
                        CONF_MODE: MODE_RECEIVER,
                        CONF_UDP_PORT: self._udp_port,
                        CONF_BROADCASTER_NAME: self._broadcaster_name,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_UDP_PORT, default=DEFAULT_UDP_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_UDP_PORT, max=MAX_UDP_PORT)
                ),
                vol.Optional(
                    CONF_BROADCASTER_NAME, default=DEFAULT_BROADCASTER_NAME
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="receiver",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return EntityGhostOptionsFlowHandler(config_entry)


class EntityGhostOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Entity Ghost."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle options flow."""
        mode = self.config_entry.data[CONF_MODE]

        if mode == MODE_BROADCASTER:
            return await self.async_step_broadcaster_options(user_input)
        elif mode == MODE_RECEIVER:
            return await self.async_step_receiver_options(user_input)

    async def async_step_broadcaster_options(self, user_input=None) -> FlowResult:
        """Handle broadcaster options flow."""
        errors = {}

        if user_input is not None:
            # Validate entities are selected
            entities = user_input.get(CONF_ENTITIES, [])
            if not entities:
                errors[CONF_ENTITIES] = "no_entities_selected"

            # Validate port if changed
            port = user_input.get(CONF_UDP_PORT, self.config_entry.data[CONF_UDP_PORT])
            if port != self.config_entry.data[CONF_UDP_PORT]:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("", port))
                    sock.close()
                except OSError:
                    errors[CONF_UDP_PORT] = "port_in_use"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Get available entities
        entity_registry = async_get_entity_registry(self.hass)
        entity_options = {}

        for entity in entity_registry.entities.values():
            if entity.entity_id.startswith(
                ("sensor.", "binary_sensor.", "switch.", "light.")
            ):
                friendly_name = entity.original_name or entity.entity_id
                entity_options[entity.entity_id] = (
                    f"{entity.entity_id} ({friendly_name})"
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENTITIES,
                    default=self.config_entry.options.get(
                        CONF_ENTITIES, self.config_entry.data.get(CONF_ENTITIES, [])
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": entity_id, "label": name}
                            for entity_id, name in sorted(entity_options.items())
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_UDP_PORT,
                    default=self.config_entry.options.get(
                        CONF_UDP_PORT, self.config_entry.data[CONF_UDP_PORT]
                    ),
                ): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_UDP_PORT, max=MAX_UDP_PORT)
                ),
                vol.Required(
                    CONF_NAME,
                    default=self.config_entry.options.get(
                        CONF_NAME,
                        self.config_entry.data.get(
                            CONF_NAME, "Entity Ghost Broadcaster"
                        ),
                    ),
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="broadcaster_options",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_receiver_options(self, user_input=None) -> FlowResult:
        """Handle receiver options flow."""
        errors = {}

        if user_input is not None:
            # Validate port if changed
            port = user_input.get(CONF_UDP_PORT, self.config_entry.data[CONF_UDP_PORT])

            if port != self.config_entry.data[CONF_UDP_PORT]:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("", port))
                    sock.close()
                except OSError:
                    errors[CONF_UDP_PORT] = "port_in_use"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_UDP_PORT,
                    default=self.config_entry.options.get(
                        CONF_UDP_PORT, self.config_entry.data[CONF_UDP_PORT]
                    ),
                ): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_UDP_PORT, max=MAX_UDP_PORT)
                ),
                vol.Optional(
                    CONF_BROADCASTER_NAME,
                    default=self.config_entry.options.get(
                        CONF_BROADCASTER_NAME,
                        self.config_entry.data.get(
                            CONF_BROADCASTER_NAME, DEFAULT_BROADCASTER_NAME
                        ),
                    ),
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="receiver_options",
            data_schema=data_schema,
            errors=errors,
        )
