// Daybook desktop app — native windows around the local Daybook service, plus real in-app browser panes.
// You can open several Daybook windows (e.g. one per screen); each has its own page, browser panes and embedded Chrome.
const {app, BrowserWindow, WebContentsView, ipcMain, session, shell, Tray, Menu, nativeImage, dialog, screen, desktopCapturer} = require("electron");
const path = require("path");
const fs = require("fs");
const http = require("http");
const {spawn} = require("child_process");

const URL_BASE = "http://127.0.0.1:8503";
const DEV_ROOT = path.resolve(__dirname, "..");                       // D:\projects\local-reminders when run from source
const ICON = path.join(__dirname, "assets", "daybook.ico");
const STATE = path.join(app.getPath("userData"), "window-state.json");
const CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/" +
  process.versions.chrome.replace(/\..*/, "") + ".0.0.0 Safari/537.36";
// Google refuses to sign in inside embedded browsers; it accepts Firefox. So *only* Google's sign-in pages see a
// Firefox identity (and none of Chromium's client-hint headers). Everything else stays normal Chrome.
const FIREFOX_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0";
const isGoogleAuth = u => /^https:\/\/accounts\.google\.[a-z.]+\//i.test(u || "") || /^https:\/\/(myaccount|gds)\.google\.com\//i.test(u || "");
let win = null, tray = null, quitting = false, backend = null;   // win = the main window
const wins = new Set();                                          // every Daybook window
const panes = new Map();                                         // pane id → {view, profile, owner}
let paneSeq = 1;

app.setAppUserModelId("com.daybook.app");
if (!app.requestSingleInstanceLock()) { app.quit(); }
app.on("second-instance", (_e, argv) => { showWindow(viewArg(argv)); });
const viewArg = argv => ((argv.find(a => a.startsWith("--view=")) || "").slice(7)) || null;
const ownerOf = e => BrowserWindow.fromWebContents(e.sender);
const hwndOf = w => { const b = w.getNativeWindowHandle(); return b.length >= 8 ? Number(b.readBigUInt64LE(0)) : b.readUInt32LE(0); };

// ---------------- backend (the Python service) ----------------
function ping() {
  return new Promise(res => { const r = http.get(URL_BASE + "/api/settings", x => { x.resume(); res(x.statusCode === 200); }); r.on("error", () => res(false)); r.setTimeout(1500, () => { r.destroy(); res(false); }); });
}
function post(pathname, body, timeout = 2500) {
  return new Promise(res => {
    const r = http.request(URL_BASE + pathname, {method: "POST", headers: {"Content-Type": "application/json"}}, x => { x.resume(); x.on("end", res); });
    r.on("error", res); r.setTimeout(timeout, () => { r.destroy(); res(); }); r.end(JSON.stringify(body || {}));
  });
}
async function ensureBackend() {
  if (await ping()) return true;
  const packed = path.join(process.resourcesPath || "", "backend", "daybook-backend.exe");
  if (app.isPackaged && fs.existsSync(packed)) backend = spawn(packed, [], {detached: true, stdio: "ignore", windowsHide: true, env: {...process.env, DAYBOOK_APP_EXE: process.execPath}});
  else {
    const py = path.join(DEV_ROOT, "venv", "Scripts", "pythonw.exe");
    if (fs.existsSync(py)) backend = spawn(py, [path.join(DEV_ROOT, "daemon.pyw")], {cwd: DEV_ROOT, detached: true, stdio: "ignore", windowsHide: true});
  }
  if (backend) backend.unref();
  for (let i = 0; i < 60; i++) { if (await ping()) return true; await new Promise(r => setTimeout(r, 500)); }
  return false;
}

// ---------------- windows ----------------
function loadState() { try { return JSON.parse(fs.readFileSync(STATE, "utf8").replace(/^\uFEFF/, "")); } catch { return {}; } }
function saveState() {
  if (!win || win.isDestroyed()) return;
  const s = {...loadState(), maximized: win.isMaximized()};
  if (!win.isMaximized() && !win.isMinimized()) s.bounds = win.getBounds();
  try { fs.writeFileSync(STATE, JSON.stringify(s)); } catch {}
}
function fitBounds(b, display) {
  const wa = (display || screen.getDisplayMatching(b || {x: 0, y: 0, width: 10, height: 10})).workArea;
  const w = Math.min((b && b.width) || 1360, wa.width), h = Math.min((b && b.height) || 880, wa.height);
  const x = b && !display ? Math.min(Math.max(b.x, wa.x), wa.x + wa.width - w) : wa.x + (wa.width - w) / 2;
  const y = b && !display ? Math.min(Math.max(b.y, wa.y), wa.y + wa.height - h) : wa.y + (wa.height - h) / 2;
  return {x: Math.round(x), y: Math.round(y), width: w, height: h};
}
function nextDisplay(from) {
  // the screen with the fewest Daybook windows (prefers a different screen than the one you clicked from)
  const all = screen.getAllDisplays(); if (all.length < 2) return null;
  const here = from ? screen.getDisplayMatching(from.getBounds()).id : null;
  const count = d => [...wins].filter(w => !w.isDestroyed() && screen.getDisplayMatching(w.getBounds()).id === d.id).length;
  return all.filter(d => d.id !== here).sort((a, b) => count(a) - count(b))[0] || null;
}
async function createWindow(view, opts = {}) {
  const st = loadState(), main = !opts.extra;
  const bounds = main ? fitBounds(st.bounds) : fitBounds(opts.from ? {...opts.from.getBounds()} : st.bounds, nextDisplay(opts.from));
  if (!main && !nextDisplay(opts.from) && opts.from) { const b = opts.from.getBounds(); bounds.x = b.x + 40; bounds.y = b.y + 40; }  // one screen: cascade
  const w = new BrowserWindow({
    ...bounds, minWidth: 900, minHeight: 600, show: false, title: "Daybook", icon: ICON, backgroundColor: "#0a0b10",
    titleBarStyle: "hidden", titleBarOverlay: {color: "#00000000", symbolColor: "#c9cdda", height: 34},
    webPreferences: {preload: path.join(__dirname, "preload.js"), contextIsolation: true, sandbox: true, spellcheck: true, plugins: true},
  });
  w._layout = {visible: false, rects: {}};
  wins.add(w);
  if (main) { win = w; if (st.maximized) w.maximize(); }
  w.once("ready-to-show", () => { if (!main || !process.argv.includes("--hidden")) w.show(); });
  w.on("close", e => {
    if (main && !quitting && loadState().toTray !== false) { e.preventDefault(); w.hide(); saveState(); return; }
    if (!main && !w._released) {  // an extra window: give its Chrome windows back to the desktop first
      e.preventDefault(); w._released = true;
      post("/api/dock/embed/release", {parent: hwndOf(w)}).then(() => { if (!w.isDestroyed()) w.close(); });
    }
  });
  w.on("closed", () => { wins.delete(w); for (const [id, p] of panes) if (p.owner === w) panes.delete(id); if (w === win) win = null; });
  if (main) ["resize", "move", "maximize", "unmaximize"].forEach(ev => w.on(ev, () => { clearTimeout(w._st); w._st = setTimeout(saveState, 400); }));
  w.webContents.setWindowOpenHandler(({url}) => { if (/^https?:/.test(url)) shell.openExternal(url); return {action: "deny"}; });
  w.webContents.on("will-navigate", (e, url) => { if (!url.startsWith(URL_BASE) && !url.startsWith("http://localhost:8503")) { e.preventDefault(); shell.openExternal(url); } });
  const ok = await ensureBackend();
  if (!ok) { w.loadURL("data:text/html," + encodeURIComponent(`<body style="background:#0a0b10;color:#eee;font:16px Segoe UI;display:grid;place-items:center;height:100vh"><div><h2>Daybook's service didn't start</h2><p>Try restarting Daybook. If it keeps happening, check data\\daemon.log.</p></div></body>`)); return w; }
  w.loadURL(URL_BASE + "/#" + (view || "today"));
  return w;
}
function showWindow(view) {
  if (!win || win.isDestroyed()) return createWindow(view);
  if (win.isMinimized()) win.restore();
  win.show(); win.focus();
  if (view) win.webContents.executeJavaScript(`go(${JSON.stringify(view)})`).catch(() => {});
}

// ---------------- tray ----------------
function createTray() {
  tray = new Tray(nativeImage.createFromPath(ICON));
  tray.setToolTip("Daybook");
  const send = js => () => { showWindow(); win && win.webContents.executeJavaScript(js).catch(() => {}); };
  tray.setContextMenu(Menu.buildFromTemplate([
    {label: "Open Daybook", click: () => showWindow()},
    {label: "New window", click: () => createWindow("today", {extra: true, from: win})},
    {type: "separator"},
    {label: "New reminder", click: send("reminderModal()")}, {label: "New note", click: send("templateModal()")},
    {label: "Record voice memo", click: send("go('memos');setTimeout(memoRecToggle,300)")},
    {label: "Browser", click: () => showWindow("browser")}, {label: "Timers", click: () => showWindow("clock")},
    {type: "separator"},
    {label: "Quit Daybook (reminders keep running)", click: () => { quitting = true; app.quit(); }},
  ]));
  tray.on("click", () => showWindow());
}

// ---------------- in-app browser panes ----------------
function partitionFor(profile) { return "persist:daybook-" + String(profile || "personal").toLowerCase().replace(/[^a-z0-9]+/g, "-"); }
const prepared = new Set();
function prepareSession(part) {
  if (prepared.has(part)) return session.fromPartition(part);
  prepared.add(part);
  const s = session.fromPartition(part);
  s.setUserAgent(CHROME_UA);                                   // so sites treat it as normal Chrome
  s.webRequest.onBeforeSendHeaders((d, cb) => {
    const h = d.requestHeaders;
    if (isGoogleAuth(d.url) || (d.webContents && isGoogleAuth(d.webContents.getURL()) && /google/.test(d.url))) {
      h["User-Agent"] = FIREFOX_UA;
      for (const k of Object.keys(h)) if (/^sec-ch-ua/i.test(k)) delete h[k];
    }
    cb({requestHeaders: h});
  });
  s.setPermissionRequestHandler(async (wc, perm, cb, details) => {
    if (["fullscreen", "clipboard-sanitized-write", "notifications", "pointerLock"].includes(perm)) return cb(true);
    if (["media", "geolocation", "midiSysex", "display-capture"].includes(perm)) {
      const site = new URL(details.requestingUrl || wc.getURL()).host;
      const what = perm === "media" ? ((details.mediaTypes || []).join(" & ") || "camera/microphone") : perm;
      const parent = BrowserWindow.fromWebContents(wc) || [...panes.values()].find(p => p.view.webContents === wc)?.owner || win;
      const r = await dialog.showMessageBox(parent, {type: "question", buttons: ["Allow", "Block"], defaultId: 1, cancelId: 1, title: "Daybook", message: `${site} wants to use your ${what}`});
      return cb(r.response === 0);
    }
    cb(false);
  });
  s.on("will-download", (_e, item, wc) => {
    item.setSavePath(path.join(app.getPath("downloads"), item.getFilename()));
    const owner = [...panes.values()].find(p => p.view.webContents === wc)?.owner || win;
    item.once("done", (_x, state) => sendPanes(owner, {toast: state === "completed" ? `Downloaded ${item.getFilename()} → Downloads` : `Download ${state}`}));
  });
  return s;
}
function paneInfo(id, p) {
  const wc = p.view.webContents;
  return {id, profile: p.profile, title: wc.getTitle() || "New tab", url: wc.getURL(), loading: wc.isLoading(), canBack: wc.navigationHistory.canGoBack(), canFwd: wc.navigationHistory.canGoForward(), favicon: p.favicon || "", muted: wc.isAudioMuted(), audible: wc.isCurrentlyAudible()};
}
const panesOf = owner => [...panes].filter(([, p]) => p.owner === owner);
function sendPanes(owner, extra) {
  if (!owner || owner.isDestroyed()) return;
  owner.webContents.send("browser:update", {panes: panesOf(owner).map(([id, p]) => paneInfo(id, p)), ...(extra || {})});
}
function openPane(profile, url, owner) {
  owner = owner || win;
  const part = partitionFor(profile);
  prepareSession(part);
  const view = new WebContentsView({webPreferences: {partition: part, contextIsolation: true, sandbox: true, plugins: true, preload: path.join(__dirname, "browser-preload.js")}});
  view.setBackgroundColor("#ffffff");
  const id = paneSeq++;
  const p = {view, profile, owner};
  panes.set(id, p);
  view.setVisible(false);
  owner.contentView.addChildView(view);
  const wc = view.webContents;
  wc.setWindowOpenHandler(({url: u, disposition, features}) => {
    if (disposition === "new-window" && /width|height|popup/.test(features || "")) {      // sign-in popups (Google, Discord…) keep the same profile
      return {action: "allow", overrideBrowserWindowOptions: {parent: owner, width: 520, height: 700, autoHideMenuBar: true, webPreferences: {partition: part}}};
    }
    openPane(profile, u, owner); return {action: "deny"};                               // links that open a new tab → a new pane
  });
  ["did-start-loading", "did-stop-loading", "page-title-updated", "did-navigate", "did-navigate-in-page", "audio-state-changed"].forEach(ev => wc.on(ev, () => sendPanes(owner)));
  wc.on("page-favicon-updated", (_e, icons) => { p.favicon = icons[0] || ""; sendPanes(owner); });
  wc.on("enter-html-full-screen", () => { p.full = true; layoutPanes(owner); });
  wc.on("leave-html-full-screen", () => { p.full = false; layoutPanes(owner); });
  wc.on("before-input-event", (e, i) => { // browser shortcuts inside a pane
    if (i.type !== "keyDown") return;
    const k = i.key.toLowerCase();
    if (i.control && k === "w") { e.preventDefault(); closePane(id); }
    else if (i.control && k === "t") { e.preventDefault(); owner.webContents.send("browser:shortcut", {action: "new", profile}); }
    else if (i.control && k === "l") { e.preventDefault(); owner.webContents.focus(); owner.webContents.send("browser:shortcut", {action: "address", id}); }
    else if ((i.control && k === "r") || k === "f5") { e.preventDefault(); wc.reload(); }
    else if (i.alt && k === "arrowleft") { e.preventDefault(); wc.navigationHistory.goBack(); }
    else if (i.alt && k === "arrowright") { e.preventDefault(); wc.navigationHistory.goForward(); }
  });
  wc.on("render-process-gone", () => sendPanes(owner, {toast: "A page crashed — press reload"}));
  wc.loadURL(url || "https://www.google.com");
  sendPanes(owner, {focus: id});
  return id;
}
function closePane(id) {
  const p = panes.get(id); if (!p) return;
  if (!p.owner.isDestroyed()) p.owner.contentView.removeChildView(p.view);
  p.view.webContents.close();
  panes.delete(id); sendPanes(p.owner);
}
function layoutPanes(owner, l) {
  if (!owner || owner.isDestroyed()) return;
  if (l) owner._layout = l;
  const {visible, rects} = owner._layout;
  const mine = panesOf(owner), full = mine.find(([, p]) => p.full);
  for (const [id, p] of mine) {
    const r = rects[id];
    if (full) { const show = full[0] === id && visible; p.view.setVisible(show); if (show) { const [w, h] = owner.getContentSize(); p.view.setBounds({x: 0, y: 0, width: w, height: h}); } continue; }
    if (!visible || !r || r.w < 20 || r.h < 20) { p.view.setVisible(false); continue; }
    p.view.setBounds({x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.w), height: Math.round(r.h)});
    p.view.setVisible(true);
  }
}
ipcMain.handle("browser:open", (e, {profile, url}) => openPane(profile, url, ownerOf(e)));
ipcMain.handle("browser:close", (_e, id) => closePane(id));
ipcMain.handle("browser:list", e => panesOf(ownerOf(e)).map(([id, p]) => paneInfo(id, p)));
ipcMain.on("browser:layout", (e, l) => layoutPanes(ownerOf(e), l));
ipcMain.handle("browser:nav", (_e, {id, action, url}) => {
  const p = panes.get(id); if (!p) return; const wc = p.view.webContents;
  if (action === "back") wc.navigationHistory.goBack(); else if (action === "forward") wc.navigationHistory.goForward();
  else if (action === "reload") wc.reload(); else if (action === "stop") wc.stop(); else if (action === "mute") wc.setAudioMuted(!wc.isAudioMuted());
  else if (action === "go" && url) wc.loadURL(url); else if (action === "focus") wc.focus();
  else if (action === "external") shell.openExternal(wc.getURL());
  else if (action === "zoomin") wc.setZoomFactor(Math.min(3, wc.getZoomFactor() + 0.1)); else if (action === "zoomout") wc.setZoomFactor(Math.max(0.3, wc.getZoomFactor() - 0.1));
  else if (action === "clear") { session.fromPartition(partitionFor(p.profile)).clearStorageData(); }
  sendPanes(p.owner);
});
ipcMain.handle("app:settings", (_e, s) => { const st = {...loadState(), ...s}; fs.writeFileSync(STATE, JSON.stringify(st)); if ("startAtLogin" in s) app.setLoginItemSettings({openAtLogin: !!s.startAtLogin, args: ["--hidden"]}); return st; });
ipcMain.handle("app:info", e => ({version: app.getVersion(), packaged: app.isPackaged, ...loadState(), startAtLogin: app.getLoginItemSettings().openAtLogin,
  main: ownerOf(e) === win, windows: wins.size, hwnd: hwndOf(ownerOf(e))}));
ipcMain.handle("app:newWindow", (e, view) => { createWindow(view || "today", {extra: true, from: ownerOf(e)}); return true; });

// ---------------- start ----------------
// every page in a browser pane (and sign-in pop-ups): match navigator.userAgent to the headers above
app.on("web-contents-created", (_e, wc) => {
  if (wc.getType() === "webview" || !wc.session || wc.session === session.defaultSession) return;
  wc.on("did-start-navigation", d => { if (!d.isMainFrame) return; const ua = isGoogleAuth(d.url) ? FIREFOX_UA : CHROME_UA; if (wc.getUserAgent() !== ua) wc.setUserAgent(ua); });
  wc.on("did-create-window", w => w.webContents.setUserAgent(isGoogleAuth(w.webContents.getURL()) ? FIREFOX_UA : CHROME_UA));
});
app.whenReady().then(async () => {
  // mic + screen capture for voice/video notes inside Daybook's own pages
  session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(["media", "display-capture", "clipboard-sanitized-write", "notifications", "fullscreen"].includes(perm)));
  session.defaultSession.setDisplayMediaRequestHandler(async (req, cb) => {
    const sources = await desktopCapturer.getSources({types: ["screen", "window"], thumbnailSize: {width: 0, height: 0}});
    const names = sources.map(s => s.name);
    const parent = (req.frame && BrowserWindow.fromWebContents(req.frame)) || win;
    const r = await dialog.showMessageBox(parent, {type: "question", title: "Record your screen", message: "What should Daybook record?", buttons: [...names.slice(0, 8), "Cancel"], cancelId: Math.min(8, names.length)});
    if (r.response >= Math.min(8, names.length)) return cb({});
    cb({video: sources[r.response], audio: "loopback"});
  });
  createTray();
  const st = loadState();
  if (app.isPackaged && st.firstRunDone === undefined) {  // installed app: start with Windows so reminders always work
    app.setLoginItemSettings({openAtLogin: true, args: ["--hidden"]});
    fs.writeFileSync(STATE, JSON.stringify({...st, firstRunDone: true}));
  }
  await createWindow(viewArg(process.argv));
});
let released = false;
app.on("before-quit", e => {
  quitting = true; saveState();
  if (released) return;
  e.preventDefault();  // hand embedded Chrome windows back to the desktop before the windows go away
  post("/api/dock/embed/release", {all: 1}).then(() => { released = true; app.quit(); });
});
app.on("window-all-closed", e => e.preventDefault()); // stay in the tray
