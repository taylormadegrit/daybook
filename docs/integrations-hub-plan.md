# Integrations Hub — plan (not built yet)

One tab that lists every app Daybook works with, shows whether each is installed and connected, installs the
missing ones with one click, and tells people what their PC can run (Basic / Intermediate / Power).

## Goals

- **One place** for everything Daybook connects to, instead of settings spread across pages.
- **Honest status** per app: *Not installed → Installed → Connected → Working* (with the reason when it isn't).
- **One-click install** through `winget`, always with an explicit confirm that shows the name, publisher, source and size.
- **"What can my PC do?"** — a hardware check that maps the machine to Basic / Intermediate / Power and only
  suggests things that will run well on it.
- **Nothing secret in plain text**: tokens and API keys go to Windows Credential Manager (DPAPI), never to the settings table.

## Where it lives

- New sidebar page **Integrations** (Alt+J), also linked from Settings and the tour's last step.
- Backend: `reminders/integrations.py` — a registry of integrations + `/api/integrations` (status for all),
  `/api/integrations/<id>/install`, `/connect`, `/test`, `/disconnect`.
- Frontend: `web/app/integrations.js` — grid of cards, filters (Installed · Available · Needs attention), detail drawer.
- Reuses what exists: `models_hub.scan()` (CPU/GPU/RAM), `launchpad.scan_apps()` (installed apps), `discord.py`,
  `obs.py`, `zotero.py`, `chat.claude_cli()`, the ad blocker and browser profiles.

## The registry (one entry per integration)

```python
{"id": "localsend", "name": "LocalSend", "category": "Sharing", "winget": "LocalSend.LocalSend",
 "detect": {"exe": ["LocalSend.exe"], "port": 53317},          # how we know it's installed / running
 "connect": "none",                                            # none | token | webhook | oauth | local-api
 "tier": "basic", "disk_mb": 60, "needs_internet": False,
 "what": "Send files and notes to your phone over Wi-Fi — no cloud.",
 "daybook_uses": ["Files hub: Send to phone", "Notes: send as .txt", "Voice memos: send to phone"]}
```

## Integrations

| App | What Daybook does with it | Install (`winget`) | Connect | Tier | Disk |
|---|---|---|---|---|---|
| **LocalSend** *(new)* | Send files, notes and memos to your phone over Wi‑Fi; receive phone recordings straight into Voice memos | `LocalSend.LocalSend` | none (local network, REST API v2 on port 53317) | Basic | ~60 MB |
| **Discord** | Send notes (.txt/PDF), memos and recordings < 500 MB to a channel | `Discord.Discord` | webhook URL per channel (stored in Credential Manager) | Basic | ~400 MB |
| **OBS Studio** | Video notes: record/stop from Daybook, recordings land in Voice memos | `OBSProject.OBSStudio` | local websocket (port 4455) — only after the user turns it on in OBS | Basic → Power* | ~500 MB |
| **Whop** *(new)* | Dashboard card: members, revenue, recent sales; reminders for renewals/payouts | — (web service) | API key (Credential Manager), read-only scopes | Basic | — |
| **Ollama** | Local AI: chat, Organize notes, plain-English reminders, categories | `Ollama.Ollama` | local API (port 11434), auto-started | Intermediate | 1–1.5 GB + models |
| **Claude Code** | Claude in Chat; fallback for Organize when Ollama is off; MCP tools | installer from claude.ai (not on winget) | sign-in in Claude Code itself | Basic | ~250 MB |
| **Zotero** | Library → Zotero sources, citations, add by DOI/ISBN | `DigitalScholar.Zotero` | local API (port 23119) — user enables it in Zotero | Basic | ~250 MB |
| **Steam** / **Epic Games** | Games library, play, offline notes | `Valve.Steam`, `EpicGames.EpicGamesLauncher` | their own sign-in | Basic | 0.5–1 GB |
| **Google Chrome** | Your signed-in Chrome profiles inside Daybook | `Google.Chrome` | none | Basic | ~400 MB |
| **AI Studio models** | Images (SDXL‑Turbo), voice (XTTS) | downloaded by Daybook, not winget | none | Power | 6.5 GB + ~1.8 GB |
| **Orca** | Start coding projects from chat | existing installer | none | Intermediate | — |

\* OBS itself runs anywhere; recording 1440p/60 while editing needs Power.

### New integrations in detail

- **LocalSend** — implement the LocalSend REST protocol v2: discover devices on the LAN (multicast
  announce on 224.0.0.167:53317 + HTTP fallback scan), `prepare-upload` → `upload` for files. Receiving: run a
  small receiver only while the Integrations page or Voice memos is open, auto-accept only from devices the user
  has paired once. Right-click → *Send to phone* in Files, Notes, Voice memos.
- **Whop** — read-only first: `GET /me`, memberships, payments (paged). Cache locally, refresh every 15 min
  while online, show "last updated" when offline. Never store raw responses with customer emails in notes.

## Installing

1. Card shows **Install** → confirm dialog: *"Install LocalSend 1.x from the winget community source (publisher:
   LocalSend, ~60 MB)?"* — nothing installs without this click.
2. Run `winget install --id <ID> --exact --silent --accept-package-agreements` **only after** the user ticked
   "I accept the publisher's license" in that dialog (Daybook must not accept agreements silently).
3. Stream progress to the card; on success re-run detection; on failure show winget's message and a link to the
   publisher's download page.
4. Uninstall stays in Windows Settings (Daybook only opens that page).

## Hardware & storage tiers

Detected with `models_hub.scan()` (CPU threads, RAM, every GPU + VRAM, free disk on the data drive).

| | **Basic** | **Intermediate** | **Power** |
|---|---|---|---|
| CPU | 4 cores / 8 threads | 6–8 cores | 8+ cores |
| RAM | 8 GB | 16 GB | 32 GB+ |
| GPU | integrated is fine | NVIDIA/AMD with 6–8 GB VRAM | 12 GB+ VRAM (RTX 3060 12 GB, 4070+) |
| Free disk | 5 GB | 25 GB | 60 GB+ (SSD) |
| Runs well | Notes, reminders, calendar, browser + ad blocker, Files hub, workflows, Discord, LocalSend, Zotero, Claude in chat, speech-to-text *base* | + Ollama 7–8B models (e.g. qwen2.5:7b, 4.7 GB), Organize offline, speech-to-text *small* (≈460 MB) | + 14B+ models, SDXL‑Turbo images (6.5 GB), XTTS voice (~1.8 GB), speech-to-text *medium* (1.5 GB), OBS 1440p recording |
| Not suggested | local AI models, AI Studio | AI Studio images (slow, CPU offload) | — |

Storage, for reference (measured on the dev PC): Daybook app ~660 MB installed · speech model small.en 462 MB ·
qwen2.5:7b 4.7 GB · SDXL‑Turbo 6.5 GB · ad-block lists 7 MB · thumbnails/notes grow with use (usually < 500 MB).

The hub shows the user's tier at the top ("Your PC: **Intermediate** — 16 GB RAM, RTX 3060 8 GB, 240 GB free on D:")
and greys out cards above it with *"needs Power — 12 GB VRAM"* instead of hiding them.

## Security & privacy

- Secrets (Discord webhooks, Whop key) → `keyring` (Windows Credential Manager). Migrating the existing Discord
  webhook out of settings is a **data migration — ask the user first**.
- Local APIs bind to 127.0.0.1 only; LocalSend receive is opt-in per device.
- Every outbound integration is listed under Settings → Browser & privacy → "What Daybook connects to".

## Phases

1. **Hub shell** — page, registry, detection + status for the integrations that already exist (no new features). *Small.*
2. **Hardware tiers** — "Your PC" banner + per-card requirements. *Small.*
3. **One-click installs** via winget with the consent dialog. *Medium.*
4. **LocalSend** send-to-phone (then receive). *Medium.*
5. **Whop** read-only dashboard card. *Medium* — needs the user's API key and which numbers matter to them.
6. **Secrets to Credential Manager** — *ask first* (touches stored settings).

## Open questions for Taylor

- Which Whop numbers matter most (members, MRR, today's sales, churn)?
- LocalSend: send only, or also receive phone recordings automatically into Voice memos?
- Should the hub suggest uninstalling things that are installed but never used?
