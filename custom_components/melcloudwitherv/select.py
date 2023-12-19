"""Support for MelCloud device sensors."""
from __future__ import annotations

from typing import Any

from pymelcloud import DEVICE_TYPE_ERV, ErvDevice

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MelCloudDevice
from .const import DOMAIN

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.typing import StateType


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up MelCloud device control based on config_entry."""

    mel_devices = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = [
        ErvFanSpeedSelect(mel_device, mel_device.device) for mel_device in mel_devices[DEVICE_TYPE_ERV]
    ] + [
        ErvVentilationModeSelect(mel_device, mel_device.device) for mel_device in mel_devices[DEVICE_TYPE_ERV]
    ]
    async_add_entities(entities, True)

class ErvFanSpeedSelect(SelectEntity):
    def __init__(self, api: MelCloudDevice, device: ErvDevice):
        self._api = api
        self._device = device
        self._attr_device_info = api.device_info

    @property
    def name(self) -> str:
        return f"{self._device.name} Fan Speed"

    @property
    def unique_id(self) -> str:
        return f"{self._device.serial}-{self._device.mac}_fan_speed"

    @property
    def state(self) -> StateType:
        return self._device.fan_speed

    @property
    def options(self) -> list[str]:
        return self._device.fan_speeds

    async def async_select_option(self, option: str) -> None:
        set_dict = {"fan_speed": option}
        await self._device.set(set_dict)

class ErvVentilationModeSelect(SelectEntity):
    def __init__(self, api: MelCloudDevice, device: ErvDevice):
        self._api = api
        self._device = device
        self._attr_device_info = api.device_info

    @property
    def name(self) -> str:
        return f"{self._device.name} Ventilation Mode"

    @property
    def unique_id(self) -> str:
        return f"{self._device.serial}-{self._device.mac}_ventilation_mode"

    @property
    def state(self) -> StateType:
        return self._device.ventilation_mode

    @property
    def options(self) -> list[str]:
        return self._device.ventilation_modes

    async def async_select_option(self, option: str) -> None:
        set_dict = {"ventilation_mode": option}
        await self._device.set(set_dict)
