// ================= STARTUP TOUR — shown once to new users, skippable, reopen anytime from Help =================
const TOUR = {i: 0, steps: [
  {view: "today", title: "Welcome to Daybook 👋", body: "Your local AI hub for notes, schedule, browser, development, and daily focus. Here is a complete walkthrough showing how everything connects."},
  {sel: ".nav", view: "today", title: "Everything lives in the sidebar", body: "Notes, reminders, calendar, browser, in-app web apps, chat, terminal, games… Right-click any icon or drag to rearrange. <b>Alt + 1–9</b> jumps instantly between views."},
  {sel: ".topbar .btn.pri", view: "today", title: "New — create anything", body: "One click to create reminders, notes from 20 templates, timers, desktop sticky notes, or voice memos. Reminders parse natural English: <i>“call mom tonight at 11pm”</i>."},
  {sel: ".searchbtn", view: "today", title: "Search or jump anywhere", body: "<b>Ctrl K</b> opens the command palette. Search notes, reminders, chats, and run commands instantly from anywhere in the app."},
  {sel: "#widgets", view: "today", title: "Your customizable home page", body: "Widgets you can add, remove, and resize — live schedule, timers, workflows, games. Click <b>Customize</b> for animated ambient scenes (rain, fireflies, fireplace) with matching soundscapes."},
  {sel: "#v-notes .notes", view: "notes", title: "Notes that organize themselves", body: "Write or dictate freely. <b>Organize with AI</b> titles your note, tags it, and detects tasks with their times — one click adds them directly to your reminders and calendar."},
  {sel: '.nav .navi[data-v="chat"]', view: "chat", title: "Private AI Chat & Integrated Terminal", body: "Chat privately with local Ollama models (Qwen, Llama) or Claude. Press <b>Ctrl + `</b> to toggle the built-in terminal below your chat — split panes with <b>Ctrl+Shift+D</b>, and paste code directly with 1 click."},
  {sel: '#thread', view: "chat", title: "1-Click AI Stack (Claude Code + Ollama)", body: "Daybook installs <b>Node.js LTS, Claude Code CLI, Gemini CLI, and Ollama</b> automatically in 1 click! On clean laptops without dedicated GPUs, use free <b>Google Gemini & Claude</b> in the cloud or lightweight 1.5B models with zero overheating or complex setup."},
  {sel: '.nav .navi[data-v="browser"]', view: "today", title: "Private Browser & Chrome Downloads", body: "Built-in private browser with ad & tracker blocking (YouTube ads blocked too), multi-profile logins, download shelf with progress bars, and 📄 one-click 'Send to Notes'."},
  {sel: '.nav .navi[data-v="apps"]', view: "today", title: "In-App Web Apps & LocalSend LAN Sharing", body: "Send files, voice memos, and photos across your local Wi-Fi to your phone without internet using <b>LocalSend</b>. Launch Gemini, Claude, Spotify, and YouTube Studio right inside Daybook."},
  {sel: '.nav .navi[data-v="workflows"]', view: "today", title: "Workflows", body: "1-click workspaces that launch all folders, applications, and web pages needed for a specific task (e.g. <i>Content Studio</i> = recordings folder + CapCut + YouTube)."},
  {sel: '.nav .navi[data-v="games"]', view: "today", title: "12-in-1 Retro Arcade & Console Hub", body: "Play Snake, Pong, Galactica, Breakout and more in the 8-bit offline retro arcade, or launch your favorite PC games and console emulators directly from the Games hub."},
  {sel: '.nav .navi[data-v="memos"]', view: "today", title: "Voice Memos & Screen Annotations", body: "Tap to record voice memos transcribed privately on your PC with Whisper. Freeze your screen anytime with <span class='kbd'>Ctrl Alt P</span> to draw arrows, highlights, and annotations."},
  {sel: '.nav .navi[data-v="settings"]', view: "today", title: "Full Settings & 1-Click Updates", body: "Full visibility customization: themes, layout styles, voice devices, and Discord sync. Use the sticky quick-jump bar and live filter to navigate, and update Daybook with 1 click from GitHub."},
  {sel: '.nav .navi[data-v="help"]', view: "today", title: "You're all set! 🚀", body: "The full manual and every keyboard shortcut are always available in <b>Help</b>. Reopen this walkthrough anytime from <b>Help → Take the tour</b>."}
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
