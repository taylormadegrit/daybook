// ================= CHAT → TERMINAL (Orca-style): real shells + Claude / Gemini / local AI CLIs, Emacs and Orca =================
// The terminal runs in Daybook's desktop app (node-pty + ConPTY); this page only draws it (xterm.js, bundled offline).
// Sessions live in the app, not the page: if the page reloads they keep running and are reattached with their recent output.
// Layout: tabs along the top; a tab can hold up to 4 split panes. "Workspace" view adds the Projects sidebar and fills Chat.
const TM = {tabs: [], groups: [], active: 0, open: store.get("daybook-term-open", "0") === "1", h: +store.get("daybook-term-h", "320"),
  work: store.get("daybook-term-work", "0") === "1", bound: false, projects: [], filter: "", restored: false};
const termOk = () => !!(window.desktop && desktop.term);
const T_ICON = {claude: ["✳", "#d97757"], gemini: ["✦", "#6aa8ff"], ollama: ["◆", "#3ee0a0"], "ai-stack": ["⚡", "#f7b731"], pwsh: [">_", "#9aa4b2"], cmd: ["C:", "#9aa4b2"],
  bash: ["$", "#98c379"], wsl: ["λ", "#e5c07b"], emacs: ["e", "#c678dd"], orca: ["◒", "#56b6c2"], arcade: ["🎮", "#ffbe5c"]};
const termIcon = p => { const [g, c] = T_ICON[p] || T_ICON.pwsh; return `<span class="t-ico" style="color:${c}">${g}</span>`; };
function termTheme() {  // Orca's terminal colors (One Dark)
  return {background: "#282c34", foreground: "#dcdfe4", cursor: "#dcdfe4", cursorAccent: "#282c34", selectionBackground: "rgba(97,175,239,.32)",
    black: "#3f4451", red: "#e06c75", green: "#98c379", yellow: "#e5c07b", blue: "#61afef", magenta: "#c678dd", cyan: "#56b6c2", white: "#d7dae0",
    brightBlack: "#5c6370", brightRed: "#ff7a85", brightGreen: "#b5e890", brightYellow: "#ffd58a", brightBlue: "#7dc4ff", brightMagenta: "#de8ef5", brightCyan: "#6fd3e0", brightWhite: "#ffffff"};
}
const termAge = ms => { const m = Math.round((Date.now() - ms) / 60000); return m < 1 ? "now" : m < 60 ? m + "m" : m < 1440 ? Math.round(m / 60) + "h" : Math.round(m / 1440) + "d"; };
const termGroupOf = id => TM.groups.find(g => g.ids.includes(id));
const termActiveTab = () => TM.tabs[TM.active];
const termSaveLayout = () => store.set("daybook-term-layout", JSON.stringify(TM.groups.map(g => ({ids: g.ids, dir: g.dir}))));

// ---------- the panel ----------
function termEnsureUI() {
  const main = $("#v-chat .cmain"); if (!main || $("#tpanel")) return;
  if (!$("#t-term")) $("#v-chat .cbar").insertAdjacentHTML("beforeend", `<button class="btn sm t-open" id="t-term" onclick="termToggle()" title="Terminal (Ctrl+\`)"><span class="t-ico">&gt;_</span>Terminal</button>`);
  $("#v-chat .compose").insertAdjacentHTML("afterend", `<div class="t-reopen" id="t-reopen" onclick="termToggle(true)" title="Open the terminal (Ctrl+\`)"><span class="t-ico">&gt;_</span><b>Terminal</b><span id="t-reopen-n"></span><span class="sp"></span><span class="muted">Ctrl+\`</span>${ic("up")}</div>`);
  $("#cscroll").insertAdjacentHTML("afterend", `<div class="tpanel" id="tpanel" data-ctx="term">
      <div class="t-grab" title="Drag to resize · double-click for the full workspace"></div>
      <div class="t-body">
        <aside class="t-side" id="t-side"></aside>
        <div class="t-main">
          <div class="t-bar"><button class="t-btn" id="t-side-btn" title="Projects sidebar" onclick="termWork()">${ic("sidebar")}</button>
            <div class="t-tabs" id="t-tabs"></div><button class="t-btn" title="New terminal" onclick="termAddMenu(event)">${ic("plus")}</button>
            <button class="t-btn t-cmd" title="Run a command in a new tab" onclick="termCommandBox()">${ic("play")}Command</button>
            <div class="sp"></div>
            <button class="t-btn" title="Split right (Ctrl+Shift+D)" onclick="termSplit('row')"><span class="t-split r"></span></button>
            <button class="t-btn" title="Split down (Ctrl+Shift+E)" onclick="termSplit('col')"><span class="t-split d"></span></button>
            <button class="t-btn" id="t-full" title="Workspace view (fills Chat)" onclick="termWork()">${ic("expand")}</button>
            <button class="t-btn" title="Hide the terminal — everything keeps running (Ctrl+\`)" onclick="termToggle(false)">${ic("down")}</button></div>
          <div class="t-stage" id="t-stage"></div>
          <div class="t-status" id="t-status"></div>
        </div>
      </div></div>`);
  paintIcons(main);
  const grab = $("#tpanel .t-grab");
  grab.addEventListener("pointerdown", e => {
    if (TM.work) return;
    e.preventDefault(); grab.setPointerCapture(e.pointerId); const y0 = e.clientY, h0 = $("#tpanel").offsetHeight;
    const mv = ev => { TM.h = Math.max(140, Math.min(main.clientHeight - 120, h0 + (y0 - ev.clientY))); termLayout(); };
    const up = () => { grab.removeEventListener("pointermove", mv); store.set("daybook-term-h", String(Math.round(TM.h))); };
    grab.addEventListener("pointermove", mv); grab.addEventListener("pointerup", up, {once: true});
  });
  grab.addEventListener("dblclick", () => termWork());
  new ResizeObserver(() => termFit()).observe($("#t-stage"));
  termLayout();
}
function termLayout() {
  const p = $("#tpanel"); if (!p) return;
  p.style.display = TM.open ? "" : "none"; p.classList.toggle("work", TM.work);
  $("#v-chat .cmain").classList.toggle("t-full", TM.open && TM.work); $("#v-chat").classList.toggle("t-work", TM.open && TM.work);
  if (!TM.work) p.style.height = TM.h + "px"; else p.style.height = "";
  const t = $("#t-term"); if (t) t.classList.toggle("on", TM.open);
  const ro = $("#t-reopen"); if (ro) ro.style.display = TM.open || !termOk() ? "none" : "";
  const live = TM.tabs.filter(t => !t.exited).length, n = $("#t-reopen-n"); if (n) n.textContent = live ? ` · ${live} running` : "";
  if (TM.work) termSide();
  termFit();
}
async function termToggle(force) {
  if (!termOk()) return toast("The terminal is part of the Daybook desktop app");
  if (S.view !== "chat") go("chat");
  termEnsureUI(); await termRestore();
  TM.open = force === undefined ? !TM.open : !!force; store.set("daybook-term-open", TM.open ? "1" : "0"); termLayout();
  if (TM.open && !TM.tabs.length) await termNew("pwsh");
  if (TM.open) termFocus();
}
function termWork(on) {
  TM.work = on === undefined ? !TM.work : !!on; store.set("daybook-term-work", TM.work ? "1" : "0");
  if (!TM.open) { TM.open = true; store.set("daybook-term-open", "1"); }
  termLayout(); termFocus();
}

// ---------- sessions ----------
function termBind() {
  if (TM.bound) return; TM.bound = true;
  desktop.term.onData(({id, data}) => { const t = TM.tabs.find(x => x.id === id); if (t && !t.attaching) t.term.write(data); });
  desktop.term.onExit(({id, code}) => { const t = TM.tabs.find(x => x.id === id); if (!t) return; t.exited = true;
    t.term.write(`\r\n\x1b[90m[${t.name} ended${code ? " · code " + code : ""} — press Enter to restart, or close it]\x1b[0m\r\n`); termTabs(); termLayout(); });
}
function termMakeView(info) {  // an xterm for a session (new, or reattached after a reload)
  const el = document.createElement("div"); el.className = "t-pane"; el.dataset.id = info.id || "";
  el.innerHTML = `<div class="t-ph"></div><div class="t-xt"></div>`;
  $("#t-stage").appendChild(el);
  const term = new Terminal({fontFamily: '"JetBrains Mono", "Cascadia Mono", Consolas, monospace', fontSize: 13, fontWeight: "500", fontWeightBold: "700",
    lineHeight: 1.12, cursorBlink: true, cursorStyle: "bar", allowProposedApi: true, scrollback: 10000, theme: termTheme()});
  const fit = new FitAddon.FitAddon(); term.loadAddon(fit);
  term.loadAddon(new WebLinksAddon.WebLinksAddon((_e, url) => window.desktop ? bdNew("personal", url) : open(url, "_blank")));
  term.open(el.querySelector(".t-xt")); try { fit.fit(); } catch (e) {}
  el.addEventListener("mousedown", () => { const i = TM.tabs.findIndex(t => t.el === el); if (i >= 0 && i !== TM.active) { TM.active = i; termTabs(); } });
  return {el, term, fit};
}
function termWire(tab) {
  tab.term.onData(d => { if (tab.exited) { if (d === "\r") termRestart(tab); return; } desktop.term.input(tab.id, d); });
  tab.term.onResize(({cols, rows}) => { if (!tab.exited) desktop.term.resize(tab.id, cols, rows); });
  tab.term.onTitleChange(t => { tab.title = t; termTabs(); });
  tab.term.attachCustomKeyEventHandler(e => termKeys(e, tab));
}
async function termNew(profile, opts = {}) {
  if (!termOk()) return;
  termEnsureUI(); termBind(); await termRestore();
  if (!TM.open) { TM.open = true; store.set("daybook-term-open", "1"); termLayout(); }
  const cwd = opts.cwd || (opts.split && termActiveTab() ? termActiveTab().cwd : undefined);
  const v = termMakeView({});
  if (profile === "emacs") v.term.write("\x1b[90mStarting Emacs with your Doom config — this can take 20–30 seconds…\x1b[0m\r\n");
  const r = await desktop.term.create({profile, cwd, model: opts.model, run: opts.run, cols: v.term.cols, rows: v.term.rows});
  if (!r || r.error) { v.el.remove(); v.term.dispose(); toast((r && r.error) || "Couldn't start the terminal"); return; }
  const tab = {id: r.id, name: r.name, profile, ...v, cwd: r.cwd, opts: {model: opts.model, run: opts.run}, started: Date.now()};
  v.el.dataset.id = r.id; termWire(tab);
  const g = opts.split && termGroupOf((termActiveTab() || {}).id);
  if (g && g.ids.length < 4) { g.ids.splice(g.ids.indexOf(termActiveTab().id) + 1, 0, tab.id); g.dir = g.ids.length > 2 ? "grid" : opts.split; }
  else TM.groups.push({ids: [tab.id], dir: "row"});
  TM.tabs.push(tab); TM.active = TM.tabs.length - 1; termSaveLayout(); termTabs(); termLayout(); termFocus();
  return tab;
}
async function termRestore() {  // reattach sessions that kept running while the page reloaded
  if (TM.restored || !termOk()) return; TM.restored = true; termBind();
  let list = []; try { list = await desktop.term.list(); } catch (e) {}
  if (!list.length) return;
  termEnsureUI();
  let saved = []; try { saved = JSON.parse(store.get("daybook-term-layout", "[]")); } catch (e) {}
  for (const s of list) {
    if (TM.tabs.some(t => t.id === s.id)) continue;
    const v = termMakeView(s);
    const tab = {id: s.id, name: s.name, profile: s.profile, ...v, cwd: s.cwd, opts: s.opts || {}, started: s.started, exited: s.exited, attaching: true};
    TM.tabs.push(tab);
    // messages arrive in order: output delivered before this reply is already part of the replayed log
    const a = await desktop.term.attach(s.id);
    if (a && a.log) v.term.write(a.log);
    tab.attaching = false;
    if (s.exited) v.term.write(`\r\n\x1b[90m[${s.name} ended — press Enter to restart, or close it]\x1b[0m\r\n`);
    termWire(tab);
    setTimeout(() => { try { tab.fit.fit(); desktop.term.resize(tab.id, tab.term.cols, tab.term.rows); } catch (e) {} }, 50);
  }
  const ids = new Set(TM.tabs.map(t => t.id));
  TM.groups = saved.map(g => ({ids: (g.ids || []).filter(i => ids.has(i)), dir: g.dir || "row"})).filter(g => g.ids.length);
  for (const t of TM.tabs) if (!termGroupOf(t.id)) TM.groups.push({ids: [t.id], dir: "row"});
  TM.active = Math.max(0, TM.tabs.length - 1); termSaveLayout(); termTabs(); termLayout();
}
function termKeys(e, tab) {  // copy/paste like Windows Terminal; Emacs keeps its own keys
  if (e.type !== "keydown") return true;
  const k = e.key.toLowerCase(), sel = tab.term.hasSelection();
  if (e.ctrlKey && e.shiftKey && k === "c") { if (sel) navigator.clipboard.writeText(tab.term.getSelection()); return false; }
  if (e.ctrlKey && e.shiftKey && k === "v") { desktop.edit("paste"); return false; }
  if (e.ctrlKey && e.shiftKey && k === "d") { termSplit("row"); return false; }
  if (e.ctrlKey && e.shiftKey && k === "e") { termSplit("col"); return false; }
  if (e.ctrlKey && e.shiftKey && k === "t") { termNew(tab.profile === "emacs" ? "pwsh" : tab.profile, {cwd: tab.cwd}); return false; }
  if (e.ctrlKey && e.shiftKey && k === "w") { termClose(tab.id); return false; }
  if (e.ctrlKey && e.key === "Tab") { termCycle(e.shiftKey ? -1 : 1); return false; }
  if (e.ctrlKey && !e.shiftKey && k === "c" && sel && tab.profile !== "emacs") { navigator.clipboard.writeText(tab.term.getSelection()); tab.term.clearSelection(); return false; }
  if (e.ctrlKey && !e.shiftKey && k === "v" && tab.profile !== "emacs") { desktop.edit("paste"); return false; }
  if (e.ctrlKey && k === "`") { termToggle(false); return false; }
  return true;
}
async function termRestart(tab) {
  const g = termGroupOf(tab.id), pos = g ? g.ids.indexOf(tab.id) : -1;
  termClose(tab.id, true);
  if (g && !TM.groups.includes(g)) TM.groups.push(g);   // keep the tab where it was
  const t = await termNew(tab.profile, {...tab.opts, cwd: tab.cwd});
  if (t && g && pos >= 0) { for (const x of TM.groups) x.ids = x.ids.filter(i => i !== t.id); TM.groups = TM.groups.filter(x => x.ids.length || x === g); g.ids.splice(pos, 0, t.id); termSaveLayout(); termTabs(); }
}
function termClose(id, quiet) {
  const i = TM.tabs.findIndex(t => t.id === id); if (i < 0) return; const t = TM.tabs[i];
  desktop.term.kill(id); t.term.dispose(); t.el.remove(); TM.tabs.splice(i, 1);
  const g = termGroupOf(id); if (g) { g.ids = g.ids.filter(x => x !== id); if (g.ids.length < 3 && g.dir === "grid") g.dir = "row"; }
  TM.groups = TM.groups.filter(x => x.ids.length);
  TM.active = Math.max(0, Math.min(TM.active, TM.tabs.length - 1)); termSaveLayout(); termTabs(); termLayout();
  if (!TM.tabs.length && !quiet) termToggle(false);
}
function termSplit(dir) { const t = termActiveTab(); if (!t) return termNew("pwsh");
  if ((termGroupOf(t.id) || {ids: []}).ids.length >= 4) toast("A tab holds up to 4 panes — opened a new tab"); termNew(t.profile === "emacs" || t.opts.run || t.profile === "ollama" ? "pwsh" : t.profile, {split: dir, cwd: t.cwd}); }
function termCycle(step) {
  if (!TM.groups.length) return; const g = termGroupOf((termActiveTab() || {}).id), gi = (TM.groups.indexOf(g) + step + TM.groups.length) % TM.groups.length;
  termShowGroup(gi);
}
function termShowGroup(gi) { const g = TM.groups[gi]; if (!g) return; const id = g.last && g.ids.includes(g.last) ? g.last : g.ids[0]; TM.active = TM.tabs.findIndex(t => t.id === id); termTabs(); termFocus(); }
function termFocusSession(id) { const i = TM.tabs.findIndex(t => t.id === id); if (i < 0) return; TM.active = i; if (!TM.open) termToggle(true); termTabs(); termFocus(); }

// ---------- drawing ----------
function termTabs() {
  const box = $("#t-tabs"); if (!box) return;
  const cur = termActiveTab(), cg = cur && termGroupOf(cur.id); if (cg) cg.last = cur.id;
  box.innerHTML = TM.groups.map((g, gi) => {
    const first = TM.tabs.find(t => t.id === g.ids[0]); if (!first) return "";
    const ended = g.ids.every(id => (TM.tabs.find(t => t.id === id) || {}).exited);
    const label = termLabel(g.ids.length > 1 && cg === g ? cur : first);
    return `<div class="t-tab ${g === cg ? "on" : ""} ${ended ? "ended" : ""}" onclick="termShowGroup(${gi})" title="${esc(first.cwd || "")}">
      ${termIcon(first.profile)}<span>${esc(label)}</span>${g.ids.length > 1 ? `<em>${g.ids.length}</em>` : ""}
      <button title="Close tab" onclick="event.stopPropagation();termCloseGroup(${gi})">${ic("x")}</button></div>`;
  }).join("");
  paintIcons(box);
  // stage: the active tab's panes, side by side / stacked / 2×2
  const st = $("#t-stage"); st.className = "t-stage " + (cg ? "d-" + cg.dir + " n" + cg.ids.length : "");
  TM.tabs.forEach(t => {
    const pos = cg ? cg.ids.indexOf(t.id) : -1;
    t.el.classList.toggle("on", pos >= 0); t.el.style.order = pos; t.el.classList.toggle("cur", t === cur && cg && cg.ids.length > 1);
    t.el.querySelector(".t-ph").innerHTML = cg && cg.ids.length > 1 && pos >= 0 ? `${termIcon(t.profile)}<span>${esc(termLabel(t))}</span><span class="muted">${esc(termShort(t.cwd))}</span><button title="Close pane" onclick="termClose(${t.id})">${ic("x")}</button>` : "";
  });
  paintIcons(st);
  termStatus(); if (TM.work) termSide();
  requestAnimationFrame(() => TM.tabs.forEach(t => { if (t.el.classList.contains("on")) try { t.fit.fit(); } catch (e) {} }));
}
function termCloseGroup(gi) { const g = TM.groups[gi]; if (g) [...g.ids].forEach((id, i, a) => termClose(id, i < a.length - 1)); }
const termLabel = t => { const tt = (t.title || "").replace(/^Administrator:\s*/, ""); return t.opts && t.opts.model ? t.opts.model : tt && !/\\(pwsh|powershell|cmd)\.exe$/i.test(tt) && tt.length < 48 ? tt : t.name; };
const termShort = p => { if (!p) return ""; const parts = p.replace(/[\\/]+$/, "").split(/[\\/]/); return parts.length > 2 ? "…\\" + parts.slice(-2).join("\\") : p; };
function termProjectOf(cwd) {
  const c = (cwd || "").toLowerCase(); let best = null;
  for (const p of TM.projects) { const k = p.path.toLowerCase(); if ((c === k || c.startsWith(k + "\\")) && (!best || k.length > best.path.length)) best = p; }
  return best;
}
function termStatus() {
  const s = $("#t-status"); if (!s) return;
  const live = TM.tabs.filter(t => !t.exited), ai = live.filter(t => ["claude", "gemini", "ollama"].includes(t.profile)).length, cur = termActiveTab();
  const proj = cur && termProjectOf(cur.cwd);
  s.innerHTML = `<span><i class="t-dot ${live.length ? "on" : ""}"></i>${live.length} running</span>${ai ? `<span>${termIcon("claude")} ${ai} AI</span>` : ""}
    ${cur ? `<span class="t-cwd" title="${esc(cur.cwd || "")}">${esc(cur.cwd || "")}</span>` : ""}${proj && proj.branch ? `<span>⎇ ${esc(proj.branch)}</span>` : ""}
    <span class="sp"></span><span class="muted">Ctrl+Shift+D split · Ctrl+Tab next · Ctrl+\` hide</span>`;
}
async function termLoadProjects() { try { TM.projects = await desktop.term.projects(); } catch (e) { TM.projects = []; } }
async function termSide(reload) {
  const side = $("#t-side"); if (!side) return;
  if (reload || !TM.projects.length && !TM._pl) { TM._pl = true; await termLoadProjects(); }
  const f = TM.filter.toLowerCase(), groups = new Map();
  for (const t of TM.tabs) { const p = termProjectOf(t.cwd); const k = p ? p.path : ""; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(t); }
  const sess = t => { const i = TM.tabs.indexOf(t); return `<div class="t-sess ${i === TM.active ? "on" : ""}" onclick="termFocusSession(${t.id})" title="${esc(t.cwd || "")}">
      <i class="t-dot ${t.exited ? "" : "on"}"></i>${termIcon(t.profile)}<span>${esc(termLabel(t))}</span><span class="muted">${termAge(t.started || Date.now())}</span></div>`; };
  const proj = p => { const list = groups.get(p.path) || [];
    if (f && !p.name.toLowerCase().includes(f) && !list.some(t => termLabel(t).toLowerCase().includes(f))) return "";
    return `<div class="t-proj" data-ctx="tproj" data-path="${esc(p.path)}"><div class="t-pname" onclick="termNew('pwsh',{cwd:${esc(JSON.stringify(p.path))}})" title="New shell in ${esc(p.path)}">${ic("folder")}<b>${esc(p.name)}</b>
        <span class="t-pacts"><button title="New shell here" onclick="event.stopPropagation();termNew('pwsh',{cwd:${esc(JSON.stringify(p.path))}})">${termIcon("pwsh")}</button><button title="Claude Code here" onclick="event.stopPropagation();termNew('claude',{cwd:${esc(JSON.stringify(p.path))}})">${termIcon("claude")}</button><button title="Gemini here" onclick="event.stopPropagation();termNew('gemini',{cwd:${esc(JSON.stringify(p.path))}})">${termIcon("gemini")}</button></span></div>
      ${p.branch ? `<div class="t-branch"><i class="t-dot ${list.some(t => !t.exited) ? "on" : ""}"></i>${esc(p.branch)}${list.length ? `<span class="t-badge">${list.length}</span>` : ""}</div>` : ""}
      ${list.map(sess).join("")}</div>`; };
  const other = groups.get("") || [];
  side.innerHTML = `<div class="t-search">${ic("search")}<input placeholder="Search" value="${esc(TM.filter)}" oninput="TM.filter=this.value;termSide()"></div>
    <div class="t-sh"><span>Projects</span><button title="Add a project folder" onclick="termAddProject()">${ic("plus")}</button><button title="Refresh" onclick="termSide(true)">${ic("rep")}</button></div>
    <div class="t-plist">${TM.projects.map(proj).join("") || `<div class="muted t-none">Add a folder you work in with +</div>`}
    ${other.length ? `<div class="t-proj"><div class="t-pname">${ic("chip")}<b>Other sessions</b></div>${other.map(sess).join("")}</div>` : ""}</div>`;
  paintIcons(side);
  const inp = side.querySelector("input"); if (TM.filter && document.activeElement !== inp) { inp.focus(); inp.setSelectionRange(TM.filter.length, TM.filter.length); }
}
async function termAddProject() { const d = await desktop.term.addProject(); if (d) { await termSide(true); toast("Added " + d); } }
function termFit() { if (!TM.open) return; requestAnimationFrame(() => TM.tabs.forEach(t => { if (t.el.classList.contains("on")) try { t.fit.fit(); } catch (e) {} })); }
function termFocus() { const t = termActiveTab(); if (t) setTimeout(() => t.term.focus(), 30); }
// "Command": type a command, it runs in a new tab in the current folder (the shell stays open afterwards)
function termCommandBox() {
  const cur = termActiveTab(), cwd = cur ? cur.cwd : "";
  const bar = $("#tpanel .t-bar"); if ($("#t-cmdbox")) return $("#t-cmdbox input").focus();
  bar.insertAdjacentHTML("afterend", `<div class="t-cmdbox" id="t-cmdbox">${ic("play")}<input placeholder="Command to run${cwd ? " in " + esc(termShort(cwd)) : ""} — e.g. npm run dev, git status, python app.py" autocomplete="off"><span class="muted">Enter to run · Esc to cancel</span></div>`);
  paintIcons($("#t-cmdbox")); const inp = $("#t-cmdbox input"); inp.focus();
  inp.addEventListener("keydown", e => {
    if (e.key === "Escape") { $("#t-cmdbox").remove(); termFocus(); }
    if (e.key === "Enter" && inp.value.trim()) { const run = inp.value.trim(); $("#t-cmdbox").remove(); termNew("pwsh", {cwd, run}); }
  });
}
async function termAddMenu(e) {
  e && e.stopPropagation && e.stopPropagation();
  const profs = await desktop.term.profiles(), models = await desktop.term.models(), cwd = (termActiveTab() || {}).cwd;
  const item = p => {
    if (p.id === "ai-stack") return {t: p.name, i: "zap", run: () => termNew("ai-stack", {cwd})};
    if (p.id === "ollama") {
      if (p.ok) return {t: p.name, i: "chip", sub: [...models.map(m => ({t: m, i: "chip", run: () => termNew("ollama", {model: m, cwd})})), "-", {t: "List models (ollama list)", i: "list", run: () => termNew("ollama", {cwd})}]};
      return {t: "Ollama (1-Click Install)", i: "plus", run: () => termNew("ollama", {cwd})};
    }
    if (p.id === "claude" && !p.ok) return {t: "Claude Code (1-Click Install)", i: "plus", run: () => termNew("claude", {cwd})};
    if (p.id === "gemini" && !p.ok) return {t: "Gemini CLI — install & sign in", i: "plus", run: () => termNew("gemini", {cwd})};
    return {t: p.name, i: {claude: "spark", gemini: "spark", emacs: "pen", orca: "zap", arcade: "gamepad"}[p.id] || "chip", off: !p.ok, run: () => termNew(p.id, {cwd})};
  };
  const groups = ["Shells", "AI", "Tools"].map(g => [{h: g}, ...profs.filter(p => p.group === g).map(item)]).flat();
  const missing = profs.filter(p => !p.ok && !["gemini", "claude", "ollama", "ai-stack"].includes(p.id));
  const r = e && e.currentTarget ? e.currentTarget.getBoundingClientRect() : {left: innerWidth / 2, bottom: innerHeight / 2};
  ctxShow(r.left, r.bottom + 4, [...groups, "-", {t: "Run a command…", i: "play", run: termCommandBox},
    ...(missing.length ? ["-", {h: "Not installed: " + missing.map(p => p.name).join(", ")}] : [])]);
}

// ---------- menus & hooks ----------
const termHasFocus = e => !!(e.target && e.target.closest && e.target.closest(".xterm"));
CTX.term = el => {
  const t = termActiveTab(), sel = t && t.term.hasSelection();
  return [{t: "Copy", i: "copy", k: "Ctrl Shift C", off: !sel, run: () => navigator.clipboard.writeText(t.term.getSelection())},
    {t: "Paste", i: "copy", k: "Ctrl Shift V", off: !t, run: () => { t.term.focus(); desktop.edit("paste"); }},
    {t: "Select all", i: "check", off: !t, run: () => t.term.selectAll()},
    {t: "Clear", i: "trash", off: !t, run: () => t.term.clear()}, "-",
    {t: "New terminal", i: "plus", run: () => termAddMenu()},
    {t: "Split right", i: "layers", k: "Ctrl Shift D", run: () => termSplit("row")},
    {t: "Split down", i: "layers", k: "Ctrl Shift E", run: () => termSplit("col")},
    {t: "Run a command…", i: "play", run: termCommandBox},
    {t: TM.work ? "Back to the chat" : "Workspace view", i: "expand", run: () => termWork()},
    t ? {t: "Restart this session", i: "rep", run: () => termRestart(t)} : null,
    t && t.cwd ? {t: "Open this folder in Files", i: "folder", run: () => { LP.view = "folders"; go("launchpad", "folders"); setTimeout(() => fdNewPane(t.cwd), 300); }} : null,
    t ? {t: "Close", i: "x", k: "Ctrl Shift W", run: () => termClose(t.id)} : null].filter(Boolean);
};
CTX.tproj = el => {
  const p = el.closest("[data-path]").dataset.path, mine = (TM.projects.find(x => x.path === p) || {}).mine;
  return [{h: p}, {t: "New shell here", i: "chip", run: () => termNew("pwsh", {cwd: p})}, {t: "Claude Code here", i: "spark", run: () => termNew("claude", {cwd: p})},
    {t: "Gemini here", i: "spark", run: () => termNew("gemini", {cwd: p})}, {t: "Emacs here", i: "pen", run: () => termNew("emacs", {cwd: p})}, "-",
    {t: "Open in Files", i: "folder", run: () => { LP.view = "folders"; go("launchpad", "folders"); setTimeout(() => fdNewPane(p), 300); }},
    mine ? {t: "Remove from the list", i: "x", run: async () => { await desktop.term.removeProject(p); termSide(true); }} : null].filter(Boolean);
};
const _fdFolderItems = fdFolderItems;
fdFolderItems = function (id, path) {
  const items = _fdFolderItems(id, path);
  if (termOk()) items.splice(3, 0, {t: "Open terminal here", i: "chip", run: () => { go("chat"); setTimeout(() => termNew("pwsh", {cwd: path}), 200); }});
  return items;
};
// code blocks in AI replies → paste into the terminal (never runs by itself: you press Enter)
function termDecorateCode() {
  if (!termOk()) return;
  $$("#thread pre:not([data-term])").forEach(pre => {
    pre.dataset.term = 1; const code = pre.querySelector("code") || pre;
    const lang = (code.className.match(/language-(\w+)/) || [])[1] || "";
    if (lang && !/^(bash|sh|shell|zsh|powershell|ps1|pwsh|cmd|bat|console)$/i.test(lang)) return;
    const b = document.createElement("button"); b.className = "btn sm t-run"; b.title = "Paste into the terminal — press Enter there to run it";
    b.innerHTML = ic("chip") + "Paste into terminal";
    b.onclick = async () => { let t = termActiveTab(); if (!t || t.exited) t = await termNew("pwsh"); else await termToggle(true);
      desktop.term.input(t.id, code.innerText.replace(/\n+$/, "").replace(/\n/g, "\r")); t.term.focus(); };
    pre.appendChild(b);
  });
}
if ($("#thread")) new MutationObserver(() => termDecorateCode()).observe($("#thread"), {childList: true, subtree: true});
addEventListener("keydown", e => { if (e.ctrlKey && e.key === "`" && !termHasFocus(e)) { e.preventDefault(); termToggle(); } });
if (typeof CMDS !== "undefined" && termOk()) CMDS.push(["Open terminal", "chip", () => termToggle(true)], ["Terminal workspace (projects, splits)", "expand", () => termWork(true)],
  ["New Claude Code session", "spark", () => { go("chat"); termNew("claude"); }], ["Run a command in a terminal", "play", () => { termToggle(true).then(termCommandBox); }],
  ["Play 8-Bit Retro Arcade in Terminal", "gamepad", () => { go("chat"); termNew("arcade"); }]);
// reopen it where you left it, and pick up sessions that kept running through a reload
setTimeout(async () => { if (!termOk()) return; await termRestore(); if (TM.open && S.view === "chat") { TM.open = false; termToggle(true); } }, 1500);
const _enterChat = enterChat;
enterChat = async function (sub) { const r = await _enterChat(sub); if (termOk()) { termEnsureUI(); await termRestore(); termLayout(); if (TM.open && !TM.tabs.length) termNew("pwsh"); } return r; };
