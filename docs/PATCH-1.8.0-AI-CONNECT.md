# Daybook 1.8.0 patch plan: connect Gemini and Claude, fresh-machine AI stack

Daybook 1.7.9 installs Gemini CLI but never connects it to Daybook, and the Claude Code connection it does create is broken. Both trace to one missing word: daybook-mcp.exe must be started as `daybook-mcp.exe mcp`. This patch fixes that, connects Gemini, and makes the 1-Click AI Stack work on a machine with no Node.js or Python.

Verified on this PC (2026-10-16): adding `mcp` turned Gemini CLI 0.64.0 from "Disconnected" to "Connected", and the connector listed 14 tools. Everything else below comes from reading Daybook 1.7.9's main.js, install-ai-stack.ps1 and the Settings page. None of it has been tested on a clean machine yet.

## Problems

| # | Problem | Who it hits | Fix in section |
|---|---|---|---|
| 1 | daybook-mcp.exe with no argument starts the background service, which is already running, so it quits silently | Every Claude Code and Gemini user | Root cause 1 |
| 2 | The installer registers Claude as `claude mcp add reminders -- <exe>` with no `mcp` argument | Every Claude Code user | Root cause 1 |
| 3 | Nothing ever registers Daybook with Gemini CLI | Every Gemini user | In-app install flow, Config files |
| 4 | The connector takes 20+ seconds to start, close to client timeouts | Everyone, worse on laptops | Root cause 2 |
| 5 | Gemini turns off all connectors in folders the user hasn't trusted | Fresh Gemini users | Config files |
| 6 | The installer accepts Node 18, but Gemini CLI needs Node 20 or newer | Users with an old Node | Fresh-machine dependencies |
| 7 | GEMINI_CLI_VERSION is defined but never used, so installs aren't pinned | Everyone | In-app install flow |
| 8 | The final summary prints ✓ for every item even when a step failed | Fresh users | In-app install flow |
| 9 | /api/ai/stack-status reports Claude as connected: true without testing the connection, and has no Gemini connection field | Everyone | In-app install flow |
| 10 | The 8-Bit Arcade runs python, which a fresh machine doesn't have | Fresh users | Fresh-machine dependencies |

## Root cause 1: the connector needs the mcp argument

daybook-mcp.exe is a second copy of the packaged backend, not a separate program. Its entry script is backend_main.py, which picks a mode from the first argument. With no argument it runs daemon.pyw. The daemon sees Daybook already running on port 8503 and exits with code 0, printing nothing. To an AI client that looks like "connection closed".

Evidence:
- The docstring inside the exe reads: `daybook-backend.exe mcp — the MCP server Claude uses to reach Daybook.`
- daybook-mcp.exe with no argument: exits 0 straight away, nothing on stdout or stderr.
- `daybook-mcp.exe mcp`: answers initialize, and tools/list returns 14 tools: add_reminder, day_schedule, add_reminder_natural, list_reminders, complete_reminder, snooze_reminder, update_reminder, delete_reminder, search_notes, get_note, add_note, update_note, log_to_today, notes_overview.
- install-ai-stack.ps1 line 264: `& claude mcp add --scope user reminders -- "$mcpExe"`. No `mcp` argument, so every Claude Code install made by the 1-Click installer is broken.

**Fix A (required): default to MCP mode by exe name.** In backend_main.py, before the argument lookup:

```python
import sys, pathlib
# daybook-mcp.exe is only ever an MCP server: never fall through to the daemon
if pathlib.Path(sys.executable).stem.lower() == "daybook-mcp" and (len(sys.argv) < 2 or sys.argv[1] != "mcp"):
    sys.argv.insert(1, "mcp")
```

This repairs every existing install the moment the update lands, including configs that were already written without `mcp`.

**Fix B (required): pass the argument everywhere anyway.** Change installer line 264 to:

```powershell
& claude mcp remove --scope user reminders 2>$null
& claude mcp add --scope user reminders -- "$mcpExe" mcp
```

The remove first replaces the broken entry left by older versions.

**Fix C (recommended): never exit silently.** If the daemon finds another instance already running, write one line to stderr, such as `Daybook backend already running on :8503`, before it exits. AI clients show stderr in their logs, so the next problem like this takes a minute to find, not an hour.

## Root cause 2: the connector starts slowly

In the last session, `daybook-mcp.exe mcp` took more than 20 seconds to answer its first request on this laptop (15 GB RAM, no GPU). Gemini CLI's default connector timeout is close to that, and Claude Code's is in the same range. A slow start therefore looks the same as a broken one: "Disconnected" or "Connection closed".

The likely reason: daybook-mcp.exe is a full copy of the backend, so in mcp mode it loads everything the web server needs before it reads its first message. This hasn't been profiled yet. Run `python -X importtime backend_main.py mcp` in the dev venv to see which imports cost the most.

**Fix A (required): give the clients more time.** Every config Daybook writes must set a long timeout:
- Gemini CLI: `"timeout": 90000` (milliseconds) on the server entry. This is the value now working on this PC.
- Claude Code: set the user environment variable `MCP_TIMEOUT=90000` (milliseconds), which Claude Code reads when it starts connectors.

**Fix B (recommended): make mcp mode light.** In mcp mode, import only the MCP protocol code and an HTTP client. Each tool forwards its request to the backend that's already running on 127.0.0.1:8503, instead of opening the database and loading the whole service itself. That should bring startup down to a second or two, and it also stops two processes writing to the same database.

**Fix C (recommended): answer initialize first.** Read and answer the initialize request before any slow setup, then load the rest in the background. Clients mark the server as connected as soon as initialize comes back.

**Fix D: handle the backend not running.** If nothing answers on port 8503, start daybook-backend.exe and wait up to 30 seconds. If it still isn't up, return a clear tool error such as "Daybook isn't running. Open Daybook and try again." Don't exit.

## Fresh-machine dependencies

What a brand-new Windows user needs, and who should supply it:

| Component | Needed for | Fresh machine has it? | Who installs it |
|---|---|---|---|
| Daybook backend (Python) | Everything | No Python, but none needed | Already bundled with PyInstaller in resources\backend |
| daybook-mcp.exe | Claude and Gemini connector | Ships with Daybook | Already bundled |
| Node.js 20 or newer | Gemini CLI only | No | Daybook: portable zip, no admin rights |
| Gemini CLI | Gemini in the terminal | No | Daybook: npm into its own tools folder |
| Claude Code | Claude in the terminal | No | Daybook: Anthropic's native installer, no Node needed |
| Ollama | Local AI only | No | Optional. Daybook: winget or the official installer |
| Python | Only the 8-Bit Arcade | No | Nobody: remove the dependency (below) |

**Python: not needed.** The backend and connector are compiled exes. The only thing that calls python is the 8-Bit Arcade terminal profile, in the `arcade` case of termCommand() in main.js, which runs `python -u arcade.py`. On a fresh machine that opens the Microsoft Store page or prints "Python was not found". Fix: add an `arcade` mode to backend_main.py and launch `daybook-backend.exe arcade`, the same way quickadd already works. Until then, hide the Arcade profile when whichExe("python") returns nothing.

**Node.js: raise the minimum to 20.** install-ai-stack.ps1 accepts Node 18, but current Gemini CLI releases need Node 20 or newer, so a user with Node 18 gets an install that fails at runtime. Change the check:

```powershell
if ($major -ge 20) {
    Write-Success "Node.js $nodeVer is already installed."
    $nodeInstalled = $true
} else {
    Write-Warn "Node.js $nodeVer is too old (Gemini CLI needs 20 or newer). Installing a private copy for Daybook..."
}
```

If the user has an old Node, don't replace it: other programs may rely on it. Install Daybook's portable copy and put it first on the PATH that Daybook's terminal uses.

**Portable Node: check the download.** The installer already downloads node-v22.14.0-win-x64.zip without admin rights, which is the right approach. Add two things:
- Compare the zip's SHA-256 with the line for that file in https://nodejs.org/dist/v22.14.0/SHASUMS256.txt before extracting.
- Pick the ARM64 build when `$env:PROCESSOR_ARCHITECTURE -eq 'ARM64'`.

**Tools folder: don't assume D: is writable.** main.js sets TOOLS_DIR to D:\Applications whenever a D: drive exists. On many laptops D: is a recovery partition, card reader or DVD drive. Pick D: only if Daybook can create a folder there:

```js
function pickToolsDir() {
  const local = path.join(process.env.LOCALAPPDATA || app.getPath("userData"), "Daybook-tools");
  try { fs.mkdirSync("D:\\Applications", {recursive: true}); fs.accessSync("D:\\Applications", fs.constants.W_OK); return "D:\\Applications"; }
  catch { return local; }
}
const TOOLS_DIR = pickToolsDir();
```

Pass the same folder to the installer (`-ToolsDir`) so both sides agree.

**Remove the developer path.** The installer's first connector candidate is `D:\projects\local-reminders\daybook-mcp.exe`, a path from the developer's machine. On a user's PC it either doesn't exist or points at an old build. Pass the real path from main.js instead (`-McpExe`, see the next section).

**No winget is fine.** Some Windows installs don't have winget. The installer already falls back to direct downloads for Node and Ollama, so keep that order: winget first, then the direct download.

## In-app install flow (Chat and Settings)

Today there are three entry points, and all of them run the same script, install-ai-stack.ps1, in a Daybook terminal:
- Settings → 1-Click AI Stack → "Install / Verify Now" or "Launch 1-Click Installer"
- Settings → Claude Code & Desktop Integration → "1-Click Install Claude + Node"
- Chat → Terminal → Gemini CLI or Claude Code profile when the tool isn't found

Keep that design: one script, many buttons. It needs these changes.

### 1. Pass everything the script needs from main.js

Add parameters to the script and pass them from termCommand():

```powershell
param(
    [switch]$SkipModelPull,
    [string]$Model = "",
    [switch]$NonInteractive,
    [ValidateSet("all", "gemini", "claude", "ollama")]
    [string]$Only = "all",
    [string]$McpExe = "",
    [string]$ToolsDir = "$env:LOCALAPPDATA\Daybook-tools",
    [string]$GeminiVersion = "0.62.0"
)
```

```js
const mcpExe = path.join(process.resourcesPath, "backend", "daybook-mcp.exe");
const stack = only => inPs(`& powershell.exe -NoProfile -ExecutionPolicy Bypass -File ${q(AI_STACK_SCRIPT)} ` +
  `-Only ${only} -McpExe ${q(mcpExe)} -ToolsDir ${q(TOOLS_DIR)} -GeminiVersion ${GEMINI_CLI_VERSION}`);
// case "ai-stack": return stack("all");
// case "gemini":   return prof._gemini ? geminiCmd(prof) : stack("gemini");
// case "claude":   return prof._claude ? ["cmd.exe", ["/k", `"${prof._claude}"`]] : stack("claude");
```

This puts the unused GEMINI_CLI_VERSION constant to work, and the Gemini button no longer installs Ollama and a model the user didn't ask for. With `-Only gemini`, run Node, Gemini CLI and the Gemini connector steps only.

### 2. Install Gemini CLI into Daybook's tools folder, pinned

Replace the global `npm install -g @google/gemini-cli` with:

```powershell
$geminiDir = Join-Path $ToolsDir "gemini-cli"
New-Item -ItemType Directory -Force $geminiDir | Out-Null
& npm install -g --prefix "$geminiDir" "@google/gemini-cli@$GeminiVersion" --no-fund --no-audit
if ($LASTEXITCODE -ne 0) { Write-Err "npm couldn't install Gemini CLI (exit $LASTEXITCODE)."; $results.gemini = $false }
Add-To-UserPath $geminiDir
```

On Windows, `npm -g --prefix` puts gemini.cmd straight into that folder. whichExe() and the terminal's extraPaths already look in TOOLS_DIR\gemini-cli, so Daybook finds it with no other changes. It also avoids needing write access to %APPDATA%\npm.

### 3. Connect both tools to Daybook

After Gemini CLI installs, call Register-GeminiMcp (next section). After Claude Code installs, run:

```powershell
& claude mcp remove --scope user reminders 2>$null
& claude mcp add --scope user reminders -- "$McpExe" mcp
[Environment]::SetEnvironmentVariable("MCP_TIMEOUT", "90000", "User")
```

Run both connector steps even when the tool was already installed. That's what repairs existing users who got the broken entry.

### 4. Make the summary tell the truth

The summary at the end prints [✓] and "Daybook Link: Connected" no matter what happened. Track each step in `$results = @{}` and print from that:

```powershell
function Show-Result($label, $ok, $detail) {
    if ($ok) { Write-Host "  [OK]   $label $detail" -ForegroundColor Green }
    else     { Write-Host "  [FAIL] $label $detail" -ForegroundColor Red }
}
# ...one line per step...
if ($results.Values -contains $false) { exit 1 } else { exit 0 }
```

The title should only say "SETUP COMPLETE" when everything passed.

### 5. Test the connection, don't assume it

For "connected", run the same handshake the clients do. Start `daybook-mcp.exe mcp`, send initialize, wait up to 90 seconds for the reply, then stop the process. Use it in two places:
- At the end of the installer, for the "Daybook link" line.
- In /api/ai/stack-status, cached for 10 minutes. Today claude.connected is true without any test, and there's no Gemini field. Return:

```json
{
  "claude": {"installed": true, "version": "2.1.301", "registered": true, "args_ok": true},
  "gemini": {"installed": true, "version": "0.64.0", "registered": true, "args_ok": true, "signed_in": true},
  "mcp": {"handshake_ok": true, "startup_ms": 21400}
}
```

args_ok is false when an entry exists but doesn't pass `mcp`. When it is, Settings shows a Repair connection button that runs `-Only claude` or `-Only gemini`.

### 6. Sign-in is the last step, in the terminal

Neither tool works until the user signs in, and Daybook shouldn't handle passwords or keys itself. When the installer finishes, open the tool in the same terminal:
- Gemini: run `gemini`. On first run it asks the user to sign in with Google or use an API key. Show one line above it: "Choose 'Login with Google' for the free tier."
- Claude Code: run `claude`. It opens the browser to sign in.

After sign-in, the user can ask "what's on my schedule today?" to confirm the Daybook tools work.

## Config files Daybook must write

Always merge into existing files. Never overwrite them: users may have other connectors and settings.

### Gemini CLI: %USERPROFILE%\.gemini\settings.json

The entry Daybook needs, exactly as it now works on this PC:

```json
{
  "mcpServers": {
    "daybook": {
      "command": "C:\\Users\\<user>\\AppData\\Local\\Programs\\Daybook\\resources\\backend\\daybook-mcp.exe",
      "args": ["mcp"],
      "timeout": 90000
    }
  }
}
```

PowerShell to merge it in:

```powershell
function Register-GeminiMcp([string]$McpExe) {
    $dir  = Join-Path $env:USERPROFILE ".gemini"
    $file = Join-Path $dir "settings.json"
    New-Item -ItemType Directory -Force $dir | Out-Null
    $cfg = [pscustomobject]@{}
    if (Test-Path $file) {
        $raw = Get-Content $file -Raw
        if ($raw.Trim()) {
            try { $cfg = $raw | ConvertFrom-Json }
            catch { Write-Err "settings.json isn't plain JSON, so Daybook left it alone. Add the 'daybook' entry by hand."; return $false }
        }
        Copy-Item $file "$file.daybook-backup" -Force
    }
    if (-not $cfg.mcpServers) { $cfg | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force }
    $entry = [pscustomobject]@{ command = $McpExe; args = @("mcp"); timeout = 90000 }
    $cfg.mcpServers | Add-Member -NotePropertyName daybook -NotePropertyValue $entry -Force
    $json = $cfg | ConvertTo-Json -Depth 20
    # Windows PowerShell 5.1 adds a BOM with -Encoding utf8, so write UTF-8 without one
    [IO.File]::WriteAllText($file, $json, (New-Object Text.UTF8Encoding $false))
    return $true
}
```

Notes:
- Use the server name `daybook` for Gemini. Claude Code's existing installs use `reminders`; keep that name there so the repair replaces the old entry.
- ConvertTo-Json in PowerShell 5.1 turns a one-item array into a plain string unless the value is built with @(), as above. Check the written file has `"args": ["mcp"]`.
- If the user already has a daybook entry with different settings, the merge replaces it. That's intended.

### Gemini CLI: folder trust, %USERPROFILE%\.gemini\trustedFolders.json

Gemini CLI turns off all connectors in folders the user hasn't trusted. Daybook's terminal starts in the user's home folder, so that folder has to be trusted for the Daybook tools to load. This PC has:

```json
{
  "c:/users/taylor": "TRUST_PARENT"
}
```

Trusting a folder is a security choice, so don't do it silently. In Settings, show a checkbox that's ticked by default: "Let Gemini use Daybook tools when started from Daybook (trusts your home folder)". If it's ticked, merge `"<home folder, lowercase, forward slashes>": "TRUST_FOLDER"` into the file, using the same merge pattern as above. If not, Gemini shows its own trust prompt the first time and the user answers it there.

### Gemini CLI: sign-in

Don't write sign-in settings. Gemini asks on first run and saves the choice itself under `security.auth.selectedType`: `oauth-personal` for Google sign-in, or `gemini-api-key` for an API key. This PC uses `gemini-api-key`. For API-key users, Daybook can offer a field that saves the key as the user environment variable GEMINI_API_KEY. Never write the key into a file inside Daybook's install folder.

### Claude Code: %USERPROFILE%\.claude.json

Don't edit this file directly: it holds sign-in state and history. Use the commands in the previous section. Afterwards, `claude mcp get reminders` should show:

```
reminders:
  Scope: User config (available in all your projects)
  Status: ✓ Connected
  Type: stdio
  Command: C:\Users\<user>\AppData\Local\Programs\Daybook\resources\backend\daybook-mcp.exe
  Args: mcp
```

On this PC today it shows `Args:` empty and `✘ Failed to connect`: the broken entry from the current installer.

### Environment variables (user scope)

| Variable | Value | Why |
|---|---|---|
| Path | adds Node folder, TOOLS_DIR\gemini-cli, %USERPROFILE%\.local\bin | So node, gemini and claude work outside Daybook too |
| MCP_TIMEOUT | 90000 | Gives Claude Code time to start the connector |
| GEMINI_API_KEY | user's key | Only if the user chose API-key sign-in |

Terminals that were already open won't see new variables. Daybook's own terminal does, because term:create builds its PATH itself.

## Testing checklist on a clean Windows machine

Use Windows Sandbox (free on Windows 11 Pro; Home needs a VM such as Hyper-V or VirtualBox) or a spare PC. Start with a standard, non-admin user account and nothing installed but Daybook.

Before you start, confirm the machine is clean: `node -v`, `python --version`, `gemini --version` and `claude --version` should all fail, and %USERPROFILE%\.gemini shouldn't exist.

**Connector**
- [ ] daybook-mcp.exe with no argument stays open and answers MCP requests (Fix A in Root cause 1)
- [ ] `daybook-mcp.exe mcp` answers initialize, and tools/list returns all 14 tools
- [ ] Time to answer initialize, written down: ____ seconds (goal: under 5)
- [ ] With Daybook closed, a tool call returns "Daybook isn't running" instead of the connector exiting

**Gemini from Chat → Terminal → Gemini CLI**
- [ ] Installs Node and Gemini CLI only (no Ollama, no model download)
- [ ] Works with no admin prompt
- [ ] gemini.cmd lands in TOOLS_DIR\gemini-cli, and `gemini --version` shows the pinned version
- [ ] settings.json has the daybook entry with `"args": ["mcp"]` and no BOM
- [ ] Trust checkbox on: trustedFolders.json has the home folder. Off: Gemini asks itself
- [ ] Gemini opens and asks the user to sign in
- [ ] After sign-in, /mcp inside Gemini lists daybook as connected with 14 tools
- [ ] "Add a reminder to call Mum at 5pm" creates the reminder in Daybook

**Gemini from Settings**
- [ ] Same results from "Install / Verify Now"
- [ ] Running it a second time changes nothing and reports everything OK
- [ ] The status card shows Gemini installed, connected and signed in

**Claude Code**
- [ ] Installs without Node
- [ ] `claude mcp get reminders` shows `Args: mcp` and `✓ Connected`
- [ ] The repair works: add the old broken entry by hand (`claude mcp add --scope user reminders -- "<exe>"`), then click Repair connection, and it's fixed

**Failure cases**
- [ ] No internet: every step reports FAIL and the script exits 1. Nothing prints a ✓
- [ ] A D: drive that's read-only (insert a DVD or mount an ISO): tools go to %LOCALAPPDATA%\Daybook-tools
- [ ] Node 18 already installed: Daybook installs its own Node 22 and leaves Node 18 alone
- [ ] An existing settings.json with other servers keeps them after install
- [ ] A settings.json with comments in it is left untouched, with a clear message
- [ ] No winget: direct downloads still work
- [ ] 8-Bit Arcade either works without Python or is hidden

## Release notes and manual fix

### Release notes (for users)

**Daybook 1.8.0: Gemini and Claude now connect to Daybook**
- Gemini CLI connects to Daybook. Ask Gemini to add reminders, check your day or search your notes. Set it up from Settings → AI Stack, or open Gemini from the Chat terminal.
- Fixed: Claude Code couldn't reach Daybook. If Claude showed Daybook as "Failed to connect", this update fixes it automatically.
- Nothing to install first. Daybook sets up everything Gemini needs, without admin rights. You don't need Node.js or Python.
- Honest setup results. The installer now tells you exactly which steps worked, and Settings has a Repair button if a connection breaks.
- Faster connection. Gemini and Claude connect to Daybook more quickly.

Only ship the last bullet if Fix B or C from Root cause 2 is in the release.

### Manual fix for existing installs (until the update ships)

For anyone on Daybook 1.7.9 right now. Open PowerShell and run:

Claude Code:

```powershell
$exe = "$env:LOCALAPPDATA\Programs\Daybook\resources\backend\daybook-mcp.exe"
claude mcp remove --scope user reminders
claude mcp add --scope user reminders -- "$exe" mcp
[Environment]::SetEnvironmentVariable("MCP_TIMEOUT", "90000", "User")
```

Then close and reopen Claude Code and run `claude mcp get reminders`. It should say Connected.

Gemini CLI: open %USERPROFILE%\.gemini\settings.json in Notepad and add this inside the outer { }. If the file already has a "mcpServers" section, add only the "daybook" part inside it. Replace <user> with your Windows user name.

```json
"mcpServers": {
  "daybook": {
    "command": "C:\\Users\\<user>\\AppData\\Local\\Programs\\Daybook\\resources\\backend\\daybook-mcp.exe",
    "args": ["mcp"],
    "timeout": 90000
  }
}
```

Then run `gemini mcp list`. It should show daybook as connected. If it says the folder isn't trusted, start Gemini, accept its trust prompt for your home folder, and check again.

## Status on this PC (2026-10-16)

- Gemini CLI: fixed. Connected, 14 tools.
- Claude Code: still broken. The reminders entry has no `mcp` argument (`claude mcp get reminders` shows `✘ Failed to connect`). The Claude Code commands above fix it.
