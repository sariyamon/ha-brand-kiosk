"""On/off switches for kiosk mode: one for everyone, one per kiosk user."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ENABLED, CONF_KIOSK, CONF_KIOSK_MASTER, CONF_USER_ID, DOMAIN, SIGNAL_UPDATED


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    entities: list[SwitchEntity] = [KioskMasterSwitch(entry)]
    for rule in entry.options.get(CONF_KIOSK, []):
        user = await hass.auth.async_get_user(rule[CONF_USER_ID])
        entities.append(KioskUserSwitch(entry, rule[CONF_USER_ID], user.name if user else "removed user"))
    # Drop switches of kiosk users that were deleted.
    keep = {e.unique_id for e in entities}
    registry = er.async_get(hass)
    for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg.domain == "switch" and reg.unique_id not in keep:
            registry.async_remove(reg.entity_id)
    async_add_entities(entities)


class _KioskSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Brand & Kiosk",
            manufacturer="Brand & Kiosk",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self.async_write_ha_state))

    @callback
    def _save(self, **changes: Any) -> None:
        self.hass.config_entries.async_update_entry(self._entry, options={**self._entry.options, **changes})


class KioskMasterSwitch(_KioskSwitch):
    """Kiosk mode for all kiosk users at once."""

    _attr_name = "Kiosk mode"
    _attr_icon = "mdi:tablet-dashboard"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_kiosk_master"

    @property
    def is_on(self) -> bool:
        return bool(self._entry.options.get(CONF_KIOSK_MASTER, True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._save(**{CONF_KIOSK_MASTER: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._save(**{CONF_KIOSK_MASTER: False})


class KioskUserSwitch(_KioskSwitch):
    """Kiosk mode for one user; their dashboard and settings are kept when off."""

    _attr_icon = "mdi:account-lock"

    def __init__(self, entry: ConfigEntry, user_id: str, user_name: str) -> None:
        super().__init__(entry)
        self._user_id = user_id
        self._attr_name = f"Kiosk {user_name}"
        self._attr_unique_id = f"{entry.entry_id}_kiosk_{user_id}"

    def _rule(self) -> dict[str, Any] | None:
        return next((r for r in self._entry.options.get(CONF_KIOSK, []) if r[CONF_USER_ID] == self._user_id), None)

    @property
    def available(self) -> bool:
        return self._rule() is not None

    @property
    def is_on(self) -> bool:
        rule = self._rule()
        return bool(rule and rule.get(CONF_ENABLED, True))

    async def _set(self, on: bool) -> None:
        rules = [
            {**r, CONF_ENABLED: on} if r[CONF_USER_ID] == self._user_id else r
            for r in self._entry.options.get(CONF_KIOSK, [])
        ]
        self._save(**{CONF_KIOSK: rules})

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
