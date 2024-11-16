"""Camera component for Nanit baby monitor integration."""

from __future__ import annotations

import logging

import pynanit

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nanit Camera based on a config entry."""
    client: pynanit.NanitClient = hass.data[DOMAIN][config_entry.entry_id]
    babies = await client.get_babies()
    async_add_entities(
        [NanitCamera(client, baby, baby["camera"]) for baby in babies["babies"]]
    )


class NanitCamera(Camera):
    """Implementation of a Nanit camera."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self, client: pynanit.NanitClient, baby_info: dict, camera_info: dict
    ) -> None:
        """Initialize Nanit camera."""
        super().__init__()
        camera_uid = camera_info["uid"]
        self._client = client
        self._baby_info = baby_info
        self._camera_info = camera_info
        self._attr_unique_id = f"nanit_camera_{camera_uid}"
        self._attr_name = f"Nanit Camera {baby_info.get('name', camera_uid)}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_uid)},
            model=f"Nanit Camera ({camera_info['hardware']}, {camera_info['mode']})",
            name=self._attr_name,
        )

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return self._client.get_stream_url(self._baby_info["uid"])
