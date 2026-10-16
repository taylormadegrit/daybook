# Daybook Application Architecture & Inventory Map

## 1. System Overview & Technology Stack

Daybook is an all-in-one local-first personal intelligence hub and desktop productivity operating environment.

### Tech Stack Components:
- **Desktop Host (Shell)**: Electron 37.10.3 (Chromium 138, Node 22.20.5), multi-profile `WebContentsView` dock workspace, native Windows ConPTY terminal integration via `@lydell/node-pty-win32-x64`, custom NSIS installer via `electron-builder`.
- **Backend Service (Python Daemon)**: Python 3.11 with Flask 3.1.3, SQLite 3 (WAL mode), `pywin32` (Windows Win32/DWM/UIAutomation APIs), `faster-whisper` (speech-to-text), `ctranslate2`, `pypdfium2`, `fpdf2`, `icoextract`, `pefile`.
- **Frontend Architecture**: Lightweight reactive DOM runtime without heavy framework overhead, CSS custom variables with glassmorphism design system, native Web Audio API, ResizeObservers, and WebSocket/SSE streaming.

---

## 2. Architecture Diagram

```mermaid
flowchart TD
    subgraph DesktopShell["Electron Desktop Host (desktop/main.js)"]
        Tray["System Tray & Watchdog"]
        WindowManager["BrowserWindow Manager"]
        Panes["WebContentsView Multi-Pane Engine"]
        ConPTY["Node-PTY Windows Terminal"]
        DownloadMgr["Central Chrome-like Download Manager"]
    end

    subgraph Renderer["Frontend UI Runtime (web/)"]
        ShellUI["index.html & UI Controller"]
        Views["Views: Today, Notes, Browser, Apps, Chat, Studio, Memos, Clock, Games, Library"]
        AppWrap["App Wrapper: Gemini, Claude, ChatGPT, LocalSend, Discord, Spotify"]
        WebPanes["WebPanes Workspace"]
    end

    subgraph BackendDaemon["Flask Backend Daemon (reminders/web.py :8503)"]
        CoreAPI["Core APIs (Reminders, Notes, Settings, Status)"]
        DB["SQLite Database Layer (db.py)"]
        AI["AI Integration (Claude Code, Ollama, Faster-Whisper STT, Studio TTS/Image)"]
        SystemBridge["Windows System Bridge (Dock, Window Embedding, App Scanner, Network)"]
        Integrations["Integrations (Discord, LocalSend, OBS, Zotero, Games)"]
    end

    DesktopShell <-->|IPC (preload.js)| Renderer
    Panes <-->|WebContentsView / Native Chromium| AppWrap
    Renderer <-->|HTTP / REST / SSE Streaming| BackendDaemon
    BackendDaemon <-->|File System & Win32 API| WindowsOS["Windows 10 / 11 OS"]
    BackendDaemon <-->|LAN Socket (Port 53317)| LocalSendApp["LocalSend LAN Hub"]
    BackendDaemon <-->|CLI Subprocess / API| LocalAI["Ollama & Claude Code CLI"]
```

---

## 3. Directory & File Inventory

### `desktop/` — Electron Desktop Host
| File | Size | Role & Purpose |
|------|------|----------------|
| `main.js` | 66.2 KB | Electron main process: window creation, WebContentsView layout, user-agent spoofing (Google OAuth Firefox UA bypass), CSP/X-Frame-Options stripping, ConPTY terminal IPC, tray, ad-blocking, download manager. |
| `preload.js` | 4.3 KB | Context bridge exposing `window.desktop` (clipboard, terminal, browser panes, window control, drag-and-drop). |
| `browser-preload.js` | 5.5 KB | Preload script injected into WebContentsView panes (find-in-page, full screen, navigation events). |
| `package.json` | 1.3 KB | Package metadata, build configurations, scripts (`npm run dist`). |

### `reminders/` — Python Backend Services
| Module | Role & Purpose |
|--------|----------------|
| `web.py` | Primary Flask application entry point, Blueprint registrations, static file routers, error handlers. |
| `db.py` | SQLite connection pooling, migrations, schema definition, CRUD operations for reminders, notes, tags. |
| `paths.py` | Central directory resolver (`DATA`, `TEMP`, `BACKGROUNDS`, `MEMOS`, `PDFS`). |
| `chat.py` | Multi-provider chat engine (Ollama, local models, Claude integration, streaming SSE tokens). |
| `claude_link.py` | Integration with Claude CLI (`claude.exe`), installation wizard, context sync. |
| `clock.py` | World clocks, recurring alarms, stopwatch, timers, sound assets. |
| `clock_ui.py` | System tray and alert window integration for clock alarms. |
| `categories.py` | Category hierarchy, tag rules, color assignments. |
| `desk.py` | Desktop sticky notes, screen annotations overlay. |
| `discord.py` | Discord webhook integration, clipboard-to-discord, media payload compression. |
| `dock.py` | Win32 window docking and embedding (`SetParent`, window positioning inside Daybook). |
| `folders.py` | Multi-pane file explorer, folder pinning, file preview thumbnails. |
| `games.py` | Steam, Epic, and emulator scanner (PCSX2, RPCS3, Cemu, RetroArch), game art scraper, launcher. |
| `launchpad.py` | Installed Windows application scanner, browser profile detector (Chrome, Edge, Brave). |
| `links.py` | Link bookmarks, URL metadata scraping, screenshot favicon fetcher. |
| `localsend.py` | LocalSend discovery (port 53317), LAN IP resolution, 1-click launch, Claude-to-Gemini exporter. |
| `memos.py` | Audio voice notes, video recordings, automated Whisper transcription pipeline. |
| `models_hub.py` | Local LLM manager (Ollama model pulling, hardware tier recommendations, quantization selector). |
| `network.py` | Wi-Fi network scanner, ping diagnostics, LAN device discovery. |
| `nlp.py` | Natural language date parser, task priority extraction, title summarization. |
| `notes.py` | Markdown notes storage, full-text search, auto-categorization, AI organization. |
| `obs.py` | OBS Studio WebSocket connection, recording/streaming triggers. |
| `orca.py` | Orca assistive technology and screen reader compatibility bridge. |
| `pdflib.py` | PDF document rendering, page extraction, PDFium2 text indexer. |
| `shortcuts.py` | Global Windows keyboard shortcut hooks (`RegisterHotKey`). |
| `stt.py` | Faster-Whisper offline transcription engine. |
| `studio.py` | AI Studio image generation and text-to-speech synthesis. |
| `templates.py` | Pre-built note and meeting templates. |
| `ui.py` | Windows notification toasts, alert dialogs, sound playback. |
| `updates.py` | GitHub release checker, 1-click self-updating engine, SSL-resilient downloaders. |
| `zotero.py` | Zotero reference manager local SQLite library reader and citation exporter. |

### `web/app/` — Client View Controllers
| Script | Role & Purpose |
|--------|----------------|
| `appwrap.js` | In-app App Wrapper: Native WebContentsView manager for Gemini, Claude, ChatGPT, LocalSend, Discord, Spotify. |
| `browser.js` | Daybook Browser workspace docking coordinator and layout synchronizer. |
| `webpanes.js` | Multi-tab Chromium web browser workspace with tab management and find-in-page. |
| `discord.js` | Discord modal dialogue, channel poster, and 1-click clipboard paste bridge. |
| `home.js` | Today view widgets, upcoming reminders, habits, daily quotes. |
| `notesx.js` | Rich markdown notes editor, tag manager, split-view organizer. |
| `terminal.js` | Full xterm.js-based terminal emulator connected to Windows ConPTY shell. |
| `voice.js` | Voice memo audio recorder, visualizer, playback speed controller. |
| `video.js` | Video note screen recorder and camera capture. |
| `clock.js` | Interactive world map clock, countdown timers, stopwatch, alarms. |
| `games.js` | Games gallery, emulator configurations, game launcher cards. |
| `files.js` | File explorer panes, drag-and-drop file operations. |
| `updates.js` | In-app software update banner, progress bar, 1-click update trigger. |
| `workflows.js` | 1-click multi-app workflow launcher (apps, files, urls, terminals). |

---

## 4. Complete Database Schema (SQLite `data/daybook.db`)

1. **`reminders`**: `id`, `text`, `due`, `recur`, `done`, `cat`, `priority`, `created_at`, `updated_at`
2. **`notes`**: `id`, `title`, `body`, `source`, `cat`, `tags`, `note_date`, `created_at`, `updated_at`
3. **`memos`**: `id`, `name`, `path`, `duration`, `transcript`, `created_at`
4. **`chats`**: `id`, `title`, `model`, `persona`, `created_at`, `updated_at`
5. **`chat_messages`**: `id`, `chat_id`, `role`, `content`, `created_at`
6. **`links`**: `id`, `url`, `title`, `notes`, `created_at`
7. **`stickies`**: `id`, `text`, `x`, `y`, `w`, `h`, `color`, `pinned`, `collapsed`
8. **`timers`**: `id`, `label`, `duration`, `remaining`, `state`, `ends_at`
9. **`alarms`**: `id`, `time`, `label`, `days`, `enabled`, `sound`
10. **`workflows`**: `id`, `name`, `icon`, `items` (JSON: apps, urls, files)
11. **`settings`**: Key-value key-value configuration store
12. **`categories`**: `id`, `name`, `color`, `icon`, `rules`
13. **`emulator_configs`**: `id`, `emulator_name`, `exe_path`, `roms_path`, `args`

---

## 5. Complete API Route Catalog (Flask)

| HTTP Method | Route | Module | Purpose |
|-------------|-------|--------|---------|
| `GET` | `/api/meta` | `web.py` | Application version, status, and system metadata |
| `GET`, `POST` | `/api/reminders` | `web.py` | List and create reminders |
| `PATCH`, `DELETE` | `/api/reminders/<id>` | `web.py` | Update or delete a reminder |
| `POST` | `/api/reminders/<id>/done` | `web.py` | Mark reminder complete / toggle |
| `POST` | `/api/reminders/<id>/snooze` | `web.py` | Snooze reminder by specified duration |
| `GET`, `POST` | `/api/notes` | `web.py` | Search, filter, and create notes |
| `GET`, `PATCH`, `DELETE` | `/api/notes/<id>` | `web.py` | Read note, edit text/tags, delete note |
| `POST` | `/api/notes/<id>/organize` | `notes.py` | AI-assisted note categorization and tagging |
| `GET` | `/api/settings` | `web.py` | Fetch all user settings |
| `PATCH` | `/api/settings` | `web.py` | Persist updated configuration keys |
| `GET` | `/api/status` | `web.py` | Diagnostics, service health, and counts |
| `GET`, `POST` | `/api/chats` | `chat.py` | List chat conversations or start new chat |
| `POST` | `/api/chats/<id>/send` | `chat.py` | Stream message prompt to LLM (SSE) |
| `GET` | `/api/localsend/status` | `localsend.py` | Detect LocalSend port 53317 & LAN IP |
| `POST` | `/api/localsend/launch` | `localsend.py` | 1-click launch LocalSend desktop app |
| `POST` | `/api/localsend/share` | `localsend.py` | Share note or audio file via LocalSend |
| `GET` | `/api/ai/claude-to-gemini` | `localsend.py` | Compile Claude prompt/persona for Gemini |
| `GET` | `/api/ai/stack-status` | `claude_link.py`| Check Node.js, Claude CLI, Ollama status |
| `POST` | `/api/ai/stack-install` | `claude_link.py`| 1-click background installer for Claude/Ollama |
| `GET` | `/api/updates/check` | `updates.py` | Query GitHub for new releases |
| `POST` | `/api/updates/apply` | `updates.py` | Download and launch NSIS update installer |
| `GET`, `POST` | `/api/discord` | `discord.py` | Get configured webhooks, add webhook |
| `POST` | `/api/discord/send` | `discord.py` | Send note/media via webhook or copy to clipboard |
| `GET` | `/api/games` | `games.py` | List installed PC and emulator games |
| `GET` | `/api/games/emulators` | `games.py` | Detect installed console emulators |
| `POST` | `/api/games/emulators/save` | `games.py` | Save custom emulator paths & ROM directories |
| `GET` | `/api/launchpad` | `launchpad.py` | List installed apps, browser profiles, pinned shortcuts |
| `GET`, `POST` | `/api/memos` | `memos.py` | Query voice recordings, save audio memo |
| `GET` | `/api/clock` | `clock.py` | Retrieve world clocks, alarms, active timers |
| `GET`, `POST` | `/api/links` | `links.py` | Bookmarks library management |
| `GET`, `POST` | `/api/folders` | `folders.py` | File explorer panes and directory bookmarks |
| `GET` | `/api/zotero` | `zotero.py` | Local Zotero library and citations reader |

---

## 6. IPC Interface Catalog (Electron Main <-> Renderer)

| Channel | Direction | Payload | Description |
|---------|-----------|---------|-------------|
| `browser:open` | Invoke | `{profile, url}` | Open WebContentsView pane with given profile |
| `browser:close`| Invoke | `id` | Destroy WebContentsView pane |
| `browser:list` | Invoke | - | Get list and state of all active panes |
| `browser:nav`  | Invoke | `{id, action, url}` | Navigate pane (go, back, forward, reload) |
| `browser:layout`| Send | `{visible, rects}` | Set screen coordinates for all panes |
| `browser:update`| Emit | `{panes}` | Broadcast pane title, URL, loading status |
| `term:create`  | Invoke | `{shell, cols, rows}` | Spawn ConPTY process |
| `term:input`   | Send | `{id, data}` | Send stdin to ConPTY terminal |
| `term:data`    | Emit | `{id, data}` | Stream stdout from terminal to xterm.js |
| `app:newWindow`| Invoke | `view` | Open secondary Daybook window |
| `app:settings` | Invoke | `settings` | Read or save desktop level preferences |
