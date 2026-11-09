"""Constants for Brand & Kiosk."""
from __future__ import annotations

DOMAIN = "brand_kiosk"
SIGNAL_UPDATED = f"{DOMAIN}_updated"

# Branding
CONF_TITLE = "title"
CONF_COLOR = "color"
CONF_GRADIENT = "gradient"
CONF_COLOR2 = "color2"
CONF_BROWSER_TITLE = "browser_title"
CONF_HIDE_ITEMS = "hide_items"
CONF_HIDE_FOR_ADMINS = "hide_for_admins"

# Logo / icon
CONF_LOGO_UPLOAD = "logo_upload"      # form field only (file id)
CONF_LOGO = "logo"                    # stored file name inside <config>/brand_kiosk/
CONF_LOGO_SIDEBAR = "logo_sidebar"
CONF_LOGO_FAVICON = "logo_favicon"
CONF_LOGO_APP_ICON = "logo_app_icon"
CONF_LOGO_REMOVE = "logo_remove"      # form field only
LOGO_DIR = "brand_kiosk"
FILES_URL = "/brand_kiosk_files"
LOGO_TYPES = {".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".ico": "image/x-icon"}

# Kiosk rules: list of dicts in entry.options[CONF_KIOSK]
CONF_KIOSK = "kiosk"
CONF_USER_ID = "user_id"
CONF_ENABLED = "enabled"
CONF_DASHBOARD = "dashboard"
CONF_VIEW = "view"
CONF_HIDE_HEADER = "hide_header"
CONF_HIDE_SIDEBAR = "hide_sidebar"
CONF_LOCK = "lock"
CONF_REMOVE = "remove"            # form field only
CONF_KIOSK_MASTER = "kiosk_master"  # master on/off for all kiosk users

DEFAULT_TITLE = "Home Assistant"
DEFAULT_COLOR = [3, 169, 244]
DEFAULT_COLOR2 = [255, 152, 0]

CARDS_URL = "/brand_kiosk/brand-kiosk.js"
