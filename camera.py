"""Camera component for Nanit baby monitor integration."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NanitCoordinator
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

    async_add_entities([NanitCamera(coordinator, baby) for baby in coordinator.babies["babies"]])


class NanitCamera(CoordinatorEntity[NanitCoordinator], Camera):
    """Implementation of a Nanit camera."""

    _attr_supported_features = CameraEntityFeature.STREAM
    use_stream_for_stills = True

    def __init__(self, coordinator: NanitCoordinator, baby_info: dict) -> None:
        """Initialize Nanit camera."""
        super().__init__(coordinator)
        Camera.__init__(self)

        _LOGGER.info("Setting up nanit camera with ID: %s", baby_info["uid"])

        camera_info = baby_info["camera"]
        camera_uid = camera_info["uid"]
        self._coordinator = coordinator
        self._baby_info = baby_info
        self._camera_info = camera_info
        self._attr_unique_id = f"nanit_camera_{camera_uid}"
        self._attr_name = f"Nanit Camera {baby_info.get('name', camera_uid)}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_uid)},
            model=f"Nanit Camera ({camera_info['hardware']}, {camera_info['mode']})",
            name=self._attr_name,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.info("Handling updated data for camera", extra={"unique_id": self._attr_unique_id})
        for baby_info in self._coordinator.babies["babies"]:
            _LOGGER.info("Found data for camera", extra={"unique_id": self._attr_unique_id})
            # Replace current baby info with the matching one from the coordinator
            if baby_info["uid"] == self._baby_info["uid"]:
                self._baby_info = baby_info
                self.async_write_ha_state()
                break

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return self._coordinator.get_stream_url(self._baby_info["uid"])
