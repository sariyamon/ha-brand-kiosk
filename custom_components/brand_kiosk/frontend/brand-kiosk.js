/*
 * Brand & Kiosk – loaded automatically on every Home Assistant page.
 *
 * Gets this user's settings from the integration (websocket "brand_kiosk/subscribe")
 * and applies them: sidebar title text, colour/gradient and logo, browser tab title
 * and icon, hidden sidebar items, and kiosk mode (no top bar / no sidebar / fixed
 * dashboard). Settings changes apply at once to every open screen.
 *
 * In any browser tab:  ?kiosk=off  turns kiosk mode off for that tab,
 *                      ?kiosk      turns it on (top bar and sidebar hidden).
 */
const VERSION = "1.1.1";
const TAG = "brand-kiosk";
const SESSION_KEY = "brand_kiosk_override";

let settings = null;
let override = readOverride();

/* ------------------------------------------------------------ helpers */

function readOverride() {
  try {
    const params = new URLSearchParams(location.search);
    if (params.has("kiosk")) {
      const v = (params.get("kiosk") || "").toLowerCase();
      const mode = ["off", "false", "0", "no"].includes(v) ? "off" : "on";
      sessionStorage.setItem(SESSION_KEY, mode);
      return mode;
    }
    return sessionStorage.getItem(SESSION_KEY);
  } catch (_e) {
    return null;
  }
}

const q = (root, sel) => (root && root.shadowRoot ? root.shadowRoot.querySelector(sel) : null);

function nodes() {
  const ha = document.querySelector("home-assistant");
  const main = q(ha, "home-assistant-main");
  const mainRoot = main && main.shadowRoot;
  const sidebar = mainRoot && mainRoot.querySelector("ha-sidebar");
  const drawer = mainRoot && mainRoot.querySelector("ha-drawer");
  const panel = mainRoot && mainRoot.querySelector("partial-panel-resolver > *");
  const lovelace = panel && panel.localName === "ha-panel-lovelace" ? panel : null;
  const huiRoot = q(lovelace, "hui-root");
  return { ha, main, mainRoot, sidebar, drawer, panel, huiRoot };
}

function setStyle(root, id, css) {
  if (!root) return;
  let el = root.querySelector(`style#${id}`);
  if (!css) {
    if (el) el.remove();
    return;
  }
  if (!el) {
    el = document.createElement("style");
    el.id = id;
    root.appendChild(el);
  }
  if (el.textContent !== css) el.textContent = css;
}

const cssString = (s) => `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, " ")}"`;

function kioskActive() {
  if (override === "off") return null;
  if (override === "on") return { hide_header: true, hide_sidebar: true, lock: false, ...(settings && settings.kiosk) };
  return settings && settings.kiosk;
}

/* ----------------------------------------------------------- branding */

function titleCss(s) {
  const fill =
    s.colors.length > 1
      ? `background: linear-gradient(90deg, ${s.colors.join(", ")}); -webkit-background-clip: text; background-clip: text; color: transparent;`
      : `color: ${s.colors[0]};`;
  const logo = s.logo_sidebar
    ? `.title::before { content: ""; display: inline-block; flex: none; width: 24px; height: 24px; margin-right: 8px;
         background: url(${cssString(s.logo)}) center / contain no-repeat; vertical-align: middle; }`
    : "";
  return `
    .title { font-size: 0 !important; display: flex !important; align-items: center; overflow: hidden; }
    .title::after { content: ${cssString(s.title)}; font-size: ${s.logo_sidebar ? 18 : 20}px; font-weight: 400; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis; line-height: 1.4; ${fill} }
    ${logo}
    [data-bk-hidden] { display: none !important; }
  `;
}

function applyHiddenItems(n) {
  const root = n.sidebar && n.sidebar.shadowRoot;
  if (!root) return;
  const hide = new Set(((settings && settings.hide_items) || []).map((p) => `/${p}`));
  for (const item of root.querySelectorAll("ha-md-list-item, a[href]")) {
    const href = item.href || item.getAttribute("href");
    if (!href) continue;
    let path;
    try {
      path = new URL(href, location.href).pathname.replace(/\/$/, "");
    } catch (_e) {
      continue;
    }
    const hidden = hide.has(path);
    if (hidden && !item.hasAttribute("data-bk-hidden")) item.setAttribute("data-bk-hidden", "");
    else if (!hidden && item.hasAttribute("data-bk-hidden")) item.removeAttribute("data-bk-hidden");
  }
}

function applyBranding(n) {
  const s = settings;
  setStyle(n.sidebar && n.sidebar.shadowRoot, `${TAG}-title`, s ? titleCss(s) : "");
  applyHiddenItems(n);
  applyBrowserTitle();
  applyFavicon();
}

let titleObserver = null;
// Last title we wrote. Writing document.title fires the observer again, so the
// guard must stop that echo; otherwise a title that still contains "Home Assistant"
// (e.g. the default) loops forever and freezes the page.
let appliedTitle = null;
function fixTitle() {
  if (!settings || !settings.browser_title) return;
  const current = document.title;
  if (current === appliedTitle || !current.includes("Home Assistant")) return;
  if (settings.title.includes("Home Assistant")) return; // nothing to change
  const next = current.replace(/Home Assistant/g, settings.title);
  appliedTitle = next;
  if (next !== current) document.title = next;
}
function applyBrowserTitle() {
  fixTitle();
  const titleEl = document.querySelector("title");
  if (!titleObserver && titleEl) {
    titleObserver = new MutationObserver(fixTitle);
    titleObserver.observe(titleEl, { childList: true, characterData: true, subtree: true });
  }
}

let originalIcons = null;
function applyFavicon() {
  const s = settings;
  const links = [...document.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"]')];
  if (!originalIcons) originalIcons = links.map((l) => [l, l.href]);
  if (s && s.logo_favicon) {
    for (const l of links) if (l.href !== new URL(s.logo, location.href).href) l.href = s.logo;
    if (!links.length) {
      const l = document.createElement("link");
      l.rel = "icon";
      l.href = s.logo;
      document.head.appendChild(l);
    }
  } else if (originalIcons) {
    for (const [l, href] of originalIcons) if (l.href !== href) l.href = href;
  }
}

/* -------------------------------------------------------------- kiosk */

function applyKiosk(n) {
  const k = kioskActive();
  setStyle(
    n.mainRoot,
    `${TAG}-kiosk`,
    k && k.hide_sidebar
      ? `ha-sidebar { display: none !important; }
         ha-drawer { --mdc-drawer-width: 0px !important; --ha-sidebar-width: 0px !important; }
         ha-drawer .mdc-drawer, ha-drawer aside { display: none !important; }`
      : ""
  );
  if (n.drawer && n.drawer.shadowRoot)
    setStyle(n.drawer.shadowRoot, `${TAG}-kiosk`, k && k.hide_sidebar ? `.mdc-drawer { display: none !important; } .mdc-drawer-app-content { margin-left: 0 !important; margin-right: 0 !important; }` : "");
  setStyle(
    n.huiRoot && n.huiRoot.shadowRoot,
    `${TAG}-kiosk`,
    k
      ? `${k.hide_header ? `.header, .toolbar, app-header, ha-app-layout > [slot="header"] { display: none !important; }
           :host { --header-height: 0px !important; }
           #view, hui-view-container { padding-top: env(safe-area-inset-top) !important; min-height: 100vh !important; }` : ""}
         ${k.hide_sidebar ? `ha-menu-button { display: none !important; }` : ""}`
      : ""
  );
  if (k && k.lock && settings && settings.kiosk) {
    const base = `/${k.dashboard}`;
    const target = k.view ? `${base}/${k.view}` : base;
    const path = location.pathname;
    if (path !== base && !path.startsWith(`${base}/`)) navigate(target);
  }
}

function navigate(path) {
  history.replaceState(null, "", path);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: true } }));
}

/* ---------------------------------------------------------- main loop */

function applyAll() {
  const n = nodes();
  if (!n.ha) return;
  applyBranding(n);
  applyKiosk(n);
}

async function connect() {
  let ha = document.querySelector("home-assistant");
  for (let i = 0; i < 600 && !(ha && ha.hass && ha.hass.connection); i++) {
    await new Promise((r) => setTimeout(r, 100));
    ha = document.querySelector("home-assistant");
  }
  if (!ha || !ha.hass) return;
  try {
    await ha.hass.connection.subscribeMessage(
      (msg) => {
        settings = msg || null;
        applyAll();
      },
      { type: "brand_kiosk/subscribe" },
      { resubscribe: true }
    );
  } catch (err) {
    console.warn("Brand & Kiosk: could not load settings", err);
  }
}

if (!window.__brandKiosk) {
  window.__brandKiosk = VERSION;
  connect();
  // Home Assistant re-creates parts of the page as you move around; re-apply cheaply.
  setInterval(applyAll, 700);
  window.addEventListener("location-changed", () => setTimeout(applyAll, 50));
  console.info(`%c BRAND & KIOSK %c ${VERSION} `, "background:#0f766e;color:#fff;font-weight:600", "background:#333;color:#fff");
}
