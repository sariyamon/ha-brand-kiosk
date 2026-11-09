"""Setup and settings screens for Brand & Kiosk."""
from __future__ import annotations

import secrets
import shutil
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_BROWSER_TITLE,
    CONF_COLOR,
    CONF_COLOR2,
    CONF_DASHBOARD,
    CONF_ENABLED,
    CONF_GRADIENT,
    CONF_HIDE_FOR_ADMINS,
    CONF_HIDE_HEADER,
    CONF_HIDE_ITEMS,
    CONF_HIDE_SIDEBAR,
    CONF_KIOSK,
    CONF_LOCK,
    CONF_LOGO,
    CONF_LOGO_APP_ICON,
    CONF_LOGO_FAVICON,
    CONF_LOGO_REMOVE,
    CONF_LOGO_SIDEBAR,
    CONF_LOGO_UPLOAD,
    CONF_TITLE,
    CONF_USER_ID,
    CONF_VIEW,
    DEFAULT_COLOR,
    DEFAULT_COLOR2,
    DOMAIN,
    LOGO_DIR,
    LOGO_TYPES,
)



def _branding_schema(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_TITLE, default=d.get(CONF_TITLE, "Home Assistant")): selector.TextSelector(),
            vol.Required(CONF_COLOR, default=d.get(CONF_COLOR, DEFAULT_COLOR)): selector.ColorRGBSelector(),
            vol.Required(CONF_GRADIENT, default=d.get(CONF_GRADIENT, False)): selector.BooleanSelector(),
            vol.Required(CONF_COLOR2, default=d.get(CONF_COLOR2, DEFAULT_COLOR2)): selector.ColorRGBSelector(),
            vol.Required(CONF_BROWSER_TITLE, default=d.get(CONF_BROWSER_TITLE, True)): selector.BooleanSelector(),
        }
    )


def _logo_schema(d: dict[str, Any], with_remove: bool) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Optional(CONF_LOGO_UPLOAD): selector.FileSelector(
            selector.FileSelectorConfig(accept="image/png,image/svg+xml,image/jpeg,image/webp,image/x-icon")
        ),
        vol.Required(CONF_LOGO_SIDEBAR, default=d.get(CONF_LOGO_SIDEBAR, True)): selector.BooleanSelector(),
        vol.Required(CONF_LOGO_FAVICON, default=d.get(CONF_LOGO_FAVICON, True)): selector.BooleanSelector(),
        vol.Required(CONF_LOGO_APP_ICON, default=d.get(CONF_LOGO_APP_ICON, True)): selector.BooleanSelector(),
    }
    if with_remove:
        fields[vol.Required(CONF_LOGO_REMOVE, default=False)] = selector.BooleanSelector()
    return vol.Schema(fields)


def _save_logo(hass: HomeAssistant, file_id: str, old: str | None) -> str:
    """Copy an uploaded image into <config>/brand_kiosk/ (runs in the executor)."""
    folder = Path(hass.config.path(LOGO_DIR))
    folder.mkdir(exist_ok=True)
    with process_uploaded_file(hass, file_id) as tmp:
        ext = Path(tmp.name).suffix.lower()
        if ext not in LOGO_TYPES:
            raise ValueError("unsupported")
        name = f"logo-{secrets.token_hex(4)}{ext}"  # new name each time: no stale browser cache
        shutil.copyfile(tmp, folder / name)
    if old:
        (folder / old).unlink(missing_ok=True)
    return name


def _delete_logo(hass: HomeAssistant, name: str) -> None:
    Path(hass.config.path(LOGO_DIR, name)).unlink(missing_ok=True)


async def _users(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    users = await hass.auth.async_get_users()
    return [
        selector.SelectOptionDict(value=u.id, label=f"{u.name}{' (admin)' if u.is_admin else ''}")
        for u in users
        if u.is_active and not u.system_generated
    ]


def _panels(hass: HomeAssistant, dashboards_only: bool) -> list[selector.SelectOptionDict]:
    from homeassistant.components.frontend import DATA_PANELS

    out = []
    for url_path, panel in hass.data.get(DATA_PANELS, {}).items():
        if dashboards_only and panel.component_name != "lovelace":
            continue
        title = panel.sidebar_title or url_path
        if url_path == "lovelace":
            title = "Overview"
        elif title == title.lower():  # untranslated key, e.g. "map", "config"
            title = title.replace("_", " ").replace("-", " ").title()
        if not dashboards_only and not panel.sidebar_title:
            continue
        out.append(selector.SelectOptionDict(value=url_path, label=f"{title}  (/{url_path})"))
    for extra in ("config", "developer-tools", "profile") if not dashboards_only else ():
        if extra not in {o["value"] for o in out}:
            out.append(selector.SelectOptionDict(value=extra, label=f"{extra.replace('-', ' ').title()}  (/{extra})"))
    return sorted(out, key=lambda o: o["label"].lower())


class BrandKioskConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per Home Assistant."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {k: v for k, v in user_input.items() if k != CONF_LOGO_UPLOAD}
            if file_id := user_input.get(CONF_LOGO_UPLOAD):
                try:
                    data[CONF_LOGO] = await self.hass.async_add_executor_job(_save_logo, self.hass, file_id, None)
                except ValueError:
                    errors[CONF_LOGO_UPLOAD] = "bad_logo"
            if not errors:
                return self.async_create_entry(title=data[CONF_TITLE], data={}, options={**data, CONF_KIOSK: []})
        schema = _branding_schema(user_input or {}).extend(_logo_schema(user_input or {}, False).schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BrandKioskOptionsFlow()


class BrandKioskOptionsFlow(OptionsFlow):
    """Menu: branding, logo, kiosk per user, sidebar items; Save writes everything at once."""

    def __init__(self) -> None:
        self._opts: dict[str, Any] | None = None
        self._user_id: str | None = None

    @property
    def opts(self) -> dict[str, Any]:
        if self._opts is None:
            self._opts = {**self.config_entry.data, **self.config_entry.options}
            self._opts[CONF_KIOSK] = [dict(r) for r in self._opts.get(CONF_KIOSK, [])]
        return self._opts

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["branding", "logo", "kiosk_user", "sidebar", "save"],
            description_placeholders={"kiosk": await self._kiosk_summary()},
        )

    async def _kiosk_summary(self) -> str:
        rules = [r for r in self.opts[CONF_KIOSK] if r.get(CONF_ENABLED, True)]
        if not rules:
            return "No kiosk users yet."
        names = {o["value"]: o["label"] for o in await _users(self.hass)}
        return "Kiosk users: " + ", ".join(
            f"{names.get(r[CONF_USER_ID], 'removed user')} → /{r.get(CONF_DASHBOARD, 'lovelace')}" for r in rules
        )

    async def async_step_branding(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self.opts.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(step_id="branding", data_schema=_branding_schema(self.opts))

    async def async_step_logo(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = self.opts.get(CONF_LOGO)
        if user_input is not None:
            for key in (CONF_LOGO_SIDEBAR, CONF_LOGO_FAVICON, CONF_LOGO_APP_ICON):
                self.opts[key] = user_input[key]
            if file_id := user_input.get(CONF_LOGO_UPLOAD):
                try:
                    self.opts[CONF_LOGO] = await self.hass.async_add_executor_job(
                        _save_logo, self.hass, file_id, current
                    )
                except ValueError:
                    errors[CONF_LOGO_UPLOAD] = "bad_logo"
            elif user_input.get(CONF_LOGO_REMOVE) and current:
                await self.hass.async_add_executor_job(_delete_logo, self.hass, current)
                self.opts.pop(CONF_LOGO, None)
            if not errors:
                return await self.async_step_init()
        return self.async_show_form(
            step_id="logo",
            data_schema=_logo_schema(self.opts, bool(current)),
            errors=errors,
            description_placeholders={"current": current or "none (Home Assistant's own icon)"},
        )

    async def async_step_kiosk_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._user_id = user_input[CONF_USER_ID]
            return await self.async_step_kiosk()
        return self.async_show_form(
            step_id="kiosk_user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USER_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=await _users(self.hass))
                    )
                }
            ),
        )

    async def async_step_kiosk(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        rules = self.opts[CONF_KIOSK]
        rule = next((r for r in rules if r[CONF_USER_ID] == self._user_id), None)
        if user_input is not None:
            rules[:] = [r for r in rules if r[CONF_USER_ID] != self._user_id]
            if user_input[CONF_ENABLED]:
                rules.append({CONF_USER_ID: self._user_id, **user_input})
            return await self.async_step_init()
        r = rule or {}
        user = await self.hass.auth.async_get_user(self._user_id) if self._user_id else None
        return self.async_show_form(
            step_id="kiosk",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENABLED, default=r.get(CONF_ENABLED, True)): selector.BooleanSelector(),
                    vol.Required(CONF_DASHBOARD, default=r.get(CONF_DASHBOARD, "lovelace")): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=_panels(self.hass, True), custom_value=True)
                    ),
                    vol.Optional(CONF_VIEW, description={"suggested_value": r.get(CONF_VIEW, "")}): selector.TextSelector(),
                    vol.Required(CONF_HIDE_HEADER, default=r.get(CONF_HIDE_HEADER, True)): selector.BooleanSelector(),
                    vol.Required(CONF_HIDE_SIDEBAR, default=r.get(CONF_HIDE_SIDEBAR, True)): selector.BooleanSelector(),
                    vol.Required(CONF_LOCK, default=r.get(CONF_LOCK, True)): selector.BooleanSelector(),
                }
            ),
            description_placeholders={"user": user.name if user else "this user"},
        )

    async def async_step_sidebar(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self.opts[CONF_HIDE_ITEMS] = user_input.get(CONF_HIDE_ITEMS, [])
            self.opts[CONF_HIDE_FOR_ADMINS] = user_input[CONF_HIDE_FOR_ADMINS]
            return await self.async_step_init()
        return self.async_show_form(
            step_id="sidebar",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HIDE_ITEMS, default=self.opts.get(CONF_HIDE_ITEMS, [])): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=_panels(self.hass, False), multiple=True, custom_value=True)
                    ),
                    vol.Required(CONF_HIDE_FOR_ADMINS, default=self.opts.get(CONF_HIDE_FOR_ADMINS, False)): selector.BooleanSelector(),
                }
            ),
        )

    async def async_step_save(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self.hass.config_entries.async_update_entry(self.config_entry, title=self.opts.get(CONF_TITLE, "Brand & Kiosk"))
        return self.async_create_entry(data=self.opts)
