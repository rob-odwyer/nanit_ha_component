"""The Nanit integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
import pynanit

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import ACCESS_TOKEN, CLIENT, COORDINATOR, DOMAIN, REFRESH_TOKEN

PLATFORMS: list[Platform] = [Platform.CAMERA]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanit from a config entry."""
    _LOGGER.info("Setting up Nanit integration")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    # Create API client and store it in the entry data
    client = pynanit.NanitClient(
        async_get_clientsession(hass),
        access_token=entry.data[ACCESS_TOKEN],
        refresh_token=entry.data[REFRESH_TOKEN],
    )
    hass.data[DOMAIN][entry.entry_id][CLIENT] = client

    # Create the coordinator for refreshing from the API and store in the entry data
    coordinator = NanitCoordinator(hass, client)
    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NanitCoordinator(DataUpdateCoordinator):
    """Data update coordinator for refreshing data from the Nanit REST API."""

    def __init__(self, hass: HomeAssistant, client: pynanit.NanitClient) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Nanit Camera",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True,
        )
        self._client = client
        self.babies = []

    async def _async_setup(self):
        """Set up your coordinator, or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        _LOGGER.info("Setting up Nanit initial data")
        await self._async_update_data()

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            try:
                _LOGGER.info(
                    "Refreshing data from Nanit API",
                )
                async with async_timeout.timeout(10):
                    self.babies = await self._client.get_babies()
                    return

            # FIXME:
            # except pynanit.NanitUnauthorizedError:
            except pynanit.NanitAPIError:
                _LOGGER.warning(
                    "Got HTTP 401 Unauthorized from Nanit API, attempting to refresh token"
                )
                # Fetch a new access token using the refresh token
                # This should mean that the credentials never expire, as long as HA is running this regularly
                await self._client.refresh_session()
                _LOGGER.info(
                    "Successfully refreshed Nanit API token, retrying request",
                )
                self.babies = await self._client.get_babies()

        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        except pynanit.NanitAPIError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err

    def get_stream_url(self, baby_uid: str) -> str:
        return self._client.get_stream_url(baby_uid)
