// ================= HOME: widgets you can add/remove/reorder/resize + relaxing animated scenes =================
// Loaded before the main script: definitions only.
const WIDGETS = {
  nownext: {name: "Now & next", icon: "zap", desc: "What's happening now and what's coming up", size: "wide",
    html: () => `<div class="now" id="nownext"></div>`, bare: true},
  schedule: {name: "Today's schedule", icon: "clock", desc: "Your timeline with done, snooze and ⏱ task timers",
    html: () => `<div class="card"><h3>${ic("clock")}<span id="sched-h">Schedule</span><button class="btn sm" onclick="reminderModal({date:S.viewDate})">${ic("plus")}Add</button></h3><div id="overdue"></div><div class="tl" id="timeline"></div></div>`},
  timers: {name: "Timers", icon: "timer", desc: "Countdowns for tasks — Focus 25, breaks, custom. They ring even if Daybook is closed",
    html: () => `<div class="card"><h3>${ic("timer")}Timers<button class="btn sm ghost" onclick="go('clock','timers')">Open</button></h3><div data-w="timers" data-compact="1"></div></div>`, after: () => clockStart()},
  stopwatch: {name: "Stopwatch", icon: "watch", desc: "Start, stop, laps (fastest in green, slowest in red)",
    html: () => `<div class="card"><h3>${ic("watch")}Stopwatch<button class="btn sm ghost" onclick="go('clock','stopwatch')">Open</button></h3><div data-w="sw"></div></div>`, after: () => clockStart()},
  alarms: {name: "Alarms", icon: "alarm", desc: "Your alarms with on/off switches",
    html: () => `<div class="card"><h3>${ic("alarm")}Alarms<button class="btn sm ghost" onclick="go('clock','alarms')">Open</button></h3><div data-w="alarms" data-compact="1"></div></div>`, after: () => clockStart()},
  world: {name: "World clock", icon: "globe", desc: "Live clocks for the cities you care about",
    html: () => `<div class="card"><h3>${ic("globe")}World clock<button class="btn sm ghost" onclick="go('clock','world')">Open</button></h3><div data-w="world" data-compact="1"></div></div>`, after: () => clockStart()},
  log: {name: "Daily log", icon: "pen", desc: "Quick timestamped thoughts for today (with 🎤 dictation)",
    html: () => `<div class="card"><h3>${ic("pen")}Daily log<button class="btn sm ghost" onclick="S.logId&&openNote(S.logId)">Open in Notes</button></h3>
      <div class="row" style="margin-bottom:10px;flex-wrap:nowrap" id="l-row"><input class="f" id="l-add" placeholder="Jot something down… press Enter" onkeydown="event.key==='Enter'&&addLog()"><button class="btn" onclick="addLog()">Log</button></div>
      <div class="log" id="logbody"></div><div class="row small muted" id="logtags" style="margin-top:8px"></div></div>`,
    after: () => micFor($("#l-add"), $("#l-row"))},
  upnext: {name: "Coming up", icon: "bell", desc: "The next reminders after today",
    html: () => `<div class="card"><h3>${ic("bell")}Coming up<button class="btn sm ghost" onclick="go('reminders')">All reminders</button></h3><div id="upnext"></div></div>`},
  stickies: {name: "Sticky notes & annotate", icon: "sticky", desc: "Your desktop sticky notes, show-all and screen annotation",
    html: () => `<div class="card"><h3>${ic("sticky")}Sticky notes
        <span class="row" style="gap:6px;margin-left:auto"><button class="btn sm" onclick="peekStickies()" title="Lift every note above your apps — press again to tuck them back">${ic("layers")}Show all</button>
        <button class="btn sm" onclick="annotateNow()">${ic("brush")}Annotate</button></span></h3>
      <div class="minis" id="home-stickies"></div><div class="annos" id="home-annos"></div>
      <div class="hotk"><span><span class="kbd">Ctrl Alt S</span> new</span><span><span class="kbd">Ctrl Alt W</span> show all</span><span><span class="kbd">Ctrl Alt P</span> annotate</span><span><span class="kbd">Ctrl V</span> pastes pictures into a note</span></div></div>`},
  memos: {name: "Voice memos", icon: "mic", desc: "Record a memo in one tap and see your latest ones",
    html: () => `<div class="card"><h3>${ic("mic")}Voice memos<button class="btn sm ghost" onclick="go('memos')">All memos</button></h3>
      <div class="recbig" style="margin-bottom:8px"><button class="recbtn" title="Record a voice memo" onclick="go('memos');setTimeout(memoRecToggle,250)"><i></i></button>
      <div class="small muted">Tap to record — it's transcribed on this PC.<br>Got recordings on your phone? <a href="#memos" onclick="go('memos')">Import them</a>.</div></div><div id="w-memos"></div></div>`,
    after: async () => { const j = await api("/api/memos"); const el = $("#w-memos"); if (!el) return;
      el.innerHTML = j.items.slice(0, 3).map(m => `<div class="memo" onclick="go('memos');setTimeout(()=>openMemo(${m.id}),150)"><div class="mt"><b>${esc(m.title || "New memo")}</b><span class="small muted">${mmss(m.duration)}</span></div>
        <div class="mm"><span>${dayName(m.memo_date)} · ${tm(m.memo_date)}</span>${m.labels.map(l => `<span class="badge">${esc(l)}</span>`).join("")}</div></div>`).join(""); }},
  notes: {name: "Recent notes", icon: "note", desc: "Jump back into what you were writing",
    html: () => `<div class="card"><h3>${ic("note")}Recent notes<button class="btn sm" onclick="templateModal()">${ic("plus")}New</button></h3><div id="w-notes"></div></div>`,
    after: async () => { const ns = await api("/api/notes?q="); const el = $("#w-notes"); if (!el) return;
      el.innerHTML = ns.slice(0, 5).map(n => `<div class="cat" onclick="openNote(${n.id})">${ic(CAT_ICON[n.category] || "note")}<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(n.title || "Untitled")}</span><span class="c">${dayName(n.note_date + "T12:00")}</span></div>`).join("") || `<div class="empty">No notes yet</div>`; }},
  ambience: {name: "Ambience", icon: "palette", desc: "Pick a relaxing scene and play its sound",
    html: () => `<div class="card"><h3>${ic("palette")}Ambience<button class="btn sm ghost" onclick="customizeModal()">More</button></h3><div id="w-amb"></div></div>`, after: () => renderAmbWidget()},
  breathe: {name: "Breathe", icon: "spark", desc: "A 1-minute box-breathing exercise (4-4-4-4) to reset",
    html: () => `<div class="card"><h3>${ic("spark")}Breathe<span class="small muted" style="margin-left:auto" id="br-n"></span></h3><div class="breathe" onclick="breatheToggle()"><div class="orb" id="br-orb"></div><div class="bt" id="br-t">Tap to start</div></div></div>`},
};
const DEFAULT_LAYOUT = ["nownext", "schedule", "log", "timers", "stickies", "alarms", "upnext", "ambience"].map(id => ({id, size: WIDGETS[id].size || "col"}));
const H = {editing: false, built: ""};
function layout() { const l = homeCfg().widgets; return (Array.isArray(l) && l.length ? l : DEFAULT_LAYOUT).filter(w => WIDGETS[w.id]); }
async function saveLayout(l) { await saveHomeCfg({widgets: l}); H.built = ""; renderHomeWidgets(true); if (S.view === "today") renderToday(); }

function renderHomeWidgets(force) {
  const host = $("#widgets"); if (!host) return;
  const l = layout(), sig = JSON.stringify(l) + H.editing;
  if (!force && H.built === sig && host.children.length) { runAfters(l); return; }
  H.built = sig;
  let out = "", group = [];
  const flush = () => { if (group.length) out += `<div class="wcols">${group.join("")}</div>`; group = []; };
  l.forEach((w, i) => {
    const W = WIDGETS[w.id];
    const el = `<div class="widget ${w.size === "wide" ? "wwide" : ""}" data-id="${w.id}" data-i="${i}" ${H.editing ? 'draggable="true"' : ""}>
      <div class="wedit"><button title="Drag to move · or use arrows" onclick="moveWidget(${i},-1)">${ic("left")}</button><button title="Move later" onclick="moveWidget(${i},1)">${ic("right")}</button>
        <button title="${w.size === "wide" ? "Make narrow" : "Make full width"}" onclick="sizeWidget(${i})">${ic("expand")}</button><button class="rm" title="Remove" onclick="removeWidget(${i})">${ic("x")}</button></div>
      ${W.html()}</div>`;
    if (w.size === "wide") { flush(); out += el; } else group.push(el);
  });
  flush();
  host.innerHTML = out || `<div class="empty"><b>Your home page is empty</b><button class="btn pri" style="margin-top:10px" onclick="addWidgetModal()">${ic("plus")}Add widgets</button></div>`;
  paintIcons(host);
  if (H.editing) dragSetup(host);
  runAfters(l);
}
function runAfters(l) { l.forEach(w => { try { const f = WIDGETS[w.id].after; f && f(); } catch (e) { console.warn(e); } }); }
function homeEdit(on) {
  H.editing = on ?? !H.editing;
  $("#v-today").classList.toggle("editing", H.editing);
  renderHomeWidgets(true); renderToday();
}
function moveWidget(i, d) { const l = layout(), j = i + d; if (j < 0 || j >= l.length) return; [l[i], l[j]] = [l[j], l[i]]; saveLayout(l); }
function sizeWidget(i) { const l = layout(); l[i].size = l[i].size === "wide" ? "col" : "wide"; saveLayout(l); }
function removeWidget(i) { const l = layout(); const [w] = l.splice(i, 1); saveLayout(l); toast(`Removed ${WIDGETS[w.id].name} — add it back with + Add widget`); }
function dragSetup(host) {
  let from = null;
  host.querySelectorAll(".widget").forEach(el => {
    el.addEventListener("dragstart", e => { from = +el.dataset.i; el.classList.add("drag"); e.dataTransfer.effectAllowed = "move"; });
    el.addEventListener("dragend", () => { el.classList.remove("drag"); host.querySelectorAll(".over").forEach(x => x.classList.remove("over")); });
    el.addEventListener("dragover", e => { e.preventDefault(); el.classList.add("over"); });
    el.addEventListener("dragleave", () => el.classList.remove("over"));
    el.addEventListener("drop", e => { e.preventDefault(); const to = +el.dataset.i; if (from === null || from === to) return;
      const l = layout(); const [w] = l.splice(from, 1); l.splice(to, 0, w); saveLayout(l); });
  });
}
function addWidgetModal() {
  const have = new Set(layout().map(w => w.id));
  modal(`<h2>${ic("grid", "i")}Add widgets<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="wgal">${Object.entries(WIDGETS).map(([id, W]) => `<div class="wg ${have.has(id) ? "added" : ""}" onclick="${have.has(id) ? "" : `addWidget('${id}')`}">
      <b>${ic(W.icon)}${W.name}${have.has(id) ? `<span class="badge" style="margin-left:auto">on home</span>` : ""}</b><span>${W.desc}</span></div>`).join("")}</div>
    <div class="row" style="margin-top:14px"><button class="btn ghost" onclick="if(confirmReset(this))saveLayout(DEFAULT_LAYOUT).then(closeModal)">Reset to default layout</button></div>`, true);
}
function confirmReset(btn) { if (btn.dataset.sure) return true; btn.dataset.sure = 1; btn.textContent = "Click again to reset"; return false; }
function addWidget(id) { const l = layout(); l.unshift({id, size: WIDGETS[id].size || "col"}); closeModal(); saveLayout(l); toast(WIDGETS[id].name + " added to the top — drag it anywhere"); }

// ---------- breathe ----------
const BR = {on: false, t: 0, n: 0};
function breatheToggle() {
  BR.on = !BR.on; clearInterval(BR.t);
  const orb = $("#br-orb"), txt = $("#br-t");
  if (!BR.on) { orb.style.transform = ""; txt.textContent = "Tap to start"; return; }
  const steps = [["Breathe in…", 2.3], ["Hold", 2.3], ["Breathe out…", 1], ["Hold", 1]]; let k = 0;
  const step = () => { const [t, sc] = steps[k % 4]; const o = $("#br-orb"); if (!o || !BR.on) { clearInterval(BR.t); BR.on = false; return; }
    o.style.transform = `scale(${sc})`; $("#br-t").textContent = t; if (k % 4 === 0 && k) { BR.n++; $("#br-n").textContent = BR.n + " breath" + (BR.n > 1 ? "s" : ""); }
    k++; if (k >= 16) { setTimeout(() => { BR.on = false; $("#br-t") && ($("#br-t").textContent = "Nice. Tap to go again"); $("#br-orb") && ($("#br-orb").style.transform = ""); }, 4000); clearInterval(BR.t); } };
  step(); BR.t = setInterval(step, 4000);
}

// ================= SCENES (canvas, generated — no downloads) =================
const SCENES = {
  none: {name: "Theme glow", em: "✨", bg: "var(--bg)"},
  fireplace: {name: "Fireplace", em: "🔥", bg: "linear-gradient(#1a0a04,#5a1d06)"},
  rain: {name: "Rainy window", em: "🌧️", bg: "linear-gradient(#0c1424,#1e2c44)"},
  forest: {name: "Firefly forest", em: "🌲", bg: "linear-gradient(#06141a,#0f3a34)"},
  ocean: {name: "Ocean sunset", em: "🌅", bg: "linear-gradient(#ff9a5a,#5b2a86)"},
  night: {name: "Starry night", em: "🌌", bg: "linear-gradient(#030512,#1a1f4a)"},
  snow: {name: "Snowfall", em: "❄️", bg: "linear-gradient(#5d7499,#c9d6ea)"},
  meadow: {name: "Spring meadow", em: "🌼", bg: "linear-gradient(#8ccff5,#7ccb6a)"},
  custom: {name: "My picture / video", em: "🖼️", bg: "var(--card2)"},
};
const SC = {name: "none", ctx: null, w: 0, h: 0, raf: 0, last: 0, st: {}, mx: .5, my: .5, cfg: {}};
const R = (a, b) => a + Math.random() * (b - a);
function sceneCfg() { const h = homeCfg(); return {scene: h.scene || "none", sound: !!h.sound, vol: h.vol ?? .5, dim: h.dim ?? .25, everywhere: !!h.everywhere, still: !!h.still, bgfile: h.bgfile || ""}; }
function applyScene() {
  const c = sceneCfg(); SC.cfg = c;
  const show = c.scene !== "none" && (c.everywhere || S.view === "today");
  document.body.classList.toggle("scened", show);
  document.body.classList.toggle("custombg", c.scene === "custom");
  let dim = $("#scenedim"); if (dim) dim.style.background = `rgba(4,5,10,${c.dim})`;
  const bg = $("#scenebg");
  if (c.scene === "custom" && c.bgfile && bg && bg.dataset.f !== c.bgfile) {
    bg.dataset.f = c.bgfile; const url = "/backgrounds/" + c.bgfile + "?v=" + (homeCfg().bgv || 0);
    bg.innerHTML = /\.(mp4|webm)$/i.test(c.bgfile) ? `<video src="${url}" autoplay muted loop playsinline style="width:100%;height:100%;object-fit:cover"></video>` : `<img src="${url}" style="width:100%;height:100%;object-fit:cover" alt="">`;
  }
  if (show && c.scene !== "custom") sceneStart(c.scene); else sceneStop();
  ambience(c.sound && c.scene !== "none" && c.scene !== "custom" ? c.scene : null, c.vol);
}
function sceneStart(name) {
  const cv = $("#scene"); if (!cv) return;
  if (SC.name !== name || !SC.ctx) { SC.name = name; SC.st = {}; }
  SC.ctx = cv.getContext("2d"); sceneResize();
  if (!SC.raf) { SC.last = performance.now(); SC.raf = requestAnimationFrame(sceneFrame); }
}
function sceneStop() { cancelAnimationFrame(SC.raf); SC.raf = 0; }
function sceneResize() { const cv = $("#scene"); if (!cv) return; const s = Math.min(devicePixelRatio, 1.25); SC.w = cv.width = innerWidth * s; SC.h = cv.height = innerHeight * s; SC.st = {}; }
function sceneFrame(now) {
  SC.raf = requestAnimationFrame(sceneFrame);
  if (document.hidden) return;
  const dt = Math.min(.05, (now - SC.last) / 1000); SC.last = now;
  if (SC.cfg.still && SC.st.drawn) return;
  try { DRAW[SC.name] && DRAW[SC.name](SC.ctx, SC.w, SC.h, SC.cfg.still ? 0 : dt, now / 1000, SC.st); SC.st.drawn = 1; } catch (e) { console.warn(e); sceneStop(); }
}
function sceneClick(e) {
  if (!document.body.classList.contains("scened") || e.target.closest(".card,button,input,textarea,select,a,.nav,.topbar,.modal,.widget,.now")) return;
  const s = Math.min(devicePixelRatio, 1.25); CLICK[SC.name] && CLICK[SC.name](e.clientX * s, e.clientY * s, SC.st);
}
const sprite = (r, stops) => { const c = document.createElement("canvas"); c.width = c.height = r * 2; const g = c.getContext("2d"), gr = g.createRadialGradient(r, r, 0, r, r, r);
  stops.forEach(([o, col]) => gr.addColorStop(o, col)); g.fillStyle = gr; g.fillRect(0, 0, r * 2, r * 2); return c; };
function pines(g, w, baseY, n, hmin, hmax, col, seed) {
  g.fillStyle = col; let x = -40; let k = seed;
  const rnd = () => (k = (k * 9301 + 49297) % 233280) / 233280;
  while (x < w + 40) { const h = hmin + rnd() * (hmax - hmin), bw = h * .38; g.beginPath(); g.moveTo(x, baseY - h);
    for (let t = 1; t <= 4; t++) { const y = baseY - h + h * t / 4, ww = bw * t / 4; g.lineTo(x + ww, y); g.lineTo(x + ww * .45, y); }
    g.lineTo(x + 2, baseY + 2); g.lineTo(x - 2, baseY + 2);
    for (let t = 4; t >= 1; t--) { const y = baseY - h + h * t / 4, ww = bw * t / 4; g.lineTo(x - ww * .45, y); g.lineTo(x - ww, y); }
    g.closePath(); g.fill(); x += bw * (.6 + rnd() * .9) * n; }
  g.fillRect(0, baseY, w, 4000);
}
const DRAW = {
  fireplace(g, w, h, dt, t, st) {
    if (!st.p) { st.p = []; st.e = []; st.spr = [sprite(40, [[0, "rgba(255,250,210,.9)"], [.4, "rgba(255,200,80,.5)"], [1, "rgba(255,120,20,0)"]]), sprite(40, [[0, "rgba(255,160,40,.8)"], [.5, "rgba(255,90,10,.35)"], [1, "rgba(200,30,0,0)"]]), sprite(40, [[0, "rgba(200,50,10,.5)"], [1, "rgba(80,10,0,0)"]])]; st.burst = []; }
    const cx = w * .5, base = h * .93, sc = h / 900, fl = .85 + .1 * Math.sin(t * 7.3) + .06 * Math.sin(t * 13.1) + .04 * Math.random();
    let gr = g.createRadialGradient(cx, base, 10, cx, base, h * 1.1 * fl);
    gr.addColorStop(0, "#7a2a08"); gr.addColorStop(.35, "#3a1206"); gr.addColorStop(1, "#0c0503"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
    g.fillStyle = "#1d0d07"; g.fillRect(0, base + 8 * sc, w, h); // hearth
    const wind = (SC.mx - .5) * 40 * sc;
    for (let i = 0; i < 6; i++) st.p.push({x: cx + R(-150, 150) * sc, y: base - 10 * sc, vx: R(-12, 12) * sc, vy: R(-160, -90) * sc, l: 0, L: R(.7, 1.3), s: R(26, 46) * sc});
    if (Math.random() < .5) st.e.push({x: cx + R(-140, 140) * sc, y: base - 30 * sc, vx: R(-20, 20) * sc, vy: R(-120, -50) * sc, l: 0, L: R(1.5, 3.5)});
    g.globalCompositeOperation = "lighter";
    st.p = st.p.filter(p => (p.l += dt) < p.L);
    for (const p of st.p) { const k = p.l / p.L; p.x += (p.vx + wind * k) * dt; p.y += p.vy * dt; p.vx += (cx - p.x) * .9 * dt;
      const s = p.s * (1 - k * .7), spr = st.spr[k < .35 ? 0 : k < .7 ? 1 : 2]; g.globalAlpha = (1 - k) * .8; g.drawImage(spr, p.x - s, p.y - s, s * 2, s * 2); }
    g.globalAlpha = 1;
    // logs
    g.globalCompositeOperation = "source-over";
    [[-130, 12, 270, 30, .12], [-60, 24, 260, 28, -.18], [-100, -2, 210, 24, .02]].forEach(([dx, dy, lw, lh, a]) => { g.save(); g.translate(cx + dx * sc + lw * sc / 2, base + dy * sc - 10 * sc); g.rotate(a);
      g.fillStyle = "#2a1408"; g.beginPath(); g.roundRect(-lw * sc / 2, -lh * sc / 2, lw * sc, lh * sc, lh * sc / 2); g.fill();
      g.strokeStyle = `rgba(255,${110 + 60 * fl | 0},30,${.35 * fl})`; g.lineWidth = 3 * sc; g.stroke(); g.restore(); });
    g.globalCompositeOperation = "lighter";
    st.e = st.e.concat(st.burst.splice(0)).filter(e => (e.l += dt) < e.L);
    for (const e of st.e) { e.x += (e.vx + Math.sin(t * 3 + e.L * 9) * 18 * sc + wind) * dt; e.y += e.vy * dt; e.vy *= .995;
      g.fillStyle = `rgba(255,${160 + Math.random() * 80 | 0},60,${1 - e.l / e.L})`; g.fillRect(e.x, e.y, 2.4 * sc, 2.4 * sc); }
    g.globalCompositeOperation = "source-over";
  },
  rain(g, w, h, dt, t, st) {
    if (!st.bk) { const c = document.createElement("canvas"); c.width = w; c.height = h; const b = c.getContext("2d");
      const gr = b.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#0a1220"); gr.addColorStop(1, "#1b2a42"); b.fillStyle = gr; b.fillRect(0, 0, w, h);
      for (let i = 0; i < 45; i++) { const r = R(20, 90) * h / 900, col = ["255,190,110", "255,120,90", "120,180,255", "255,230,160", "160,120,255"][i % 5];
        b.drawImage(sprite(r, [[0, `rgba(${col},.55)`], [1, `rgba(${col},0)`]]), R(0, w) - r, R(h * .3, h) - r); }
      st.bk = c; st.dr = Array.from({length: 380}, () => ({x: R(0, w), y: R(0, h), z: R(.4, 1)}));
      st.gl = Array.from({length: 70}, () => ({x: R(0, w), y: R(0, h), r: R(1.5, 5) * h / 900, v: 0})); st.fl = 0; }
    g.drawImage(st.bk, 0, 0);
    if (st.fl > 0) { g.fillStyle = `rgba(200,215,255,${st.fl * .5})`; g.fillRect(0, 0, w, h); st.fl -= dt * 1.6; }
    const wind = (SC.mx - .5) * 500 * h / 900;
    g.strokeStyle = "rgba(180,200,235,.35)"; g.lineWidth = 1.1; g.beginPath();
    for (const d of st.dr) { const vy = 1100 * d.z * h / 900; d.y += vy * dt; d.x += wind * d.z * dt; if (d.y > h) { d.y = -20; d.x = R(-100, w + 100); }
      g.moveTo(d.x, d.y); g.lineTo(d.x - wind * .025 * d.z, d.y - 22 * d.z); }
    g.stroke();
    for (const d of st.gl) { if (Math.random() < .002) d.v = R(60, 200); d.y += d.v * dt; d.v *= .985; if (d.y > h + 10) { d.y = R(-10, h * .5); d.x = R(0, w); d.v = 0; }
      g.fillStyle = "rgba(200,220,255,.18)"; g.beginPath(); g.arc(d.x, d.y, d.r, 0, 7); g.fill(); g.fillStyle = "rgba(255,255,255,.35)"; g.fillRect(d.x - d.r * .4, d.y - d.r * .5, d.r * .4, d.r * .4); }
  },
  forest(g, w, h, dt, t, st) {
    if (!st.l) { st.l = [0, 1, 2].map(i => { const c = document.createElement("canvas"); c.width = w + 120; c.height = h; const b = c.getContext("2d");
        pines(b, w + 120, h * (.62 + i * .14), 1, h * (.22 + i * .08), h * (.42 + i * .12), ["#103a3a", "#0a2628", "#04121a"][i], 7 + i * 13); return c; });
      st.ff = Array.from({length: 70}, () => ({x: R(0, w), y: R(h * .35, h), a: R(0, 7), s: R(.6, 1.4), vx: 0, vy: 0})); st.spr = sprite(18, [[0, "rgba(230,255,150,1)"], [.25, "rgba(200,255,120,.5)"], [1, "rgba(120,255,80,0)"]]); }
    const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#04101c"); gr.addColorStop(.6, "#0d3138"); gr.addColorStop(1, "#103c36"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
    g.drawImage(sprite(h * .25, [[0, "rgba(220,240,255,.35)"], [1, "rgba(220,240,255,0)"]]), w * .78 - h * .25, h * .16 - h * .25);
    g.fillStyle = "#e9f2ff"; g.beginPath(); g.arc(w * .78, h * .16, h * .045, 0, 7); g.fill();
    st.l.forEach((c, i) => { g.drawImage(c, -60 + (SC.mx - .5) * -(i + 1) * 25, 0);
      g.fillStyle = `rgba(160,220,210,${.05 + i * .02})`; g.fillRect(0, h * (.55 + i * .13) + Math.sin(t * .2 + i) * 10, w, h * .08); });
    g.globalCompositeOperation = "lighter";
    const mx = SC.mx * w, my = SC.my * h;
    for (const f of st.ff) { f.a += dt * f.s; f.vx += Math.cos(f.a * 1.3) * 12 * dt; f.vy += Math.sin(f.a) * 10 * dt;
      const dx = mx - f.x, dy = my - f.y, d = Math.hypot(dx, dy); if (d < 250 && d > 30) { f.vx += dx / d * 25 * dt; f.vy += dy / d * 25 * dt; }
      f.vx *= .98; f.vy *= .98; f.x += f.vx * dt * 20; f.y += f.vy * dt * 20;
      if (f.x < -20) f.x = w + 20; if (f.x > w + 20) f.x = -20; if (f.y < h * .2) f.vy += 2; if (f.y > h) f.vy -= 2;
      const b = (Math.sin(t * 2.2 * f.s + f.a * 3) + 1) / 2; g.globalAlpha = .25 + b * .75; const s = 10 + 8 * b; g.drawImage(st.spr, f.x - s, f.y - s, s * 2, s * 2); }
    g.globalAlpha = 1; g.globalCompositeOperation = "source-over";
  },
  ocean(g, w, h, dt, t, st) {
    const hz = h * .52, sx = w * (.5 + (SC.mx - .5) * .1);
    let gr = g.createLinearGradient(0, 0, 0, hz); gr.addColorStop(0, "#3b1d6b"); gr.addColorStop(.55, "#e0607e"); gr.addColorStop(1, "#ffb36b"); g.fillStyle = gr; g.fillRect(0, 0, w, hz + 2);
    g.drawImage(sprite(h * .35, [[0, "rgba(255,230,170,.9)"], [.15, "rgba(255,190,120,.5)"], [1, "rgba(255,120,100,0)"]]), sx - h * .35, hz - h * .08 - h * .35);
    g.fillStyle = "#ffe9b8"; g.beginPath(); g.arc(sx, hz - h * .05, h * .065, Math.PI, 0); g.fill();
    const cols = ["#7a3f7d", "#5b2f73", "#422566", "#2e1b55", "#1d1240"];
    cols.forEach((c, i) => { const y0 = hz + i * h * .1, amp = (6 + i * 7) * h / 900, sp = .5 + i * .25; g.fillStyle = c; g.beginPath(); g.moveTo(0, h);
      for (let x = 0; x <= w + 20; x += 20) g.lineTo(x, y0 + Math.sin(x / (160 + i * 60) + t * sp + i) * amp + Math.sin(x / 57 + t * sp * 1.7) * amp * .35);
      g.lineTo(w, h); g.fill(); });
    g.globalCompositeOperation = "lighter";
    for (let i = 0; i < 70; i++) { const y = hz + 6 + Math.pow(Math.random(), 1.6) * h * .45, spread = 20 + (y - hz) * .5, x = sx + R(-spread, spread);
      g.fillStyle = `rgba(255,220,160,${R(.1, .5) * (1 - (y - hz) / (h * .5))})`; g.fillRect(x, y, R(8, 30), 1.5); }
    g.globalCompositeOperation = "source-over";
  },
  night(g, w, h, dt, t, st) {
    if (!st.s) { st.s = Array.from({length: 420}, () => ({x: R(0, w), y: Math.pow(Math.random(), 1.3) * h * .8, r: R(.4, 1.6), p: R(0, 7), sp: R(.5, 2)})); st.sh = [];
      st.mt = document.createElement("canvas"); st.mt.width = w; st.mt.height = h; const b = st.mt.getContext("2d");
      [[.74, "#0d1230", 3], [.82, "#060818", 11]].forEach(([y0, c, seed]) => { b.fillStyle = c; b.beginPath(); b.moveTo(0, h); let k = seed;
        for (let x = 0; x <= w; x += 30) { k = (k * 9301 + 49297) % 233280; b.lineTo(x, h * y0 - Math.sin(x / 300 + seed) * h * .06 - (k / 233280) * h * .03); } b.lineTo(w, h); b.fill(); }); }
    const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#02030c"); gr.addColorStop(1, "#161b45"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
    g.globalCompositeOperation = "lighter";
    [[.25, "60,255,170"], [.33, "150,90,255"]].forEach(([y0, c], i) => { for (let k = 0; k < 3; k++) { g.beginPath(); g.moveTo(0, h);
        for (let x = 0; x <= w; x += 24) g.lineTo(x, h * y0 + Math.sin(x / 260 + t * .25 + i + k) * h * .06 + Math.sin(x / 90 + t * .5) * h * .015 + k * 14);
        g.lineTo(w, 0); g.lineTo(0, 0); g.closePath(); g.fillStyle = `rgba(${c},.022)`; g.fill(); } });
    for (const s of st.s) { const a = .35 + .65 * (Math.sin(t * s.sp + s.p) + 1) / 2; g.fillStyle = `rgba(230,235,255,${a})`; g.fillRect(s.x, s.y, s.r, s.r); }
    if (Math.random() < dt / 6) st.sh.push({x: R(w * .2, w), y: R(0, h * .3), l: 0});
    st.sh = st.sh.filter(s => (s.l += dt) < 1);
    for (const s of st.sh) { const k = s.l, x = s.x - k * w * .35, y = s.y + k * h * .2, g2 = g.createLinearGradient(x, y, x + 120, y - 70);
      g2.addColorStop(0, `rgba(255,255,255,${1 - k})`); g2.addColorStop(1, "rgba(255,255,255,0)"); g.strokeStyle = g2; g.lineWidth = 2; g.beginPath(); g.moveTo(x, y); g.lineTo(x + 120, y - 70); g.stroke(); }
    g.globalCompositeOperation = "source-over"; g.drawImage(st.mt, 0, 0);
  },
  snow(g, w, h, dt, t, st) {
    if (!st.f) { st.f = Array.from({length: 320}, () => ({x: R(0, w), y: R(0, h), z: R(.3, 1), p: R(0, 7)}));
      st.bk = document.createElement("canvas"); st.bk.width = w + 80; st.bk.height = h; const b = st.bk.getContext("2d");
      const gr = b.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#4b6288"); gr.addColorStop(1, "#b9c8de"); b.fillStyle = gr; b.fillRect(0, 0, w + 80, h);
      pines(b, w + 80, h * .78, 1.3, h * .2, h * .36, "#3d5574", 5); pines(b, w + 80, h * .9, 1.1, h * .25, h * .45, "#22344d", 21);
      b.fillStyle = "#e8eef8"; b.fillRect(0, h * .9, w + 80, h); st.gust = 0; }
    g.drawImage(st.bk, -40 + (SC.mx - .5) * -30, 0);
    const wind = (SC.mx - .5) * 60 + st.gust; st.gust *= .97;
    g.fillStyle = "#fff";
    for (const f of st.f) { f.y += (30 + 60 * f.z) * dt * h / 900; f.x += (Math.sin(t + f.p) * 18 * f.z + wind * f.z) * dt;
      if (f.y > h) { f.y = -5; f.x = R(0, w); } if (f.x > w + 10) f.x = -10; if (f.x < -10) f.x = w + 10;
      g.globalAlpha = .4 + f.z * .6; g.beginPath(); g.arc(f.x, f.y, 1 + f.z * 2.6, 0, 7); g.fill(); }
    g.globalAlpha = 1;
  },
  meadow(g, w, h, dt, t, st) {
    if (!st.c) { st.c = Array.from({length: 7}, (_, i) => ({x: R(0, w), y: R(h * .05, h * .35), s: R(.6, 1.3), v: R(6, 16)}));
      st.cs = (() => { const c = document.createElement("canvas"); c.width = 360; c.height = 140; const b = c.getContext("2d"); b.fillStyle = "rgba(255,255,255,.9)";
        [[80, 90, 50], [140, 70, 60], [210, 80, 55], [270, 95, 40], [170, 100, 50]].forEach(([x, y, r]) => { b.beginPath(); b.arc(x, y, r, 0, 7); b.fill(); }); return c; })();
      st.g = Array.from({length: 260}, () => ({x: R(0, w), h: R(30, 90) * h / 900, p: R(0, 7), c: ["#3f9a3a", "#56b146", "#2f7d31", "#6cc25a"][Math.random() * 4 | 0]}));
      st.pt = Array.from({length: 30}, () => ({x: R(0, w), y: R(0, h), p: R(0, 7), c: ["#ffd6e8", "#fff3a8", "#ffffff"][Math.random() * 3 | 0]})); }
    const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#5fb4ec"); gr.addColorStop(.6, "#bfe6fb"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
    g.drawImage(sprite(h * .22, [[0, "rgba(255,250,220,.95)"], [.2, "rgba(255,240,180,.5)"], [1, "rgba(255,240,180,0)"]]), w * .15 - h * .22, h * .14 - h * .22);
    for (const c of st.c) { c.x += c.v * dt; if (c.x > w + 200) c.x = -400; g.globalAlpha = .85; g.drawImage(st.cs, c.x, c.y, 360 * c.s, 140 * c.s); } g.globalAlpha = 1;
    [["#9fd88a", .62, 280], ["#79c46a", .72, 200], ["#5aae4f", .84, 150]].forEach(([c, y0, f], i) => { g.fillStyle = c; g.beginPath(); g.moveTo(0, h);
      for (let x = 0; x <= w; x += 20) g.lineTo(x, h * y0 + Math.sin(x / f + i * 2) * h * .03); g.lineTo(w, h); g.fill(); });
    const wind = (SC.mx - .5) * 20;
    g.lineWidth = 2; for (const b of st.g) { const sw = Math.sin(t * 1.6 + b.p + b.x / 200) * 8 + wind; g.strokeStyle = b.c; g.beginPath(); g.moveTo(b.x, h); g.quadraticCurveTo(b.x + sw * .4, h - b.h * .5, b.x + sw, h - b.h); g.stroke(); }
    for (const p of st.pt) { p.p += dt; p.x += (25 + wind * 2) * dt + Math.sin(p.p * 2) * .6; p.y += Math.sin(p.p) * 15 * dt + 8 * dt; if (p.x > w + 10) { p.x = -10; p.y = R(0, h * .8); } if (p.y > h) p.y = 0;
      g.fillStyle = p.c; g.save(); g.translate(p.x, p.y); g.rotate(p.p); g.fillRect(-3, -1.5, 6, 3); g.restore(); }
  },
};
const CLICK = {
  fireplace: (x, y, st) => { for (let i = 0; i < 50; i++) st.burst.push({x, y, vx: R(-160, 160), vy: R(-260, -40), l: 0, L: R(.6, 1.8)}); ambSfx("crackle"); },
  rain: (x, y, st) => { st.fl = 1; setTimeout(() => ambSfx("thunder"), 300); },
  forest: (x, y, st) => { for (const f of st.ff) { const dx = f.x - x, dy = f.y - y, d = Math.hypot(dx, dy) || 1; if (d < 300) { f.vx += dx / d * 30; f.vy += dy / d * 30; } } },
  night: (x, y, st) => st.sh.push({x: x + 50, y, l: 0}),
  snow: (x, y, st) => { st.gust = (x / SC.w < .5 ? 1 : -1) * 260; ambSfx("gust"); },
  ocean: () => {}, meadow: (x, y, st) => { for (let i = 0; i < 12; i++) st.pt.push({x, y, p: R(0, 7), c: "#ffd6e8"}); st.pt.splice(0, Math.max(0, st.pt.length - 60)); },
};

// ================= AMBIENT SOUND (synthesized with WebAudio) =================
const AU = {ctx: null, master: null, nodes: [], timers: [], scene: null, pending: null};
function noiseBuf(ctx, kind) {
  const n = ctx.sampleRate * 4, b = ctx.createBuffer(1, n, ctx.sampleRate), d = b.getChannelData(0);
  let l = 0, b0 = 0, b1 = 0, b2 = 0;
  for (let i = 0; i < n; i++) { const wv = Math.random() * 2 - 1;
    if (kind === "brown") { l = (l + .02 * wv) / 1.02; d[i] = l * 3.5; }
    else if (kind === "pink") { b0 = .99765 * b0 + wv * .099; b1 = .963 * b1 + wv * .2965; b2 = .57 * b2 + wv * 1.0526; d[i] = (b0 + b1 + b2 + wv * .1848) * .18; }
    else d[i] = wv; }
  return b;
}
function auNoise(kind, filters, gain) {
  const c = AU.ctx, s = c.createBufferSource(); s.buffer = AU.bufs[kind]; s.loop = true;
  let node = s; filters.forEach(([type, f, q]) => { const fl = c.createBiquadFilter(); fl.type = type; fl.frequency.value = f; if (q) fl.Q.value = q; node.connect(fl); node = fl; });
  const g = c.createGain(); g.gain.value = gain; node.connect(g); g.connect(AU.master); s.start(); AU.nodes.push(s, g); return g;
}
function auLFO(param, rate, depth, base) { const c = AU.ctx, o = c.createOscillator(), g = c.createGain(); o.frequency.value = rate; g.gain.value = depth; param.value = base; o.connect(g); g.connect(param); o.start(); AU.nodes.push(o); }
function auBurst(freq, dur, vol, q = 1) {
  const c = AU.ctx, s = c.createBufferSource(); s.buffer = AU.bufs.white; const f = c.createBiquadFilter(); f.type = "bandpass"; f.frequency.value = freq; f.Q.value = q;
  const g = c.createGain(), t = c.currentTime; g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
  s.connect(f); f.connect(g); g.connect(AU.master); s.start(t, Math.random() * 3); s.stop(t + dur + .05);
}
function auChirp(f0, f1, dur, vol) {
  const c = AU.ctx, o = c.createOscillator(), g = c.createGain(), t = c.currentTime; o.type = "sine";
  o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + dur); g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + dur * .2); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
  o.connect(g); g.connect(AU.master); o.start(t); o.stop(t + dur + .02);
}
const every = (ms, f) => AU.timers.push(setInterval(f, ms));
const SOUNDS = {
  fireplace() { auNoise("brown", [["lowpass", 380]], .55); auNoise("pink", [["bandpass", 900, .7]], .05);
    every(45, () => { if (Math.random() < .28) auBurst(R(1200, 5200), R(.01, .05), R(.05, .45), R(1, 6)); if (Math.random() < .02) auBurst(R(300, 700), .15, .3, 1); }); },
  rain() { const g = auNoise("pink", [["highpass", 400], ["lowpass", 7000]], .5); auLFO(g.gain, .07, .08, .5); auNoise("white", [["bandpass", 3200, .5]], .03);
    every(70, () => { if (Math.random() < .25) auChirp(R(1500, 3000), R(800, 1400), .05, R(.01, .04)); }); },
  forest() { const wnd = auNoise("pink", [["bandpass", 500, .6]], .12); auLFO(wnd.gain, .05, .08, .14);
    every(900, () => { if (Math.random() < .7) { let k = 0; const n = 2 + (Math.random() * 3 | 0), f = R(4200, 4800); const id = setInterval(() => { auChirp(f, f * .98, .04, .04); if (++k >= n) clearInterval(id); }, 70); } });
    every(5000, () => { if (Math.random() < .25) { auChirp(420, 380, .5, .05); setTimeout(() => auChirp(420, 370, .7, .05), 600); } }); },
  ocean() { const g = auNoise("brown", [["lowpass", 650]], .5); auLFO(g.gain, .085, .42, .5); const h = auNoise("pink", [["highpass", 1200]], .08); auLFO(h.gain, .085, .07, .08); },
  night() { const wnd = auNoise("pink", [["bandpass", 350, .5]], .08); auLFO(wnd.gain, .04, .05, .09);
    every(600, () => { if (Math.random() < .6) { let k = 0; const f = R(3800, 4400); const id = setInterval(() => { auChirp(f, f, .035, .025); if (++k >= 3) clearInterval(id); }, 60); } }); },
  snow() { const wnd = auNoise("pink", [["bandpass", 420, .4]], .2); auLFO(wnd.gain, .06, .14, .2); auNoise("brown", [["lowpass", 200]], .15); },
  meadow() { const wnd = auNoise("pink", [["bandpass", 700, .5]], .06); auLFO(wnd.gain, .08, .04, .06);
    every(1300, () => { if (Math.random() < .55) { const n = 2 + (Math.random() * 4 | 0), f = R(2400, 3600); for (let i = 0; i < n; i++) setTimeout(() => auChirp(f * R(.9, 1.15), f * R(1.2, 1.5), R(.06, .12), .05), i * R(90, 150)); } }); },
};
function ambSfx(kind) {
  if (!AU.ctx || !AU.scene) return;
  if (kind === "thunder") { const c = AU.ctx, s = c.createBufferSource(); s.buffer = AU.bufs.brown; const f = c.createBiquadFilter(); f.type = "lowpass"; f.frequency.value = 160;
    const g = c.createGain(), t = c.currentTime; g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(1.6, t + .15); g.gain.exponentialRampToValueAtTime(.0001, t + 3.5);
    s.connect(f); f.connect(g); g.connect(AU.master); s.start(t); s.stop(t + 3.6); }
  if (kind === "crackle") for (let i = 0; i < 8; i++) setTimeout(() => auBurst(R(1500, 5000), .03, .5, 3), i * R(20, 60));
  if (kind === "gust") auBurst(500, 1.6, .5, .4);
}
function ambience(scene, vol) {
  if (scene && !AU.ctx) { // browsers need a click before sound can start
    try { AU.ctx = new AudioContext(); } catch (e) { return; }
    AU.master = AU.ctx.createGain(); AU.master.connect(AU.ctx.destination); AU.bufs = {white: noiseBuf(AU.ctx, "white"), pink: noiseBuf(AU.ctx, "pink"), brown: noiseBuf(AU.ctx, "brown")};
  }
  if (!AU.ctx) return;
  AU.master.gain.setTargetAtTime(scene ? vol * .8 : 0, AU.ctx.currentTime, .3);
  if (scene === AU.scene) return;
  AU.nodes.forEach(n => { try { n.stop ? n.stop() : n.disconnect(); } catch (e) {} }); AU.timers.forEach(clearInterval); AU.nodes = []; AU.timers = [];
  AU.scene = scene;
  if (scene && SOUNDS[scene]) SOUNDS[scene]();
  if (AU.ctx.state === "suspended") { AU.ctx.resume(); document.addEventListener("pointerdown", () => AU.ctx.resume(), {once: true}); }
}

// ---------- ambience widget + customize panel ----------
function renderAmbWidget() {
  const el = $("#w-amb"); if (!el) return; const c = sceneCfg();
  el.innerHTML = `<div class="amb"><div class="chips">${Object.entries(SCENES).filter(([k]) => k !== "custom" || c.bgfile).map(([k, s]) => `<button class="chipb ${c.scene === k ? "on" : ""}" onclick="setScene('${k}')" title="${s.name}">${s.em} ${s.name}</button>`).join("")}</div></div>
    <div class="row" style="margin-top:12px;flex-wrap:nowrap"><button class="btn sm ${c.sound ? "pri" : ""}" onclick="setAmb({sound:${!c.sound}})" ${c.scene === "none" || c.scene === "custom" ? "disabled title='Pick a scene first'" : ""}>${c.sound ? "🔊 Sound on" : "🔈 Sound off"}</button>
      <input type="range" min="0" max="1" step=".05" value="${c.vol}" style="flex:1" oninput="setAmb({vol:+this.value},true)" title="Volume"></div>
    <div class="small muted" style="margin-top:8px">${c.scene !== "none" && c.scene !== "custom" ? "Tip: click an empty part of the background — the scene reacts." : "Scenes are animated and generated on this PC."}</div>`;
}
async function setScene(k) { await saveHomeCfg({scene: k}); applyScene(); renderAmbWidget(); $("#scenes-grid") && customizeModal(); }
async function setAmb(p, quiet) { const h = await saveHomeCfg(p); applyScene(); if (!quiet) renderAmbWidget(); if (!quiet && $("#scenes-grid")) customizeModal(); }
function customizeModal() {
  const c = sceneCfg();
  modal(`<h2>${ic("palette", "i")}Customize home<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="grouph" style="margin-top:0">Background scene</div>
    <div class="scenes" id="scenes-grid">${Object.entries(SCENES).map(([k, s]) => `<div class="scn ${c.scene === k ? "on" : ""}" onclick="${k === "custom" && !c.bgfile ? "$('#bgfile').click()" : `setScene('${k}')`}"><div class="pv" style="background:${s.bg}">${s.em}</div><b>${s.name}</b></div>`).join("")}</div>
    <div class="row" style="margin-top:8px"><button class="btn sm" onclick="$('#bgfile').click()">${ic("up")}Upload my own picture or video</button><span class="small muted">jpg · png · webp · gif · mp4 · webm</span>
      <input type="file" id="bgfile" accept="image/*,video/mp4,video/webm" style="display:none" onchange="uploadBg(this.files[0])"></div>
    <div class="frm" style="margin-top:14px">
      <label>Ambient sound</label><div class="row" style="flex-wrap:nowrap"><button class="sw ${c.sound ? "on" : ""}" style="margin-left:0" onclick="setAmb({sound:${!c.sound}})"></button><input type="range" min="0" max="1" step=".05" value="${c.vol}" style="flex:1" oninput="setAmb({vol:+this.value},true)"></div>
      <label>Darken background</label><input type="range" min="0" max=".8" step=".05" value="${c.dim}" oninput="setAmb({dim:+this.value},true)">
      <label>Show on every page</label><button class="sw ${c.everywhere ? "on" : ""}" style="margin-left:0" onclick="setAmb({everywhere:${!c.everywhere}})"></button>
      <label>Still image (no motion)</label><button class="sw ${c.still ? "on" : ""}" style="margin-left:0" onclick="setAmb({still:${!c.still}})"></button></div>
    <div class="grouph">Widgets</div>
    <div class="row"><button class="btn pri" onclick="closeModal();homeEdit(true)">${ic("grid")}Edit home layout</button><button class="btn" onclick="closeModal();addWidgetModal()">${ic("plus")}Add widgets</button></div>`, true);
}
async function uploadBg(f) {
  if (!f) return; const fd = new FormData(); fd.append("file", f); toast("Uploading…");
  const r = await fetch("/api/home/background", {method: "POST", body: fd}); const j = await r.json();
  if (!r.ok) return toast(j.error);
  await saveHomeCfg({scene: "custom", bgfile: j.file, bgv: Date.now()}); const bg = $("#scenebg"); if (bg) bg.dataset.f = "";
  applyScene(); customizeModal(); toast("Background set ✓");
}
function sceneInit() {
  addEventListener("resize", () => debounce("scres", () => { if (SC.ctx) sceneResize(); }, 200));
  addEventListener("mousemove", e => { SC.mx = e.clientX / innerWidth; SC.my = e.clientY / innerHeight; }, {passive: true});
  addEventListener("click", sceneClick);
}
