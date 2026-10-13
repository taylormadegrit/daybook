// ================= CATEGORIES + IMPORTANCE + PLAN MY DAY =================
// Your own categories for reminders and tasks (AI-organized and imported ones get one automatically), an importance
// for each task, and "Plan my day": today's flexible tasks placed into your free time, most important first —
// drag to reorder, and the new order becomes their importance.
const CAT = {list: [], counts: {}, filter: store.get("daybook-rem-cat", "")};
const IMPORTANCE = [[80, "High"], [50, "Normal"], [25, "Low"]];
const impName = v => v >= 70 ? "High" : v >= 40 ? "Normal" : "Low";
async function catLoad(force) { if (!CAT.list.length || force) { const j = await api("/api/categories"); CAT.list = j.categories; CAT.counts = j.counts; } return CAT.list; }
const catColor = name => (CAT.list.find(c => c.name === name) || {}).color || "#8a90a3";
const catChip = name => name ? `<span class="catchip" style="--c:${catColor(name)}">${esc(name)}</span>` : "";
function catSelect(id, cur) {
  return `<select class="f" id="${id}"><option value="">${cur === undefined ? "Automatic (AI picks)" : "No category"}</option>${CAT.list.map(c => `<option value="${esc(c.name)}" ${c.name === cur ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>`;
}
function impSelect(id, cur = 50) {
  const opts = IMPORTANCE.some(([v]) => v === cur) ? IMPORTANCE : [...IMPORTANCE, [cur, `Custom (${cur})`]];
  return `<select class="f" id="${id}">${opts.map(([v, l]) => `<option value="${v}" ${v === cur ? "selected" : ""}>${l}</option>`).join("")}</select>`;
}

// ---- reminder editor: category + importance replace the old Normal/Important switch ----
const _exactFields = exactFields;
exactFields = function (r = {}) {
  const html = _exactFields(r);
  const imp = r.importance !== undefined ? r.importance : (r.priority ? 80 : 50);
  return html.replace(/<div><label class="lb">Priority<\/label><select class="f" id="ex-pri">[\s\S]*?<\/select><\/div>/,
    `<div><label class="lb">Category</label>${catSelect("ex-cat", r.id ? (r.category || "") : undefined)}</div><div><label class="lb">Importance</label>${impSelect("ex-imp", imp)}</div>`);
};
const _exactBody = exactBody;
exactBody = function () {
  const b = (() => { const pri = $("#ex-pri"); if (!pri) { const d = document.createElement("input"); d.id = "ex-pri"; d.type = "hidden"; d.value = "0"; $("#rm-ex").appendChild(d); } return _exactBody(); })();
  if (!b) return b;
  if ($("#ex-imp")) { b.importance = +$("#ex-imp").value; b.priority = b.importance >= 70 ? 1 : 0; }
  if ($("#ex-cat")) b.category = $("#ex-cat").value;
  return b;
};
// make sure the list is loaded before an editor opens
const _reminderModal = reminderModal;
reminderModal = function (pre) { if (!CAT.list.length) { catLoad().then(() => _reminderModal(pre)); return; } return _reminderModal(pre); };
const _editReminder = editReminder;
editReminder = async function (id) { await catLoad(); return _editReminder(id); };

// ---- reminders list: category chips, a category filter and "Plan my day" ----
const _renderReminders = renderReminders;
renderReminders = async function () {
  await catLoad(true);
  const bar = $("#remcats");
  if (bar) bar.innerHTML = [["", "All categories"], ...CAT.list.map(c => [c.name, c.name])].map(([k, l]) => `<button class="chipb ${CAT.filter === k ? "on" : ""}" ${k ? `style="--c:${catColor(k)}"` : ""} onclick="CAT.filter=${JSON.stringify(k).replace(/"/g, "&quot;")};store.set('daybook-rem-cat',CAT.filter);renderReminders()">${k ? `<i class="catdot"></i>` : ""}${esc(l)}${k && CAT.counts[k] ? ` <span class="muted">${CAT.counts[k]}</span>` : ""}</button>`).join("");
  await _renderReminders();
  // decorate rows: category chip + importance, and hide rows outside the filter
  const rs = await api("/api/reminders" + (S.remFilter === "done" ? "?status=done" : "")), by = Object.fromEntries(rs.map(r => [r.id, r]));
  $$("#remlist .rem").forEach(row => {
    const id = +((row.innerHTML.match(/editReminder\((\d+)\)|remDone\((\d+)\)/) || []).slice(1).find(Boolean)); const r = by[id]; if (!r) return;
    row.dataset.id = id;
    const name = row.querySelector("span:nth-child(2) b"); if (name && !row.querySelector(".catchip")) name.insertAdjacentHTML("afterend", " " + catChip(r.category) + (r.importance >= 70 ? "" : r.importance < 40 ? `<span class="badge low">low</span>` : ""));
    if (CAT.filter && r.category !== CAT.filter) row.style.display = "none";
  });
  $$("#remlist .grouph").forEach(h => { let n = h.nextElementSibling, any = false; while (n && !n.classList.contains("grouph")) { if (n.style.display !== "none") any = true; n = n.nextElementSibling; } h.style.display = any ? "" : "none"; });
};

// ---- Plan my day ----
const PLAN = {date: "", order: null, include: null, data: null};
async function planDay(day) {
  await catLoad();
  PLAN.date = day || isoDay(new Date()); PLAN.order = null; PLAN.include = null;
  modal(`<h2>${ic("clock", "i")}Plan my day<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="row" style="gap:8px;margin-bottom:8px"><div class="seg sm" id="plan-day">${[[0, "Today"], [1, "Tomorrow"]].map(([k, l]) => `<button class="${isoDay(new Date(Date.now() + k * 864e5)) === PLAN.date ? "on" : ""}" onclick="PLAN.date='${isoDay(new Date(Date.now() + k * 864e5))}';PLAN.order=null;PLAN.include=null;planPaint()">${l}</button>`).join("")}</div>
      <span class="muted small">Flexible tasks are placed into your free time between routine blocks — most important first. Drag to reorder; untick to keep a task's time.</span></div>
    <div id="plan-list" class="plan-list"></div>
    <div class="mfoot"><span class="muted small" id="plan-note"></span><div class="sp"></div><button class="btn ghost" onclick="closeModal()">Cancel</button><button class="btn pri" onclick="planApply()">${ic("check")}Apply plan</button></div>`, true);
  planPaint();
}
async function planPaint() {
  $$("#plan-day button").forEach(b => b.classList.toggle("on", b.getAttribute("onclick").includes(PLAN.date)));
  const body = {date: PLAN.date}; if (PLAN.order) body.order = PLAN.order; if (PLAN.include) body.include = PLAN.include;
  const p = PLAN.data = await api("/api/plan", {method: "POST", body});
  const el = $("#plan-list"); if (!el) return;
  el.innerHTML = p.tasks.length ? p.tasks.map((t, i) => `<div class="plan-row ${t.include ? "" : "off"}" draggable="true" data-id="${t.id}">
      <span class="grip" title="Drag to change importance">⋮⋮</span><input type="checkbox" ${t.include ? "checked" : ""} onchange="planToggle(${t.id},this.checked)" title="Plan this task">
      <span class="plan-t"><b>${esc(t.text)}</b>${catChip(t.category)}</span>
      <span class="plan-imp" title="Importance ${t.importance}"><i style="width:${t.importance}%"></i></span>
      <span class="plan-when">${t.include ? (t.slot ? `<b>${tm(t.slot)}</b> <span class="muted">${t.minutes} min</span>` : `<span style="color:var(--warn)">no free time left</span>`) : `<span class="muted">stays at ${tm(t.now)}</span>`}</span></div>`).join("")
    : `<div class="empty"><b>Nothing flexible to plan</b>One-time tasks (not routine blocks) due ${PLAN.date === isoDay(new Date()) ? "today or overdue" : "that day"} show up here.</div>`;
  $("#plan-note").textContent = p.tasks.length ? `Free time from ${tm(p.start)} to ${tm(p.end)} · ${p.busy.length} busy block${p.busy.length === 1 ? "" : "s"}` : "";
  el.querySelectorAll(".plan-row").forEach(row => {
    row.addEventListener("dragstart", e => { e.dataTransfer.setData("x-plan", row.dataset.id); row.classList.add("dragging"); });
    row.addEventListener("dragend", () => row.classList.remove("dragging"));
    row.addEventListener("dragover", e => { if (e.dataTransfer.types.includes("x-plan")) { e.preventDefault(); row.classList.add("over"); } });
    row.addEventListener("dragleave", () => row.classList.remove("over"));
    row.addEventListener("drop", e => {
      e.preventDefault(); row.classList.remove("over");
      const from = +e.dataTransfer.getData("x-plan"), to = +row.dataset.id; if (!from || from === to) return;
      const ids = PLAN.data.tasks.map(t => t.id); ids.splice(ids.indexOf(from), 1); ids.splice(ids.indexOf(to), 0, from);
      PLAN.order = ids; planPaint();
    });
  });
}
function planToggle(id, on) {
  const inc = new Set(PLAN.include || PLAN.data.tasks.filter(t => t.include).map(t => t.id));
  on ? inc.add(id) : inc.delete(id); PLAN.include = [...inc]; PLAN.order = PLAN.data.tasks.map(t => t.id); planPaint();
}
async function planApply() {
  const body = {date: PLAN.date, order: PLAN.data.tasks.map(t => t.id), include: PLAN.data.tasks.filter(t => t.include).map(t => t.id)};
  const p = await api("/api/plan/apply", {method: "POST", body});
  closeModal(); toast(`Planned ${p.tasks.filter(t => t.include && t.slot).length} task${p.tasks.length === 1 ? "" : "s"} — your order is now their importance`); refresh();
}

// ---- Settings → Categories ----
async function renderCatSettings() {
  const el = $("#catset"); if (!el) return; await catLoad(true);
  el.innerHTML = `<div class="muted small" style="margin-bottom:8px">Used for reminders and tasks — the AI picks one for tasks it finds and for reminders you add without choosing.</div>
    <div class="cat-edit">${CAT.list.map((c, i) => `<div class="cat-row"><input type="color" value="${c.color}" onchange="catEdit(${i},{color:this.value})">
      <input class="f" value="${esc(c.name)}" onchange="catEdit(${i},{name:this.value})"><span class="muted small">${CAT.counts[c.name] || 0} open</span>
      <button class="iconbtn" title="Delete (its reminders become uncategorized)" onclick="catDel(${i})">${ic("trash")}</button></div>`).join("")}</div>
    <div class="row" style="flex-wrap:nowrap;margin-top:8px"><input class="f" id="cat-new" placeholder="New category, e.g. Ori uploads" onkeydown="event.key==='Enter'&&catAdd()"><button class="btn" onclick="catAdd()">${ic("plus")}Add</button></div>`;
  paintIcons(el);
}
async function catSave(list, extra = {}) { const j = await api("/api/categories", {method: "POST", body: {categories: list, ...extra}}); CAT.list = j.categories; renderCatSettings(); }
function catAdd() { const n = $("#cat-new").value.trim(); if (!n) return; const colors = ["#4fd1ff", "#ff7ac6", "#3ee0a0", "#ffbe5c", "#8b7bff", "#a3e635", "#ff6b81", "#f97316"]; catSave([...CAT.list, {name: n, color: colors[CAT.list.length % colors.length]}]).then(() => toast(`Added “${n}”`)); }
function catEdit(i, patch) {
  const list = CAT.list.map(c => ({...c})), old = list[i].name; Object.assign(list[i], patch);
  catSave(list, patch.name && patch.name.trim() !== old ? {rename: {[old]: patch.name.trim()}} : {}).then(() => toast("Saved ✓"));
}
function catDel(i) { const c = CAT.list[i]; if (!confirm(`Delete “${c.name}”? Its reminders stay, just without a category.`)) return; catSave(CAT.list.filter((_, j) => j !== i), {removed: [c.name]}).then(() => toast("Deleted")); }
