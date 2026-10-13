// ================= DESKTOP APP: real in-app browser panes (Electron WebContentsView) =================
// Only used inside the Daybook desktop app (window.desktop exists). In a plain browser, browser.js docks Chrome windows instead.
const BD = {panes: [], focus: null, layout: store.get("daybook-bd-layout", "auto"), ro: null, restored: false, bound: false, last: "", ratios: (() => { try { return JSON.parse(localStorage.getItem("daybook-bd-ratios") || "{}"); } catch (e) { return {}; } })()};
BD.chrome = [];
const bdAll = () => BD.panes.concat(BD.chrome.map(c => ({id: -c.hwnd, chrome: c, profile: "chrome:" + c.profile, title: c.title.replace(/ - Google Chrome$/, "") || c.label, url: "", loading: false})));
async function bdWin() { if (!BD.win) BD.win = await desktop.info(); return BD.win; }
async function bdChromeRefresh() { try { const w = await bdWin(); BD.chrome = await api("/api/dock/embedded?parent=" + w.hwnd); } catch (e) { BD.chrome = []; } }
function bdClose(id) { return id < 0 ? api("/api/dock/embed/release", {method: "POST", body: {hwnd: -id, close: true}}).then(() => setTimeout(async () => { await bdChromeRefresh(); bdPaint(); }, 400)) : desktop.browser.close(id); }
async function bdChromeOpen(b, p) {
  $$(".menu").forEach(x => x.classList.remove("on")); if (S.view !== "browser") go("browser");
  toast("Opening your Chrome profile inside Daybook…");
  try { const w = await bdWin(); const j = await api("/api/dock/embed/open", {method: "POST", body: {browser: b, profile: p, parent: w.hwnd}}); await bdChromeRefresh(); BD.focus = -j.hwnd; bdPaint(); }
  catch (e) { toast(e.message); }
}
async function bdChromePop(id) { await api("/api/dock/embed/release", {method: "POST", body: {hwnd: -id}}); await bdChromeRefresh(); bdPaint(); }
const bdKind = (n, layout) => layout === "rows" ? "rows" : (layout === "tabs" || layout === "grid" || (layout === "auto" && n > 3)) ? "" : "cols";
function bdWeights(n, layout) { const k = bdKind(n, layout) + n, w = BD.ratios[k]; return w && w.length === n ? w : Array(n).fill(1 / n); }
const BD_COLORS = ["#8b7bff", "#4fd1ff", "#ff7ac6", "#3ee0a0", "#ffbe5c", "#ff6b81", "#a3e635", "#f97316"];
function webProfiles() {
  try { const p = JSON.parse(S.settings.web_profiles || "[]"); if (p.length) return p; } catch (e) {}
  return [{id: "personal", name: "Personal", color: BD_COLORS[0]}];
}
const bdProf = id => webProfiles().find(p => p.id === id) || {id, name: id, color: "#888"};
function bdUrl(v) {
  v = v.trim(); if (!v) return "";
  if (/^[a-z]+:\/\//i.test(v)) return v;
  if (/^[\w-]+(\.[\w-]+)+(\/|$|:)/.test(v) || v.startsWith("localhost")) return "https://" + v;
  return "https://www.google.com/search?q=" + encodeURIComponent(v);
}
async function renderBrowserDesktop() {
  if (!BD.bound) {
    BD.bound = true;
    desktop.browser.onUpdate(d => {
      BD.panes = d.panes; if (d.focus) BD.focus = d.focus; if (d.toast) toast(d.toast);
      if (!BD.panes.find(p => p.id === BD.focus)) BD.focus = (BD.panes[BD.panes.length - 1] || {}).id;
      if (BD.win && BD.win.main) try { localStorage.setItem("daybook-bd-session", JSON.stringify(BD.panes.map(p => ({profile: p.profile, url: p.url})).filter(p => /^https?:/.test(p.url)))); } catch (e) {}
      if (S.view === "browser") bdPaint();
    });
    desktop.browser.onShortcut(d => {
      if (d.action === "new") bdNew(d.profile);
      if (d.action === "save") bdSaveLink(d.id);
      if (d.action === "saved") { if (typeof LK !== "undefined") LK.saved[d.url] = d.lid; bdPaint(); }
      if (d.action === "address") { go("browser"); setTimeout(() => { const i = $(`.bd-pane[data-id="${d.id}"] .bd-url`); if (i) { i.focus(); i.select(); } }, 60); }
    });
  }
  BD.panes = await desktop.browser.list(); await bdChromeRefresh();
  clearInterval(BD.poll); BD.poll = setInterval(async () => { if (S.view !== "browser") return; const was = JSON.stringify(BD.chrome); await bdChromeRefresh(); if (was !== JSON.stringify(BD.chrome)) bdPaint(); }, 2500);
  const me = await bdWin();
  if (!BD.restored) {  // reopen last session's pages (main window only — extra windows start fresh)
    BD.restored = true;
    if (!BD.panes.length && me.main) {
      let saved = []; try { saved = JSON.parse(localStorage.getItem("daybook-bd-session") || "[]"); } catch (e) {}
      for (const p of saved.slice(0, 8)) await desktop.browser.open(p.profile, p.url);
      BD.panes = await desktop.browser.list();
    }
  }
  const profs = webProfiles();
  $("#v-browser").innerHTML = `<div class="bw-bar">
      <div class="bd-profs">${profs.map(p => `<button class="bd-prof" style="--c:${p.color}" title="New ${esc(p.name)} tab (Ctrl+T)" onclick="bdNew('${p.id}')"><i></i>${esc(p.name)}<span>${ic("plus")}</span></button>`).join("")}
        <button class="iconbtn" title="Add a browser profile (separate logins)" onclick="bdProfileModal()">${ic("plus")}</button></div>
      <div class="sp"></div>
      <button class="btn sm ghost" id="bd-adb" title="Blocks ads and trackers in Daybook's browser (YouTube ads too)" onclick="bdAdblock(true)">🛡 Ad blocker</button>
      <div class="seg sm">${[["tabs", "Tabs"], ["auto", "Split"], ["grid", "Grid"], ["rows", "Rows"]].map(([k, l]) => `<button class="${BD.layout === k ? "on" : ""}" onclick="bdLayout('${k}')">${l}</button>`).join("")}</div>
      <div style="position:relative"><button class="btn sm" title="Your real Chrome profiles — already signed in — inside Daybook" onclick="bdChromeMenu(event)">${ic("globe")}Chrome profiles</button>
        <div class="menu" id="bw-profiles" style="right:0;top:36px;max-height:60vh;overflow:auto;min-width:280px"></div></div></div>
    <div class="bd-tabs" id="bd-tabs"></div>
    <div class="bd-stage" id="bd-stage"></div>`;
  paintIcons($("#v-browser")); bdAdblock();
  if (!BD.ro) BD.ro = new ResizeObserver(() => { bdPaint(); });
  BD.ro.observe($("#bd-stage"));
  bdPaint(); bdSync(true);
}
function bdTiles(n, w, h, layout) {
  const g = 8; if (!n) return [];
  if (layout === "tabs") return [[0, 0, w, h]];
  if (layout === "rows") { const wt = bdWeights(n, layout), avail = h - g * (n - 1); let y = 0; return wt.map(f => { const t = [0, y, w, avail * f]; y += avail * f + g; return t; }); }
  if (layout === "grid" || (layout === "auto" && n > 3)) {
    const c = Math.ceil(Math.sqrt(n)), r = Math.ceil(n / c), ch = (h - g * (r - 1)) / r;
    return [...Array(n)].map((_, i) => { const row = Math.floor(i / c), inRow = Math.min(c, n - row * c), cw = (w - g * (inRow - 1)) / inRow; return [(i - row * c) * (cw + g), row * (ch + g), cw, ch]; });
  }
  const wt = bdWeights(n, layout), avail = w - g * (n - 1); let x = 0; return wt.map(f => { const t = [x, 0, avail * f, h]; x += avail * f + g; return t; });
}
// draggable dividers between panes (side by side, or stacked in Rows)
function bdDividers(st, tiles, n) {
  st.querySelectorAll(".split-h").forEach(e => e.remove());
  const kind = bdKind(n, BD.layout); if (!kind || n < 2) return;
  for (let i = 0; i < n - 1; i++) {
    const h = document.createElement("div"); h.className = "split-h" + (kind === "rows" ? " row" : ""); h.title = "Drag to resize · double-click to make them even";
    const t = tiles[i];
    if (kind === "rows") Object.assign(h.style, {left: "0", width: "100%", top: (t[1] + t[3] + 4 - 4) + "px"}); else Object.assign(h.style, {left: (t[0] + t[2] + 4 - 4) + "px", top: "0", height: "100%"});
    h.addEventListener("pointerdown", e => {
      e.preventDefault(); h.setPointerCapture(e.pointerId); h.classList.add("dragging", "on"); document.body.classList.add("splitting"); if (kind === "rows") document.body.classList.add("rows");
      const wt = bdWeights(n, BD.layout).slice(), total = kind === "rows" ? st.clientHeight - 8 * (n - 1) : st.clientWidth - 8 * (n - 1), start = kind === "rows" ? e.clientY : e.clientX;
      h._d = {wt, total, start};
    });
    h.addEventListener("pointermove", e => {
      if (!h._d) return; const {wt, total, start} = h._d, d = ((kind === "rows" ? e.clientY : e.clientX) - start) / total, pair = wt[i] + wt[i + 1];
      const a = Math.max(0.1, Math.min(pair - 0.1, wt[i] + d)), nw = wt.slice(); nw[i] = a; nw[i + 1] = pair - a;
      BD.ratios[kind + n] = nw; bdPaint();
      const t2 = BD.lastTiles[i]; if (t2) { if (kind === "rows") h.style.top = (t2[1] + t2[3]) + "px"; else h.style.left = (t2[0] + t2[2]) + "px"; }
    });
    const end = () => { if (!h._d) return; h._d = null; h.classList.remove("dragging", "on"); document.body.classList.remove("splitting", "rows"); bdPaint(); try { localStorage.setItem("daybook-bd-ratios", JSON.stringify(BD.ratios)); } catch (e) {} };
    h.addEventListener("pointerup", end); h.addEventListener("pointercancel", end);
    h.addEventListener("dblclick", () => { delete BD.ratios[kind + n]; try { localStorage.setItem("daybook-bd-ratios", JSON.stringify(BD.ratios)); } catch (e) {} bdPaint(); });
    st.appendChild(h);
  }
}
function bdPaint() {
  const st = $("#bd-stage"); if (!st) return;
  const panes = bdAll(); if (!panes.find(p => p.id === BD.focus)) BD.focus = (panes[0] || {}).id;
  const focus = BD.focus;
  const tabsHtml = panes.map(p => { const pr = p.chrome ? {color: "#4285f4"} : bdProf(p.profile); return `<div class="bd-tab ${p.id === focus ? "on" : ""}" style="--c:${pr.color}" title="${esc(p.title)}\n${esc(p.url)}" onclick="bdFocus(${p.id})">
      ${p.chrome ? `<span class="bd-chrome">C</span>` : p.loading ? `<span class="spin"></span>` : p.favicon ? `<img src="${esc(p.favicon)}" alt="">` : `<i></i>`}<span>${esc(p.chrome ? p.chrome.label + " · " + p.title : p.title || "New tab")}</span>${p.audible ? "🔊" : ""}
      <button title="Close" onclick="event.stopPropagation();bdClose(${p.id})">${ic("x")}</button></div>`; }).join("")
    + (panes.length ? `<button class="iconbtn" title="New tab (Ctrl+T)" onclick="bdNew((BD.panes.find(p=>p.id===BD.focus)||{}).profile||'personal')">${ic("plus")}</button>` : "");
  const tabsEl = $("#bd-tabs"); if (tabsEl._html !== tabsHtml) { tabsEl._html = tabsHtml; tabsEl.innerHTML = tabsHtml; paintIcons(tabsEl); }
  const W = st.clientWidth, H = st.clientHeight, shown = BD.layout === "tabs" ? panes.filter(p => p.id === focus) : panes;
  const tiles = bdTiles(shown.length, W, H, BD.layout), have = new Set(); BD.lastTiles = tiles;
  st.querySelector(".bd-empty") && panes.length && st.querySelector(".bd-empty").remove();
  shown.forEach((p, i) => {
    have.add(String(p.id));
    let el = st.querySelector(`.bd-pane[data-id="${p.id}"]`);
    if (!el && p.chrome) {
      el = document.createElement("div"); el.className = "bd-pane chrome"; el.dataset.id = p.id;
      el.innerHTML = `<div class="bd-ph"><span class="bd-chrome">C</span><b class="bd-ctitle"></b><span class="bd-pbadge" style="--c:#4285f4"></span><span class="sp"></span>
        <button class="iconbtn" title="Pop out into its own window" onclick="bdChromePop(${p.id})">${ic("ext")}</button>
        <button class="iconbtn" title="Close this Chrome window" onclick="bdClose(${p.id})">${ic("x")}</button></div><div class="bd-body"></div>`;
      el.addEventListener("mousedown", () => { if (BD.focus !== p.id) { BD.focus = p.id; bdMarkFocus(); } });
      st.appendChild(el); paintIcons(el);
    }
    if (!el) {
      el = document.createElement("div"); el.className = "bd-pane"; el.dataset.id = p.id;
      el.innerHTML = `<div class="bd-ph">
        <button class="iconbtn" data-a="back" title="Back (Alt+←)">${ic("left")}</button><button class="iconbtn" data-a="forward" title="Forward (Alt+→)">${ic("right")}</button>
        <button class="iconbtn" data-a="reload" title="Reload (Ctrl+R)">${ic("rep")}</button>
        <input class="bd-url" spellcheck="false" placeholder="Search or type a web address"><button class="iconbtn bd-star" data-a="save" title="Save to your Library (Ctrl+D)">☆</button><span class="bd-pbadge"></span>
        <button class="iconbtn" data-a="mute" title="Mute / unmute">🔈</button><button class="iconbtn" data-a="external" title="Open in your normal browser">${ic("ext")}</button>
        <button class="iconbtn" data-a="close" title="Close (Ctrl+W)">${ic("x")}</button></div><div class="bd-body"></div>`;
      el.querySelectorAll("[data-a]").forEach(b => b.onclick = () => b.dataset.a === "close" ? desktop.browser.close(p.id) : b.dataset.a === "save" ? bdSaveLink(p.id) : desktop.browser.nav(p.id, b.dataset.a));
      const u = el.querySelector(".bd-url");
      u.onkeydown = e => { if (e.key === "Enter") { const url = bdUrl(u.value); if (url) { desktop.browser.nav(p.id, "go", url); desktop.browser.nav(p.id, "focus"); } } if (e.key === "Escape") u.blur(); };
      u.onfocus = () => setTimeout(() => u.select(), 0);
      el.addEventListener("mousedown", () => { if (BD.focus !== p.id) { BD.focus = p.id; bdMarkFocus(); } });
      st.appendChild(el); paintIcons(el);
    }
    const [x, y, w, h] = tiles[i]; Object.assign(el.style, {left: x + "px", top: y + "px", width: w + "px", height: h + "px"});
    if (p.chrome) {
      el.querySelector(".bd-ctitle").textContent = p.title; el.querySelector(".bd-pbadge").textContent = "Chrome · " + p.chrome.label;
      el.classList.toggle("on", p.id === focus); return;
    }
    const pr = bdProf(p.profile), u = el.querySelector(".bd-url");
    if (document.activeElement !== u) u.value = p.url && !p.url.startsWith("about:") ? p.url : "";
    el.querySelector('[data-a="back"]').disabled = !p.canBack; el.querySelector('[data-a="forward"]').disabled = !p.canFwd;
    const m = el.querySelector('[data-a="mute"]'); m.textContent = p.muted ? "🔇" : "🔈"; m.style.display = p.audible || p.muted ? "" : "none";
    const b = el.querySelector(".bd-pbadge"); b.textContent = pr.name; b.style.setProperty("--c", pr.color);
    const star = el.querySelector(".bd-star"), saved = typeof LK !== "undefined" && !!LK.saved[p.url];
    star.textContent = saved ? "★" : "☆"; star.classList.toggle("on", saved); star.title = saved ? "Saved in your Library — click to file it" : "Save to your Library (Ctrl+D)";
    if (window.bdCheckSaved && !p.loading) bdCheckSaved(p.url);
    el.classList.toggle("loading", !!p.loading); el.classList.toggle("on", p.id === focus);
  });
  st.querySelectorAll(".bd-pane").forEach(el => { if (!have.has(el.dataset.id)) el.remove(); });
  if (!st.querySelector(".split-h.dragging")) bdDividers(st, tiles, shown.length);
  if (!panes.length && !st.querySelector(".bd-empty")) st.innerHTML = `<div class="empty bd-empty"><b>Browse without leaving Daybook</b>Real web pages, right here. Each profile keeps its own logins — sign in once. Open several and they split the space evenly.
      <div class="row" style="justify-content:center;margin-top:14px;gap:8px">${webProfiles().map(p => `<button class="btn" onclick="bdNew('${p.id}')"><span class="bd-dot" style="background:${p.color}"></span>${esc(p.name)}</button>`).join("")}
      <button class="btn ghost" onclick="bdNew('personal','https://www.youtube.com')">YouTube</button><button class="btn ghost" onclick="bdNew('personal','https://mail.google.com')">Gmail</button></div></div>`;
  bdSync();
}
async function bdAdblock(toggle) {
  if (!desktop.browser.adblock) return;
  let s = await desktop.browser.adblock();
  if (toggle && s.ready) { s = await desktop.browser.adblock(!s.on); toast(s.on ? "Ad blocker on — reload a page to see it clean" : "Ad blocker off"); }
  const b = $("#bd-adb"); if (!b) return;
  b.textContent = !s.ready ? "🛡 Ad blocker (loading…)" : s.on ? `🛡 Ads blocked${s.blocked ? ": " + s.blocked.toLocaleString() : ""}` : "🛡 Ad blocker off";
  b.classList.toggle("on", s.ready && s.on);
}
function bdMarkFocus() { $$(".bd-pane").forEach(e => e.classList.toggle("on", +e.dataset.id === BD.focus)); $$(".bd-tab").forEach(e => e.classList.toggle("on", e.getAttribute("onclick") === `bdFocus(${BD.focus})`)); }
function bdSync(force) {
  const st = $("#bd-stage");
  const overlay = $("#scrim").classList.contains("on") || $$(".menu.on").length > 0 || !!$(".dict.on");
  const visible = S.view === "browser" && !!st && !overlay;
  const rects = {}, items = [];
  if (visible) $$(".bd-pane").forEach(el => { const r = el.querySelector(".bd-body").getBoundingClientRect(), id = +el.dataset.id, rr = {x: r.x, y: r.y, w: r.width, h: r.height};
    if (id < 0) items.push({hwnd: -id, ...rr}); else rects[id] = rr; });
  const key = JSON.stringify({visible, rects, items}); if (!force && key === BD.last) return; BD.last = key;
  desktop.browser.layout({visible, rects});
  if (BD.chrome.length || items.length) fetch("/api/dock/embed/place", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({visible, items, dpr: devicePixelRatio, parent: BD.win && BD.win.hwnd})}).catch(() => {});
}
async function bdNew(profile, url) {
  if (S.view !== "browser") go("browser");
  const id = await desktop.browser.open(profile || "personal", url || "https://www.google.com"); BD.focus = id;
  if (!url) setTimeout(() => { const i = $(`.bd-pane[data-id="${id}"] .bd-url`); if (i) i.focus(); }, 300);
}
function bdFocus(id) { BD.focus = id; bdPaint(); if (id > 0) desktop.browser.nav(id, "focus"); }
function bdLayout(l) { BD.layout = l; store.set("daybook-bd-layout", l); renderBrowserDesktop(); }
function bdProfileModal() {
  modal(`<h2>${ic("globe", "i")}Browser profiles<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    <div class="muted small" style="margin-bottom:10px">Each profile is its own browser with separate logins and cookies — e.g. Personal, Work, Ori. Sign in once and it remembers.</div>
    ${webProfiles().map(p => `<div class="srow"><div class="d"><b><span class="bd-dot" style="background:${p.color}"></span>${esc(p.name)}</b></div>${p.id !== "personal" ? `<button class="btn sm ghost danger" onclick="bdDelProfile('${p.id}')">${ic("trash")}</button>` : ""}</div>`).join("")}
    <div class="row" style="flex-wrap:nowrap;margin-top:10px"><input class="f" id="bdp-n" placeholder="New profile name, e.g. Work" onkeydown="event.key==='Enter'&&bdAddProfile()"><button class="btn pri" onclick="bdAddProfile()">${ic("plus")}Add</button></div>`);
  setTimeout(() => $("#bdp-n").focus(), 30);
}
async function bdAddProfile() {
  const n = $("#bdp-n").value.trim(); if (!n) return;
  const ps = webProfiles(), id = n.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  if (!ps.find(p => p.id === id)) ps.push({id, name: n, color: BD_COLORS[ps.length % BD_COLORS.length]});
  await saveSetting("web_profiles", JSON.stringify(ps)); closeModal(); renderBrowserDesktop();
}
async function bdDelProfile(id) { await saveSetting("web_profiles", JSON.stringify(webProfiles().filter(p => p.id !== id))); bdProfileModal(); renderBrowserDesktop(); }
async function bdChromeMenu(e) {
  e.stopPropagation(); if (!LP.data) LP.data = await api("/api/launchpad");
  const m = $("#bw-profiles"), on = !m.classList.contains("on");
  m.innerHTML = `<div class="mh">Your signed-in Chrome profiles — open inside Daybook</div>` + LP.data.browsers.flatMap(b => b.profiles.map(p => `<div onclick="bdChromeOpen('${b.id}',${JSON.stringify(p.id).replace(/"/g, "&quot;")})">${p.picture ? `<img class="bw-av" src="/browser-avatar/${b.id}/${encodeURIComponent(p.id)}">` : `<span class="bw-av" style="background:${p.color}">${esc(p.name[0])}</span>`}${esc(p.name)}<span class="kbd">${esc(b.name.replace("Google ", ""))}</span></div>`)).join("");
  $$(".menu").forEach(x => x.classList.remove("on")); m.classList.toggle("on", on); bdSync();
}
