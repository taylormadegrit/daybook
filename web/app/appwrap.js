// ================= IN-APP APP WRAPPER: Run Gemini, Claude, ChatGPT, LocalSend, Spotify & Web Apps inside Daybook =================
const AW = {
  currentApp: "gemini",
  apps: {
    gemini: { name: "Gemini", icon: "spark", url: "https://gemini.google.com/app", hint: "Google AI" },
    claude: { name: "Claude", icon: "chat", url: "https://claude.ai", hint: "Anthropic Claude" },
    chatgpt: { name: "ChatGPT", icon: "chip", url: "https://chatgpt.com", hint: "OpenAI ChatGPT" },
    localsend: { name: "LocalSend", icon: "send", url: "http://localhost:53317", hint: "LAN File Sharing" },
    spotify: { name: "Spotify", icon: "play", url: "https://open.spotify.com", hint: "Music & Podcasts" },
    youtube: { name: "YouTube Studio", icon: "video", url: "https://studio.youtube.com", hint: "Creator Studio" },
    discord: { name: "Discord", icon: "send", url: "https://discord.com/app", hint: "Chat & Communities" },
  },
  customUrl: store.get("daybook-app-custom-url", ""),
  paneId: null,
  discordView: "app",
  localSendRunning: false,
  localSendStatus: null,
  ro: null,
  bound: false,
  lastLayout: "",
};

function awGetUrl(key) {
  if (key === "custom") return store.get("daybook-app-custom-url", "https://google.com");
  return AW.apps[key]?.url || "https://gemini.google.com/app";
}

async function awCheckLocalSend() {
  try {
    const res = await api("/api/localsend/status");
    AW.localSendStatus = res;
    AW.localSendRunning = !!res?.running;
    return res;
  } catch (e) {
    AW.localSendStatus = null;
    AW.localSendRunning = false;
    return null;
  }
}

async function awEnsurePane(targetUrl) {
  if (!window.desktop || !desktop.browser) return null;
  if (AW.paneId) {
    const list = await desktop.browser.list().catch(() => []);
    if ((list || []).some(p => p.id === AW.paneId)) {
      return AW.paneId;
    }
    AW.paneId = null;
  }
  const list = await desktop.browser.list().catch(() => []);
  const existing = (list || []).find(p => p.profile === "appwrap");
  if (existing) {
    AW.paneId = existing.id;
    return AW.paneId;
  }
  const url = targetUrl || awGetUrl(AW.currentApp);
  try {
    AW.paneId = await desktop.browser.open("appwrap", url);
  } catch (e) {
    console.error("Failed to open appwrap pane:", e);
  }
  return AW.paneId;
}

function awSync(force) {
  if (!window.desktop || !desktop.browser) return;
  const host = $("#aw-frame-host");
  const overlay = $("#scrim")?.classList.contains("on") || $$(".menu.on").length > 0 || !!$(".dict.on");
  const isLocalSend = (AW.currentApp === "localsend");
  const visible = S.view === "apps" && !!host && !overlay && !isLocalSend && document.visibilityState === "visible";
  
  if (!AW.paneId) return;
  
  const rects = {};
  if (visible && host) {
    const r = host.getBoundingClientRect();
    if (r.width >= 20 && r.height >= 20) {
      rects[AW.paneId] = { x: r.x, y: r.y, w: r.width, h: r.height };
    }
  }
  const key = JSON.stringify({visible, rects});
  if (!force && key === AW.lastLayout) return;
  AW.lastLayout = key;
  desktop.browser.layout({visible, rects});
}
window.awSync = awSync;

function awRenderLocalSendHubHtml() {
  const st = AW.localSendStatus;
  const installed = !!st?.installed;
  const running = !!st?.running;
  const lanIp = st?.lan_ip || "Detecting...";
  const lanUrl = st?.lan_url || ("http://" + lanIp + ":8503");

  return `
    <div class="aw-localsend-hub">
      <div class="aw-ls-card">
        <div class="aw-ls-header">
          <div class="aw-ls-badge ${running ? 'online' : (installed ? 'standby' : 'offline')}">
            <span class="aw-ls-dot"></span>
            ${running ? 'LocalSend Active & Receiving' : (installed ? 'LocalSend Offline / Standby' : 'LocalSend Not Installed')}
          </div>
          <h2>LocalSend LAN Hub</h2>
          <p class="muted">Share files, voice notes, photos, and recordings between your PC, phones, and tablets on the local Wi-Fi. 100% private, peer-to-peer, no cloud or cables required.</p>
        </div>
        <div class="aw-ls-actions">
          ${installed ? `
            <button class="btn pri" onclick="awLaunchLocalSend()">
              ${ic("play")} Launch LocalSend Desktop App
            </button>
          ` : `
            <button class="btn pri" onclick="awInstallLocalSend()">
              ${ic("down")} Install LocalSend (Winget)
            </button>
            <a href="https://localsend.org/#/download" target="_blank" class="btn ghost">
              ${ic("ext")} Download Website
            </a>
          `}
          <button class="btn ghost" onclick="awRefreshLocalSend()">
            ${ic("rep")} Refresh Status
          </button>
          ${installed ? `
            <a href="https://localsend.org" target="_blank" class="btn ghost">
              ${ic("globe")} Official Site
            </a>
          ` : ''}
        </div>
        <div class="aw-ls-details">
          <div class="aw-ls-detail-item">
            <span class="lbl">Your Local Wi-Fi IP</span>
            <span class="val"><code class="kbd">${esc(lanIp)}</code></span>
          </div>
          <div class="aw-ls-detail-item">
            <span class="lbl">Daybook Mobile LAN URL</span>
            <span class="val"><a href="${esc(lanUrl)}" target="_blank">${esc(lanUrl)}</a></span>
          </div>
          <div class="aw-ls-detail-item">
            <span class="lbl">In-App Web Wrapper Mode</span>
            <span class="val">Port 53317 (Open LocalSend → Settings → Enable 'Web Share' to view receiver here)</span>
          </div>
        </div>
        <div class="aw-ls-tips">
          <div class="aw-ls-tip">
            <b>💡 Mobile to PC:</b> Open LocalSend on your iPhone or Android phone on the same Wi-Fi. Your PC appears automatically in the recipient list.
          </div>
          <div class="aw-ls-tip">
            <b>🎙 Daybook Voice Notes:</b> In Voice & Video Notes, click "Share to LocalSend" to beam audio notes or recordings straight to your phone.
          </div>
        </div>
      </div>
    </div>
  `;
}

async function renderAppWrapper(appKey) {
  if (appKey) AW.currentApp = appKey;
  const host = $("#v-apps");
  if (!host) return;

  if (AW.currentApp === "localsend") {
    await awCheckLocalSend();
  }

  const curKey = AW.currentApp;
  const curApp = AW.apps[curKey] || { name: "Custom App", icon: "globe", url: awGetUrl("custom"), hint: "Web App" };
  const url = curKey === "custom" ? awGetUrl("custom") : curApp.url;
  const isOfflineLocalSend = (curKey === "localsend" && !AW.localSendRunning);

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
          ${curKey === "gemini" ? `<button class="btn sm pri" onclick="awConnectGemini()" title="Sign in or connect your Google Account to Gemini">${ic("spark")} Connect / Sign In</button>` : ""}
          <button class="btn sm ghost" onclick="awSetStartupDefault('${curKey}')" title="Configure this app to open automatically when Daybook starts">★ Set Default</button>
          <button class="iconbtn" title="Open in separate window" onclick="window.desktop ? desktop.newWindow('apps') : window.open('${esc(url)}','_blank')">${ic("ext")}</button>
        </div>
      </div>
      ${curKey === "discord" ? `
        <div class="aw-subbar">
          <button class="aw-subtab ${AW.discordView === 'app' ? 'on' : ''}" onclick="awDiscordNav('https://discord.com/app', 'app')" title="Open Discord DMs, friends, and servers you belong to">
            ${ic("chat", "i sm")} Personal Account &amp; DMs
          </button>
          <button class="aw-subtab ${AW.discordView === 'login' ? 'on' : ''}" onclick="awDiscordNav('https://discord.com/login', 'login')" title="Log in with your personal Discord credentials">
            ${ic("spark", "i sm")} Sign In / Switch Account
          </button>
          <button class="aw-subtab ${AW.discordView === 'discovery' ? 'on' : ''}" onclick="awDiscordNav('https://discord.com/guild-discovery', 'discovery')" title="Browse public Discord servers and communities">
            ${ic("search", "i sm")} Public Server Discovery
          </button>
          <button class="aw-subtab" onclick="awPromptDiscordInvite()" title="Join any Discord server using an invite code or URL">
            ${ic("plus", "i sm")} Join Server by Invite
          </button>
          <div class="sp"></div>
          <span class="aw-sub-label">Public Communities:</span>
          <button class="aw-chip" onclick="awDiscordNav('https://discord.gg/openai', 'openai')">OpenAI</button>
          <button class="aw-chip" onclick="awDiscordNav('https://discord.gg/anthropic', 'anthropic')">Anthropic</button>
          <button class="aw-chip" onclick="awDiscordNav('https://discord.gg/midjourney', 'midjourney')">Midjourney</button>
          <button class="aw-chip" onclick="awDiscordNav('https://discord.gg/huggingface', 'huggingface')">Hugging Face</button>
          <button class="aw-chip" onclick="awDiscordNav('https://discord.gg/cursor', 'cursor')">Cursor</button>
          <button class="aw-chip" onclick="awDiscordNav('https://discord.gg/localllama', 'localllama')">LocalLLaMA</button>
        </div>
      ` : ''}
      <div class="aw-frame-host" id="aw-frame-host">
        ${curKey === "localsend" ? awRenderLocalSendHubHtml() : (
          (window.desktop && desktop.browser) ? '' : `
            <div class="aw-localsend-hub">
              <div class="aw-ls-card" style="text-align:center;align-items:center;">
                <h2>${esc(curApp.name)} Web App</h2>
                <p class="muted">Major web applications (Gemini, Discord, Claude) restrict framing in generic web browsers for security. In the <b>Daybook Desktop App</b>, they render in native isolated Chromium panes with full account sync.</p>
                <div class="aw-ls-actions" style="justify-content:center;margin-top:14px;">
                  <a href="${esc(url)}" target="_blank" class="btn pri lg">
                    ${ic("ext")} Open ${esc(curApp.name)} in New Window
                  </a>
                  ${curKey === "gemini" ? `
                    <button class="btn ghost" onclick="window.open('https://accounts.google.com/InteractiveLogin?continue=https%3A%2F%2Fgemini.google.com%2Fapp','_blank')">
                      ${ic("spark")} Sign In with Google
                    </button>
                  ` : ''}
                  ${curKey === "discord" ? `
                    <button class="btn ghost" onclick="window.open('https://discord.com/login','_blank')">
                      ${ic("chat")} Sign In to Discord
                    </button>
                  ` : ''}
                </div>
              </div>
            </div>
          `
        )}
      </div>
    </div>
  `;

  paintIcons(host);

  if (window.desktop && desktop.browser) {
    if (curKey !== "localsend") {
      await awEnsurePane(url);
      if (AW.paneId) {
        desktop.browser.nav(AW.paneId, "go", url);
      }
    } else {
      awSync(true);
    }
    if (!AW.ro) {
      AW.ro = new ResizeObserver(() => awSync());
    }
    const frameHost = $("#aw-frame-host");
    if (frameHost) AW.ro.observe(frameHost);

    if (!AW.bound) {
      AW.bound = true;
      desktop.browser.onUpdate(d => {
        if (S.view !== "apps") return;
        const myPane = (d.panes || []).find(p => p.id === AW.paneId);
        if (myPane && myPane.url && !myPane.url.startsWith("about:")) {
          const uInput = $("#aw-url");
          if (uInput && document.activeElement !== uInput) uInput.value = myPane.url;
        }
      });
    }
    awSync(true);
    setTimeout(() => { if (S.view === "apps") awSync(); }, 350);
  }
}

async function awSwitch(key) {
  AW.currentApp = key;
  await renderAppWrapper(key);
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
  if (!val || AW.currentApp === "localsend") return;
  let clean = val.trim();
  if (!/^https?:\/\//i.test(clean)) clean = "https://" + clean;
  if (window.desktop && desktop.browser && AW.paneId) {
    desktop.browser.nav(AW.paneId, "go", clean);
    desktop.browser.nav(AW.paneId, "focus");
    awSync(true);
    return;
  }
  const f = $("#aw-frame");
  if (f) f.src = clean;
}

function awNav(action) {
  if (AW.currentApp === "localsend") {
    if (action === "reload") awRefreshLocalSend();
    return;
  }
  if (window.desktop && desktop.browser && AW.paneId) {
    desktop.browser.nav(AW.paneId, action);
    return;
  }
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

async function awLaunchLocalSend() {
  toast("Launching LocalSend...");
  try {
    const res = await api("/api/localsend/launch", { method: "POST" });
    if (res.error) toast(res.error);
    else toast("✓ LocalSend launched");
    let attempts = 0;
    const timer = setInterval(async () => {
      attempts++;
      const st = await awCheckLocalSend();
      if (st?.running) {
        clearInterval(timer);
        toast("✓ LocalSend is active!");
        awSwitch("localsend");
      } else if (attempts > 12) {
        clearInterval(timer);
      }
    }, 1500);
  } catch (e) {
    toast("Failed to launch LocalSend: " + e.message);
  }
}

async function awRefreshLocalSend() {
  toast("Checking LocalSend status...");
  const st = await awCheckLocalSend();
  if (st?.running) {
    toast("✓ LocalSend is active on port 53317");
    awSwitch("localsend");
  } else {
    toast(st?.installed ? "LocalSend installed but not currently running" : "LocalSend not detected");
    renderAppWrapper("localsend");
  }
}

async function awInstallLocalSend() {
  toast("Triggering LocalSend installation via winget...");
  try {
    if (window.desktop && desktop.term) {
      window.desktop.newWindow("term");
    } else {
      window.open("https://localsend.org/#/download", "_blank");
    }
  } catch (e) {
    window.open("https://localsend.org/#/download", "_blank");
  }
}

function awConnectGemini() {
  const url = "https://accounts.google.com/InteractiveLogin?continue=https%3A%2F%2Fgemini.google.com%2Fapp";
  awLoadUrl(url);
}

function awDiscordNav(url, viewKey) {
  AW.discordView = viewKey || "app";
  awLoadUrl(url);
  $$(".aw-subtab").forEach(b => b.classList.toggle("on", !!b.getAttribute("onclick")?.includes(`'${viewKey}'`)));
}

function awPromptDiscordInvite() {
  const inv = prompt("Enter Discord server invite code or link (e.g. discord.gg/openai):", "https://discord.gg/");
  if (inv && inv.trim()) {
    let clean = inv.trim();
    if (!/^https?:\/\//i.test(clean)) clean = "https://" + clean;
    awDiscordNav(clean, "invite");
  }
}

