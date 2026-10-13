// ================= AI STUDIO: images + your voice, with the models on this PC =================
const ST = {tab: "image", data: null, busy: false, style: "none", size: "square", count: 2, engine: "local"};
const SIZES = {square: [512, 512, "Square"], portrait: [512, 896, "Portrait 9:16"], landscape: [896, 512, "Landscape 16:9"]};
const STYLE_LABEL = {none: "No style", photo: "Photo", cinematic: "Cinematic", anime: "Anime", thumbnail: "Thumbnail", logo: "Logo", "3d": "3D", art: "Concept art", spiritual: "Spiritual"};
async function renderStudio(sub) {
  if (sub) ST.tab = sub;
  ST.data = await api("/api/studio");
  const d = ST.data;
  $("#studio").innerHTML = `<div class="ctabs" style="margin:0 0 16px">${[["image", "spark", "Images"], ["voice", "mic", "My voice"], ["chat", "chat", "Chat"], ["models", "chip", "Models"]].map(([k, i, l]) =>
      `<button class="${ST.tab === k ? "on" : ""}" onclick="${k === "chat" || k === "models" ? `go('${k}')` : `ST.tab='${k}';history.replaceState(null,'','#studio/${k}');renderStudio()`}">${ic(i)}${l}</button>`).join("")}</div>
    <div class="grid2 studio-grid"><div class="card">${ST.tab === "image" ? studioImage(d) : studioVoice(d)}</div>
    <div class="card"><h3>${ic("grid")}Creations<span class="small muted" style="margin-left:auto">${esc(d.out)}</span></h3><div class="cre-grid" id="cre">${creGrid(d.creations)}</div></div></div>`;
  paintIcons($("#studio"));
}
function studioImage(d) {
  const ready = d.image_model;
  return `<h3>${ic("spark")}Create an image</h3>
    <textarea class="f" id="st-p" rows="3" placeholder="Describe it… e.g. ancient Egyptian temple at sunset, glowing hieroglyphs" onkeydown="if(event.key==='Enter'&&(event.ctrlKey||event.metaKey))stGen()">${esc(store.get("daybook-st-p", ""))}</textarea>
    <div class="grouph">Style</div><div class="presets">${d.styles.map(s => `<button class="chipb ${ST.style === s ? "on" : ""}" onclick="ST.style='${s}';$$('.presets .chipb').forEach(b=>b.classList.toggle('on',b.textContent==='${STYLE_LABEL[s]}'))">${STYLE_LABEL[s] || s}</button>`).join("")}</div>
    <div class="row" style="margin-top:12px;gap:10px">
      <div class="seg sm">${Object.entries(SIZES).map(([k, v]) => `<button class="${ST.size === k ? "on" : ""}" onclick="ST.size='${k}';this.parentNode.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b===this))">${v[2]}</button>`).join("")}</div>
      <div class="seg sm">${[1, 2, 4].map(n => `<button class="${ST.count === n ? "on" : ""}" onclick="ST.count=${n};this.parentNode.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b===this))">${n}×</button>`).join("")}</div>
      ${d.gemini ? `<select class="f" style="width:auto" onchange="ST.engine=this.value"><option value="local">On this PC (free)</option><option value="gemini" ${ST.engine === "gemini" ? "selected" : ""}>Gemini (cloud, needs billing)</option></select>` : ""}</div>
    <div class="row" style="margin-top:14px"><button class="btn pri lg" id="st-go" onclick="stGen()" ${ready || ST.engine === "gemini" ? "" : "disabled"}>${ic("spark")}Create</button><span class="small muted" id="st-msg">${ready ? "SDXL-Turbo on your GPU · Ctrl+Enter" : "The image model is still downloading…"}</span></div>`;
}
function studioVoice(d) {
  return `<h3>${ic("mic")}Say it in a voice</h3>
    <div class="muted small" style="margin-bottom:10px">Uses the XTTS voice-cloning model from your Ori Brazil project. Pick a short, clean sample (6–30 s) — your TBG voice samples, or any voice memo.</div>
    <div class="frm"><label>Voice</label><select class="f" id="st-v">${d.voices.map(v => `<option value="${esc(v.path)}" ${v.path === store.get("daybook-st-v", "") ? "selected" : ""}>${esc(v.name)} · ${esc(v.src)}</option>`).join("") || `<option value="">No samples — record a voice memo first</option>`}</select>
    <label>Language</label><select class="f" id="st-lang">${[["en", "English"], ["es", "Spanish"], ["pt", "Portuguese"], ["fr", "French"], ["de", "German"], ["it", "Italian"], ["ja", "Japanese"], ["ar", "Arabic"], ["hi", "Hindi"]].map(([k, l]) => `<option value="${k}">${l}</option>`).join("")}</select></div>
    <textarea class="f" id="st-t" rows="5" style="margin-top:10px" placeholder="What should it say?"></textarea>
    <div class="row" style="margin-top:12px"><button class="btn pri lg" id="st-go" onclick="stSpeak()" ${d.tts_model ? "" : "disabled"}>${ic("mic")}Speak</button><span class="small muted" id="st-msg">${d.tts_model ? "First run loads the model (~30 s)" : "XTTS model not found in D:\\coqui-models"}</span></div>`;
}
function creGrid(items) {
  return items.map(c => c.kind === "image"
    ? `<div class="cre"><img src="/creations/${encodeURIComponent(c.name)}" loading="lazy" title="${esc(c.prompt)}" onclick="window.open(this.src,'_blank')">
        <div class="cra"><button class="iconbtn" title="Use this prompt" onclick="ST.tab='image';store.set('daybook-st-p',${JSON.stringify(c.prompt).replace(/"/g, "&quot;")});renderStudio()">${ic("rep")}</button>
        <button class="iconbtn" title="Send to Discord" onclick="discordSend('creation','${esc(c.name)}')">${ic("send")}</button>
        <button class="iconbtn" title="Delete" onclick="stDel(this,'${esc(c.name)}')">${ic("trash")}</button></div></div>`
    : `<div class="cre au"><audio src="/creations/${encodeURIComponent(c.name)}" controls preload="none"></audio><div class="cra"><span class="small muted">${dayName(c.created)} ${tm(c.created)}</span>
        <button class="iconbtn" title="Send to Discord" onclick="discordSend('creation','${esc(c.name)}')">${ic("send")}</button><button class="iconbtn" title="Delete" onclick="stDel(this,'${esc(c.name)}')">${ic("trash")}</button></div></div>`).join("")
    || `<div class="empty" style="grid-column:1/-1"><b>Nothing yet</b>Your images and voice clips appear here.</div>`;
}
function stBusy(on, msg) { ST.busy = on; const b = $("#st-go"); if (b) b.disabled = on; if ($("#st-msg")) $("#st-msg").textContent = msg; }
async function stGen() {
  const p = $("#st-p").value.trim(); if (!p || ST.busy) return; store.set("daybook-st-p", p);
  const [w, h] = SIZES[ST.size];
  stBusy(true, ST.data.worker && ST.data.worker.image ? "Creating…" : "Waking the GPU and loading the model (first time ~30–60 s)…");
  try {
    const j = await api("/api/studio/image", {method: "POST", body: {prompt: p, style: ST.style, width: w, height: h, count: ST.count, engine: ST.engine}});
    stBusy(false, j.seconds ? `Done in ${j.seconds}s on ${j.device}` : "Done");
    ST.data = await api("/api/studio"); $("#cre").innerHTML = creGrid(ST.data.creations); paintIcons($("#cre"));
  } catch (e) { stBusy(false, e.message); toast(e.message); }
}
async function stSpeak() {
  const t = $("#st-t").value.trim(), v = $("#st-v").value; if (!t || !v || ST.busy) return; store.set("daybook-st-v", v);
  stBusy(true, "Speaking… (first time loads the voice model)");
  try {
    const j = await api("/api/studio/tts", {method: "POST", body: {text: t, voice: v, language: $("#st-lang").value}});
    stBusy(false, `Done in ${j.seconds}s`); ST.data = await api("/api/studio"); $("#cre").innerHTML = creGrid(ST.data.creations); paintIcons($("#cre"));
    const a = $("#cre audio"); a && a.play();
  } catch (e) { stBusy(false, e.message); toast(e.message); }
}
async function stDel(btn, name) { if (!btn.dataset.sure) { btn.dataset.sure = 1; btn.style.color = "var(--bad)"; toast("Click again to delete"); return; } await api("/api/studio/creations/" + encodeURIComponent(name), {method: "DELETE"}); btn.closest(".cre").remove(); }
// home widget: quick prompt + latest creations
async function studioWidget() {
  const el = $("#w-studio"); if (!el) return;
  const d = ST.data || (ST.data = await api("/api/studio"));
  el.innerHTML = `<div class="row" style="flex-wrap:nowrap"><input class="f" id="w-st" placeholder="Describe an image… Enter to create" onkeydown="if(event.key==='Enter'&&this.value.trim()){store.set('daybook-st-p',this.value.trim());go('studio','image');setTimeout(stGen,600)}">
    <button class="btn" onclick="go('studio')">Open</button></div>
    <div class="cre-mini">${d.creations.filter(c => c.kind === "image").slice(0, 6).map(c => `<img src="/creations/${encodeURIComponent(c.name)}" loading="lazy" title="${esc(c.prompt)}" onclick="go('studio')">`).join("")}</div>`;
}
