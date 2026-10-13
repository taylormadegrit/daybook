// Daybook desktop app — a native window around the local Daybook service, plus real in-app browser panes.
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
let win = null, tray = null, quitting = false, backend = null;
const panes = new Map(); // id → {view, profile}
let paneSeq = 1;

app.setAppUserModelId("com.daybook.app");
if (!app.requestSingleInstanceLock()) { app.quit(); }
app.on("second-instance", (_e, argv) => { showWindow(viewArg(argv)); });
const viewArg = argv => ((argv.find(a => a.startsWith("--view=")) || "").slice(7)) || null;

// ---------------- backend (the Python service) ----------------
function ping() {
  return new Promise(res => { const r = http.get(URL_BASE + "/api/settings", x => { x.resume(); res(x.statusCode === 200); }); r.on("error", () => res(false)); r.setTimeout(1500, () => { r.destroy(); res(false); }); });
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

// ---------------- main window ----------------
function loadState() { try { return JSON.parse(fs.readFileSync(STATE, "utf8").replace(/^﻿/, "")); } catch { return {}; } }
function saveState() {
  if (!win || win.isDestroyed()) return;
  const s = {...loadState(), maximized: win.isMaximized()};
  if (!win.isMaximized() && !win.isMinimized()) s.bounds = win.getBounds();
  try { fs.writeFileSync(STATE, JSON.stringify(s)); } catch {}
}
function fitBounds(b) {
  const wa = screen.getDisplayMatching(b || {x: 0, y: 0, width: 10, height: 10}).workArea;
  const w = Math.min((b && b.width) || 1360, wa.width), h = Math.min((b && b.height) || 880, wa.height);
  const x = b ? Math.min(Math.max(b.x, wa.x), wa.x + wa.width - w) : wa.x + (wa.width - w) / 2;
  const y = b ? Math.min(Math.max(b.y, wa.y), wa.y + wa.height - h) : wa.y + (wa.height - h) / 2;
  return {x: Math.round(x), y: Math.round(y), width: w, height: h};
}
async function createWindow(view) {
  const st = loadState();
  win = new BrowserWindow({
    ...fitBounds(st.bounds), minWidth: 900, minHeight: 600, show: false, title: "Daybook", icon: ICON, backgroundColor: "#0a0b10",
    titleBarStyle: "hidden", titleBarOverlay: {color: "#00000000", symbolColor: "#c9cdda", height: 34},
    webPreferences: {preload: path.join(__dirname, "preload.js"), contextIsolation: true, sandbox: true, spellcheck: true, plugins: true},
  });
  if (st.maximized) win.maximize();
  win.once("ready-to-show", () => { if (!process.argv.includes("--hidden")) win.show(); });
  win.on("close", e => { if (!quitting && loadState().toTray !== false) { e.preventDefault(); win.hide(); saveState(); } });
  ["resize", "move", "maximize", "unmaximize"].forEach(ev => win.on(ev, () => { clearTimeout(win._st); win._st = setTimeout(saveState, 400); }));
  win.webContents.setWindowOpenHandler(({url}) => { if (/^https?:/.test(url)) shell.openExternal(url); return {action: "deny"}; });
  win.webContents.on("will-navigate", (e, url) => { if (!url.startsWith(URL_BASE) && !url.startsWith("http://localhost:8503")) { e.preventDefault(); shell.openExternal(url); } });
  const ok = await ensureBackend();
  if (!ok) { win.loadURL("data:text/html," + encodeURIComponent(`<body style="background:#0a0b10;color:#eee;font:16px Segoe UI;display:grid;place-items:center;height:100vh"><div><h2>Daybook's service didn't start</h2><p>Try restarting Daybook. If it keeps happening, check data\\daemon.log.</p></div></body>`)); return; }
  win.loadURL(URL_BASE + "/#" + (view || "today"));
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
  const send = js => () => { showWindow(); win.webContents.executeJavaScript(js).catch(() => {}); };
  tray.setContextMenu(Menu.buildFromTemplate([
    {label: "Open Daybook", click: () => showWindow()},
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
  s.setUserAgent(CHROME_UA);                                   // so Google & co. treat it as normal Chrome
  s.setPermissionRequestHandler(async (wc, perm, cb, details) => {
    if (["fullscreen", "clipboard-sanitized-write", "notifications", "pointerLock"].includes(perm)) return cb(true);
    if (["media", "geolocation", "midiSysex", "display-capture"].includes(perm)) {
      const site = new URL(details.requestingUrl || wc.getURL()).host;
      const what = perm === "media" ? ((details.mediaTypes || []).join(" & ") || "camera/microphone") : perm;
      const r = await dialog.showMessageBox(win, {type: "question", buttons: ["Allow", "Block"], defaultId: 1, cancelId: 1, title: "Daybook", message: `${site} wants to use your ${what}`});
      return cb(r.response === 0);
    }
    cb(false);
  });
  s.on("will-download", (_e, item) => { item.setSavePath(path.join(app.getPath("downloads"), item.getFilename())); item.once("done", (_x, state) => sendPanes({toast: state === "completed" ? `Downloaded ${item.getFilename()} → Downloads` : `Download ${state}`})); });
  return s;
}
function paneInfo(id, p) {
  const wc = p.view.webContents;
  return {id, profile: p.profile, title: wc.getTitle() || "New tab", url: wc.getURL(), loading: wc.isLoading(), canBack: wc.navigationHistory.canGoBack(), canFwd: wc.navigationHistory.canGoForward(), favicon: p.favicon || "", muted: wc.isAudioMuted(), audible: wc.isCurrentlyAudible()};
}
function sendPanes(extra) {
  if (!win || win.isDestroyed()) return;
  win.webContents.send("browser:update", {panes: [...panes].map(([id, p]) => paneInfo(id, p)), ...(extra || {})});
}
function openPane(profile, url) {
  const part = partitionFor(profile);
  prepareSession(part);
  const view = new WebContentsView({webPreferences: {partition: part, contextIsolation: true, sandbox: true, plugins: true, preload: path.join(__dirname, "browser-preload.js")}});
  view.setBackgroundColor("#ffffff");
  const id = paneSeq++;
  const p = {view, profile};
  panes.set(id, p);
  view.setVisible(false);
  win.contentView.addChildView(view);
  const wc = view.webContents;
  wc.setWindowOpenHandler(({url: u, disposition, features}) => {
    if (disposition === "new-window" && /width|height|popup/.test(features || "")) {      // sign-in popups (Google, Discord…) keep the same profile
      return {action: "allow", overrideBrowserWindowOptions: {parent: win, width: 520, height: 700, autoHideMenuBar: true, webPreferences: {partition: part}}};
    }
    openPane(profile, u); return {action: "deny"};                                      // links that open a new tab → a new pane
  });
  ["did-start-loading", "did-stop-loading", "page-title-updated", "did-navigate", "did-navigate-in-page", "audio-state-changed"].forEach(ev => wc.on(ev, () => sendPanes()));
  wc.on("page-favicon-updated", (_e, icons) => { p.favicon = icons[0] || ""; sendPanes(); });
  wc.on("enter-html-full-screen", () => { p.full = true; layoutPanes(); });
  wc.on("leave-html-full-screen", () => { p.full = false; layoutPanes(); });
  wc.on("before-input-event", (e, i) => { // browser shortcuts inside a pane
    if (i.type !== "keyDown") return;
    const k = i.key.toLowerCase();
    if (i.control && k === "w") { e.preventDefault(); closePane(id); }
    else if (i.control && k === "t") { e.preventDefault(); win.webContents.send("browser:shortcut", {action: "new", profile}); }
    else if (i.control && k === "l") { e.preventDefault(); win.webContents.focus(); win.webContents.send("browser:shortcut", {action: "address", id}); }
    else if ((i.control && k === "r") || k === "f5") { e.preventDefault(); wc.reload(); }
    else if (i.alt && k === "arrowleft") { e.preventDefault(); wc.navigationHistory.goBack(); }
    else if (i.alt && k === "arrowright") { e.preventDefault(); wc.navigationHistory.goForward(); }
  });
  wc.on("render-process-gone", () => sendPanes({toast: "A page crashed — press reload"}));
  wc.loadURL(url || "https://www.google.com");
  sendPanes({focus: id});
  return id;
}
function closePane(id) {
  const p = panes.get(id); if (!p) return;
  win.contentView.removeChildView(p.view);
  p.view.webContents.close();
  panes.delete(id); sendPanes();
}
let lastLayout = {visible: false, rects: {}};
function layoutPanes(l) {
  if (l) lastLayout = l;
  const {visible, rects} = lastLayout;
  const full = [...panes].find(([, p]) => p.full);
  for (const [id, p] of panes) {
    const r = rects[id];
    if (full) { const show = full[0] === id && visible; p.view.setVisible(show); if (show) { const [w, h] = win.getContentSize(); p.view.setBounds({x: 0, y: 0, width: w, height: h}); } continue; }
    if (!visible || !r || r.w < 20 || r.h < 20) { p.view.setVisible(false); continue; }
    p.view.setBounds({x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.w), height: Math.round(r.h)});
    p.view.setVisible(true);
  }
}
ipcMain.handle("browser:open", (_e, {profile, url}) => openPane(profile, url));
ipcMain.handle("browser:close", (_e, id) => closePane(id));
ipcMain.handle("browser:list", () => [...panes].map(([id, p]) => paneInfo(id, p)));
ipcMain.on("browser:layout", (_e, l) => layoutPanes(l));
ipcMain.handle("browser:nav", (_e, {id, action, url}) => {
  const p = panes.get(id); if (!p) return; const wc = p.view.webContents;
  if (action === "back") wc.navigationHistory.goBack(); else if (action === "forward") wc.navigationHistory.goForward();
  else if (action === "reload") wc.reload(); else if (action === "stop") wc.stop(); else if (action === "mute") wc.setAudioMuted(!wc.isAudioMuted());
  else if (action === "go" && url) wc.loadURL(url); else if (action === "focus") wc.focus();
  else if (action === "external") shell.openExternal(wc.getURL());
  else if (action === "zoomin") wc.setZoomFactor(Math.min(3, wc.getZoomFactor() + 0.1)); else if (action === "zoomout") wc.setZoomFactor(Math.max(0.3, wc.getZoomFactor() - 0.1));
  else if (action === "clear") { session.fromPartition(partitionFor(p.profile)).clearStorageData(); }
  sendPanes();
});
ipcMain.handle("app:settings", (_e, s) => { const st = {...loadState(), ...s}; fs.writeFileSync(STATE, JSON.stringify(st)); if ("startAtLogin" in s) app.setLoginItemSettings({openAtLogin: !!s.startAtLogin, args: ["--hidden"]}); return st; });
ipcMain.handle("app:info", () => ({version: app.getVersion(), packaged: app.isPackaged, ...loadState(), startAtLogin: app.getLoginItemSettings().openAtLogin}));

// ---------------- start ----------------
app.whenReady().then(async () => {
  // mic + screen capture for voice/video notes inside Daybook's own pages
  session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(["media", "display-capture", "clipboard-sanitized-write", "notifications", "fullscreen"].includes(perm)));
  session.defaultSession.setDisplayMediaRequestHandler(async (_req, cb) => {
    const sources = await desktopCapturer.getSources({types: ["screen", "window"], thumbnailSize: {width: 0, height: 0}});
    const names = sources.map(s => s.name);
    const r = await dialog.showMessageBox(win, {type: "question", title: "Record your screen", message: "What should Daybook record?", buttons: [...names.slice(0, 8), "Cancel"], cancelId: Math.min(8, names.length)});
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
app.on("before-quit", () => { quitting = true; saveState(); });
app.on("window-all-closed", e => e.preventDefault()); // stay in the tray
