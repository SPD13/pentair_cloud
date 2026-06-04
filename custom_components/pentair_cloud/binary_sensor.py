"""Platform for binary sensor integration."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, DEBUG_INFO
from .pentaircloud import PentairCloudHub, PentairDevice

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PentairBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Pentair binary sensor and how to read its state."""

    value_fn: Callable[[PentairDevice], bool | None]


BINARY_SENSOR_TYPES: tuple[PentairBinarySensorEntityDescription, ...] = (
    PentairBinarySensorEntityDescription(
        key="alarm",
        name="Alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        # The device-level "alarm" flag is what Pentair reports; the numeric
        # fault bits are exposed separately as the "Alarm code" sensor.
        value_fn=lambda device: (
            bool(device.alarm) or bool(device.alarm_code)
            if device.alarm is not None or device.alarm_code is not None
            else None
        ),
    ),
    PentairBinarySensorEntityDescription(
        key="online",
        name="Connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.online,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    hub = hass.data[DOMAIN][config_entry.entry_id]["pentair_cloud_hub"]
    devices: list[PentairDevice] = await hass.async_add_executor_job(hub.get_devices)
    entities = []
    for device in devices:
        for description in BINARY_SENSOR_TYPES:
            entities.append(
                PentairCloudBinarySensor(_LOGGER, hub, device, description)
            )
    async_add_entities(entities)


class PentairCloudBinarySensor(BinarySensorEntity):

    entity_description: PentairBinarySensorEntityDescription

    def __init__(
        self,
        LOGGER,
        hub: PentairCloudHub,
        pentair_device: PentairDevice,
        description: PentairBinarySensorEntityDescription,
    ) -> None:
        self.LOGGER = LOGGER
        self.hub = hub
        self.pentair_device = pentair_device
        self.entity_description = description
        self._attr_name = (
            "Pentair " + pentair_device.nickname + " - " + description.name
        )
        if DEBUG_INFO:
            self.LOGGER.info(
                "Pentair Cloud Binary Sensor " + self._attr_name + " Configured"
            )

    @property
    def unique_id(self):
        return (
            "pentair_"
            + self.pentair_device.pentair_device_id
            + "_"
            + self.entity_description.key
        )

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, "pentair_" + self.pentair_device.pentair_device_id)
            },
            "name": self.pentair_device.nickname,
            "model": self.pentair_device.nickname,
            "sw_version": "1.0",
            "manufacturer": "Pentair",
        }

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.pentair_device)

    @property
    def extra_state_attributes(self):
        if self.entity_description.key == "alarm":
            return {"alarm_code": self.pentair_device.alarm_code}
        return None

    def update(self) -> None:
        self.hub.update_pentair_devices_status()
