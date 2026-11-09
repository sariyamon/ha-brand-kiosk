# Brand & Kiosk for Home Assistant

Put your own name, colours and logo on Home Assistant, and turn any user into a kiosk, for example a wall tablet that only shows one dashboard. Everything is set from the integration's settings screen, with no YAML and no extra plugins.

![Brand & Kiosk](custom_components/brand_kiosk/brand/icon@2x.png)

## What you get

**Branding**
- **Sidebar title.** Replace "Home Assistant" at the top of the sidebar with your own text.
- **Title colour.** One colour, or a two-colour gradient.
- **Logo.** Upload a PNG, SVG, JPG, WebP or ICO and show it:
  - next to the sidebar title
  - as the browser tab icon
  - as the home-screen app icon, when Home Assistant is added to a phone or tablet home screen
- **Browser tab title.** "Overview – Home Assistant" becomes "Overview – *Your title*".
- **Home-screen app name.** Your title, in the web app manifest.

**Kiosk mode per user**
- **Dashboard and view.** Pick a user, then the dashboard (and optionally a view) they see.
- **Hide parts of the screen.** Hide the top bar, the sidebar, or both.
- **Lock to the dashboard.** If that user opens any other page, they are sent straight back.
- **Separate settings.** Each user has their own. A good set-up is a separate user for each wall tablet.

**Sidebar**
- **Hide items.** Hide sidebar items such as Map, Energy or Settings, for everyone or for non-admins only. You can also type a path, e.g. `hacs`.

Changes apply to every open screen as soon as you press **Save**, with no restart or page reload.

## Install

1. In Home Assistant open **Settings → Marketplace** (HACS on 2026.10 and older) → ⋮ → **Add from link**, enter `https://github.com/sariyamon/ha-brand-kiosk` with category **Integration**, and install **Brand & Kiosk**.
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → Brand & Kiosk.** Enter your title, colours and, optionally, a logo.

Change anything later with **Configure** on the integration:

| Menu | What it changes |
|---|---|
| **Title and colours** | Title text, colour or gradient, browser tab title |
| **Logo and icons** | Upload, replace or remove the logo; where it is used |
| **Kiosk mode for a user** | Pick a user, then their dashboard, view, hidden top bar / sidebar, and lock. Switch "Kiosk mode for this user" off to remove it. |
| **Hide sidebar items** | Items to hide, and whether admins see them anyway |
| **Save** | Applies everything to every open screen |

## Kiosk tips

- Add `?kiosk=off` to the address in a browser tab to turn kiosk mode off for that tab, for example to reach Settings on the wall tablet. Add `?kiosk` to turn it on in any tab, for any user.
- Kiosk mode hides the screen parts with styling. It is not a security boundary, so give a kiosk user a non-admin account.
- The Companion app keeps its own cached copy of the page. After changing settings, pull down to refresh, or use **Settings → Companion app → Reset frontend cache**.
- A new home-screen icon shows after you remove the shortcut and add it again.

## How it works

The integration serves a small script that Home Assistant loads on every page. That script asks the integration over the websocket for the signed-in user's settings and applies them. The logo is stored in `<config>/brand_kiosk/` and served from `/brand_kiosk_files/`. Removing the integration puts Home Assistant's own name and icons back.

## License

MIT
