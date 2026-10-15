// Exposes a small, safe API to the Daybook page (window.desktop). Only Daybook's own pages get this.
const {contextBridge, ipcRenderer, webUtils} = require("electron");

contextBridge.exposeInMainWorld("desktop", {
  isDesktop: true,
  reload: () => ipcRenderer.invoke("app:reload"),
  relaunch: () => ipcRenderer.invoke("app:relaunch"),
  info: () => ipcRenderer.invoke("app:info"),
  settings: s => ipcRenderer.invoke("app:settings", s),
  newWindow: view => ipcRenderer.invoke("app:newWindow", view),
  edit: (action, arg) => ipcRenderer.send("app:edit", action, arg),
  clipboard: {
    readText: () => ipcRenderer.invoke("clipboard:readText"),
    writeText: text => ipcRenderer.invoke("clipboard:writeText", text),
  },
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
    list: () => ipcRenderer.invoke("term:list"),                         // sessions still running (after a reload)
    attach: id => ipcRenderer.invoke("term:attach", id),
    projects: () => ipcRenderer.invoke("term:projects"),
    addProject: () => ipcRenderer.invoke("term:addProject"),
    removeProject: dir => ipcRenderer.invoke("term:removeProject", dir),
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
    onRelayout: fn => ipcRenderer.on("browser:relayout", () => fn()),     // the Daybook window moved / came back
    adblock: on => ipcRenderer.invoke("browser:adblock", on),        // no argument = just read the state
    toNote: id => ipcRenderer.invoke("browser:toNote", id),            // page text → new note → {id,title} or {error}
    downloads: {
      list: () => ipcRenderer.invoke("browser:downloads:list"),
      open: id => ipcRenderer.invoke("browser:downloads:open", id),
      show: id => ipcRenderer.invoke("browser:downloads:show", id),
      cancel: id => ipcRenderer.invoke("browser:downloads:cancel", id),
      clear: () => ipcRenderer.invoke("browser:downloads:clear"),
      openFolder: () => ipcRenderer.invoke("browser:downloads:openFolder"),
      onUpdate: fn => ipcRenderer.on("browser:downloads", (_e, d) => fn(d)),
    },
    find: (id, text, opts) => ipcRenderer.invoke("browser:find", {id, text, ...(opts || {})}),
    stopFind: (id, action) => ipcRenderer.invoke("browser:stopFind", {id, action}),
    onFindResult: fn => ipcRenderer.on("browser:findResult", (_e, d) => fn(d)),
  },
});
