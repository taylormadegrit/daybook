// ================= DISCORD: send notes (.txt / .pdf), memos, recordings, images, any file =================
const DC = {hooks: null};
async function discordSend(kind, ref, fmt) {
  if (!DC.hooks) DC.hooks = (await api("/api/discord")).hooks;
  let info; try { info = await api("/api/discord/info", {method: "POST", body: {kind, ref, fmt: fmt || "txt"}}); } catch (e) { return toast(e.message); }
  const mb = info.size / 1048576, last = +store.get("daybook-dc-hook", "0");
  modal(`<h2>${ic("send", "i")}Send to Discord<button class="iconbtn" onclick="closeModal()">${ic("x")}</button></h2>
    ${kind === "note" ? `<div class="seg" style="margin-bottom:12px"><button class="${(fmt || "txt") === "txt" ? "on" : ""}" onclick="discordSend('note',${JSON.stringify(ref)},'txt')">As .txt</button><button class="${fmt === "pdf" ? "on" : ""}" onclick="discordSend('note',${JSON.stringify(ref)},'pdf')">As PDF</button></div>` : ""}
    ${info.warning ? `<div class="obs-card" style="border-color:var(--bad);margin-bottom:10px"><b style="color:var(--bad)">⚠ Heads up</b><p class="small" style="margin:4px 0 0">${esc(info.warning)}</p></div>` : ""}
    <div class="dc-file">${ic(info.media ? "rec" : "note", "i")}<div><b>${esc(info.name)}</b><span>${mb < 0.1 ? "<0.1" : mb.toFixed(1)} MB</span></div></div>
    ${DC.hooks.length ? `<div class="frm" style="margin-top:12px"><label>Channel</label><select class="f" id="dc-h">${DC.hooks.map(h => `<option value="${h.id}" ${h.id === last ? "selected" : ""}>${esc(h.name)}</option>`).join("")}</select>
      <label>Message</label><input class="f" id="dc-m" placeholder="optional"></div>
      <div class="muted small" style="margin-top:6px">${mb > 9.5 ? info.media ? "Bigger than the free 10 MB webhook limit — Daybook will compress it to fit if your server needs it." : "Over 10 MB: only servers with boosts accept this by webhook. If it fails, use the Discord app option." : "Sends straight into the channel."}</div>
      <div class="row" style="margin-top:14px"><button class="btn pri" id="dc-go" onclick="dcGo(${JSON.stringify(kind).replace(/"/g, "&quot;")},${JSON.stringify(ref).replace(/"/g, "&quot;")},'${fmt || "txt"}')">${ic("send")}Send</button>`
    : `<div class="obs-card" style="margin-top:12px"><b>Connect a Discord channel (one time)</b><p class="muted small">In Discord: channel ⚙ Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL. Then paste it in Settings → Discord.</p><button class="btn" onclick="closeModal();go('settings');setTimeout(()=>$('#discordset').scrollIntoView({behavior:'smooth'}),300)">Open Discord settings</button></div><div class="row" style="margin-top:14px">`}
      <button class="btn" ${info.nitro_ok ? "" : "disabled"} title="Copies the file and opens Discord — paste it (Ctrl+V) into any chat or DM. Uses your account's limit: 10 MB free, 500 MB with Nitro." onclick="dcGo(${JSON.stringify(kind).replace(/"/g, "&quot;")},${JSON.stringify(ref).replace(/"/g, "&quot;")},'${fmt || "txt"}','app')">${ic("copy")}Copy & open Discord app</button></div>
    <div class="muted small" style="margin-top:8px">“Copy & open Discord app” works for anything up to 500 MB with Nitro — paste with Ctrl+V into any chat or DM.</div>`);
}
async function dcGo(kind, ref, fmt, mode) {
  const b = $("#dc-go"); const hook = $("#dc-h") ? +$("#dc-h").value : 0; store.set("daybook-dc-hook", String(hook));
  if (b && mode !== "app") { b.disabled = true; b.innerHTML = ic("send") + "Sending…"; }
  try {
    const j = await api("/api/discord/send", {method: "POST", body: {kind, ref, fmt, hook, mode, message: ($("#dc-m") || {}).value || ""}});
    closeModal(); toast(j.result === "copied" ? "Copied — Discord is opening: paste with Ctrl+V" : j.result === "sent (compressed)" ? "Sent to Discord ✓ (compressed to fit)" : "Sent to Discord ✓");
  } catch (e) { toast(e.message); if (b) { b.disabled = false; b.innerHTML = ic("send") + "Send"; } }
}
async function renderDiscordSettings() {
  const host = $("#discordset"); if (!host) return;
  DC.hooks = (await api("/api/discord")).hooks;
  host.innerHTML = `<div class="muted small" style="margin-bottom:10px">Send notes (as .txt or PDF), voice memos, video notes, images and files to your channels. In Discord: channel ⚙ <b>Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL</b>, then paste it here. Links stay on this PC.</div>
    ${DC.hooks.map(h => `<div class="srow"><div class="d"><b># ${esc(h.name)}</b><span>connected</span></div><div class="row" style="gap:6px"><button class="btn sm" onclick="dcTest(${h.id})">Send test</button><button class="btn sm ghost danger" onclick="dcRemove(${h.id})">${ic("trash")}</button></div></div>`).join("")}
    <div class="row" style="flex-wrap:nowrap;margin-top:8px"><input class="f" id="dc-name" placeholder="Name, e.g. #notes" style="max-width:180px"><input class="f" id="dc-url" placeholder="https://discord.com/api/webhooks/…"><button class="btn pri" onclick="dcAdd()">${ic("plus")}Add channel</button></div>`;
}
async function dcAdd() {
  const hooks = [...DC.hooks.map(h => ({id: h.id, name: h.name})), {name: $("#dc-name").value || "Discord", url: $("#dc-url").value.trim()}];
  try { await api("/api/discord/hooks", {method: "POST", body: {hooks}}); toast("Channel added ✓ — press Send test"); renderDiscordSettings(); } catch (e) { toast(e.message); }
}
async function dcRemove(id) { const hooks = DC.hooks.filter(h => h.id !== id).map(h => ({id: h.id, name: h.name})); await api("/api/discord/hooks", {method: "POST", body: {hooks}}); renderDiscordSettings(); }
async function dcTest(id) { try { await api("/api/discord/test/" + id, {method: "POST"}); toast("Test message sent ✓"); } catch (e) { toast(e.message); } }
