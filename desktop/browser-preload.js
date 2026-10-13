// Runs in web pages shown in Daybook's browser panes. Exposes nothing to them.
// On YouTube (when the ad blocker is on) it removes video ads — general block lists can't, because YouTube serves
// ads from the same servers as the videos and decides inside the page when to play them.
const {ipcRenderer, contextBridge, webFrame} = require("electron");

function youtubeAdBlock() {
  // ---- 1. strip ad instructions from the player's data before YouTube reads it ----
  const AD_KEYS = ["adPlacements", "adSlots", "playerAds", "adBreakHeartbeatParams", "adBreakParams"];
  const prune = o => {
    if (!o || typeof o !== "object") return o;
    for (const k of AD_KEYS) if (k in o) delete o[k];
    if (o.playerResponse) prune(o.playerResponse);
    if (Array.isArray(o)) o.forEach(x => x && x.playerResponse && prune(x.playerResponse));
    return o;
  };
  const parse = JSON.parse;
  JSON.parse = function (text, reviver) {
    const v = parse.call(this, text, reviver);
    try { if (typeof text === "string" && text.length > 200 && /"(adPlacements|adSlots|playerAds)"/.test(text)) prune(v); } catch (e) {}
    return v;
  };
  const origJson = Response.prototype.json;
  Response.prototype.json = function () { return origJson.call(this).then(v => { try { prune(v); } catch (e) {} return v; }); };
  for (const name of ["ytInitialPlayerResponse", "playerResponse"]) {
    let val;
    try {
      Object.defineProperty(window, name, {configurable: true, get: () => val, set: v => { val = prune(v); }});
    } catch (e) {}
  }

  // ---- 2. anything that still plays: mute it, play it at 16x and press Skip.
  //      (Never seek an ad to its end: YouTube's newer player then freezes on the ad — that was the "won't play" bug.) ----
  const SKIP = ".ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-skip-button-container button, button[id^='skip-button']";
  let wasMuted = null;
  const tick = () => {
    const player = document.querySelector(".html5-video-player");
    const video = player && player.querySelector("video");
    const ad = player && (player.classList.contains("ad-showing") || player.classList.contains("ad-interrupting"));
    // mute through YouTube's own player so it doesn't remember "muted" for every later video
    const isMuted = () => player.isMuted ? player.isMuted() : video.muted;
    if (ad && video) {
      if (wasMuted === null) wasMuted = isMuted();
      if (player.mute) player.mute(); else video.muted = true;
      if (video.playbackRate < 16) video.playbackRate = 16;
      document.querySelectorAll(SKIP).forEach(b => b.click());
    } else if (video && wasMuted !== null) {
      if (!wasMuted) { if (player.unMute) player.unMute(); video.muted = false; }
      wasMuted = null;
      if (video.playbackRate > 2) video.playbackRate = 1;
    }
    // "Ad blockers are not allowed" pop-up: close it and keep playing
    const wall = document.querySelector("ytd-enforcement-message-view-model");
    if (wall) {
      const dlg = wall.closest("tp-yt-paper-dialog, ytd-popup-container > *"); (dlg || wall).remove();
      document.querySelectorAll("tp-yt-iron-overlay-backdrop").forEach(b => b.remove());
      if (video && video.paused) video.play().catch(() => {});
    }
  };
  setInterval(tick, 250);

  // ---- 3. hide banner, feed, search and side ads ----
  const css = `#masthead-ad, ytd-ad-slot-renderer, ytd-in-feed-ad-layout-renderer, ytd-promoted-sparkles-web-renderer, ytd-promoted-video-renderer,
    ytd-display-ad-renderer, ytd-banner-promo-renderer, ytd-statement-banner-renderer, ytd-player-legacy-desktop-watch-ads-renderer, #player-ads,
    .ytp-ad-overlay-container, .ytp-ad-overlay-slot, ytd-companion-slot-renderer, ytd-action-companion-ad-renderer, ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-ads"],
    ytd-rich-item-renderer:has(> #content > ytd-ad-slot-renderer), ytd-search-pyv-renderer, ytd-merch-shelf-renderer, ytm-promoted-sparkles-web-renderer,
    .ytd-mealbar-promo-renderer, ytd-mealbar-promo-renderer { display: none !important; }`;
  const addStyle = () => { if (document.getElementById("daybook-yt-ads") || !document.documentElement) return; const s = document.createElement("style"); s.id = "daybook-yt-ads"; s.textContent = css; (document.head || document.documentElement).appendChild(s); };
  // this runs before the page has a document; wait for it, then watch the player and keep the CSS in place
  const ready = () => {
    if (!document.documentElement) return setTimeout(ready, 15);
    addStyle();
    let queued = 0;  // at most once per frame — YouTube changes the page constantly while a video plays
    new MutationObserver(() => { if (!queued) queued = requestAnimationFrame(() => { queued = 0; tick(); addStyle(); }); }).observe(document.documentElement, {subtree: true, attributes: true, attributeFilter: ["class"], childList: true});
  };
  ready(); document.addEventListener("DOMContentLoaded", addStyle);
}

if (/(^|\.)youtube\.com$/.test(location.hostname) && window === window.top) {
  let on = true;
  try { on = ipcRenderer.sendSync("browser:adblock-on") !== false; } catch (e) {}
  if (on) {
    // must run in the page's own world, before YouTube's scripts
    try { contextBridge.executeInMainWorld({func: youtubeAdBlock}); }
    catch (e) { webFrame.executeJavaScript(`(${youtubeAdBlock.toString()})()`); }
  }
}
