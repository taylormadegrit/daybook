// ================= LAUNCHPAD: console-style home for browser profiles (accounts) + apps =================
const LP = {data: null, row: 0, col: 0, view: "home", q: "", shelf: "All"};
const lpRows = () => {
  const accts = [];
  (LP.data.browsers || []).forEach(b => b.profiles.forEach(p => accts.push({type: "profile", b, p, color: p.color || b.color, name: p.name, sub: p.email || b.name})));
  const apps = (LP.data.pinned || []).map(a => ({type: "app", a, name: a.name, sub: a.shelf === "Other" ? "App" : a.shelf, color: null}));
  return [accts, [...apps, {type: "add", name: "Add apps", sub: "Pin anything from your PC"}]];
};
async function renderLaunchpad(force) {
  if (!LP.data || force) { $("#lp").innerHTML = `<div class="empty" style="padding-top:20vh"><b>Finding your browsers and apps…</b></div>`; LP.data = await api("/api/launchpad" + (force === "rescan" ? "?rescan=1" : "")); }
  (({all: lpAllApps, games: renderGames, folders: renderFolders})[LP.view] || lpHome)();
}
function lpTile(it, r, c) {
  const on = r === LP.row && c === LP.col;
  let face;
  if (it.type === "profile") face = it.p.picture ? `<img src="/browser-avatar/${it.b.id}/${encodeURIComponent(it.p.id)}" alt="">` : `<span class="ini" style="background:${it.color}">${esc((it.name || "?").trim()[0].toUpperCase())}</span>`;
  else if (it.type === "app") face = `<img src="/app-icon/${it.a.id}.png" alt="" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'ini',textContent:'${esc(it.name[0]).replace(/'/g, "")}'}))">`;
  else face = `<span class="ini add">${ic("plus", "i")}</span>`;
  return `<button class="lpt ${on ? "on" : ""} t-${it.type}" data-r="${r}" data-c="${c}" onmouseenter="lpFocus(${r},${c},1)" onfocus="lpFocus(${r},${c},1)" onclick="lpOpen(${r},${c})" title="${esc(it.name)}">
    ${face}${it.type === "profile" ? `<i class="bdg" style="background:${it.b.color}" title="${esc(it.b.name)}">${esc(it.b.name[0])}</i>` : ""}<span class="lbl">${esc(it.name)}</span></button>`;
}
function lpHome() {
  const rows = lpRows(); LP.row = Math.min(LP.row, 1); LP.col = Math.min(LP.col, rows[LP.row].length - 1);
  $("#lp").innerHTML = `<div class="lp-top">${lpTabs()}
      <div class="sp"></div><button class="iconbtn" title="Rescan browsers & apps" onclick="renderLaunchpad('rescan')">${ic("rep")}</button><span class="lp-clock" id="lp-clock"></span></div>
    <div class="lp-row"><div class="lp-rl">Accounts</div><div class="lp-tiles" id="lp-r0">${rows[0].map((it, c) => lpTile(it, 0, c)).join("") || `<span class="muted small">No browsers found</span>`}</div></div>
    <div class="lp-row"><div class="lp-rl">Apps</div><div class="lp-tiles" id="lp-r1">${rows[1].map((it, c) => lpTile(it, 1, c)).join("")}</div></div>
    <div class="lp-hero" id="lp-hero"></div>
    <div class="lp-keys">←→↑↓ move · Enter open · P pin/unpin</div>`;
  lpFocus(LP.row, LP.col); lpClock();
}
function lpFocus(r, c, fromFocus) {
  const rows = lpRows(); if (!rows[r] || !rows[r][c]) return;
  LP.row = r; LP.col = c;
  $$(".lpt").forEach(t => t.classList.toggle("on", +t.dataset.r === r && +t.dataset.c === c));
  const it = rows[r][c], h = $("#lp-hero"); if (!h) return;
  const color = it.color || "var(--a1)";
  $("#lp").style.setProperty("--lpc", color);
  const art = it.type === "profile" && it.p.picture ? `/browser-avatar/${it.b.id}/${encodeURIComponent(it.p.id)}` : it.type === "app" ? `/app-icon/${it.a.id}.png` : "";
  $("#lp").style.setProperty("--lpart", art ? `url("${art}")` : "none");
  if (it.type === "profile") {
    h.innerHTML = `<div class="lp-h1">${esc(it.name)}</div><div class="lp-sub">${esc(it.p.account || "")}${it.p.email ? " · " + esc(it.p.email) : ""} <span class="badge">${esc(it.b.name)}</span></div>
      <div class="row" style="margin-top:16px;gap:8px"><button class="btn pri lg" onclick="bwOpen('${it.b.id}','${esc(it.p.id)}')">${ic("play")}Open in Daybook</button>
        <button class="btn" onclick="lpBrowser('${it.b.id}','${esc(it.p.id)}')" title="Open as its own separate window">${ic("ext")}Own window</button>
        ${LP.data.quick_links.map(([n, u]) => `<button class="chipb" onclick="bwOpen('${it.b.id}','${esc(it.p.id)}','${u}')">${n}</button>`).join("")}</div>
      <div class="row" style="margin-top:10px;flex-wrap:nowrap;max-width:560px"><input class="f" id="lp-url" placeholder="Open a site in this profile… e.g. canva.com" onkeydown="if(event.key==='Enter'){bwOpen('${it.b.id}','${esc(it.p.id)}',lpUrl(this.value))}"></div>`;
  } else if (it.type === "app") {
    const pinned = true;
    h.innerHTML = `<div class="lp-h1">${esc(it.name)}</div><div class="lp-sub">${esc(it.sub)}</div>
      <div class="row" style="margin-top:16px;gap:8px"><button class="btn pri lg" onclick="lpOpen(${r},${c})">${ic("play")}Open</button>
        ${/obs/i.test(it.name) ? `<button class="btn" onclick="go('memos');setTimeout(()=>videoRecModal('obs'),300)">${ic("rec")}Record a video note</button>` : ""}
        <button class="btn ghost" onclick="lpPin('${it.a.id}',${!pinned})">${ic("x")}Unpin</button>
        <span class="small muted">${c > 0 ? `<a href="javascript:void 0" onclick="lpMove(${c},-1)">◀ move left</a>` : ""} ${c < rows[1].length - 2 ? `<a href="javascript:void 0" onclick="lpMove(${c},1)">move right ▶</a>` : ""}</span></div>`;
  } else h.innerHTML = `<div class="lp-h1">Add apps</div><div class="lp-sub">Pin DaVinci Resolve, OBS, CapCut, games — anything installed on this PC.</div>
      <div class="row" style="margin-top:16px"><button class="btn pri lg" onclick="LP.view='all';renderLaunchpad()">${ic("grid")}Browse all apps</button></div>`;
  if (!fromFocus) { const t = $(`.lpt[data-r="${r}"][data-c="${c}"]`); t && t.scrollIntoView({block: "nearest", inline: "nearest", behavior: "smooth"}); }
}
const lpUrl = v => (v = v.trim()) && !/^https?:/i.test(v) ? "https://" + v : v;
async function lpBrowser(b, p, url = "") { try { await api("/api/launchpad/browser", {method: "POST", body: {browser: b, profile: p, url}}); toast("Opening…"); } catch (e) { toast(e.message); } }
async function lpOpen(r, c) {
  const it = lpRows()[r][c]; if (!it) return;
  if (it.type === "profile") return store.get("daybook-dock", "1") === "1" ? bwOpen(it.b.id, it.p.id) : lpBrowser(it.b.id, it.p.id);
  if (it.type === "add") { LP.view = "all"; return renderLaunchpad(); }
  try { await api("/api/launchpad/app/" + it.a.id, {method: "POST"}); toast("Opening " + it.name + "…"); } catch (e) { toast(e.message); }
}
async function lpSavePins(ids) { await api("/api/launchpad/pins", {method: "POST", body: {pins: ids}}); const by = Object.fromEntries(LP.data.apps.map(a => [a.id, a])); LP.data.pinned = ids.map(i => by[i]).filter(Boolean); }
async function lpPin(id, on) {
  const ids = LP.data.pinned.map(a => a.id).filter(x => x !== id); if (on) ids.push(id);
  await lpSavePins(ids); toast(on ? "Pinned to Launchpad" : "Unpinned"); renderLaunchpad();
}
async function lpMove(c, d) { const ids = LP.data.pinned.map(a => a.id); [ids[c], ids[c + d]] = [ids[c + d], ids[c]]; await lpSavePins(ids); LP.col = c + d; renderLaunchpad(); }
function lpAllApps() {
  const shelves = ["All", "Create", "Work", "Play", "Social", "Other"], pins = new Set(LP.data.pinned.map(a => a.id)), q = LP.q.toLowerCase();
  const list = LP.data.apps.filter(a => (LP.shelf === "All" || a.shelf === LP.shelf) && a.name.toLowerCase().includes(q));
  $("#lp").innerHTML = `<div class="lp-top">${lpTabs()}
      <input class="f" style="max-width:280px;margin-left:12px" placeholder="Search ${LP.data.apps.length} apps…" value="${esc(LP.q)}" oninput="LP.q=this.value;debounce('lpq',lpAllApps,150)" id="lp-q">
      <div class="sp"></div><span class="lp-clock" id="lp-clock"></span></div>
    <div class="row" style="margin:6px 0 16px;gap:6px">${shelves.map(s => `<button class="chipb ${LP.shelf === s ? "on" : ""}" onclick="LP.shelf='${s}';lpAllApps()">${s}</button>`).join("")}</div>
    <div class="lp-grid">${list.map(a => `<div class="lpg ${pins.has(a.id) ? "pinned" : ""}"><button class="lpi" onclick="api('/api/launchpad/app/${a.id}',{method:'POST'}).then(()=>toast('Opening ${esc(a.name).replace(/'/g, "")}…'))" title="Open">
        <img src="/app-icon/${a.id}.png" loading="lazy" alt="" onerror="this.style.visibility='hidden'"></button><span class="lbl">${esc(a.name)}</span>
        <button class="pin" title="${pins.has(a.id) ? "Unpin" : "Pin to Launchpad"}" onclick="lpPin('${a.id}',${!pins.has(a.id)})">${pins.has(a.id) ? "★" : "☆"}</button></div>`).join("") || `<div class="empty">No apps match</div>`}</div>`;
  lpClock(); const qi = $("#lp-q"); if (LP.q && qi) { qi.focus(); qi.setSelectionRange(LP.q.length, LP.q.length); }
}
function lpClock() { const c = $("#lp-clock"); if (c) c.textContent = new Date().toLocaleTimeString([], {hour: "numeric", minute: "2-digit"}); }
function lpKeys(e) {
  if (S.view !== "launchpad" || LP.view !== "home" || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || $("#scrim").classList.contains("on")) return false;
  const rows = lpRows(); let {row: r, col: c} = LP;
  if (e.key === "ArrowRight") c = Math.min(c + 1, rows[r].length - 1);
  else if (e.key === "ArrowLeft") c = Math.max(c - 1, 0);
  else if (e.key === "ArrowDown" || e.key === "ArrowUp") { r = e.key === "ArrowDown" ? 1 : 0; c = Math.min(c, rows[r].length - 1); }
  else if (e.key === "Enter") { lpOpen(r, c); return true; }
  else if (e.key.toLowerCase() === "p" && rows[r][c].type === "app") { lpPin(rows[r][c].a.id, false); return true; }
  else return false;
  lpFocus(r, c); return true;
}
// home widget: a compact row of the same tiles
async function lpWidget() {
  const el = $("#w-lp"); if (!el) return;
  if (!LP.data) LP.data = await api("/api/launchpad");
  const rows = lpRows();
  el.innerHTML = `<div class="lp-mini">${rows[0].slice(0, 8).map((it, c) => lpTile(it, 0, c)).join("")}</div><div class="lp-mini">${rows[1].slice(0, -1).slice(0, 8).map((it, c) => lpTile(it, 1, c)).join("")}</div>`;
  $$("#w-lp .lpt").forEach(t => { t.onmouseenter = null; t.onfocus = null; t.classList.remove("on"); });
}

function lpTabs() {
  return `<div class="lp-tabs">${[["home", "Home"], ["games", "Games"], ["folders", "Folders"], ["all", "All apps"]].map(([k, l]) => `<button class="${LP.view === k ? "on" : ""}" onclick="LP.view='${k}';history.replaceState(null,'','#launchpad/${k}');renderLaunchpad()">${l}</button>`).join("")}</div>`;
}
