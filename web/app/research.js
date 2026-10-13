// ================= RESEARCH: your Zotero library inside Daybook =================
const ZR = {st: null, items: [], cur: null, col: "", q: "", style: null, mode: "live"};
const zStyle = () => ZR.style || store.get("daybook-cite-style", "apa");
async function renderResearch() {
  if (PL.tab === "pdfs") return renderPdfLibrary();
  if (PL.tab === "links") return renderLinks();
  ZR.st = await api("/api/zotero");
  const s = ZR.st, host = $("#research");
  if (!s.installed) { host.innerHTML = `<div class="lib-head">${libTabs()}</div><div class="empty" style="padding-top:12vh"><b>Zotero isn't installed</b>Get it free from <a href="https://www.zotero.org/download/" target="_blank" rel="noopener">zotero.org/download</a>, then come back.</div>`; return; }
  host.innerHTML = `<div class="lib-head">${libTabs()}</div><div class="zr">
    <div class="zcol">
      <button class="btn pri" style="width:100%;justify-content:center" onclick="zAddModal()">${ic("plus")}Add a source</button>
      ${s.running ? "" : `<div class="obs-card" style="margin-top:10px"><b>Zotero is closed</b><p class="small muted">Search still works from your saved library. Open Zotero for citations, PDFs and adding sources.</p><button class="btn sm" onclick="zLaunch()">${ic("play")}Open Zotero</button></div>`}
      ${s.running && !s.api ? `<div class="obs-card" style="margin-top:10px;border-color:var(--warn)"><b>One setting needed</b><p class="small muted">${esc(s.api_error || "")}</p></div>` : ""}
      <div class="grouph">Library · ${s.items} item${s.items === 1 ? "" : "s"}</div>
      <div class="cat ${!ZR.col ? "on" : ""}" onclick="ZR.col='';zLoad()">${ic("note")}My Library</div>
      ${(s.collections || []).map(c => `<div class="cat ${ZR.col === c.key ? "on" : ""}" style="${c.parent ? "padding-left:26px" : ""}" onclick="ZR.col='${c.key}';zLoad()">📁 ${esc(c.name)}<span class="c">${c.count}</span></div>`).join("")}
      <div class="grouph">Citation style</div>
      <select class="f" onchange="ZR.style=this.value;store.set('daybook-cite-style',this.value);zLoad();ZR.cur&&zOpen(ZR.cur.key)">${s.styles.map(([k, n]) => `<option value="${k}" ${k === zStyle() ? "selected" : ""}>${n}</option>`).join("")}</select>
      <div class="muted small" style="margin-top:14px">Library: <code>${esc(s.data_dir)}</code></div>
    </div>
    <div class="zcol"><div class="row" style="flex-wrap:nowrap;gap:6px;margin-bottom:8px"><input class="f" id="zq" placeholder="Search titles, authors, notes and PDFs…" value="${esc(ZR.q)}" oninput="ZR.q=this.value;debounce('zq',zLoad,250)">
      <button class="iconbtn" title="Add a source (DOI, ISBN, arXiv, BibTeX)" onclick="zAddModal()">${ic("plus")}</button></div>
      <div id="zmode" class="small muted" style="margin-bottom:6px"></div><div id="zlist"></div></div>
    <div class="zcol"><div class="card" id="zed" style="min-height:100%"><div class="empty"><b>Pick a source</b>See its citation, abstract, notes and PDFs — save it as a Daybook note or cite it in one.</div></div></div>
  </div>`;
  paintIcons(host); zLoad();
}
async function zLoad() {
  const j = await api(`/api/zotero/items?` + new URLSearchParams({q: ZR.q, collection: ZR.col, style: zStyle()}));
  ZR.items = j.items; ZR.mode = j.mode;
  $("#zmode").textContent = j.mode === "offline" ? "Zotero is closed — showing your saved library (read-only)" : "";
  $("#zlist").innerHTML = j.items.map(i => `<div class="item ${ZR.cur && ZR.cur.key === i.key ? "on" : ""}" onclick="zOpen('${i.key}')">
      <div class="ti">${i.icon} ${esc(i.title)}</div><div class="row small muted" style="gap:6px">${esc(i.authors)}${i.year ? " · " + i.year : ""}${i.venue ? ` · <i>${esc(i.venue)}</i>` : ""}</div>
      ${i.tags.length ? `<div class="tags" style="margin-top:4px">${i.tags.slice(0, 4).map(t => `<span class="tag">#${esc(t)}</span>`).join("")}</div>` : ""}</div>`).join("")
    || `<div class="empty"><b>${ZR.q ? "No matches" : "Your library is empty"}</b>${ZR.q ? "Try other words." : "Press Add a source — paste a DOI, ISBN, arXiv link or BibTeX."}</div>`;
}
async function zOpen(key) {
  let it; try { it = await api(`/api/zotero/items/${key}?style=${zStyle()}`); } catch (e) { toast(e.message); return; }
  ZR.cur = it; $$("#zlist .item").forEach(x => x.classList.toggle("on", x.getAttribute("onclick") === `zOpen('${key}')`));
  $("#zed").innerHTML = `<div class="small muted">${it.icon} ${esc(it.type.replace(/([A-Z])/g, " $1").toLowerCase())}${it.date ? " · " + esc(it.date) : ""}</div>
    <h2 style="margin:6px 0 4px;font-size:21px">${esc(it.title)}</h2><div class="muted">${esc(it.creators.join(", "))}${it.venue ? ` — <i>${esc(it.venue)}</i>` : ""}</div>
    <div class="cite-box"><div class="row" style="flex-wrap:nowrap"><b class="small">In-text</b><code style="flex:1">${esc(it.citation)}</code><button class="btn sm" onclick="zCopy(ZR.cur.citation)">${ic("copy")}Copy</button></div>
      <div class="row" style="flex-wrap:nowrap;margin-top:8px;align-items:flex-start"><b class="small">Reference</b><span style="flex:1;font-size:13px">${esc(it.bib_text)}</span><button class="btn sm" onclick="zCopy(ZR.cur.bib_text)">${ic("copy")}Copy</button></div></div>
    <div class="row" style="margin:12px 0;gap:6px">
      <button class="btn pri" onclick="zNote('${key}')">${ic("note")}Save as Daybook note</button>
      <button class="btn" onclick="api('/api/zotero/open',{method:'POST',body:{key:'${key}'}})">${ic("ext")}Open in Zotero</button>
      ${it.url ? `<a class="btn ghost" href="${esc(it.url)}" target="_blank" rel="noopener">${ic("globe")}Source</a>` : ""}
      <button class="btn ghost" onclick="zExport('${key}')">BibTeX</button></div>
    ${it.files.length ? `<div class="grouph">Files</div>${it.files.map(f => `<div class="cat" onclick='${f.path ? `api("/api/zotero/open",{method:"POST",body:{path:${JSON.stringify(f.path)}}})` : f.url ? `window.open(${JSON.stringify(f.url)})` : ""}'>${/pdf/.test(f.type) ? "📕" : "📎"} ${esc(f.title)}${f.path ? "" : `<span class="c">not downloaded</span>`}</div>`).join("")}` : ""}
    ${it.abstract ? `<div class="grouph">Abstract</div><div style="font-size:13.5px;line-height:1.6">${esc(it.abstract)}</div>` : ""}
    ${it.notes.length ? `<div class="grouph">Zotero notes</div>${it.notes.map(n => `<div class="znote">${esc(n)}</div>`).join("")}` : ""}
    ${it.tags.length ? `<div class="grouph">Tags</div><div class="tags">${it.tags.map(t => `<span class="tag" onclick="ZR.q='${esc(t)}';$('#zq').value=ZR.q;zLoad()">#${esc(t)}</span>`).join("")}</div>` : ""}`;
  paintIcons($("#zed"));
}
function zCopy(t) { navigator.clipboard.writeText(t); toast("Copied"); }
async function zExport(key) { const j = await api("/api/zotero/export", {method: "POST", body: {keys: [key], format: "bibtex"}}); zCopy(j.text); toast("BibTeX copied"); }
async function zNote(key) { const j = await api("/api/zotero/note", {method: "POST", body: {key, style: zStyle()}}); toast("Saved to Notes ✓"); openNote(j.note_id); }
async function zLaunch() { await api("/api/zotero/launch", {method: "POST"}); toast("Opening Zotero…"); setTimeout(renderResearch, 6000); }
function zAddModal() {
  modal(`<h2>${ic("plus", "i")}Add a source to Zotero<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <textarea class="f" id="z-add" rows="4" placeholder="Paste any of these:
• a DOI or doi.org link — 10.1038/nature14539
• an ISBN — 978-0-7432-7356-5
• an arXiv ID or link — arxiv.org/abs/1706.03762
• BibTeX or RIS text"></textarea>
    <div class="muted small" style="margin-top:6px">Details are looked up (doi.org · arXiv · Open Library) and saved into Zotero — into whatever collection is selected in Zotero.</div>
    <div class="row" style="margin-top:12px"><button class="btn pri" id="z-go" onclick="zAdd()">${ic("plus")}Add</button><span class="small muted" id="z-msg"></span></div>`);
  setTimeout(() => $("#z-add").focus(), 30);
}
async function zAdd() {
  const t = $("#z-add").value.trim(); if (!t) return; $("#z-go").disabled = true; $("#z-msg").textContent = "Looking it up…";
  try { const j = await api("/api/zotero/add", {method: "POST", body: {text: t}}); closeModal(); toast(`Added ${j.items.length} item${j.items.length === 1 ? "" : "s"} (${j.what}) ✓`);
    if (S.view === "research") { await renderResearch(); j.items[0] && zOpen(j.items[0].key); } }
  catch (e) { $("#z-msg").textContent = e.message; $("#z-go").disabled = false; }
}
// ---------- cite from a note ----------
function citeModal() {
  if (!S.cur) return;
  modal(`<h2>${ic("note", "i")}Cite a source<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <input class="f" id="cq" placeholder="Search your Zotero library…" oninput="debounce('cq',citeSearch,250)">
    <div id="cres" style="max-height:50vh;overflow:auto;margin-top:10px"></div>
    <div class="muted small" style="margin-top:8px">Inserts the in-text citation where your cursor was and adds the full reference under “References” at the end of the note.</div>`, true);
  ZR.caret = ($("#n-body") || {}).selectionStart; citeSearch(); setTimeout(() => $("#cq").focus(), 30);
}
async function citeSearch() {
  const j = await api("/api/zotero/items?" + new URLSearchParams({q: $("#cq").value, style: zStyle()}));
  $("#cres").innerHTML = j.items.map(i => `<div class="cat" onclick="citeInsert('${i.key}')">${i.icon}<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><b>${esc(i.title)}</b> <span class="muted">${esc(i.authors)} ${i.year}</span></span></div>`).join("")
    || `<div class="empty">${j.mode === "offline" ? "Open Zotero to cite" : "Nothing found"}</div>`;
}
async function citeInsert(key) {
  let it; try { it = await api(`/api/zotero/items/${key}?style=${zStyle()}`); } catch (e) { return toast(e.message); }
  closeModal(); const b = $("#n-body"); if (!b) return;
  const pos = ZR.caret ?? b.value.length; let v = b.value.slice(0, pos) + (/\s$/.test(b.value.slice(0, pos)) || !pos ? "" : " ") + it.citation + b.value.slice(pos);
  if (!v.includes(it.bib_text)) v = v.replace(/\s*$/, "") + (/\n## References\n/.test(v) ? "\n" : "\n\n## References\n") + "- " + it.bib_text + "\n";
  b.value = v; b.dispatchEvent(new Event("input")); saveNote(false); toast("Cited ✓");
}
// ---------- home widget ----------
async function researchWidget() {
  const el = $("#w-research"); if (!el) return;
  const j = await api("/api/zotero/items?limit=5");
  el.innerHTML = `<div class="row" style="flex-wrap:nowrap;margin-bottom:8px"><input class="f" placeholder="Search your library… Enter" onkeydown="if(event.key==='Enter'){ZR.q=this.value;go('research')}"><button class="btn" onclick="go('research');setTimeout(zAddModal,400)">${ic("plus")}</button></div>`
    + (j.items.slice(0, 5).map(i => `<div class="cat" onclick="go('research');setTimeout(()=>zOpen('${i.key}'),500)">${i.icon}<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(i.title)}</span><span class="c">${i.year}</span></div>`).join("") || `<div class="muted small">No sources yet</div>`);
}
