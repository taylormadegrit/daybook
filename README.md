# Daybook — local AI reminders, routine & notes

Everything runs on this PC: SQLite + the local Ollama model (qwen2.5:7b). Nothing goes to the cloud.

## Hotkeys (Start Menu shortcuts)
| Keys | What |
|---|---|
| **Ctrl+Alt+D** | Open the Daybook dashboard — http://localhost:8503 |
| **Ctrl+Alt+R** | Quick reminder: `call mom sunday 5pm`, `take meds every day at 9am` |
| **Ctrl+Alt+N** | Quick note → appended to today's daily log |
| **Ctrl+Alt+A** | Agenda pop-out (overdue + next 14 days) |

## Dashboard (localhost:8503)
- **Today** — the day as a timeline of time blocks (routine + reminders), live block highlighted,
  ◀ ▶ to browse days, plus the **daily log** (timestamped one-liners).
- **Notes** — categories (Meeting, YouTube / Learning, Idea, To-do, Journal, Business, Content, Tech,
  Personal), tag cloud, date filter, full-text search. **New** with a template (Meeting, YouTube, Idea…).
  The local AI fills in title, category, tags, summary, topics and **action items**; each action item
  has a **⏰ Remind me** button. Your text is never changed by the AI.
- **Reminders** — plain-English or exact add, repeats, end times (blocks), edit / snooze / delete.

## Pop-ups
`daemon.pyw` (task `LocalRemindersDaemon`, at logon) shows an always-on-top pop-up when something is due
and rings every 5 min until **Done** or **Snooze**. Missed reminders pop up at the next logon.
The agenda opens once a day after 3 AM. Task `LocalRemindersWakeUp` wakes the PC from sleep at 2:58 AM.
The same process serves the dashboard and runs the AI note organizer in the background.

## Claude
MCP server `reminders` (user scope) — Claude can: add/list/snooze/update/complete/delete reminders,
show a day's schedule, search/read/add/update notes, log to today, and give a notebook overview.

## Old notes
`F:\28HRTZ` top-level .txt/.odt/.md/.docx notes were imported (read-only — originals untouched;
files that look like logins/keys are skipped). "Import new files from F:\28HRTZ" in Notes picks up new ones.

## Files
- `reminders/db.py` reminders · `reminders/notes.py` notes, import, AI organizer · `reminders/nlp.py` plain English → time
- `reminders/ui.py` Tk pop-ups · `reminders/web.py` + `web/index.html` dashboard
- `daemon.pyw`, `quickadd.pyw`, `mcp_server.py` · data in `data/reminders.db` (not in git)

## Chat (localhost:8503/chat · Ctrl+Alt+C)
Claude-style chat with every local Ollama model (model picker), saved conversations, streaming,
Markdown + code highlighting, personas (Assistant, Coder, Content strategist, Ori script writer, Thinking partner).
Toggles let the model use **Daybook** tools (schedule, reminders, notes, daily log) and **Orca** tools
(list projects, create a new project in D:\projects + start Claude/Codex on it, start a task in an existing
project). Orca actions always show a Confirm / Cancel card first. Code: `reminders/chat.py`, `reminders/orca.py`, `web/chat.html`.
