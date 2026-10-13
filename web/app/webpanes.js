// ================= DESKTOP APP: real in-app browser panes (Electron WebContentsView) =================
// Only used inside the Daybook desktop app (window.desktop exists). In a plain browser, browser.js docks Chrome windows instead.
const BD = {panes: [], focus: null, layout: store.get("daybook-bd-layout", "auto"), ro: null, restored: false, bound: false, last: ""};
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
      try { localStorage.setItem("daybook-bd-session", JSON.stringify(BD.panes.map(p => ({profile: p.profile, url: p.url})).filter(p => /^https?:/.test(p.url)))); } catch (e) {}
      if (S.view === "browser") bdPaint();
    });
    desktop.browser.onShortcut(d => {
      if (d.action === "new") bdNew(d.profile);
      if (d.action === "address") { go("browser"); setTimeout(() => { const i = $(`.bd-pane[data-id="${d.id}"] .bd-url`); if (i) { i.focus(); i.select(); } }, 60); }
    });
  }
  BD.panes = await desktop.browser.list();
  if (!BD.restored) {  // reopen last session's pages
    BD.restored = true;
    if (!BD.panes.length) {
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
      <div class="seg sm">${[["tabs", "Tabs"], ["auto", "Split"], ["grid", "Grid"], ["rows", "Rows"]].map(([k, l]) => `<button class="${BD.layout === k ? "on" : ""}" onclick="bdLayout('${k}')">${l}</button>`).join("")}</div>
      <div style="position:relative"><button class="btn sm ghost" title="Open one of your real Chrome profiles in its own window" onclick="bdChromeMenu(event)">${ic("globe")}Chrome profiles</button>
        <div class="menu" id="bw-profiles" style="right:0;top:36px;max-height:60vh;overflow:auto;min-width:280px"></div></div></div>
    <div class="bd-tabs" id="bd-tabs"></div>
    <div class="bd-stage" id="bd-stage"></div>`;
  paintIcons($("#v-browser"));
  if (!BD.ro) BD.ro = new ResizeObserver(() => { bdPaint(); });
  BD.ro.observe($("#bd-stage"));
  bdPaint();
}
function bdTiles(n, w, h, layout) {
  const g = 8; if (!n) return [];
  if (layout === "tabs") return [[0, 0, w, h]];
  if (layout === "rows") { const hh = (h - g * (n - 1)) / n; return [...Array(n)].map((_, i) => [0, i * (hh + g), w, hh]); }
  if (layout === "grid" || (layout === "auto" && n > 3)) {
    const c = Math.ceil(Math.sqrt(n)), r = Math.ceil(n / c), ch = (h - g * (r - 1)) / r;
    return [...Array(n)].map((_, i) => { const row = Math.floor(i / c), inRow = Math.min(c, n - row * c), cw = (w - g * (inRow - 1)) / inRow; return [(i - row * c) * (cw + g), row * (ch + g), cw, ch]; });
  }
  const cw = (w - g * (n - 1)) / n; return [...Array(n)].map((_, i) => [i * (cw + g), 0, cw, h]);
}
function bdPaint() {
  const st = $("#bd-stage"); if (!st) return;
  const panes = BD.panes; if (!panes.find(p => p.id === BD.focus)) BD.focus = (panes[0] || {}).id;
  const focus = BD.focus;
  $("#bd-tabs").innerHTML = panes.map(p => { const pr = bdProf(p.profile); return `<div class="bd-tab ${p.id === focus ? "on" : ""}" style="--c:${pr.color}" title="${esc(p.title)}\n${esc(p.url)}" onclick="bdFocus(${p.id})">
      ${p.loading ? `<span class="spin"></span>` : p.favicon ? `<img src="${esc(p.favicon)}" alt="">` : `<i></i>`}<span>${esc(p.title || "New tab")}</span>${p.audible ? "🔊" : ""}
      <button title="Close (Ctrl+W)" onclick="event.stopPropagation();desktop.browser.close(${p.id})">${ic("x")}</button></div>`; }).join("")
    + (panes.length ? `<button class="iconbtn" title="New tab (Ctrl+T)" onclick="bdNew((BD.panes.find(p=>p.id===BD.focus)||{}).profile||'personal')">${ic("plus")}</button>` : "");
  const W = st.clientWidth, H = st.clientHeight, shown = BD.layout === "tabs" ? panes.filter(p => p.id === focus) : panes;
  const tiles = bdTiles(shown.length, W, H, BD.layout), have = new Set();
  st.querySelector(".bd-empty") && panes.length && st.querySelector(".bd-empty").remove();
  shown.forEach((p, i) => {
    have.add(String(p.id));
    let el = st.querySelector(`.bd-pane[data-id="${p.id}"]`);
    if (!el) {
      el = document.createElement("div"); el.className = "bd-pane"; el.dataset.id = p.id;
      el.innerHTML = `<div class="bd-ph">
        <button class="iconbtn" data-a="back" title="Back (Alt+←)">${ic("left")}</button><button class="iconbtn" data-a="forward" title="Forward (Alt+→)">${ic("right")}</button>
        <button class="iconbtn" data-a="reload" title="Reload (Ctrl+R)">${ic("rep")}</button>
        <input class="bd-url" spellcheck="false" placeholder="Search or type a web address"><span class="bd-pbadge"></span>
        <button class="iconbtn" data-a="mute" title="Mute / unmute">🔈</button><button class="iconbtn" data-a="external" title="Open in your normal browser">${ic("ext")}</button>
        <button class="iconbtn" data-a="close" title="Close (Ctrl+W)">${ic("x")}</button></div><div class="bd-body"></div>`;
      el.querySelectorAll("[data-a]").forEach(b => b.onclick = () => b.dataset.a === "close" ? desktop.browser.close(p.id) : desktop.browser.nav(p.id, b.dataset.a));
      const u = el.querySelector(".bd-url");
      u.onkeydown = e => { if (e.key === "Enter") { const url = bdUrl(u.value); if (url) { desktop.browser.nav(p.id, "go", url); desktop.browser.nav(p.id, "focus"); } } if (e.key === "Escape") u.blur(); };
      u.onfocus = () => setTimeout(() => u.select(), 0);
      el.addEventListener("mousedown", () => { if (BD.focus !== p.id) { BD.focus = p.id; bdMarkFocus(); } });
      st.appendChild(el); paintIcons(el);
    }
    const [x, y, w, h] = tiles[i]; Object.assign(el.style, {left: x + "px", top: y + "px", width: w + "px", height: h + "px"});
    const pr = bdProf(p.profile), u = el.querySelector(".bd-url");
    if (document.activeElement !== u) u.value = p.url && !p.url.startsWith("about:") ? p.url : "";
    el.querySelector('[data-a="back"]').disabled = !p.canBack; el.querySelector('[data-a="forward"]').disabled = !p.canFwd;
    const m = el.querySelector('[data-a="mute"]'); m.textContent = p.muted ? "🔇" : "🔈"; m.style.display = p.audible || p.muted ? "" : "none";
    const b = el.querySelector(".bd-pbadge"); b.textContent = pr.name; b.style.setProperty("--c", pr.color);
    el.classList.toggle("loading", !!p.loading); el.classList.toggle("on", p.id === focus);
  });
  st.querySelectorAll(".bd-pane").forEach(el => { if (!have.has(el.dataset.id)) el.remove(); });
  if (!panes.length && !st.querySelector(".bd-empty")) st.innerHTML = `<div class="empty bd-empty"><b>Browse without leaving Daybook</b>Real web pages, right here. Each profile keeps its own logins — sign in once. Open several and they split the space evenly.
      <div class="row" style="justify-content:center;margin-top:14px;gap:8px">${webProfiles().map(p => `<button class="btn" onclick="bdNew('${p.id}')"><span class="bd-dot" style="background:${p.color}"></span>${esc(p.name)}</button>`).join("")}
      <button class="btn ghost" onclick="bdNew('personal','https://www.youtube.com')">YouTube</button><button class="btn ghost" onclick="bdNew('personal','https://mail.google.com')">Gmail</button></div></div>`;
  paintIcons($("#bd-tabs")); bdSync(true);
}
function bdMarkFocus() { $$(".bd-pane").forEach(e => e.classList.toggle("on", +e.dataset.id === BD.focus)); $$(".bd-tab").forEach(e => e.classList.toggle("on", e.getAttribute("onclick") === `bdFocus(${BD.focus})`)); }
function bdSync(force) {
  const st = $("#bd-stage");
  const overlay = $("#scrim").classList.contains("on") || $$(".menu.on").length > 0 || !!$(".dict.on");
  const visible = S.view === "browser" && !!st && !overlay;
  const rects = {};
  if (visible) $$(".bd-pane").forEach(el => { const r = el.querySelector(".bd-body").getBoundingClientRect(); rects[el.dataset.id] = {x: r.x, y: r.y, w: r.width, h: r.height}; });
  const key = JSON.stringify({visible, rects}); if (!force && key === BD.last) return; BD.last = key;
  desktop.browser.layout({visible, rects});
}
async function bdNew(profile, url) {
  if (S.view !== "browser") go("browser");
  const id = await desktop.browser.open(profile || "personal", url || "https://www.google.com"); BD.focus = id;
  if (!url) setTimeout(() => { const i = $(`.bd-pane[data-id="${id}"] .bd-url`); if (i) i.focus(); }, 300);
}
function bdFocus(id) { BD.focus = id; bdPaint(); desktop.browser.nav(id, "focus"); }
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
  m.innerHTML = `<div class="mh">Your Chrome profiles — opens in Chrome</div>` + LP.data.browsers.flatMap(b => b.profiles.map(p => `<div onclick="$$('.menu').forEach(x=>x.classList.remove('on'));lpBrowser('${b.id}',${JSON.stringify(p.id).replace(/"/g, "&quot;")})">${p.picture ? `<img class="bw-av" src="/browser-avatar/${b.id}/${encodeURIComponent(p.id)}">` : `<span class="bw-av" style="background:${p.color}">${esc(p.name[0])}</span>`}${esc(p.name)}<span class="kbd">${esc(b.name.replace("Google ", ""))}</span></div>`)).join("");
  $$(".menu").forEach(x => x.classList.remove("on")); m.classList.toggle("on", on); bdSync();
}
