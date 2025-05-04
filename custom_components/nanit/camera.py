"""Camera component for Nanit baby monitor integration."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NanitCoordinator, BabyMeta
from .const import COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nanit Camera based on a config entry."""

    _LOGGER.info("Setting up Nanit cameras")
    coordinator: NanitCoordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    async_add_entities([NanitCamera(coordinator, baby) for baby in coordinator.data.babies.values()])


class NanitCamera(CoordinatorEntity[NanitCoordinator], Camera):
    """Implementation of a Nanit camera."""

    _attr_supported_features = CameraEntityFeature.STREAM
    use_stream_for_stills = True
    _attr_brand = "Nanit"
    _attr_is_streaming = True

    def __init__(self, coordinator: NanitCoordinator, baby_meta: BabyMeta) -> None:
        """Initialize Nanit camera."""
        super().__init__(coordinator)
        Camera.__init__(self)

        _LOGGER.info("Setting up nanit camera with baby_uid: %s", baby_meta.baby_uid)

        camera_info = baby_meta.camera
        camera_uid = camera_info.camera_uid
        self._coordinator = coordinator
        self._baby_uid = baby_meta.baby_uid
        self._camera_info = camera_info
        self._attr_unique_id = f"{baby_meta.baby_uid}_camera_${camera_uid}"
        self._attr_name = f"Nanit Camera {baby_meta.name}"
        self._attr_device_info = baby_meta.device_info
        self._attr_model = camera_info.hardware

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.info("Handling updated data for camera id: %s", self._attr_unique_id)
        if self._baby_uid in self.coordinator.data.babies:
            _LOGGER.info("Found data for camera with baby_uid: %s", self._baby_uid)
            # We don't actually have anything to update here yet - the stream source URL requires only baby UID + current auth token

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return self._coordinator.get_stream_url(self._baby_uid)
