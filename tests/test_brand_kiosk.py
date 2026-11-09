"""Brand & Kiosk: setup, settings menu, per-user kiosk rules and the frontend feed."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from custom_components.brand_kiosk import build_config
from custom_components.brand_kiosk.const import DOMAIN

BRANDING = {
    "title": "Hawaii Automations",
    "color": [79, 209, 197],
    "gradient": True,
    "color2": [246, 173, 85],
    "browser_title": True,
    "logo_sidebar": True,
    "logo_favicon": True,
    "logo_app_icon": True,
}


async def _setup(hass: HomeAssistant) -> str:
    assert await async_setup_component(hass, "http", {})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], BRANDING)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hawaii Automations"
    await hass.async_block_till_done()
    return result["result"].entry_id


async def test_setup_branding(hass: HomeAssistant) -> None:
    await _setup(hass)
    cfg = build_config(hass, "someone")
    assert cfg["title"] == "Hawaii Automations"
    assert cfg["colors"] == ["#4fd1c5", "#f6ad55"]
    assert cfg["kiosk"] is None
    assert cfg["logo"] is None and cfg["logo_sidebar"] is False
    # Home-screen app name follows the title.
    assert frontend.MANIFEST_JSON["name"] == "Hawaii Automations"
    assert frontend.MANIFEST_JSON["short_name"] == "Hawaii"


async def test_single_instance(hass: HomeAssistant) -> None:
    await _setup(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT


async def _options(hass: HomeAssistant, entry_id: str, *steps: tuple[str, dict | None]):
    result = await hass.config_entries.options.async_init(entry_id)
    assert result["type"] is FlowResultType.MENU
    for step, data in steps:
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": step})
        while data is not None and result["type"] is FlowResultType.FORM:
            payload = data.pop(result["step_id"])
            result = await hass.config_entries.options.async_configure(result["flow_id"], payload)
    await hass.async_block_till_done()
    return result


async def test_kiosk_rule_per_user(hass: HomeAssistant, hass_admin_user, hass_read_only_user) -> None:
    entry_id = await _setup(hass)
    wall = hass_read_only_user.id
    result = await _options(
        hass,
        entry_id,
        (
            "kiosk_user",
            {
                "kiosk_user": {"user_id": wall},
                "kiosk": {
                    "enabled": True,
                    "dashboard": "wall-panel",
                    "view": "/cams/",
                    "hide_header": True,
                    "hide_sidebar": True,
                    "lock": True,
                },
            },
        ),
        ("save", None),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    kiosk = build_config(hass, wall)["kiosk"]
    assert kiosk == {"dashboard": "wall-panel", "view": "cams", "hide_header": True, "hide_sidebar": True, "lock": True}
    assert build_config(hass, hass_admin_user.id)["kiosk"] is None

    # A switch per kiosk user, plus the master switch.
    user_switch = f"switch.brand_kiosk_kiosk_{hass_read_only_user.name.lower().replace(' ', '_')}"
    assert hass.states.get("switch.brand_kiosk_kiosk_mode").state == "on"
    assert hass.states.get(user_switch).state == "on"

    # Per-user switch off: kiosk off, settings kept.
    await hass.services.async_call("switch", "turn_off", {"entity_id": user_switch}, blocking=True)
    await hass.async_block_till_done()
    assert build_config(hass, wall)["kiosk"] is None
    assert hass.states.get(user_switch).state == "off"
    await hass.services.async_call("switch", "turn_on", {"entity_id": user_switch}, blocking=True)
    await hass.async_block_till_done()
    assert build_config(hass, wall)["kiosk"]["dashboard"] == "wall-panel"

    # Master switch off pauses everyone.
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.brand_kiosk_kiosk_mode"}, blocking=True)
    await hass.async_block_till_done()
    assert build_config(hass, wall)["kiosk"] is None
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.brand_kiosk_kiosk_mode"}, blocking=True)
    await hass.async_block_till_done()
    assert build_config(hass, wall)["kiosk"] is not None

    # Delete removes the rule and its switch.
    await _options(
        hass,
        entry_id,
        ("kiosk_user", {"kiosk_user": {"user_id": wall}, "kiosk": {"enabled": True, "dashboard": "wall-panel", "hide_header": True, "hide_sidebar": True, "lock": True, "remove": True}}),
        ("save", None),
    )
    assert build_config(hass, wall)["kiosk"] is None
    assert hass.states.get(user_switch) is None


async def test_hidden_items_skip_admins(hass: HomeAssistant) -> None:
    entry_id = await _setup(hass)
    await _options(hass, entry_id, ("sidebar", {"sidebar": {"hide_items": ["map", "config"], "hide_for_admins": False}}), ("save", None))
    assert build_config(hass, "u", is_admin=False)["hide_items"] == ["map", "config"]
    assert build_config(hass, "u", is_admin=True)["hide_items"] == []
    await _options(hass, entry_id, ("sidebar", {"sidebar": {"hide_items": ["map"], "hide_for_admins": True}}), ("save", None))
    assert build_config(hass, "u", is_admin=True)["hide_items"] == ["map"]


async def test_branding_change_and_unload(hass: HomeAssistant) -> None:
    entry_id = await _setup(hass)
    await _options(hass, entry_id, ("branding", {"branding": {k: v for k, v in {**BRANDING, "title": "Villa", "gradient": False}.items() if not k.startswith("logo")}}), ("save", None))
    cfg = build_config(hass, "u")
    assert cfg["title"] == "Villa" and cfg["colors"] == ["#4fd1c5"]
    assert hass.config_entries.async_get_entry(entry_id).title == "Villa"
    assert await hass.config_entries.async_unload(entry_id)
    assert frontend.MANIFEST_JSON["name"] == "Home Assistant"


async def test_websocket_feed(hass: HomeAssistant, hass_ws_client) -> None:
    await _setup(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "brand_kiosk/subscribe"})
    assert (await client.receive_json())["success"]
    event = await client.receive_json()
    assert event["event"]["title"] == "Hawaii Automations"
    assert event["event"]["is_admin"] is True
