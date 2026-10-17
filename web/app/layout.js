// ================= LAYOUT: Simple · Balanced · Power, Display Orientation & Productivity =================
const NAV_PAGES = [["today", "Today"], ["launchpad", "Launchpad"], ["games", "Games"], ["workflows", "Workflows"], ["browser", "Browser"], ["calendar", "Calendar"], ["reminders", "Reminders"], ["notes", "Notes"], ["memos", "Voice & video"], ["studio", "AI Studio"], ["research", "Library"],
  ["clock", "Clock"], ["desktop", "Desktop"], ["chat", "Chat"], ["models", "Models"]];
const PRESETS_LAYOUT = {
  simple: {name: "Simple", desc: "Just the essentials — big, calm, no shortcuts to learn", nav: ["today", "launchpad", "workflows", "games", "browser", "notes", "memos", "studio", "clock"], density: "comfy", hints: false, quick: false, status: false,
    widgets: ["nownext", "schedule", "timers", "log"]},
  balanced: {name: "Balanced", desc: "Everything, with room to breathe (default)", nav: NAV_PAGES.map(p => p[0]), density: "normal", hints: true, quick: true, status: true,
    widgets: ["nownext", "schedule", "workflows", "log", "timers", "stickies", "alarms", "upnext", "ambience"]},
  power: {name: "Power", desc: "Dense, every page and shortcut, more widgets", nav: NAV_PAGES.map(p => p[0]), density: "compact", hints: true, quick: true, status: true,
    widgets: ["nownext", "schedule", "workflows", "launchpad", "timers", "log", "studio", "games", "folders", "stopwatch", "alarms", "world", "memos", "notes", "upnext", "stickies"]},
};
const ORIENT_MODES = [
  ["landscape", "🖥️ Landscape", "Standard side-by-side horizontal columns"],
  ["laptop", "💻 Laptop Compact", "Max vertical space, compact bars & scrollable menus"],
  ["portrait", "📱 Vertical / Portrait", "Single-column top-to-bottom stack for tall or split screens"],
  ["ultrawide", "🌌 Ultrawide 3-Col", "Full-width multi-column command center"],
];
function layoutCfg() {
  let l = {}; try { l = JSON.parse(S.settings.layout || "{}"); } catch (e) {}
  const c = {
    ...PRESETS_LAYOUT.balanced,
    mode: "balanced",
    start: "today",
    orient: localStorage.getItem("daybook-orient") || "landscape",
    splitDir: localStorage.getItem("daybook-split-dir") || "horizontal",
    uiScale: +(localStorage.getItem("daybook-ui-scale") || 100),
    topbarMin: localStorage.getItem("daybook-topbar-min") === "1",
    ...l,
  };
  // pages added in newer versions show up unless you've hidden them yourself
  const known = l.navKnown || NAV_PAGES.map(p => p[0]).filter(v => !["browser", "studio", "research", "games", "workflows"].includes(v));
  c.nav = [...new Set([...c.nav, ...NAV_PAGES.map(p => p[0]).filter(v => !known.includes(v))])];
  return c;
}
function applyLayout() {
  const l = layoutCfg(), b = document.body, d = document.documentElement;
  b.classList.toggle("lay-compact", l.density === "compact" || l.orient === "laptop");
  b.classList.toggle("lay-comfy", l.density === "comfy" && l.orient !== "laptop");
  b.classList.toggle("lay-nohints", !l.hints);
  b.classList.toggle("lay-noquick", !l.quick);
  b.classList.toggle("lay-nostatus", !l.status);
  b.classList.toggle("topbar-min", !!l.topbarMin);
  d.dataset.orient = l.orient || "landscape";
  d.dataset.split = l.splitDir || "horizontal";
  try {
    localStorage.setItem("daybook-orient", d.dataset.orient);
    localStorage.setItem("daybook-split-dir", d.dataset.split);
    localStorage.setItem("daybook-ui-scale", String(l.uiScale || 100));
    localStorage.setItem("daybook-topbar-min", l.topbarMin ? "1" : "0");
  } catch (e) {}
  const scale = Math.max(75, Math.min(125, +(l.uiScale || 100))) / 100;
  const appEl = $(".app");
  if (appEl) appEl.style.zoom = scale === 1 ? "" : String(scale);
  $$(".navi").forEach(n => { const v = n.dataset.v; if (v === "settings" || v === "help") return; n.style.display = l.nav.includes(v) ? "" : "none"; });
  $$(".lay-pick button").forEach(x => x.classList.toggle("on", x.dataset.m === l.mode));
  applyNavLayout();
  injectCardMinButtons();
}
function injectCardMinButtons() {
  $$("#v-settings .card > h3, #v-today .card > h3, #v-desktop .card > h3, #v-models .card > h3").forEach(h3 => {
    if (h3.querySelector(".card-min-btn")) return;
    const btn = document.createElement("button");
    btn.className = "card-min-btn";
    btn.title = "Minimize / expand this section";
    btn.textContent = "—";
    btn.style.marginLeft = h3.querySelector(".btn, .swatches") ? "6px" : "auto";
    btn.onclick = e => {
      e.stopPropagation();
      const card = h3.closest(".card");
      if (!card) return;
      const col = card.classList.toggle("collapsed");
      btn.textContent = col ? "+" : "—";
    };
    h3.appendChild(btn);
  });
}
async function setDisplayOrient(orient) {
  await saveLayoutCfg({orient});
  if (orient === "laptop" && !$(".app").classList.contains("slim")) setSlim(true);
  if (S.view === "settings") renderLayoutSettings();
  if ($("#cz-orient-grid")) customizeModal("display");
  const found = ORIENT_MODES.find(x => x[0] === orient);
  toast(`Display orientation: ${found ? found[1] : orient}`);
}
async function setSplitDir(splitDir) {
  await saveLayoutCfg({splitDir});
  if (S.view === "settings") renderLayoutSettings();
  if ($("#cz-orient-grid")) customizeModal("display");
  toast(splitDir === "vertical" ? "Workspace split: Vertical (Top ⇅ Bottom)" : "Workspace split: Horizontal (Left ⇄ Right)");
}
async function setUiScale(val, quiet) {
  const uiScale = Math.max(80, Math.min(120, Math.round(+val || 100)));
  const lbl = $("#ui-scale-lbl"); if (lbl) lbl.textContent = uiScale + "%";
  const lbl2 = $("#cz-scale-lbl"); if (lbl2) lbl2.textContent = uiScale + "%";
  const appEl = $(".app"); if (appEl) appEl.style.zoom = uiScale === 100 ? "" : String(uiScale / 100);
  localStorage.setItem("daybook-ui-scale", String(uiScale));
  if (!quiet) await saveLayoutCfg({uiScale});
}
async function toggleTopbarMin() {
  const l = layoutCfg();
  await saveLayoutCfg({topbarMin: !l.topbarMin});
  if (S.view === "settings") renderLayoutSettings();
  if ($("#cz-orient-grid")) customizeModal("display");
  toast(!l.topbarMin ? "Top bar minimized for maximum vertical space" : "Top bar expanded");
}
async function saveLayoutCfg(patch) { const l = {...layoutCfg(), ...patch, navKnown: NAV_PAGES.map(p => p[0])}; S.settings = await api("/api/settings", {method: "PATCH", body: {layout: JSON.stringify(l)}}); applyLayout(); return l; }
async function pickLayout(mode, withWidgets = true) {
  const p = PRESETS_LAYOUT[mode]; const {name, desc, widgets, ...rest} = p;
  await saveLayoutCfg({...rest, mode});
  if (withWidgets) await saveHomeCfg({widgets: widgets.filter(id => WIDGETS[id]).map(id => ({id, size: WIDGETS[id].size || "col"}))});
  H.built = ""; toast(`${name} layout ✓ — fine-tune it any time in Settings → Layout`);
  if (S.view === "settings") renderLayoutSettings(); if (S.view === "today") renderToday();
  if (!layoutCfg().nav.includes(S.view) && !["settings", "help"].includes(S.view)) go("today");
}
function renderLayoutSettings() {
  const host = $("#layoutset"); if (!host) return; const l = layoutCfg();
  host.innerHTML = `<div class="lay-cards">${Object.entries(PRESETS_LAYOUT).map(([k, p]) => `<div class="lay-card ${l.mode === k ? "on" : ""}" onclick="pickLayout('${k}', $('#lay-w').checked)">
      <div class="lay-pv ${k}"><i></i><b></b><b></b><b></b>${k === "power" ? "<b></b><b></b>" : ""}</div><b>${p.name}</b><span>${p.desc}</span></div>`).join("")}</div>
    <label class="small muted" style="display:flex;gap:8px;align-items:center;margin:8px 0 14px"><input type="checkbox" id="lay-w" checked> Also set my home widgets for that layout</label>
    <div class="grouph">Display Orientation &amp; Laptop Productivity</div>
    <div class="orient-grid">${ORIENT_MODES.map(([k, n, d]) => `<div class="orient-card ${(l.orient || "landscape") === k ? "on" : ""}" onclick="setDisplayOrient('${k}')"><b>${n}</b><span>${d}</span></div>`).join("")}</div>
    <div class="srow"><div class="d"><b>Workspace split direction</b><span>Arrange multi-pane views side-by-side (Horizontal) or stacked top-to-bottom (Vertical)</span></div>
      <div class="seg">${[["horizontal", "⇄ Horizontal Split"], ["vertical", "⇅ Vertical Stack"]].map(([k, n]) => `<button class="${(l.splitDir || "horizontal") === k ? "on" : ""}" onclick="setSplitDir('${k}')">${n}</button>`).join("")}</div></div>
    <div class="srow"><div class="d"><b>UI scale / display zoom (<span id="ui-scale-lbl">${l.uiScale || 100}%</span>)</b><span>Scale down to 85–92% on smaller laptop screens to fit more without scrolling</span></div>
      <div class="row" style="gap:8px"><input type="range" min="80" max="120" step="2" value="${l.uiScale || 100}" oninput="setUiScale(this.value,true)" onchange="setUiScale(this.value,false)"><button class="btn sm ghost" onclick="setUiScale(100,false);renderLayoutSettings()">100%</button></div></div>
    <div class="srow"><div class="d"><b>Minimize top bar</b><span>Compact header bar for extra vertical space on laptops</span></div><button class="sw ${l.topbarMin ? "on" : ""}" onclick="toggleTopbarMin()"></button></div>
    <div class="grouph">Fine-tune</div>
    <div class="srow"><div class="d"><b>Sidebar order &amp; position</b><span>Drag pages into your order · put the bar left, right, top or bottom</span></div><button class="btn" onclick="sidebarModal()">${ic("sidebar")}Customize sidebar</button></div>
    <div class="srow"><div class="d"><b>Sidebar pages</b><span>Hide the pages you don't use</span></div><div class="row" style="gap:6px;max-width:520px;justify-content:flex-end">
      ${NAV_PAGES.map(([v, n]) => `<button class="chipb ${l.nav.includes(v) ? "on" : ""}" onclick="layNav('${v}')">${n}</button>`).join("")}</div></div>
    <div class="srow"><div class="d"><b>Density</b><span>How much fits on screen</span></div><div class="seg">${[["comfy", "Roomy"], ["normal", "Normal"], ["compact", "Compact"]].map(([k, n]) => `<button class="${l.density === k ? "on" : ""}" onclick="saveLayoutCfg({density:'${k}',mode:'custom'}).then(renderLayoutSettings)">${n}</button>`).join("")}</div></div>
    <div class="srow"><div class="d"><b>Keyboard hints</b><span>Show shortcut badges like “Alt 1”</span></div><button class="sw ${l.hints ? "on" : ""}" onclick="saveLayoutCfg({hints:${!l.hints},mode:'custom'}).then(renderLayoutSettings)"></button></div>
    <div class="srow"><div class="d"><b>Top-bar quick tools</b><span>Sticky, annotate, dictate, timers buttons</span></div><button class="sw ${l.quick ? "on" : ""}" onclick="saveLayoutCfg({quick:${!l.quick},mode:'custom'}).then(renderLayoutSettings)"></button></div>
    <div class="srow"><div class="d"><b>Status in sidebar</b><span>Local AI / Claude indicators</span></div><button class="sw ${l.status ? "on" : ""}" onclick="saveLayoutCfg({status:${!l.status},mode:'custom'}).then(renderLayoutSettings)"></button></div>
    <div class="srow"><div class="d"><b>Start on</b><span>The page Daybook opens to</span></div><select class="f" style="width:auto" onchange="saveLayoutCfg({start:this.value})">${NAV_PAGES.filter(([v]) => l.nav.includes(v)).map(([v, n]) => `<option value="${v}" ${l.start === v ? "selected" : ""}>${n}</option>`).join("")}</select></div>`;
}
async function layNav(v) { const l = layoutCfg(); const nav = l.nav.includes(v) ? l.nav.filter(x => x !== v) : [...l.nav, v]; if (!nav.length) return; await saveLayoutCfg({nav, mode: "custom"}); renderLayoutSettings(); }
