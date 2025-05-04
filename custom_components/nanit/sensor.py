"""Sensor components for Nanit baby monitor integration."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NanitCoordinator, BabyMeta
from .const import COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

LATEST_EVENT_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="latest_event",
    device_class=SensorDeviceClass.ENUM,
    has_entity_name=True,
    name="Latest Event",
    state_class=None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nanit sensor based on a config entry."""

    _LOGGER.info("Setting up Nanit sensors")
    coordinator: NanitCoordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    async_add_entities(
        [
            NanitLatestEventSensor(coordinator, baby_meta)
            for baby_meta in coordinator.data.babies.values()
        ]
    )


class NanitLatestEventSensor(CoordinatorEntity[NanitCoordinator], SensorEntity):
    """
    Implementation of a Nanit sensor that exposes the latest event for a baby as the current status.

    Example state stored in coordinator.latest_events:
    {
        "xyz": {
            "key": "FELL_ASLEEP",
            "time": 1742446401.241,
            "updated_at": 1742448984
        }
    }
    """

    entity_description = LATEST_EVENT_SENSOR_DESCRIPTION

    def __init__(
        self, coordinator: NanitCoordinator, baby_meta: BabyMeta
    ) -> None:
        """Initialize Nanit latest event sensor."""
        super().__init__(coordinator)

        _LOGGER.info(
            "Setting up nanit latest event sensor for baby_uid: %s with data: %s",
            baby_meta.baby_uid,
            baby_meta.latest_event,
        )

        self._baby_uid = baby_meta.baby_uid
        self._attr_unique_id = f"{baby_meta.baby_uid}_latest_event"
        self._attr_native_value = baby_meta.latest_event.key
        self._attr_device_info = baby_meta.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.info("Handling updated data for latest event sensor for baby_uid: %s", self._baby_uid)
        if self._baby_uid in self.coordinator.data.babies:
            self._attr_native_value = self.coordinator.data.babies[self._baby_uid].latest_event.key
            self.async_write_ha_state()
