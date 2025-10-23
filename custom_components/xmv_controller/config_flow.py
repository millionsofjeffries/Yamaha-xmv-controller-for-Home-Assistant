"""Config flow for XMV Controller integration."""
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import AmplifierClient
from .const import (
    CONF_CHANNELS, CONF_HOST, CONF_MAX_DB, CONF_MIN_DB, CONF_PORT,
    DEFAULT_CHANNELS, DEFAULT_HOST, DEFAULT_MAX_DB, DEFAULT_MIN_DB, DEFAULT_PORT, DOMAIN
)

_LOGGER = logging.getLogger(__name__)


def build_schema(config: dict) -> vol.Schema:
    """Build the configuration schema with defaults from existing config."""
    channels_str = ",".join([f"{k}:{v}" for k, v in config.get(CONF_CHANNELS, {}).items()])
    if not channels_str:
        channels_str = DEFAULT_CHANNELS

    return vol.Schema({
        vol.Required(CONF_HOST, default=config.get(CONF_HOST, DEFAULT_HOST)): str,
        vol.Required(CONF_PORT, default=config.get(CONF_PORT, DEFAULT_PORT)): int,
        vol.Required(CONF_CHANNELS, default=channels_str): str,
        vol.Required(CONF_MIN_DB, default=config.get(CONF_MIN_DB, DEFAULT_MIN_DB)): int,
        vol.Required(CONF_MAX_DB, default=config.get(CONF_MAX_DB, DEFAULT_MAX_DB)): int,
    })


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect and parse channels."""
    # Test the connection using the new static method
    if not await AmplifierClient.test_connection(data[CONF_HOST], data[CONF_PORT]):
        raise CannotConnect

    # Validate and parse the channels string
    parsed_channels = {}
    try:
        channel_pairs = data[CONF_CHANNELS].split(",")
        for pair in channel_pairs:
            if ":" not in pair:
                raise ValueError("Channel pair missing ':' separator")
            channel_id, name = pair.split(":", 1)
            parsed_channels[channel_id.strip()] = name.strip()
        if not parsed_channels:
            raise ValueError("No channels were defined")
    except Exception as exc:
        _LOGGER.error("Error parsing channels: %s", exc)
        raise InvalidChannels from exc

    # Return the validated and formatted data
    return {
        CONF_HOST: data[CONF_HOST],
        CONF_PORT: data[CONF_PORT],
        CONF_MIN_DB: data[CONF_MIN_DB],
        CONF_MAX_DB: data[CONF_MAX_DB],
        CONF_CHANNELS: parsed_channels,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for XMV Controller."""
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "OptionsFlowHandler":
        return OptionsFlowHandler()

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                validated_data = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=validated_data
                )
            except CannotConnect: errors["base"] = "cannot_connect"
            except InvalidChannels: errors["base"] = "invalid_channels"
            except Exception: errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=build_schema({}), errors=errors
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for XMV Controller."""

    # --- THE DEPRECATED __init__ METHOD IS NOW REMOVED ---

    async def async_step_init(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        errors: Dict[str, str] = {}
        
        # self.config_entry is automatically provided by Home Assistant
        current_config = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            try:
                validated_data = await validate_input(self.hass, user_input)
                return self.async_create_entry(title="", data=validated_data)
            except CannotConnect: errors["base"] = "cannot_connect"
            except InvalidChannels: errors["base"] = "invalid_channels"
            except Exception: errors["base"] = "unknown"
        
        return self.async_show_form(
            step_id="init",
            data_schema=build_schema(current_config),
            errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
class InvalidChannels(HomeAssistantError):
    """Error to indicate channels are formatted incorrectly."""