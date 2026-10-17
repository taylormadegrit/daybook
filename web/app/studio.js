// ================= AI STUDIO: images, videos (Higgsfield) + your voice =================
const ST = {
  tab: "image", data: null, busy: false, style: "none", size: "square", count: 2,
  engine: "local", hfImageModel: "gpt_image_2_5", hfVideoModel: "seedance_2_5",
  videoAr: "16:9", videoDur: 5, startImg: "", showHfPrompts: true
};
const SIZES = {square: [512, 512, "Square 1:1", "1:1"], portrait: [512, 896, "Portrait 9:16", "9:16"], landscape: [896, 512, "Landscape 16:9", "16:9"]};
const STYLE_LABEL = {none: "No style", photo: "Photo", cinematic: "Cinematic", anime: "Anime", thumbnail: "Thumbnail", logo: "Logo", "3d": "3D", art: "Concept art", spiritual: "Spiritual"};

const HIGGSFIELD_SETUP_PROMPT = `Set up Higgsfield for me so I can generate images and videos from here.
1. Install the CLI: run \`npm i -g @higgsfield/cli\`.
2. Authenticate: run \`higgsfield auth login\` and complete the sign-in in the browser it opens.
3. Install the companion skills: run \`npx skills add higgsfield-ai/skills\`.
Once that’s done, let me know when it’s ready.`;

const HIGGSFIELD_CLI_COMMANDS = [
  {label: "1. Install Higgsfield CLI", cmd: "npm i -g @higgsfield/cli"},
  {label: "2. Sign in (opens browser)", cmd: "higgsfield auth login"},
  {label: "3. Install 8 Companion Skills", cmd: "npx -y skills add higgsfield-ai/skills -g --all --copy"},
  {label: "Select workspace & check credits", cmd: "higgsfield account status"},
  {label: "List workspaces", cmd: "higgsfield workspace list"},
  {label: "List all image & video models", cmd: "higgsfield model list"},
  {label: "Generate Image (CLI)", cmd: 'higgsfield generate create gpt_image_2_5 --prompt "cinematic neon cyberpunk street in rain" --aspect_ratio 16:9 --wait'},
  {label: "Generate Video (CLI)", cmd: 'higgsfield generate create seedance_2_5 --prompt "drone shot flying over misty mountains at sunrise" --aspect_ratio 16:9 --duration 5 --wait'},
];

const HIGGSFIELD_IMAGE_PRESETS = [
  ["Cinematic Hero", "Cinematic wide shot of an ancient futuristic sanctuary at golden hour, volumetric light rays, ultra-detailed 8k"],
  ["Product Studio", "Luxury matte-black wireless headphones floating on a wet obsidian surface with soft rim lighting, commercial studio photography"],
  ["YouTube Thumbnail", "High-contrast expressive tech review thumbnail, glowing neon rim light, dramatic depth of field, ultra-sharp"],
  ["Anime Keyframe", "Makoto Shinkai style twilight cityscape overlooking a glowing harbor, vibrant clouds, meteor shower"],
];

const HIGGSFIELD_VIDEO_PRESETS = [
  ["Cinematic Drone", "Sweeping FPV drone shot flying through a misty canyon at sunrise, golden sunbeams breaking through clouds, 4k cinematic motion"],
  ["Camera Push-In", "Slow cinematic dolly push-in as neon rain reflects off the street, subtle subject movement and atmospheric fog"],
  ["Product Reveal", "Smooth orbital camera rotation around the product with dramatic rim lighting and floating light particles"],
  ["Action Tracking", "Dynamic low-angle tracking shot following a futuristic sports car drifting around a rain-slicked corner at night"],
];

async function renderStudio(sub) {
  if (sub) ST.tab = sub;
  ST.data = await api("/api/studio");
  const d = ST.data;
  if (!d.image_model && d.higgsfield && d.higgsfield.installed && ST.engine === "local") {
    ST.engine = "higgsfield";
  }
  const pane = ST.tab === "image" ? studioImage(d) : (ST.tab === "video" ? studioVideo(d) : studioVoice(d));
  $("#studio").innerHTML = `<div class="ctabs" style="margin:0 0 12px">${[
      ["image", "spark", "Images"],
      ["video", "rec", "Videos (Higgsfield)"],
      ["voice", "mic", "My voice"],
      ["chat", "chat", "Chat"],
      ["models", "chip", "Models"]
    ].map(([k, i, l]) =>
      `<button class="${ST.tab === k ? "on" : ""}" onclick="${k === "chat" || k === "models" ? `go('${k}')` : `ST.tab='${k}';history.replaceState(null,'','#studio/${k}');renderStudio()`}">${ic(i)}${l}</button>`).join("")}</div>
    ${studioHiggsfieldBar(d.higgsfield)}
    <div class="grid2 studio-grid"><div class="card">${pane}</div>
    <div class="card"><h3>${ic("grid")}Creations<span class="small muted" style="margin-left:auto">${esc(d.out)}</span></h3><div class="cre-grid" id="cre">${creGrid(d.creations)}</div></div></div>`;
  paintIcons($("#studio"));
}

function studioHiggsfieldBar(hf) {
  hf = hf || {};
  const inst = !!hf.installed;
  const signed = !!hf.signed_in;
  const skills = !!hf.skills_installed;
  const mcp = !!hf.registered;
  const chip = (ok, txt) => `<span class="badge" style="color:${ok ? "var(--ok)" : "var(--muted)"};border-color:${ok ? "rgba(62,224,160,.4)" : "var(--line2)"}">${ok ? "✓ " : "○ "}${txt}</span>`;
  const creditsLabel = signed
    ? `Signed In${hf.plan ? " · " + esc(String(hf.plan).toUpperCase()) : ""}${hf.credits != null ? " · " + esc(String(hf.credits)) + " credits" : ""}`
    : "Sign-in Needed";
  return `<div class="card" style="margin-bottom:14px;padding:12px 16px;background:rgba(255,255,255,.025)">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <div style="display:flex;align-items:center;gap:8px;min-width:200px">
        <span style="font-size:18px">🎬</span>
        <div>
          <b style="font-size:13.5px">Higgsfield AI Studio &amp; MCP</b>
          <div class="small muted">GPT Image 2.5 · Nano Banana 2 · Soul 2.0 · Seedance 2.5 · Kling 3.0 · Veo 3.1</div>
        </div>
      </div>
      <div class="row" style="gap:6px;flex-wrap:wrap">
        ${chip(inst, inst && hf.version ? `CLI v${esc(hf.version)}` : "CLI")}
        ${chip(skills, "8 Agent Skills")}
        ${chip(mcp, "MCP Connected")}
        ${chip(signed, creditsLabel)}
      </div>
      <div class="row" style="gap:6px;margin-left:auto;flex-wrap:wrap">
        ${!inst || !skills || !mcp ? `<button class="btn pri sm" onclick="stHiggsfieldSetup(this)">${ic("zap")}⚡ 1-Click Setup Higgsfield</button>` : ""}
        ${inst && !signed ? `<button class="btn pri sm" onclick="stHiggsfieldLogin(this)">${ic("ext")}1-Click Sign In (Browser)</button>` : ""}
        ${inst && signed ? `<button class="btn ghost sm" onclick="stHiggsfieldLogin(this)" title="Re-authenticate Higgsfield CLI">Re-auth</button>` : ""}
        <button class="btn sm ${ST.showHfPrompts ? "pri" : ""}" onclick="ST.showHfPrompts=!ST.showHfPrompts;renderStudio()">${ic("copy")}1-Click Prompts &amp; CLI</button>
        <button class="btn sm" onclick="openHiggsfieldTerm()" title="Open a terminal ready for higgsfield commands">${ic("chip")}Terminal</button>
      </div>
    </div>
    ${ST.showHfPrompts ? `
      <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--line);display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div style="background:rgba(0,0,0,.22);border:1px solid var(--line2);border-radius:10px;padding:12px">
          <div class="row" style="margin-bottom:6px;gap:6px;flex-wrap:wrap">
            <b style="font-size:12.5px">🤖 1-Click Agent Setup Prompt (Claude / Gemini / Chat)</b>
            <div class="sp"></div>
            <button class="btn sm pri" onclick="stPromptToChat(HIGGSFIELD_SETUP_PROMPT, true)">${ic("send")}1-Click Prompt in Chat</button>
            <button class="btn sm" onclick="stCopyText(HIGGSFIELD_SETUP_PROMPT, 'Copied Higgsfield setup prompt!')">${ic("copy")}Copy Prompt</button>
          </div>
          <pre style="margin:0;padding:8px 10px;background:rgba(0,0,0,.3);border-radius:8px;font-size:11.5px;line-height:1.45;white-space:pre-wrap;color:var(--fg)">${esc(HIGGSFIELD_SETUP_PROMPT)}</pre>
          <div class="row" style="margin-top:8px;gap:6px;flex-wrap:wrap">
            <span class="small muted">1-Click Agent Tasks:</span>
            <button class="btn sm ghost" onclick="stPromptToChat('Use Higgsfield (gpt_image_2_5) to generate a 16:9 cinematic image of: ', false)">🖼 Image Prompt → Chat</button>
            <button class="btn sm ghost" onclick="stPromptToChat('Use Higgsfield (seedance_2_5) to generate a 5s 16:9 video of: ', false)">🎬 Video Prompt → Chat</button>
            <button class="btn sm ghost" onclick="stPromptToChat('Use the higgsfield-youtube-thumbnail skill to create a high-CTR YouTube thumbnail for: ', false)">📺 Thumbnail → Chat</button>
            <button class="btn sm ghost" onclick="stPromptToChat('Use the higgsfield-product-photoshoot skill to create studio product shots for: ', false)">🛍 Photoshoot → Chat</button>
          </div>
        </div>
        <div style="background:rgba(0,0,0,.22);border:1px solid var(--line2);border-radius:10px;padding:12px">
          <div class="row" style="margin-bottom:6px;gap:6px">
            <b style="font-size:12.5px">⚡ 1-Click Higgsfield CLI Commands (Terminal)</b>
            <div class="sp"></div>
            <button class="btn sm pri" onclick="stRunInTerm('higgsfield auth login')">${ic("play")}Run Auth Login</button>
          </div>
          <div style="display:flex;flex-direction:column;gap:5px;max-height:165px;overflow-y:auto;padding-right:2px">
            ${HIGGSFIELD_CLI_COMMANDS.map((item, idx) => `
              <div style="display:flex;align-items:center;gap:6px;background:rgba(0,0,0,.28);padding:5px 8px;border-radius:7px;font-size:11.5px">
                <span class="muted" style="min-width:155px;font-weight:600">${esc(item.label)}</span>
                <code style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#f472b6" title="${esc(item.cmd)}">${esc(item.cmd)}</code>
                <button class="btn sm pri" style="padding:2px 7px;font-size:11px" onclick="stRunCliIdx(${idx})" title="Run in Daybook Terminal">▶ Run</button>
                <button class="btn sm ghost" style="padding:2px 7px;font-size:11px" onclick="stCopyCliIdx(${idx})" title="Copy command">Copy</button>
              </div>
            `).join("")}
          </div>
        </div>
      </div>
    ` : ""}
  </div>`;
}

function stCopyText(txt, msg) {
  navigator.clipboard.writeText(txt);
  toast(msg || "Copied to clipboard!");
}

function stCopyCliIdx(idx) {
  const item = HIGGSFIELD_CLI_COMMANDS[idx];
  if (!item) return;
  stCopyText(item.cmd, `Copied: ${item.cmd}`);
}

function stRunCliIdx(idx) {
  const item = HIGGSFIELD_CLI_COMMANDS[idx];
  if (!item) return;
  stRunInTerm(item.cmd);
}

function stRunInTerm(cmd) {
  if (!window.desktop || !desktop.term) {
    stCopyText(cmd, "Copied CLI command (open Terminal in Desktop app to run)");
    return;
  }
  go("chat");
  setTimeout(() => {
    if (typeof termToggle === "function") termToggle(true);
    if (typeof termNew === "function") termNew("pwsh", {run: cmd});
  }, 250);
}

function stPromptToChat(text, autoSend) {
  go("chat");
  setTimeout(() => {
    const inp = $("#cinput");
    if (!inp) return;
    inp.value = text;
    inp.dispatchEvent(new Event("input"));
    inp.focus();
    if (autoSend && typeof sendOrStop === "function") {
      sendOrStop();
    } else {
      toast("Prompt loaded into Chat — finish typing and press Enter!");
    }
  }, 250);
}

function stSetPrompt(inputId, storeKey, text) {
  const el = $("#" + inputId);
  if (el) {
    el.value = text;
    store.set(storeKey, text);
    el.focus();
  }
}

function stRunCurrentInCli(kind) {
  if (kind === "video") {
    const p = ($("#st-vp") ? $("#st-vp").value : "").trim() || "cinematic drone shot over misty mountains at sunrise";
    const m = ST.hfVideoModel || "seedance_2_5";
    const ar = ST.videoAr || "16:9";
    const dur = ST.videoDur || 5;
    const startArg = ST.startImg && ST.data ? ` --start-image "${ST.data.out}\\${ST.startImg}"` : "";
    const cmd = `higgsfield generate create ${m} --prompt "${p.replace(/"/g, '\\"')}" --aspect_ratio ${ar} --duration ${dur}${startArg} --wait`;
    stRunInTerm(cmd);
  } else {
    const p = ($("#st-p") ? $("#st-p").value : "").trim() || "cinematic neon cyberpunk street in rain";
    const m = ST.hfImageModel || "gpt_image_2_5";
    const [, , , ar] = SIZES[ST.size] || SIZES.square;
    const cmd = `higgsfield generate create ${m} --prompt "${p.replace(/"/g, '\\"')}" --aspect_ratio ${ar || "1:1"} --wait`;
    stRunInTerm(cmd);
  }
}

async function stHiggsfieldSetup(btn) {
  if (btn) { btn.disabled = true; btn.textContent = "Setting up CLI, Skills & MCP…"; }
  toast("Installing @higgsfield/cli, 8 companion skills & connecting MCP…");
  try {
    const r = await api("/api/studio/higgsfield/setup", {method: "POST", body: {login: true}});
    toast(r.message || "Higgsfield ready!");
    await renderStudio();
  } catch (e) {
    toast("⚠ " + e.message);
    if (btn) { btn.disabled = false; btn.textContent = "⚡ 1-Click Setup Higgsfield"; }
  }
}

async function stHiggsfieldLogin(btn) {
  if (btn) { btn.disabled = true; btn.textContent = "Opening browser…"; }
  toast("Opening Higgsfield OAuth login in your browser…");
  try {
    const r = await api("/api/studio/higgsfield/login", {method: "POST"});
    toast(r.message || "Complete login in your browser, then click Refresh.");
    setTimeout(() => renderStudio(), 6000);
  } catch (e) {
    toast("⚠ " + e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "1-Click Sign In (Browser)"; }
  }
}

function openHiggsfieldTerm() {
  go("chat");
  setTimeout(() => {
    if (typeof termToggle === "function") termToggle(true);
    if (typeof termNew === "function") termNew("higgsfield");
  }, 250);
}

function studioImage(d) {
  const hf = d.higgsfield || {};
  const hfModels = hf.image_models || [{id: "gpt_image_2_5", name: "GPT Image 2.5"}];
  const isHf = ST.engine === "higgsfield";
  const canRun = isHf ? !!hf.installed : (ST.engine === "gemini" ? !!d.gemini : !!d.image_model);
  const statusHint = isHf
    ? (hf.installed ? (hf.signed_in ? "Higgsfield Cloud AI · Ctrl+Enter" : "Click '1-Click Sign In (Browser)' above to authenticate Higgsfield") : "Click '⚡ 1-Click Setup Higgsfield' above to install")
    : (ST.engine === "gemini" ? "Google Gemini Cloud" : (d.image_model ? "SDXL-Turbo on your GPU · Ctrl+Enter" : "Local SDXL-Turbo model not downloaded — switch Engine to Higgsfield AI!"));

  return `<h3>${ic("spark")}Create an image</h3>
    <textarea class="f" id="st-p" rows="3" placeholder="Describe it… e.g. ancient Egyptian temple at sunset, glowing hieroglyphs" onkeydown="if(event.key==='Enter'&&(event.ctrlKey||event.metaKey))stGen()">${esc(store.get("daybook-st-p", ""))}</textarea>
    <div class="row" style="margin-top:6px;gap:6px;flex-wrap:wrap">
      <span class="small muted">1-Click Prompts:</span>
      ${HIGGSFIELD_IMAGE_PRESETS.map(([label, prompt]) =>
        `<button class="chipb" style="font-size:11px;padding:3px 8px" onclick='stSetPrompt("st-p","daybook-st-p",${JSON.stringify(prompt)})'>✦ ${esc(label)}</button>`
      ).join("")}
    </div>
    <div class="grouph">Style</div><div class="presets">${d.styles.map(s => `<button class="chipb ${ST.style === s ? "on" : ""}" onclick="ST.style='${s}';$$('.presets .chipb').forEach(b=>b.classList.toggle('on',b.textContent==='${STYLE_LABEL[s]}'))">${STYLE_LABEL[s] || s}</button>`).join("")}</div>
    <div class="row" style="margin-top:12px;gap:10px;flex-wrap:wrap">
      <select class="f" style="width:auto;font-weight:600" onchange="ST.engine=this.value;renderStudio()">
        <option value="local" ${ST.engine === "local" ? "selected" : ""}>On this PC (SDXL-Turbo · Free)</option>
        <option value="higgsfield" ${ST.engine === "higgsfield" ? "selected" : ""}>🎬 Higgsfield AI (40+ Cloud Models)</option>
        ${d.gemini ? `<option value="gemini" ${ST.engine === "gemini" ? "selected" : ""}>Gemini (Cloud)</option>` : ""}
      </select>
      ${isHf ? `<select class="f" style="width:auto;flex:1;min-width:220px" onchange="ST.hfImageModel=this.value">
        ${hfModels.map(m => `<option value="${esc(m.id)}" ${ST.hfImageModel === m.id ? "selected" : ""}>${esc(m.name)}</option>`).join("")}
      </select>` : ""}
    </div>
    <div class="row" style="margin-top:10px;gap:10px;flex-wrap:wrap">
      <div class="seg sm">${Object.entries(SIZES).map(([k, v]) => `<button class="${ST.size === k ? "on" : ""}" onclick="ST.size='${k}';this.parentNode.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b===this))">${v[2]}</button>`).join("")}</div>
      ${!isHf ? `<div class="seg sm">${[1, 2, 4].map(n => `<button class="${ST.count === n ? "on" : ""}" onclick="ST.count=${n};this.parentNode.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b===this))">${n}×</button>`).join("")}</div>` : ""}
    </div>
    <div class="row" style="margin-top:14px;gap:8px;flex-wrap:wrap">
      <button class="btn pri lg" id="st-go" onclick="stGen()" ${canRun ? "" : "disabled"}>${ic("spark")}${isHf ? "Generate with Higgsfield" : "Create"}</button>
      ${isHf ? `<button class="btn sm" onclick="stRunCurrentInCli('image')" title="Run this exact higgsfield generate command in Daybook Terminal">${ic("play")}Run in CLI</button>` : ""}
      <span class="small muted" id="st-msg">${esc(statusHint)}</span>
    </div>`;
}

function studioVideo(d) {
  const hf = d.higgsfield || {};
  const vModels = hf.video_models || [{id: "seedance_2_5", name: "Seedance 2.5 (SOTA Default)"}];
  const imgCreations = (d.creations || []).filter(c => c.kind === "image");
  const canRun = !!hf.installed;
  const statusHint = !hf.installed
    ? "Click '⚡ 1-Click Setup Higgsfield' above to install @higgsfield/cli"
    : (hf.signed_in ? "Saves MP4 straight to your Creations folder · Ctrl+Enter" : "Click '1-Click Sign In (Browser)' above to authenticate before generating");

  return `<h3>${ic("rec")}Create a video with Higgsfield AI</h3>
    <textarea class="f" id="st-vp" rows="3" placeholder="Describe the video motion &amp; camera… e.g. cinematic drone shot sweeping over a misty mountain valley at sunrise" onkeydown="if(event.key==='Enter'&&(event.ctrlKey||event.metaKey))stGenVideo()">${esc(store.get("daybook-st-vp", ""))}</textarea>
    <div class="row" style="margin-top:6px;gap:6px;flex-wrap:wrap">
      <span class="small muted">1-Click Prompts:</span>
      ${HIGGSFIELD_VIDEO_PRESETS.map(([label, prompt]) =>
        `<button class="chipb" style="font-size:11px;padding:3px 8px" onclick='stSetPrompt("st-vp","daybook-st-vp",${JSON.stringify(prompt)})'>🎬 ${esc(label)}</button>`
      ).join("")}
    </div>
    <div class="frm" style="margin-top:12px">
      <label>Video Model</label>
      <select class="f" id="st-vmodel" onchange="ST.hfVideoModel=this.value">
        ${vModels.map(m => `<option value="${esc(m.id)}" ${ST.hfVideoModel === m.id ? "selected" : ""}>${esc(m.name)}</option>`).join("")}
      </select>
      <label>Start Frame (optional Image-to-Video)</label>
      <select class="f" id="st-vstart" onchange="ST.startImg=this.value">
        <option value="">None (Text-to-Video)</option>
        ${imgCreations.map(c => `<option value="${esc(c.name)}" ${ST.startImg === c.name ? "selected" : ""}>🖼 ${esc(c.name)}${c.prompt ? " — " + esc(c.prompt.slice(0, 40)) : ""}</option>`).join("")}
      </select>
    </div>
    <div class="row" style="margin-top:12px;gap:10px;flex-wrap:wrap">
      <div class="seg sm">${[["16:9", "Landscape 16:9"], ["9:16", "Vertical 9:16"], ["1:1", "Square 1:1"]].map(([k, l]) =>
        `<button class="${ST.videoAr === k ? "on" : ""}" onclick="ST.videoAr='${k}';this.parentNode.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b===this))">${l}</button>`).join("")}</div>
      <div class="seg sm">${[5, 10].map(s =>
        `<button class="${ST.videoDur === s ? "on" : ""}" onclick="ST.videoDur=${s};this.parentNode.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b===this))">${s}s</button>`).join("")}</div>
    </div>
    <div class="row" style="margin-top:14px;gap:8px;flex-wrap:wrap">
      <button class="btn pri lg" id="st-go" onclick="stGenVideo()" ${canRun ? "" : "disabled"}>${ic("rec")}Generate Video</button>
      <button class="btn sm" onclick="stRunCurrentInCli('video')" title="Run this exact higgsfield generate command in Daybook Terminal">${ic("play")}Run in CLI</button>
      <span class="small muted" id="st-msg">${esc(statusHint)}</span>
    </div>`;
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
    ? `<div class="cre"><img src="/creations/${encodeURIComponent(c.name)}" loading="lazy" title="${esc(c.prompt || c.name)}" onclick="window.open(this.src,'_blank')">
        <div class="cra"><button class="iconbtn" title="Use this prompt" onclick="ST.tab='image';store.set('daybook-st-p',${JSON.stringify(c.prompt || "").replace(/"/g, "&quot;")});renderStudio()">${ic("rep")}</button>
        <button class="iconbtn" title="Animate this image into a video with Higgsfield" onclick="ST.tab='video';ST.startImg='${esc(c.name)}';renderStudio('video')">${ic("rec")}</button>
        <button class="iconbtn" title="Send to Discord" onclick="discordSend('creation','${esc(c.name)}')">${ic("send")}</button>
        <button class="iconbtn" title="Delete" onclick="stDel(this,'${esc(c.name)}')">${ic("trash")}</button></div></div>`
    : c.kind === "video"
    ? `<div class="cre"><video src="/creations/${encodeURIComponent(c.name)}" controls preload="metadata" style="width:100%;display:block;border-radius:10px;background:#000"></video>
        <div class="cra"><span class="small muted" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.name)}</span>
        <button class="iconbtn" title="Open full screen" onclick="window.open('/creations/${encodeURIComponent(c.name)}','_blank')">${ic("ext")}</button>
        <button class="iconbtn" title="Send to Discord" onclick="discordSend('creation','${esc(c.name)}')">${ic("send")}</button>
        <button class="iconbtn" title="Delete" onclick="stDel(this,'${esc(c.name)}')">${ic("trash")}</button></div></div>`
    : `<div class="cre au"><audio src="/creations/${encodeURIComponent(c.name)}" controls preload="none"></audio><div class="cra"><span class="small muted">${dayName(c.created)} ${tm(c.created)}</span>
        <button class="iconbtn" title="Send to Discord" onclick="discordSend('creation','${esc(c.name)}')">${ic("send")}</button><button class="iconbtn" title="Delete" onclick="stDel(this,'${esc(c.name)}')">${ic("trash")}</button></div></div>`).join("")
    || `<div class="empty" style="grid-column:1/-1"><b>Nothing yet</b>Your images, videos, and voice clips appear here.</div>`;
}

function stBusy(on, msg) { ST.busy = on; const b = $("#st-go"); if (b) b.disabled = on; if ($("#st-msg")) $("#st-msg").textContent = msg; }

async function stGen() {
  const p = $("#st-p").value.trim(); if (!p || ST.busy) return; store.set("daybook-st-p", p);
  const [w, h, , ar] = SIZES[ST.size];
  const waitMsg = ST.engine === "higgsfield"
    ? `Generating with Higgsfield (${ST.hfImageModel})…`
    : (ST.data.worker && ST.data.worker.image ? "Creating…" : "Waking the GPU and loading the model (first time ~30–60 s)…");
  stBusy(true, waitMsg);
  try {
    const j = await api("/api/studio/image", {
      method: "POST",
      body: {prompt: p, style: ST.style, width: w, height: h, aspect_ratio: ar, count: ST.count, engine: ST.engine, hf_model: ST.hfImageModel}
    });
    stBusy(false, j.seconds ? `Done in ${j.seconds}s on ${j.device}` : "Done");
    ST.data = await api("/api/studio"); $("#cre").innerHTML = creGrid(ST.data.creations); paintIcons($("#cre"));
  } catch (e) { stBusy(false, e.message); toast(e.message); }
}

async function stGenVideo() {
  const p = $("#st-vp").value.trim(); if (!p || ST.busy) return; store.set("daybook-st-vp", p);
  const model = $("#st-vmodel") ? $("#st-vmodel").value : ST.hfVideoModel;
  const startImg = $("#st-vstart") ? $("#st-vstart").value : ST.startImg;
  stBusy(true, `Generating video with Higgsfield (${model}) — this takes ~1–3 minutes…`);
  try {
    const j = await api("/api/studio/video", {
      method: "POST",
      body: {prompt: p, hf_model: model, aspect_ratio: ST.videoAr, duration: ST.videoDur, start_image: startImg}
    });
    stBusy(false, j.seconds ? `Video ready in ${j.seconds}s (${j.device})` : "Video ready!");
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

