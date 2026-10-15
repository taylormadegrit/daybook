// ================= IN-APP APP WRAPPER: Run LocalSend, Gemini, Claude & Web Apps inside Daybook =================
const AW = {
  currentApp: "localsend",
  apps: {
    localsend: { name: "LocalSend", icon: "send", url: "http://localhost:53317", hint: "LAN File Sharing" },
    gemini: { name: "Gemini", icon: "spark", url: "https://gemini.google.com/app", hint: "Google AI" },
    claude: { name: "Claude", icon: "chat", url: "https://claude.ai", hint: "Anthropic Claude" },
    chatgpt: { name: "ChatGPT", icon: "chip", url: "https://chatgpt.com", hint: "OpenAI ChatGPT" },
    spotify: { name: "Spotify", icon: "play", url: "https://open.spotify.com", hint: "Music & Podcasts" },
    youtube: { name: "YouTube Studio", icon: "video", url: "https://studio.youtube.com", hint: "Creator Studio" },
    discord: { name: "Discord", icon: "send", url: "https://discord.com/app", hint: "Chat & Communities" },
  },
  customUrl: store.get("daybook-app-custom-url", ""),
  paneId: null,
};

function awGetUrl(key) {
  if (key === "custom") return store.get("daybook-app-custom-url", "https://google.com");
  return AW.apps[key]?.url || "https://gemini.google.com/app";
}

async function renderAppWrapper(appKey) {
  if (appKey) AW.currentApp = appKey;
  const host = $("#v-apps");
  if (!host) return;

  const curKey = AW.currentApp;
  const curApp = AW.apps[curKey] || { name: "Custom App", icon: "globe", url: awGetUrl("custom"), hint: "Web App" };
  const url = curKey === "custom" ? awGetUrl("custom") : curApp.url;

  host.innerHTML = `
    <div class="aw-wrap">
      <div class="aw-bar">
        <div class="aw-tabs">
          ${Object.entries(AW.apps).map(([k, a]) => `
            <button class="aw-tab ${k === curKey ? "on" : ""}" onclick="awSwitch('${k}')">
              ${ic(a.icon || "globe", "i sm")}
              <span>${esc(a.name)}</span>
            </button>
          `).join("")}
          <button class="aw-tab ${curKey === "custom" ? "on" : ""}" onclick="awPromptCustom()">
            ${ic("plus", "i sm")}
            <span>Custom URL</span>
          </button>
        </div>
        <div class="sp"></div>
        <div class="aw-acts">
          <button class="iconbtn" title="Back" onclick="awNav('back')">${ic("left")}</button>
          <button class="iconbtn" title="Forward" onclick="awNav('forward')">${ic("right")}</button>
          <button class="iconbtn" title="Reload" onclick="awNav('reload')">${ic("rep")}</button>
          <input class="f aw-url-input" id="aw-url" value="${esc(url)}" placeholder="https://..." onkeydown="if(event.key==='Enter')awLoadUrl(this.value)">
          <button class="btn sm ghost" onclick="awSetStartupDefault('${curKey}')" title="Configure this app to open automatically when Daybook starts">★ Set Default</button>
          <button class="iconbtn" title="Open in separate window" onclick="window.desktop ? desktop.newWindow('apps') : window.open('${esc(url)}','_blank')">${ic("ext")}</button>
        </div>
      </div>
      <div class="aw-frame-host" id="aw-frame-host">
        <iframe id="aw-frame" src="${esc(url)}" class="aw-iframe" allow="microphone; camera; clipboard-read; clipboard-write; display-capture; autoplay; encrypted-media; fullscreen" sandbox="allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts allow-downloads"></iframe>
        <div class="aw-external-bar" id="aw-ext-bar">
          <span>Displaying <b>${esc(curApp.name)}</b> inside Daybook wrapper.</span>
          <a href="${esc(url)}" target="_blank" class="btn sm pri">Open Externally</a>
          ${curKey === "localsend" ? `<button class="btn sm" onclick="api('/api/localsend/launch',{method:'POST'}).then(r=>toast(r.error||'LocalSend started')).catch(e=>toast(e.message))">Launch LocalSend App</button>` : ""}
        </div>
      </div>
    </div>
  `;

  paintIcons(host);
}

function awSwitch(key) {
  AW.currentApp = key;
  renderAppWrapper(key);
}

function awPromptCustom() {
  const current = store.get("daybook-app-custom-url", "https://");
  const val = prompt("Enter the Web App URL to embed inside Daybook:", current);
  if (val && val.trim()) {
    let clean = val.trim();
    if (!/^https?:\/\//i.test(clean)) clean = "https://" + clean;
    store.set("daybook-app-custom-url", clean);
    AW.customUrl = clean;
    awSwitch("custom");
  }
}

function awLoadUrl(val) {
  if (!val) return;
  let clean = val.trim();
  if (!/^https?:\/\//i.test(clean)) clean = "https://" + clean;
  const f = $("#aw-frame");
  if (f) f.src = clean;
}

function awNav(action) {
  const f = $("#aw-frame");
  if (!f) return;
  try {
    if (action === "reload") f.src = f.src;
    else if (action === "back") history.back();
    else if (action === "forward") history.forward();
  } catch (e) {
    f.src = f.src;
  }
}

async function awSetStartupDefault(key) {
  const url = awGetUrl(key);
  try {
    await saveSetting("startup_view", "apps:" + key);
    localStorage.setItem("daybook-startup-view", "apps:" + key);
    toast(`✓ Set ${AW.apps[key]?.name || "Custom App"} as your default startup window!`);
  } catch (e) {
    localStorage.setItem("daybook-startup-view", "apps:" + key);
    toast(`✓ Default startup app saved`);
  }
}
