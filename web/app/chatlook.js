// ================= CHAT → Look: style, text size, width, bubbles (remembered on this PC) =================
const CL_DEF = {style: "daybook", size: "m", width: "normal", bubbles: true};
const CL_STYLES = [["daybook", "Daybook", "Your theme and background"], ["orca", "Orca", "Flat charcoal, like Orca"],
  ["midnight", "Midnight", "Deep blue, high contrast"], ["paper", "Paper", "Light and easy to read"], ["mono", "Terminal", "Monospace text"]];
function clGet() { try { return {...CL_DEF, ...JSON.parse(store.get("daybook-chat-look", "{}"))}; } catch (e) { return {...CL_DEF}; } }
function clApply() {
  const v = $("#v-chat"); if (!v) return; const l = clGet();
  v.dataset.look = l.style; v.dataset.csize = l.size; v.dataset.cwidth = l.width; v.dataset.bubbles = l.bubbles ? "1" : "0";
}
function clSet(k, val) { const l = clGet(); l[k] = val; store.set("daybook-chat-look", JSON.stringify(l)); clApply(); }
function clMenu(e) {
  e && e.stopPropagation && e.stopPropagation();
  const l = clGet(), mark = on => on ? "check" : undefined;
  const r = e && e.currentTarget ? e.currentTarget.getBoundingClientRect() : {left: innerWidth / 2, bottom: 120};
  ctxShow(r.left, r.bottom + 4, [{h: "Style"}, ...CL_STYLES.map(([id, t]) => ({t, i: mark(l.style === id), run: () => clSet("style", id)})),
    "-", {h: "Text size"}, ...[["s", "Small"], ["m", "Medium"], ["l", "Large"]].map(([id, t]) => ({t, i: mark(l.size === id), run: () => clSet("size", id)})),
    "-", {h: "Width"}, ...[["narrow", "Narrow"], ["normal", "Comfortable"], ["wide", "Wide"], ["full", "Full width"]].map(([id, t]) => ({t, i: mark(l.width === id), run: () => clSet("width", id)})),
    "-", {t: "Message bubbles", i: mark(l.bubbles), run: () => clSet("bubbles", !l.bubbles)},
    {t: "Reset look", i: "rep", run: () => { store.set("daybook-chat-look", "{}"); clApply(); }}]);
}
(function clInit() {
  const bar = $("#v-chat .cbar"); if (!bar) return;
  if (!$("#c-look")) bar.insertAdjacentHTML("beforeend", `<button class="btn sm" id="c-look" onclick="clMenu(event)" title="Change how Chat looks">${ic("palette")}Look</button>`);
  paintIcons(bar); clApply();
  if (typeof CMDS !== "undefined") CMDS.push(["Change how Chat looks", "palette", () => { go("chat"); setTimeout(() => clMenu({currentTarget: $("#c-look")}), 250); }]);
})();
