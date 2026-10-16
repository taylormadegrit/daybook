# Daybook — context for AI coding agents (Gemini CLI, Claude Code, antigravity)

Read this first. It lets any agent pick up the project where the last one stopped, e.g. when Claude runs out
of usage and Gemini takes over (or the other way round). Keep the **Current state** section up to date.

## What it is
Daybook is a Windows desktop "local AI hub": reminders, notes, calendar, chat (Ollama / Claude Code / Gemini CLI),
terminal, in-app web apps (Gemini, Discord, LocalSend…), screen annotation, games. Repo: github.com/taylormadegrit/daybook
(**public** — it is the update channel). Every other personal repo stays **private**; never change repo visibility.

- Backend: Python 3.11 + Flask, `reminders/` package, served on http://127.0.0.1:8503 by `daemon.pyw`
  (packaged: `backend-dist/daybook-backend/daybook-backend.exe`, entry `backend_main.py`).
- UI: plain JS, no build step — `web/index.html` (core + 2 inline scripts) and `web/app/*.js`, `web/app/*.css`.
- Desktop shell: Electron in `desktop/` (`main.js`, `preload.js` → `window.desktop.*`; terminal = `@lydell/node-pty`).
- Data: `%LOCALAPPDATA%\Daybook` when installed, `./data` from source, or `DAYBOOK_DATA` if set. Not in git.

## Key files
| Area | Files |
|---|---|
| Chat (Ollama / `claude:` / `gemini:` models, Claude→Gemini fallback) | `reminders/chat.py`, chat UI in `web/index.html` (`enterChat`, `chatHero`, SSE reader) |
| AI stack detection / installers | `reminders/claude_link.py`, `install-ai-stack.ps1` |
| Terminal (Chat → Terminal) | `web/app/terminal.js`, `desktop/main.js` (`termProfiles`, `termCommand`, `term:*` IPC) |
| In-app web apps | `web/app/appwrap.js`, `web/app/webpanes.js`, native panes in `desktop/main.js` |
| Plain-English times | `reminders/nlp.py` (`parse`, `resolve_when`) |
| Annotation | `reminders/annotate.py` (Tk overlay, own process via `quickadd.pyw annotate`), `reminders/winlist.py` |
| Updates | `reminders/updates.py` (GitHub releases, `.exe` asset), `web/app/updates.js` |
| Architecture map | `APPLICATION_MAP.md` |

## Rules (learned the hard way)
1. **Never delete a function you didn't mean to.** v1.7.8 silently dropped `stickyDel` while editing nearby code.
   Before committing: `git diff` and check every removed `function`/`def` is really unused (`git grep -n name`).
2. **Run the tests against throwaway data** — the suite writes to the data folder:
   ```
   $env:DAYBOOK_DATA="$env:TEMP\daybook-test"; $env:PYTHONPATH="."; .\venv\Scripts\python.exe -m pytest TEST_SUITE -q
   ```
   Never weaken a test to make it pass. Add a regression test for each bug fixed.
3. **Syntax-check the UI** after editing JS: `node --check web/app/<file>.js`; for `web/index.html` extract the inline
   `<script>` blocks and `node --check` them. A single syntax error blanks the whole app.
4. UI code must work both inside Electron and in a plain browser (phone / LAN): guard `desktop.*` with
   `if (!window.desktop || !desktop.<api>) return;`.
5. Don't show status you haven't checked (e.g. "Ready" badges) — read it from `/api/ai/stack-status`.
6. Don't touch the user's running instance on :8503 for experiments; start a second server on another port with
   `DAYBOOK_DATA` pointing at a temp folder.
7. Ask before releasing, pushing, or changing anything on GitHub.

## Release (only when the user asks)
1. Bump the version in **all** of: `reminders/web.py` (`VERSION`), `reminders/updates.py` (`CURRENT_VERSION`),
   `desktop/package.json`, `desktop/package-lock.json` (top two `"version"` entries).
2. Tests green (rule 2).
3. `.\venv\Scripts\pyinstaller daybook-backend.spec --noconfirm --distpath backend-dist --workpath build`
   (new `reminders/*.py` modules must also be imported in `backend_main.py`).
4. `npm --prefix desktop run dist` → `desktop/dist/Daybook Setup X.Y.Z.exe`.
5. Commit, `git push origin master`, then
   `gh release create vX.Y.Z "desktop/dist/Daybook Setup X.Y.Z.exe" --target master --title "Daybook vX.Y.Z" --notes-file <notes.md>`.
   The in-app updater picks the first `.exe` asset of the latest release.

## Claude ↔ Gemini handoff
- In Daybook's Chat, a `claude:` model that hits a usage / credit limit automatically finishes the reply with Gemini
  (same conversation) and skips Claude for 15 minutes (`CLAUDE_COOLDOWN_S` in `reminders/chat.py`).
- For coding: open a terminal in this folder and run `gemini` (or Chat → Terminal → + → Gemini CLI). It reads this file.
  Sign Gemini in with **Login with Google** — a free API key only allows ~20 requests/day.
- When you stop, update **Current state** below so the next agent knows what's done and what's next.

## Current state
- **v1.8.1** released 2026-10-16: Connect Gemini CLI, Claude Code, and Antigravity (`agy`) to Daybook (`docs/PATCH-1.8.0-AI-CONNECT.md`).
  - [x] Root cause 1 Fix A (`backend_main.py`, test `TEST_SUITE/test_mcp_entry.py`), Fix B (installer passes `mcp`,
    removes the old entry first), Fix C (`daemon.pyw` writes to stderr before its silent exit)
  - [x] Root cause 2 Fix A for Claude (`MCP_TIMEOUT=90000` in the installer); Node minimum raised to 20;
    developer path removed from the installer's connector candidates
  - [x] Root cause 2 Fix B–D (`backend_main.py` lazy imports, `mcp_server.py` lightweight startup + HTTP forwarding to
    `/api/mcp/tool` on `:8503` + auto-start / friendly error when Daybook isn't running)
  - [x] Installer params (`-Only`, `-McpExe`, `-ToolsDir`, `-GeminiVersion`), pinned Gemini install into
    `$ToolsDir\gemini-cli`, `Register-GeminiMcp`, SHA-256 + ARM64 portable Node check, `Test-McpHandshake`, honest
    `$results` summary (`install-ai-stack.ps1`, tested in `TEST_SUITE/test_ai_connect.py`)
  - [x] `pickToolsDir()`, `termCommand()` stack flags, and packaged `daybook-backend.exe arcade` mode (`desktop/main.js`,
    `backend_main.py`, `web/app/terminal.js`)
  - [x] `/api/ai/stack-status` fields (`registered`, `args_ok`, `signed_in`, `trusted_home`, 10-min cached `mcp`
    handshake), Repair connection buttons, and Gemini home-folder trust checkbox (`reminders/claude_link.py`,
    `reminders/web.py`, `web/index.html`)
  - [x] Antigravity (`agy`) terminal & MCP support: `whichExe` in `desktop/main.js` checks `.exe`/`.cmd`/`.bat` before `""`
    and includes Antigravity bin dirs (`PATH` first, then `%LOCALAPPDATA%\agy\bin` etc.; no machine-specific paths); `agy` terminal profile + UI menu item
    (`desktop/main.js`, `web/app/terminal.js`); Daybook's PowerShell terminals pass `-ExecutionPolicy Bypass`;
    `Register-AgyMcp` (`agy mcp add daybook <McpExe> mcp` + merge into `~/.gemini/config/mcp_config.json` and
    `~/.gemini/antigravity/mcp_config.json` without BOM, `-Only agy`, `$results` summary in `install-ai-stack.ps1`);
    `agy` status / Connect / Repair / Disconnect in `reminders/claude_link.py`, `reminders/web.py`, and `web/index.html`
    (70 tests green in `TEST_SUITE`).
  - [ ] Clean-machine testing checklist (`docs/PATCH-1.8.0-AI-CONNECT.md`) on a fresh Windows PC / VM
  - This PC: Gemini's `daybook` entry is in `~/.gemini/settings.json` and Connected. Claude Code's `reminders`
    entry runs the dev `venv\Scripts\python.exe mcp_server.py` and is Connected — leave it alone.
  - Review (2026-10-16, Claude): 69 tests green; all 14 MCP tools verified end-to-end through `/api/mcp/tool` on a
    throwaway backend (initialize ~1 s). Fixed: installer handshake sent a stdin BOM (never answered); Settings
    trusted the home folder on first view (now only on Connect/Repair/checkbox); `opts.only` whitelisted in
    `termCommand`; packaged Arcade launched with `Start-Process -Wait` (daybook-backend.exe is windowed);
    stack-status handshake timeout 30 s. Untested until a build: the packaged Arcade console attach.
- **v1.8.0** released 2026-10-16: Claude→Gemini automatic fallback in Chat (+ `TEST_SUITE/test_gemini_fallback.py`), this file.
- v1.7.9 (2026-10-16) fixed regressions from v1.7.4–1.7.8 (sticky delete, AI-stack badge, window list, "at 9" times,
  plain-browser boot).
- Still to verify on the laptop: typing in a Claude Code terminal tab (launched via `cmd.exe /k` since v1.7.8) and the
  terminal bar showing in Chat after an update.
- Known, not fixed: `resolve_when("15")` (a lone number) resolves to a past date via the fallback parser.
