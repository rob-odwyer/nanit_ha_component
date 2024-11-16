"""The Nanit integration."""

from __future__ import annotations

import pynanit

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.CAMERA]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanit from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create API client
    client = pynanit.NanitClient(
        async_get_clientsession(hass),
        access_token=entry.data["access_token"],
        refresh_token=entry.data["refresh_token"],
    )

    # Store an API client for your platforms to access
    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
