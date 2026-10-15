// Daybook In-App Automatic Updater & 1-Click Update Client
let UP_STATE = null;
let UP_CHECKING = false;
let UP_UPDATING = false;

async function checkUpdates(manual = false) {
  if (UP_CHECKING || UP_UPDATING) return;
  UP_CHECKING = true;
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
        toast(`✨ Update available: ${data.remote?.short || "latest commit"}`);
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
  if (!UP_STATE || !UP_STATE.update_available) {
    host.style.display = "none";
    host.innerHTML = "";
    return;
  }

  const r = UP_STATE.remote || {};
  const msg = r.message || "New update available";
  const short = r.short || "";

  host.style.display = "block";
  host.innerHTML = `
    <div class="update-pill" onclick="openUpdateModal()" title="Click to view update details">
      <span class="update-pulse"></span>
      <span class="update-pill-badge">Update available</span>
      <span class="update-pill-msg" title="${esc(msg)}"><b>${esc(short)}</b>: ${esc(msg)}</span>
      <button class="btn xs pri update-now-btn" onclick="event.stopPropagation(); oneClickUpdate(this)">
        <svg class="i xs" viewBox="0 0 24 24"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>Update now
      </button>
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
            Version <b>${esc(s.current_version)}</b> · Commit <code>${esc(local.short || "HEAD")}</code>
            ${local.message ? ` — <i>"${esc(local.message)}"</i>` : ""}
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
  const behindCount = s.commits_behind || 1;
  const commits = s.commit_list || [];

  host.innerHTML = `
    <div class="update-status-box has-update">
      <div class="update-icon-circle alert">🚀</div>
      <div class="update-box-content">
        <div class="update-box-title">
          <span>New update available on GitHub!</span>
          <span class="badge warn">${behindCount} new commit${behindCount > 1 ? "s" : ""}</span>
        </div>
        <div class="update-box-sub">
          Latest commit <code>${esc(remote.short || "")}</code> by <b>${esc(remote.author || "Taylor")}</b>
          ${remote.date ? `(${new Date(remote.date).toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"})})` : ""}
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
          <span>Current: <code>${esc(local.short || "HEAD")}</code></span>
          <span>·</span>
          <span>Target: <code>${esc(remote.short || "")}</code></span>
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

  modal(`
    <h2>
      <svg class="i" viewBox="0 0 24 24"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
      Daybook Update Available
      <button class="iconbtn" onclick="closeModal()">${ic("x")}</button>
    </h2>
    <div style="margin-bottom:14px">
      <div style="font-size:15px;font-weight:600;margin-bottom:6px">
        ${esc(remote.message || "New update published to GitHub")}
      </div>
      <div class="muted small">
        Commit <code>${esc(remote.short || "")}</code> by <b>${esc(remote.author || "Taylor")}</b>
        ${remote.date ? `· ${new Date(remote.date).toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"})}` : ""}
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
      This pulls the latest changes from GitHub, updates dependencies, restarts the Daybook background service, and refreshes the desktop app seamlessly.
    </div>

    <div id="update-modal-progress" style="display:none;margin-bottom:14px">
      <div class="update-progress-bar"><div class="update-progress-fill"></div></div>
      <div class="update-progress-text" id="update-progress-msg">Updating Daybook…</div>
      <pre class="update-log-box" id="update-log-box" style="display:none"></pre>
    </div>

    <div class="mfoot" id="update-modal-footer">
      <a href="${esc(remote.html_url || s.repo_url)}" target="_blank" class="btn ghost">View on GitHub</a>
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

  if (prog) prog.style.display = "block";
  if (pmsg) pmsg.textContent = "Connecting to GitHub and pulling latest changes…";
  if (pbtn) { pbtn.disabled = true; pbtn.innerHTML = `<span class="spin">↻</span> Updating…`; }

  try {
    const res = await api("/api/updates/apply", {method: "POST"});

    if (!res.ok) {
      throw new Error(res.error || "Update failed");
    }

    if (res.mode === "installer") {
      if (pmsg) pmsg.textContent = "Downloaded installer: " + (res.tag || "");
      toast("Installer ready: " + res.name);
      if (res.download_url) window.open(res.download_url, "_blank");
      UP_UPDATING = false;
      return;
    }

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
    if (pmsg) pmsg.innerHTML = `<span style="color:var(--bad)">⚠ Update failed: ${esc(err.message)}</span>`;
    if (pbtn) { pbtn.disabled = false; pbtn.textContent = "Retry Update"; }
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
