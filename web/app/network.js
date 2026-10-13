// ================= NETWORK: connection status in the top bar + Wi-Fi picker =================
const NET = {st: null, list: null, open: false, busy: false, speed: null, pick: null};
const netBars = s => `<svg class="i sm" viewBox="0 0 24 24" style="stroke:none">${[[3, 17, 4], [8, 13, 8], [13, 9, 12], [18, 5, 16]].map(([x, y, h], i) => `<rect x="${x}" y="${y}" width="3.4" height="${h}" rx="1" fill="currentColor" opacity="${s >= [1, 30, 55, 80][i] ? 1 : .25}"/>`).join("")}</svg>`;
const ICON_ETH = `<svg class="i sm" viewBox="0 0 24 24"><path d="M5 3h14v12H5zM9 15v3M15 15v3M7 21h10M8 7h1M11 7h1M14 7h1"/></svg>`;
async function netRefresh(full) {
  try { NET.st = await api("/api/network" + (full ? "?ping=1" : "")); } catch (e) { NET.st = null; }
  const b = $("#netbtn"); if (!b) return;
  const w = NET.st && NET.st.wifi, c = NET.st && NET.st.conn;
  const online = c && /internet/i.test(c.internet || "");
  b.innerHTML = !c ? `<span style="color:var(--bad)">${netBars(0)}</span>` : c.kind === "wifi" && w ? netBars(w.signal) : ICON_ETH;
  b.classList.toggle("offline", !online);
  b.title = !c ? "Not connected — click to pick a network" : `${c.kind === "wifi" && w ? w.ssid + " · " + w.signal + "%" : (c.alias || "Ethernet")}${online ? "" : " · no internet"} — click for details`;
  if (NET.open) netPanel();
}
async function netToggle(e) {
  e && e.stopPropagation(); const m = $("#netmenu");
  if (m.classList.contains("on")) { m.classList.remove("on"); NET.open = false; return; }
  $$(".menu").forEach(x => x.classList.remove("on")); m.classList.add("on"); NET.open = true;
  netPanel(); await netRefresh(true); netScan(false); netScan(true);
}
async function netScan(fresh) { try { NET.list = await api("/api/network/wifi" + (fresh ? "?scan=1" : "")); } catch (e) { NET.list = {items: []}; } if (NET.open) netPanel(); }
function netPanel() {
  const m = $("#netmenu"), st = NET.st || {}, w = st.wifi, c = st.conn;
  const online = c && /internet/i.test(c.internet || "");
  const cur = !c ? `<div class="net-cur off"><b>Not connected</b><span>Pick a network below</span></div>`
    : `<div class="net-cur"><div class="row" style="flex-wrap:nowrap;gap:10px"><span class="net-ic">${c.kind === "wifi" && w ? netBars(w.signal) : ICON_ETH}</span>
        <div style="min-width:0;flex:1"><b>${esc(c.kind === "wifi" && w ? w.ssid : c.name || c.alias)}</b><span>${online ? "Connected · Internet" : "Connected · no internet"}${st.ping_ms ? " · " + st.ping_ms + " ms ping" : ""}</span></div>
        ${c.kind === "wifi" ? `<button class="btn sm ghost" onclick="netAct('disconnect')">Disconnect</button>` : ""}</div>
      <div class="net-grid">${[["Signal", w ? w.signal + "%" : ""], ["Speed", w ? `${w.rx} ↓ / ${w.tx} ↑ Mbps` : c.speed], ["Wi-Fi", w ? `${w.radio}${w.channel ? " · ch " + w.channel : ""}` : ""],
        ["Security", w ? w.auth : ""], ["IP address", c.ip], ["Router", c.gateway], ["DNS", c.dns], ["Adapter", c.desc]].filter(x => x[1]).map(([k, v]) => `<span>${k}</span><b title="${esc(v)}">${esc(v)}</b>`).join("")}</div>
      <div class="row" style="gap:8px;margin-top:8px"><button class="btn sm" id="net-speed" onclick="netSpeed()">${ic("zap")}Speed test</button>
        <span class="small muted" id="net-speed-r">${NET.speed ? `↓ ${NET.speed.down_mbps} Mbps · ${NET.speed.ping_ms ?? "?"} ms` : ""}</span></div></div>`;
  const items = (NET.list && NET.list.items) || [];
  const list = NET.list && NET.list.error === "location" ? `<div class="obs-card small">Windows needs location access turned on to list Wi-Fi networks. <a href="javascript:void 0" onclick="netAct('location')">Open location settings</a></div>`
    : !st.has_wifi && NET.st ? `<div class="muted small" style="padding:8px">No Wi-Fi adapter on this PC — you're on ${esc((c && c.alias) || "Ethernet")}.</div>`
    : items.length ? items.filter(n => !(w && n.ssid === w.ssid && w.state === "connected")).map(n => `<div class="net-row" onclick="netPick(${JSON.stringify(n.ssid).replace(/"/g, "&quot;")})">
        <span class="net-ic">${netBars(n.signal)}</span><span class="net-n">${esc(n.ssid)}</span>${n.saved ? `<span class="badge">saved</span>` : ""}<span class="small muted">${n.secure ? "🔒" : "open"}</span></div>
        ${NET.pick === n.ssid ? `<div class="net-join">${n.secure && !n.saved ? `<input class="f" type="password" id="net-pw" placeholder="Wi-Fi password" onkeydown="event.key==='Enter'&&netJoin()">` : ""}
          <button class="btn sm pri" onclick="netJoin()">${NET.busy ? "Connecting…" : "Connect"}</button>${n.saved ? `<button class="btn sm ghost" onclick="netAct('forget',{ssid:NET.pick})">Forget</button>` : ""}</div>` : ""}`).join("")
    : `<div class="muted small" style="padding:8px">${NET.list ? "No networks found" : "Looking for networks…"}</div>`;
  m.innerHTML = `<div class="net-h"><b>Network</b><button class="iconbtn" title="Scan again" onclick="event.stopPropagation();netScan(true)">${ic("rep")}</button>
      <button class="iconbtn" title="Windows network settings" onclick="netAct('settings')">${ic("sliders")}</button></div>${cur}
    ${st.has_wifi ? `<div class="mh" style="padding-left:2px">Wi-Fi networks</div>` : ""}<div class="net-list">${list}</div>`;
  m.onclick = e => e.stopPropagation();
  paintIcons(m); if (NET.pick && $("#net-pw")) $("#net-pw").focus({preventScroll: true});
}
function netPick(ssid) { NET.pick = NET.pick === ssid ? null : ssid; netPanel(); }
async function netJoin() {
  const pw = ($("#net-pw") || {}).value || ""; NET.busy = true; netPanel();
  try { await api("/api/network/connect", {method: "POST", body: {ssid: NET.pick, password: pw}}); toast("Connected to " + NET.pick + " ✓"); NET.pick = null; }
  catch (e) { toast(e.message); }
  NET.busy = false; await netRefresh(true); netScan(false);
}
async function netAct(a, body) { try { await api("/api/network/" + a, {method: "POST", body: body || {}}); } catch (e) { toast(e.message); } if (a !== "settings" && a !== "location") { NET.pick = null; await netRefresh(true); netScan(false); } }
async function netSpeed() {
  const b = $("#net-speed"); if (b) { b.disabled = true; b.textContent = "Testing…"; }
  try { NET.speed = await api("/api/network/speed", {method: "POST"}); } catch (e) { toast(e.message); }
  netPanel();
}
function netInit() { netRefresh(); setInterval(() => document.visibilityState === "visible" && netRefresh(), 30000); document.addEventListener("click", () => { if (NET.open) { $("#netmenu").classList.remove("on"); NET.open = false; } }); }
