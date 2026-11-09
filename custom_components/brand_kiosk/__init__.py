"""Brand & Kiosk: your own sidebar title, colours and logo, plus kiosk mode per user."""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CARDS_URL,
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
    CONF_LOGO_SIDEBAR,
    CONF_TITLE,
    CONF_USER_ID,
    CONF_VIEW,
    DEFAULT_COLOR,
    DEFAULT_COLOR2,
    DEFAULT_TITLE,
    DOMAIN,
    FILES_URL,
    LOGO_DIR,
    LOGO_TYPES,
    SIGNAL_UPDATED,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
JS_FILE = Path(__file__).parent / "frontend" / "brand-kiosk.js"

_ORIGINAL_MANIFEST = "original_manifest"


def _hex(rgb: Any, fallback: list[int]) -> str:
    try:
        r, g, b = (int(v) for v in rgb)
    except (TypeError, ValueError):
        r, g, b = fallback
    return f"#{r:02x}{g:02x}{b:02x}"


def build_config(
    hass: HomeAssistant, user_id: str | None, is_admin: bool = False
) -> dict[str, Any] | None:
    """What the frontend needs for one user: branding plus that user's kiosk rule."""
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = next((e for e in entries if not e.disabled_by), None)
    if entry is None:
        return None
    opts = {**entry.data, **entry.options}
    colors = [_hex(opts.get(CONF_COLOR), DEFAULT_COLOR)]
    if opts.get(CONF_GRADIENT):
        colors.append(_hex(opts.get(CONF_COLOR2), DEFAULT_COLOR2))
    logo = opts.get(CONF_LOGO)
    logo_url = f"{FILES_URL}/{logo}" if logo else None
    rule = next(
        (
            r
            for r in opts.get(CONF_KIOSK, [])
            if r.get(CONF_USER_ID) == user_id and r.get(CONF_ENABLED, True)
        ),
        None,
    )
    kiosk = None
    if rule:
        kiosk = {
            "dashboard": rule.get(CONF_DASHBOARD) or "lovelace",
            "view": (rule.get(CONF_VIEW) or "").strip("/"),
            "hide_header": bool(rule.get(CONF_HIDE_HEADER, True)),
            "hide_sidebar": bool(rule.get(CONF_HIDE_SIDEBAR, True)),
            "lock": bool(rule.get(CONF_LOCK, True)),
        }
    return {
        "title": opts.get(CONF_TITLE) or DEFAULT_TITLE,
        "colors": colors,
        "browser_title": bool(opts.get(CONF_BROWSER_TITLE, True)),
        "hide_items": []
        if is_admin and not opts.get(CONF_HIDE_FOR_ADMINS)
        else list(opts.get(CONF_HIDE_ITEMS, [])),
        "is_admin": is_admin,
        "logo": logo_url,
        "logo_sidebar": bool(logo_url and opts.get(CONF_LOGO_SIDEBAR, True)),
        "logo_favicon": bool(logo_url and opts.get(CONF_LOGO_FAVICON, True)),
        "kiosk": kiosk,
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the frontend script and the logo folder; register the websocket API."""
    websocket_api.async_register_command(hass, ws_subscribe)
    logo_dir = Path(hass.config.path(LOGO_DIR))
    await hass.async_add_executor_job(lambda: logo_dir.mkdir(exist_ok=True))
    if getattr(hass, "http", None):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(CARDS_URL, str(JS_FILE), True),
                StaticPathConfig(FILES_URL, str(logo_dir), False),
            ]
        )
    if "frontend" in hass.config.components:
        version = await hass.async_add_executor_job(_manifest_version)
        frontend.add_extra_js_url(hass, f"{CARDS_URL}?v={version}")
    return True


def _manifest_version() -> str:
    import json

    return json.loads((Path(__file__).parent / "manifest.json").read_text())["version"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Apply the branding and tell open browsers."""
    hass.data.setdefault(DOMAIN, {})
    _apply_app_manifest(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_updated))
    async_dispatcher_send(hass, SIGNAL_UPDATED)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Put Home Assistant's own name and icons back."""
    original = hass.data.get(DOMAIN, {}).pop(_ORIGINAL_MANIFEST, None)
    if original:
        for key, val in original.items():
            frontend.add_manifest_json_key(key, val)
    async_dispatcher_send(hass, SIGNAL_UPDATED)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the uploaded logo."""
    logo = {**entry.data, **entry.options}.get(CONF_LOGO)
    if logo:
        path = Path(hass.config.path(LOGO_DIR, logo))
        await hass.async_add_executor_job(lambda: path.unlink(missing_ok=True))


async def _async_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    _apply_app_manifest(hass, entry)
    async_dispatcher_send(hass, SIGNAL_UPDATED)


@callback
def _apply_app_manifest(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Name and icon used when Home Assistant is added to a phone's home screen."""
    data = hass.data.setdefault(DOMAIN, {})
    manifest = frontend.MANIFEST_JSON
    if _ORIGINAL_MANIFEST not in data:
        data[_ORIGINAL_MANIFEST] = {
            key: copy.deepcopy(manifest[key]) for key in ("name", "short_name", "icons")
        }
    original = data[_ORIGINAL_MANIFEST]
    opts = {**entry.data, **entry.options}
    title = opts.get(CONF_TITLE) or DEFAULT_TITLE
    frontend.add_manifest_json_key("name", title)
    frontend.add_manifest_json_key(
        "short_name", title if len(title) <= 12 else title.split()[0][:12]
    )
    logo = opts.get(CONF_LOGO)
    if logo and opts.get(CONF_LOGO_APP_ICON, True):
        mime = LOGO_TYPES.get(Path(logo).suffix.lower(), "image/png")
        url = f"{FILES_URL}/{logo}"
        frontend.add_manifest_json_key(
            "icons",
            [
                {"src": url, "sizes": "any" if mime == "image/svg+xml" else size, "type": mime, "purpose": purpose}
                for size in ("192x192", "512x512")
                for purpose in ("any", "maskable")
            ],
        )
    else:
        frontend.add_manifest_json_key("icons", copy.deepcopy(original["icons"]))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send this user's branding and kiosk settings now and whenever they change."""
    user_id = connection.user.id if connection.user else None
    is_admin = bool(connection.user and connection.user.is_admin)

    @callback
    def send() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], build_config(hass, user_id, is_admin))
        )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL_UPDATED, send)
    connection.send_result(msg["id"])
    send()
