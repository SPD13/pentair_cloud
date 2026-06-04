"""Platform for switch integration."""
from __future__ import annotations

import logging
import time

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, DEBUG_INFO
from .pentaircloud import PentairCloudHub, PentairDevice, PentairPumpProgram
from logging import Logger

_LOGGER = logging.getLogger(__name__)

# How long an optimistic program selection is trusted before falling back to
# the API-reported state, as a backstop if a poll never lands. Kept above the
# hub's UPDATE_MIN_SECONDS (60s) so a normal poll cycle gets a chance to confirm.
OPTIMISTIC_TIMEOUT = 90


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
            cloud_devices.append(PentairCloudSwitch(_LOGGER, hub, device, program))
    async_add_entities(cloud_devices)


class PentairCloudSwitch(SwitchEntity):

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
            self.LOGGER.info("Pentair Cloud Switch " + self._name + " Configured")

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

    async def async_added_to_hass(self) -> None:
        """Register with the device so siblings can be refreshed together."""
        if self not in self.pentair_device.switch_entities:
            self.pentair_device.switch_entities.append(self)

    async def async_will_remove_from_hass(self) -> None:
        if self in self.pentair_device.switch_entities:
            self.pentair_device.switch_entities.remove(self)

    def _optimistic_active(self) -> bool:
        """True while the optimistic selection should override the API state.

        The override holds until the first real API poll lands after it was set
        (hub.last_update advances past optimistic_set_at), or until the hard
        expiry, whichever comes first.
        """
        dev = self.pentair_device
        if not dev.optimistic_expiry or time.time() >= dev.optimistic_expiry:
            return False
        if self.hub.last_update is not None and self.hub.last_update > dev.optimistic_set_at:
            return False  # a real poll has confirmed/reverted the state
        return True

    def _set_optimistic(self, program_id) -> None:
        dev = self.pentair_device
        dev.optimistic_program = program_id
        dev.optimistic_set_at = time.time()
        dev.optimistic_expiry = dev.optimistic_set_at + OPTIMISTIC_TIMEOUT
        for ent in dev.switch_entities:
            if ent.hass is not None:
                ent.schedule_update_ha_state()

    @property
    def is_on(self) -> bool | None:
        if self._optimistic_active():
            self._state = self.pentair_program.id == self.pentair_device.optimistic_program
        else:
            self._state = self.pentair_program.running
        return self._state

    def turn_on(self, **kwargs) -> None:
        if DEBUG_INFO:
            self.LOGGER.info(
                "Pentair Cloud Switch "
                + self.pentair_device.pentair_device_id
                + " Called ON program: "
                + str(self.pentair_program.id)
            )
        # Optimistically select this program (starting one stops the others).
        self._set_optimistic(self.pentair_program.id)
        self.hub.start_program(
            self.pentair_device.pentair_device_id, self.pentair_program.id
        )

    def turn_off(self, **kwargs) -> None:
        if DEBUG_INFO:
            self.LOGGER.info(
                "Pentair Cloud Switch "
                + self.pentair_device.pentair_device_id
                + " Called OFF program: "
                + str(self.pentair_program.id)
            )
        # Optimistically clear the running program (all programs off).
        self._set_optimistic(None)
        self.hub.stop_program(
            self.pentair_device.pentair_device_id, self.pentair_program.id
        )

    def update(self) -> None:
        self.hub.update_pentair_devices_status()
        self._state = self.pentair_program.running
        if DEBUG_INFO:
            self.LOGGER.info(
                "Pentair Cloud Switch "
                + self.pentair_device.pentair_device_id
                + " Called UPDATE"
            )
