// ================= VOICE: dictation (local Whisper), mic choice, voice memos =================
// Loaded before the main script: only definitions here, nothing runs at load time.
const V = {stream: null, rec: null, chunks: [], ctx: null, an: null, raf: 0, start: 0, target: null, mode: null, lastField: null, cancel: false};
const store = {get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }};

async function micStream() {
  const id = store.get("daybook-mic", "");
  const audio = {echoCancellation: true, noiseSuppression: true, autoGainControl: true};
  if (id) audio.deviceId = {exact: id};
  try { return await navigator.mediaDevices.getUserMedia({audio}); }
  catch (e) {
    if (id && e.name === "OverconstrainedError") { store.set("daybook-mic", ""); return navigator.mediaDevices.getUserMedia({audio: true}); }
    throw e;
  }
}
function micError(e) {
  toast(e.name === "NotAllowedError" ? "Microphone blocked — click the 🎤/lock icon in the address bar and allow it"
    : e.name === "NotFoundError" ? "No microphone found — plug one in or pick another in Settings → Voice" : "Microphone error: " + e.message);
}
function levelLoop(canvas, onLevel) {
  const buf = new Uint8Array(V.an.fftSize), c = canvas && canvas.getContext("2d"), hist = [];
  const draw = () => {
    V.an.getByteTimeDomainData(buf);
    let peak = 0; for (const v of buf) peak = Math.max(peak, Math.abs(v - 128) / 128);
    onLevel && onLevel(peak);
    if (c) {
      const w = canvas.width = canvas.clientWidth * devicePixelRatio, h = canvas.height = canvas.clientHeight * devicePixelRatio;
      hist.push(peak); while (hist.length > 60) hist.shift();
      c.clearRect(0, 0, w, h); c.fillStyle = getComputedStyle(document.body).getPropertyValue("--a2") || "#4fd1ff";
      const bw = w / 60;
      hist.forEach((p, i) => { const bh = Math.max(2 * devicePixelRatio, Math.min(1, p * 2.2) * h); c.fillRect(i * bw + bw * .2, (h - bh) / 2, bw * .6, bh); });
    }
    V.raf = requestAnimationFrame(draw);
  };
  draw();
}
async function startRecording(canvas, onLevel) {
  V.stream = await micStream();
  V.ctx = new AudioContext(); V.an = V.ctx.createAnalyser(); V.an.fftSize = 1024;
  V.ctx.createMediaStreamSource(V.stream).connect(V.an);
  const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
  V.rec = new MediaRecorder(V.stream, mime ? {mimeType: mime} : {}); V.chunks = [];
  V.rec.ondataavailable = e => e.data.size && V.chunks.push(e.data);
  V.rec.start(250); V.start = Date.now(); V.paused = 0;
  levelLoop(canvas, onLevel);
}
function stopRecording() {
  return new Promise(res => {
    if (!V.rec) return res(null);
    V.rec.onstop = () => { const blob = new Blob(V.chunks, {type: V.rec.mimeType || "audio/webm"}); cleanupRec(); res(blob); };
    V.rec.state !== "inactive" ? V.rec.stop() : V.rec.onstop();
  });
}
function cleanupRec() {
  cancelAnimationFrame(V.raf); V.stream && V.stream.getTracks().forEach(t => t.stop());
  V.ctx && V.ctx.close().catch(() => {}); V.stream = V.rec = V.ctx = V.an = null;
}
const mmss = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

// ---------- Top recording indicator & dictation ----------
function topRecPill() {
  let p = $("#top-rec-pill");
  if (!p) {
    p = document.createElement("div");
    p.id = "top-rec-pill";
    p.className = "top-rec-pill";
    p.innerHTML = `<span class="rec-dot"></span><span id="top-rec-lbl" class="rec-lbl">Recording</span><canvas id="top-rec-wave" width="54" height="16"></canvas><span id="top-rec-t" class="rec-t">0:00</span><button class="top-rec-btn top-rec-stop" id="top-rec-stop" title="Stop & save">${ic("check")}Done</button><button class="top-rec-btn top-rec-cancel" id="top-rec-cancel" title="Discard">${ic("x")}</button>`;
    const topmic = $("#topmic");
    if (topmic && topmic.parentElement) {
      topmic.parentElement.style.position = "relative";
      topmic.before(p);
    } else {
      const topbar = $(".topbar");
      if (topbar) topbar.appendChild(p); else document.body.appendChild(p);
    }
  }
  return p;
}

function showTopRecIndicator(label, onStop, onCancel) {
  const p = topRecPill();
  const lbl = $("#top-rec-lbl"); if (lbl) lbl.textContent = label || "Recording…";
  p.style.display = "inline-flex";
  p.classList.add("on");
  const topmic = $("#topmic");
  if (topmic) topmic.classList.add("rec");
  const stopBtn = $("#top-rec-stop");
  if (stopBtn) stopBtn.onclick = (e) => { e.stopPropagation(); onStop && onStop(); };
  const cancelBtn = $("#top-rec-cancel");
  if (cancelBtn) cancelBtn.onclick = (e) => { e.stopPropagation(); onCancel ? onCancel() : dictateStop(true); };
}

function hideTopRecIndicator() {
  const p = $("#top-rec-pill");
  if (p) {
    p.classList.remove("on");
    p.style.display = "none";
  }
  const topmic = $("#topmic");
  if (topmic) topmic.classList.remove("rec");
  $$(".micbtn").forEach(b => b.classList.remove("rec"));
}

async function quickVoiceRecord() {
  if (V.mode === "quickmemo") return quickVoiceStop();
  if (V.mode) return dictateStop();
  V.mode = "quickmemo";
  showTopRecIndicator("Voice Memo", quickVoiceStop, quickVoiceCancel);
  const pill = topRecPill();
  try {
    await startRecording(pill.querySelector("canvas"));
  } catch (e) {
    V.mode = null;
    hideTopRecIndicator();
    return micError(e);
  }
  V.tick = setInterval(() => {
    const s = (Date.now() - V.start) / 1000;
    const t = $("#top-rec-t");
    if (t) t.textContent = mmss(s);
  }, 250);
}

async function quickVoiceStop() {
  if (V.mode !== "quickmemo") return;
  clearInterval(V.tick);
  hideTopRecIndicator();
  const blob = await stopRecording();
  V.mode = null;
  if (!blob || blob.size < 2000) return toast("Too short — nothing recorded");
  M.recBlob = blob;
  M.recKind = "audio";
  memoSaveModal(blob, (Date.now() - V.start) / 1000);
}

function quickVoiceCancel() {
  if (V.mode !== "quickmemo") return;
  clearInterval(V.tick);
  hideTopRecIndicator();
  cleanupRec();
  V.mode = null;
  toast("Voice memo discarded");
}

function trackFields() {
  document.addEventListener("focusin", e => { const t = e.target;
    if (t.matches("textarea, input.f:not([type]), input.f[type=text], input.f[type=search], #cinput, #n-title")) V.lastField = t; });
}
function dictBar() {
  let b = $("#dict");
  if (!b) {
    b = document.createElement("div"); b.id = "dict"; b.className = "dict";
    b.innerHTML = `<span class="dot"></span><span id="dict-lbl" class="small">Listening…</span><canvas></canvas><span class="dt" id="dict-t">0:00</span>
      <button class="btn sm pri" onclick="dictateStop()">${ic("check")}Done</button><button class="iconbtn" title="Cancel (Esc)" onclick="dictateStop(true)">${ic("x")}</button>`;
    document.body.appendChild(b);
  }
  return b;
}
async function dictate(target) {
  if (V.mode === "quickmemo") return quickVoiceStop();
  if (V.mode) return dictateStop();
  target = target || (V.lastField && document.body.contains(V.lastField) ? V.lastField : null);
  if (!target) { return quickVoiceRecord(); }
  V.target = target; V.mode = "dict";
  const bar = dictBar(); bar.classList.remove("busy"); $("#dict-lbl").textContent = "Listening… speak now";
  showTopRecIndicator("Dictating…", () => dictateStop(), () => dictateStop(true));
  try { await startRecording(bar.querySelector("canvas")); }
  catch (e) { V.mode = null; hideTopRecIndicator(); micError(e); return; }
  bar.classList.add("on");
  $$(".micbtn").forEach(b => b.classList.toggle("rec", b._for === target));
  V.tick = setInterval(() => {
    const s = (Date.now() - V.start) / 1000;
    $("#dict-t").textContent = mmss(s);
    const t = $("#top-rec-t");
    if (t) t.textContent = mmss(s);
  }, 250);
}
async function dictateStop(cancel) {
  if (V.mode !== "dict") return;
  clearInterval(V.tick);
  hideTopRecIndicator();
  const blob = await stopRecording(), bar = $("#dict"), target = V.target;
  $$(".micbtn").forEach(b => b.classList.remove("rec"));
  if (cancel || !blob || blob.size < 1500) { bar.classList.remove("on"); V.mode = null; if (!cancel) toast("Didn't catch anything"); return; }
  bar.classList.add("busy"); $("#dict-lbl").textContent = "Transcribing on this PC…";
  try {
    const fd = new FormData(); fd.append("audio", blob, "dictation.webm");
    const r = await fetch("/api/stt", {method: "POST", body: fd}); const j = await r.json();
    if (!r.ok) throw new Error(j.error);
    if (!j.text) toast("Didn't catch anything — try speaking a little closer to the mic");
    else insertText(target, j.text);
  } catch (e) { toast(e.message); }
  bar.classList.remove("on", "busy"); V.mode = null;
}
function insertText(el, text) {
  el.focus();
  const s = el.selectionStart ?? el.value.length, e = el.selectionEnd ?? el.value.length, before = el.value.slice(0, s);
  const pre = before && !/\s$/.test(before) ? " " : "";
  el.value = before + pre + text + el.value.slice(e);
  const pos = s + pre.length + text.length; el.setSelectionRange && el.setSelectionRange(pos, pos);
  el.dispatchEvent(new Event("input", {bubbles: true})); el.dispatchEvent(new Event("change", {bubbles: true}));
}
// Adds a 🎤 button next to (or inside) a field. `host` = element to append the button to.
function micFor(field, host, cls = "iconbtn") {
  if (!field || !host || host.querySelector(".micbtn")) return;
  const b = document.createElement("button"); b.type = "button"; b.className = cls + " micbtn"; b.title = "Dictate (Alt M) — speech to text, on this PC";
  b.innerHTML = ic("mic"); b._for = field; b.onclick = e => { e.preventDefault(); V.mode ? dictateStop() : dictate(field); };
  host.appendChild(b);
}

// ---------- Settings → Voice ----------
async function renderVoiceSettings() {
  const host = $("#voiceset"); if (!host) return;
  const st = await api("/api/stt/status");
  let devs = [];
  try { devs = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === "audioinput"); } catch (e) {}
  const named = devs.some(d => d.label), cur = store.get("daybook-mic", "");
  host.innerHTML = `<div class="frm">
    <label>Microphone</label><div class="row" style="flex-wrap:nowrap"><select class="f" id="mic-sel" onchange="setMic(this.value)">
      <option value="">System default</option>${devs.filter(d => d.deviceId && d.deviceId !== "default" && d.deviceId !== "communications").map(d => `<option value="${d.deviceId}" ${d.deviceId === cur ? "selected" : ""}>${esc(d.label || "Microphone")}</option>`).join("")}</select>
      ${named ? "" : `<button class="btn" onclick="micAllow()">Allow mic to see names</button>`}</div>
    <label>Mic level</label><div class="row" style="flex-wrap:nowrap"><div class="meter" style="flex:1"><i id="mic-meter"></i></div><button class="btn sm" id="mic-test" onclick="micTest()">${ic("mic")}Test</button></div>
    <label>Speech model</label><select class="f" onchange="saveSetting('stt_model',this.value).then(()=>{api('/api/stt/prepare',{method:'POST'});toast('Switching model — first use downloads it once');renderVoiceSettings()})">
      ${st.models.map(m => `<option value="${m.id}" ${m.id === st.model ? "selected" : ""}>${m.label} · ${m.size}${m.downloaded ? " ✓" : " (downloads on first use)"}</option>`).join("")}</select>
    ${st.model.endsWith(".en") ? "" : `<label>Language</label><select class="f" onchange="saveSetting('stt_language',this.value)">${[["", "Detect automatically"], ["en", "English"], ["es", "Spanish"], ["pt", "Portuguese"], ["fr", "French"], ["de", "German"], ["it", "Italian"], ["ja", "Japanese"], ["ko", "Korean"], ["zh", "Chinese"], ["ar", "Arabic"], ["hi", "Hindi"]].map(([v, l]) => `<option value="${v}" ${S.settings.stt_language === v ? "selected" : ""}>${l}</option>`).join("")}</select>`}
  </div><div class="muted small" style="margin-top:8px">${st.loading ? "Loading the speech model…" : st.loaded ? "✓ Speech model ready" : "Model loads on first use"} · Everything is transcribed on this PC — audio never leaves it. Press <span class="kbd">Alt M</span> or any 🎤 button to dictate.</div>`;
}
async function micAllow() { try { (await micStream()).getTracks().forEach(t => t.stop()); } catch (e) { micError(e); } renderVoiceSettings(); }
function setMic(id) { store.set("daybook-mic", id); toast("Microphone saved"); }
async function micTest() {
  if (V.mode === "test") { clearTimeout(V.testT); cleanupRec(); V.mode = null; $("#mic-meter").style.width = "0"; $("#mic-test").innerHTML = ic("mic") + "Test"; return; }
  if (V.mode) return;
  try {
    V.stream = await micStream(); V.ctx = new AudioContext(); V.an = V.ctx.createAnalyser(); V.an.fftSize = 1024;
    V.ctx.createMediaStreamSource(V.stream).connect(V.an); V.mode = "test";
    $("#mic-test").innerHTML = ic("stop") + "Stop";
    levelLoop(null, p => { const m = $("#mic-meter"); if (m) m.style.width = Math.min(100, p * 220) + "%"; });
    V.testT = setTimeout(() => V.mode === "test" && micTest(), 15000);
    if (!$("#mic-sel").options[1] || !$("#mic-sel").options[1].textContent.trim() || $("#mic-sel").options[1].textContent === "Microphone") renderVoiceSettings();
  } catch (e) { micError(e); }
}

// ================= VOICE MEMOS page =================
const M = {items: [], labels: [], suggested: [], cur: null, label: "", kind: "", audio: null, peaks: null, recBlob: null, recKind: "audio"};
const memoURL = m => "/memo-media/" + m.id;
const MEMO_LABEL_COLOR = {Journal: "var(--a1)", Idea: "var(--warn)", Meeting: "var(--a2)", "To-do": "var(--ok)", Lyrics: "var(--a3)", Content: "var(--a3)", Personal: "var(--a2)", Learning: "var(--ok)"};
async function renderMemos() {
  const qs = new URLSearchParams({q: ($("#mq") || {}).value || "", label: M.label, kind: M.kind});
  $("#mkinds").innerHTML = [["", "All"], ["audio", "Voice"], ["video", "Video"]].map(([k, l]) => `<button class="${M.kind === k ? "on" : ""}" onclick="M.kind='${k}';renderMemos()">${l}</button>`).join("");
  const j = await api("/api/memos?" + qs); M.items = j.items; M.labels = j.labels; M.suggested = j.suggested;
  $("#mlabels").innerHTML = (j.labels.length ? `<span class="tag ${!M.label ? "on" : ""}" onclick="M.label='';renderMemos()">All labels</span>` : "") +
    j.labels.map(([l, n]) => `<span class="tag ${M.label === l ? "on" : ""}" onclick="M.label=M.label==='${esc(l)}'?'':'${esc(l)}';renderMemos()">${esc(l)} · ${n}</span>`).join("");
  let month = "";
  $("#mlist").innerHTML = j.items.length ? j.items.map(m => {
    const d = new Date(m.memo_date), mh = d.toLocaleDateString([], {month: "long", year: "numeric"});
    const head = mh !== month ? `<div class="grouph">${month = mh}</div>` : "";
    return head + `<div class="memo ${M.cur && M.cur.id === m.id ? "on" : ""}" onclick="openMemo(${m.id})">
      <div class="mt">${m.kind === "video" ? `<span title="Video note" style="color:var(--a3)">${ic("rec")}</span>` : ""}<b>${m.starred ? "★ " : ""}${esc(m.title || (m.status === "done" ? "Untitled memo" : "New memo"))}</b><span class="small muted">${mmss(m.duration)}</span></div>
      <div class="mm"><span>${d.toLocaleDateString([], {weekday: "short", month: "short", day: "numeric"})} · ${tm(m.memo_date)}</span>
        ${m.labels.map(l => `<span class="badge" style="color:${MEMO_LABEL_COLOR[l] || "var(--fg2)"}">${esc(l)}</span>`).join("")}
        ${m.status === "pending" || m.status === "working" ? `<span class="badge ai">Transcribing…</span>` : m.status === "error" ? `<span class="badge" style="color:var(--bad)">error</span>` : ""}
        ${m.source === "imported" ? `<span title="Imported from a phone or file">📱</span>` : ""}</div>
      ${m.transcript ? `<div class="su small muted" style="margin-top:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${esc(m.transcript)}</div>` : ""}</div>`;
  }).join("") : `<div class="empty"><b>No voice memos yet</b>Press the red button to record, or drop phone recordings (m4a, mp3…) below.</div>`;
  if (j.items.some(m => m.status === "pending" || m.status === "working")) {
    debounce("memopoll", () => S.view === "memos" && (renderMemos(), M.cur && openMemo(M.cur.id, true)), 3000);
  } else if (M.cur && (M.cur.status === "pending" || M.cur.status === "working")) {
    const fresh = j.items.find(x => x.id === M.cur.id);
    if (fresh && fresh.status === "done") { openMemo(M.cur.id, true); }
  }
  if (!M.cur && j.items.length && !$("#medit").dataset.init) { $("#medit").dataset.init = 1; }
}
async function memoRecToggle() {
  const btn = $("#recbtn");
  if (V.mode === "memo") {
    clearInterval(V.tick); const blob = await stopRecording(); V.mode = null; btn && btn.classList.remove("on");
    hideTopRecIndicator();
    if ($("#rect")) $("#rect").textContent = "Tap to record";
    if (!blob || blob.size < 2000) return toast("Too short — nothing saved");
    M.recBlob = blob; M.recKind = "audio"; memoSaveModal(blob, (Date.now() - V.start) / 1000);
    return;
  }
  if (V.mode) return;
  try { await startRecording($("#recwave")); } catch (e) { return micError(e); }
  V.mode = "memo"; btn && btn.classList.add("on");
  showTopRecIndicator("Voice Memo", memoRecToggle, () => { cleanupRec(); V.mode = null; hideTopRecIndicator(); const b = $("#recbtn"); if (b) b.classList.remove("on"); if ($("#rect")) $("#rect").textContent = "Tap to record"; });
  V.tick = setInterval(() => {
    const s = (Date.now() - V.start) / 1000;
    if ($("#rect")) $("#rect").textContent = "Recording " + mmss(s) + " · tap to stop";
    const t = $("#top-rec-t"); if (t) t.textContent = mmss(s);
  }, 250);
}
function labelPicker(id, chosen) {
  const all = [...new Set([...M.suggested, ...M.labels.map(([l]) => l), ...chosen])];
  return `<div class="lblchips" id="${id}">${all.map(l => `<span class="tag ${chosen.includes(l) ? "on" : ""}" onclick="this.classList.toggle('on')">${esc(l)}</span>`).join("")}
    <input class="f" style="width:130px;padding:4px 9px;font-size:12.5px" placeholder="+ new label" onkeydown="if(event.key==='Enter'&&this.value.trim()){event.preventDefault();const s=document.createElement('span');s.className='tag on';s.textContent=this.value.trim();s.onclick=()=>s.classList.toggle('on');this.before(s);this.value=''}"></div>`;
}
const pickedLabels = id => $$(`#${id} .tag.on`).map(t => t.textContent.trim());
const localISO = d => new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
function memoSaveModal(blob, secs) {
  modal(`<h2>${ic("mic", "i")}Save voice memo<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="frm"><label>Name</label><input class="f" id="ms-title" placeholder="Leave blank — the local AI names it from what you said">
    <label>Labels</label>${labelPicker("ms-lbl", [])}
    <label>Date</label><input class="f" type="datetime-local" id="ms-date" value="${localISO(new Date())}"></div>
    <div class="muted small" style="margin-top:8px">${mmss(secs)} recorded · it will be transcribed on this PC</div>
    <div class="row" style="margin-top:14px"><button class="btn pri" onclick="memoUpload()">${ic("check")}Save</button><button class="btn ghost danger" onclick="M.recBlob=null;closeModal();toast('Discarded')">Discard</button></div>`);
  setTimeout(() => $("#ms-title").focus(), 50);
}
async function memoUpload() {
  const fd = new FormData(); fd.append("audio", M.recBlob, M.recKind === "video" ? "video-note.webm" : "memo.webm"); fd.append("kind", M.recKind || "audio");
  fd.append("title", $("#ms-title").value); fd.append("labels", JSON.stringify(pickedLabels("ms-lbl")));
  fd.append("date", $("#ms-date").value ? $("#ms-date").value + ":00" : ""); fd.append("source", "recorded");
  closeModal(); toast("Saved — transcribing…");
  const j = await (await fetch("/api/memos", {method: "POST", body: fd})).json(); M.recBlob = null;
  if (S.view === "memos") { await renderMemos(); j.added[0] && openMemo(j.added[0]); } else if (S.view === "today") renderHomeWidgets();
}
function memoImportPick() { $("#mfile").click(); }
async function memoImport(files) {
  files = [...files].filter(f => /\.(m4a|mp3|wav|webm|ogg|opus|aac|flac|mp4|3gp|amr|caf|qta)$/i.test(f.name) || f.type.startsWith("audio/"));
  if (!files.length) return toast("Those aren't audio files — use m4a, mp3, wav, ogg…");
  const fd = new FormData(); fd.append("source", "imported"); fd.append("labels", JSON.stringify(M.label ? [M.label] : []));
  files.forEach(f => { fd.append("audio", f, f.name); fd.append("modified_" + f.name, f.lastModified); });
  toast(`Importing ${files.length} recording${files.length > 1 ? "s" : ""}…`);
  const j = await (await fetch("/api/memos", {method: "POST", body: fd})).json();
  toast(`Imported ${j.added.length}${j.errors.length ? " · " + j.errors.length + " failed" : ""} — transcribing in the background`);
  if (j.errors.length) console.warn(j.errors);
  await renderMemos(); j.added[0] && openMemo(j.added[0]);
}
function memoDropSetup() {
  const d = $("#mdrop"); if (!d || d._ok) return; d._ok = 1;
  ["dragenter", "dragover"].forEach(ev => d.addEventListener(ev, e => { e.preventDefault(); d.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => d.addEventListener(ev, e => { e.preventDefault(); d.classList.remove("over"); }));
  d.addEventListener("drop", e => memoImport(e.dataTransfer.files));
  $("#v-memos").addEventListener("dragover", e => e.preventDefault());
  $("#v-memos").addEventListener("drop", e => { e.preventDefault(); if (e.target.closest("#mdrop")) return; memoImport(e.dataTransfer.files); });
}
async function openMemo(id, quiet) {
  const m = await api("/api/memos/" + id); const same = M.cur && M.cur.id === id; M.cur = m;
  $$(".memo").forEach(x => x.classList.toggle("on", x.getAttribute("onclick") === `openMemo(${id})`));
  if (quiet && same) { // just refresh the transcript/title while it's processing
    if ($("#m-trans") && document.activeElement !== $("#m-trans")) $("#m-trans").value = m.transcript;
    if ($("#m-title") && document.activeElement !== $("#m-title")) $("#m-title").value = m.title;
    $("#m-status").innerHTML = memoStatus(m); return;
  }
  if (M.audio) { M.audio.pause(); M.audio = null; }
  $("#medit").innerHTML = `<input id="m-title" class="bigin" value="${esc(m.title)}" placeholder="Name this memo" onchange="memoSave({title:this.value})">
    <div class="row small muted" style="gap:10px;margin-top:4px"><input class="f" type="datetime-local" style="width:auto;padding:4px 8px" value="${m.memo_date.slice(0, 16)}" onchange="memoSave({memo_date:this.value+':00'})">
      <span>${mmss(m.duration)} · ${(m.size / 1048576).toFixed(1)} MB · ${m.source === "imported" ? "📱 " + esc(m.original) : "recorded in Daybook"}</span>
      <span id="m-status">${memoStatus(m)}</span></div>
    ${m.kind === "video" ? `<video class="mvid" src="${memoURL(m)}" controls preload="metadata"></video><div class="row small muted" style="margin:-4px 0 10px">${m.source === "obs" ? "Recorded with OBS · " + esc(m.path) : ""}</div>` : `<div class="player"><button class="pp" id="m-pp" onclick="memoPlay()">${ic("play", "i")}</button>
      <div style="flex:1;min-width:0"><canvas class="wave" id="m-wave"></canvas><div class="ptimes"><span id="m-cur">0:00</span><span id="m-dur">${mmss(m.duration)}</span></div></div>
      <div class="col" style="display:flex;flex-direction:column;gap:4px"><button class="btn sm" onclick="memoSkip(-15)">−15s</button><button class="btn sm" onclick="memoSkip(15)">+15s</button></div>
      <select class="f" style="width:auto" onchange="M.audio&&(M.audio.playbackRate=+this.value)"><option value="1">1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></div>
      <div class="row" style="margin:4px 0 8px;opacity:0.85"><audio id="m-native-audio" src="${memoURL(m)}" controls preload="auto" style="width:100%;height:32px"></audio></div>`}
    <label class="small muted">Labels</label>${labelPicker("m-lbl", m.labels)}
    <div class="row" style="margin:14px 0 6px"><b>Transcript</b><div class="sp"></div>
      <button class="btn sm ghost" id="m-speak-btn" onclick="memoSpeakTranscript()">${ic("mic")}<span id="m-speak-txt">Read aloud</span></button>
      <button class="btn sm ghost" onclick="navigator.clipboard.writeText($('#m-trans').value);toast('Copied')">${ic("copy")}Copy</button></div>
    <textarea class="f" id="m-trans" placeholder="${m.status === "done" ? "No speech found" : "Transcribing on this PC…"}" onchange="memoSave({transcript:this.value})">${esc(m.transcript)}</textarea>
    <label class="small muted" style="display:block;margin-top:10px">My notes</label>
    <div class="inmic"><textarea class="f" id="m-notes" style="min-height:80px" placeholder="Anything to add…" onchange="memoSave({notes:this.value})">${esc(m.notes)}</textarea></div>
    <div class="row" style="margin-top:12px">
      <button class="btn pri" onclick="memoToNote()">${ic("note")}${m.note_id ? "Save again as note" : "Save as note"}</button>
      <button class="btn" onclick="discordSend('memo',${m.id})">${ic("send")}Discord</button>
      <button class="btn" onclick="shareMemoLocalSend(${m.id})">${ic("send")}LocalSend</button>
      <button class="btn" onclick="memoSave({starred:${m.starred ? 0 : 1}}).then(()=>openMemo(${m.id}))">${m.starred ? "★ Starred" : "☆ Star"}</button>
      <button class="btn" onclick="api('/api/memos/${m.id}/retranscribe',{method:'POST'}).then(()=>{toast('Transcribing again…');renderMemos();openMemo(${m.id})})">${ic("rep")}Re-transcribe</button>
      <a class="btn ghost" href="${memoURL(m)}" download="${esc((m.title || "memo").replace(/[\\/:*?"<>|]/g, ""))}${m.file.slice(m.file.lastIndexOf("."))}">${ic("down")}Download</a>
      <div class="sp"></div><button class="btn ghost danger" onclick="memoDel(this)">${ic("trash")}Delete</button></div>`;
  $("#m-lbl").addEventListener("click", () => setTimeout(() => memoSave({labels: pickedLabels("m-lbl")}), 0));
  $("#m-lbl input").addEventListener("keydown", e => e.key === "Enter" && setTimeout(() => memoSave({labels: pickedLabels("m-lbl")}), 0));
  micFor($("#m-notes"), $("#m-notes").parentElement, "iconbtn inmicbtn");
  if (m.kind === "video") { M.audio = null; return; }
  const aEl = $("#m-native-audio");
  M.audio = aEl || new Audio(memoURL(m));
  M.audio.preload = "auto";
  const onMeta = () => {
    const cur = (M.audio && isFinite(M.audio.currentTime)) ? M.audio.currentTime : 0;
    const dur = memoDuration();
    if ($("#m-cur")) $("#m-cur").textContent = mmss(cur);
    if ($("#m-dur") && dur > 0) $("#m-dur").textContent = mmss(dur);
    drawWave();
  };
  M.audio.onloadedmetadata = onMeta;
  M.audio.ontimeupdate = () => {
    const cur = (M.audio && isFinite(M.audio.currentTime)) ? M.audio.currentTime : 0;
    if ($("#m-cur")) $("#m-cur").textContent = mmss(cur);
    drawWave();
  };
  M.audio.onended = () => {
    if ($("#m-pp")) $("#m-pp").innerHTML = ic("play", "i");
    drawWave();
  };
  M.audio.onpause = () => {
    if ($("#m-pp")) $("#m-pp").innerHTML = ic("play", "i");
  };
  M.audio.onplay = () => {
    if ($("#m-pp")) $("#m-pp").innerHTML = ic("pause", "i");
  };
  $("#m-wave").onclick = e => {
    const r = e.target.getBoundingClientRect(), dur = memoDuration();
    if (dur > 0 && M.audio) {
      const frac = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
      M.audio.currentTime = frac * dur;
      drawWave();
    }
  };
  M.peaks = null; drawWave(); loadPeaks(m);
}
function memoDuration() {
  if (M.audio && isFinite(M.audio.duration) && M.audio.duration > 0) return M.audio.duration;
  if (M.cur && isFinite(M.cur.duration) && M.cur.duration > 0) return M.cur.duration;
  return 0;
}
const memoStatus = m => m.status === "done" ? "✓ transcribed" : m.status === "error" ? `<span style="color:var(--bad)">couldn't transcribe</span>` : `<span class="badge ai">Transcribing…</span>`;
async function loadPeaks(m) {
  try {
    const buf = await (await fetch(memoURL(m))).arrayBuffer();
    const ac = new OfflineAudioContext(1, 1, 44100), ab = await ac.decodeAudioData(buf), ch = ab.getChannelData(0), n = 160, step = Math.floor(ch.length / n) || 1;
    const peaks = []; for (let i = 0; i < n; i++) { let p = 0; for (let j = i * step; j < (i + 1) * step && j < ch.length; j += 16) p = Math.max(p, Math.abs(ch[j])); peaks.push(p); }
    const mx = Math.max(...peaks, .01); if (M.cur && M.cur.id === m.id) { M.peaks = peaks.map(p => p / mx); drawWave(); }
  } catch (e) { M.peaks = null; }
}
function drawWave() {
  const cv = $("#m-wave"); if (!cv) return;
  const w = cv.width = cv.clientWidth * devicePixelRatio, h = cv.height = cv.clientHeight * devicePixelRatio, c = cv.getContext("2d");
  const peaks = M.peaks || Array.from({length: 160}, (_, i) => .15 + .1 * Math.sin(i / 3));
  const dur = memoDuration();
  const cur = (M.audio && isFinite(M.audio.currentTime)) ? M.audio.currentTime : 0;
  const prog = (dur > 0) ? Math.max(0, Math.min(1, cur / dur)) : 0;
  const cs = getComputedStyle(document.body);
  const bw = w / peaks.length;
  peaks.forEach((p, i) => { c.fillStyle = i / peaks.length < prog ? cs.getPropertyValue("--a2") : "rgba(160,170,200,.35)";
    const bh = Math.max(2, p * h * .92); c.fillRect(i * bw + bw * .15, (h - bh) / 2, bw * .7, bh); });
}
function memoPlay() {
  if (!M.audio) return;
  if (M.audio.ended) M.audio.currentTime = 0;
  if (M.audio.paused) {
    const p = M.audio.play();
    if (p && p.catch) {
      p.catch(e => {
        console.warn("Audio play error:", e);
        toast("Playback error — try playing again or click the player below");
      });
    }
  } else {
    M.audio.pause();
  }
}
function memoSkip(s) {
  if (M.audio) {
    const dur = memoDuration();
    const cur = (isFinite(M.audio.currentTime)) ? M.audio.currentTime : 0;
    const tgt = Math.max(0, cur + s);
    M.audio.currentTime = dur > 0 ? Math.min(dur, tgt) : tgt;
    drawWave();
  }
}
function memoSpeakTranscript() {
  if (window.speechSynthesis && window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    if ($("#m-speak-txt")) $("#m-speak-txt").textContent = "Read aloud";
    return;
  }
  const text = ($("#m-trans") ? $("#m-trans").value : "").trim();
  if (!text) return toast("No transcript text to read");
  if (!('speechSynthesis' in window)) return toast("Speech synthesis not supported in this browser");
  const u = new SpeechSynthesisUtterance(text);
  u.onend = u.onerror = () => { if ($("#m-speak-txt")) $("#m-speak-txt").textContent = "Read aloud"; };
  window.speechSynthesis.speak(u);
  if ($("#m-speak-txt")) $("#m-speak-txt").textContent = "Stop reading";
}
async function memoSave(f) { if (!M.cur) return; M.cur = await api("/api/memos/" + M.cur.id, {method: "PATCH", body: f}); renderMemos(); }
async function memoToNote() { await memoSave({transcript: $("#m-trans").value, notes: $("#m-notes").value}); const j = await api(`/api/memos/${M.cur.id}/to-note`, {method: "POST"}); toast("Saved to Notes ✓"); openNote(j.note_id); }
function memoDel(btn) {
  if (!btn.dataset.sure) { btn.dataset.sure = 1; btn.innerHTML = ic("trash") + "Click again to delete"; return; }
  api("/api/memos/" + M.cur.id, {method: "DELETE"}).then(() => { if (M.audio) M.audio.pause(); M.cur = null; $("#medit").innerHTML = `<div class="empty"><b>Deleted</b></div>`; renderMemos(); });
}

async function shareMemoLocalSend(id) {
  toast("Preparing LocalSend share…");
  try {
    const res = await api("/api/localsend/share", {method: "POST", body: {memo_id: id}});
    if (res.launched_localsend) {
      toast("✓ LocalSend opened with your recording! Ready to send to phone or PC.");
    } else {
      modal(`<h2>${ic("send", "i")}Share via LocalSend / Wi-Fi<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
        <p class="muted">Share this voice memo wirelessly to your phone or any device on your local Wi-Fi.</p>
        <div class="frm">
          <label>Option 1: Direct LAN Download Link</label>
          <div class="row" style="flex-wrap:nowrap">
            <input class="f" id="ls-link" value="${esc(res.lan_download_url || '')}" readonly>
            <button class="btn" onclick="navigator.clipboard.writeText($('#ls-link').value);toast('Link copied!')">${ic("copy")}Copy</button>
          </div>
          <div class="muted small" style="margin-top:4px">Open this link in your phone's browser while connected to the same Wi-Fi.</div>
          <label style="margin-top:14px">Option 2: Open LocalSend App</label>
          <div class="row" style="gap:8px">
            <button class="btn pri" onclick="api('/api/localsend/launch',{method:'POST'}).then(r=>toast(r.error||'LocalSend launched')).catch(e=>toast(e.message))">Launch LocalSend</button>
            <button class="btn" onclick="go('apps');awSwitch('localsend');closeModal()">Open In-App LocalSend</button>
            <a href="https://localsend.org" target="_blank" class="btn ghost">Download LocalSend</a>
          </div>
        </div>
        <div class="row" style="margin-top:16px"><button class="btn" onclick="closeModal()">Close</button></div>`);
    }
  } catch (e) {
    toast("Share error: " + e.message);
  }
}
