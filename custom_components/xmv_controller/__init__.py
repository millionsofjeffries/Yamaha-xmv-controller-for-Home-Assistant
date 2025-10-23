"""The XMV Controller integration."""
from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import AmplifierClient

from .const import (
    CONF_CHANNELS, CONF_HOST, CONF_MAX_DB, CONF_MIN_DB, CONF_PORT, DOMAIN
)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up XMV Controller from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    config = entry.options or entry.data
    
    api_client = AmplifierClient(
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        min_db=config[CONF_MIN_DB],
        max_db=config[CONF_MAX_DB],
    )

    api_client.start()

    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": api_client,
        "channels": config[CONF_CHANNELS]
    }
    
    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        api_client: AmplifierClient = data["api_client"]
        await api_client.disconnect()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.info("Configuration options updated, reloading XMV Controller integration")
    await hass.config_entries.async_reload(entry.entry_id)