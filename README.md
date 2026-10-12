# Local Reminders

Local AI reminders with desktop pop-ups. Nothing leaves this PC.

## Ways to add a reminder
- **Ask Claude** (any Claude Code session): "remind me Friday at 3pm to send the invoice".
  Claude uses the `reminders` MCP server (`mcp_server.py`, registered at user scope).
- **Ctrl+Alt+R** opens the quick-add box: type plain English, e.g.
  `call mom sunday 5pm`, `take meds every day at 9am`, `pay rent on the 1st every month`.
  Parsed locally: Ollama qwen2.5:7b splits task / when / repeat, `dateparser` does the date math.
  Type `undo` to remove the last one, `agenda` to open the agenda.
- **Ctrl+Alt+A** opens the agenda (overdue + next 14 days, with Done / Delete).

## Pop-ups
`daemon.pyw` runs at logon (task `LocalRemindersDaemon`). When something is due it shows an
always-on-top pop-up bottom-right that rings again every 5 min until you press **Done** or
**Snooze** (10 min / 1 hour / tonight / tomorrow / typed time). Closing it = snooze 10 min.
Reminders missed while the PC was off pop up at the next logon. The agenda pops up once a day after 8 AM.

Repeats: daily, weekdays, weekly, monthly, yearly, every N minutes/hours/days/weeks.
Words like "urgent", "important", "asap" mark it important.

## Files
- `reminders/db.py` – SQLite store (`data/reminders.db`)
- `reminders/nlp.py` – plain English → reminder
- `reminders/ui.py` – pop-up, agenda and quick-add windows
- `daemon.pyw`, `quickadd.pyw`, `mcp_server.py`
