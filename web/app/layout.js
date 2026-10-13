// ================= LAYOUT: Simple · Balanced · Power, or fully custom =================
const NAV_PAGES = [["today", "Today"], ["launchpad", "Launchpad"], ["calendar", "Calendar"], ["reminders", "Reminders"], ["notes", "Notes"], ["memos", "Voice & video"], ["studio", "AI Studio"],
  ["clock", "Clock"], ["desktop", "Desktop"], ["chat", "Chat"], ["models", "Models"]];
const PRESETS_LAYOUT = {
  simple: {name: "Simple", desc: "Just the essentials — big, calm, no shortcuts to learn", nav: ["today", "launchpad", "notes", "memos", "studio", "clock"], density: "comfy", hints: false, quick: false, status: false,
    widgets: ["nownext", "schedule", "timers", "log"]},
  balanced: {name: "Balanced", desc: "Everything, with room to breathe (default)", nav: NAV_PAGES.map(p => p[0]), density: "normal", hints: true, quick: true, status: true,
    widgets: ["nownext", "schedule", "log", "timers", "stickies", "alarms", "upnext", "ambience"]},
  power: {name: "Power", desc: "Dense, every page and shortcut, more widgets", nav: NAV_PAGES.map(p => p[0]), density: "compact", hints: true, quick: true, status: true,
    widgets: ["nownext", "schedule", "launchpad", "timers", "log", "studio", "games", "folders", "stopwatch", "alarms", "world", "memos", "notes", "upnext", "stickies"]},
};
function layoutCfg() { let l = {}; try { l = JSON.parse(S.settings.layout || "{}"); } catch (e) {} return {...PRESETS_LAYOUT.balanced, mode: "balanced", start: "today", ...l}; }
function applyLayout() {
  const l = layoutCfg(), b = document.body;
  b.classList.toggle("lay-compact", l.density === "compact"); b.classList.toggle("lay-comfy", l.density === "comfy");
  b.classList.toggle("lay-nohints", !l.hints); b.classList.toggle("lay-noquick", !l.quick); b.classList.toggle("lay-nostatus", !l.status);
  $$(".navi").forEach(n => { const v = n.dataset.v; if (v === "settings" || v === "help") return; n.style.display = l.nav.includes(v) ? "" : "none"; });
  $$(".lay-pick button").forEach(x => x.classList.toggle("on", x.dataset.m === l.mode));
}
async function saveLayoutCfg(patch) { const l = {...layoutCfg(), ...patch}; S.settings = await api("/api/settings", {method: "PATCH", body: {layout: JSON.stringify(l)}}); applyLayout(); return l; }
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
    <div class="grouph">Fine-tune</div>
    <div class="srow"><div class="d"><b>Sidebar pages</b><span>Hide the pages you don't use</span></div><div class="row" style="gap:6px;max-width:520px;justify-content:flex-end">
      ${NAV_PAGES.map(([v, n]) => `<button class="chipb ${l.nav.includes(v) ? "on" : ""}" onclick="layNav('${v}')">${n}</button>`).join("")}</div></div>
    <div class="srow"><div class="d"><b>Density</b><span>How much fits on screen</span></div><div class="seg">${[["comfy", "Roomy"], ["normal", "Normal"], ["compact", "Compact"]].map(([k, n]) => `<button class="${l.density === k ? "on" : ""}" onclick="saveLayoutCfg({density:'${k}',mode:'custom'}).then(renderLayoutSettings)">${n}</button>`).join("")}</div></div>
    <div class="srow"><div class="d"><b>Keyboard hints</b><span>Show shortcut badges like “Alt 1”</span></div><button class="sw ${l.hints ? "on" : ""}" onclick="saveLayoutCfg({hints:${!l.hints},mode:'custom'}).then(renderLayoutSettings)"></button></div>
    <div class="srow"><div class="d"><b>Top-bar quick tools</b><span>Sticky, annotate, dictate, timers buttons</span></div><button class="sw ${l.quick ? "on" : ""}" onclick="saveLayoutCfg({quick:${!l.quick},mode:'custom'}).then(renderLayoutSettings)"></button></div>
    <div class="srow"><div class="d"><b>Status in sidebar</b><span>Local AI / Claude indicators</span></div><button class="sw ${l.status ? "on" : ""}" onclick="saveLayoutCfg({status:${!l.status},mode:'custom'}).then(renderLayoutSettings)"></button></div>
    <div class="srow"><div class="d"><b>Start on</b><span>The page Daybook opens to</span></div><select class="f" style="width:auto" onchange="saveLayoutCfg({start:this.value})">${NAV_PAGES.filter(([v]) => l.nav.includes(v)).map(([v, n]) => `<option value="${v}" ${l.start === v ? "selected" : ""}>${n}</option>`).join("")}</select></div>`;
}
async function layNav(v) { const l = layoutCfg(); const nav = l.nav.includes(v) ? l.nav.filter(x => x !== v) : [...l.nav, v]; if (!nav.length) return; await saveLayoutCfg({nav, mode: "custom"}); renderLayoutSettings(); }
