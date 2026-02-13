"""The MELCloud Climate integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import importlib
import importlib.metadata
import logging
import subprocess
import sys
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from pymelcloud import Device, get_devices
from pymelcloud.atw_device import Zone
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.util import Throttle

from .const import DOMAIN
 
_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER, Platform.SELECT, Platform.SWITCH]

async def _async_migrate_pymelcloud_package(hass: HomeAssistant) -> bool:
    """Migrate from old pymelcloud fork to upstream python-melcloud.

    When switching from git+https://github.com/ojkaas/pymelcloud to the PyPI
    python-melcloud package, pip does not automatically uninstall the old
    package because they have different distribution names but share the same
    pymelcloud module namespace.  Detect the conflict and fix it.

    Returns True if a migration was performed (restart required).
    """
    try:
        importlib.metadata.distribution("pymelcloud")
    except importlib.metadata.PackageNotFoundError:
        return False  # Old package not installed, nothing to do

    _LOGGER.warning(
        "Found old 'pymelcloud' package that conflicts with 'python-melcloud'. "
        "Removing it and reinstalling the correct package"
    )
    try:
        await hass.async_add_executor_job(
            subprocess.check_call,
            [sys.executable, "-m", "pip", "uninstall", "-y", "pymelcloud"],
        )
        await hass.async_add_executor_job(
            subprocess.check_call,
            [
                sys.executable, "-m", "pip", "install",
                "--force-reinstall", "python-melcloud==0.1.2",
            ],
        )
    except subprocess.CalledProcessError:
        _LOGGER.error(
            "Failed to migrate pymelcloud package automatically. "
            "Please run manually inside the HA container: "
            "pip uninstall -y pymelcloud && pip install python-melcloud==0.1.2 "
            "and restart Home Assistant"
        )
        return False

    # Clear cached pymelcloud modules so they are re-imported from the
    # newly installed package when the platform modules are loaded.
    for mod_name in list(sys.modules):
        if mod_name == "pymelcloud" or mod_name.startswith("pymelcloud."):
            del sys.modules[mod_name]
    importlib.invalidate_caches()

    # Re-import the symbols this module uses at the top level.
    global Device, get_devices, Zone  # noqa: PLW0603
    from pymelcloud import Device, get_devices  # noqa: F811
    from pymelcloud.atw_device import Zone  # noqa: F811

    _LOGGER.warning("pymelcloud package migration completed successfully")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with MELClooud."""
    await _async_migrate_pymelcloud_package(hass)

    conf = entry.data
    try:
        mel_devices = await mel_devices_setup(hass, conf[CONF_TOKEN])
    except ClientResponseError as ex:
        if isinstance(ex, ClientResponseError) and ex.code == 401:
            raise ConfigEntryAuthFailed from ex
        raise ConfigEntryNotReady from ex
    except (TimeoutError, ClientConnectionError) as ex:
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: mel_devices})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    hass.data[DOMAIN].pop(config_entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return unload_ok


class MelCloudDevice:
    """MELCloud Device instance."""

    def __init__(self, device: Device) -> None:
        """Construct a device wrapper."""
        self.device = device
        self.name = device.name
        self._available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs):
        """Pull the latest data from MELCloud."""
        try:
            await self.device.update()
            self._available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self.name)
            self._available = False
        except ClientResponseError as err:
            if err.status == 401:
                raise
            # Energy report may fail (e.g. 500 for ERV devices) after
            # device state was already fetched successfully. Keep device
            # available since the state data is likely still valid.
            _LOGGER.debug(
                "API error during update for %s (device may still be functional): %s",
                self.name,
                err,
            )
            self._available = True
        except AttributeError as err:
            _LOGGER.warning(
                "Device update failed for %s due to pymelcloud incompatibility: %s. "
                "Ensure the correct pymelcloud version is installed",
                self.name,
                err,
            )
            self._available = False

    async def async_set(self, properties: dict[str, Any]):
        """Write state changes to the MELCloud API."""
        try:
            await self.device.set(properties)
            self._available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self.name)
            self._available = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_id(self):
        """Return device ID."""
        return self.device.device_id

    @property
    def building_id(self):
        """Return building ID of the device."""
        return self.device.building_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        model = None
        if (unit_infos := self.device.units) is not None:
            model = ", ".join([x["model"] for x in unit_infos if x["model"]])
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, f"{self.device.mac}-{self.device.serial}")},
            manufacturer="Mitsubishi Electric",
            model=model,
            name=self.name,
        )

    def zone_device_info(self, zone: Zone) -> DeviceInfo:
        """Return a zone device description for device registry."""
        dev = self.device
        return DeviceInfo(
            identifiers={(DOMAIN, f"{dev.mac}-{dev.serial}-{zone.zone_index}")},
            manufacturer="Mitsubishi Electric",
            model="ATW zone device",
            name=f"{self.name} {zone.name}",
            via_device=(DOMAIN, f"{dev.mac}-{dev.serial}"),
        )

async def mel_devices_setup(
    hass: HomeAssistant, token: str
) -> dict[str, list[MelCloudDevice]]:
    """Query connected devices from MELCloud."""
    session = async_get_clientsession(hass)
    async with asyncio.timeout(10):
        all_devices = await get_devices(
            token,
            session,
            conf_update_interval=timedelta(minutes=15),
            device_set_debounce=timedelta(seconds=2),
        )
    wrapped_devices: dict[str, list[MelCloudDevice]] = {}
    for device_type, devices in all_devices.items():
        wrapped_devices[device_type] = [MelCloudDevice(device) for device in devices]
    return wrapped_devices