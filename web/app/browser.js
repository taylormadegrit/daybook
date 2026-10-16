// ================= BROWSER WORKSPACE: real browser windows docked inside Daybook =================
const BW = {data: null, poll: 0, ro: null, lastSent: ""};
async function renderBrowser() {
  if (window.desktop) return renderBrowserDesktop();
  if (!LP.data) LP.data = await api("/api/launchpad");
  BW.data = await api("/api/dock");
  const profiles = LP.data.browsers.flatMap(b => b.profiles.map(p => ({b, p})));
  $("#v-browser").innerHTML = `<div class="bw-bar">
      <div class="bw-tabs" id="bw-tabs"></div>
      <div class="sp"></div>
      <div style="position:relative"><button class="btn sm pri" onclick="bwMenu(event,'profiles')">${ic("plus")}Open profile</button>
        <div class="menu" id="bw-profiles" style="right:0;top:36px;max-height:60vh;overflow:auto">${profiles.map(({b, p}) => `<div onclick="bwOpen('${b.id}',${JSON.stringify(p.id).replace(/"/g, "&quot;")})">
          ${p.picture ? `<img class="bw-av" src="/browser-avatar/${b.id}/${encodeURIComponent(p.id)}">` : `<span class="bw-av" style="background:${p.color}">${esc(p.name[0])}</span>`}${esc(p.name)}<span class="kbd">${esc(b.name.replace("Google ", ""))}</span></div>`).join("")}</div></div>
      <div style="position:relative"><button class="btn sm" onclick="bwMenu(event,'windows')" title="Bring a browser window that's already open into Daybook">${ic("down")}Dock a window</button>
        <div class="menu" id="bw-windows" style="right:0;top:36px;max-height:60vh;overflow:auto;min-width:320px"></div></div>
      <div class="seg sm" id="bw-layout">${[["auto", "Auto"], ["cols", "Columns"], ["rows", "Rows"], ["grid", "Grid"], ["focus", "Focus"]].map(([k, l]) => `<button data-l="${k}" onclick="bwLayout('${k}')">${l}</button>`).join("")}</div>
      <button class="btn sm ghost" onclick="api('/api/dock/undock',{method:'POST',body:{all:1}}).then(bwRefresh)" title="Give every window back to the desktop">Undock all</button></div>
    <div class="bw-stage" id="bw-stage"><div class="empty" id="bw-empty"><b>Browse without leaving Daybook</b>Open a profile and its real browser window docks right here — your tabs, extensions and logins included. Open a few: they split the space evenly.
      <div class="row" style="justify-content:center;margin-top:14px;gap:8px">${profiles.slice(0, 6).map(({b, p}) => `<button class="chipb" onclick="bwOpen('${b.id}',${JSON.stringify(p.id).replace(/"/g, "&quot;")})">${esc(p.name)}</button>`).join("")}</div></div></div>`;
  paintIcons($("#v-browser"));
  bwPaint();
  if (!BW.ro) { BW.ro = new ResizeObserver(() => dockSync()); }
  BW.ro.observe($("#bw-stage"));
  clearInterval(BW.poll); BW.poll = setInterval(() => S.view === "browser" ? bwRefresh() : clearInterval(BW.poll), 2500);
  dockSync(true);
}
function bwPaint() {
  const d = BW.data; if (!$("#bw-tabs")) return;
  $("#bw-tabs").innerHTML = d.docked.map(w => `<div class="bw-tab ${w.focus ? "on" : ""}" title="${esc(w.title)}" onclick="bwFocus(${w.hwnd})"><span>${esc(w.label || w.exe.replace(".exe", ""))}</span><small>${esc(w.title.replace(/ - (Google Chrome|Microsoft​? Edge|Brave|Comet).*$/, ""))}</small>
      <button title="Give back to the desktop" onclick="event.stopPropagation();api('/api/dock/undock',{method:'POST',body:{hwnd:${w.hwnd}}}).then(bwRefresh)">${ic("ext")}</button>
      <button title="Close window" onclick="event.stopPropagation();api('/api/dock/close',{method:'POST',body:{hwnd:${w.hwnd}}}).then(()=>setTimeout(bwRefresh,600))">${ic("x")}</button></div>`).join("");
  $("#bw-empty").style.display = d.docked.length ? "none" : "";
  $$("#bw-layout button").forEach(b => b.classList.toggle("on", b.dataset.l === d.layout));
  paintIcons($("#bw-tabs"));
}
async function bwRefresh() { BW.data = await api("/api/dock"); bwPaint(); }
function bwMenu(e, which) {
  e.stopPropagation(); const m = $("#bw-" + which), on = !m.classList.contains("on");
  $$(".menu").forEach(x => x.classList.remove("on"));
  if (which === "windows") m.innerHTML = BW.data.available.map(w => `<div onclick="bwAttach(${w.hwnd})">${ic("ext")}<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(w.title)}</span></div>`).join("") || `<div class="muted small" style="cursor:default">No other browser windows open</div>`;
  m.classList.toggle("on", on); paintIcons(m); dockSync();
}
async function bwOpen(b, p, url) {
  $$(".menu").forEach(x => x.classList.remove("on"));
  if (S.view !== "browser") go("browser");
  toast("Opening…");
  try { await api("/api/dock/open", {method: "POST", body: {browser: b, profile: p, url: url || ""}}); } catch (e) { toast(e.message); }
  bwRefresh(); dockSync(true);
}
async function bwAttach(h) { $$(".menu").forEach(x => x.classList.remove("on")); await api("/api/dock/attach", {method: "POST", body: {hwnd: h}}); bwRefresh(); dockSync(true); }
async function bwLayout(l) { await api("/api/dock/layout", {method: "POST", body: {layout: l}}); BW.data.layout = l; bwPaint(); }
async function bwFocus(h) { await api("/api/dock/focus", {method: "POST", body: {hwnd: h}}); bwRefresh(); }
// Tell the dock where the stage is. Docked windows are real windows on top of Daybook, so they hide
// whenever a menu, dialog or search is open, or you're on another page.
function dockSync(force) {
  if (window.desktop) {
    if (S.view === "apps" && typeof awSync === "function") return awSync(force);
    return bdSync(force);
  }
  const st = $("#bw-stage");
  const overlay = $("#scrim").classList.contains("on") || $$(".menu.on").length > 0 || (H && H.editing);
  const visible = S.view === "browser" && st && !overlay && document.visibilityState === "visible";
  const r = st ? st.getBoundingClientRect() : {x: 0, y: 0, width: 0, height: 0};
  const body = visible ? {visible: true, x: r.x, y: r.y, w: r.width, h: r.height, dpr: devicePixelRatio} : {visible: false};
  const key = JSON.stringify(body); if (!force && key === BW.lastSent) return; BW.lastSent = key;
  fetch("/api/dock/stage", {method: "POST", headers: {"Content-Type": "application/json"}, body: key}).catch(() => {});
}
function dockInit() {
  addEventListener("resize", () => dockSync());
  document.addEventListener("visibilitychange", () => dockSync());
  let queued = 0;
  const later = () => { if (!queued) queued = requestAnimationFrame(() => { queued = 0; dockSync(); }); };
  new MutationObserver(ms => { if (ms.some(m => m.target.matches && m.target.matches(".menu,#scrim,.dict"))) later(); })
    .observe(document.body, {attributes: true, attributeFilter: ["class"], subtree: true});
  document.addEventListener("click", () => setTimeout(dockSync, 0), true);
  document.addEventListener("keyup", e => { if (e.key === "Escape") later(); }, true);
}

// ================= SIDEBAR: order, position, visibility =================
const NAV_POS = [["left", "Left"], ["right", "Right"], ["top", "Top"], ["bottom", "Bottom"]];
function navOrder() { const l = layoutCfg(), all = $$(".nav .navi").map(n => n.dataset.v).filter(v => v !== "settings" && v !== "help"); const o = (l.navOrder || []).filter(v => all.includes(v)); return [...o, ...all.filter(v => !o.includes(v))]; }
function applyNavLayout() {
  const l = layoutCfg(), app = $(".app"), sep = $(".nav .navsep");
  navOrder().forEach(v => { const n = $(`.nav .navi[data-v="${v}"]`); if (n) sep.before(n); });
  ["left", "right", "top", "bottom"].forEach(p => app.classList.toggle("nav-" + p, (l.navPos || "left") === p));
  $$(".nav .navi").forEach(n => { if (!n.title) n.title = n.textContent.replace(/Alt .+$|\?$/, "").trim(); });  // tooltips for icon-only bars
  // keep Alt+number shortcuts matching what you see
  let k = 1; navOrder().filter(v => l.nav.includes(v)).forEach(v => { const kk = $(`.nav .navi[data-v="${v}"] .k`); if (kk && !["launchpad", "studio"].includes(v)) kk.textContent = k <= 9 ? "Alt " + k++ : ""; });
  NAV_KEYS = navOrder().filter(v => l.nav.includes(v) && !["launchpad", "studio"].includes(v)).slice(0, 9);
}
let NAV_KEYS = null;
function sidebarModal() {
  const l = layoutCfg(), names = Object.fromEntries(NAV_PAGES);
  modal(`<h2>${ic("sidebar", "i")}Customize the sidebar<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="grouph" style="margin-top:0">Where it sits</div>
    <div class="pos-pick">${NAV_POS.map(([k, n]) => `<button class="${(l.navPos || "left") === k ? "on" : ""}" onclick="saveLayoutCfg({navPos:'${k}'}).then(()=>{applyNavLayout();sidebarModal()})"><span class="pp ${k}"><i></i><b></b></span>${n}</button>`).join("")}</div>
    <div class="grouph">Order & which pages show — drag to reorder</div>
    <div class="navlist" id="navlist">${navOrder().map(v => `<div class="nl" draggable="true" data-v="${v}"><span class="grip">⋮⋮</span>${ic("grid")}<b>${esc(names[v] || v)}</b>
      <button class="iconbtn" title="Move up" onclick="navMove('${v}',-1)">${ic("up")}</button>
      <button class="sw ${l.nav.includes(v) ? "on" : ""}" onclick="layNav('${v}').then(sidebarModal)"></button></div>`).join("")}</div>
    <div class="row" style="margin-top:14px"><button class="btn ghost" onclick="saveLayoutCfg({navOrder:[],navPos:'left'}).then(()=>{applyNavLayout();sidebarModal()})">Reset</button><div class="sp"></div><button class="btn pri" onclick="closeModal()">Done</button></div>`);
  $$("#navlist .nl").forEach(n => { const v = n.dataset.v, src = $(`.nav .navi[data-v="${v}"] svg`); if (src) n.querySelector("svg").outerHTML = src.outerHTML; });
  let from = null;
  $$("#navlist .nl").forEach(el => {
    el.addEventListener("dragstart", () => { from = el.dataset.v; el.classList.add("drag"); });
    el.addEventListener("dragend", () => el.classList.remove("drag"));
    el.addEventListener("dragover", e => { e.preventDefault(); el.classList.add("over"); });
    el.addEventListener("dragleave", () => el.classList.remove("over"));
    el.addEventListener("drop", async e => { e.preventDefault(); const o = navOrder(), to = el.dataset.v; if (!from || from === to) return;
      o.splice(o.indexOf(from), 1); o.splice(o.indexOf(to), 0, from); await saveLayoutCfg({navOrder: o}); applyNavLayout(); sidebarModal(); });
  });
}
async function navMove(v, d) { const o = navOrder(), i = o.indexOf(v), j = i + d; if (j < 0) return; [o[i], o[j]] = [o[j], o[i]]; await saveLayoutCfg({navOrder: o}); applyNavLayout(); sidebarModal(); }
