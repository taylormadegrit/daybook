// ================= STARTUP TOUR — shown once to new users, skippable, reopen anytime from Help =================
const TOUR = {i: 0, steps: [
  {view: "today", title: "Welcome to Daybook 👋", body: "A quick tour of the main parts — about a minute. You can skip it now and reopen it anytime from <b>Help → Take the tour</b>."},
  {sel: ".nav", view: "today", title: "Everything lives in the sidebar", body: "Notes, reminders, your calendar, the browser, workflows, games… Right-click a page or drag the edges to rearrange. <b>Alt + number</b> jumps between pages."},
  {sel: ".topbar .btn.pri", view: "today", title: "New — create anything", body: "Reminders, notes from 20 templates, timers, sticky notes, voice memos. Reminders understand plain English: <i>“call mom tonight at 11pm”</i>."},
  {sel: ".searchbtn", view: "today", title: "Search or jump anywhere", body: "<b>Ctrl K</b> searches notes, reminders and chats, and runs commands."},
  {sel: "#widgets", view: "today", title: "Your home page", body: "Widgets you can add, remove and rearrange — schedule, timers, workflows, games. <b>Customize</b> sets relaxing scenes and sounds."},
  {sel: "#v-notes .notes", view: "notes", title: "Notes that organize themselves", body: "Write freely. <b>Organize with AI</b> adds a title, tags and finds tasks with their times — one click puts them on your reminders and calendar."},
  {sel: '.nav .navi[data-v="browser"]', view: "today", title: "A private browser built in", body: "Ads and trackers blocked (YouTube too), logins per profile, ☆ saves links to your Library, and 📄 sends a page — like an AI chat — to Notes."},
  {sel: '.nav .navi[data-v="workflows"]', view: "today", title: "Workflows", body: "One click opens the folders, apps and sites you need for a task — e.g. <i>Editing</i> = recordings folder + CapCut + YouTube Studio."},
  {view: "today", title: "Right-click anything", body: "Every page has a right-click menu: go anywhere, create things, copy and search text, spelling suggestions, and actions for files, notes, apps and links."},
  {sel: '.nav .navi[data-v="help"]', view: "today", title: "That's it — you're ready", body: "The full guide and every keyboard shortcut are in <b>Help</b>. You can <b>reopen this tour anytime</b> from Help → Take the tour."},
]};
function tourStart(fromStep = 0) {
  closeModal(); closeMenu(); TOUR.i = fromStep;
  if (!$("#tour")) document.body.insertAdjacentHTML("beforeend", `<div id="tour" class="tour"><div class="tour-spot"></div><div class="tour-card" role="dialog" aria-live="polite"></div></div>`);
  tourShow();
}
async function tourShow() {
  const st = TOUR.steps[TOUR.i], n = TOUR.steps.length, root = $("#tour"); if (!root) return;
  if (st.view && S.view !== st.view) { go(st.view); await new Promise(r => setTimeout(r, 450)); }
  const target = st.sel ? $(st.sel) : null, spot = root.querySelector(".tour-spot"), card = root.querySelector(".tour-card");
  card.innerHTML = `<div class="tour-step">${TOUR.i + 1} / ${n}</div><h3>${st.title}</h3><p>${st.body}</p>
    <div class="tour-dots">${TOUR.steps.map((_, k) => `<i class="${k === TOUR.i ? "on" : ""}"></i>`).join("")}</div>
    <div class="row" style="margin-top:12px;gap:8px"><button class="btn ghost sm" onclick="tourEnd(true)">${TOUR.i === n - 1 ? "Close" : "Skip tour"}</button><div class="sp"></div>
      ${TOUR.i ? `<button class="btn sm" onclick="TOUR.i--;tourShow()">Back</button>` : ""}
      <button class="btn pri sm" id="tour-next" onclick="${TOUR.i === n - 1 ? "tourEnd(false)" : "TOUR.i++;tourShow()"}">${TOUR.i === n - 1 ? "Finish" : TOUR.i ? "Next" : "Start the tour"}</button></div>`;
  const r = target && target.offsetParent !== null ? target.getBoundingClientRect() : null;
  root.classList.toggle("center", !r);
  if (r) {
    const pad = 6; Object.assign(spot.style, {left: r.left - pad + "px", top: r.top - pad + "px", width: r.width + pad * 2 + "px", height: r.height + pad * 2 + "px"});
    const cw = 340, ch = card.offsetHeight || 220, W = innerWidth, H = innerHeight;
    let x = r.right + 16 + cw < W ? r.right + 16 : r.left - 16 - cw >= 0 ? r.left - 16 - cw : Math.min(W - cw - 16, Math.max(16, r.left));
    let y = r.right + 16 + cw < W || r.left - 16 - cw >= 0 ? Math.min(H - ch - 16, Math.max(16, r.top)) : (r.bottom + 16 + ch < H ? r.bottom + 16 : Math.max(16, r.top - ch - 16));
    Object.assign(card.style, {left: x + "px", top: y + "px"});
  } else { Object.assign(spot.style, {left: "50%", top: "50%", width: "0px", height: "0px"}); card.style.left = card.style.top = ""; }
  setTimeout(() => { const b = $("#tour-next"); b && b.focus(); }, 30);
}
async function tourEnd(skipped) {
  const root = $("#tour"); if (root) root.remove();
  try { await saveSetting("tour_seen", "1"); } catch (e) {}
  if (skipped) toast("Tour skipped — reopen it anytime from Help → Take the tour");
}
addEventListener("keydown", e => {
  if (!$("#tour")) return;
  if (e.key === "Escape") { e.stopPropagation(); tourEnd(true); }
  else if (e.key === "ArrowRight" && TOUR.i < TOUR.steps.length - 1) { TOUR.i++; tourShow(); }
  else if (e.key === "ArrowLeft" && TOUR.i > 0) { TOUR.i--; tourShow(); }
}, true);
addEventListener("resize", () => { if ($("#tour")) tourShow(); });
// first run: new users see it once (people who already use Daybook aren't interrupted — it's in Help)
setTimeout(() => {
  const s = S.settings || {};
  if (s.tour_seen === "1" || $("#tour")) return;
  if (s.welcome_seen === "0" && S.view === "today") tourStart();
}, 1800);
