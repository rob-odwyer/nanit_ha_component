"""The Nanit integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from dataclasses import dataclass

import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .nanit_client import NanitClient, NanitAPIError, NanitUnauthorizedError
from .const import ACCESS_TOKEN, CLIENT, COORDINATOR, DOMAIN, REFRESH_TOKEN

PLATFORMS: list[Platform] = [Platform.CAMERA, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanit from a config entry."""
    _LOGGER.info("Setting up Nanit integration")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    # Create API client and store it in the entry data
    client = NanitClient(
        async_get_clientsession(hass),
        access_token=entry.data[ACCESS_TOKEN],
        refresh_token=entry.data[REFRESH_TOKEN],
    )
    hass.data[DOMAIN][entry.entry_id][CLIENT] = client

    # Create the coordinator for refreshing from the API and store in the entry data
    coordinator = NanitCoordinator(hass, entry, client)
    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@dataclass
class Camera:
    camera_uid: str
    hardware: str
    mode: str


@dataclass
class LatestEvent:
    key: str
    time: float


@dataclass
class ConnectionStatus:
    connected: bool


@dataclass
class BabyMeta:
    baby_uid: str
    camera: Camera
    name: str
    latest_event: LatestEvent
    connection_status: ConnectionStatus
    device_info: DeviceInfo
    thumbnail_url: str | None = None


@dataclass
class NanitData:
    """Container for cached data from the Nanit API."""

    babies: dict[str, BabyMeta]


class NanitCoordinator(DataUpdateCoordinator[NanitData]):
    """Data update coordinator for refreshing data from the Nanit REST API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, client: NanitClient) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Nanit Camera",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=60),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True,
        )
        self._config_entry = config_entry
        self._client = client

    async def _async_setup(self):
        """Set up your coordinator, or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        _LOGGER.info("Setting up Nanit initial data")
        await self._async_update_data()

    async def _async_update_data(self) -> NanitData:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            try:
                return await self._update_babies()
            except NanitUnauthorizedError:
                _LOGGER.warning(
                    "Got HTTP 401 Unauthorized from Nanit API, attempting to refresh token"
                )
                # Fetch a new access token using the refresh token
                # This should mean that the credentials never expire, as long as HA is running this regularly
                access_token, refresh_token = await self._client.refresh_session()

                # FIXME: remove
                _LOGGER.info(
                    "New Nanit API tokens: access_token=%s, refresh_token=%s",
                    access_token,
                    refresh_token,
                )

                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={
                        **self._config_entry.data,
                        ACCESS_TOKEN: access_token,
                        REFRESH_TOKEN: refresh_token,
                    },
                )

                _LOGGER.info(
                    "Successfully refreshed Nanit API token, retrying update",
                )
                return await self._update_babies()

        except NanitUnauthorizedError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except NanitAPIError as err:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            _LOGGER.warning("Error fetching data from Nanit API: %s", err)
            raise err

    async def _update_babies(self) -> NanitData:
        _LOGGER.info(
            "Refreshing data from Nanit API",
        )

        # FIXME: remove
        _LOGGER.info("Nanit access token: %s", self._client._access_token)
        _LOGGER.info("Nanit refresh token: %s", self._client._refresh_token)

        async with async_timeout.timeout(30):
            babies = await self._client.get_babies()

            baby_metas = {}
            for baby in babies["babies"]:
                baby_uid = baby["uid"]

                latest_event = await self._client.get_latest_event(baby_uid)

                camera_info = baby["camera"]
                camera_uid = camera_info["uid"]
                connection_status_response = await self._client.get_connection_status(camera_uid)

                camera = Camera(
                    camera_uid,
                    camera_info.get("hardware", "Unknown hardware"),
                    camera_info.get("mode", "Unknown mode"),
                )

                device_info = DeviceInfo(
                    identifiers={(DOMAIN, baby_uid)},
                    manufacturer="Nanit",
                    name=baby.get("name", baby_uid),
                    model=camera.hardware,
                    serial_number=camera_uid,
                    hw_version=camera_info.get("hardware"),
                    sw_version=camera_info.get("version"),
                )

                # Fetch thumbnail from stats/latest, but only when the latest event has changed
                thumbnail_url = None
                current_event_time = latest_event.get("time", 0)
                previous_baby = self.data.babies.get(baby_uid) if self.data else None
                previous_event_time = previous_baby.latest_event.time if previous_baby else None

                if previous_event_time != current_event_time:
                    _LOGGER.info(
                        "Latest event changed for baby %s, fetching new thumbnail", baby_uid
                    )
                    try:
                        stats = await self._client.get_stats_latest(baby_uid)
                        latest_stats = stats.get("latest", {})
                        media_urls = latest_stats.get("media_urls", {})
                        thumbnail_url = media_urls.get("thumbnail")
                        _LOGGER.info(f"Thumbnail URL set to {thumbnail_url}")
                    except NanitAPIError:
                        _LOGGER.warning("Failed to fetch stats/latest for baby %s", baby_uid)
                else:
                    # Keep the previous thumbnail URL
                    thumbnail_url = previous_baby.thumbnail_url if previous_baby else None

                baby_meta = BabyMeta(
                    baby_uid=baby_uid,
                    camera=camera,
                    name=baby.get("name", baby_uid),
                    latest_event=LatestEvent(
                        key=latest_event.get("key", "UNKNOWN"), time=current_event_time
                    ),
                    connection_status=ConnectionStatus(
                        connected=connection_status_response.get("connected", False),
                    ),
                    device_info=device_info,
                    thumbnail_url=thumbnail_url,
                )
                baby_metas[baby_meta.baby_uid] = baby_meta

            return NanitData(babies=baby_metas)

    def get_stream_url(self, baby_uid: str) -> str:
        _LOGGER.info(
            f"Getting stream URL for baby_uid={baby_uid}",
        )
        return self._client.get_stream_url(baby_uid)
