// Exposes a small, safe API to the Daybook page (window.desktop). Only Daybook's own pages get this.
const {contextBridge, ipcRenderer, webUtils} = require("electron");

contextBridge.exposeInMainWorld("desktop", {
  isDesktop: true,
  info: () => ipcRenderer.invoke("app:info"),
  settings: s => ipcRenderer.invoke("app:settings", s),
  newWindow: view => ipcRenderer.invoke("app:newWindow", view),
  edit: (action, arg) => ipcRenderer.send("app:edit", action, arg),
  menu: (items, x, y) => ipcRenderer.invoke("app:menu", items, x, y),           // native menu → id of the picked item
  onContextParams: fn => ipcRenderer.on("ctx:params", (_e, d) => fn(d)),
  onAppKey: fn => ipcRenderer.on("app:key", (_e, d) => fn(d)),            // shortcuts pressed inside a web page
  hotkeys: () => ipcRenderer.invoke("app:hotkeys"),
  term: {                                                                // Chat → Terminal
    profiles: () => ipcRenderer.invoke("term:profiles"),
    models: () => ipcRenderer.invoke("term:models"),
    create: opts => ipcRenderer.invoke("term:create", opts),
    input: (id, data) => ipcRenderer.send("term:input", {id, data}),
    resize: (id, cols, rows) => ipcRenderer.send("term:resize", {id, cols, rows}),
    kill: id => ipcRenderer.send("term:kill", id),
    onData: fn => ipcRenderer.on("term:data", (_e, d) => fn(d)),
    onExit: fn => ipcRenderer.on("term:exit", (_e, d) => fn(d)),
  },
  defaultBrowser: action => ipcRenderer.invoke("app:defaultBrowser", action),  // status / "register" / {linkProfile}
  privacy: s => ipcRenderer.invoke("browser:privacy", s),                 // cut / copy / paste / selectAll / undo / redo
  files: {
    startDrag: paths => ipcRenderer.send("files:drag", paths),           // drag real files out to Explorer, Discord, upload boxes…
    pathFor: file => { try { return webUtils.getPathForFile(file); } catch (e) { return ""; } },  // dropped File → its path on disk
  },
  browser: {
    open: (profile, url) => ipcRenderer.invoke("browser:open", {profile, url}),
    close: id => ipcRenderer.invoke("browser:close", id),
    list: () => ipcRenderer.invoke("browser:list"),
    nav: (id, action, url) => ipcRenderer.invoke("browser:nav", {id, action, url}),
    layout: l => ipcRenderer.send("browser:layout", l),
    onUpdate: fn => ipcRenderer.on("browser:update", (_e, d) => fn(d)),
    onShortcut: fn => ipcRenderer.on("browser:shortcut", (_e, d) => fn(d)),
    adblock: on => ipcRenderer.invoke("browser:adblock", on),        // no argument = just read the state
    toNote: id => ipcRenderer.invoke("browser:toNote", id),            // page text → new note → {id,title} or {error}
  },
});
