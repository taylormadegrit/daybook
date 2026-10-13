// ================= SAVED LINKS (Library → Saved links) + one-click saving from Daybook's browser =================
const LK = {items: [], cols: [], col: "", q: "", kind: store.get("daybook-links-kind", ""), saved: {}};
const lkOpenUrl = (url, id) => { if (id) api(`/api/links/${id}`, {method: "PATCH", body: {opened: 1}}).catch(() => {}); window.desktop ? bdNew("personal", url) : open(url, "_blank"); };
async function renderLinks() {
  const host = $("#research");
  host.innerHTML = `<div class="lib-head">${libTabs()}
      <div class="gm-search lib-search">${ic("search")}<input id="lkq" placeholder="Search saved videos and pages…" value="${esc(LK.q)}" oninput="LK.q=this.value;debounce('lkq',lkLoad,180)"></div>
      <div class="seg sm">${[["", "All"], ["youtube", "YouTube"], ["web", "Pages"]].map(([k, l]) => `<button class="${LK.kind === k ? "on" : ""}" onclick="LK.kind='${k}';store.set('daybook-links-kind','${k}');renderLinks()">${l}</button>`).join("")}</div>
      <button class="btn sm" onclick="lkAddModal()">${ic("plus")}Add a link</button></div>
    <div class="lib">
      <div class="zcol"><div class="grouph" style="margin-top:0">Collections</div><div id="lk-cols"></div>
        <button class="btn sm" style="margin-top:8px" onclick="lkNewCollection()">${ic("plus")}New collection</button>
        <div class="muted small" style="margin-top:12px">Save from the browser with the ☆ button, <b>Ctrl D</b>, or right-click → Save to Library. Drag a card onto a collection to file it.</div></div>
      <div class="zcol"><div class="lk-grid" id="lk-grid"></div></div>
    </div>`;
  paintIcons(host); lkLoad();
}
async function lkLoad() {
  const qs = new URLSearchParams({q: LK.q, collection: LK.col, kind: LK.kind});
  const j = await api("/api/links?" + qs); LK.items = j.items; LK.cols = j.collections;
  const total = LK.cols.reduce((a, c) => a + c.count, 0), none = (LK.cols.find(c => !c.name) || {}).count || 0;
  const colRow = (key, name, n, icon) => `<div class="cat ${LK.col === key ? "on" : ""}" data-col="${esc(key)}" onclick="LK.col=${JSON.stringify(key).replace(/"/g, "&quot;")};lkLoad()" ${key && key !== "_none" ? `data-ctx="lkcol"` : ""}>${ic(icon)}<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(name)}</span><span class="c">${n}</span></div>`;
  $("#lk-cols").innerHTML = colRow("", "All links", total, "list") + (none ? colRow("_none", "Unsorted", none, "layers") : "")
    + LK.cols.filter(c => c.name).map(c => colRow(c.name, c.name, c.count, "folder")).join("")
    + (LK.extraCol && !LK.cols.some(c => c.name === LK.extraCol) ? colRow(LK.extraCol, LK.extraCol, 0, "folder") : "");
  paintIcons($("#lk-cols"));
  $$("#lk-cols .cat[data-col]").forEach(el => {
    if (!el.dataset.col || el.dataset.col === "") return;
    el.addEventListener("dragover", e => { if (e.dataTransfer.types.includes("x-daybook-link")) { e.preventDefault(); el.classList.add("drop-on"); } });
    el.addEventListener("dragleave", () => el.classList.remove("drop-on"));
    el.addEventListener("drop", async e => { e.preventDefault(); el.classList.remove("drop-on"); const id = +e.dataTransfer.getData("x-daybook-link"); const c = el.dataset.col === "_none" ? "" : el.dataset.col; await lkSet(id, {collection: c}); toast(c ? `Filed in “${c}”` : "Moved to Unsorted"); });
  });
  $("#lk-grid").innerHTML = LK.items.map(l => `<div class="lk" draggable="true" data-id="${l.id}" data-ctx="link" onclick="lkOpenUrl(${JSON.stringify(l.url).replace(/"/g, "&quot;")},${l.id})" title="${esc(l.title)}\n${esc(l.url)}">
      <div class="lk-img">${l.thumb ? `<img src="${l.thumb}" loading="lazy" alt="">` : `<span>${esc((l.site || "?")[0].toUpperCase())}</span>`}${l.kind === "youtube" ? `<i class="lk-yt">▶</i>` : ""}</div>
      <div class="lk-b"><b>${esc(l.title)}</b><span>${esc(l.channel || l.site)}</span>
        <div class="lk-meta">${l.collection ? `<span class="badge">${esc(l.collection)}</span>` : ""}${l.note_id ? `<span class="badge" title="Attached to a note">${ic("note")}note</span>` : ""}${l.starred ? "⭐" : ""}</div></div>
      <button class="iconbtn lk-more" title="More" onclick="event.stopPropagation();lkMenu(event,${l.id})">${ic("list")}</button></div>`).join("")
    || `<div class="empty" style="grid-column:1/-1"><b>${LK.q || LK.col ? "Nothing here yet" : "No saved links yet"}</b>Find a video or page in Daybook's Browser and press ☆ (or Ctrl D) — it lands here with its real title, ready to open in one click.</div>`;
  paintIcons($("#lk-grid"));
  $$("#lk-grid .lk").forEach(el => el.addEventListener("dragstart", e => { e.dataTransfer.setData("x-daybook-link", el.dataset.id); e.dataTransfer.setData("text/uri-list", LK.items.find(x => x.id === +el.dataset.id).url); }));
}
async function lkSet(id, body) { await api(`/api/links/${id}`, {method: "PATCH", body}); if (S.view === "research" && PL.tab === "links") lkLoad(); }
function lkMenu(e, id) { const b = e.currentTarget.getBoundingClientRect(); ctxShow(b.left - 180, b.bottom + 4, CTX.link($(`.lk[data-id="${id}"]`))); }
function lkColItems(apply, current) {
  return [...LK.cols.filter(c => c.name).map(c => ({t: c.name, i: c.name === current ? "check" : "folder", run: () => apply(c.name)})),
    current ? {t: "Unsorted", i: "layers", run: () => apply("")} : null, "-", {t: "New collection…", i: "plus", run: () => { const n = prompt("Name for the new collection (e.g. Editing tips, Study, Ideas)"); if (n && n.trim()) apply(n.trim()); }}].filter(Boolean);
}
async function lkAttachNote(id) {
  modal(`<h2>${ic("note", "i")}Attach to a note<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <input class="f" id="lkn-q" placeholder="Search your notes…" oninput="debounce('lkn',()=>lkNoteList(${id}),150)"><div id="lkn-res" style="margin-top:10px;max-height:50vh;overflow:auto"></div>
    <div class="row" style="margin-top:12px"><button class="btn ghost" onclick="lkSet(${id},{note_id:null});closeModal();toast('Detached from its note')">Detach</button></div>`);
  lkNoteList(id); setTimeout(() => $("#lkn-q").focus(), 30);
}
async function lkNoteList(id) {
  const q = ($("#lkn-q") || {}).value || ""; const ns = await api("/api/notes?q=" + encodeURIComponent(q));
  $("#lkn-res").innerHTML = (ns.notes || ns).slice(0, 40).map(n => `<div class="cat" onclick="lkSet(${id},{note_id:${n.id}});closeModal();toast('Attached to “${esc((n.title || "note").replace(/'/g, ""))}”')">${ic("note")}<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(n.title || "Untitled")}</span><span class="c">${esc(n.category || "")}</span></div>`).join("") || `<div class="muted small">No notes found</div>`;
  paintIcons($("#lkn-res"));
}
function lkNewCollection() { const n = prompt("Name for the new collection (e.g. Editing tips, Study, Ideas)"); if (!n || !n.trim()) return; LK.extraCol = n.trim(); LK.col = n.trim(); lkLoad(); toast("Drag links onto it, or use ⋯ → Collection"); }
function lkAddModal() {
  modal(`<h2>${ic("plus", "i")}Add a link<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="frm"><label>Address</label><input class="f" id="lka-u" placeholder="Paste a YouTube or web address"><label>Collection (optional)</label>
    <input class="f" id="lka-c" list="lka-cl" placeholder="e.g. Editing tips" value="${esc(LK.col && LK.col !== "_none" ? LK.col : "")}"><datalist id="lka-cl">${LK.cols.filter(c => c.name).map(c => `<option value="${esc(c.name)}">`).join("")}</datalist></div>
    <div class="row" style="margin-top:14px"><button class="btn pri" onclick="lkAddSave()">${ic("check")}Save</button></div>`);
  setTimeout(() => $("#lka-u").focus(), 30);
}
async function lkAddSave() {
  let u = $("#lka-u").value.trim(); if (!u) return; if (!/^https?:\/\//i.test(u)) u = "https://" + u;
  try { await api("/api/links", {method: "POST", body: {url: u, collection: $("#lka-c").value.trim()}}); closeModal(); toast("Saved — fetching its title…"); setTimeout(lkLoad, 1500); lkLoad(); } catch (e) { toast(e.message); }
}
CTX.link = el => {
  const id = +el.dataset.id, l = LK.items.find(x => x.id === id); if (!l) return [];
  return [{h: l.title.slice(0, 40)}, {t: "Open in Daybook's browser", i: "globe", run: () => lkOpenUrl(l.url, id)},
    {t: "Open in your normal browser", i: "ext", run: () => open(l.url, "_blank")}, {t: "Copy link", i: "copy", run: () => navigator.clipboard.writeText(l.url).then(() => toast("Link copied"))}, "-",
    {t: "Collection", i: "folder", sub: lkColItems(c => lkSet(id, {collection: c}).then(() => toast(c ? `Filed in “${c}”` : "Moved to Unsorted")), l.collection)},
    {t: l.note_id ? "Attached note…" : "Attach to a note…", i: "note", run: () => lkAttachNote(id)},
    l.note_id ? {t: "Open its note", i: "note", run: () => { go("notes"); setTimeout(() => openNote(l.note_id), 300); }} : null,
    {t: l.starred ? "Unstar" : "Star (keeps it at the top)", i: "spark", run: () => lkSet(id, {starred: l.starred ? 0 : 1})},
    {t: "Rename", i: "pen", run: () => { const n = prompt("Title", l.title); if (n && n.trim()) lkSet(id, {title: n.trim()}); }}, "-",
    {t: "Delete", i: "trash", danger: true, run: () => api(`/api/links/${id}`, {method: "DELETE"}).then(() => { toast("Link removed"); lkLoad(); })}].filter(Boolean);
};
CTX.lkcol = el => { const c = el.dataset.col; return [{t: "Rename collection", i: "pen", run: async () => {
  const n = prompt("New name", c); if (!n || !n.trim() || n.trim() === c) return;
  const j = await api("/api/links?" + new URLSearchParams({collection: c})); for (const l of j.items) await api(`/api/links/${l.id}`, {method: "PATCH", body: {collection: n.trim()}}); LK.col = n.trim(); lkLoad(); }}]; };
// ---- saving from the browser ----
async function bdSaveLink(id) {
  const p = BD.panes.find(x => x.id === id); if (!p || !/^https?:/.test(p.url)) return toast("Open a web page first");
  try {
    const j = await api("/api/links", {method: "POST", body: {url: p.url, title: p.title}});
    LK.saved[p.url] = j.link.id; bdPaint();
    const b = $(`.bd-pane[data-id="${id}"] [data-a="save"]`), r = b ? b.getBoundingClientRect() : {left: innerWidth / 2, bottom: 120};
    if (!LK.cols.length) { try { LK.cols = (await api("/api/links?kind=none")).collections; } catch (e) {} }
    ctxShow(r.left - 200, r.bottom + 6, [{h: j.new ? "Saved to Library ✓" : "Already in your Library ✓"},
      {t: "Put it in a collection", i: "folder", sub: lkColItems(c => lkSet(j.link.id, {collection: c}).then(() => toast(c ? `Filed in “${c}”` : "Unsorted")), j.link.collection)},
      {t: "Attach to a note…", i: "note", run: () => lkAttachNote(j.link.id)},
      {t: "Open the Library", i: "book", run: () => { PL.tab = "links"; store.set("daybook-lib-tab", "links"); go("research"); }}]);
  } catch (e) { toast(e.message); }
}
async function bdCheckSaved(url) {
  if (!/^https?:/.test(url) || url in LK.saved) return;
  LK.saved[url] = null;
  try { const j = await api("/api/links/check?url=" + encodeURIComponent(url)); LK.saved[url] = j.saved ? j.id : null; if (j.saved) bdPaint(); } catch (e) {}
}

// ================= Settings → Browser & privacy =================
async function renderPrivacy() {
  const el = $("#privacyset"); if (!el) return;
  if (!window.desktop || !desktop.privacy) { el.innerHTML = `<div class="muted small">Open the Daybook desktop app to manage browser privacy and make Daybook your default browser.</div>`; return; }
  const [pv, db, ab] = await Promise.all([desktop.privacy(), desktop.defaultBrowser(), desktop.browser.adblock()]);
  const profs = webProfiles();
  el.innerHTML = `<div class="srow"><div class="d"><b>Default browser</b><span>${db.isDefault ? "Daybook is your default browser — links from other apps open here, in your " + esc(bdProf(pv.linkProfile).name) + " profile."
        : db.registered ? "Daybook is available as a browser. Pick it under <b>Web browser</b> in the Windows window that opens." : "Let links from email, Discord and other apps open in Daybook's browser."}</span></div>
      ${db.isDefault ? `<span class="badge" style="color:var(--ok)">${ic("check")}Default</span>` : `<button class="btn pri" onclick="setDefaultBrowser()">${ic("globe")}Make Daybook my default browser</button>`}</div>
    <div class="srow"><div class="d"><b>Open outside links in</b><span>Which browser profile gets links from other apps</span></div>
      <select class="f" style="width:auto" onchange="desktop.defaultBrowser({linkProfile:this.value}).then(()=>toast('Saved ✓'))">${profs.map(p => `<option value="${p.id}" ${p.id === pv.linkProfile ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></div>
    <div class="srow"><div class="d"><b>Block ads &amp; trackers</b><span>${ab.ready ? `${(ab.blocked || 0).toLocaleString()} blocked since Daybook started · YouTube ads included` : "Loading block lists…"}</span></div>
      <button class="sw ${ab.on ? "on" : ""}" onclick="desktop.browser.adblock(${!ab.on}).then(renderPrivacy)"></button></div>
    <div class="srow"><div class="d"><b>Ask sites not to track or sell my data</b><span>Sends Do Not Track and Global Privacy Control with every page</span></div>
      <button class="sw ${pv.signals ? "on" : ""}" onclick="desktop.privacy({signals:${!pv.signals}}).then(renderPrivacy)"></button></div>
    <div class="srow"><div class="d"><b>Clear browsing data</b><span>History, cookies, logins, cache and site permissions for one profile</span></div>
      <select class="f" style="width:auto" id="pv-prof">${profs.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}</select>
      <button class="btn ghost danger" onclick="clearBrowsing(this)">${ic("trash")}Clear</button></div>
    <div class="srow"><div class="d"><b>Site permissions</b><span>Location, camera and mic answers you gave sites — forget them all so sites ask again</span></div>
      <button class="btn" onclick="desktop.privacy({forgetPermissions:true}).then(()=>toast('Sites will ask again'))">Forget all</button></div>
    <div class="muted small" style="margin-top:8px">Everything Daybook stores — notes, reminders, saved links, browsing data — stays on this PC. Nothing is uploaded.</div>`;
  paintIcons(el);
}
async function setDefaultBrowser() { await desktop.defaultBrowser("register"); toast("In the Windows window: click the current Web browser and choose Daybook"); setTimeout(renderPrivacy, 1500); }
async function clearBrowsing(btn) {
  if (!btn.dataset.sure) { btn.dataset.sure = 1; btn.innerHTML = ic("trash") + "Click again to clear"; return; }
  const prof = $("#pv-prof").value; await desktop.privacy({clear: prof}); toast(`Cleared ${bdProf(prof).name}: you'll need to sign in to sites again`); renderPrivacy();
}
