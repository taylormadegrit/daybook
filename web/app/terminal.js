// ================= CHAT → TERMINAL: real shells + Claude / Gemini / local AI CLIs, Emacs and Orca =================
// The terminal runs in Daybook's desktop app (node-pty + ConPTY); this page only draws it (xterm.js, bundled offline).
const TM = {tabs: [], active: 0, open: store.get("daybook-term-open", "0") === "1", h: +store.get("daybook-term-h", "320"), full: false, bound: false, profiles: null};
const termOk = () => !!(window.desktop && desktop.term);
function termCssVar(n, d) { const v = getComputedStyle(document.documentElement).getPropertyValue(n).trim(); return v || d; }
function termTheme() {
  return {background: "#0b0c12", foreground: termCssVar("--fg", "#eceef4"), cursor: termCssVar("--a2", "#4fd1ff"), selectionBackground: "rgba(139,123,255,.35)",
    black: "#1b1d27", red: "#ff6b81", green: "#3ee0a0", yellow: "#ffbe5c", blue: "#6aa8ff", magenta: "#c792ea", cyan: "#4fd1ff", white: "#d7dae5",
    brightBlack: "#5c6370", brightRed: "#ff8fa0", brightGreen: "#7ff0c0", brightYellow: "#ffd98a", brightBlue: "#94c1ff", brightMagenta: "#ddb6f2", brightCyan: "#8de6ff", brightWhite: "#ffffff"};
}
function termEnsureUI() {
  const main = $("#v-chat .cmain"); if (!main || $("#tpanel")) return;
  $("#v-chat .cbar .tog#t-orca").insertAdjacentHTML("afterend", `<span class="tog" id="t-term" onclick="termToggle()" title="Terminal — PowerShell, Claude, Gemini, local AI, Emacs, Orca (Ctrl+\`)">${ic("chip")}Terminal</span>`);
  $("#cscroll").insertAdjacentHTML("afterend", `<div class="tpanel" id="tpanel" data-ctx="term">
      <div class="t-grab" title="Drag to resize · double-click for full height"></div>
      <div class="t-bar"><div class="t-tabs" id="t-tabs"></div><button class="iconbtn" title="New terminal" onclick="termAddMenu(event)">${ic("plus")}</button>
        <div class="sp"></div><button class="iconbtn" id="t-full" title="Full height" onclick="termFull()">${ic("expand")}</button>
        <button class="iconbtn" title="Hide terminal (keeps it running)" onclick="termToggle(false)">${ic("down")}</button></div>
      <div class="t-stage" id="t-stage"></div></div>`);
  paintIcons(main);
  const grab = $("#tpanel .t-grab");
  grab.addEventListener("pointerdown", e => {
    e.preventDefault(); grab.setPointerCapture(e.pointerId); const y0 = e.clientY, h0 = $("#tpanel").offsetHeight;
    const mv = ev => { TM.h = Math.max(140, Math.min(main.clientHeight - 120, h0 + (y0 - ev.clientY))); termLayout(); };
    const up = () => { grab.removeEventListener("pointermove", mv); store.set("daybook-term-h", String(Math.round(TM.h))); };
    grab.addEventListener("pointermove", mv); grab.addEventListener("pointerup", up, {once: true});
  });
  grab.addEventListener("dblclick", termFull);
  new ResizeObserver(() => termFit()).observe($("#t-stage"));
  termLayout();
}
function termLayout() {
  const p = $("#tpanel"); if (!p) return;
  p.style.display = TM.open ? "" : "none"; p.classList.toggle("full", TM.full);
  $("#v-chat .cmain").classList.toggle("t-full", TM.open && TM.full);
  if (!TM.full) p.style.height = TM.h + "px";
  const t = $("#t-term"); if (t) t.classList.toggle("on", TM.open);
  termFit();
}
async function termToggle(force) {
  if (!termOk()) return toast("The terminal is part of the Daybook desktop app");
  if (S.view !== "chat") go("chat");
  termEnsureUI(); TM.open = force === undefined ? !TM.open : !!force; store.set("daybook-term-open", TM.open ? "1" : "0"); termLayout();
  if (TM.open && !TM.tabs.length) await termNew("pwsh");
  if (TM.open) termFocus();
}
function termFull() { TM.full = !TM.full; termLayout(); }
async function termNew(profile, opts = {}) {
  if (!termOk()) return;
  termEnsureUI(); if (!TM.open) { TM.open = true; store.set("daybook-term-open", "1"); termLayout(); }
  if (!TM.bound) {
    TM.bound = true;
    desktop.term.onData(({id, data}) => { const t = TM.tabs.find(x => x.id === id); if (t) t.term.write(data); });
    desktop.term.onExit(({id, code}) => { const t = TM.tabs.find(x => x.id === id); if (!t) return; t.exited = true;
      t.term.write(`\r\n\x1b[90m[${t.name} ended${code ? " · code " + code : ""} — press Enter to restart, or close this tab]\x1b[0m\r\n`); termTabs(); });
  }
  const el = document.createElement("div"); el.className = "t-pane"; $("#t-stage").appendChild(el);
  const term = new Terminal({fontFamily: '"JetBrains Mono", Consolas, monospace', fontSize: 13, cursorBlink: true, allowProposedApi: true, scrollback: 5000, theme: termTheme()});
  const fit = new FitAddon.FitAddon(); term.loadAddon(fit);
  term.loadAddon(new WebLinksAddon.WebLinksAddon((_e, url) => window.desktop ? bdNew("personal", url) : open(url, "_blank")));
  term.open(el); try { fit.fit(); } catch (e) {}
  if (profile === "emacs") term.write("\x1b[90mStarting Emacs with your Doom config — this can take 20–30 seconds…\x1b[0m\r\n");
  const r = await desktop.term.create({profile, cwd: opts.cwd, model: opts.model, cols: term.cols, rows: term.rows});
  if (!r || r.error) { el.remove(); term.dispose(); return toast((r && r.error) || "Couldn't start the terminal"); }
  const tab = {id: r.id, name: opts.model ? `${opts.model}` : r.name, profile, term, fit, el, cwd: r.cwd, opts};
  term.onData(d => { if (tab.exited) { if (d === "\r") termRestart(tab); return; } desktop.term.input(tab.id, d); });
  term.onResize(({cols, rows}) => desktop.term.resize(tab.id, cols, rows));
  term.attachCustomKeyEventHandler(e => termKeys(e, tab));
  TM.tabs.push(tab); TM.active = TM.tabs.length - 1; termTabs(); termFocus();
  return tab;
}
function termKeys(e, tab) {  // copy/paste like Windows Terminal; Emacs keeps its own keys
  if (e.type !== "keydown") return true;
  const k = e.key.toLowerCase(), sel = tab.term.hasSelection();
  if (e.ctrlKey && e.shiftKey && k === "c") { if (sel) navigator.clipboard.writeText(tab.term.getSelection()); return false; }
  if (e.ctrlKey && e.shiftKey && k === "v") { desktop.edit("paste"); return false; }
  if (e.ctrlKey && !e.shiftKey && k === "c" && sel && tab.profile !== "emacs") { navigator.clipboard.writeText(tab.term.getSelection()); tab.term.clearSelection(); return false; }
  if (e.ctrlKey && !e.shiftKey && k === "v" && tab.profile !== "emacs") { desktop.edit("paste"); return false; }
  if (e.ctrlKey && k === "`") { termToggle(false); return false; }
  return true;
}
async function termRestart(tab) {
  const i = TM.tabs.indexOf(tab); termClose(tab.id, true);
  const t = await termNew(tab.profile, tab.opts); if (t && i >= 0) { TM.tabs.splice(TM.tabs.indexOf(t), 1); TM.tabs.splice(i, 0, t); TM.active = i; termTabs(); }
}
function termClose(id, quiet) {
  const i = TM.tabs.findIndex(t => t.id === id); if (i < 0) return; const t = TM.tabs[i];
  if (!t.exited) desktop.term.kill(id); t.term.dispose(); t.el.remove(); TM.tabs.splice(i, 1);
  TM.active = Math.max(0, Math.min(TM.active, TM.tabs.length - 1)); termTabs();
  if (!TM.tabs.length && !quiet) termToggle(false);
}
function termTabs() {
  const box = $("#t-tabs"); if (!box) return;
  box.innerHTML = TM.tabs.map((t, i) => `<div class="t-tab ${i === TM.active ? "on" : ""} ${t.exited ? "ended" : ""}" onclick="TM.active=${i};termTabs();termFocus()" title="${esc(t.cwd || "")}">
      <span>${esc(t.name)}</span><button title="Close" onclick="event.stopPropagation();termClose(${t.id})">${ic("x")}</button></div>`).join("");
  paintIcons(box);
  TM.tabs.forEach((t, i) => t.el.classList.toggle("on", i === TM.active));
  termFit();
}
function termFit() { const t = TM.tabs[TM.active]; if (!t || !TM.open) return; requestAnimationFrame(() => { try { t.fit.fit(); } catch (e) {} }); }
function termFocus() { const t = TM.tabs[TM.active]; if (t) setTimeout(() => t.term.focus(), 30); }
async function termAddMenu(e) {
  e && e.stopPropagation();
  const profs = await desktop.term.profiles(), models = await desktop.term.models();
  const item = p => p.id === "ollama" && p.ok ? {t: p.name, i: "chip", sub: [...models.map(m => ({t: m, i: "chip", run: () => termNew("ollama", {model: m})})), "-", {t: "List models (ollama list)", i: "list", run: () => termNew("ollama")}]}
    : p.id === "gemini" && !p.ok ? {t: "Gemini CLI — install & sign in", i: "plus", run: () => termNew("gemini")}
    : {t: p.name, i: {pwsh: "chip", cmd: "chip", bash: "chip", wsl: "chip", claude: "spark", gemini: "spark", emacs: "pen", orca: "zap"}[p.id] || "chip", off: !p.ok, run: () => termNew(p.id)};
  const groups = ["Shells", "AI", "Tools"].map(g => [{h: g}, ...profs.filter(p => p.group === g).map(item)]).flat();
  const missing = profs.filter(p => !p.ok && p.id !== "gemini");
  const r = e && e.currentTarget ? e.currentTarget.getBoundingClientRect() : {left: innerWidth / 2, bottom: innerHeight / 2};
  ctxShow(r.left, r.bottom + 4, [...groups, ...(missing.length ? ["-", {h: "Not installed: " + missing.map(p => p.name).join(", ")}] : [])]);
}
// keep the terminal's keys inside it (Emacs, shells and AI CLIs use Ctrl/Alt combos)
const termHasFocus = e => !!(e.target && e.target.closest && e.target.closest(".xterm"));
// right-click inside the terminal
CTX.term = el => {
  const t = TM.tabs[TM.active], sel = t && t.term.hasSelection();
  return [{t: "Copy", i: "copy", k: "Ctrl Shift C", off: !sel, run: () => navigator.clipboard.writeText(t.term.getSelection())},
    {t: "Paste", i: "copy", k: "Ctrl Shift V", off: !t, run: () => { t.term.focus(); desktop.edit("paste"); }},
    {t: "Select all", i: "check", off: !t, run: () => t.term.selectAll()},
    {t: "Clear", i: "trash", off: !t, run: () => t.term.clear()}, "-",
    {t: "New terminal", i: "plus", run: () => termAddMenu()},
    t ? {t: "Restart this tab", i: "rep", run: () => termRestart(t)} : null,
    t && t.cwd ? {t: "Open this folder in Files", i: "folder", run: () => { LP.view = "folders"; go("launchpad", "folders"); setTimeout(() => fdNewPane(t.cwd), 300); }} : null,
    t ? {t: "Close tab", i: "x", run: () => termClose(t.id)} : null].filter(Boolean);
};
// Files hub → "Open terminal here"
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
    b.onclick = async () => { let t = TM.tabs[TM.active]; if (!t) t = await termNew("pwsh"); else termToggle(true);
      desktop.term.input(t.id, code.innerText.replace(/\n+$/, "").replace(/\n/g, "\r")); t.term.focus(); };
    pre.appendChild(b);
  });
}
if ($("#thread")) new MutationObserver(() => termDecorateCode()).observe($("#thread"), {childList: true, subtree: true});
addEventListener("keydown", e => { if (e.ctrlKey && e.key === "`" && !termHasFocus(e)) { e.preventDefault(); termToggle(); } });
// reopen it where you left it
setTimeout(() => { if (termOk() && TM.open && S.view === "chat") { TM.open = false; termToggle(true); } }, 1500);
const _enterChat = enterChat;
enterChat = async function (sub) { const r = await _enterChat(sub); if (termOk()) { termEnsureUI(); termLayout(); if (TM.open && !TM.tabs.length) termNew("pwsh"); } return r; };
