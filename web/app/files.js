// ================= FILES HUB (Launchpad → Folders): folders as panes, like the Browser =================
// Sidebar: workflows, pinned folders, quick places, drives. Stage: 1+ folder panes (tabs / split / grid) you can
// drag around, pop out into their own window, and drag files between — or out to Explorer, Discord, web uploads.
ICONS.folder = "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z";
ICONS.drive = "M3 13h18v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1zM5 13l2-7h10l2 7M17 16h.01";
const FD = {data: null, panes: [], focus: 0, layout: store.get("daybook-fh-layout", "split"), seq: 1, clip: null, poll: null};
const FCOL = ["#8b7bff", "#4fd1ff", "#ff7ac6", "#3ee0a0", "#ffbe5c", "#ff6b81"];
const FICON = e => /\.(png|jpe?g|gif|webp|bmp)$/.test(e) ? "🖼" : /\.(mp4|mkv|mov|webm|avi)$/.test(e) ? "🎬" : /\.(mp3|wav|m4a|flac|ogg)$/.test(e) ? "🎵" : /\.(pdf)$/.test(e) ? "📕" : /\.(txt|md|docx?|odt|rtf)$/.test(e) ? "📄" : /\.(zip|7z|rar)$/.test(e) ? "🗜" : /\.(exe|msi|lnk|bat)$/.test(e) ? "⚙" : /\.(psd|prproj|drp|aep|blend)$/.test(e) ? "🎨" : "📄";
const fq = s => JSON.stringify(s).replace(/"/g, "&quot;");   // a path, safe inside onclick="…"
const fbase = p => p.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || p;
const fdMain = () => !window.desktop || !BD.win || BD.win.main !== false;
function fdSave() {
  if (!fdMain()) return;
  try { localStorage.setItem("daybook-fh-panes", JSON.stringify({panes: FD.panes.map(p => ({path: p.path})), focus: FD.panes.findIndex(p => p.id === FD.focus)})); } catch (e) {}
}
function fdPane(id) { return FD.panes.find(p => p.id === id); }
async function renderFolders(refresh) {
  if (!FD.data || refresh) {
    if (!FD.data && !$("#fh")) $("#lp").innerHTML = `<div class="lp-top">${lpTabs()}<div class="sp"></div><span class="lp-clock" id="lp-clock"></span></div><div class="empty" style="padding-top:8vh"><span class="spin"></span> Opening your folders…</div>`;
    try { FD.data = await api("/api/folders"); } catch (e) { $("#lp").innerHTML = `<div class="lp-top">${lpTabs()}</div><div class="empty"><b>Couldn't load folders</b>${esc(e.message)} <button class="btn sm" onclick="renderFolders(true)">Try again</button></div>`; return; }
    if (S.view !== "launchpad" || LP.view !== "folders") return;  // you moved on while it loaded
  }
  if (window.desktop && !BD.win) try { BD.win = await desktop.info(); } catch (e) {}
  if (!FD.panes.length) {  // restore last session, or a pane passed in the address (#launchpad/folders/<path>)
    const pass = decodeURIComponent(location.hash.split("/")[2] || "");
    let saved = {panes: []}; try { saved = JSON.parse(localStorage.getItem("daybook-fh-panes") || "{}"); } catch (e) {}
    const paths = pass ? [pass] : (saved.panes || []).map(p => p.path).filter(Boolean).slice(0, 6);
    for (const p of paths) FD.panes.push({id: FD.seq++, path: p, hist: [p], hi: 0, sel: new Set(), q: "", list: null});
    FD.focus = (FD.panes[Math.max(0, saved.focus || 0)] || FD.panes[0] || {}).id || 0;
  }
  const d = FD.data;
  $("#lp").innerHTML = `<div class="lp-top">${lpTabs()}<div class="sp"></div><span class="lp-clock" id="lp-clock"></span></div>
    <div class="fh" id="fh">
      <aside class="fh-side">
        <button class="fh-wflink" onclick="go('workflows')">${ic("play")}<span><b>Workflows</b>${d.workflows.length ? `${d.workflows.length} ready — open everything for a task in one click` : "Open your folders, apps and sites together in one click"}</span>${ic("right")}</button>
        <div class="fh-h">Pinned<button class="iconbtn" title="Pin a folder" onclick="fdPick()">${ic("plus")}</button></div>
        ${d.pins.map((f, i) => `<div class="fh-place" data-ctx="place" data-path="${esc(f.path)}" data-pin="${i}" data-drop="${esc(f.path)}" onclick="fdGo(${fq(f.path)}, event)" title="${esc(f.path)}\nClick: open here · Ctrl+click: new pane · drop files here to move them"><span class="fh-dot" style="background:${f.color || FCOL[i % 6]}"></span>${esc(f.name)}</div>`).join("")
          || `<div class="muted small" style="padding:2px 10px 6px">Pin folders you use every day — right-click any folder, or press + .</div>`}
        <div class="fh-h">This PC</div>
        ${d.places.quick.map(f => `<div class="fh-place" data-ctx="place" data-path="${esc(f.path)}" data-drop="${esc(f.path)}" onclick="fdGo(${fq(f.path)}, event)" title="${esc(f.path)}">${ic("folder")}${esc(f.name)}</div>`).join("")}
        ${d.places.drives.map(v => `<div class="fh-place" data-ctx="place" data-path="${esc(v.path)}" data-drop="${esc(v.path)}" onclick="fdGo(${fq(v.path)}, event)" title="${esc(v.name)} (${v.letter}:)${v.total ? ` — ${gmSize(v.free)} free of ${gmSize(v.total)}` : ""}">${ic("drive")}<span>${esc(v.name)} <span class="muted">(${v.letter}:)</span></span>${v.total ? `<i class="fh-bar"><i style="width:${Math.round(100 - v.free / v.total * 100)}%"></i></i>` : ""}</div>`).join("")}
      </aside>
      <section class="fh-main">
        <div class="fh-top"><div class="fh-tabs" id="fh-tabs"></div><div class="sp"></div>
          <div class="seg sm">${[["tabs", "Tabs"], ["split", "Split"], ["grid", "Grid"]].map(([k, l]) => `<button class="${FD.layout === k ? "on" : ""}" onclick="fdLayout('${k}')">${l}</button>`).join("")}</div>
          <button class="btn sm" title="Open another folder pane (Ctrl+T)" onclick="fdNewPane()">${ic("plus")}Pane</button></div>
        <div class="fh-stage" id="fh-stage"></div>
      </section>
    </div>`;
  paintIcons($("#lp")); lpClock(); fdSize(); fdPaint();
  $$("#fh .fh-place[data-drop]").forEach(fdDropTarget);
  clearInterval(FD.poll); FD.poll = setInterval(fdAutoRefresh, 4000);
}
function fdSize() { const h = $("#fh"); if (h) h.style.height = Math.max(380, innerHeight - h.getBoundingClientRect().top - 18) + "px"; }
addEventListener("resize", () => fdSize());
function fdLayout(l) { FD.layout = l; store.set("daybook-fh-layout", l); renderFolders(); }
function fdNewPane(path) {
  const start = path || (fdPane(FD.focus) || {}).path || (FD.data.pins[0] || FD.data.places.quick[0] || {}).path || "C:\\";
  const p = {id: FD.seq++, path: start, hist: [start], hi: 0, sel: new Set(), q: "", list: null};
  FD.panes.push(p); FD.focus = p.id; fdSave(); fdPaint();
}
function fdClosePane(id) { FD.panes = FD.panes.filter(p => p.id !== id); if (FD.focus === id) FD.focus = (FD.panes[FD.panes.length - 1] || {}).id || 0; fdSave(); fdPaint(); }
// open a folder: in the focused pane, or a new pane with Ctrl/middle click (or when there is none yet)
function fdGo(path, e) {
  if (S.view !== "launchpad" || LP.view !== "folders") { LP.view = "folders"; go("launchpad", "folders"); }
  const p = fdPane(FD.focus);
  if (!p || (e && (e.ctrlKey || e.metaKey || e.button === 1))) return fdNewPane(path);
  fdNav(p.id, path);
}
async function fdNav(id, path, fromHist) {
  const p = fdPane(id); if (!p) return;
  try { p.list = await api("/api/folders/list?path=" + encodeURIComponent(path)); }
  catch (e) { toast(e.message || "Can't open that folder"); return; }
  if (!fromHist) { p.hist = p.hist.slice(0, p.hi + 1); if (p.hist[p.hi] !== p.list.path) p.hist.push(p.list.path); p.hi = p.hist.length - 1; }
  p.path = p.list.path; p.sel = new Set(); p.q = ""; p.anchor = null; FD.focus = id; fdSave(); fdPaint();
}
function fdBack(id) { const p = fdPane(id); if (p && p.hi > 0) { p.hi--; fdNav(id, p.hist[p.hi], true); } }
function fdFwd(id) { const p = fdPane(id); if (p && p.hi < p.hist.length - 1) { p.hi++; fdNav(id, p.hist[p.hi], true); } }
function fdUp(id) { const p = fdPane(id); if (p && p.list && p.list.parent) fdNav(id, p.list.parent); }
async function fdReload(id) { const p = fdPane(id); if (!p) return; try { p.list = await api("/api/folders/list?path=" + encodeURIComponent(p.path)); } catch (e) { p.list = {path: p.path, items: [], total: 0, error: e.message}; } fdPaintPane(p); }
async function fdAutoRefresh() {  // new downloads, renders, exports… show up without pressing anything
  if (S.view !== "launchpad" || LP.view !== "folders" || document.hidden || FD.dragging || $(".fr input")) return;
  for (const p of fdShown()) {
    try { const l = await api("/api/folders/list?path=" + encodeURIComponent(p.path)); if (JSON.stringify(l.items) !== JSON.stringify((p.list || {}).items)) { p.list = l; fdPaintPane(p); } } catch (e) {}
  }
}
const fdShown = () => FD.layout === "tabs" ? FD.panes.filter(p => p.id === FD.focus) : FD.panes;
function fdPaint() {
  const st = $("#fh-stage"); if (!st) return;
  if (!fdPane(FD.focus)) FD.focus = (FD.panes[0] || {}).id || 0;
  $("#fh-tabs").innerHTML = FD.panes.map(p => `<div class="fh-tab ${p.id === FD.focus ? "on" : ""}" draggable="true" data-pane="${p.id}" data-ctx="pane" onclick="FD.focus=${p.id};fdPaint()" title="${esc(p.path)}">${ic("folder")}<span>${esc(fbase(p.path))}</span><button title="Close" onclick="event.stopPropagation();fdClosePane(${p.id})">${ic("x")}</button></div>`).join("");
  paintIcons($("#fh-tabs"));
  $$("#fh-tabs .fh-tab").forEach(fdPaneDrag);
  const shown = fdShown();
  st.className = "fh-stage " + (FD.layout === "grid" && shown.length > 2 ? "grid" : FD.layout === "tabs" ? "tabs" : "split");
  st.style.setProperty("--n", shown.length);
  if (!FD.panes.length) {
    st.innerHTML = `<div class="empty fh-start"><b>Open a folder</b>Pick one on the left, or start with one of these. Open more side by side and drag files between them.
      <div class="row" style="justify-content:center;margin-top:14px;gap:8px">${[...FD.data.pins, ...FD.data.places.quick].slice(0, 6).map(f => `<button class="btn" onclick="fdNewPane(${fq(f.path)})">${ic("folder")}${esc(f.name)}</button>`).join("")}</div></div>`;
    paintIcons(st); return;
  }
  st.querySelector(".fh-start") && st.querySelector(".fh-start").remove();
  const keep = new Set(shown.map(p => String(p.id)));
  st.querySelectorAll(".fp").forEach(el => { if (!keep.has(el.dataset.pane)) el.remove(); });
  shown.forEach((p, i) => {
    let el = st.querySelector(`.fp[data-pane="${p.id}"]`);
    if (!el) { el = document.createElement("div"); el.className = "fp"; el.dataset.pane = p.id; st.appendChild(el); fdPaneEvents(el, p); }
    el.style.order = i;
    el.classList.toggle("on", p.id === FD.focus && shown.length > 1);
    if (!p.list) fdReload(p.id); else fdPaintPane(p);
  });
}
function fdPaintPane(p) {
  const el = $(`.fp[data-pane="${p.id}"]`); if (!el) return;
  const l = p.list || {path: p.path, items: [], total: 0};
  const q = p.q.toLowerCase(), items = l.items.filter(x => x.name.toLowerCase().includes(q));
  const parts = l.path.split("\\").filter(Boolean); let acc = "";
  const crumbs = parts.map(s => { acc += s + "\\"; return `<a href="javascript:void 0" data-drop="${esc(acc)}" onclick="fdNav(${p.id},${fq(acc)})">${esc(s)}</a>`; }).join(`<span class="muted">›</span>`);
  const scroll = el.querySelector(".fp-list") ? el.querySelector(".fp-list").scrollTop : 0;
  el.innerHTML = `<div class="fp-h" draggable="true" title="Drag this bar onto another pane to swap them">
      <button class="iconbtn" title="Back (Alt+←)" ${p.hi > 0 ? "" : "disabled"} onclick="fdBack(${p.id})">${ic("left")}</button>
      <button class="iconbtn" title="Forward (Alt+→)" ${p.hi < p.hist.length - 1 ? "" : "disabled"} onclick="fdFwd(${p.id})">${ic("right")}</button>
      <button class="iconbtn" title="Up a folder (Alt+↑)" ${l.parent ? "" : "disabled"} onclick="fdUp(${p.id})">${ic("up")}</button>
      <div class="fp-crumbs" title="Click empty space to type a path" onclick="if(event.target===this)fdEditPath(${p.id})">${crumbs}</div>
      <input class="fp-q" placeholder="Filter" value="${esc(p.q)}" oninput="fdPane(${p.id}).q=this.value;debounce('fq${p.id}',()=>fdPaintPane(fdPane(${p.id})),120)">
      <button class="iconbtn" title="More" onclick="fdPaneMenu(event,${p.id})">${ic("list")}</button>
      ${FD.panes.length > 1 ? `<button class="iconbtn" title="Close pane" onclick="fdClosePane(${p.id})">${ic("x")}</button>` : ""}</div>
    <div class="fp-list" tabindex="0" data-drop="${esc(l.path)}" data-ctx="folderbg">
      ${l.error ? `<div class="empty"><b>Can't open this folder</b>${esc(l.error)}</div>` : items.map(x => `<div class="fr ${p.sel.has(x.path) ? "sel" : ""}" draggable="true" data-ctx="file" data-path="${esc(x.path)}"${x.dir ? ` data-drop="${esc(x.path)}"` : ""}>
        <span class="fic">${x.dir ? "📁" : /\.(png|jpe?g|gif|webp)$/.test(x.ext) ? `<img src="/api/folders/thumb?path=${encodeURIComponent(x.path)}" loading="lazy" alt="">` : FICON(x.ext)}</span>
        <span class="fn" title="${esc(x.name)}">${esc(x.name)}</span><span class="fs">${x.dir ? "" : gmSize(x.size).replace(/^0 MB$/, "<1 MB")}</span><span class="fm">${dayName(x.modified)}</span></div>`).join("")
        || `<div class="empty">${q ? "Nothing matches the filter" : "This folder is empty — drop files here"}</div>`}</div>
    <div class="fp-foot"><span>${items.length}${l.total > l.items.length ? " of " + l.total : ""} item${items.length === 1 ? "" : "s"}${p.sel.size ? ` · <b>${p.sel.size} selected</b>` : ""}</span><span class="sp"></span><span class="muted">Double-click to open · drag to move (Ctrl = copy) · right-click for more</span></div>`;
  paintIcons(el);
  el.querySelector(".fp-list").scrollTop = scroll;
  el.querySelectorAll("[data-drop]").forEach(fdDropTarget);
  const h = el.querySelector(".fp-h"); h.addEventListener("dragstart", e => { if (e.target !== h) return; e.dataTransfer.setData("x-daybook-pane", p.id); e.dataTransfer.effectAllowed = "move"; });
}
function fdPaneEvents(el, p) {  // events on the pane box survive repaints (the inside is re-rendered)
  el.addEventListener("mousedown", () => { if (FD.focus !== p.id) { FD.focus = p.id; $$(".fp").forEach(x => x.classList.toggle("on", +x.dataset.pane === p.id && fdShown().length > 1)); $$(".fh-tab").forEach(t => t.classList.toggle("on", +t.dataset.pane === p.id)); fdSave(); } });
  el.addEventListener("click", e => {
    const r = e.target.closest(".fr"); if (!r || e.target.closest("button,input")) return;
    const path = r.dataset.path, rows = [...el.querySelectorAll(".fr")].map(x => x.dataset.path);
    if (e.shiftKey && p.anchor) { const a = rows.indexOf(p.anchor), b = rows.indexOf(path); p.sel = new Set(rows.slice(Math.min(a, b), Math.max(a, b) + 1)); }
    else if (e.ctrlKey || e.metaKey) { p.sel.has(path) ? p.sel.delete(path) : p.sel.add(path); p.anchor = path; }
    else { p.sel = new Set([path]); p.anchor = path; }
    fdMarkSel(el, p);
  });
  el.addEventListener("click", e => { if (e.target.classList.contains("fp-list")) { p.sel.clear(); fdMarkSel(el, p); } });
  el.addEventListener("dblclick", e => { const r = e.target.closest(".fr"); if (r) fdOpenItem(p.id, r.dataset.path); });
  el.addEventListener("dragstart", e => {
    const r = e.target.closest(".fr"); if (!r) return;
    if (!p.sel.has(r.dataset.path)) { p.sel = new Set([r.dataset.path]); fdMarkSel(el, p); }
    const paths = [...p.sel];
    FD.dragging = {paths, from: p.path};
    if (window.desktop && desktop.files) { e.preventDefault(); desktop.files.startDrag(paths); setTimeout(() => FD.dragging = null, 400); return; }  // real files: drop anywhere
    e.dataTransfer.setData("x-daybook-paths", JSON.stringify(paths)); e.dataTransfer.setData("text/plain", paths.join("\n")); e.dataTransfer.effectAllowed = "copyMove";
  });
  el.addEventListener("dragend", () => FD.dragging = null);
  el.addEventListener("dragover", e => { if (e.dataTransfer.types.includes("x-daybook-pane")) { e.preventDefault(); el.classList.add("swap"); } });
  el.addEventListener("dragleave", e => { if (!el.contains(e.relatedTarget)) el.classList.remove("swap"); });
  el.addEventListener("drop", e => {
    el.classList.remove("swap");
    const from = +e.dataTransfer.getData("x-daybook-pane"); if (!from || from === p.id) return;
    e.preventDefault(); const a = FD.panes.findIndex(x => x.id === from), b = FD.panes.findIndex(x => x.id === p.id);
    [FD.panes[a], FD.panes[b]] = [FD.panes[b], FD.panes[a]]; fdSave(); fdPaint();
  });
}
function fdMarkSel(el, p) {
  el.querySelectorAll(".fr").forEach(r => r.classList.toggle("sel", p.sel.has(r.dataset.path)));
  const f = el.querySelector(".fp-foot span"); if (f) { const n = el.querySelectorAll(".fr").length; f.innerHTML = `${n} item${n === 1 ? "" : "s"}${p.sel.size ? ` · <b>${p.sel.size} selected</b>` : ""}`; }
}
function fdPaneDrag(t) {  // reorder tabs by dragging
  t.addEventListener("dragstart", e => { e.dataTransfer.setData("x-daybook-pane", t.dataset.pane); e.dataTransfer.effectAllowed = "move"; });
  t.addEventListener("dragover", e => { if (e.dataTransfer.types.includes("x-daybook-pane")) { e.preventDefault(); t.classList.add("swap"); } });
  t.addEventListener("dragleave", () => t.classList.remove("swap"));
  t.addEventListener("drop", e => {
    t.classList.remove("swap"); const from = +e.dataTransfer.getData("x-daybook-pane"), to = +t.dataset.pane; if (!from || from === to) return;
    e.preventDefault(); const a = FD.panes.findIndex(x => x.id === from), [m] = FD.panes.splice(a, 1); FD.panes.splice(FD.panes.findIndex(x => x.id === to), 0, m); fdSave(); fdPaint();
  });
}
// any element with data-drop="<folder>" accepts files: from other panes, Explorer, the desktop…
function fdDropTarget(t) {
  if (t._drop) return; t._drop = 1;
  const ok = e => e.dataTransfer.types.includes("Files") || e.dataTransfer.types.includes("x-daybook-paths");
  t.addEventListener("dragover", e => {
    if (!ok(e)) return; e.preventDefault(); e.stopPropagation();
    const into = t.dataset.drop, from = FD.dragging && FD.dragging.from;
    e.dataTransfer.dropEffect = e.ctrlKey || (from && from.slice(0, 2).toLowerCase() !== into.slice(0, 2).toLowerCase()) ? "copy" : "move";
    $$(".drop-on").forEach(x => x !== t && x.classList.remove("drop-on")); t.classList.add("drop-on");
  });
  t.addEventListener("dragleave", e => { if (!t.contains(e.relatedTarget)) t.classList.remove("drop-on"); });
  t.addEventListener("drop", async e => {
    if (!ok(e)) return; e.preventDefault(); e.stopPropagation(); t.classList.remove("drop-on");
    let paths = [];
    try { paths = JSON.parse(e.dataTransfer.getData("x-daybook-paths") || "[]"); } catch (x) {}
    if (!paths.length && window.desktop && desktop.files) paths = [...e.dataTransfer.files].map(f => desktop.files.pathFor(f)).filter(Boolean);
    if (!paths.length) return toast("Those files can't be moved from here");
    const dest = t.dataset.drop, sameDrive = paths[0].slice(0, 2).toLowerCase() === dest.slice(0, 2).toLowerCase();
    fdOp(e.ctrlKey || !sameDrive ? "copy" : "move", paths, dest);
  });
}
async function fdOp(op, paths, dest, name) {
  try {
    const j = await api("/api/folders/op", {method: "POST", body: {op, paths, dest, name}});
    const n = j.done.length, what = n === 1 ? `“${fbase(j.done[0])}”` : `${n} items`;
    if (op === "move" || op === "copy") toast(n ? `${op === "move" ? "Moved" : "Copied"} ${what} to ${fbase(dest)}` : "Already there");
    else if (op === "delete") toast(`Moved ${what} to the Recycle Bin`);
    else if (op === "mkdir") toast("Folder created");
    for (const p of FD.panes) if (p.list) await fdReload(p.id);
    return j.done;
  } catch (e) { toast(e.message); return []; }
}
function fdOpenItem(id, path) {
  const p = fdPane(id), x = p && p.list && p.list.items.find(i => i.path === path);
  if (x && x.dir) fdNav(id, path); else fdOpen(path);
}
function fdOpen(path, reveal) { api("/api/folders/open", {method: "POST", body: {path, reveal: !!reveal}}).catch(e => toast(e.message)); }
function fdEditPath(id) {
  const p = fdPane(id), c = $(`.fp[data-pane="${id}"] .fp-crumbs`); if (!c) return;
  c.innerHTML = `<input class="fp-path" value="${esc(p.path)}" spellcheck="false">`; const i = c.querySelector("input"); i.focus(); i.select();
  i.onkeydown = e => { if (e.key === "Enter") fdNav(id, i.value.trim().replace(/^"|"$/g, "")); if (e.key === "Escape") fdPaintPane(p); };
  i.onblur = () => setTimeout(() => fdPaintPane(p), 150);
}
function fdRename(id, path) {
  const r = $(`.fp[data-pane="${id}"] .fr[data-path="${CSS.escape(path)}"] .fn`); if (!r) return;
  const old = fbase(path); r.innerHTML = `<input class="fp-ren" value="${esc(old)}" spellcheck="false">`; const i = r.querySelector("input"); i.focus();
  const dot = old.lastIndexOf("."); i.setSelectionRange(0, dot > 0 && !(fdPane(id).list.items.find(x => x.path === path) || {}).dir ? dot : old.length);
  let done = false; const finish = save => { if (done) return; done = true; const v = i.value.trim(); if (save && v && v !== old) fdOp("rename", [path], "", v); else fdPaintPane(fdPane(id)); };
  i.onkeydown = e => { e.stopPropagation(); if (e.key === "Enter") finish(true); if (e.key === "Escape") finish(false); };
  i.onblur = () => finish(true); i.onclick = e => e.stopPropagation(); i.ondblclick = e => e.stopPropagation();
}
async function fdNewFolder(id) { const p = fdPane(id); const [made] = await fdOp("mkdir", [], p.path, "New folder"); if (made) setTimeout(() => fdRename(id, made), 150); }
function fdDelete(id, paths) { if (paths.length) fdOp("delete", paths); }
function fdCopyPaths(paths) { navigator.clipboard.writeText(paths.join("\r\n")).then(() => toast(paths.length > 1 ? "Paths copied" : "Path copied")); }
function fdClip(cut, paths) { if (!paths.length) return; FD.clip = {cut, paths}; toast(`${cut ? "Cut" : "Copied"} ${paths.length} item${paths.length === 1 ? "" : "s"} — paste in any pane (Ctrl+V)`); }
function fdPaste(id) { const p = fdPane(id); if (!FD.clip || !p) return toast("Nothing to paste — copy or cut files first"); const c = FD.clip; if (c.cut) FD.clip = null; fdOp(c.cut ? "move" : "copy", c.paths, p.path); }
function fdPopOut(id) {
  const p = fdPane(id); if (!p) return;
  if (window.desktop) { desktop.newWindow("launchpad/folders/" + encodeURIComponent(p.path)); if (FD.panes.length > 1) fdClosePane(id); }
  else open("/#launchpad/folders/" + encodeURIComponent(p.path), "_blank");
}
function fdPinPath(path) { fdPin(path); }
function fdPaneMenu(e, id) {
  e.stopPropagation(); const p = fdPane(id); const r = e.currentTarget.getBoundingClientRect();
  ctxShow(r.left, r.bottom + 4, fdFolderItems(id, p.path));
}
function fdFolderItems(id, path) {
  return [{t: "New folder", i: "plus", run: () => fdNewFolder(id)},
    {t: "Paste", i: "copy", k: "Ctrl V", off: !FD.clip, run: () => fdPaste(id)},
    {t: "Refresh", i: "rep", k: "F5", run: () => fdReload(id)}, "-",
    {t: "Pin this folder", i: "plus", off: FD.data.pins.some(f => f.path.toLowerCase() === path.toLowerCase()), run: () => fdPin(path)},
    {t: "Open in File Explorer", i: "ext", run: () => fdOpen(path)},
    {t: "Copy folder path", i: "copy", run: () => fdCopyPaths([path])},
    {t: "Open in a new pane", i: "plus", run: () => fdNewPane(path)},
    window.desktop ? {t: "Pop out into its own window", i: "expand", run: () => fdPopOut(id)} : null, "-",
    {t: "Close pane", i: "x", off: FD.panes.length < 2, run: () => fdClosePane(id)}].filter(Boolean);
}
// keyboard, Explorer-style, while a pane has focus
document.addEventListener("keydown", e => {
  if (S.view !== "launchpad" || LP.view !== "folders" || $("#scrim").classList.contains("on")) return;
  if (e.target.closest && e.target.closest("input,textarea,[contenteditable]")) return;
  if (e.altKey && !/^Arrow/.test(e.key)) return;  // Alt+letters are Daybook's page shortcuts
  if (e.target !== document.body && !(e.target.closest && e.target.closest("#fh"))) return;  // focus is elsewhere (a button, a menu…)
  const p = fdPane(FD.focus); if (!p) { if (e.ctrlKey && e.key.toLowerCase() === "t") { e.preventDefault(); fdNewPane(); } return; }
  const sel = [...p.sel], k = e.key, ctl = e.ctrlKey || e.metaKey;
  const act = {
    Delete: () => fdDelete(p.id, sel), F2: () => sel[0] && fdRename(p.id, sel[0]), F5: () => fdReload(p.id),
    Enter: () => sel.forEach(s => fdOpenItem(p.id, s)), Backspace: () => fdBack(p.id),
  }[k];
  if (act) { e.preventDefault(); return act(); }
  if (e.altKey && k === "ArrowLeft") { e.preventDefault(); fdBack(p.id); }
  else if (e.altKey && k === "ArrowRight") { e.preventDefault(); fdFwd(p.id); }
  else if (e.altKey && k === "ArrowUp") { e.preventDefault(); fdUp(p.id); }
  else if (ctl && k.toLowerCase() === "a") { e.preventDefault(); p.sel = new Set((p.list.items || []).filter(x => x.name.toLowerCase().includes(p.q.toLowerCase())).map(x => x.path)); fdMarkSel($(`.fp[data-pane="${p.id}"]`), p); }
  else if (ctl && k.toLowerCase() === "c") { e.preventDefault(); fdClip(false, sel); }
  else if (ctl && k.toLowerCase() === "x") { e.preventDefault(); fdClip(true, sel); }
  else if (ctl && k.toLowerCase() === "v") { e.preventDefault(); fdPaste(p.id); }
  else if (ctl && k.toLowerCase() === "t") { e.preventDefault(); fdNewPane(); }
  else if (ctl && k.toLowerCase() === "w" && FD.panes.length > 1) { e.preventDefault(); fdClosePane(p.id); }
});
// pinned folders
async function fdPick() {
  toast("Choose a folder in the window that just opened (check your taskbar if you don't see it)…");
  const j = await api("/api/folders/pick", {method: "POST"}); if (j.path) fdPin(j.path);
}
async function fdPin(path, name) {
  if (FD.data.pins.some(f => f.path.toLowerCase() === path.toLowerCase())) return toast("Already pinned");
  const pins = [...FD.data.pins, {path, name: name || fbase(path)}]; await api("/api/folders/pins", {method: "POST", body: {pins}}); toast(`Pinned “${name || fbase(path)}”`);
  FD.data = null; if (S.view === "launchpad" && LP.view === "folders") renderFolders(true); else FD.data = await api("/api/folders");
}
async function fdUnpin(i) { const pins = FD.data.pins.filter((_, j) => j !== i); await api("/api/folders/pins", {method: "POST", body: {pins}}); toast("Unpinned"); renderFolders(true); }
async function fdRenamePin(i) {
  const f = FD.data.pins[i]; const n = prompt("Name for this pinned folder", f.name); if (!n) return;
  const pins = FD.data.pins.map((x, j) => j === i ? {...x, name: n.trim()} : x); await api("/api/folders/pins", {method: "POST", body: {pins}}); renderFolders(true);
}
async function foldersWidget() {
  const el = $("#w-folders"); if (!el) return;
  if (!FD.data) FD.data = await api("/api/folders");
  el.innerHTML = (FD.data.workflows.length ? `<div class="row" style="gap:6px;margin-bottom:8px">${FD.data.workflows.map((w, i) => `<button class="chipb" onclick="wfRun(${i})">▶ ${esc(w.name)}</button>`).join("")}</div>` : "")
    + (FD.data.pins.slice(0, 6).map(f => `<div class="cat" onclick="fdGo(${fq(f.path)})" title="Open in Daybook's Files">📁 <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(f.name)}</span><span class="c">${ic("right")}</span></div>`).join("")
    || `<div class="muted small">No folders pinned — <a href="javascript:void 0" onclick="go('launchpad','folders')">add some</a>.</div>`);
}

// ---- right-click items for files, places, panes and workflows (used by ctx.js) ----
CTX.file = el => {
  const pane = el.closest(".fp"), id = +pane.dataset.pane, p = fdPane(id), path = el.dataset.path;
  if (!p.sel.has(path)) { p.sel = new Set([path]); p.anchor = path; fdMarkSel(pane, p); }
  const sel = [...p.sel], x = (p.list.items || []).find(i => i.path === path) || {}, many = sel.length > 1;
  return [many ? {h: `${sel.length} items`} : null,
    x.dir ? {t: "Open", i: "folder", run: () => fdNav(id, path)} : {t: "Open", i: "play", run: () => sel.forEach(s => fdOpen(s))},
    x.dir ? {t: "Open in a new pane", i: "plus", run: () => fdNewPane(path)} : null,
    x.dir ? {t: "Pin to sidebar", i: "plus", run: () => fdPin(path)} : null,
    {t: "Show in File Explorer", i: "ext", run: () => fdOpen(path, true)}, "-",
    {t: "Cut", i: "copy", k: "Ctrl X", run: () => fdClip(true, sel)},
    {t: "Copy", i: "copy", k: "Ctrl C", run: () => fdClip(false, sel)},
    {t: "Copy path", i: "copy", run: () => fdCopyPaths(sel)},
    FD.panes.length > 1 ? {t: "Move to other pane", i: "right", sub: FD.panes.filter(o => o.id !== id).map(o => ({t: fbase(o.path), i: "folder", run: () => fdOp("move", sel, o.path)}))} : null,
    FD.panes.length > 1 ? {t: "Copy to other pane", i: "copy", sub: FD.panes.filter(o => o.id !== id).map(o => ({t: fbase(o.path), i: "folder", run: () => fdOp("copy", sel, o.path)}))} : null, "-",
    !many ? {t: "Rename", i: "pen", k: "F2", run: () => fdRename(id, path)} : null,
    !x.dir && !many && typeof discordSend === "function" ? {t: "Send to Discord", i: "send", run: () => discordSend("file", path)} : null,
    {t: "Delete", i: "trash", k: "Del", danger: true, run: () => fdDelete(id, sel)}].filter(Boolean);
};
CTX.folderbg = el => { const id = +el.closest(".fp").dataset.pane; return fdFolderItems(id, fdPane(id).path); };
CTX.pane = el => { const id = +el.dataset.pane; return fdFolderItems(id, fdPane(id).path); };
CTX.place = el => {
  const path = el.dataset.path, i = el.dataset.pin;
  return [{t: "Open here", i: "folder", run: () => fdGo(path)}, {t: "Open in a new pane", i: "plus", run: () => fdNewPane(path)},
    {t: "Open in File Explorer", i: "ext", run: () => fdOpen(path)}, {t: "Copy path", i: "copy", run: () => fdCopyPaths([path])}, "-",
    i !== undefined ? {t: "Rename pin", i: "pen", run: () => fdRenamePin(+i)} : {t: "Pin to sidebar", i: "plus", run: () => fdPin(path)},
    i !== undefined ? {t: "Unpin", i: "x", danger: true, run: () => fdUnpin(+i)} : null].filter(Boolean);
};
