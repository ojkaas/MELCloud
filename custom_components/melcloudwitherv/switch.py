"""Support for MelCloud device sensors."""
from __future__ import annotations

from typing import Any, cast

from pymelcloud import DEVICE_TYPE_ATA, DEVICE_TYPE_ATW, DEVICE_TYPE_ERV, ErvDevice

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MelCloudDevice
from .const import DOMAIN

from homeassistant.helpers.typing import StateType


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up MelCloud device control based on config_entry."""

    mel_devices = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [
        PowerSwitch(mel_device, mel_device.device) for mel_device in mel_devices[DEVICE_TYPE_ERV]
    ] + [
        PowerSwitch(mel_device, mel_device.device) for mel_device in mel_devices[DEVICE_TYPE_ATA]
    ]+ [
        PowerSwitch(mel_device, mel_device.device) for mel_device in mel_devices[DEVICE_TYPE_ATW]
    ]
    async_add_entities(entities, True)

class PowerSwitch(SwitchEntity):
    def __init__(self, api: MelCloudDevice, device: ErvDevice):
        self._api = api
        self._device = device
        self._attr_device_info = api.device_info


    @property
    def name(self) -> str:
        return f"{self._device.name} Power"

    @property
    def unique_id(self) -> str:
        return f"{self._device.serial}-{self._device.mac}_power_switch"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        set_dict = {"power": True}
        await self._device.set(set_dict)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        set_dict = {"power": False}
        await self._device.set(set_dict)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return cast(bool, self._device.power)