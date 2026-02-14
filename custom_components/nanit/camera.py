"""Camera component for Nanit baby monitor integration."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NanitCoordinator, BabyMeta
from .nanit_client import NanitClient
from .const import CLIENT, COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nanit Camera based on a config entry."""

    _LOGGER.info("Setting up Nanit cameras")
    coordinator: NanitCoordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    client = hass.data[DOMAIN][config_entry.entry_id][CLIENT]

    async_add_entities(
        [NanitCamera(coordinator, client, baby) for baby in coordinator.data.babies.values()]
    )


class NanitCamera(CoordinatorEntity[NanitCoordinator], Camera):
    """Implementation of a Nanit camera."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "Nanit"

    def __init__(self, coordinator: NanitCoordinator, client, baby_meta: BabyMeta) -> None:
        """Initialize Nanit camera."""
        super().__init__(coordinator)
        Camera.__init__(self)

        _LOGGER.info("Setting up nanit camera with baby_uid: %s", baby_meta.baby_uid)

        camera_info = baby_meta.camera
        camera_uid = camera_info.camera_uid
        self._coordinator = coordinator
        self._client: NanitClient = client
        self._baby_uid = baby_meta.baby_uid
        self._camera_info = camera_info
        self._attr_unique_id = f"{baby_meta.baby_uid}_camera_${camera_uid}"
        self._attr_name = f"Nanit Camera {baby_meta.name}"
        self._attr_device_info = baby_meta.device_info
        self._attr_model = camera_info.hardware
        self._attr_is_streaming = baby_meta.connection_status.connected
        self._cached_image: bytes | None = None
        self._cached_thumbnail_url: str | None = baby_meta.thumbnail_url

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.info("Handling updated data for camera id: %s", self._attr_unique_id)
        if self._baby_uid in self.coordinator.data.babies:
            baby = self.coordinator.data.babies[self._baby_uid]
            self._attr_is_streaming = baby.connection_status.connected
            # Invalidate cached image when the thumbnail URL changes
            if baby.thumbnail_url != self._cached_thumbnail_url:
                _LOGGER.info(
                    "Thumbnail URL changed for baby %s, clearing cached image", self._baby_uid
                )
                self._cached_image = None
                self._cached_thumbnail_url = baby.thumbnail_url
        self.async_write_ha_state()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the latest thumbnail image from the Nanit API."""
        if self._cached_image is not None:
            return self._cached_image

        if self._cached_thumbnail_url is None:
            return None

        try:
            self._cached_image = await self._client.get_thumbnail(self._cached_thumbnail_url)
            return self._cached_image
        except Exception:
            _LOGGER.warning("Failed to fetch thumbnail image for baby %s", self._baby_uid)
            return None

    async def stream_source(self) -> str:
        """Return the source of the stream."""
        url = self._coordinator.get_stream_url(self._baby_uid)
        _LOGGER.info("Got stream URL: %s", url)
        return url
