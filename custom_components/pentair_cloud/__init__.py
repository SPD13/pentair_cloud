"""The PentairCloud integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
import logging
from .pentaircloud import PentairCloudHub

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.LIGHT]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the PentairCloud component."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)
    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_EMAIL: conf[CONF_EMAIL], CONF_PASSWORD: conf[CONF_PASSWORD]},
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PentairCloud from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    try:
        hub = PentairCloudHub(_LOGGER)
        if not await hass.async_add_executor_job(
            hub.authenticate, entry.data["username"], entry.data["password"]
        ):
            return False

        await hass.async_add_executor_job(hub.populate_AWS_and_data_fields)
    except Exception as err:
        _LOGGER.error("Exception while setting up Pentair Cloud. Will retry. %s", err)
        raise ConfigEntryNotReady(
            f"Exception while setting up Pentair Cloud. Will retry. {err}"
        )

    hass.data[DOMAIN][entry.entry_id] = {"pentair_cloud_hub": hub}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
