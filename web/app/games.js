// ================= GAMES (Launchpad tab): one tidy library + a free-games store =================
const GM = {data: null, view: store.get("daybook-gm-view", "library"), q: "", sort: store.get("daybook-gm-sort", "recent"), src: "all", genre: "All", poll: 0};
const gmSize = b => !b ? "" : b > 1e9 ? (b / 1e9).toFixed(1) + " GB" : Math.max(1, Math.round(b / 1e6)) + " MB";
const SRC_NAME = {steam: "Steam", epic: "Epic", free: "Free"};
const gmHue = s => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
// cover art, or a clean gradient card with the title when a game has none
const gmPh = (name, wide) => `<div class="gph ${wide ? "wide" : ""}" style="--h:${gmHue(name)}"><span>${esc(name.replace(/[™®]/g, ""))}</span></div>`;
const gmArt = (g, wide) => `<img src="/game-art/${g.id}?name=${encodeURIComponent(g.name)}${wide ? "&wide=1" : ""}" alt="" loading="lazy" onerror="this.outerHTML=gmPh(this.dataset.n,${!!wide})" data-n="${esc(g.name)}">`;
const playedText = g => !g.last ? "" : (d => { const days = Math.floor((Date.now() - d) / 864e5); return days < 1 ? "Played today" : days < 2 ? "Played yesterday" : days < 30 ? `Played ${days} days ago` : "Played " + new Date(d).toLocaleDateString([], {month: "short", year: "numeric"}); })(g.last * 1000);

async function renderGames(refresh) {
  if (!GM.data || refresh) GM.data = await api("/api/games");
  const d = GM.data, games = d.owned.filter(g => g.kind === "game");
  $("#lp").innerHTML = `<div class="lp-top">${lpTabs()}<div class="sp"></div><span class="lp-clock" id="lp-clock"></span></div>
    <div class="gm-head">
      <div class="seg gm-views"><button class="${GM.view === "library" ? "on" : ""}" onclick="gmView('library')">${ic("grid")}My library <span class="cnt">${games.length}</span></button>
        <button class="${GM.view === "free" ? "on" : ""}" onclick="gmView('free')">${ic("down")}Get free games <span class="cnt">${d.free.length}</span></button></div>
      <div class="gm-search">${ic("search")}<input id="gm-q" placeholder="${GM.view === "library" ? "Search your games…" : "Search free games…"}" value="${esc(GM.q)}" oninput="GM.q=this.value;debounce('gmq',gmBody,120)"></div>
      ${GM.view === "library" ? `<select class="f gm-sort" onchange="GM.sort=this.value;store.set('daybook-gm-sort',this.value);gmBody()">
          ${[["recent", "Recently played"], ["az", "A → Z"], ["size", "Largest first"]].map(([k, l]) => `<option value="${k}" ${GM.sort === k ? "selected" : ""}>${l}</option>`).join("")}</select>` : ""}
      <button class="iconbtn" title="Refresh" onclick="renderGames(true)">${ic("rep")}</button></div>
    <div id="gm-body"></div>`;
  paintIcons($("#lp")); lpClock(); gmBody();
  if (d.free.some(g => g.job && ["starting", "downloading", "extracting"].includes(g.job.state))) { clearTimeout(GM.poll); GM.poll = setTimeout(() => S.view === "launchpad" && LP.view === "games" && renderGames(true), 1500); }
}
function gmView(v) { GM.view = v; GM.q = ""; store.set("daybook-gm-view", v); renderGames(); }
function gmBody() { GM.view === "free" ? gmFree() : gmLibrary(); paintIcons($("#gm-body")); }

function gmLibrary() {
  const d = GM.data, q = GM.q.toLowerCase();
  const match = g => (GM.src === "all" || g.src === GM.src) && (!q || g.name.toLowerCase().includes(q));
  const sorter = {recent: (a, b) => (b.last - a.last) || a.name.localeCompare(b.name), az: (a, b) => a.name.localeCompare(b.name), size: (a, b) => b.size - a.size}[GM.sort];
  const games = d.owned.filter(g => g.kind === "game" && match(g)).sort(sorter);
  const demos = d.owned.filter(g => g.kind === "demo" && match(g)).sort(sorter), tools = d.owned.filter(g => g.kind === "tool" && match(g));
  const recent = q || GM.src !== "all" ? [] : d.owned.filter(g => g.last && g.kind !== "tool").sort((a, b) => b.last - a.last).slice(0, 4);
  const counts = s => d.owned.filter(g => g.kind === "game" && (s === "all" || g.src === s)).length;
  const card = g => `<div class="gcard" title="${esc(g.name)}"><div class="gcover" onclick="gmDetails('${g.id}')">${gmArt(g)}
      <button class="gplay" title="Play" onclick="event.stopPropagation();gmPlay('${g.id}')">${ic("play", "i")}</button><i class="gsrc ${g.src}">${SRC_NAME[g.src]}</i></div>
      <div class="gname" onclick="gmDetails('${g.id}')">${esc(g.name.replace(/[™®]/g, ""))}</div><div class="gmeta">${playedText(g) || gmSize(g.size)}</div></div>`;
  $("#gm-body").innerHTML = `
    ${recent.length ? `<div class="gm-sec"><h4>Jump back in</h4><div class="gm-recent">${recent.map(g => `<div class="grec" onclick="gmDetails('${g.id}')">${gmArt(g, true)}
        <div class="grec-i"><b>${esc(g.name.replace(/[™®]/g, ""))}</b><span>${playedText(g)} · ${SRC_NAME[g.src]}</span></div>
        <button class="btn pri sm" onclick="event.stopPropagation();gmPlay('${g.id}')">${ic("play")}Play</button></div>`).join("")}</div></div>` : ""}
    <div class="gm-sec"><div class="gm-sech"><h4>${q ? `Results for “${esc(GM.q)}”` : "All games"} <span class="muted">${games.length}</span></h4>
      <div class="chips">${["all", "steam", "epic", "free"].filter(s => s === "all" || counts(s)).map(s => `<button class="chipb ${GM.src === s ? "on" : ""}" onclick="GM.src='${s}';gmBody()">${s === "all" ? "All" : SRC_NAME[s]} · ${counts(s)}</button>`).join("")}</div></div>
      <div class="gm-grid">${games.map(card).join("") || `<div class="empty" style="grid-column:1/-1"><b>No games match</b>Try another search${GM.src !== "all" ? " or show All" : ""}.</div>`}</div></div>
    ${demos.length ? `<details class="gm-sec gm-fold"><summary><h4>Demos <span class="muted">${demos.length}</span></h4></summary><div class="gm-grid sm">${demos.map(card).join("")}</div></details>` : ""}
    ${tools.length ? `<details class="gm-sec gm-fold"><summary><h4>Apps & tools <span class="muted">${tools.length}</span></h4></summary><div class="gm-grid sm">${tools.map(card).join("")}</div></details>` : ""}
    <div class="muted small" style="margin:6px 0 20px">Steam and Epic games launch through their own apps with your account. Playing offline: in Steam use <i>Steam → Go Offline…</i> once while online; Epic games you've launched before work offline.</div>`;
}

function gmDetails(id) {
  const g = GM.data.owned.find(x => x.id === id); if (!g) return;
  const free = GM.data.free.find(x => x.id === id);
  modal(`<div class="gdet">${gmArt(g, true)}<button class="iconbtn gdet-x" onclick="closeModal()">${ic("x")}</button></div>
    <h2 style="margin:14px 0 2px">${esc(g.name.replace(/[™®]/g, ""))}</h2>
    <div class="row small muted" style="gap:8px"><span class="badge">${SRC_NAME[g.src]}</span>${g.kind !== "game" ? `<span class="badge">${g.kind}</span>` : ""}${g.size ? `<span>${gmSize(g.size)}</span>` : ""}${g.last ? `<span>${playedText(g)}</span>` : ""}</div>
    ${free ? `<p class="muted" style="margin:10px 0 0">${esc(free.desc)}</p>` : ""}
    <div class="row" style="margin-top:16px;gap:8px"><button class="btn pri lg" onclick="closeModal();gmPlay('${id}')">${ic("play")}Play</button>
      ${g.src === "epic" ? `<button class="btn" title="Start the game's own .exe — for DRM-free games, works with no internet" onclick="closeModal();gmPlay('${id}',true)">Play offline</button>` : ""}
      <button class="btn ghost" onclick="api('/api/games/${id}/folder',{method:'POST'})">${ic("ext")}Game folder</button>
      ${free ? `<div class="sp"></div><button class="btn ghost danger" onclick="gmRemove(this,'${id}')">${ic("trash")}Uninstall</button>` : ""}</div>`, true);
}
async function gmPlay(id, direct) { try { await api(`/api/games/${id}/play`, {method: "POST", body: {direct: !!direct}}); toast("Launching…"); } catch (e) { toast(e.message); } }

function gmFree() {
  const d = GM.data, q = GM.q.toLowerCase();
  const genres = ["All", ...new Set(d.free.map(g => g.genre))];
  const list = d.free.filter(g => (GM.genre === "All" || g.genre === GM.genre) && (!q || (g.name + g.desc + g.genre).toLowerCase().includes(q)));
  const ready = list.filter(g => !g.own), byo = list.filter(g => g.own);
  $("#gm-body").innerHTML = `<div class="muted" style="margin:2px 0 12px">Free, open-source games — downloaded straight from each project's official GitHub release into <code>${esc(d.games_dir)}</code>. Once downloaded they show up in <b>My library</b>.</div>
    <div class="chips" style="margin-bottom:14px">${genres.map(g => `<button class="chipb ${GM.genre === g ? "on" : ""}" onclick="GM.genre='${g}';gmBody()">${g}</button>`).join("")}</div>
    ${ready.length ? `<div class="gm-sec"><h4>Play right away <span class="muted">${ready.length}</span></h4><div class="free-grid">${ready.map(freeCard).join("")}</div></div>` : ""}
    ${byo.length ? `<div class="gm-sec"><h4>Remakes — need files from a game you own <span class="muted">${byo.length}</span></h4>
      <div class="muted small" style="margin:-4px 0 10px">Modern open-source engines for classics. They're free, but you supply the original game's data files.</div><div class="free-grid">${byo.map(freeCard).join("")}</div></div>` : ""}
    ${!list.length ? `<div class="empty"><b>Nothing matches</b></div>` : ""}`;
}
function freeCard(g) {
  const j = g.job, busy = j && ["starting", "downloading", "extracting"].includes(j.state);
  const act = busy ? `<div class="meter" style="flex:1"><i style="width:${j.pct}%"></i></div><span class="small">${j.state === "extracting" ? "Unpacking…" : j.pct + "%"}</span>`
    : g.exe ? `<button class="btn sm pri" onclick="gmPlay('${g.id}')">${ic("play")}Play</button><span class="small" style="color:var(--ok);white-space:nowrap">✓ Installed</span>`
    : g.installer ? `<button class="btn sm pri" onclick="gmPlay('${g.id}')">Finish installing</button><span class="small muted">runs its installer</span>`
    : `<button class="btn sm" onclick="gmDownload('${g.id}')">${ic("down")}Download${g.dl_size ? " · " + gmSize(g.dl_size) : ""}</button>`;
  return `<div class="free"><div class="fcov">${gmArt(g)}</div><div class="fbody"><div class="ft"><b>${esc(g.name)}</b><span class="badge">${esc(g.genre)}</span></div>
    <div class="small muted fdesc">${esc(g.desc)}</div>${g.own ? `<div class="small" style="color:var(--warn)">Needs: ${esc(g.own)}</div>` : ""}
    ${j && j.state === "error" ? `<div class="small" style="color:var(--bad)">${esc(j.msg)}</div>` : ""}
    <div class="row fact">${act}<a class="small muted" style="margin-left:auto" href="https://github.com/${g.repo}" target="_blank" rel="noopener">GitHub ↗</a></div></div></div>`;
}
async function gmDownload(id) { await api(`/api/games/${id}/download`, {method: "POST"}); toast("Downloading…"); renderGames(true); }
async function gmRemove(btn, id) { if (!btn.dataset.sure) { btn.dataset.sure = 1; btn.innerHTML = "Click again to uninstall"; return; } await api(`/api/games/${id}/remove`, {method: "POST"}); closeModal(); toast("Uninstalled"); renderGames(true); }
// home widget: recently played covers
async function gamesWidget() {
  const el = $("#w-games"); if (!el) return;
  if (!GM.data) GM.data = await api("/api/games");
  const all = GM.data.owned.filter(g => g.kind === "game"), list = (all.some(g => g.last) ? all.filter(g => g.last) : all).slice(0, 6);
  el.innerHTML = `<div class="gm-mini">${list.map(g => `<div class="gcard sm" title="Play ${esc(g.name)}"><div class="gcover" onclick="gmPlay('${g.id}')">${gmArt(g)}</div></div>`).join("")}</div>`;
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
