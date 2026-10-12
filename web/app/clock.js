// ================= CLOCK: world clock · alarms · stopwatch · timers (iPhone-style) =================
// Alarms + timers live in the background service (they ring even with this window closed).
// The stopwatch and world clock run here; the stopwatch survives reloads.
const C = {tab: "timers", data: {alarms: [], timers: [], recents: [], sounds: [], ringing: []}, fetched: 0, tick: 0, poll: 0};
const DAYS = ["M", "T", "W", "T", "F", "S", "S"], DAYN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const pad2 = n => String(n).padStart(2, "0");
const fmtHMS = s => { s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return h ? `${h}:${pad2(m)}:${pad2(x)}` : `${pad2(m)}:${pad2(x)}`; };
const fmtSW = ms => { const cs = Math.floor(ms / 10) % 100, s = Math.floor(ms / 1000) % 60, m = Math.floor(ms / 60000) % 60, h = Math.floor(ms / 3600000); return (h ? h + ":" + pad2(m) : pad2(m)) + ":" + pad2(s) + "." + pad2(cs); };
const ampm = t => { const [h, m] = t.split(":").map(Number); return {t: `${h % 12 || 12}:${pad2(m)}`, p: h < 12 ? "AM" : "PM"}; };
const repeatText = d => !d.length ? "Once" : d.length === 7 ? "Every day" : d.join() === "0,1,2,3,4" ? "Weekdays" : d.join() === "5,6" ? "Weekends" : d.map(i => DAYN[i]).join(" ");

async function clockFetch() {
  try { C.data = await api("/api/clock"); C.fetched = Date.now(); } catch (e) { return; }
  renderRingbar(); clockPaint();
}
function clockStart() { // keep data fresh + tick the display while the clock page or a clock widget is on screen
  if (!C.tick) C.tick = setInterval(clockPaintTick, 250);
  if (!C.poll) C.poll = setInterval(clockFetch, 3000);
  clockFetch();
}
function timerLeft(t) { return t.state === "running" ? Math.max(0, t.left - (Date.now() - C.fetched) / 1000) : t.left; }

// ---------- ring banner (inside the app) ----------
function renderRingbar() {
  let b = $("#ringbar");
  if (!b) { b = document.createElement("div"); b.id = "ringbar"; b.className = "ringbar"; document.body.appendChild(b); }
  const r = C.data.ringing || [];
  b.classList.toggle("on", r.length > 0);
  const run = C.data.timers.filter(t => t.state === "running").length, tc = $("#tm-count");
  if (tc) { tc.style.display = run ? "" : "none"; tc.textContent = run; tc.title = run + " timer" + (run > 1 ? "s" : "") + " running"; }
  b.innerHTML = r.map(x => `<span>${x.kind === "alarm" ? "⏰" : "⏱"} <b>${esc(x.label)}</b></span>
    ${x.kind === "alarm" && x.snooze ? `<button class="btn sm" onclick="api('/api/alarms/${x.id}/snooze',{method:'POST'}).then(clockFetch)">Snooze</button>` : ""}
    ${x.kind === "timer" ? `<button class="btn sm" onclick="tmrAct(${x.id},'add')">+1 min</button>` : ""}
    <button class="btn sm pri" onclick="${x.kind === "alarm" ? `api('/api/alarms/${x.id}/stop',{method:'POST'}).then(clockFetch)` : `tmrAct(${x.id},'stop')`}">Stop</button>`).join("<span style='opacity:.3'>|</span>");
}

// ---------- the Clock page ----------
function renderClock(sub) {
  if (sub && ["world", "alarms", "stopwatch", "timers"].includes(sub)) C.tab = sub;
  $("#ctabs").innerHTML = [["world", "globe", "World Clock"], ["alarms", "alarm", "Alarms"], ["stopwatch", "watch", "Stopwatch"], ["timers", "timer", "Timers"]]
    .map(([k, i, l]) => `<button class="${C.tab === k ? "on" : ""}" onclick="C.tab='${k}';history.replaceState(null,'','#clock/${k}');renderClock()">${ic(i)}${l}</button>`).join("");
  const body = $("#cbody");
  if (C.tab === "stopwatch") body.innerHTML = `<div class="card" style="max-width:640px;margin:0 auto"><div data-w="swfull"></div><div class="muted small" style="text-align:center;margin-top:10px">Space starts / stops · keeps running if you close the window</div></div>`;
  else if (C.tab === "world") body.innerHTML = `<div class="card" style="max-width:760px;margin:0 auto"><h3>${ic("globe")}World clock<button class="btn sm" onclick="cityModal()">${ic("plus")}Add city</button></h3><div data-w="world"></div></div>`;
  else if (C.tab === "alarms") body.innerHTML = `<div class="card" style="max-width:760px;margin:0 auto"><h3>${ic("alarm")}Alarms<button class="btn sm pri" onclick="alarmModal()">${ic("plus")}Add alarm</button></h3><div data-w="alarms"></div>
      <div class="muted small" style="margin-top:10px">Alarms ring with sound and a pop-up even when the Daybook window is closed (as long as the PC is on and you're signed in).</div></div>`;
  else body.innerHTML = `<div class="grid2" style="max-width:1100px;margin:0 auto">${tmrNewHTML()}<div class="card"><h3>${ic("timer")}Running</h3><div data-w="timers"></div></div></div>`;
  clockStart(); clockPaint();
}
function clockPaint() { // full repaint of every clock widget currently on screen
  $$("[data-w=world]").forEach(el => el.innerHTML = worldHTML(el.dataset.compact));
  $$("[data-w=alarms]").forEach(el => el.innerHTML = alarmsHTML(el.dataset.compact));
  $$("[data-w=timers]").forEach(el => el.innerHTML = timersHTML(el.dataset.compact));
  $$("[data-w=sw]").forEach(el => el.innerHTML = swHTML(true));
  $$("[data-w=swfull]").forEach(el => el.innerHTML = swHTML(false));
  clockPaintTick();
}
function clockPaintTick() { // cheap per-frame updates (numbers only)
  if (!$("[data-w], #sw-time")) { clearInterval(C.tick); clearInterval(C.poll); C.tick = C.poll = 0; return; }
  const now = new Date();
  $$(".wc-live").forEach(el => { const z = el.dataset.z, t = zoneTime(z, now); el.querySelector(".ct").innerHTML = `${t.hm}<small>${t.p}</small>`; drawDial(el.querySelector(".dial"), t); });
  C.data.timers.forEach(t => { const el = document.getElementById("tl-" + t.id); if (el) { const left = timerLeft(t); el.textContent = fmtHMS(left);
    const ring = document.getElementById("tr-" + t.id); if (ring) ring.style.strokeDashoffset = String(113 * (1 - left / t.seconds)); } });
  const sw = swState(), el = $$("#sw-time, .sw-time");
  el.forEach(e => e.textContent = fmtSW(swElapsed(sw)));
  const cur = $$(".lap.cur span:last-child"); cur.forEach(e => e.textContent = fmtSW(swElapsed(sw) - sw.laps.reduce((a, b) => a + b, 0)));
}

// ---------- world clock ----------
function homeCfg() { try { return JSON.parse(S.settings.home || "{}"); } catch (e) { return {}; } }
async function saveHomeCfg(patch) { const h = {...homeCfg(), ...patch}; await saveSetting("home", JSON.stringify(h)); return h; }
const cities = () => homeCfg().cities || ["America/New_York", "Europe/London", "Asia/Tokyo"];
function zoneTime(z, now = new Date()) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", {timeZone: z, hour: "numeric", minute: "2-digit", second: "2-digit", hour12: true, year: "numeric", month: "2-digit", day: "2-digit"})
    .formatToParts(now).map(x => [x.type, x.value]));
  const local = new Date(now.toLocaleString("en-US")), there = new Date(now.toLocaleString("en-US", {timeZone: z}));
  const diffH = Math.round((there - local) / 36e5 * 2) / 2, dd = there.getDate() - local.getDate();
  const day = dd === 0 ? "Today" : (dd === 1 || dd < -1) ? "Tomorrow" : "Yesterday";
  const h24 = there.getHours();
  return {hm: `${p.hour}:${p.minute}`, p: p.dayPeriod, h: h24, m: there.getMinutes(), s: there.getSeconds(), day, diff: diffH, night: h24 < 6 || h24 >= 19};
}
const cityName = z => z.split("/").pop().replace(/_/g, " ");
function dialSVG(size) {
  const ticks = Array.from({length: 12}, (_, i) => { const a = i * Math.PI / 6, r1 = 17, r2 = i % 3 ? 18.5 : 16; return `<line class="tick" x1="${20 + r1 * Math.sin(a)}" y1="${20 - r1 * Math.cos(a)}" x2="${20 + r2 * Math.sin(a)}" y2="${20 - r2 * Math.cos(a)}"/>`; }).join("");
  return `<svg class="dial" width="${size}" height="${size}" viewBox="0 0 40 40"><circle class="face" cx="20" cy="20" r="19.5"/>${ticks}<line class="hh" x1="20" y1="20" x2="20" y2="11" stroke-width="2.2"/><line class="mh" x1="20" y1="20" x2="20" y2="6" stroke-width="1.6"/><line class="sh" x1="20" y1="23" x2="20" y2="5" stroke-width=".8"/><circle cx="20" cy="20" r="1.4" fill="var(--warn)"/></svg>`;
}
function drawDial(svg, t) {
  if (!svg) return;
  svg.classList.toggle("night", t.night);
  const set = (cls, deg) => svg.querySelector(cls).setAttribute("transform", `rotate(${deg} 20 20)`);
  set(".hh", (t.h % 12 + t.m / 60) * 30); set(".mh", (t.m + t.s / 60) * 6); set(".sh", t.s * 6);
}
function worldHTML(compact) {
  const zs = [Intl.DateTimeFormat().resolvedOptions().timeZone, ...cities()];
  return zs.slice(0, compact ? 4 : 30).map((z, i) => { const t = zoneTime(z);
    return `<div class="wclock wc-live ${compact ? "sm" : ""}" data-z="${z}">${dialSVG(compact ? 40 : 54)}
      <div class="cn"><b>${i === 0 ? "Here · " + esc(cityName(z)) : esc(cityName(z))}</b><span>${t.day}, ${i === 0 ? "local time" : (t.diff >= 0 ? "+" : "") + t.diff + " HRS"}</span></div>
      <div class="ct">${t.hm}<small>${t.p}</small></div>
      ${!compact && i > 0 ? `<button class="iconbtn" title="Remove" onclick="removeCity('${z}')">${ic("x")}</button>` : ""}</div>`; }).join("")
    + (compact ? `<div class="row" style="margin-top:8px"><button class="btn sm ghost" onclick="cityModal()">${ic("plus")}Add city</button></div>` : "");
}
function cityModal() {
  let zones = []; try { zones = Intl.supportedValuesOf("timeZone"); } catch (e) { zones = ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Europe/London", "Europe/Paris", "Asia/Tokyo", "Australia/Sydney"]; }
  modal(`<h2>${ic("globe", "i")}Add a city<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <input class="f" id="cz-q" placeholder="Search — e.g. London, Tokyo, Sao Paulo, Lagos" oninput="cityList()" autofocus>
    <div id="cz-l" style="max-height:50vh;overflow:auto;margin-top:10px"></div>`);
  window._zones = zones; cityList(); setTimeout(() => $("#cz-q").focus(), 30);
}
function cityList() {
  const q = $("#cz-q").value.toLowerCase().replace(/\s+/g, "_");
  $("#cz-l").innerHTML = window._zones.filter(z => z.toLowerCase().includes(q)).slice(0, 80).map(z => { const t = zoneTime(z);
    return `<div class="cat" onclick="addCity('${z}')"><b>${esc(cityName(z))}</b><span class="muted small">${esc(z.split("/")[0])}</span><span class="c">${t.hm} ${t.p}</span></div>`; }).join("") || `<div class="empty">No match</div>`;
}
async function addCity(z) { const c = cities(); if (!c.includes(z)) c.push(z); await saveHomeCfg({cities: c}); closeModal(); clockPaint(); toast(cityName(z) + " added"); }
async function removeCity(z) { await saveHomeCfg({cities: cities().filter(x => x !== z)}); clockPaint(); }

// ---------- alarms ----------
function alarmsHTML(compact) {
  const a = C.data.alarms;
  if (!a.length) return `<div class="empty"><b>No alarms</b><button class="btn sm pri" style="margin-top:8px" onclick="alarmModal()">${ic("plus")}Add alarm</button></div>`;
  const next = a.filter(x => x.next).sort((x, y) => x.next.localeCompare(y.next))[0];
  return (compact && next ? `<div class="small muted" style="margin-bottom:4px">Next: <b style="color:var(--fg)">${esc(next.label || "Alarm")}</b> · ${dayName(next.next)} ${tm(next.next)}</div>` : "")
    + a.slice(0, compact ? 4 : 99).map(x => { const t = ampm(x.time);
      return `<div class="alarm ${x.enabled ? "" : "off"} ${compact ? "sm" : ""}"><div style="min-width:0">
        <div class="at" onclick="alarmModal(${x.id})">${t.t}<small>${t.p}</small></div>
        <div class="al" onclick="alarmModal(${x.id})">${esc(x.label || "Alarm")}, ${repeatText(x.days)}${x.snoozed_until ? " · snoozed" : ""}</div></div>
        <button class="sw ${x.enabled ? "on" : ""}" title="${x.enabled ? "On" : "Off"}" onclick="alarmToggle(${x.id},${x.enabled ? 0 : 1})"></button></div>`; }).join("")
    + (compact ? `<div class="row" style="margin-top:8px"><button class="btn sm ghost" onclick="alarmModal()">${ic("plus")}Add alarm</button><button class="btn sm ghost" onclick="go('clock','alarms')">All alarms</button></div>` : "");
}
async function alarmToggle(id, on) { await api("/api/alarms/" + id, {method: "PATCH", body: {enabled: on}}); clockFetch(); }
function alarmModal(id) {
  const a = id ? C.data.alarms.find(x => x.id === id) : {time: "07:00", label: "", days: [], sound: "Radar", snooze: 1};
  window._ad = [...a.days];
  modal(`<h2>${ic("alarm", "i")}${id ? "Edit alarm" : "Add alarm"}<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <input class="f" type="time" id="al-t" value="${a.time}" style="font:300 44px/1 Inter;text-align:center;padding:10px">
    <div class="frm"><label>Repeat</label><div><div class="days" id="al-d">${DAYS.map((d, i) => `<button type="button" class="${a.days.includes(i) ? "on" : ""}" title="${DAYN[i]}" onclick="alDay(${i})">${d}</button>`).join("")}</div>
      <div class="row" style="margin-top:6px;gap:6px"><button class="chipb" onclick="alDays([0,1,2,3,4])">Weekdays</button><button class="chipb" onclick="alDays([5,6])">Weekends</button><button class="chipb" onclick="alDays([0,1,2,3,4,5,6])">Every day</button><button class="chipb" onclick="alDays([])">Once</button></div></div>
    <label>Label</label><input class="f" id="al-l" value="${esc(a.label)}" placeholder="Alarm — e.g. Wake up, Unleash U">
    <label>Sound</label><div class="row" style="flex-wrap:nowrap"><select class="f" id="al-s">${C.data.sounds.map(s => `<option ${s === a.sound ? "selected" : ""}>${s}</option>`).join("")}</select><button class="btn" onclick="previewSound($('#al-s').value)">${ic("play")}Play</button></div>
    <label>Snooze</label><button class="sw ${a.snooze ? "on" : ""}" id="al-z" style="margin-left:0" onclick="this.classList.toggle('on')"></button></div>
    <div class="row" style="margin-top:16px"><button class="btn pri" onclick="alarmSave(${id || 0})">${ic("check")}Save</button>${id ? `<div class="sp"></div><button class="btn ghost danger" onclick="alarmDel(${id})">${ic("trash")}Delete alarm</button>` : ""}</div>`);
}
function alDay(i) { const d = window._ad; d.includes(i) ? d.splice(d.indexOf(i), 1) : d.push(i); $$("#al-d button").forEach((b, j) => b.classList.toggle("on", d.includes(j))); }
function alDays(arr) { window._ad = [...arr]; $$("#al-d button").forEach((b, j) => b.classList.toggle("on", arr.includes(j))); }
async function alarmSave(id) {
  const body = {time: $("#al-t").value, label: $("#al-l").value, days: window._ad, sound: $("#al-s").value, snooze: $("#al-z").classList.contains("on"), enabled: 1};
  try { const a = await api(id ? "/api/alarms/" + id : "/api/alarms", {method: id ? "PATCH" : "POST", body}); closeModal();
    toast(`Alarm set — ${a.next ? dayName(a.next) + " " + tm(a.next) : "off"}`); clockFetch(); } catch (e) { toast(e.message); }
}
async function alarmDel(id) { await api("/api/alarms/" + id, {method: "DELETE"}); closeModal(); clockFetch(); }
let _snd;
function previewSound(n) { if (_snd) { _snd.pause(); } _snd = new Audio("/clock-sounds/" + n + ".wav"); _snd.play(); setTimeout(() => _snd && _snd.pause(), 4000); }

// ---------- stopwatch ----------
function swState() { try { return JSON.parse(localStorage.getItem("daybook-sw")) || {run: false, t0: 0, acc: 0, laps: []}; } catch (e) { return C.sw || (C.sw = {run: false, t0: 0, acc: 0, laps: []}); } }
function swSave(s) { C.sw = s; try { localStorage.setItem("daybook-sw", JSON.stringify(s)); } catch (e) {} }
const swElapsed = s => s.acc + (s.run ? Date.now() - s.t0 : 0);
function swHTML(compact) {
  const s = swState(), total = swElapsed(s), laps = s.laps, lt = laps.length > 1 ? [Math.min(...laps), Math.max(...laps)] : [];
  const lapRows = (total > 0 ? [`<div class="lap cur"><span>Lap ${laps.length + 1}</span><span>${fmtSW(total - laps.reduce((a, b) => a + b, 0))}</span></div>`] : [])
    .concat(laps.map((l, i) => [l, i]).reverse().map(([l, i]) => `<div class="lap ${l === lt[0] ? "best" : l === lt[1] ? "worst" : ""}"><span>Lap ${i + 1}</span><span>${fmtSW(l)}</span></div>`));
  return `<div class="bigtime ${compact ? "sm" : ""} ${compact ? "sw-time" : ""}" ${compact ? "" : 'id="sw-time"'}>${fmtSW(total)}</div>
    <div class="cbtns"><button class="rbtn ${compact ? "sm" : ""}" ${!s.run && !total ? "disabled" : ""} onclick="${s.run ? "swLap()" : "swReset()"}">${s.run || !total ? "Lap" : "Reset"}</button>
      <button class="rbtn ${compact ? "sm" : ""} ${s.run ? "stop" : "go"}" onclick="swToggle()">${s.run ? "Stop" : "Start"}</button></div>
    <div class="laps" ${compact ? 'style="max-height:150px;overflow:auto"' : ""}>${lapRows.slice(0, compact ? 4 : 999).join("")}</div>`;
}
function swToggle() { const s = swState(); if (s.run) { s.acc += Date.now() - s.t0; s.run = false; } else { s.t0 = Date.now(); s.run = true; } swSave(s); clockPaint(); clockStart(); }
function swLap() { const s = swState(); const total = swElapsed(s); s.laps.push(total - s.laps.reduce((a, b) => a + b, 0)); swSave(s); clockPaint(); }
function swReset() { swSave({run: false, t0: 0, acc: 0, laps: []}); clockPaint(); }

// ---------- timers ----------
const PRESETS = [[60, "1 min", ""], [180, "3 min", ""], [300, "5 min", ""], [600, "10 min", ""], [900, "15 min", ""], [1500, "🎯 Focus 25", "Focus"], [300, "☕ Break 5", "Break"], [1800, "30 min", ""], [2700, "45 min", ""], [3600, "1 hour", ""]];
const presetBtn = ([s, l, lbl]) => `<button class="chipb" onclick="tmrStart(${s},'${lbl}')">${l}</button>`;
function tmrNewHTML() {
  return `<div class="card"><h3>${ic("timer")}New timer</h3>
    <div class="hms"><label><input class="f" type="number" min="0" max="99" id="tm-h" value="0">hours</label><b style="font-size:28px">:</b>
      <label><input class="f" type="number" min="0" max="59" id="tm-m" value="5">min</label><b style="font-size:28px">:</b>
      <label><input class="f" type="number" min="0" max="59" id="tm-s" value="0">sec</label></div>
    <div class="frm"><label>Label</label><input class="f" id="tm-l" placeholder="Timer — e.g. Facebook uploads, laundry">
      <label>When it ends</label><div class="row" style="flex-wrap:nowrap"><select class="f" id="tm-snd">${(C.data.sounds.length ? C.data.sounds : ["Chimes"]).map(s => `<option ${s === "Chimes" ? "selected" : ""}>${s}</option>`).join("")}</select><button class="btn" onclick="previewSound($('#tm-snd').value)">${ic("play")}</button></div></div>
    <div style="text-align:center;margin:16px 0 6px"><button class="rbtn go" onclick="tmrStartForm()">Start</button></div>
    <div class="grouph">Presets</div><div class="presets">${PRESETS.map(presetBtn).join("")}</div>
    ${C.data.recents.length ? `<div class="grouph">Recents</div><div class="presets">${C.data.recents.map((r, i) => `<button class="chipb" onclick="tmrRecent(${i})">${fmtHMS(r.seconds)}${r.label ? " · " + esc(r.label) : ""}</button>`).join("")}</div>` : ""}</div>`;
}
function tmrRecent(i) { const r = C.data.recents[i]; tmrStart(r.seconds, r.label, r.sound); }
function tmrStartForm() {
  const secs = (+$("#tm-h").value || 0) * 3600 + (+$("#tm-m").value || 0) * 60 + (+$("#tm-s").value || 0);
  if (secs < 1) return toast("Set a time first");
  tmrStart(secs, $("#tm-l").value, $("#tm-snd").value);
}
async function tmrStart(seconds, label = "", sound = "Chimes") {
  await api("/api/timers", {method: "POST", body: {seconds, label, sound}});
  toast(`⏱ ${label || "Timer"} — ${fmtHMS(seconds)}`); await clockFetch();
  if (C.tab === "timers" && S.view === "clock") renderClock();
}
async function tmrAct(id, a) { await api(`/api/timers/${id}/${a}`, {method: "POST"}); clockFetch(); }
function timersHTML(compact) {
  const ts = C.data.timers;
  const list = ts.map(t => { const left = timerLeft(t), ring = t.state === "ringing";
    return `<div class="tmr ${ring ? "ring" : ""}"><svg class="ring" width="44" height="44" viewBox="0 0 44 44"><circle cx="22" cy="22" r="18" fill="none" stroke="var(--line2)" stroke-width="4"/>
        <circle id="tr-${t.id}" cx="22" cy="22" r="18" fill="none" stroke="${ring ? "var(--warn)" : t.state === "paused" ? "var(--muted)" : "var(--a2)"}" stroke-width="4" stroke-linecap="round" stroke-dasharray="113" style="stroke-dashoffset:${113 * (1 - left / t.seconds)};transform:rotate(-90deg);transform-origin:center"/></svg>
      <div class="tl"><b id="tl-${t.id}">${ring ? "00:00" : fmtHMS(left)}</b><span>${esc(t.label || "Timer")} · ${fmtHMS(t.seconds)}${t.state === "paused" ? " · paused" : ring ? " · done!" : ""}</span></div>
      ${ring ? `<button class="btn sm" onclick="tmrAct(${t.id},'add')">+1 min</button><button class="btn sm" onclick="tmrAct(${t.id},'repeat')">Repeat</button><button class="btn sm pri" onclick="tmrAct(${t.id},'stop')">Stop</button>`
        : `<button class="iconbtn" title="+1 minute" onclick="tmrAct(${t.id},'add')">+1</button>
           <button class="iconbtn" title="${t.state === "paused" ? "Resume" : "Pause"}" onclick="tmrAct(${t.id},'${t.state === "paused" ? "resume" : "pause"}')">${ic(t.state === "paused" ? "play" : "pause")}</button>
           <button class="iconbtn" title="Cancel" onclick="tmrAct(${t.id},'cancel')">${ic("x")}</button>`}</div>`; }).join("");
  if (!compact) return list || `<div class="empty"><b>No timers running</b>Pick a preset or set a time.</div>`;
  return (list || `<div class="muted small" style="margin-bottom:6px">No timers running — tap a preset:</div>`)
    + `<div class="presets" style="margin-top:10px">${PRESETS.slice(0, 7).map(presetBtn).join("")}
      <button class="chipb" onclick="go('clock','timers')">Custom…</button></div>`;
}
// timer for a task on the schedule (⏱ on a timeline block)
function taskTimer(label, seconds) { tmrStart(Math.max(60, Math.round(seconds)), label); }
