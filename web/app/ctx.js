// ================= RIGHT-CLICK MENU — everywhere in Daybook =================
// Right-click anything: the thing under the mouse gets its own actions on top (files, apps, games, notes, reminders…),
// then text tools (copy, paste, search, save as note) and the app itself (go to any page, create anything, search).
// Items: {t: label, i: icon, k: shortcut hint, run, off: disabled, danger, sub: [items], h: heading} or "-" (separator).
const CTX = {};
const CTX_HIST = [];
(function trackPages() {  // remember where you've been, for "Back"
  const orig = go;
  go = function (v, sub) { if (S.view && S.view !== v) { CTX_HIST.push(S.view); if (CTX_HIST.length > 30) CTX_HIST.shift(); } return orig(v, sub); };
})();
function ctxHide() { const had = $$(".ctxm"); had.forEach(m => m.remove()); if (had.length && window.dockSync) setTimeout(dockSync, 0); }
function ctxNativeNeeded() { return !!(window.desktop && desktop.menu && S.view === "browser" && typeof BD !== "undefined" && BD.panes.length + BD.chrome.length > 0); }
async function ctxShowNative(x, y, items) {
  const runs = {}; let n = 0;
  const strip = list => list.filter(Boolean).map(it => it === "-" ? "-" : it.h ? {h: it.h} : {t: it.t, k: it.k, off: !!it.off, id: (runs[++n] = it.run, n), sub: it.sub ? strip(it.sub) : undefined});
  const id = await desktop.menu(strip(items), x, y);
  const run = id && runs[id]; if (run) { try { const r = run(); if (r && r.catch) r.catch(err => toast(err.message)); } catch (err) { toast(err.message); } }
}
function ctxShow(x, y, items, parent) {
  if (!parent && ctxNativeNeeded()) { ctxHide(); ctxShowNative(x, y, items); return null; }
  if (!parent) ctxHide();
  const clean = items.filter((it, k) => it !== "-" || (k > 0 && items[k - 1] !== "-" && k < items.length - 1));
  const m = document.createElement("div"); m.className = "menu on ctxm"; m.setAttribute("role", "menu");
  m.innerHTML = clean.map((it, k) => it === "-" ? `<hr>` : it.h ? `<div class="mh">${esc(it.h)}</div>`
    : `<div class="ctxi ${it.off ? "off" : ""} ${it.danger ? "danger" : ""} ${it.sub ? "has-sub" : ""}" data-k="${k}">${it.i ? ic(it.i) : `<span class="ctx-sp"></span>`}<span class="ctx-t">${esc(it.t)}</span>${it.k ? `<span class="kbd">${esc(it.k)}</span>` : ""}${it.sub ? ic("right") : ""}</div>`).join("");
  document.body.appendChild(m);
  const r = m.getBoundingClientRect(), W = innerWidth, H = innerHeight;
  m.style.left = Math.max(6, x + r.width > W - 6 ? (parent ? parent.left - r.width + 4 : x - r.width) : x) + "px";
  m.style.top = Math.max(6, Math.min(y, H - r.height - 6)) + "px";
  m.querySelectorAll(".ctxi").forEach(el => {
    const it = clean[+el.dataset.k];
    el.addEventListener("mouseenter", () => {
      $$(".ctxm").forEach(o => { if (o !== m && o._parent === m) o.remove(); });
      if (it.sub && !it.off) { const b = el.getBoundingClientRect(); const s = ctxShow(b.right - 4, b.top - 6, it.sub, b); s._parent = m; }
    });
    el.addEventListener("click", e => {
      e.stopPropagation(); if (it.off || it.sub) return;
      ctxHide(); try { const r = it.run && it.run(); if (r && r.catch) r.catch(err => toast(err.message)); } catch (err) { toast(err.message); }
    });
  });
  return m;
}
addEventListener("mousedown", e => { if (!e.target.closest(".ctxm")) ctxHide(); }, true);
addEventListener("keydown", e => { if (e.key === "Escape" && $(".ctxm")) { ctxHide(); e.stopPropagation(); } }, true);
addEventListener("blur", ctxHide); addEventListener("resize", ctxHide);
addEventListener("wheel", e => { if (!e.target.closest(".ctxm")) ctxHide(); }, {capture: true, passive: true});

async function ctxEdit(a, el) {
  if (!el && CTXP.pending && CTXP.pending.typed) el = CTXP.pending.typed;
  if (!el && document.activeElement && /INPUT|TEXTAREA/.test(document.activeElement.tagName)) el = document.activeElement;
  if (el && typeof el.focus === "function") el.focus();

  if (a === "paste") {
    let clip = "";
    try {
      if (window.desktop && desktop.clipboard && desktop.clipboard.readText) clip = await desktop.clipboard.readText();
      else if (navigator.clipboard && navigator.clipboard.readText) clip = await navigator.clipboard.readText();
    } catch (e) {}

    if (clip && el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? el.value.length;
      if (typeof el.setRangeText === "function") {
        el.setRangeText(clip, start, end, "end");
      } else {
        el.value = el.value.slice(0, start) + clip + el.value.slice(end);
      }
      el.dispatchEvent(new Event("input", {bubbles: true}));
      return;
    }
    if (clip && el && el.isContentEditable) {
      document.execCommand("insertText", false, clip);
      return;
    }
  }

  if (window.desktop && desktop.edit) desktop.edit(a);
  else document.execCommand(a);
}
function ctxSearchWeb(q) {
  const url = "https://www.google.com/search?q=" + encodeURIComponent(q);
  if (window.desktop) bdNew("personal", url); else open(url, "_blank");
}
async function ctxSaveNote(text, title) {
  const n = await api("/api/notes", {method: "POST", body: {body: text, title: title || ""}});
  toast("Saved to Notes — the AI will title and tag it"); return n;
}
function ctxAskAI(text) { go("chat"); setTimeout(() => { const c = $("#cinput"); if (c) { c.value = text; c.focus(); c.dispatchEvent(new Event("input")); } }, 200); }
function ctxGeneral() {
  const pages = $$(".nav .navi").filter(n => n.offsetParent !== null || n.dataset.v).map(n => ({t: (n.querySelector("span") || n).textContent.trim() || VIEWS[n.dataset.v][0], v: n.dataset.v}))
    .filter(p => VIEWS[p.v]).map(p => ({t: p.t, i: VIEW_ICON[p.v] || "right", off: p.v === S.view, run: () => go(p.v)}));
  return [
    {t: "Back", i: "left", off: !CTX_HIST.length, k: "", run: () => { const v = CTX_HIST.pop(); go(v); CTX_HIST.pop(); }},
    {t: "Go to", i: "grid", sub: pages},
    {t: "New", i: "plus", sub: [{t: "Note…", i: "note", run: () => templateModal()}, {t: "Reminder", i: "bell", k: "Ctrl Alt R", run: () => reminderModal()},
      {t: "Sticky note", i: "sticky", k: "Alt S", run: () => newSticky()}, {t: "Voice memo", i: "mic", run: () => { go("memos"); setTimeout(memoRecToggle, 250); }},
      {t: "Timer", i: "timer", run: () => go("clock", "timers")}, {t: "Chat", i: "chat", run: () => newChat()},
      window.desktop ? {t: "Browser tab", i: "globe", run: () => bdNew("personal")} : null,
      {t: "Folder pane", i: "folder", run: () => { LP.view = "folders"; go("launchpad", "folders"); setTimeout(() => fdNewPane(), 300); }}].filter(Boolean)},
    {t: "Search everything…", i: "search", k: "Ctrl K", run: () => openPalette()}, "-",
    {t: "Take the tour", i: "help", run: () => tourStart()},
    {t: "Show sticky notes", i: "layers", k: "Alt W", run: () => peekStickies()},
    {t: "Annotate screen", i: "brush", k: "Alt P", run: () => annotateNow()},
    S.view === "today" ? {t: "Customize home", i: "palette", run: () => customizeModal()} : null,
    S.view === "today" ? {t: "Edit home widgets", i: "grid", run: () => homeEdit(true)} : null,
    {t: "Refresh this page", i: "rep", run: () => go(S.view, location.hash.split("/")[1])},
    window.desktop ? {t: "New Daybook window", i: "expand", k: "Ctrl Shift N", run: () => newAppWindow(S.view)} : null,
    {t: "Settings", i: "settings", off: S.view === "settings", run: () => go("settings")}].filter(Boolean);
}
const VIEW_ICON = {today: "home", launchpad: "grid", workflows: "play", games: "gamepad", browser: "globe", calendar: "cal", reminders: "bell", notes: "note", memos: "mic",
  studio: "spark", clock: "timer", research: "book", desktop: "sticky", chat: "chat", models: "chip", settings: "settings", help: "help"};
// actions for a row/card: mirror its own buttons, so every list in the app gets a menu without extra code
function ctxRowActions(el) {
  const seen = new Set(), out = [];
  if (el.getAttribute("onclick")) out.push({t: "Open", i: "right", run: () => el.click()});
  el.querySelectorAll("button, [onclick]").forEach(b => {
    if (b === el || b.disabled || b.closest(".menu") || !b.offsetParent) return;
    const t = (b.getAttribute("title") || b.textContent || "").trim().replace(/\s+/g, " ").split("\n")[0].slice(0, 48);
    if (!t || seen.has(t) || /^[✕×]$/.test(t)) return; seen.add(t);
    out.push({t, i: /delete|remove|trash/i.test(t) ? "trash" : /edit|rename/i.test(t) ? "pen" : /done|complete|check/i.test(t) ? "check" : /play|start|open|launch/i.test(t) ? "play" : /snooze/i.test(t) ? "snooze" : "right",
      danger: /delete|remove/i.test(t), run: () => b.click()});
  });
  return out.slice(0, 10);
}
CTX.lpt = el => {
  const r = +el.dataset.r, c = +el.dataset.c, it = (lpRows()[r] || [])[c]; if (!it) return [];
  if (it.type === "profile") return [{h: it.name}, {t: "Open inside Daybook", i: "globe", run: () => window.desktop ? bdChromeOpen(it.b.id, it.p.id) : lpOpen(r, c)},
    {t: "Open in its own window", i: "ext", run: () => lpBrowser(it.b.id, it.p.id)}];
  return [{h: it.name}, {t: "Open", i: "play", run: () => lpOpen(r, c)}];
};
CTX.gcard = el => {
  const m = (el.innerHTML.match(/gmDetails\('([^']+)'\)/) || [])[1]; if (!m) return ctxRowActions(el);
  const g = GM.data && GM.data.owned.find(x => x.id === m) || {name: ""};
  return [{h: g.name.replace(/[™®]/g, "")}, {t: "Play", i: "play", run: () => gmPlay(m)}, {t: "Details", i: "list", run: () => gmDetails(m)}];
};
CTX.note = el => {
  const id = +((el.getAttribute("onclick") || "").match(/openNote\((\d+)\)/) || [])[1]; if (!id) return [];
  const title = (el.querySelector("b,.t") || el).textContent.trim().split("\n")[0].slice(0, 40);
  return [{h: title}, {t: "Open", i: "note", run: () => openNote(id)},
    {t: "Organize with AI (find tasks)", i: "spark", run: async () => { await openNote(id); aiNote(); }},
    typeof discordSend === "function" ? {t: "Send to Discord", i: "send", run: () => discordSend("note", id)} : null,
    {t: "Copy text", i: "copy", run: async () => { const n = await api("/api/notes/" + id); await navigator.clipboard.writeText((n.title ? n.title + "\n\n" : "") + n.body); toast("Note copied"); }}, "-",
    {t: "Delete note", i: "trash", danger: true, run: async () => { if (!confirm(`Delete “${title}”?`)) return; await api("/api/notes/" + id, {method: "DELETE"}); if (S.cur && S.cur.id === id) { S.cur = null; $("#ed").innerHTML = `<div class="empty"><b>Deleted</b></div>`; } loadNotes(); toast("Note deleted"); }}].filter(Boolean);
};
document.addEventListener("contextmenu", e => {
  const t = e.target;
  if (t.closest(".ctxm")) return e.preventDefault();
  let own = [];
  const tagged = t.closest("[data-ctx]");
  if (tagged && tagged.dataset.ctx === "term") { e.preventDefault(); const it = CTX.term(tagged); ctxShow(e.clientX, e.clientY, it); return; }
  const typed = t.closest("input:not([type=checkbox]):not([type=radio]):not([type=range]):not([type=color]), textarea, [contenteditable=''], [contenteditable=true]");
  if (!(typed && !tagged && window.desktop && desktop.onContextParams)) e.preventDefault();  // text boxes: let Electron report spelling
  const sel = String(getSelection() || "").trim();
  const link = t.closest("a[href^='http']");
  if (tagged && CTX[tagged.dataset.ctx]) own = CTX[tagged.dataset.ctx](tagged, e) || [];
  else if (typed && window.desktop && desktop.onContextParams && !typed.closest("[data-ctx]")) {
    // don't block this one: Electron then sends the misspelled word + suggestions (ctx:params) and we show the menu
    CTXP.pending = {x: e.clientX, y: e.clientY, typed, sel, at: Date.now()};
    clearTimeout(CTXP.timer); CTXP.timer = setTimeout(() => ctxTyped(null), 250);  // no answer → show it without suggestions
    return;
  }
  else if (typed) {
    typed.focus();
    const has = typed.value !== undefined ? typed.selectionStart !== typed.selectionEnd : !!sel;
    own = [{t: "Undo", i: "left", k: "Ctrl Z", run: () => ctxEdit("undo", typed)}, "-",
      {t: "Cut", i: "copy", k: "Ctrl X", off: !has, run: () => ctxEdit("cut", typed)}, {t: "Copy", i: "copy", k: "Ctrl C", off: !has, run: () => ctxEdit("copy", typed)},
      {t: "Paste", i: "copy", k: "Ctrl V", run: () => ctxEdit("paste", typed)}, {t: "Select all", i: "check", k: "Ctrl A", run: () => typed.select ? typed.select() : ctxEdit("selectAll", typed)},
      typeof dictate === "function" ? {t: "Dictate (speech to text)", i: "mic", run: () => dictate(typed)} : null].filter(Boolean);
  } else {
    if (link) own.push({t: "Open link in Daybook's browser", i: "globe", run: () => window.desktop ? bdNew("personal", link.href) : open(link.href, "_blank")},
      {t: "Open link in your normal browser", i: "ext", run: () => open(link.href, "_blank")}, {t: "Copy link", i: "copy", run: () => navigator.clipboard.writeText(link.href).then(() => toast("Link copied"))}, "-");
    if (sel) {
      const short = sel.length > 28 ? sel.slice(0, 28) + "…" : sel;
      own.push({t: "Copy", i: "copy", k: "Ctrl C", run: () => navigator.clipboard.writeText(sel).then(() => toast("Copied"))},
        {t: `Search the web for “${short}”`, i: "search", run: () => ctxSearchWeb(sel)},
        {t: "Save as a new note", i: "note", run: () => ctxSaveNote(sel)},
        {t: "Make it a reminder", i: "bell", run: () => { reminderModal(); setTimeout(() => { const i = $("#rm-nl"); if (i) { i.value = sel.slice(0, 200); i.dispatchEvent(new Event("input")); i.focus(); } }, 60); }},
        {t: "Ask AI about it", i: "chat", run: () => ctxAskAI(sel)}, "-");
    }
    const special = t.closest(".lpt") ? "lpt" : t.closest(".gcard,.grec") ? "gcard" : t.closest("#nlist .item") ? "note" : "";
    if (special) own.push(...CTX[special](t.closest(special === "lpt" ? ".lpt" : special === "gcard" ? ".gcard,.grec" : "#nlist .item")), "-");
    else {
      const row = t.closest(".rem, .item, .srow, .memo, .mi, .bd-tab, .wf, .cat, .tile, .card .row.li");
      if (row) { const a = ctxRowActions(row); if (a.length) own.push(...a, "-"); }
    }
  }
  const items = [...own, own.length ? "-" : null, ...ctxGeneral()].filter(x => x !== null);
  ctxShow(e.clientX, e.clientY, items);
  if (S.view === "browser" && window.bdSync) bdSync();  // the menu must not end up under a web page
});

// ---- spelling suggestions in Daybook's own text boxes ----
const CTXP = {pending: null, timer: 0};
function ctxTyped(params) {
  const p = CTXP.pending; if (!p) return; CTXP.pending = null; clearTimeout(CTXP.timer);
  const typed = p.typed; typed.focus();
  const has = typed.value !== undefined ? typed.selectionStart !== typed.selectionEnd : !!p.sel;
  const spell = params && params.misspelledWord ? [
    ...(params.suggestions.length ? params.suggestions.map(w => ({t: w, i: "check", run: () => desktop.edit("replaceMisspelling", w)})) : [{t: "No spelling suggestions", off: true}]),
    {t: `Add “${params.misspelledWord}” to dictionary`, i: "plus", run: () => { desktop.edit("addToDictionary", params.misspelledWord); toast("Added to your dictionary"); }}, "-"] : [];
  const items = [...spell, {t: "Undo", i: "left", k: "Ctrl Z", run: () => ctxEdit("undo", typed)}, "-",
    {t: "Cut", i: "copy", k: "Ctrl X", off: !has, run: () => ctxEdit("cut", typed)}, {t: "Copy", i: "copy", k: "Ctrl C", off: !has, run: () => ctxEdit("copy", typed)},
    {t: "Paste", i: "copy", k: "Ctrl V", run: () => ctxEdit("paste", typed)}, {t: "Select all", i: "check", k: "Ctrl A", run: () => typed.select ? typed.select() : ctxEdit("selectAll", typed)},
    typeof dictate === "function" ? {t: "Dictate (speech to text)", i: "mic", run: () => dictate(typed)} : null, "-", ...ctxGeneral()].filter(Boolean);
  ctxShow(p.x, p.y, items);
}
if (window.desktop && desktop.onContextParams) desktop.onContextParams(d => { if (CTXP.pending && d.isEditable) ctxTyped(d); });
