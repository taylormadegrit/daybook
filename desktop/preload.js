// Exposes a small, safe API to the Daybook page (window.desktop). Only Daybook's own pages get this.
const {contextBridge, ipcRenderer} = require("electron");

contextBridge.exposeInMainWorld("desktop", {
  isDesktop: true,
  info: () => ipcRenderer.invoke("app:info"),
  settings: s => ipcRenderer.invoke("app:settings", s),
  browser: {
    open: (profile, url) => ipcRenderer.invoke("browser:open", {profile, url}),
    close: id => ipcRenderer.invoke("browser:close", id),
    list: () => ipcRenderer.invoke("browser:list"),
    nav: (id, action, url) => ipcRenderer.invoke("browser:nav", {id, action, url}),
    layout: l => ipcRenderer.send("browser:layout", l),
    onUpdate: fn => ipcRenderer.on("browser:update", (_e, d) => fn(d)),
    onShortcut: fn => ipcRenderer.on("browser:shortcut", (_e, d) => fn(d)),
  },
});
