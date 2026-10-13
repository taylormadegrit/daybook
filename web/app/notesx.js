// ================= NOTES extras: template picker, collapsible panels, focus mode =================
const TP = {group: "Suggested", sel: "blank", q: "", sugg: []};
const BLANK = {key: "blank", name: "Blank note", icon: "📝", group: "", category: "", best: "Anything — just start typing", why: "No structure. You can still let the local AI organize it afterwards.", body: ""};
function fillTpl(body) {
  const d = new Date();
  return body.replace(/\{date\}/g, d.toLocaleDateString([], {month: "short", day: "numeric", year: "numeric"}))
    .replace(/\{time\}/g, d.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})).replace(/\{weekday\}/g, d.toLocaleDateString([], {weekday: "long"}));
}
function tplSuggest(text) { // instant local matching: "discord call with the team" → Discord / voice call
  const words = text.toLowerCase().match(/[a-z0-9-]+/g) || [];
  return S.meta.templates.map(t => ({t, s: words.reduce((a, w) => a + (w.length > 2 && (t.words + " " + t.name.toLowerCase()).includes(w) ? 1 : 0), 0)}))
    .filter(x => x.s > 0).sort((a, b) => b.s - a.s).slice(0, 4).map(x => x.t.key);
}
function suggestedNow() { // what fits right now: time of day + what's on the schedule
  const h = new Date().getHours(), out = [];
  if (h >= 19 || h < 4) out.push("journal"); if (h >= 4 && h < 9) out.push("checklist");
  if (new Date().getDay() === 0) out.push("weekly");
  out.push("meeting", "discord", "video", "brainstorm");
  return [...new Set(out)].slice(0, 6);
}
async function templateModal() {
  closeMenu(); if (!S.meta.templates || !Array.isArray(S.meta.templates)) await loadMeta();
  TP.q = ""; TP.sugg = suggestedNow(); TP.group = "Suggested"; TP.sel = TP.sugg[0] || "blank";
  modal(`<h2>${ic("note", "i")}New note — pick a format<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="tsearch"><input class="f" id="tp-q" placeholder="What are you doing? e.g. “discord call about uploads”, “watching a tutorial”, “planning my week”" oninput="tpSearch(this.value)">
      <button class="btn" onclick="newNote('blank')">${ic("plus")}Blank note</button></div>
    <div class="tplx"><div class="tg" id="tp-g"></div><div class="tc" id="tp-c"></div><div class="tprev" id="tp-p"></div></div>`, "xl");
  tpRender(); setTimeout(() => $("#tp-q").focus(), 40);
}
function tpSearch(v) { TP.q = v; const s = tplSuggest(v); if (v.trim()) { TP.sugg = s; TP.group = "Suggested"; if (s[0]) TP.sel = s[0]; } else { TP.sugg = suggestedNow(); } tpRender(); }
function tpRender() {
  const all = S.meta.templates, groups = ["Suggested", "All", ...(S.meta.template_groups || [])];
  $("#tp-g").innerHTML = groups.map(g => `<div class="${TP.group === g ? "on" : ""}" onclick="TP.group='${g}';tpRender()">${g === "Suggested" ? (TP.q ? "✨ Best matches" : "✨ Suggested now") : g}</div>`).join("");
  let list = TP.group === "Suggested" ? TP.sugg.map(k => all.find(t => t.key === k)).filter(Boolean) : TP.group === "All" ? all : all.filter(t => t.group === TP.group);
  if (TP.group === "Suggested" && !list.length) list = all.slice(0, 4);
  $("#tp-c").innerHTML = [BLANK, ...list].map((t, i) => `<div class="tcard ${TP.sel === t.key ? "on" : ""}" onclick="TP.sel='${t.key}';tpRender()" ondblclick="newNote('${t.key}')">
    ${TP.group === "Suggested" && i === 1 ? `<span class="sug">best fit</span>` : ""}<div class="em">${t.icon}</div><b>${esc(t.name)}</b><span>${esc(t.best)}</span></div>`).join("");
  const t = TP.sel === "blank" ? BLANK : all.find(x => x.key === TP.sel) || BLANK;
  $("#tp-p").innerHTML = `<div class="ph"><b>${t.icon} ${esc(t.name)}</b><div class="why"><b>Best for:</b> ${esc(t.best)}</div><div class="why"><b>Why this format:</b> ${esc(t.why)}</div></div>
    <div class="pb md">${t.body ? md(fillTpl(t.body)) : `<div class="muted">An empty page.</div>`}</div>
    <div class="pf"><button class="btn pri" onclick="newNote('${t.key}')">${ic("check")}Use this format</button><span class="small muted" style="align-self:center">or double-click a card</span></div>`;
}
async function newNote(key) {
  closeModal(); if (S.view !== "notes") go("notes");
  const t = key && key !== "blank" ? S.meta.templates.find(x => x.key === key) : null;
  S.cur = await api("/api/notes", {method: "POST", body: {title: "", category: t ? t.category : "", body: t ? fillTpl(t.body) : "", organize: false}});
  renderEditor(); loadNotes();
  if (t) { // cursor goes to the first empty field (e.g. "**Attendees:**" or the first "- ")
    const b = $("#n-body"), lines = b.value.split("\n"); let pos = b.value.length, acc = 0;
    for (const ln of lines) { acc += ln.length; if (/:\*\*\s*$|^-\s*$|^\d+\.\s*$|^- \[ \]\s*$/.test(ln)) { pos = acc; break; } acc += 1; }
    b.focus(); b.setSelectionRange(pos, pos); if (!/\s$/.test(b.value.slice(0, pos))) { b.setRangeText(" ", pos, pos, "end"); }
  } else $("#n-title").focus();
}

// ---------- collapsible panels ----------
const NP = {f: store.get("daybook-np-f", "1") === "1", l: store.get("daybook-np-l", "1") === "1"};
function notesPanels() {
  const n = $("#v-notes .notes"); if (!n) return;
  n.classList.toggle("nf", !NP.f); n.classList.toggle("nl", !NP.l);
  $$(".np-f").forEach(b => b.classList.toggle("on", NP.f)); $$(".np-l").forEach(b => b.classList.toggle("on", NP.l));
}
function togglePanel(k) {
  if (k === "f" && innerWidth <= 1150) { const n = $("#v-notes .notes"); n && n.classList.toggle("fopen"); return; }  // narrow window: filters slide over
  NP[k] = !NP[k]; store.set("daybook-np-" + k, NP[k] ? "1" : "0"); notesPanels(); }
function focusMode() { // hide filters + list + the main sidebar → the editor gets the whole window
  const on = NP.f || NP.l || !$(".app").classList.contains("slim");
  NP.f = NP.l = !on; store.set("daybook-np-f", NP.f ? "1" : "0"); store.set("daybook-np-l", NP.l ? "1" : "0");
  setSlim(on); notesPanels(); toast(on ? "Focus mode — Ctrl . to bring the panels back" : "Panels back");
}
function setSlim(on) { $(".app").classList.toggle("slim", on); store.set("daybook-slim", on ? "1" : "0"); }
function edToolbar() { // buttons on top of the note editor
  return `<div class="edbar"><button class="iconbtn np-f ${NP.f ? "on" : ""}" title="Show/hide categories & filters" onclick="togglePanel('f')">${ic("sidebar")}</button>
    <button class="iconbtn np-l ${NP.l ? "on" : ""}" title="Show/hide the note list" onclick="togglePanel('l')">${ic("list")}</button>
    <button class="iconbtn" title="Focus mode — full workspace (Ctrl .)" onclick="focusMode()">${ic("expand")}</button>
    <span class="sp"></span><span class="small muted" id="n-wc"></span></div>`;
}
function wordCount() { const b = $("#n-body"); if (b && $("#n-wc")) { const w = (b.value.match(/\S+/g) || []).length; $("#n-wc").textContent = `${w} word${w === 1 ? "" : "s"} · ~${Math.max(1, Math.round(w / 230))} min read`; } }
