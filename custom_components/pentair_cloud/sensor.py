"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfPressure,
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, DEBUG_INFO
from .pentaircloud import PentairCloudHub, PentairDevice

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PentairSensorEntityDescription(SensorEntityDescription):
    """Describes a Pentair sensor and how to read its value from a device."""

    value_fn: Callable[[PentairDevice], float | int | None]


SENSOR_TYPES: tuple[PentairSensorEntityDescription, ...] = (
    PentairSensorEntityDescription(
        key="power",
        name="Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.power_watts,
    ),
    PentairSensorEntityDescription(
        key="speed",
        name="Speed",
        icon="mdi:speedometer",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.motor_speed_pct,
    ),
    PentairSensorEntityDescription(
        key="flow",
        name="Flow",
        icon="mdi:water-pump",
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.flow_gpm,
    ),
    PentairSensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.pressure_psi,
    ),
    PentairSensorEntityDescription(
        key="alarm_code",
        name="Alarm code",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.alarm_code,
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
        for description in SENSOR_TYPES:
            entities.append(PentairCloudSensor(_LOGGER, hub, device, description))
    async_add_entities(entities)


class PentairCloudSensor(SensorEntity):

    entity_description: PentairSensorEntityDescription

    def __init__(
        self,
        LOGGER,
        hub: PentairCloudHub,
        pentair_device: PentairDevice,
        description: PentairSensorEntityDescription,
    ) -> None:
        self.LOGGER = LOGGER
        self.hub = hub
        self.pentair_device = pentair_device
        self.entity_description = description
        self._attr_name = (
            "Pentair " + pentair_device.nickname + " - " + description.name
        )
        if DEBUG_INFO:
            self.LOGGER.info("Pentair Cloud Sensor " + self._attr_name + " Configured")

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
    def native_value(self) -> float | int | None:
        return self.entity_description.value_fn(self.pentair_device)

    def update(self) -> None:
        self.hub.update_pentair_devices_status()
