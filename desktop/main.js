// Daybook desktop app — native windows around the local Daybook service, plus real in-app browser panes.
// You can open several Daybook windows (e.g. one per screen); each has its own page, browser panes and embedded Chrome.
const {app, BrowserWindow, WebContentsView, ipcMain, session, shell, Tray, Menu, nativeImage, dialog, screen, desktopCapturer, globalShortcut} = require("electron");
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
const PRIMARY = app.requestSingleInstanceLock();
if (!PRIMARY) { app.quit(); return; }
app.on("second-instance", (_e, argv) => { const u = urlArg(argv); if (u) openFromOutside(u); else showWindow(viewArg(argv)); });
const viewArg = argv => ((argv.find(a => a.startsWith("--view=")) || "").slice(7)) || null;
// a link opened from another app (Daybook set as the default browser): "Daybook.exe --url <link or .html file>"
function urlArg(argv) {  // Chromium moves "--" options first, so the link can be anywhere in the list
  if (!argv.includes("--url") && !argv.some(a => /^https?:\/\//i.test(a))) return null;
  for (const raw of argv.slice(1)) {
    if (/^(https?|file):\/\//i.test(raw)) return raw;
    if (/\.(html?|xhtml|pdf)$/i.test(raw)) { try { if (fs.existsSync(raw)) return require("url").pathToFileURL(raw).href; } catch {} }
  }
  return null;
}
async function openFromOutside(url) {
  if (!win || win.isDestroyed()) await createWindow("browser");
  const w = win; if (w.isMinimized()) w.restore(); w.show(); w.focus();
  const open = () => { openPane(loadState().linkProfile || "personal", url, w); w.webContents.executeJavaScript(`go("browser")`).catch(() => {}); };
  if (w.webContents.isLoading()) w.webContents.once("did-finish-load", () => setTimeout(open, 400)); else open();
}
const ownerOf = e => BrowserWindow.fromWebContents(e.sender);
const hwndOf = w => { const b = w.getNativeWindowHandle(); return b.length >= 8 ? Number(b.readBigUInt64LE(0)) : b.readUInt32LE(0); };

// ---------------- backend (the Python service) ----------------
function ping() {
  return new Promise(res => { const r = http.get(URL_BASE + "/api/settings", x => { x.resume(); res(x.statusCode === 200); }); r.on("error", () => res(false)); r.setTimeout(1500, () => { r.destroy(); res(false); }); });
}
function postJson(pathname, body) {  // POST and read the JSON answer
  return new Promise(res => {
    const r = http.request(URL_BASE + pathname, {method: "POST", headers: {"Content-Type": "application/json"}}, x => { let d = ""; x.on("data", c => d += c); x.on("end", () => { try { res(JSON.parse(d)); } catch { res(null); } }); });
    r.on("error", () => res(null)); r.setTimeout(8000, () => { r.destroy(); res(null); }); r.end(JSON.stringify(body || {}));
  });
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
function writeState(s) { const tmp = STATE + ".tmp"; try { fs.writeFileSync(tmp, JSON.stringify(s)); fs.renameSync(tmp, STATE); } catch (e) { console.error("state", e); } }
function saveState() {
  if (!win || win.isDestroyed()) return;
  const s = {...loadState(), maximized: win.isMaximized()};
  if (!win.isMaximized() && !win.isMinimized()) s.bounds = win.getBounds();
  writeState(s);
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
    webPreferences: {preload: path.join(__dirname, "preload.js"), contextIsolation: true, sandbox: true, spellcheck: true, plugins: true, disableHtmlFullscreenWindowResize: true},
  });
  w._layout = {visible: false, rects: {}};
  const relayout = () => { if (!w.isDestroyed()) w.webContents.send("browser:relayout"); };
  const hideDocked = () => post("/api/dock/embed/place", {visible: false, items: [], parent: hwndOf(w)});
  w.on("move", relayout); w.on("moved", relayout); w.on("resize", relayout); w.on("restore", relayout); w.on("show", relayout);
  w.on("enter-full-screen", () => { layoutPanes(w); });
  w.on("leave-full-screen", () => {
    let changed = false;
    for (const [, p] of panesOf(w)) {
      if (p.full) {
        p.full = false;
        changed = true;
        try { p.view.webContents.executeJavaScript("if (document.fullscreenElement) document.exitFullscreen().catch(()=>{})"); } catch (e) {}
      }
    }
    if (w._restoreMaximized) {
      w._restoreMaximized = false;
      try { if (!w.isDestroyed() && !w.isMaximized()) w.maximize(); } catch (e) {}
    }
    if (changed) { layoutPanes(w); sendPanes(w); }
  });
  w.on("hide", hideDocked); w.on("minimize", hideDocked);
  // Daybook's page draws its own right-click menu; for text boxes it lets this event through so it can show
  // spelling suggestions (Chromium only reports them here).
  w.webContents.on("context-menu", (_e, m) => {
    if (!w.isDestroyed()) w.webContents.send("ctx:params", {x: m.x, y: m.y, isEditable: m.isEditable, misspelledWord: m.misspelledWord || "",
      suggestions: (m.dictionarySuggestions || []).slice(0, 6), canPaste: !!(m.editFlags && m.editFlags.canPaste)});
  });
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
  const logPath = app.isPackaged ? path.join(process.env.DAYBOOK_DATA || path.join(process.env.LOCALAPPDATA || "", "Daybook"), "daemon.log") : path.join(DEV_ROOT, "data", "daemon.log");
  if (!ok) { w.loadURL("data:text/html," + encodeURIComponent(`<body style="background:#0a0b10;color:#eee;font:16px Segoe UI;display:grid;place-items:center;height:100vh"><div><h2>Daybook's service didn't start</h2><p>Daybook will keep trying in the background. If it keeps happening, check ${logPath}.</p></div></body>`)); return w; }
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
// ---- Central Download Manager: Chrome-like download handling for all sessions and profiles ----
const downloads = new Map();
let downloadSeq = 1;
function setupDownloads(s) {
  if (!s || s._hasDownloads) return;
  s._hasDownloads = true;
  s.on("will-download", (_e, item, wc) => handleDownload(item, wc));
}
function handleDownload(item, wc) {
  const dId = downloadSeq++;
  const rawName = item.getFilename() || "download";
  let cleanName = rawName.replace(/[<>:"/\\|?*\x00-\x1F]/g, "_").trim();
  if (!cleanName || cleanName === "." || cleanName === "..") cleanName = "download";
  const {name, ext} = path.parse(cleanName);
  const dir = app.getPath("downloads");
  try { fs.mkdirSync(dir, {recursive: true}); } catch (e) {}
  let file = path.join(dir, (name || "download") + ext);
  for (let n = 1; fs.existsSync(file); n++) file = path.join(dir, `${name || "download"} (${n})${ext}`);
  item.setSavePath(file);

  const owner = (wc && BrowserWindow.fromWebContents(wc)) ||
    [...panes.values()].find(p => p.view.webContents === wc)?.owner ||
    win;

  const dl = {
    id: dId,
    filename: path.basename(file),
    savePath: file,
    url: item.getURL() || "",
    mimeType: item.getMimeType() || "",
    totalBytes: item.getTotalBytes() || 0,
    receivedBytes: 0,
    state: "progressing",
    percent: 0,
    startTime: Date.now(),
    doneTime: null,
  };
  downloads.set(dId, {record: dl, item, wc, owner});

  // If a pane was spawned purely to trigger this download (e.g. target="_blank" download link), hide it so the user doesn't see a blank tab
  let placeholderId = null;
  for (const [id, p] of panes) {
    if (p.view.webContents === wc) {
      if (!p._loadedAnyPage || p.view.webContents.getURL() === "" || p.view.webContents.getURL() === "about:blank" || p.view.webContents.getURL() === item.getURL()) {
        placeholderId = id;
        p._downloadPlaceholder = true;
      }
      break;
    }
  }
  if (placeholderId && owner && !owner.isDestroyed()) {
    layoutPanes(owner);
    sendPanes(owner);
  }

  broadcastDownloads();

  item.on("updated", (_e, state) => {
    dl.state = state;
    dl.receivedBytes = item.getReceivedBytes();
    dl.totalBytes = item.getTotalBytes();
    if (dl.totalBytes > 0) {
      dl.percent = Math.min(100, Math.round((dl.receivedBytes / dl.totalBytes) * 100));
    }
    broadcastDownloads();
  });

  item.once("done", (_e, state) => {
    dl.state = state; // "completed", "cancelled", "interrupted"
    dl.receivedBytes = item.getReceivedBytes();
    if (state === "completed") dl.percent = 100;
    dl.doneTime = Date.now();
    broadcastDownloads();

    if (placeholderId) {
      closePane(placeholderId);
    }

    if (owner && !owner.isDestroyed()) {
      sendPanes(owner, {
        toast: state === "completed"
          ? `Downloaded ${dl.filename} → Downloads`
          : `Download ${state}: ${dl.filename}`,
        downloadId: dId
      });
    }
  });
}

function broadcastDownloads() {
  const list = [...downloads.values()].map(d => d.record).reverse().slice(0, 50);
  for (const w of wins) {
    if (!w.isDestroyed()) {
      w.webContents.send("browser:downloads", list);
    }
  }
}
// Ad blocker for the in-app browser (ads + trackers, YouTube ads included). Block lists are cached on disk,
// and a copy ships inside the app, so it works with no internet from the very first launch.
const ADB = {blocker: null, on: loadState().adblock !== false, blocked: 0, sessions: new Set()};
const ADB_CACHE = path.join(app.getPath("userData"), "adblock-engine.bin");
async function adblockInit() {
  try {
    const {ElectronBlocker} = require("@ghostery/adblocker-electron");
    const seed = path.join(__dirname, "assets", "adblock-engine.bin");
    if (!fs.existsSync(ADB_CACHE) && fs.existsSync(seed)) fs.copyFileSync(seed, ADB_CACHE);
    // refresh the lists weekly when online; otherwise (or offline) use the saved copy
    const stale = !fs.existsSync(ADB_CACHE) || Date.now() - fs.statSync(ADB_CACHE).mtimeMs > 7 * 864e5;
    if (stale) {
      ADB.blocker = await ElectronBlocker.fromPrebuiltAdsAndTracking(fetch).catch(() => null);
      if (ADB.blocker) try { fs.writeFileSync(ADB_CACHE, ADB.blocker.serialize()); } catch {}
    }
    if (!ADB.blocker && fs.existsSync(ADB_CACHE)) ADB.blocker = ElectronBlocker.deserialize(new Uint8Array(fs.readFileSync(ADB_CACHE)));
    if (!ADB.blocker) return;
    ADB.blocker.on("request-blocked", () => { ADB.blocked++; });
    const getCosmetics = ADB.blocker.getCosmeticsFilters.bind(ADB.blocker);
    ADB.blocker.getCosmeticsFilters = opts => {
      const r = getCosmetics(opts);
      if (/(^|\.)youtube\.com$/.test(opts.hostname || "")) r.scripts = [];
      else r.scripts = (r.scripts || []).map(js => `{\n${js}\n}`);
      return r;
    };
    ADB.on = loadState().adblock !== false;
    if (ADB.on) for (const s of ADB.sessions) adblockEnable(s);
  } catch (e) { console.error("adblock", e); }
}
const ADB_IPC = ["@ghostery/adblocker/inject-cosmetic-filters", "@ghostery/adblocker/is-mutation-observer-enabled"];
function adblockEnable(s) {  // one blocker, many profiles: clear its page handlers before each enable so none fail
  if (!ADB.blocker) return;
  try { ADB_IPC.forEach(c => ipcMain.removeHandler(c)); ADB.blocker.enableBlockingInSession(s); } catch (e) { console.error("adblock enable", e); }
}
function adblockDisable(s) { try { ADB.blocker.disableBlockingInSession(s); } catch {} }
function adblockSession(s) { ADB.sessions.add(s); if (ADB.blocker && ADB.on) adblockEnable(s); }
ipcMain.on("browser:adblock-on", e => { e.returnValue = ADB.on; });
ipcMain.handle("browser:adblock", (_e, on) => {
  if (typeof on === "boolean" && ADB.blocker) {
    ADB.on = on; writeState({...loadState(), adblock: on});
    for (const s of ADB.sessions) on ? adblockEnable(s) : adblockDisable(s);
  }
  return {ready: !!ADB.blocker, on: ADB.on, blocked: ADB.blocked};
});

let privacySignals = loadState().privacySignals !== false;
ipcMain.handle("browser:privacy", (_e, s) => {
  if (s && typeof s.signals === "boolean") { privacySignals = s.signals; writeState({...loadState(), privacySignals}); }
  if (s && s.clear) {  // wipe history, cookies, logins and site data for one browser profile
    const ses = session.fromPartition(partitionFor(s.clear));
    return Promise.all([ses.clearStorageData(), ses.clearCache(), ses.clearAuthCache()]).then(() => { forgetSite(partitionFor(s.clear), ""); return {cleared: true}; });
  }
  if (s && s.forgetPermissions) { permCache = {}; try { fs.writeFileSync(PERMS, "{}"); } catch {} }
  return {signals: privacySignals, linkProfile: loadState().linkProfile || "personal"};
});

// ---- Daybook as the default browser (Windows only lets the user pick it, in Settings → Default apps) ----
const { execFile } = require("child_process");
const reg = args => new Promise(res => execFile("reg", args, {windowsHide: true}, (err, out) => res(err ? null : out)));
function handlerCommand() {
  const app_ = app.isPackaged ? "" : `"${app.getAppPath()}" `;
  return `"${process.execPath}" ${app_}--url "%1"`;
}
async function registerBrowser() {
  const cmd = handlerCommand(), icon = `"${process.execPath}",0`, base = "HKCU\\Software\\Clients\\StartMenuInternet\\Daybook";
  const sets = [
    ["HKCU\\Software\\Classes\\DaybookURL", "", "Daybook link"], ["HKCU\\Software\\Classes\\DaybookURL", "URL Protocol", ""],
    ["HKCU\\Software\\Classes\\DaybookURL\\DefaultIcon", "", icon], ["HKCU\\Software\\Classes\\DaybookURL\\shell\\open\\command", "", cmd],
    ["HKCU\\Software\\Classes\\DaybookHTML", "", "Daybook web page"], ["HKCU\\Software\\Classes\\DaybookHTML\\DefaultIcon", "", icon],
    ["HKCU\\Software\\Classes\\DaybookHTML\\shell\\open\\command", "", cmd],
    [base, "", "Daybook"], [base + "\\DefaultIcon", "", icon], [base + "\\shell\\open\\command", "", `"${process.execPath}"` + (app.isPackaged ? "" : ` "${app.getAppPath()}"`)],
    [base + "\\Capabilities", "ApplicationName", "Daybook"], [base + "\\Capabilities", "ApplicationIcon", icon],
    [base + "\\Capabilities", "ApplicationDescription", "Daybook — your notes, reminders and a private browser with ad blocking"],
    [base + "\\Capabilities\\URLAssociations", "http", "DaybookURL"], [base + "\\Capabilities\\URLAssociations", "https", "DaybookURL"],
    [base + "\\Capabilities\\FileAssociations", ".html", "DaybookHTML"], [base + "\\Capabilities\\FileAssociations", ".htm", "DaybookHTML"],
    ["HKCU\\Software\\RegisteredApplications", "Daybook", "Software\\Clients\\StartMenuInternet\\Daybook\\Capabilities"],
  ];
  for (const [key, name, val] of sets) await reg(["add", key, ...(name ? ["/v", name] : ["/ve"]), "/t", "REG_SZ", "/d", val, "/f"]);
}
async function browserStatus() {
  const q = await reg(["query", "HKCU\\Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\https\\UserChoice", "/v", "ProgId"]);
  const registered = !!(await reg(["query", "HKCU\\Software\\RegisteredApplications", "/v", "Daybook"]));
  const cur = await reg(["query", "HKCU\\Software\\Classes\\DaybookURL\\shell\\open\\command", "/ve"]);
  return {registered, isDefault: !!(q && /DaybookURL/.test(q)), current: q ? (q.match(/ProgId\s+REG_SZ\s+(\S+)/) || [])[1] || "" : "",
          upToDate: !!(cur && cur.includes(process.execPath))};
}
ipcMain.handle("app:defaultBrowser", async (_e, action) => {
  if (action === "register") { await registerBrowser(); shell.openExternal("ms-settings:defaultapps"); }
  if (action && action.linkProfile) writeState({...loadState(), linkProfile: action.linkProfile});
  const st = await browserStatus();
  if (st.registered && !st.upToDate) await registerBrowser();  // Daybook moved or updated → keep the link handler pointing at it
  return st;
});

// Site permissions (location, camera, mic…) are remembered per profile + site, so each site asks only once.
const PERMS = path.join(app.getPath("userData"), "site-permissions.json");
const askingPerm = new Map();
let permCache = null;
function loadPerms() { if (!permCache) { try { permCache = JSON.parse(fs.readFileSync(PERMS, "utf8").replace(/^\uFEFF/, "")); } catch { permCache = {}; } } return permCache; }
function savePerm(key, ok) { loadPerms()[key] = ok; try { fs.writeFileSync(PERMS, JSON.stringify(permCache, null, 1)); } catch {} }
function permKey(part, site, perm, mediaTypes) { return `${part}|${site}|${perm}${perm === "media" && mediaTypes && mediaTypes.length ? ":" + [...mediaTypes].sort().join("+") : ""}`; }
function forgetSite(part, site) { const all = loadPerms(), pre = part + "|" + (site ? site + "|" : ""); for (const k of Object.keys(all)) if (k.startsWith(pre)) delete all[k]; try { fs.writeFileSync(PERMS, JSON.stringify(all, null, 1)); } catch {} }
function prepareSession(part) {
  if (prepared.has(part)) return session.fromPartition(part);
  prepared.add(part);
  const s = session.fromPartition(part);
  s.setUserAgent(CHROME_UA);                                   // so sites treat it as normal Chrome
  adblockSession(s);
  setupDownloads(s);
  s.webRequest.onBeforeSendHeaders((d, cb) => {
    const h = d.requestHeaders;
    if (privacySignals) { h["DNT"] = "1"; h["Sec-GPC"] = "1"; }  // ask sites not to track or sell your data
    if (isGoogleAuth(d.url) || (d.webContents && isGoogleAuth(d.webContents.getURL()) && /google/.test(d.url))) {
      h["User-Agent"] = FIREFOX_UA;
      for (const k of Object.keys(h)) if (/^sec-ch-ua/i.test(k)) delete h[k];
    }
    cb({requestHeaders: h});
  });
  s.setPermissionRequestHandler(async (wc, perm, cb, details) => {
    if (["fullscreen", "clipboard-sanitized-write", "clipboard-read", "notifications", "pointerLock", "idle-detection", "window-management"].includes(perm)) return cb(true);
    if (["media", "geolocation", "midiSysex", "display-capture"].includes(perm)) {
      let site = ""; try { site = new URL(details.requestingUrl || wc.getURL()).host; } catch (e) {}
      const what = perm === "media" ? ((details.mediaTypes || []).join(" & ") || "camera/microphone") : perm === "geolocation" ? "location" : perm;
      const key = permKey(part, site, perm, details.mediaTypes);
      const saved = loadPerms()[key];
      if (saved !== undefined) return cb(saved);                // asked before → never ask again
      if (askingPerm.has(key)) return cb(await askingPerm.get(key));  // a page asking several times at once → one prompt
      const parent = BrowserWindow.fromWebContents(wc) || [...panes.values()].find(p => p.view.webContents === wc)?.owner || win;
      const ask = dialog.showMessageBox(parent, {type: "question", buttons: ["Allow", "Block"], defaultId: 1, cancelId: 1, title: "Daybook",
        message: `${site} wants to use your ${what}`, checkboxLabel: "Remember my choice for this site", checkboxChecked: true})
        .then(r => { const ok = r.response === 0; if (r.checkboxChecked) savePerm(key, ok); return ok; });
      askingPerm.set(key, ask);
      try { return cb(await ask); } finally { askingPerm.delete(key); }
    }
    cb(false);
  });
  // sites that check before asking (Google search does) see the remembered answer and don't ask again
  s.setPermissionCheckHandler((wc, perm, origin, details) => {
    if (["fullscreen", "clipboard-sanitized-write", "clipboard-read", "notifications", "pointerLock", "idle-detection", "window-management"].includes(perm)) return true;
    let site = ""; try { site = new URL(origin || (details && details.requestingUrl) || "").host; } catch (e) {}
    const saved = loadPerms()[permKey(part, site, perm === "media" ? "media" : perm, details && details.mediaType ? [details.mediaType] : null)];
    return saved === true;
  });
  return s;
}
function paneInfo(id, p) {
  const wc = p.view.webContents;
  return {id, profile: p.profile, title: wc.getTitle() || "New tab", url: wc.getURL(), loading: wc.isLoading(), canBack: wc.navigationHistory.canGoBack(), canFwd: wc.navigationHistory.canGoForward(), favicon: p.favicon || "", muted: wc.isAudioMuted(), audible: wc.isCurrentlyAudible(), full: !!p.full};
}
const panesOf = owner => [...panes].filter(([, p]) => p.owner === owner && !p._downloadPlaceholder);
function sendPanes(owner, extra) {
  if (!owner || owner.isDestroyed()) return;
  owner.webContents.send("browser:update", {panes: panesOf(owner).map(([id, p]) => paneInfo(id, p)), ...(extra || {})});
}
function openPane(profile, url, owner) {
  owner = owner || win;
  const part = partitionFor(profile);
  prepareSession(part);
  const view = new WebContentsView({webPreferences: {partition: part, contextIsolation: true, sandbox: true, plugins: true, disableHtmlFullscreenWindowResize: true, preload: path.join(__dirname, "browser-preload.js")}});
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
  wc.on("did-finish-load", () => { p._loadedAnyPage = true; });
  wc.on("found-in-page", (_e, res) => {
    if (!owner.isDestroyed()) {
      owner.webContents.send("browser:findResult", {id, active: res.activeMatchOrdinal, total: res.matches, final: res.finalUpdate});
    }
  });
  wc.on("page-favicon-updated", (_e, icons) => { p.favicon = icons[0] || ""; sendPanes(owner); });
  wc.on("enter-html-full-screen", () => {
    p.full = true;
    p._wasFullScreen = owner.isFullScreen();
    p._wasMaximized = owner.isMaximized();
    if (p._wasMaximized) owner._restoreMaximized = true;
    if (!p._wasFullScreen) owner.setFullScreen(true);
    layoutPanes(owner);
    sendPanes(owner);
  });
  wc.on("leave-html-full-screen", () => {
    p.full = false;
    if (!p._wasFullScreen && !owner.isDestroyed() && owner.isFullScreen()) {
      owner.setFullScreen(false);
    } else if (p._wasMaximized && !owner.isDestroyed() && !owner.isMaximized()) {
      owner.maximize();
    }
    layoutPanes(owner);
    sendPanes(owner);
  });
  wc.on("did-navigate", () => {
    if (p.full) {
      p.full = false;
      if (!p._wasFullScreen && !owner.isDestroyed() && owner.isFullScreen()) {
        owner.setFullScreen(false);
      } else if (p._wasMaximized && !owner.isDestroyed() && !owner.isMaximized()) {
        owner.maximize();
      }
      layoutPanes(owner);
      sendPanes(owner);
    }
  });
  wc.on("before-input-event", (e, i) => { // browser shortcuts inside a pane (matching full Chrome behavior)
    if (i.type !== "keyDown") return;
    const k = i.key.toLowerCase();
    if (i.control && k === "w") { e.preventDefault(); closePane(id); }
    else if (i.control && k === "t") { e.preventDefault(); owner.webContents.send("browser:shortcut", {action: "new", profile}); }
    else if (i.control && k === "d") { e.preventDefault(); owner.webContents.send("browser:shortcut", {action: "save", id}); }
    else if (i.control && k === "l") { e.preventDefault(); owner.webContents.focus(); owner.webContents.send("browser:shortcut", {action: "address", id}); }
    else if (i.control && k === "j") { e.preventDefault(); owner.webContents.send("browser:shortcut", {action: "downloads"}); }
    else if (i.control && k === "f") { e.preventDefault(); owner.webContents.send("browser:shortcut", {action: "find", id}); }
    else if (i.control && k === "p") { e.preventDefault(); wc.print(); }
    else if (i.control && k === "s") {
      e.preventDefault();
      const defaultName = (wc.getTitle() || "page").replace(/[<>:"/\\|?*\x00-\x1F]/g, "_").trim() + ".html";
      dialog.showSaveDialog(owner, {defaultPath: path.join(app.getPath("downloads"), defaultName)}).then(res => {
        if (!res.canceled && res.filePath) wc.savePage(res.filePath, "HTMLComplete");
      });
    }
    else if ((i.control && i.shift && k === "r") || (i.control && k === "f5")) { e.preventDefault(); wc.reloadIgnoringCache(); }
    else if ((i.control && k === "r") || k === "f5") { e.preventDefault(); wc.reload(); }
    else if ((i.control && i.shift && k === "i") || k === "f12") { e.preventDefault(); if (wc.isDevToolsOpened()) wc.closeDevTools(); else wc.openDevTools({mode: "detach"}); }
    else if (i.control && (k === "=" || k === "+" || k === "numpadadd")) { e.preventDefault(); wc.setZoomFactor(Math.min(3, wc.getZoomFactor() + 0.1)); }
    else if (i.control && (k === "-" || k === "_" || k === "numpadsubtract")) { e.preventDefault(); wc.setZoomFactor(Math.max(0.3, wc.getZoomFactor() - 0.1)); }
    else if (i.control && (k === "0" || k === "numpad0")) { e.preventDefault(); wc.setZoomFactor(1); }
    else if (i.alt && k === "arrowleft") { e.preventDefault(); wc.navigationHistory.goBack(); }
    else if (i.alt && k === "arrowright") { e.preventDefault(); wc.navigationHistory.goForward(); }
  });
  wc.on("render-process-gone", () => sendPanes(owner, {toast: "A page crashed — press reload"}));
  wc.on("context-menu", (_e, m) => {
    const t = [], sep = () => t.length && t[t.length - 1].type !== "separator" && t.push({type: "separator"});
    if (m.misspelledWord) {
      m.dictionarySuggestions.slice(0, 5).forEach(s => t.push({label: s, click: () => wc.replaceMisspelling(s)}));
      t.push({label: "Add to dictionary", click: () => wc.session.addWordToSpellCheckerDictionary(m.misspelledWord)}); sep();
    }
    const saveLink = (url, title) => postJson("/api/links", {url, title}).then(j => { sendPanes(owner, {toast: j && j.new === false ? "Already in your Library" : "Saved to your Library (Library → Saved links)"}); if (j && j.link) owner.webContents.send("browser:shortcut", {action: "saved", url: j.link.url, lid: j.link.id}); });
    if (m.linkURL) {
      t.push({label: "Save link to Daybook Library", click: () => saveLink(m.linkURL, (m.linkText || "").trim())},
             {label: "Save link as…", click: () => wc.downloadURL(m.linkURL)},
             {label: "Open link in new tab", click: () => openPane(profile, m.linkURL, owner)},
             {label: "Open link in your normal browser", click: () => shell.openExternal(m.linkURL)},
             {label: "Copy link address", click: () => require("electron").clipboard.writeText(m.linkURL)},
             {label: "Copy link text", click: () => require("electron").clipboard.writeText((m.linkText || "").trim())}); sep();
    }
    if (m.mediaType === "image" && m.srcURL) {
      t.push({label: "Open image in new tab", click: () => openPane(profile, m.srcURL, owner)},
             {label: "Save image as…", click: () => wc.downloadURL(m.srcURL)},
             {label: "Copy image", click: () => wc.copyImageAt(m.x, m.y)},
             {label: "Copy image address", click: () => require("electron").clipboard.writeText(m.srcURL)}); sep();
    }
    if (m.mediaType === "video" || m.mediaType === "audio") {
      if (m.srcURL) {
        t.push({label: "Save media as…", click: () => wc.downloadURL(m.srcURL)},
               {label: "Copy media address", click: () => require("electron").clipboard.writeText(m.srcURL)}); sep();
      }
    }
    if (m.isEditable) {
      t.push({label: "Undo", role: "undo", enabled: m.editFlags.canUndo},
             {label: "Redo", role: "redo", enabled: m.editFlags.canRedo}, {type: "separator"},
             {label: "Cut", role: "cut", enabled: m.editFlags.canCut},
             {label: "Copy", role: "copy", enabled: m.editFlags.canCopy},
             {label: "Paste", role: "paste", enabled: m.editFlags.canPaste},
             {label: "Paste and match style", role: "pasteAndMatchStyle", enabled: m.editFlags.canPaste},
             {label: "Select all", role: "selectAll"}); sep();
    } else if (m.selectionText.trim()) {
      const q = m.selectionText.trim().slice(0, 200);
      t.push({label: "Copy", role: "copy"},
             {label: `Search Google for “${q.length > 30 ? q.slice(0, 30) + "…" : q}”`, click: () => openPane(profile, "https://www.google.com/search?q=" + encodeURIComponent(q), owner)},
             {label: "Save to a new Daybook note", click: () => post("/api/notes", {title: (wc.getTitle() || "Web clip").slice(0, 80), body: q + "\n\nFrom: " + wc.getURL()}).then(() => sendPanes(owner, {toast: "Saved to Notes"}))},
             {label: "Print…", click: () => wc.print()}); sep();
    }
    if (/^https?:/.test(wc.getURL())) t.push({label: "Save this page to Daybook Library", accelerator: "Ctrl+D", click: () => saveLink(wc.getURL(), wc.getTitle())},
      {label: "Send page to Daybook as a note", click: () => pageToNote(id).then(r => sendPanes(owner, {toast: r && r.id ? `Saved “${r.title || "page"}” to Notes` : (r && r.error) || "Couldn't save"}))}, {type: "separator"});
    t.push({label: "Back", enabled: wc.navigationHistory.canGoBack(), click: () => wc.navigationHistory.goBack()},
           {label: "Forward", enabled: wc.navigationHistory.canGoForward(), click: () => wc.navigationHistory.goForward()},
           {label: "Reload", click: () => wc.reload()},
           {label: "Hard reload", click: () => wc.reloadIgnoringCache()}, {type: "separator"},
           {label: "Save page as…", click: () => {
             const defaultName = (wc.getTitle() || "page").replace(/[<>:"/\\|?*\x00-\x1F]/g, "_").trim() + ".html";
             dialog.showSaveDialog(owner, {defaultPath: path.join(app.getPath("downloads"), defaultName)}).then(res => {
               if (!res.canceled && res.filePath) wc.savePage(res.filePath, "HTMLComplete");
             });
           }},
           {label: "Print…", click: () => wc.print()},
           {label: "Find in page…", click: () => owner.webContents.send("browser:shortcut", {action: "find", id})}, {type: "separator"},
           {label: "Open page in your normal browser", click: () => shell.openExternal(wc.getURL())},
           {label: "Copy page address", click: () => require("electron").clipboard.writeText(wc.getURL())},
           {label: "Forget this site's permissions (location, camera…)", click: () => { try { forgetSite(partitionFor(profile), new URL(wc.getURL()).host); sendPanes(owner, {toast: "This site will ask again next time"}); } catch {} }},
           {label: "Close tab", click: () => closePane(id)}, {type: "separator"},
           {label: "Inspect element", click: () => wc.inspectElement(m.x, m.y)});
    Menu.buildFromTemplate(t).popup({window: owner});
  });
  wc.loadURL(url || "https://www.google.com");
  sendPanes(owner, {focus: id});
  return id;
}
// ---- Send tab to Daybook: the page's readable text (an AI chat's conversation, an article…) as a new note ----
const PAGE_TEXT_JS = `(() => {
  const pick = sel => { for (const s of sel) { const el = document.querySelector(s); if (el && el.innerText && el.innerText.trim().length > 200) return el; } return null; };
  // chat apps put the conversation in <main>; articles in <article>; otherwise the whole page
  const el = pick(["main [data-testid*=conversation]", "main", "article", "[role=main]"]) || document.body;
  const text = (el.innerText || "").replace(/\\n{3,}/g, "\\n\\n").trim();
  return {title: document.title || location.hostname, url: location.href, text: text.slice(0, 200000)};
})()`;
async function pageToNote(id) {
  const p = panes.get(id); if (!p) return null;
  let d;
  try { d = await p.view.webContents.executeJavaScript(PAGE_TEXT_JS, true); } catch (e) { return {error: "Couldn't read this page"}; }
  if (!d || !d.text) return {error: "This page has no text to save"};
  const when = new Date().toLocaleString([], {dateStyle: "medium", timeStyle: "short"});
  const note = await postJson("/api/notes", {title: d.title.replace(/ [-|–] (Claude|ChatGPT|Gemini|YouTube)$/i, "").slice(0, 100), body: `From: ${d.url}\nSaved: ${when}\n\n${d.text}`});
  return note && note.id ? {id: note.id, title: note.title, chars: d.text.length} : {error: "Daybook's service didn't answer"};
}
ipcMain.handle("browser:toNote", (_e, id) => pageToNote(id));

function closePane(id) {
  const p = panes.get(id); if (!p) return;
  if (p.full && !p._wasFullScreen && !p.owner.isDestroyed() && p.owner.isFullScreen()) {
    p.owner.setFullScreen(false);
    if (p._wasMaximized && !p.owner.isMaximized()) p.owner.maximize();
  }
  if (!p.owner.isDestroyed()) p.owner.contentView.removeChildView(p.view);
  p.view.webContents.close();
  panes.delete(id); sendPanes(p.owner);
  layoutPanes(p.owner);
}
function layoutPanes(owner, l) {
  if (!owner || owner.isDestroyed()) return;
  if (l) owner._layout = l;
  const {visible, rects} = owner._layout || {};
  const mine = panesOf(owner), full = mine.find(([, p]) => p.full);
  for (const [id, p] of mine) {
    const r = rects ? rects[id] : null;
    let show, b = null;
    if (full) {
      show = (full[0] === id);
      if (show) { const [w, h] = owner.getContentSize(); b = {x: 0, y: 0, width: w, height: h}; }
    } else {
      show = !!(visible && r && r.w >= 20 && r.h >= 20);
      if (show) b = {x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.w), height: Math.round(r.h)};
    }
    // only touch the view when something changed — re-showing a page mid-click can swallow the click
    if (b && JSON.stringify(b) !== p._b) { p.view.setBounds(b); p._b = JSON.stringify(b); }
    if (show !== p._shown) {
      // a hidden page must not keep the keyboard: hand it back to Daybook's own page (shortcuts, typing in notes…)
      if (!show && p.view.webContents.isFocused()) owner.webContents.focus();
      p.view.setVisible(show); p._shown = show;
    }
  }
}
ipcMain.handle("browser:open", (e, {profile, url}) => openPane(profile, url, ownerOf(e)));
ipcMain.handle("browser:close", (_e, id) => closePane(id));
ipcMain.handle("browser:list", e => panesOf(ownerOf(e)).map(([id, p]) => paneInfo(id, p)));
ipcMain.on("browser:layout", (e, l) => layoutPanes(ownerOf(e), l));
ipcMain.handle("browser:nav", async (_e, {id, action, url}) => {
  const p = panes.get(id); if (!p) return; const wc = p.view.webContents;
  if (action === "back") wc.navigationHistory.goBack();
  else if (action === "forward") wc.navigationHistory.goForward();
  else if (action === "reload") wc.reload();
  else if (action === "hardreload") wc.reloadIgnoringCache();
  else if (action === "stop") wc.stop();
  else if (action === "mute") wc.setAudioMuted(!wc.isAudioMuted());
  else if (action === "go" && url) wc.loadURL(url);
  else if (action === "focus") wc.focus();
  else if (action === "external") shell.openExternal(wc.getURL());
  else if (action === "zoomin") wc.setZoomFactor(Math.min(3, wc.getZoomFactor() + 0.1));
  else if (action === "zoomout") wc.setZoomFactor(Math.max(0.3, wc.getZoomFactor() - 0.1));
  else if (action === "zoomreset") wc.setZoomFactor(1);
  else if (action === "print") wc.print();
  else if (action === "devtools") { if (wc.isDevToolsOpened()) wc.closeDevTools(); else wc.openDevTools({mode: "detach"}); }
  else if (action === "savepage") {
    const defaultName = (wc.getTitle() || "page").replace(/[<>:"/\\|?*\x00-\x1F]/g, "_").trim() + ".html";
    const res = await dialog.showSaveDialog(p.owner, {defaultPath: path.join(app.getPath("downloads"), defaultName)});
    if (!res.canceled && res.filePath) wc.savePage(res.filePath, "HTMLComplete");
  }
  else if (action === "clear") { session.fromPartition(partitionFor(p.profile)).clearStorageData(); }
  sendPanes(p.owner);
});
ipcMain.handle("browser:downloads:list", () => {
  return [...downloads.values()].map(d => d.record).reverse().slice(0, 50);
});
ipcMain.handle("browser:downloads:open", (_e, id) => {
  const d = downloads.get(id);
  if (d && d.record && d.record.savePath && fs.existsSync(d.record.savePath)) {
    shell.openPath(d.record.savePath);
    return true;
  }
  return false;
});
ipcMain.handle("browser:downloads:show", (_e, id) => {
  const d = downloads.get(id);
  if (d && d.record && d.record.savePath) {
    if (fs.existsSync(d.record.savePath)) {
      shell.showItemInFolder(d.record.savePath);
    } else {
      shell.openPath(path.dirname(d.record.savePath));
    }
    return true;
  }
  return false;
});
ipcMain.handle("browser:downloads:cancel", (_e, id) => {
  const d = downloads.get(id);
  if (d && d.item && d.record.state === "progressing") {
    d.item.cancel();
    return true;
  }
  return false;
});
ipcMain.handle("browser:downloads:clear", () => {
  for (const [id, d] of downloads) {
    if (d.record.state !== "progressing") downloads.delete(id);
  }
  broadcastDownloads();
  return true;
});
ipcMain.handle("browser:downloads:openFolder", () => {
  shell.openPath(app.getPath("downloads"));
  return true;
});
ipcMain.handle("browser:find", (_e, {id, text, forward = true, findNext = false, matchCase = false}) => {
  const p = panes.get(id); if (!p) return null;
  if (!text) { p.view.webContents.stopFindInPage("clearSelection"); return null; }
  return p.view.webContents.findInPage(text, {forward, findNext, matchCase});
});
ipcMain.handle("browser:stopFind", (_e, {id, action = "clearSelection"}) => {
  const p = panes.get(id); if (!p) return;
  p.view.webContents.stopFindInPage(action);
});
ipcMain.handle("app:settings", (_e, s) => {
  const st = {...loadState(), ...s}; writeState(st);
  if ("startAtLogin" in s) app.setLoginItemSettings({openAtLogin: !!s.startAtLogin, args: ["--hidden"]});
  return st;
});
ipcMain.handle("app:info", e => ({version: app.getVersion(), packaged: app.isPackaged, ...loadState(), startAtLogin: app.getLoginItemSettings().openAtLogin,
  main: ownerOf(e) === win, windows: wins.size, hwnd: hwndOf(ownerOf(e))}));
ipcMain.handle("app:reload", () => {
  for (const w of wins) {
    if (!w.isDestroyed()) w.webContents.reload();
  }
  return true;
});
ipcMain.handle("app:relaunch", () => {
  app.relaunch();
  app.exit(0);
});
ipcMain.handle("clipboard:readText", () => require("electron").clipboard.readText());
ipcMain.handle("clipboard:writeText", (_e, text) => { require("electron").clipboard.writeText(String(text || "")); return true; });
const EDIT_ACTIONS = new Set(["cut", "copy", "paste", "selectAll", "undo", "redo", "pasteAndMatchStyle"]);
ipcMain.on("app:edit", (e, action, arg) => {
  if (EDIT_ACTIONS.has(action)) e.sender[action]();
  else if (action === "replaceMisspelling" && typeof arg === "string") e.sender.replaceMisspelling(arg);
  else if (action === "addToDictionary" && typeof arg === "string") e.sender.session.addWordToSpellCheckerDictionary(arg);
});
// a native menu, for when Daybook's own (HTML) menu would end up hidden under a web page
ipcMain.handle("app:menu", (e, items, x, y) => new Promise(res => {
  let picked = null;
  const build = list => list.map(it => it === "-" ? {type: "separator"} : it.h ? {label: it.h, enabled: false}
    : {label: it.t + (it.k ? "\t" + it.k : ""), enabled: !it.off, ...(it.sub ? {submenu: build(it.sub)} : {click: () => { picked = it.id; }})});
  const m = Menu.buildFromTemplate(build(items || []));
  m.popup({window: BrowserWindow.fromWebContents(e.sender), x: Math.round(x), y: Math.round(y), callback: () => setTimeout(() => res(picked), 0)});
}));
let dragIcon = null;
ipcMain.on("files:drag", (e, paths) => {
  const files = (Array.isArray(paths) ? paths : [paths]).filter(f => typeof f === "string" && fs.existsSync(f));
  if (!files.length) return;
  if (!dragIcon) { dragIcon = nativeImage.createFromPath(ICON); if (!dragIcon.isEmpty()) dragIcon = dragIcon.resize({width: 32, height: 32}); }
  e.sender.startDrag({file: files[0], files, icon: dragIcon});
});
ipcMain.handle("app:newWindow", (e, view) => { createWindow(view || "today", {extra: true, from: ownerOf(e)}); return true; });

// ---------------- start ----------------
app.on("web-contents-created", (_e, wc) => {
  if (wc.session) setupDownloads(wc.session);
  if (wc.getType() === "webview" || !wc.session || wc.session === session.defaultSession) return;
  wc.on("did-start-navigation", d => { if (!d.isMainFrame) return; const ua = isGoogleAuth(d.url) ? FIREFOX_UA : CHROME_UA; if (wc.getUserAgent() !== ua) wc.setUserAgent(ua); });
  wc.on("did-create-window", w => {
    if (w.webContents && w.webContents.session) setupDownloads(w.webContents.session);
    w.webContents.setUserAgent(isGoogleAuth(w.webContents.getURL()) ? FIREFOX_UA : CHROME_UA);
  });
});
// Watchdog: if Daybook's background service stops answering (crash, killed), start it again and
// bring back any window that was showing the "service didn't start" page.
let watching = false, misses = 0;
setInterval(async () => {
  if (watching || !wins.size) return;
  watching = true;
  try {
    if (await ping()) { misses = 0; return; }
    if (++misses < 2) return;  // one slow answer isn't a crash
    misses = 0;
    if (await ensureBackend()) for (const w of wins) if (!w.isDestroyed() && w.webContents.getURL().startsWith("data:")) w.loadURL(URL_BASE + "/#today");
  } finally { watching = false; }
}, 20000);


// ---------------- Terminal (Chat → Terminal): real shells, Claude / Gemini / local AI CLIs, Emacs, Orca ----------------
// Runs here in the app (not on a web address), so only Daybook's own window can use it.
const TOOLS_DIR = fs.existsSync("D:\\") ? "D:\\Applications" : path.join(process.env.LOCALAPPDATA || app.getPath("userData"), "Daybook-tools");
const terms = new Map();                               // id → session {pty, owner, name, profile, cwd, log…}
const TERM_LOG = 400000;                               // characters of recent output kept per session (for reattach)
let termSeq = 1;
function whichExe(name) {
  const dirs = (process.env.PATH || "").split(";").filter(Boolean).concat([path.join(TOOLS_DIR, "gemini-cli"), path.join(require("os").homedir(), ".local", "bin")]);
  for (const d of dirs) for (const ext of ["", ".exe", ".cmd", ".bat"]) { const f = path.join(d, name + ext); try { if (fs.statSync(f).isFile()) return f; } catch {} }
  return null;
}
function termProfiles() {
  const first = (...c) => c.find(f => f && fs.existsSync(f)) || null;
  const pwsh = whichExe("pwsh"), ps = pwsh || "powershell.exe";
  const emacs = whichExe("emacs") || first("D:\\Applications\\Emacs\\bin\\emacs.exe", "C:\\Program Files\\Emacs\\bin\\emacs.exe");
  const emacsHome = first("D:\\Applications\\EmacsHome");      // isolated HOME with the Doom config (Launch-Emacs.bat sets the same)
  const gitBash = first("C:\\Program Files\\Git\\bin\\bash.exe", "D:\\Applications\\Git\\bin\\bash.exe");
  const orca = whichExe("orca") || first("D:\\Applications\\Orca\\resources\\bin\\orca.exe", "D:\\Applications\\Orca\\resources\\bin\\orca");
  const claude = whichExe("claude"), gemini = whichExe("gemini"), ollama = whichExe("ollama") || first("D:\\Applications\\Ollama\\ollama.exe");
  return [
    {id: "pwsh", name: "PowerShell", group: "Shells", ok: true},
    {id: "cmd", name: "Command Prompt", group: "Shells", ok: true},
    {id: "bash", name: "Git Bash", group: "Shells", ok: !!gitBash},
    {id: "wsl", name: "WSL (Linux)", group: "Shells", ok: !!whichExe("wsl")},
    {id: "claude", name: "Claude Code", group: "AI", ok: !!claude, hint: "Install Claude Code from claude.ai/download, then sign in once in this terminal."},
    {id: "gemini", name: "Gemini CLI", group: "AI", ok: !!gemini, hint: "Not installed yet — Daybook can install it (Node.js needed), then sign in with Google in this terminal."},
    {id: "ollama", name: "Local AI (Ollama)", group: "AI", ok: !!ollama, hint: "Install Ollama from ollama.com, then pull a model."},
    {id: "emacs", name: emacsHome ? "Emacs (your Doom setup)" : "Emacs", group: "Tools", ok: !!emacs, hint: "Install Emacs (winget install GNU.Emacs)."},
    {id: "orca", name: "Orca", group: "Tools", ok: !!orca},
    {id: "arcade", name: "8-Bit Arcade (Snake, Pong, Galactica)", group: "Tools", ok: true},
  ].map(p => ({...p, _ps: ps, _emacs: emacs, _emacsHome: emacsHome, _bash: gitBash, _orca: orca, _claude: claude, _gemini: gemini, _ollama: ollama}));
}
function termCommand(prof, opts) {
  const ps = prof._ps, q = s => "'" + String(s).replace(/'/g, "''") + "'";
  const inPs = cmd => [ps, ["-NoLogo", "-NoExit", "-Command", cmd]];          // tool runs, you stay in a shell after it ends
  switch (prof.id) {
    case "cmd": return ["cmd.exe", []];
    case "bash": return [prof._bash, ["--login", "-i"]];
    case "wsl": return ["wsl.exe", []];
    case "claude": return inPs(`& ${q(prof._claude)}`);
    case "gemini": return prof._gemini ? inPs(`& ${q(prof._gemini)}`)
      : inPs(`Write-Host 'Installing Gemini CLI into ${TOOLS_DIR}\\gemini-cli (one time)...' -ForegroundColor Cyan; npm install -g --prefix ${q(path.join(TOOLS_DIR, "gemini-cli"))} @google/gemini-cli@${GEMINI_CLI_VERSION}; if ($?) { & ${q(path.join(TOOLS_DIR, "gemini-cli", "gemini.cmd"))} }`);
    case "ollama": return inPs(opts.model ? `& ${q(prof._ollama)} run ${q(opts.model)}` : `& ${q(prof._ollama)} list`);
    case "emacs": return [prof._emacs, ["-nw"]];
    case "orca": return inPs(`$env:PATH = ${q(path.dirname(prof._orca))} + ';' + $env:PATH; & ${q(prof._orca)} status; Write-Host ''; Write-Host 'Orca is ready here - try: orca --help' -ForegroundColor Cyan`);
    case "arcade": {
      const script = path.join(app.isPackaged ? path.join(process.resourcesPath, "backend") : DEV_ROOT, "arcade.py");
      return inPs(`python -u ${q(script)}`);
    }
    default: return opts.run ? inPs(opts.run) : [ps, ["-NoLogo"]];
  }
}
const GEMINI_CLI_VERSION = "0.62.0";   // pinned: a release at least two weeks old
ipcMain.handle("term:profiles", () => termProfiles().map(({id, name, group, ok, hint}) => ({id, name, group, ok, hint})));
ipcMain.handle("term:create", (e, opts = {}) => {
  let pty;
  try { pty = require("@lydell/node-pty"); }
  catch (err) { console.error("terminal", err); return {error: "The terminal component is missing from this install — reinstall Daybook. (" + err.message + ")"}; }
  const prof = termProfiles().find(p => p.id === (opts.profile || "pwsh")) || termProfiles()[0];
  if (!prof.ok && prof.id !== "gemini") return {error: prof.hint || `${prof.name} isn't installed`};
  const [cmd, args] = termCommand(prof, opts);
  const env = {...process.env, TERM: "xterm-256color", COLORTERM: "truecolor", DAYBOOK_TERMINAL: "1",
    PATH: [path.join(TOOLS_DIR, "gemini-cli"), process.env.PATH].join(";")};
  if (prof.id === "emacs" && prof._emacsHome) { env.HOME = prof._emacsHome; env.PATH = path.dirname(prof._emacs) + ";" + env.PATH; }
  let cwd = opts.cwd && fs.existsSync(opts.cwd) ? opts.cwd : require("os").homedir();
  let p;
  try { p = pty.spawn(cmd, args, {name: "xterm-256color", cols: Math.max(20, opts.cols | 0 || 100), rows: Math.max(5, opts.rows | 0 || 30), cwd, env, useConpty: true}); }
  catch (err) { console.error("terminal", err); return {error: `Couldn't start ${prof.name}: ${err.message}`}; }
  const id = termSeq++, owner = e.sender;
  const name = opts.model || (opts.run ? String(opts.run).slice(0, 40) : prof.name);
  const t = {pty: p, owner, id, name, profile: prof.id, cwd, opts: {model: opts.model, run: opts.run}, started: Date.now(), log: "", exited: false, code: null};
  terms.set(id, t);
  let buf = "", timer = null;   // batch output (~60 fps) so fast programs don't flood the page
  const flush = () => { timer = null; if (buf && !owner.isDestroyed()) owner.send("term:data", {id, data: buf}); buf = ""; };
  p.onData(d => {
    t.log += d; if (t.log.length > TERM_LOG) t.log = t.log.slice(-TERM_LOG * 0.75);   // recent output, replayed on reattach
    buf += d; if (!timer) timer = setTimeout(flush, 16);
  });
  p.onExit(({exitCode}) => {
    if (timer) { clearTimeout(timer); flush(); }
    t.exited = true; t.code = exitCode;
    if (t.closing) terms.delete(id); else if (!owner.isDestroyed()) owner.send("term:exit", {id, code: exitCode});
  });
  owner.once("destroyed", () => { try { p.kill(); } catch {} terms.delete(id); });
  return {id, name, profile: prof.id, cwd};
});
ipcMain.on("term:input", (e, {id, data}) => { const t = terms.get(id); if (t && t.owner === e.sender && typeof data === "string") t.pty.write(data); });
ipcMain.on("term:resize", (e, {id, cols, rows}) => { const t = terms.get(id); if (t && t.owner === e.sender && cols > 1 && rows > 1) try { t.pty.resize(cols | 0, rows | 0); } catch {} });
ipcMain.on("term:kill", (e, id) => {   // close a session for good
  const t = terms.get(id); if (!t || t.owner !== e.sender) return;
  t.closing = true; if (t.exited) terms.delete(id); else try { t.pty.kill(); } catch { terms.delete(id); }
});
// the page reloaded (or the Chat page was rebuilt): list the sessions still running and replay their output
ipcMain.handle("term:list", e => [...terms.values()].filter(t => t.owner === e.sender && !t.closing)
  .map(({id, name, profile, cwd, opts, started, exited, code}) => ({id, name, profile, cwd, opts, started, exited, code})));
ipcMain.handle("term:attach", (e, id) => { const t = terms.get(id); return t && t.owner === e.sender ? {log: t.log} : null; });
// Projects sidebar: git repos in D:\projects (or ~/projects) plus folders the user added
function gitBranch(dir) {
  try { const h = fs.readFileSync(path.join(dir, ".git", "HEAD"), "utf8").trim(); return h.startsWith("ref:") ? h.replace(/^ref:\s*refs\/heads\//, "") : h.slice(0, 7); } catch { return null; }
}
ipcMain.handle("term:projects", () => {
  const out = [], seen = new Set(), add = (dir, mine) => {
    const k = dir.toLowerCase(); if (seen.has(k) || !fs.existsSync(dir)) return; seen.add(k);
    out.push({path: dir, name: path.basename(dir) || dir, branch: gitBranch(dir), mine: !!mine});
  };
  for (const d of loadState().termProjects || []) add(d, true);
  for (const root of ["D:\\projects", path.join(require("os").homedir(), "projects")]) {
    try { for (const f of fs.readdirSync(root, {withFileTypes: true})) if (f.isDirectory() && fs.existsSync(path.join(root, f.name, ".git"))) add(path.join(root, f.name)); } catch {}
  }
  return out;
});
ipcMain.handle("term:addProject", async e => {
  const r = await dialog.showOpenDialog(BrowserWindow.fromWebContents(e.sender), {title: "Add a project folder", properties: ["openDirectory"]});
  if (r.canceled || !r.filePaths[0]) return null;
  const st = loadState(), list = st.termProjects || [];
  if (!list.some(d => d.toLowerCase() === r.filePaths[0].toLowerCase())) writeState({...st, termProjects: [r.filePaths[0], ...list]});
  return r.filePaths[0];
});
ipcMain.handle("term:removeProject", (_e, dir) => { const st = loadState(); writeState({...st, termProjects: (st.termProjects || []).filter(d => d !== dir)}); return true; });
ipcMain.handle("term:models", async () => {     // local models for "Local AI"
  try { const r = await fetch("http://127.0.0.1:11434/api/tags"); return ((await r.json()).models || []).map(m => m.name); } catch { return []; }
});
app.on("will-quit", () => { for (const t of terms.values()) try { t.pty.kill(); } catch {} });

// ---- system-wide hotkeys (work in any app while Daybook runs in the tray) ----
// Ctrl+Alt+S is left out on purpose: on this PC another tool (a screenshot script) already uses it.
const HOTKEYS = {"Control+Alt+R": "add", "Control+Alt+N": "note", "Control+Alt+A": "agenda", "Control+Alt+C": "view:chat", "Control+Alt+D": "view:today",
  "Control+Alt+W": "post:/api/stickies/peek", "Control+Alt+P": "post:/api/annotate"};
const HOTKEY_STATE = {};
function helperSpawn(mode) {  // the small quick-add / quick-note / agenda windows
  const packed = path.join(process.resourcesPath || "", "backend", "daybook-backend.exe");
  const [exe, args] = app.isPackaged && fs.existsSync(packed) ? [packed, [mode]] : [path.join(DEV_ROOT, "venv", "Scripts", "pythonw.exe"), [path.join(DEV_ROOT, "quickadd.pyw"), mode]];
  try { spawn(exe, args, {detached: true, stdio: "ignore", windowsHide: false}).unref(); } catch (e) { console.error("hotkey", mode, e); }
}
function registerHotkeys() {
  const extra = loadState().hotkeySticky;  // optional: a key for "new sticky note" chosen in Settings
  const map = {...HOTKEYS, ...(extra ? {[extra]: "post:/api/stickies"} : {})};
  for (const [acc, act] of Object.entries(map)) {
    const ok = globalShortcut.register(acc, () => {
      if (act.startsWith("view:")) showWindow(act.slice(5));
      else if (act.startsWith("post:")) post(act.slice(5), act.endsWith("/api/stickies") ? {color: "lemon"} : {});
      else helperSpawn(act);
    });
    HOTKEY_STATE[acc] = ok ? "on" : "taken";  // "taken" = another app already owns this key
  }
}
ipcMain.handle("app:hotkeys", () => HOTKEY_STATE);
app.on("will-quit", () => globalShortcut.unregisterAll());

app.whenReady().then(async () => {
  if (!PRIMARY) return;
  adblockInit();
  registerHotkeys();
  const appMenu = Menu.buildFromTemplate([
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "pasteAndMatchStyle" },
        { role: "delete" },
        { type: "separator" },
        { role: "selectAll" }
      ]
    }
  ]);
  Menu.setApplicationMenu(appMenu);
  // mic + screen capture + clipboard read/write for voice/video notes and editing
  session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(["media", "display-capture", "clipboard-sanitized-write", "clipboard-read", "notifications", "fullscreen"].includes(perm)));
  setupDownloads(session.defaultSession);
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
    writeState({...st, firstRunDone: true});
  }
  const startUrl = urlArg(process.argv);
  await createWindow(startUrl ? "browser" : viewArg(process.argv));
  if (startUrl) openFromOutside(startUrl);
});
let released = false;
app.on("before-quit", e => {
  if (!PRIMARY) return;
  quitting = true; saveState();
  if (released) return;
  e.preventDefault();  // hand embedded Chrome windows back to the desktop before the windows go away
  post("/api/dock/embed/release", {all: 1}).then(() => { released = true; app.quit(); });
});
app.on("window-all-closed", e => e.preventDefault()); // stay in the tray
