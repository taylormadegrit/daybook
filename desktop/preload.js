// Exposes a small, safe API to the Daybook page (window.desktop). Only Daybook's own pages get this.
const {contextBridge, ipcRenderer, webUtils} = require("electron");

contextBridge.exposeInMainWorld("desktop", {
  isDesktop: true,
  info: () => ipcRenderer.invoke("app:info"),
  settings: s => ipcRenderer.invoke("app:settings", s),
  newWindow: view => ipcRenderer.invoke("app:newWindow", view),
  edit: action => ipcRenderer.send("app:edit", action),                 // cut / copy / paste / selectAll / undo / redo
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
  },
});
