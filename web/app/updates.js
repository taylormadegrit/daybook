// Daybook In-App Automatic Updater & 1-Click Update Client
let UP_STATE = null;
let UP_CHECKING = false;
let UP_UPDATING = false;
let UP_DISMISSED = false;
try {
  if (sessionStorage.getItem("daybook_up_dismissed")) UP_DISMISSED = true;
} catch (_) {}

function dismissUpdatePill(e) {
  if (e) {
    if (typeof e.stopPropagation === "function") e.stopPropagation();
    if (typeof e.preventDefault === "function") e.preventDefault();
  }
  UP_DISMISSED = true;
  try {
    sessionStorage.setItem("daybook_up_dismissed", String(Date.now()));
  } catch (_) {}
  const host = $("#updatepill");
  if (host) {
    host.style.display = "none";
    host.innerHTML = "";
  }
}
window.dismissUpdatePill = dismissUpdatePill;

async function checkUpdates(manual = false) {
  if (UP_CHECKING || UP_UPDATING) return;
  UP_CHECKING = true;
  if (manual) {
    UP_DISMISSED = false;
    try { sessionStorage.removeItem("daybook_up_dismissed"); } catch (_) {}
  }
  const btn = $("#btn-check-updates");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spin">↻</span> Checking…`;
  }
  if (manual) toast("Checking GitHub for Daybook updates…");

  try {
    const data = await api(`/api/updates/check?force=${manual ? "1" : "0"}`);
    UP_STATE = data;
    renderUpdatePill();
    renderUpdatesSettings();
    if (manual) {
      if (data.update_available) {
        const title = data.remote?.tag_name || data.remote?.short || "latest update";
        toast(`✨ Update available: ${title}`);
      } else if (data.ok) {
        toast("✓ Daybook is up to date!");
      } else if (data.error) {
        toast("⚠ Note: " + data.error);
      }
    }
  } catch (err) {
    console.error("Update check failed:", err);
    if (manual) toast("⚠ Failed to check updates: " + err.message);
  } finally {
    UP_CHECKING = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Check for updates";
    }
  }
}

function renderUpdatePill() {
  const host = $("#updatepill");
  if (!host) return;
  if (!UP_STATE || !UP_STATE.update_available || UP_DISMISSED) {
    host.style.display = "none";
    host.innerHTML = "";
    return;
  }

  const r = UP_STATE.remote || {};
  const isRelease = UP_STATE.update_type === "release" || !UP_STATE.is_repo;
  const tag = r.tag_name || r.short || (isRelease ? "v" + (r.version || "") : "");
  const msg = r.message || (isRelease ? `Daybook ${tag} is available` : "New update available");

  host.style.display = "block";
  host.innerHTML = `
    <div class="update-pill" onclick="openUpdateModal()" title="Click to view update details">
      <span class="update-pulse"></span>
      <span class="update-pill-badge">${isRelease ? "New Release" : "Update available"}</span>
      <span class="update-pill-msg" title="${esc(msg)}"><b>${esc(tag)}</b>: ${esc(msg)}</span>
      <button class="btn xs pri update-now-btn" onclick="event.stopPropagation(); oneClickUpdate(this)">
        <svg class="i xs" viewBox="0 0 24 24"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>Update now
      </button>
      <button class="update-pill-close" onclick="dismissUpdatePill(event)" title="Dismiss update notification" aria-label="Dismiss">✕</button>
    </div>
  `;
}

function renderUpdatesSettings() {
  const host = $("#updateset");
  if (!host) return;

  if (!UP_STATE) {
    host.innerHTML = `<div class="muted small" style="padding:10px 0">Checking update status…</div>`;
    return;
  }

  const s = UP_STATE;
  const local = s.local || {};
  const remote = s.remote || {};

  if (!s.update_available) {
    host.innerHTML = `
      <div class="update-status-box up-to-date">
        <div class="update-icon-circle ok">✓</div>
        <div class="update-box-content">
          <div class="update-box-title">Daybook is up to date</div>
          <div class="update-box-sub">
            Version <b>${esc(s.current_version)}</b>
            ${s.is_repo ? ` · Commit <code>${esc(local.short || "HEAD")}</code>${local.message ? ` — <i>"${esc(local.message)}"</i>` : ""}` : " · Packaged Windows App"}
          </div>
          <div class="update-box-meta">
            <span>Repository: <a href="${esc(s.repo_url)}" target="_blank" class="link">${esc(s.repo_url)}</a></span>
            <span>·</span>
            <span>Last checked: ${new Date(s.checked_at).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})}</span>
          </div>
        </div>
        <div class="update-box-actions">
          <button class="btn sm" id="btn-check-updates" onclick="checkUpdates(true)">Check for updates</button>
        </div>
      </div>
    `;
    return;
  }

  // Update is available!
  const isRelease = s.update_type === "release" || !s.is_repo;
  const behindCount = s.commits_behind || 1;
  const commits = s.commit_list || [];
  const versionTitle = remote.tag_name ? `Daybook ${remote.tag_name} is ready` : "New update available on GitHub!";

  host.innerHTML = `
    <div class="update-status-box has-update">
      <div class="update-icon-circle alert">🚀</div>
      <div class="update-box-content">
        <div class="update-box-title">
          <span>${esc(versionTitle)}</span>
          <span class="badge warn">${isRelease ? "New Release" : `${behindCount} new commit${behindCount > 1 ? "s" : ""}`}</span>
        </div>
        <div class="update-box-sub">
          ${isRelease
            ? (remote.date ? `Published ${new Date(remote.date).toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"})}` : "Latest official Windows release")
            : `Latest commit <code>${esc(remote.short || "")}</code> by <b>${esc(remote.author || "Taylor")}</b> ${remote.date ? `(${new Date(remote.date).toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"})})` : ""}`
          }
        </div>
        <div class="update-latest-msg">
          <b>${esc(remote.message || "")}</b>
        </div>
        ${commits.length > 1 ? `
          <div class="update-commits-preview">
            <div class="update-commits-h">Commits included in this update:</div>
            <ul class="update-commits-ul">
              ${commits.map(c => `
                <li><code>${esc(c.sha)}</code> <span>${esc(c.message)}</span> <small class="muted">(${esc(c.author)})</small></li>
              `).join("")}
            </ul>
          </div>
        ` : ""}
        <div class="update-box-meta">
          <span>Current: <b>${esc(s.current_version)}</b> ${s.is_repo ? `(<code>${esc(local.short || "HEAD")}</code>)` : ""}</span>
          <span>·</span>
          <span>Target: <b>${esc(remote.version || remote.tag_name || remote.short || "")}</b></span>
        </div>
      </div>
      <div class="update-box-actions">
        <button class="btn pri update-big-btn" onclick="oneClickUpdate(this)">
          <svg class="i sm" viewBox="0 0 24 24"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>Update Now (1-Click)
        </button>
        <button class="btn sm" onclick="checkUpdates(true)">Refresh</button>
        <a href="${esc(remote.html_url || s.repo_url)}" target="_blank" class="btn sm ghost">View on GitHub</a>
      </div>
    </div>
  `;
}

function openUpdateModal() {
  if (!UP_STATE || !UP_STATE.update_available) {
    checkUpdates(true);
    return;
  }

  const s = UP_STATE;
  const remote = s.remote || {};
  const local = s.local || {};
  const commits = s.commit_list || [];
  const isRelease = s.update_type === "release" || !s.is_repo;
  const title = remote.tag_name ? `Daybook ${remote.tag_name}` : "Daybook Update Available";

  modal(`
    <h2>
      <svg class="i" viewBox="0 0 24 24"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
      ${esc(title)}
      <button class="iconbtn" onclick="closeModal()">${ic("x")}</button>
    </h2>
    <div style="margin-bottom:14px">
      <div style="font-size:15px;font-weight:600;margin-bottom:6px">
        ${esc(remote.message || "New update published to GitHub")}
      </div>
      <div class="muted small">
        ${isRelease
          ? `Version <b>${esc(remote.version || remote.tag_name || "")}</b> · Published ${remote.date ? new Date(remote.date).toLocaleDateString([], {month: "short", day: "numeric", year: "numeric"}) : "recently"}`
          : `Commit <code>${esc(remote.short || "")}</code> by <b>${esc(remote.author || "Taylor")}</b> ${remote.date ? `· ${new Date(remote.date).toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"})}` : ""}`
        }
      </div>
    </div>

    ${commits.length > 1 ? `
      <div class="update-commits-preview" style="max-height:180px;overflow-y:auto;margin-bottom:16px">
        <div class="update-commits-h">Changes in this update:</div>
        <ul class="update-commits-ul">
          ${commits.map(c => `
            <li><code>${esc(c.sha)}</code> <span>${esc(c.message)}</span> <small class="muted">(${esc(c.author)})</small></li>
          `).join("")}
        </ul>
      </div>
    ` : ""}

    <div class="tip" style="margin-bottom:16px">
      <b>⚡ 1-Click Update</b>
      ${isRelease
        ? "Daybook will automatically download the updated installer in the background and launch it for you. Your data, settings, notes, and reminders are fully preserved."
        : "This pulls the latest changes from GitHub, updates dependencies, restarts the Daybook background service, and refreshes the desktop app seamlessly."
      }
    </div>

    <div id="update-modal-progress" style="display:none;margin-bottom:14px">
      <div class="update-progress-bar"><div class="update-progress-fill" style="width:0%"></div></div>
      <div class="update-progress-text" id="update-progress-msg">Starting update…</div>
      <pre class="update-log-box" id="update-log-box" style="display:none"></pre>
    </div>

    <div class="mfoot" id="update-modal-footer">
      <a href="${esc(remote.html_url || s.repo_url)}" target="_blank" class="btn ghost">View on GitHub</a>
      ${remote.download_url ? `<a href="${esc(remote.download_url)}" target="_blank" class="btn ghost">Direct Link</a>` : ""}
      <div class="sp"></div>
      <button class="btn ghost" onclick="closeModal()">Later</button>
      <button class="btn pri" id="modal-update-btn" onclick="oneClickUpdate(this)">
        <svg class="i sm" viewBox="0 0 24 24"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
        Update Now (1-Click)
      </button>
    </div>
  `, true);
}

async function oneClickUpdate(btn) {
  if (UP_UPDATING) return;
  UP_UPDATING = true;

  if (!$("#update-modal-progress")) {
    openUpdateModal();
  }

  const prog = $("#update-modal-progress");
  const pmsg = $("#update-progress-msg");
  const plog = $("#update-log-box");
  const foot = $("#update-modal-footer");
  const pbtn = $("#modal-update-btn");
  const fill = $(".update-progress-fill");

  if (prog) prog.style.display = "block";
  if (pmsg) pmsg.textContent = "Connecting to GitHub...";
  if (fill) { fill.style.width = "10%"; }
  if (pbtn) { pbtn.disabled = true; pbtn.innerHTML = `<span class="spin">↻</span> Updating…`; }

  try {
    const res = await api("/api/updates/apply", {method: "POST"});

    if (!res.ok) {
      throw new Error(res.error || "Update failed");
    }

    if (res.mode === "installer_downloading") {
      if (pmsg) pmsg.textContent = res.message || "Downloading installer in background...";

      await new Promise((resolve, reject) => {
        const interval = setInterval(async () => {
          try {
            const pData = await api("/api/updates/progress");
            const job = pData.job || {};
            if (pmsg && job.msg) pmsg.textContent = job.msg;
            if (fill && typeof job.pct === "number") {
              fill.style.width = Math.max(10, job.pct) + "%";
            }
            if (job.state === "launching" || job.state === "done") {
              clearInterval(interval);
              if (fill) fill.style.width = "100%";
              if (pmsg) {
                pmsg.innerHTML = `
                  <div style="color:var(--good);font-weight:600;margin-bottom:6px">✓ ${esc(job.msg || "Installer launched!")}</div>
                  <div class="small muted">The installer has been launched on your PC. If Windows SmartScreen appears, click "More info" → "Run anyway" to complete the update.</div>
                `;
              }
              if (foot) {
                foot.innerHTML = `
                  ${res.download_url ? `<a href="${esc(res.download_url)}" target="_blank" class="btn ghost">Direct .exe Link</a>` : ""}
                  <div class="sp"></div>
                  <button class="btn pri" onclick="closeModal()">Close</button>
                `;
              }
              toast("✓ Daybook installer ready and launched!");
              UP_UPDATING = false;
              resolve();
            } else if (job.state === "error") {
              clearInterval(interval);
              reject(new Error(job.error || "Download failed"));
            }
          } catch (err) {
            clearInterval(interval);
            reject(err);
          }
        }, 600);
      });
      return;
    }

    if (res.mode === "installer") {
      if (pmsg) pmsg.textContent = "Installer ready: " + (res.tag || "");
      toast("Installer ready: " + res.name);
      if (res.download_url) window.open(res.download_url, "_blank");
      UP_UPDATING = false;
      return;
    }

    // Git pull mode
    if (fill) fill.style.width = "80%";
    if (pmsg) pmsg.textContent = "Changes pulled successfully! Restarting service…";
    if (plog && res.output) {
      plog.style.display = "block";
      plog.textContent = res.output;
    }

    try {
      await api("/api/updates/restart", {method: "POST"});
    } catch (e) {
      console.warn("Service restart signaled:", e);
    }

    if (fill) fill.style.width = "100%";
    if (pmsg) pmsg.textContent = "✓ Update complete! Refreshing application…";
    toast("✓ Daybook updated to " + (res.commit?.short || "latest") + "! Refreshing…");

    setTimeout(() => {
      try {
        if (window.desktop && typeof window.desktop.reload === "function") {
          window.desktop.reload();
        } else {
          window.location.reload();
        }
      } catch (e) {
        window.location.reload();
      }
    }, 1800);

  } catch (err) {
    console.error("1-Click Update error:", err);
    UP_UPDATING = false;
    if (fill) fill.style.width = "0%";
    if (pmsg) pmsg.innerHTML = `
      <div style="color:var(--bad);font-weight:600;margin-bottom:6px">⚠ Update failed: ${esc(err.message)}</div>
      <div class="small muted">You can manually download the latest installer from GitHub Releases below.</div>
    `;
    if (foot) {
      foot.innerHTML = `
        <a href="https://github.com/taylormadegrit/daybook/releases/latest" target="_blank" class="btn ghost">Open GitHub Releases</a>
        <div class="sp"></div>
        <button class="btn" onclick="closeModal()">Close</button>
        <button class="btn pri" id="modal-update-btn" onclick="oneClickUpdate(this)">Retry Update</button>
      `;
    }
    toast("⚠ Update error: " + err.message);
  }
}

// Automatic check on start & periodic polling
if (typeof window !== "undefined") {
  setTimeout(() => checkUpdates(false), 2500);
  setInterval(() => checkUpdates(false), 15 * 60 * 1000);
  window.addEventListener("focus", () => {
    if (UP_STATE && Date.now() - (UP_STATE.checked_at ? new Date(UP_STATE.checked_at).getTime() : 0) > 5 * 60 * 1000) {
      checkUpdates(false);
    }
  });
}
