// ================= WORKFLOWS — its own page + Home widget =================
// A workflow opens everything a task needs in one click: folders (in the Files hub), sites and Chrome profiles
// (in Daybook's browser) and apps. The editor picks folders drive-first: choose a drive, then browse into it.
const WF = {pick: {drive: "", path: "", list: null}};
const wfIcon = x => x.type === "folder" ? "📁" : x.type === "app" ? "▶" : x.type === "profile" ? "🌐" : "🔗";
const wfLabel = x => (x.label || x.url || x.path || "").replace(/^\S+\s/, "");
async function wfData(refresh) { if (!FD.data || refresh) FD.data = await api("/api/folders"); return FD.data; }

async function renderWorkflows() {
  const host = $("#wfpage"); if (!host) return;
  const d = await wfData(true);
  host.innerHTML = `<div class="wf-head"><div><h2>Workflows</h2><div class="muted">One click opens every folder, app, profile and site you need for a task.</div></div>
      <div class="sp"></div><button class="btn pri" onclick="wfModal()">${ic("plus")}New workflow</button></div>
    <div class="wf-grid">${d.workflows.map((w, i) => `<div class="wf-card" style="--c:${w.color || FCOL[i % 6]}" data-ctx="workflow" data-i="${i}">
        <div class="wf-top"><b>${esc(w.name)}</b><span class="muted small">${w.items.length} item${w.items.length === 1 ? "" : "s"}</span></div>
        <div class="wf-items">${w.items.slice(0, 6).map(x => `<span class="wf-it" title="${esc(x.path || x.url || x.label)}">${wfIcon(x)} ${esc(wfLabel(x))}</span>`).join("")}${w.items.length > 6 ? `<span class="wf-it muted">+${w.items.length - 6} more</span>` : ""}</div>
        <div class="row" style="margin-top:auto;gap:6px"><button class="btn pri" onclick="wfRun(${i})">${ic("play")}Start</button>
          <button class="btn ghost sm" onclick="wfModal(${i})">${ic("pen")}Edit</button><div class="sp"></div>
          <button class="iconbtn" title="More" onclick="event.stopPropagation();const b=this.getBoundingClientRect();ctxShow(b.left-180,b.bottom+4,CTX.workflow(this.closest('.wf-card')))">${ic("list")}</button></div></div>`).join("")}
      <button class="wf-card wf-new" onclick="wfModal()">${ic("plus", "i")}<b>New workflow</b><span>e.g. “Editing” = your recordings folder + CapCut + YouTube Studio</span></button></div>`;
  paintIcons(host);
}
// Start: folders → Files hub panes, sites/profiles → Daybook's browser / workflow space, apps → launched on the PC
function wfRun(i, forcePrompt) {
  wfData().then(d => {
    const w = d.workflows[i]; if (!w) return;
    const folders = w.items.filter(x => x.type === "folder");
    const web = w.items.filter(x => x.type === "url" || x.type === "profile");
    const savedDest = store.get("daybook-wf-dest", "");
    if (web.length && (!savedDest || forcePrompt)) {
      modal(`<h2>${ic("play", "i")}Start “${esc(w.name)}”<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
        <p class="muted">This workflow opens ${web.length} web page${web.length > 1 ? "s" : ""}${folders.length ? ` and ${folders.length} folder${folders.length > 1 ? "s" : ""}` : ""}. Where would you like the browser pages to open?</p>
        <div class="wf-dest-grid">
          <div class="wf-dest-card" onclick="wfRunExecute(${i}, 'space')">
            <div class="wf-dest-top"><span class="wf-dest-ic">📁 🌐</span><b>In this Workflow space (alongside your files)</b></div>
            <div class="wf-dest-body">Opens your folders in Files, and keeps browser tabs accessible right in the workflow so you don't have to go back and forth.</div>
          </div>
          <div class="wf-dest-card" onclick="wfRunExecute(${i}, 'browser')">
            <div class="wf-dest-top"><span class="wf-dest-ic">🌐</span><b>In Daybook's Browser hub</b></div>
            <div class="wf-dest-body">Opens tabs in Daybook's dedicated browser view with full browsing controls.</div>
          </div>
          <div class="wf-dest-card" onclick="wfRunExecute(${i}, 'window')">
            <div class="wf-dest-top"><span class="wf-dest-ic">🪟</span><b>In a New Daybook Window (recommended for dual screens)</b></div>
            <div class="wf-dest-body">Puts the browser on your second screen or side-by-side while your files stay right here.</div>
          </div>
        </div>
        <div class="row" style="margin-top:14px">
          <label class="row small muted" style="cursor:pointer;gap:6px">
            <input type="checkbox" id="wf-save-dest"> Remember my choice for future workflows
          </label>
        </div>`);
      return;
    }
    wfRunExecute(i, savedDest || "space");
  });
}

async function wfRunExecute(i, dest) {
  const remember = $("#wf-save-dest") && $("#wf-save-dest").checked;
  if (remember) store.set("daybook-wf-dest", dest);
  closeModal();

  const d = await wfData(); const w = d.workflows[i]; if (!w) return;
  const inApp = !!window.desktop;
  const folders = w.items.filter(x => x.type === "folder");
  const web = w.items.filter(x => x.type === "url" || x.type === "profile");
  const j = await api(`/api/workflows/${i}/run`, {method: "POST", body: {hub: inApp}}).catch(e => ({opened: 0, error: e.message}));

  if (inApp) {
    if (dest === "window") {
      if (window.desktop && desktop.newWindow) desktop.newWindow("browser");
      else window.open("/#browser", "_blank");
      for (const x of web) {
        if (x.type === "profile") await bdChromeOpen(x.browser, x.profile);
        else await desktop.browser.open("personal", x.url);
      }
      if (folders.length) {
        LP.view = "folders"; go("launchpad", "folders");
        for (const f of folders) if (!FD.panes.some(p => p.path.toLowerCase() === f.path.toLowerCase())) fdNewPane(f.path);
      }
    } else if (dest === "space") {
      if (folders.length) {
        LP.view = "folders"; go("launchpad", "folders");
        for (const f of folders) if (!FD.panes.some(p => p.path.toLowerCase() === f.path.toLowerCase())) fdNewPane(f.path);
      }
      for (const x of web) {
        if (x.type === "profile") await bdChromeOpen(x.browser, x.profile);
        else await desktop.browser.open("personal", x.url);
      }
      if (folders.length && web.length) {
        FD.activeWorkflow = {name: w.name, web};
        toast(`“${w.name}” started — folders & ${web.length} web page${web.length > 1 ? "s" : ""} active in workflow`);
      } else if (web.length) {
        go("browser");
      }
    } else {
      for (const x of web) {
        if (x.type === "profile") await bdChromeOpen(x.browser, x.profile);
        else await desktop.browser.open("personal", x.url);
      }
      if (folders.length) {
        LP.view = "folders";
        for (const f of folders) if (!FD.panes.some(p => p.path.toLowerCase() === f.path.toLowerCase())) fdNewPane(f.path);
      }
      go("browser");
    }
  } else {
    if (folders.length) {
      LP.view = "folders"; go("launchpad", "folders");
      for (const f of folders) if (!FD.panes.some(p => p.path.toLowerCase() === f.path.toLowerCase())) fdNewPane(f.path);
    }
  }

  const parts = [folders.length && `${folders.length} folder${folders.length > 1 ? "s" : ""}`, web.length && `${web.length} page${web.length > 1 ? "s" : ""}`, (inApp ? j.opened : 0) && `${j.opened} app${j.opened > 1 ? "s" : ""}`].filter(Boolean);
  toast(`Started “${w.name}”${inApp && parts.length ? " — " + parts.join(", ") : ""}`);
}

// ---- editor ----
async function wfModal(i) {
  if (!LP.data) LP.data = await api("/api/launchpad");
  const d = await wfData();
  const w = i !== undefined ? d.workflows[i] : {name: "", items: []};
  window._wf = JSON.parse(JSON.stringify(w.items)); WF.pick = {drive: "", path: "", list: null};
  modal(`<h2>${ic("play", "i")}${i !== undefined ? "Edit" : "New"} workflow<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="frm"><label>Name</label><input class="f" id="wf-n" value="${esc(w.name)}" placeholder="e.g. Editing, Morning uploads, Study"></div>
    <div class="wf-step"><span class="wf-num">1</span><b>Folders</b><span class="muted small">Pick a drive, then open folders and press ＋ to add them</span></div>
    <div id="wf-drives" class="wf-drives"></div><div id="wf-browse"></div>
    <div class="wf-step"><span class="wf-num">2</span><b>Apps &amp; browser profiles</b><span class="muted small">Tap to add — tap again to remove</span></div>
    <div id="wf-pick"></div>
    <div class="wf-step"><span class="wf-num">3</span><b>Websites</b></div>
    <div class="row" style="flex-wrap:nowrap"><input class="f" id="wf-url" placeholder="studio.youtube.com" onkeydown="event.key==='Enter'&&wfAddUrl()"><button class="btn" onclick="wfAddUrl()">${ic("plus")}Add</button></div>
    <div class="wf-step"><span class="wf-num">✓</span><b>This workflow opens</b></div><div id="wf-sel" class="wf-sel"></div>
    <div class="row" style="margin-top:16px"><button class="btn pri" onclick="wfSave(${i ?? -1})">${ic("check")}Save</button>${i !== undefined ? `<div class="sp"></div><button class="btn ghost danger" onclick="wfDel(${i})">${ic("trash")}Delete</button>` : ""}</div>`, true);
  wfDrives(); wfItems(); setTimeout(() => $("#wf-n").focus(), 30);
}
function wfDrives() {
  const d = FD.data, el = $("#wf-drives"); if (!el) return;
  el.innerHTML = d.places.drives.map(v => `<button class="wf-drive ${WF.pick.drive === v.path ? "on" : ""}" onclick="wfBrowse(${fq(v.path)}, true)">${ic("drive")}<span><b>${esc(v.name)} (${v.letter}:)</b>${v.total ? `<i>${gmSize(v.free)} free</i>` : ""}</span></button>`).join("")
    + `<span class="wf-or">or a shortcut:</span>` + [...d.pins, ...d.places.quick].filter((f, k, a) => a.findIndex(y => y.path === f.path) === k).slice(0, 8)
      .map(f => `<button class="chipb" onclick="wfBrowse(${fq(f.path)}, true)">📁 ${esc(f.name)}</button>`).join("");
  paintIcons(el);
}
async function wfBrowse(path, fromTop) {
  try { WF.pick.list = await api("/api/folders/list?path=" + encodeURIComponent(path)); } catch (e) { return toast(e.message); }
  WF.pick.path = WF.pick.list.path; if (fromTop) WF.pick.drive = WF.pick.path.slice(0, 3);
  wfDrives(); wfBrowsePaint();
}
function wfBrowsePaint() {
  const el = $("#wf-browse"), l = WF.pick.list; if (!el || !l) return;
  const has = p => window._wf.some(x => x.type === "folder" && x.path.toLowerCase() === p.toLowerCase());
  const parts = l.path.split("\\").filter(Boolean); let acc = "";
  const crumbs = parts.map(s => { acc += s + "\\"; return `<a href="javascript:void 0" onclick="wfBrowse(${fq(acc)})">${esc(s)}</a>`; }).join(" › ");
  const dirs = l.items.filter(x => x.dir);
  el.innerHTML = `<div class="wf-br"><div class="wf-brh">${l.parent ? `<button class="iconbtn" title="Up" onclick="wfBrowse(${fq(l.parent)})">${ic("up")}</button>` : ""}<div class="crumbs">${crumbs}</div><div class="sp"></div>
      ${has(l.path) ? `<span class="badge" style="color:var(--ok)">✓ Added</span>` : `<button class="btn sm pri" onclick="wfAddFolder(${fq(l.path)})">${ic("plus")}Add this folder</button>`}</div>
    <div class="wf-brl">${dirs.map(x => `<div class="wf-row" ondblclick="wfBrowse(${fq(x.path)})"><span class="wf-open" onclick="wfBrowse(${fq(x.path)})">📁 ${esc(x.name)}</span>
        ${has(x.path) ? `<span class="small" style="color:var(--ok)">✓ added</span>` : `<button class="btn sm ghost" title="Add this folder to the workflow" onclick="wfAddFolder(${fq(x.path)})">${ic("plus")}Add</button>`}
        <button class="iconbtn" title="Open" onclick="wfBrowse(${fq(x.path)})">${ic("right")}</button></div>`).join("") || `<div class="muted small" style="padding:10px">No folders inside — press “Add this folder” above to use this one.</div>`}</div></div>`;
  paintIcons(el);
}
function wfAddFolder(path) {
  if (!window._wf.some(x => x.type === "folder" && x.path.toLowerCase() === path.toLowerCase())) window._wf.push({type: "folder", path, label: "📁 " + fbase(path)});
  wfItems(); wfBrowsePaint();
}
const wfKey = x => x.type + ":" + (x.path || x.id || (x.browser + "/" + x.profile) || x.url);
function wfGroups() {
  return [["Apps", LP.data.pinned.map(a => ({type: "app", id: a.id, label: "▶ " + a.name}))],
    ["Chrome profiles (open inside Daybook)", LP.data.browsers.flatMap(b => b.profiles.map(p => ({type: "profile", browser: b.id, profile: p.id, label: "🌐 " + p.name})))]];
}
function wfToggle(g, k) {
  const x = wfGroups()[g][1][k], at = window._wf.findIndex(y => wfKey(y) === wfKey(x));
  at >= 0 ? window._wf.splice(at, 1) : window._wf.push(x); wfItems();
}
function wfAddUrl() { const u = lpUrl($("#wf-url").value); if (!u) return; window._wf.push({type: "url", url: u, label: "🔗 " + u.replace(/^https?:\/\//, "")}); $("#wf-url").value = ""; wfItems(); }
function wfItems() {
  const on = new Set(window._wf.map(wfKey));
  const pick = $("#wf-pick");
  if (pick) pick.innerHTML = wfGroups().filter(([, xs]) => xs.length).map(([h, xs], g) => `<div class="wf-g"><div class="wf-gh">${h}</div><div class="wf-chips">${xs.map((x, k) => `<button class="chipb ${on.has(wfKey(x)) ? "on" : ""}" onclick="wfToggle(${g},${k})">${on.has(wfKey(x)) ? "✓ " : ""}${esc(x.label)}</button>`).join("")}</div></div>`).join("");
  const sel = $("#wf-sel");
  if (sel) sel.innerHTML = window._wf.map((x, k) => `<span class="tag on" title="${esc(x.path || x.url || "")}">${wfIcon(x)} ${esc(wfLabel(x))} <a href="javascript:void 0" title="Remove" onclick="_wf.splice(${k},1);wfItems();wfBrowsePaint()">✕</a></span>`).join(" ") || `<span class="muted small">Nothing yet — add folders, apps, profiles or sites above</span>`;
}
async function wfSave(i) {
  const name = $("#wf-n").value.trim(); if (!name) { $("#wf-n").focus(); return toast("Give the workflow a name"); }
  if (!window._wf.length) return toast("Add at least one folder, app, profile or website");
  const ws = [...FD.data.workflows]; const w = {...(ws[i] || {}), name, items: window._wf};
  i >= 0 ? (ws[i] = w) : ws.push(w); await api("/api/workflows", {method: "POST", body: {workflows: ws}}); closeModal(); toast(`Saved “${name}”`); wfRefreshAll();
}
async function wfDel(i) { const ws = FD.data.workflows.filter((_, j) => j !== i); await api("/api/workflows", {method: "POST", body: {workflows: ws}}); closeModal(); toast("Workflow deleted"); wfRefreshAll(); }
async function wfDuplicate(i) { const ws = [...FD.data.workflows]; ws.splice(i + 1, 0, {...JSON.parse(JSON.stringify(ws[i])), name: ws[i].name + " (copy)"}); await api("/api/workflows", {method: "POST", body: {workflows: ws}}); toast("Duplicated"); wfRefreshAll(); }
async function wfRefreshAll() {
  await wfData(true);
  if (S.view === "workflows") renderWorkflows();
  if (S.view === "launchpad" && LP.view === "folders") renderFolders();
  workflowsWidget(); foldersWidget && foldersWidget();
}
// ---- Home widget ----
async function workflowsWidget() {
  const el = $("#w-workflows"); if (!el) return;
  const d = await wfData();
  el.innerHTML = d.workflows.length ? d.workflows.slice(0, 6).map((w, i) => `<div class="wfw" style="--c:${w.color || FCOL[i % 6]}"><div class="wfw-i"><b>${esc(w.name)}</b><span>${esc(w.items.map(wfLabel).join(" · ")).slice(0, 70)}</span></div>
      <button class="btn sm pri" onclick="wfRun(${i})">${ic("play")}Start</button></div>`).join("")
    : `<div class="muted small">No workflows yet. <a href="javascript:void 0" onclick="wfModal()">Make one</a> — e.g. your editing folder + CapCut + YouTube Studio in one click.</div>`;
  paintIcons(el);
}
WIDGETS.workflows = {name: "Workflows", icon: "play", desc: "Start a workflow — opens its folders, apps and sites in one click",
  html: () => `<div class="card"><h3>${ic("play")}Workflows<button class="btn sm ghost" onclick="go('workflows')">All</button><button class="btn sm ghost" title="New workflow" onclick="wfModal()">${ic("plus")}</button></h3><div id="w-workflows"></div></div>`,
  after: () => workflowsWidget()};
CTX.workflow = el => { const i = +el.dataset.i; return [{t: "Start", i: "play", run: () => wfRun(i)}, {t: "Edit", i: "pen", run: () => wfModal(i)}, {t: "Duplicate", i: "copy", run: () => wfDuplicate(i)}, "-",
  {t: "Delete", i: "trash", danger: true, run: () => { FD.data.workflows.splice(i, 1); api("/api/workflows", {method: "POST", body: {workflows: FD.data.workflows}}).then(() => { toast("Workflow deleted"); wfRefreshAll(); }); }}]; };

// one time: put the Workflows widget on Home (right after the schedule), for people who had Daybook before it existed
async function wfWidgetOnce() {
  try {
    const h = homeCfg(); if (h.wfWidget || !Array.isArray(h.widgets)) return;
    const ws = h.widgets.filter(w => w.id !== "workflows"), at = ws.findIndex(w => w.id === "schedule" || w.id === "nownext");
    ws.splice(at >= 0 ? at + 1 : 0, 0, {id: "workflows", size: "col"});
    await saveHomeCfg({wfWidget: 1}); await saveLayout(ws);
  } catch (e) {}
}
setTimeout(() => { if (S.settings && S.settings.home !== undefined) wfWidgetOnce(); else setTimeout(wfWidgetOnce, 3000); }, 2500);
