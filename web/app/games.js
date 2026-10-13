// ================= GAMES (Launchpad tab): Steam + Epic library and free open-source games =================
const GM = {data: null, sel: null, filter: "all", poll: 0};
const gmSize = b => b > 1e9 ? (b / 1e9).toFixed(1) + " GB" : Math.round(b / 1e6) + " MB";
async function renderGames(refresh) {
  if (!GM.data || refresh) GM.data = await api("/api/games");
  const d = GM.data, owned = d.owned.filter(g => GM.filter === "all" || g.src === GM.filter);
  const recent = d.owned.filter(g => g.last).slice(0, 10);
  const tile = g => `<button class="gtile ${GM.sel === g.id ? "on" : ""}" onmouseenter="gmFocus('${g.id}')" onclick="gmFocus('${g.id}');gmPlay('${g.id}')" title="${esc(g.name)}">
      <img src="/game-art/${g.id}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'gini',textContent:${JSON.stringify(g.name.slice(0, 2)).replace(/"/g, "&quot;")}}))">
      <i class="src ${g.src}">${g.src === "steam" ? "Steam" : g.src === "epic" ? "Epic" : "Free"}</i><span class="lbl">${esc(g.name)}</span></button>`;
  $("#lp").innerHTML = `<div class="lp-top">${lpTabs()}<div class="sp"></div><button class="iconbtn" title="Refresh" onclick="renderGames(true)">${ic("rep")}</button><span class="lp-clock" id="lp-clock"></span></div>
    <div class="lp-hero gm-hero" id="gm-hero"></div>
    ${recent.length ? `<div class="lp-row"><div class="lp-rl">Recently played</div><div class="lp-tiles gm-row">${recent.map(tile).join("")}</div></div>` : ""}
    <div class="lp-row"><div class="lp-rl" style="display:flex;gap:10px;align-items:center">Your games · ${d.owned.length}
      <span class="seg sm">${[["all", "All"], ["steam", "Steam"], ["epic", "Epic"]].map(([k, l]) => `<button class="${GM.filter === k ? "on" : ""}" onclick="GM.filter='${k}';renderGames()">${l}</button>`).join("")}</span></div>
      <div class="gm-grid">${owned.map(tile).join("") || `<div class="muted small">No ${GM.filter} games installed</div>`}</div></div>
    <div class="lp-row"><div class="lp-rl">Free & open-source games · download and play</div>
      <div class="free-grid">${d.free.map(freeCard).join("")}</div>
      <div class="muted small" style="margin-top:10px">Downloads come straight from each game's official GitHub releases into <code>${esc(d.games_dir)}</code>. Games marked “bring your own” are open-source engines that need files from a copy you own.</div></div>`;
  lpClock();
  if (!GM.sel || !d.owned.find(g => g.id === GM.sel)) GM.sel = (recent[0] || d.owned[0] || {}).id;
  gmFocus(GM.sel);
  if (d.free.some(g => g.job && ["starting", "downloading", "extracting"].includes(g.job.state))) { clearTimeout(GM.poll); GM.poll = setTimeout(() => S.view === "launchpad" && LP.view === "games" && renderGames(true), 1500); }
}
function gmFocus(id) {
  const g = GM.data.owned.find(x => x.id === id); if (!g) return; GM.sel = id;
  $$(".gtile").forEach(t => t.classList.toggle("on", t.getAttribute("onclick").includes(`'${id}'`)));
  $("#lp").style.setProperty("--lpart", `url("/game-art/${id}")`);
  $("#gm-hero").innerHTML = `<div class="lp-h1">${esc(g.name)}</div><div class="lp-sub">${g.src === "steam" ? "Steam" : "Epic Games"} · ${gmSize(g.size)}${g.last ? " · last played " + new Date(g.last * 1000).toLocaleDateString() : ""}</div>
    <div class="row" style="margin-top:14px;gap:8px"><button class="btn pri lg" onclick="gmPlay('${id}')">${ic("play")}Play</button>
      ${g.src === "epic" ? `<button class="btn" title="Start the game's own .exe — works offline for DRM-free games" onclick="gmPlay('${id}',true)">Play offline (direct)</button>` : ""}
      <button class="btn ghost" onclick="api('/api/games/${id}/folder',{method:'POST'})">${ic("note")}Game folder</button></div>
    <div class="muted small" style="margin-top:8px">${g.src === "steam" ? "Plays through Steam with your account. To play without internet: Steam → Go Offline… (once, while online)." : "Plays through the Epic Games Launcher with your account — it supports offline mode for games you've launched online before."}</div>`;
}
async function gmPlay(id, direct) { try { await api(`/api/games/${id}/play`, {method: "POST", body: {direct: !!direct}}); toast("Launching…"); } catch (e) { toast(e.message); } }
function freeCard(g) {
  const j = g.job, busy = j && ["starting", "downloading", "extracting"].includes(j.state);
  const act = busy ? `<div class="meter" style="flex:1"><i style="width:${j.pct}%"></i></div><span class="small">${j.state === "extracting" ? "Unpacking…" : j.pct + "%"}</span>`
    : g.exe ? `<button class="btn sm pri" onclick="gmPlayFree('${g.id}')">${ic("play")}Play</button><button class="btn sm ghost" onclick="gmRemove(this,'${g.id}')">${ic("trash")}</button>`
    : g.installer ? `<button class="btn sm pri" onclick="gmPlayFree('${g.id}')">Run installer</button><button class="btn sm ghost" onclick="gmRemove(this,'${g.id}')">${ic("trash")}</button>`
    : `<button class="btn sm" onclick="gmDownload('${g.id}')">${ic("down")}Download</button><span class="small muted" id="rel-${g.id}"></span>`;
  return `<div class="free"><div class="ft"><b>${esc(g.name)}</b><span class="badge">${esc(g.genre)}</span></div>
    <div class="small muted">${esc(g.desc)}</div>${g.own ? `<div class="small" style="color:var(--warn)">Bring your own: ${esc(g.own)}</div>` : ""}
    ${j && j.state === "error" ? `<div class="small" style="color:var(--bad)">${esc(j.msg)}</div>` : ""}
    <div class="row" style="margin-top:auto;padding-top:8px;flex-wrap:nowrap">${act}<a class="small muted" style="margin-left:auto" href="https://github.com/${g.repo}" target="_blank" rel="noopener">GitHub</a></div></div>`;
}
async function gmDownload(id) {
  try { const r = await api("/api/games/release/" + id); toast(`Downloading ${r.asset} (${gmSize(r.size)})…`); } catch (e) {}
  await api(`/api/games/${id}/download`, {method: "POST"}); renderGames(true);
}
async function gmPlayFree(id) { try { await api(`/api/games/${id}/play`, {method: "POST"}); toast("Launching…"); } catch (e) { toast(e.message); } }
async function gmRemove(btn, id) { if (!btn.dataset.sure) { btn.dataset.sure = 1; btn.innerHTML = "Remove?"; return; } await api(`/api/games/${id}/remove`, {method: "POST"}); toast("Removed"); renderGames(true); }
// home widget
async function gamesWidget() {
  const el = $("#w-games"); if (!el) return;
  if (!GM.data) GM.data = await api("/api/games");
  const list = (GM.data.owned.filter(g => g.last).length ? GM.data.owned.filter(g => g.last) : GM.data.owned).slice(0, 6);
  el.innerHTML = `<div class="gm-mini">${list.map(g => `<button class="gtile sm" title="Play ${esc(g.name)}" onclick="gmPlay('${g.id}')"><img src="/game-art/${g.id}" alt="" loading="lazy"><span class="lbl">${esc(g.name)}</span></button>`).join("")}</div>`;
}

// ================= FOLDERS (Launchpad tab): pinned folders, in-app browser, workflows =================
const FD = {data: null, path: null, list: null, q: ""};
const FCOL = ["#8b7bff", "#4fd1ff", "#ff7ac6", "#3ee0a0", "#ffbe5c", "#ff6b81"];
const FICON = e => /\.(png|jpe?g|gif|webp|bmp)$/.test(e) ? "🖼" : /\.(mp4|mkv|mov|webm|avi)$/.test(e) ? "🎬" : /\.(mp3|wav|m4a|flac|ogg)$/.test(e) ? "🎵" : /\.(pdf)$/.test(e) ? "📕" : /\.(txt|md|docx?|odt|rtf)$/.test(e) ? "📄" : /\.(zip|7z|rar)$/.test(e) ? "🗜" : /\.(exe|msi|lnk|bat)$/.test(e) ? "⚙" : "📄";
async function renderFolders(refresh) {
  if (!FD.data || refresh) FD.data = await api("/api/folders");
  const d = FD.data;
  $("#lp").innerHTML = `<div class="lp-top">${lpTabs()}<div class="sp"></div><span class="lp-clock" id="lp-clock"></span></div>
    <div class="lp-row"><div class="lp-rl">Workflows — open everything you need in one click</div><div class="wf-row">
      ${d.workflows.map((w, i) => `<div class="wf" style="--c:${w.color || FCOL[i % 6]}"><b>${esc(w.name)}</b><span>${w.items.length} item${w.items.length === 1 ? "" : "s"}: ${esc(w.items.map(x => x.label).join(", ")).slice(0, 80)}</span>
        <div class="row" style="margin-top:auto"><button class="btn sm pri" onclick="wfRun(${i})">${ic("play")}Start</button><button class="btn sm ghost" onclick="wfModal(${i})">${ic("pen")}</button></div></div>`).join("")}
      <div class="wf add" onclick="wfModal()">${ic("plus", "i")}<b>New workflow</b><span>e.g. “Editing”: recordings folder + CapCut + YouTube Studio</span></div></div></div>
    <div class="lp-row"><div class="lp-rl" style="display:flex;align-items:center;gap:10px">Pinned folders<button class="btn sm" onclick="fdPick()">${ic("plus")}Add folder</button></div>
      <div class="fd-grid">${d.pins.map((f, i) => `<div class="fd" style="--c:${f.color || FCOL[i % 6]}" onclick="fdBrowse(${JSON.stringify(f.path).replace(/"/g, "&quot;")})">
        <div class="fdi">📁</div><b>${esc(f.name)}</b><span title="${esc(f.path)}">${esc(f.path)}</span>
        <div class="fda"><button class="iconbtn" title="Open in File Explorer" onclick="event.stopPropagation();fdOpen(${JSON.stringify(f.path).replace(/"/g, "&quot;")})">${ic("ext")}</button>
          <button class="iconbtn" title="Unpin" onclick="event.stopPropagation();fdUnpin(${i})">${ic("x")}</button></div></div>`).join("") || `<div class="muted small">No folders pinned yet — add the ones you open every day.</div>`}</div>
      ${d.suggestions.length ? `<div class="row" style="margin-top:12px;gap:6px"><span class="small muted">Suggestions:</span>${d.suggestions.map(s => `<button class="chipb" title="${esc(s.path)}" onclick="fdPin(${JSON.stringify(s.path).replace(/"/g, "&quot;")},'${esc(s.name)}')">＋ ${esc(s.name)}</button>`).join("")}</div>` : ""}</div>
    <div id="fd-browser"></div>`;
  lpClock(); if (FD.path) fdBrowse(FD.path);
}
async function fdPick() { toast("Pick a folder in the window that just opened…"); const j = await api("/api/folders/pick", {method: "POST"}); if (j.path) fdPin(j.path); }
async function fdPin(path, name) { const pins = [...FD.data.pins, {path, name: name || path.split(/[\\/]/).filter(Boolean).pop()}]; await api("/api/folders/pins", {method: "POST", body: {pins}}); toast("Pinned"); renderFolders(true); }
async function fdUnpin(i) { const pins = FD.data.pins.filter((_, j) => j !== i); await api("/api/folders/pins", {method: "POST", body: {pins}}); renderFolders(true); }
function fdOpen(path, reveal) { api("/api/folders/open", {method: "POST", body: {path, reveal: !!reveal}}).catch(e => toast(e.message)); }
async function fdBrowse(path) {
  let j; try { j = await api("/api/folders/list?path=" + encodeURIComponent(path)); } catch (e) { return toast(e.message); }
  FD.path = j.path; FD.list = j;
  const parts = j.path.split("\\").filter(Boolean); let acc = "";
  const crumbs = parts.map((p, i) => { acc += p + "\\"; return `<a href="javascript:void 0" onclick="fdBrowse(${JSON.stringify(acc).replace(/"/g, "&quot;")})">${esc(p)}</a>`; }).join(" › ");
  const q = FD.q.toLowerCase(), items = j.items.filter(x => x.name.toLowerCase().includes(q));
  $("#fd-browser").innerHTML = `<div class="card fd-browser"><div class="row" style="flex-wrap:nowrap;gap:8px">
      ${j.parent ? `<button class="iconbtn" title="Up a folder" onclick="fdBrowse(${JSON.stringify(j.parent).replace(/"/g, "&quot;")})">${ic("up")}</button>` : ""}
      <div class="crumbs">${crumbs}</div><div class="sp"></div>
      <input class="f" style="width:200px;padding:5px 10px" placeholder="Filter…" value="${esc(FD.q)}" oninput="FD.q=this.value;debounce('fdq',()=>fdBrowse(FD.path),150)">
      <button class="btn sm" onclick="fdPin(FD.path)">${ic("plus")}Pin</button><button class="btn sm" onclick="fdOpen(FD.path)">${ic("ext")}Explorer</button>
      <button class="iconbtn" title="Close" onclick="FD.path=null;$('#fd-browser').innerHTML=''">${ic("x")}</button></div>
    <div class="fl">${items.map(x => `<div class="fr" ondblclick="${x.dir ? `fdBrowse(${JSON.stringify(x.path).replace(/"/g, "&quot;")})` : `fdOpen(${JSON.stringify(x.path).replace(/"/g, "&quot;")})`}">
        <span class="fic">${x.dir ? "📁" : /\.(png|jpe?g|gif|webp)$/.test(x.ext) ? `<img src="/api/folders/thumb?path=${encodeURIComponent(x.path)}" loading="lazy">` : FICON(x.ext)}</span>
        <span class="fn" title="${esc(x.name)}">${esc(x.name)}</span><span class="small muted">${x.dir ? "" : gmSize(x.size).replace("0 MB", "<1 MB")}</span><span class="small muted">${dayName(x.modified)}</span>
        <span class="fa">${x.dir ? `<button class="btn sm ghost" onclick="fdBrowse(${JSON.stringify(x.path).replace(/"/g, "&quot;")})">Open</button>`
          : `<button class="iconbtn" title="Open" onclick="fdOpen(${JSON.stringify(x.path).replace(/"/g, "&quot;")})">${ic("play")}</button><button class="iconbtn" title="Show in Explorer" onclick="fdOpen(${JSON.stringify(x.path).replace(/"/g, "&quot;")},1)">${ic("ext")}</button>
             <button class="iconbtn" title="Send to Discord" onclick='discordSend("file",${JSON.stringify(x.path).replace(/'/g, "&#39;")})'>${ic("send")}</button>`}</span></div>`).join("") || `<div class="empty">Empty folder</div>`}</div>
    ${j.total > items.length && !q ? `<div class="small muted">Showing ${items.length} of ${j.total}</div>` : ""}</div>`;
  $("#fd-browser").scrollIntoView({behavior: "smooth", block: "nearest"});
}
// workflows
async function wfRun(i) { const j = await api(`/api/workflows/${i}/run`, {method: "POST"}); toast(`Started “${FD.data.workflows[i].name}” — opened ${j.opened}`); }
async function wfModal(i) {
  if (!LP.data) LP.data = await api("/api/launchpad");
  const w = i !== undefined ? FD.data.workflows[i] : {name: "", items: []};
  window._wf = JSON.parse(JSON.stringify(w.items));
  const opts = [...FD.data.pins.map(f => ({type: "folder", path: f.path, label: "📁 " + f.name})),
    ...LP.data.pinned.map(a => ({type: "app", id: a.id, label: "▶ " + a.name})),
    ...LP.data.browsers.flatMap(b => b.profiles.map(p => ({type: "profile", browser: b.id, profile: p.id, label: "🌐 " + p.name + " (" + b.name.replace("Google ", "") + ")"})))];
  window._wfopts = opts;
  modal(`<h2>${ic("play", "i")}${i !== undefined ? "Edit" : "New"} workflow<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="frm"><label>Name</label><input class="f" id="wf-n" value="${esc(w.name)}" placeholder="e.g. Editing, Morning uploads, Study">
    <label>Opens</label><div id="wf-items"></div>
    <label>Add</label><div class="row" style="flex-wrap:nowrap"><select class="f" id="wf-add"><option value="">Choose a folder, app or browser profile…</option>${opts.map((o, k) => `<option value="${k}">${esc(o.label)}</option>`).join("")}</select>
      <button class="btn" onclick="const v=$('#wf-add').value;if(v!==''){_wf.push(_wfopts[+v]);wfItems()}">Add</button></div>
    <label>Website</label><div class="row" style="flex-wrap:nowrap"><input class="f" id="wf-url" placeholder="https://studio.youtube.com"><button class="btn" onclick="const u=lpUrl($('#wf-url').value);if(u){_wf.push({type:'url',url:u,label:'🔗 '+u.replace(/^https?:\\/\\//,'')});$('#wf-url').value='';wfItems()}">Add</button></div></div>
    <div class="row" style="margin-top:16px"><button class="btn pri" onclick="wfSave(${i ?? -1})">${ic("check")}Save</button>${i !== undefined ? `<div class="sp"></div><button class="btn ghost danger" onclick="wfDel(${i})">${ic("trash")}Delete</button>` : ""}</div>`, true);
  wfItems();
}
function wfItems() { $("#wf-items").innerHTML = window._wf.map((x, k) => `<span class="tag on">${esc(x.label)} <a href="javascript:void 0" onclick="_wf.splice(${k},1);wfItems()">✕</a></span>`).join(" ") || `<span class="muted small">Nothing yet</span>`; }
async function wfSave(i) {
  const name = $("#wf-n").value.trim(); if (!name || !window._wf.length) return toast("Give it a name and at least one item");
  const ws = [...FD.data.workflows]; const w = {name, items: window._wf};
  i >= 0 ? (ws[i] = w) : ws.push(w); await api("/api/workflows", {method: "POST", body: {workflows: ws}}); closeModal(); renderFolders(true);
}
async function wfDel(i) { const ws = FD.data.workflows.filter((_, j) => j !== i); await api("/api/workflows", {method: "POST", body: {workflows: ws}}); closeModal(); renderFolders(true); }
async function foldersWidget() {
  const el = $("#w-folders"); if (!el) return;
  if (!FD.data) FD.data = await api("/api/folders");
  el.innerHTML = (FD.data.workflows.length ? `<div class="row" style="gap:6px;margin-bottom:8px">${FD.data.workflows.map((w, i) => `<button class="chipb" onclick="wfRun(${i})">▶ ${esc(w.name)}</button>`).join("")}</div>` : "")
    + (FD.data.pins.slice(0, 6).map(f => `<div class="cat" onclick="fdOpen(${JSON.stringify(f.path).replace(/"/g, "&quot;")})" title="Open in File Explorer">📁 <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(f.name)}</span><span class="c">${ic("ext")}</span></div>`).join("")
    || `<div class="muted small">No folders pinned — <a href="javascript:void 0" onclick="go('launchpad','folders')">add some</a>.</div>`);
}
