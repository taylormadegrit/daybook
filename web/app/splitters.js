// ================= RESIZABLE PANELS: drag any divider to widen, narrow or collapse a panel =================
// Sizes are remembered. Double-click a divider to reset it. Dragging a side panel almost shut collapses it;
// drag the divider back out to reopen.
const SPL = {
  // key: [default px, min px, max px, collapsible]
  defs: {navw: [232, 150, 420, false], n1: [220, 150, 420, true], n2: [330, 200, 640, true], m1: [380, 240, 720, true],
         l1: [220, 150, 420, true], z1: [220, 150, 420, true], z2: [360, 220, 680, true], ch1: [250, 170, 480, true]},
  drag: null,
};
function splVar(k, v) { if (v == null) document.documentElement.style.removeProperty("--" + k); else document.documentElement.style.setProperty("--" + k, v + "px"); }
function splInit() {
  for (const k of Object.keys(SPL.defs)) { const v = store.get("daybook-split-" + k, null); if (v !== null && v !== "") splVar(k, +v); }
  // the main sidebar's edge
  const app = $(".app"); app.style.position = "relative";
  const h = document.createElement("div"); h.className = "split-h nav-split"; h.title = "Drag to resize the sidebar · double-click to reset"; app.appendChild(h);
  splBind(h, {key: "navw", el: () => $(".nav"), dir: () => $(".app").classList.contains("nav-right") ? -1 : 1,
    collapse: () => setSlim(true), expand: () => setSlim(false), isCollapsed: () => $(".app").classList.contains("slim")});
  new ResizeObserver(splPlaceNav).observe($(".nav")); addEventListener("resize", splPlaceNav); splPlaceNav();
}
function splPlaceNav() {
  const h = $(".nav-split"), app = $(".app"); if (!h) return;
  const side = !app.classList.contains("nav-top") && !app.classList.contains("nav-bottom") && innerWidth > 760;
  h.style.display = side ? "" : "none"; if (!side) return;
  const r = $(".nav").getBoundingClientRect();
  h.style.left = (app.classList.contains("nav-right") ? r.left - 4 : r.right - 4) + "px"; h.style.top = "0"; h.style.height = "100%";
}
// generic: a divider after column `col` of grid `grid`, sizing CSS var `key`
function splAttach(grid, col, key, extra = {}) {
  if (!grid || grid._spl && grid._spl[key]) return;
  grid._spl = grid._spl || {}; grid.style.position = "relative";
  const h = document.createElement("div"); h.className = "split-h"; h.title = "Drag to resize · double-click to reset";
  grid.appendChild(h); grid._spl[key] = h;
  const el = () => grid.children[col];
  const place = () => { const c = el(); if (!c) return; const gr = grid.getBoundingClientRect(), r = c.getBoundingClientRect();
    const gap = parseFloat(getComputedStyle(grid).columnGap) || 0; h.style.left = (r.right - gr.left + gap / 2 - 4) + "px"; h.style.top = "0"; h.style.height = "100%"; };
  splBind(h, {key, el, dir: () => 1, place, ...extra});
  new ResizeObserver(place).observe(grid); place(); setTimeout(place, 300);
  return place;
}
function splBind(h, o) {
  const [def, min, max, collapsible] = SPL.defs[o.key];
  h.addEventListener("pointerdown", e => {
    e.preventDefault(); h.setPointerCapture(e.pointerId); h.classList.add("on"); document.body.classList.add("splitting");
    const collapsed = o.isCollapsed ? o.isCollapsed() : false;
    if (collapsed && o.expand) o.expand();
    SPL.drag = {x: e.clientX, w: collapsed ? 0 : o.el().getBoundingClientRect().width};
  });
  h.addEventListener("pointermove", e => {
    if (!SPL.drag || !h.hasPointerCapture(e.pointerId)) return;
    let w = SPL.drag.w + (e.clientX - SPL.drag.x) * o.dir();
    if (w < min * 0.55 && (collapsible || o.collapse)) { h.classList.add("closing"); return; }   // will collapse on release
    h.classList.remove("closing");
    w = Math.max(min, Math.min(max, Math.round(w)));
    if (o.isCollapsed && o.isCollapsed() && o.expand) o.expand();
    splVar(o.key, w); SPL.drag.last = w; o.place && o.place(); splPlaceNav(); if (window.bdSync) bdSync();
  });
  const end = e => {
    if (!SPL.drag) return; h.classList.remove("on"); document.body.classList.remove("splitting");
    if (h.classList.contains("closing")) { h.classList.remove("closing"); if (o.collapse) o.collapse(); else { splVar(o.key, 0); store.set("daybook-split-" + o.key, "0"); } }
    else if (SPL.drag.last) store.set("daybook-split-" + o.key, String(SPL.drag.last));
    SPL.drag = null; o.place && o.place(); splPlaceNav(); if (window.bdSync) setTimeout(() => bdSync(true), 50);
  };
  h.addEventListener("pointerup", end); h.addEventListener("pointercancel", end);
  h.addEventListener("dblclick", () => { store.set("daybook-split-" + o.key, ""); splVar(o.key, null); if (o.expand) o.expand(); o.place && o.place(); splPlaceNav(); toast("Reset to the default size"); });
}
// page hooks (called after each page renders)
function splPages() {
  const notes = $("#v-notes .notes");
  if (notes) {
    splAttach(notes, 0, "n1", {collapse: () => { NP.f = false; store.set("daybook-np-f", "0"); notesPanels(); }, expand: () => { if (!NP.f) { NP.f = true; store.set("daybook-np-f", "1"); notesPanels(); } }, isCollapsed: () => !NP.f});
    splAttach(notes, 1, "n2", {collapse: () => { NP.l = false; store.set("daybook-np-l", "0"); notesPanels(); }, expand: () => { if (!NP.l) { NP.l = true; store.set("daybook-np-l", "1"); notesPanels(); } }, isCollapsed: () => !NP.l});
  }
  splAttach($(".memos"), 0, "m1");
  splAttach($(".lib"), 0, "l1");
  const zr = $(".zr"); if (zr) { splAttach(zr, 0, "z1"); splAttach(zr, 1, "z2"); }
  splAttach($(".chatwrap"), 0, "ch1");
}
