"""Sensor components for Nanit baby monitor integration."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
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

CONNECTION_STATUS_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="connection_status",
    device_class=SensorDeviceClass.ENUM,
    has_entity_name=True,
    name="Connection Status",
    state_class=None,
    entity_category=EntityCategory.DIAGNOSTIC,
)

LAST_SEEN_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="last_seen",
    device_class=SensorDeviceClass.TIMESTAMP,
    has_entity_name=True,
    name="Last Seen",
    state_class=None,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nanit sensor based on a config entry."""

    _LOGGER.info("Setting up Nanit sensors")
    coordinator: NanitCoordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    for baby_meta in coordinator.data.babies.values():
        entities.append(NanitLatestEventSensor(coordinator, baby_meta))
        entities.append(NanitConnectionStatusSensor(coordinator, baby_meta))
        entities.append(NanitLastSeenSensor(coordinator, baby_meta))

    async_add_entities(entities)


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

    def __init__(self, coordinator: NanitCoordinator, baby_meta: BabyMeta) -> None:
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
        _LOGGER.info(
            "Handling updated data for latest event sensor for baby_uid: %s", self._baby_uid
        )
        if self._baby_uid in self.coordinator.data.babies:
            self._attr_native_value = self.coordinator.data.babies[self._baby_uid].latest_event.key
            self.async_write_ha_state()


class NanitConnectionStatusSensor(CoordinatorEntity[NanitCoordinator], SensorEntity):
    """Sensor for displaying camera connection status."""

    entity_description = CONNECTION_STATUS_SENSOR_DESCRIPTION

    def __init__(self, coordinator: NanitCoordinator, baby_meta: BabyMeta) -> None:
        """Initialize Nanit connection status sensor."""
        super().__init__(coordinator)

        _LOGGER.info(
            "Setting up nanit connection status sensor for baby_uid: %s",
            baby_meta.baby_uid,
        )

        self._baby_uid = baby_meta.baby_uid
        self._attr_unique_id = f"{baby_meta.baby_uid}_connection_status"
        self._attr_native_value = "online" if baby_meta.connection_status.connected else "offline"
        self._attr_device_info = baby_meta.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.info(
            "Handling updated data for connection status sensor for baby_uid: %s", self._baby_uid
        )
        if self._baby_uid in self.coordinator.data.babies:
            connected = self.coordinator.data.babies[self._baby_uid].connection_status.connected
            self._attr_native_value = "online" if connected else "offline"
            self.async_write_ha_state()


class NanitLastSeenSensor(CoordinatorEntity[NanitCoordinator], SensorEntity):
    """Sensor for displaying when camera was last seen online."""

    entity_description = LAST_SEEN_SENSOR_DESCRIPTION

    def __init__(self, coordinator: NanitCoordinator, baby_meta: BabyMeta) -> None:
        """Initialize Nanit last seen sensor."""
        super().__init__(coordinator)

        _LOGGER.info(
            "Setting up nanit last seen sensor for baby_uid: %s",
            baby_meta.baby_uid,
        )

        self._baby_uid = baby_meta.baby_uid
        self._attr_unique_id = f"{baby_meta.baby_uid}_last_seen"
        self._attr_native_value = datetime.fromtimestamp(
            baby_meta.connection_status.last_seen, tz=timezone.utc
        )
        self._attr_device_info = baby_meta.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.info("Handling updated data for last seen sensor for baby_uid: %s", self._baby_uid)
        if self._baby_uid in self.coordinator.data.babies:
            last_seen = self.coordinator.data.babies[self._baby_uid].connection_status.last_seen
            self._attr_native_value = datetime.fromtimestamp(last_seen, tz=timezone.utc)
            self.async_write_ha_state()
