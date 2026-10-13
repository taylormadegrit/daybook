// ================= VIDEO NOTES: built-in camera / screen recorder + OBS remote =================
const VR = {src: "camera", stream: null, rec: null, chunks: [], t0: 0, tick: 0, obsPoll: 0, actx: null};
function videoRecModal(src) {
  VR.src = src || store.get("daybook-vsrc", "camera");
  modal(`<h2>${ic("rec", "i")}Record a video note<button class="iconbtn" onclick="vrClose()">${ic("x")}</button></h2>
    <div class="seg" style="margin-bottom:14px">${[["camera", "Camera"], ["screen", "Screen"], ["obs", "OBS Studio"]].map(([k, l]) => `<button class="${VR.src === k ? "on" : ""}" onclick="vrSwitch('${k}')">${l}</button>`).join("")}</div>
    <div id="vr-body"></div>`, true);
  vrBody();
}
function vrSwitch(k) { if (VR.rec) return toast("Stop the recording first"); vrStop(true); VR.src = k; store.set("daybook-vsrc", k); videoRecModal(k); }
function vrClose() { if (VR.rec && VR.rec.state === "recording") return toast("Stop the recording first (or it keeps going)"); vrStop(true); clearInterval(VR.obsPoll); closeModal(); }
async function vrBody() {
  const b = $("#vr-body"); if (!b) return;
  if (VR.src === "obs") return obsPanel();
  let cams = [];
  try { cams = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === "videoinput"); } catch (e) {}
  b.innerHTML = `<div class="vr-prev"><video id="vr-v" autoplay muted playsinline></video><div class="vr-ph" id="vr-ph">${VR.src === "camera" ? "Camera preview" : "Pick a screen or window to record"}</div>
      <div class="vr-live" id="vr-live" style="display:none"><span class="dot"></span><span id="vr-t">0:00</span></div></div>
    <div class="row" style="margin-top:12px;flex-wrap:nowrap">
      ${VR.src === "camera" ? `<select class="f" id="vr-cam" onchange="store.set('daybook-cam',this.value);vrPreview()">${cams.map(c => `<option value="${c.deviceId}" ${c.deviceId === store.get("daybook-cam", "") ? "selected" : ""}>${esc(c.label || "Camera")}</option>`).join("") || `<option value="">Default camera</option>`}</select>`
        : `<button class="btn" onclick="vrPreview()">${ic("grid")}Choose screen / window</button>`}
      <div class="sp"></div><button class="rbtn sm go" id="vr-btn" onclick="vrToggle()">Rec</button></div>
    <div class="muted small" style="margin-top:8px">Microphone: your choice in Settings → Voice. Saved to Voice memos as a video note and transcribed on this PC.</div>`;
  if (VR.src === "camera") vrPreview();
}
async function vrPreview() {
  vrStop(true);
  try {
    const mic = await micStream().catch(() => null);
    let vid;
    if (VR.src === "camera") { const id = ($("#vr-cam") || {}).value || store.get("daybook-cam", ""); vid = await navigator.mediaDevices.getUserMedia({video: id ? {deviceId: {exact: id}, width: 1920, height: 1080} : {width: 1920, height: 1080}}); }
    else vid = await navigator.mediaDevices.getDisplayMedia({video: {frameRate: 30}, audio: true});
    const tracks = [...vid.getVideoTracks()];
    const audioIns = [mic, VR.src === "screen" ? vid : null].filter(s => s && s.getAudioTracks().length);
    if (audioIns.length > 1) { // mix computer sound + mic into one track
      VR.actx = new AudioContext(); const dest = VR.actx.createMediaStreamDestination();
      audioIns.forEach(s => VR.actx.createMediaStreamSource(s).connect(dest)); tracks.push(...dest.stream.getAudioTracks());
    } else if (audioIns.length) tracks.push(...audioIns[0].getAudioTracks());
    VR.parts = [vid, mic].filter(Boolean);
    VR.stream = new MediaStream(tracks);
    vid.getVideoTracks()[0].onended = () => { if (VR.rec) vrToggle(); };
    const v = $("#vr-v"); if (v) { v.srcObject = vid; $("#vr-ph").style.display = "none"; }
    if (VR.src === "camera" && !$("#vr-cam").options[0].textContent.trim().length) vrBody();
  } catch (e) { if (e.name !== "NotAllowedError" || VR.src === "camera") micError(e); }
}
async function vrToggle() {
  if (VR.rec) {
    VR.rec.stop(); return;
  }
  if (!VR.stream) { await vrPreview(); if (!VR.stream) return; }
  const mime = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"].find(m => MediaRecorder.isTypeSupported(m));
  VR.rec = new MediaRecorder(VR.stream, {mimeType: mime, videoBitsPerSecond: 5_000_000}); VR.chunks = [];
  VR.rec.ondataavailable = e => e.data.size && VR.chunks.push(e.data);
  VR.rec.onstop = () => { clearInterval(VR.tick); const blob = new Blob(VR.chunks, {type: "video/webm"}), secs = (Date.now() - VR.t0) / 1000; VR.rec = null; vrStop(true); vrSave(blob, secs); };
  VR.rec.start(1000); VR.t0 = Date.now();
  $("#vr-btn").textContent = "Stop"; $("#vr-btn").className = "rbtn sm stop"; $("#vr-live").style.display = "flex";
  VR.tick = setInterval(() => { const t = $("#vr-t"); if (t) t.textContent = mmss((Date.now() - VR.t0) / 1000); }, 500);
}
function vrStop(keepModal) {
  (VR.parts || []).forEach(s => s.getTracks().forEach(t => t.stop())); VR.parts = []; VR.stream = null;
  if (VR.actx) { VR.actx.close().catch(() => {}); VR.actx = null; }
}
function vrSave(blob, secs) {
  if (blob.size < 5000) return toast("Too short — nothing saved");
  M.recBlob = blob; M.recKind = "video";
  modal(`<h2>${ic("rec", "i")}Save video note<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <video src="${URL.createObjectURL(blob)}" controls style="width:100%;border-radius:12px;max-height:40vh;background:#000"></video>
    <div class="frm" style="margin-top:10px"><label>Name</label><input class="f" id="ms-title" placeholder="Leave blank — the local AI names it from what you said">
    <label>Labels</label>${labelPicker("ms-lbl", [])}
    <label>Date</label><input class="f" type="datetime-local" id="ms-date" value="${localISO(new Date())}"></div>
    <div class="muted small" style="margin-top:8px">${mmss(secs)} · ${(blob.size / 1048576).toFixed(1)} MB</div>
    <div class="row" style="margin-top:14px"><button class="btn pri" onclick="memoUpload()">${ic("check")}Save</button><button class="btn ghost danger" onclick="M.recBlob=null;closeModal();toast('Discarded')">Discard</button></div>`, true);
}

// ---------- OBS ----------
async function obsPanel() {
  const b = $("#vr-body"); if (!b) return;
  let s; try { s = await api("/api/obs"); } catch (e) { b.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  clearInterval(VR.obsPoll);
  if (!s.installed) { b.innerHTML = `<div class="empty"><b>OBS Studio isn't installed</b>Use Camera or Screen instead — no setup needed.</div>`; return; }
  if (!s.enabled) {
    b.innerHTML = `<div class="obs-card"><b>Connect OBS to Daybook (one time)</b><p class="muted small">Daybook controls OBS through OBS's own local remote-control connection (WebSocket). It's off right now. Connecting turns it on with password protection; your scenes and settings aren't touched. ${s.running ? "<br><b style='color:var(--warn)'>Close OBS first</b> — it rewrites its settings when it exits." : ""}</p>
      <button class="btn pri" onclick="obsAct('enable')">${ic("check")}Connect OBS</button></div>`; return;
  }
  if (!s.running) { b.innerHTML = `<div class="obs-card"><b>OBS is connected but not open</b><p class="muted small">Open it, set up your scene (camera, screen, mic) like you normally would, then record from here.</p><button class="btn pri" onclick="obsAct('launch')">${ic("play")}Open OBS</button></div>`; VR.obsPoll = setInterval(obsPanel, 3000); return; }
  if (!s.connected) { b.innerHTML = `<div class="obs-card"><b>Waiting for OBS…</b><p class="muted small">${esc(s.error || "OBS is starting.")} If this stays, restart OBS once so it picks up the connection.</p></div>`; VR.obsPoll = setInterval(obsPanel, 3000); return; }
  b.innerHTML = `<div class="obs-card"><div class="row"><span class="badge" style="color:var(--ok)">● OBS connected</span><span class="small muted">Records your current OBS scene · saves to ${esc(s.record_dir)}</span></div>
    <div class="bigtime sm" style="margin:16px 0">${s.recording ? (s.paused ? "⏸ " : "🔴 ") + s.timecode : "00:00:00"}</div>
    ${s.recording ? "" : `<div class="frm"><label>Name</label><input class="f" id="obs-title" placeholder="optional — the AI names it from what you said"><label>Labels</label>${labelPicker("obs-lbl", [])}</div>`}
    <div class="cbtns" style="margin-top:14px">${s.recording ? `<button class="rbtn sm" onclick="obsAct('${s.paused ? "resume" : "pause"}')">${s.paused ? "Resume" : "Pause"}</button><button class="rbtn sm stop" onclick="obsAct('stop')">Stop</button>`
      : `<span></span><button class="rbtn sm go" onclick="obsAct('start')">Rec</button>`}</div></div>`;
  if (s.recording) VR.obsPoll = setInterval(obsPanel, 1000);
}
async function obsAct(a) {
  const body = a === "start" ? {title: ($("#obs-title") || {}).value || "", labels: pickedLabels("obs-lbl")} : {};
  try {
    const j = await api("/api/obs/" + a, {method: "POST", body});
    if (a === "enable") toast("OBS connected ✓ — open OBS and you're ready");
    if (a === "launch") toast("Opening OBS…");
    if (a === "stop") { toast(j.memo ? "Saved to Voice memos — transcribing…" : "Recording saved by OBS"); if (j.memo) { closeModal(); clearInterval(VR.obsPoll); go("memos"); M.kind = "video"; setTimeout(() => { renderMemos(); openMemo(j.memo); }, 300); return; } }
  } catch (e) { toast(e.message); }
  setTimeout(obsPanel, a === "launch" ? 4000 : 400);
}
