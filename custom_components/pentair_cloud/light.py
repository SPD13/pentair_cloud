"""Platform for light integration."""
from __future__ import annotations

import logging

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    LightEntity,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, DEBUG_INFO
from .pentaircloud import PentairCloudHub, PentairDevice, PentairPumpProgram
from logging import Logger

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    hub = hass.data[DOMAIN][config_entry.entry_id]["pentair_cloud_hub"]
    devices: list[PentairDevice] = await hass.async_add_executor_job(hub.get_devices)
    cloud_devices = []
    for device in devices:
        for program in device.programs:
            cloud_devices.append(PentairCloudLight(_LOGGER, hub, device, program))
    async_add_entities(cloud_devices)


class PentairCloudLight(LightEntity):
    global DOMAIN
    global DEBUG_INFO

    def __init__(
        self,
        LOGGER: Logger,
        hub: PentairCloudHub,
        pentair_device: PentairDevice,
        pentair_program: PentairPumpProgram,
    ) -> None:
        self.LOGGER = LOGGER
        self.hub = hub
        self.pentair_device = pentair_device
        self.pentair_program = pentair_program
        self._name = (
            "Pentair "
            + self.pentair_device.nickname
            + " - P"
            + str(self.pentair_program.id)
            + " / "
            + self.pentair_program.name
        )
        self._state = self.pentair_program.running
        if DEBUG_INFO:
            self.LOGGER.info("Pentair Cloud Pump " + self._name + " Configured")

    @property
    def unique_id(self):
        return (
            f"pentair_"
            + self.pentair_device.pentair_device_id
            + "_"
            + str(self.pentair_program.id)
        )

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f"pentair_" + self.pentair_device.pentair_device_id)
            },
            "name": self.pentair_device.nickname,
            "model": self.pentair_device.nickname,
            "sw_version": "1.0",
            "manufacturer": "Pentair",
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        if DEBUG_INFO:
            self.LOGGER.info(
                "Pentair Cloud Pump "
                + self.pentair_device.pentair_device_id
                + " Called IS_ON"
            )
        self._state = self.pentair_program.running
        return self._state

    def turn_on(self, **kwargs) -> None:
        """Instruct the light to turn on.
        You can skip the brightness part if your light does not support
        brightness control.
        """
        if DEBUG_INFO:
            self.LOGGER.info(
                "Pentair Cloud Pump "
                + self.pentair_device.pentair_device_id
                + " Called ON program: "
                + str(self.pentair_program.id)
            )
        self._state = True
        self.hub.start_program(
            self.pentair_device.pentair_device_id, self.pentair_program.id
        )

    def turn_off(self, **kwargs) -> None:
        """Instruct the light to turn off."""
        if DEBUG_INFO:
            self.LOGGER.info(
                "Pentair Cloud Pump "
                + self.pentair_device.pentair_device_id
                + " Called OFF program: "
                + str(self.pentair_program.id)
            )
        self._state = False
        self.hub.stop_program(
            self.pentair_device.pentair_device_id, self.pentair_program.id
        )

    def update(self) -> None:
        """Fetch new state data for this light.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.hub.update_pentair_devices_status()
        self._state = self.pentair_program.running
        if DEBUG_INFO:
            self.LOGGER.info(
                "Pentair Cloud Pump "
                + self.pentair_device.pentair_device_id
                + " Called UPDATE"
            )
