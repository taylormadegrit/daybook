// ================= LIBRARY: PDFs & books (all your folders) + Zotero sources =================
const PL = {tab: store.get("daybook-lib-tab", "pdfs"), items: [], folders: [], folder: "", q: "", sort: store.get("daybook-pdf-sort", "recent"), cur: null, poll: 0};
function libTabs() {
  return `<div class="lib-tabs seg">${[["pdfs", "book", "PDFs & books"], ["zotero", "note", "Zotero sources"]].map(([k, i, l]) => `<button class="${PL.tab === k ? "on" : ""}" onclick="PL.tab='${k}';store.set('daybook-lib-tab','${k}');renderResearch()">${ic(i)}${l}</button>`).join("")}</div>`;
}
async function renderPdfLibrary() {
  const host = $("#research");
  host.innerHTML = `<div class="lib-head">${libTabs()}
      <div class="gm-search lib-search">${ic("search")}<input id="pq2" placeholder="Search titles and the text inside your PDFs…" value="${esc(PL.q)}" oninput="PL.q=this.value;debounce('plq',plLoad,200)"></div>
      <select class="f" style="width:auto" onchange="PL.sort=this.value;store.set('daybook-pdf-sort',this.value);plLoad()">${[["recent", "Newest"], ["opened", "Recently opened"], ["name", "A → Z"], ["size", "Largest"]].map(([k, l]) => `<option value="${k}" ${PL.sort === k ? "selected" : ""}>${l}</option>`).join("")}</select>
      <span class="small muted" id="pl-state"></span></div>
    <div class="lib">
      <div class="zcol"><div class="grouph" style="margin-top:0">Folders</div><div id="pl-folders"></div>
        <button class="btn sm" style="margin-top:8px" onclick="plAddFolder()">${ic("plus")}Add a folder</button>
        <button class="btn sm ghost" style="margin-top:8px" onclick="api('/api/pdfs/scan',{method:'POST'}).then(()=>{toast('Rescanning…');plPoll()})">${ic("rep")}Rescan</button></div>
      <div class="zcol"><div class="pl-grid" id="pl-grid"></div></div>
    </div>`;
  paintIcons(host); plLoad();
}
async function plLoad() {
  const j = await api("/api/pdfs?" + new URLSearchParams({q: PL.q, folder: PL.folder, sort: PL.sort}));
  PL.items = j.items; PL.folders = j.folders;
  const st = j.state; $("#pl-state") && ($("#pl-state").textContent = st.scanning ? `Reading PDFs… ${st.done}/${st.total}` : `${j.items.length}${j.items.length >= 400 ? "+" : ""} files`);
  $("#pl-folders").innerHTML = `<div class="cat ${!PL.folder ? "on" : ""}" onclick="PL.folder='';plLoad()">${ic("book")}Everything</div>` + j.folders.map(f => `<div class="cat ${PL.folder === f.path ? "on" : ""}" title="${esc(f.path)}" onclick="PL.folder=${JSON.stringify(f.path).replace(/"/g, "&quot;")};plLoad()">📁 <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">${esc(f.name)}</span>
      <button class="iconbtn" title="Stop including this folder" onclick="event.stopPropagation();plRemoveFolder(${JSON.stringify(f.path).replace(/"/g, "&quot;")})">${ic("x")}</button></div>`).join("");
  $("#pl-grid").innerHTML = j.items.map(d => `<div class="pdf" onclick="plOpen(${d.id})" title="${esc(d.path)}">
      <div class="pcov">${d.thumb ? `<img src="/pdf-thumb/${d.id}" loading="lazy" alt="">` : `<div class="gph" style="--h:${gmHue(d.display)}"><span>${esc(d.display)}</span></div>`}${d.starred ? `<i class="pstar">★</i>` : ""}</div>
      <div class="pname">${esc(d.display)}</div><div class="pmeta">${d.pages ? d.pages + " pages · " : ""}${dayName(d.modified)}</div>
      ${d.snip ? `<div class="psnip">${esc(d.snip).replace(/\[/g, "<mark>").replace(/\]/g, "</mark>")}</div>` : ""}</div>`).join("")
    || `<div class="empty" style="grid-column:1/-1"><b>${PL.q ? "Nothing matches" : st.scanning ? "Reading your PDFs…" : "No PDFs here yet"}</b>${PL.q ? "Try other words." : "Add a folder where you keep PDFs and ebooks."}</div>`;
  if (st.scanning) plPoll();
}
function plPoll() { clearTimeout(PL.poll); PL.poll = setTimeout(() => S.view === "research" && PL.tab === "pdfs" && plLoad(), 2000); }
async function plAddFolder() { toast("Pick a folder in the window that just opened…"); const j = await api("/api/folders/pick", {method: "POST"}); if (!j.path) return;
  await api("/api/pdfs/folders", {method: "POST", body: {folders: [...PL.folders.map(f => f.path), j.path]}}); toast("Added — reading its PDFs…"); plLoad(); }
async function plRemoveFolder(p) { await api("/api/pdfs/folders", {method: "POST", body: {folders: PL.folders.map(f => f.path).filter(x => x !== p)}}); if (PL.folder === p) PL.folder = ""; plLoad(); }
function plOpen(id) {
  const d = PL.items.find(x => x.id === id); if (!d) return; PL.cur = d;
  modal(`<div class="pv-head"><div style="min-width:0;flex:1"><b class="pv-title">${esc(d.display)}</b><div class="small muted" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${d.author ? esc(d.author) + " · " : ""}${d.pages} pages · ${esc(d.path)}</div></div>
      <button class="btn sm" onclick="plAct(${id},'star').then(()=>{PL.cur.starred=!PL.cur.starred;toast(PL.cur.starred?'Starred':'Unstarred')})">★</button>
      <button class="btn sm" title="Summary + key points by your local AI, saved as a note" onclick="plNote(${id},this)">${ic("spark")}Summarize to note</button>
      <button class="btn sm" onclick="discordSend('file',${JSON.stringify(d.path).replace(/"/g, "&quot;")})">${ic("send")}Discord</button>
      <button class="btn sm" title="Add to your Zotero library (Zotero reads its details)" onclick="plZotero(${id},this)">${ic("book")}Zotero</button>
      <button class="btn sm ghost" onclick="plAct(${id},'reveal')">${ic("ext")}Folder</button>
      <button class="iconbtn" onclick="closeModal()">${ic("x")}</button></div>
    <iframe class="pv-frame" src="/pdf-file/${id}#view=FitH" title="PDF"></iframe>`, "xl");
  $(".modal").classList.add("pdfmodal");
}
const plAct = (id, a) => api(`/api/pdfs/${id}/${a}`, {method: "POST"});
async function plNote(id, b) { b.disabled = true; b.textContent = "Reading…"; try { const j = await plAct(id, "note"); closeModal(); toast("Summary saved to Notes ✓"); openNote(j.note_id); } catch (e) { toast(e.message); b.disabled = false; b.textContent = "Summarize to note"; } }
async function plZotero(id, b) { b.disabled = true; try { await plAct(id, "zotero"); toast("Sent to Zotero ✓ — it's reading the details"); } catch (e) { toast(/refused|URLError|10061/.test(e.message) ? "Open Zotero first" : e.message); } b.disabled = false; }
