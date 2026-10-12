"""MCP server so Claude can manage reminders: "remind me Friday at 3 to send the invoice".
Registered in Claude Code as `reminders` (user scope). Pop-ups come from daemon.pyw.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp.server.mcpserver import MCPServer  # noqa: E402  (mcp 2.x; was FastMCP)

from reminders import db, nlp  # noqa: E402

mcp = MCPServer("reminders")


def _when(due: str):
    """Accepts 'YYYY-MM-DDTHH:MM' (preferred) or plain English like 'friday 3pm'."""
    try:
        return db.parse_dt(due.strip())
    except ValueError:
        return nlp.parse("x " + due)["due"]


@mcp.tool()
def add_reminder(text: str, due: str, repeat: str = "", priority: int = 0, notes: str = "") -> str:
    """Schedule a desktop pop-up reminder on the user's PC.
    text: what to remind (short, imperative, e.g. "Send Ori the login link").
    due: local time 'YYYY-MM-DDTHH:MM' (compute it from the current date/time) or plain English.
    repeat: '', daily, weekdays, weekly, monthly, yearly, or every:<n>:<minutes|hours|days|weeks>.
    priority: 1 = important (highlighted). notes: optional extra detail shown in the pop-up."""
    when = _when(due)
    if when <= datetime.now():
        return f"Refused: {db.fmt(when)} is in the past. Current time is {db.fmt(datetime.now())}."
    rid = db.add(text, when, repeat, priority, notes)
    return "Scheduled " + db.describe(db.get(rid))


@mcp.tool()
def add_reminder_natural(request: str) -> str:
    """Schedule from one plain-English sentence using the local AI parser,
    e.g. 'take meds every day at 9am'. Prefer add_reminder when you can compute the time yourself."""
    p = nlp.parse(request)
    rid = db.add(p["text"], p["due"], p["repeat"], p["priority"])
    note = " (no time given, defaulted to tomorrow 9 AM)" if p.get("guessed_time") else ""
    return "Scheduled " + db.describe(db.get(rid)) + note


@mcp.tool()
def list_reminders(days_ahead: int = 30, include_done: bool = False) -> str:
    """List open reminders due within `days_ahead` days (overdue included). Shows ids for other tools."""
    now = datetime.now()
    rows = db.list_open(until=now + timedelta(days=days_ahead))
    lines = [f"Now: {now.strftime('%a %b %d %I:%M %p')}"]
    lines += [("OVERDUE " if db.parse_dt(r["due"]) < now else "") + db.describe(r) for r in rows] or ["(nothing scheduled)"]
    if include_done:
        lines += ["", "Recently done:"] + [db.describe(r) for r in db.list_recent_done()]
    return "\n".join(lines)


@mcp.tool()
def complete_reminder(id: int) -> str:
    """Mark done. Repeating reminders roll forward to their next time."""
    res = db.complete(id)
    return f"#{id}: {res}" if res else f"No reminder #{id}"


@mcp.tool()
def snooze_reminder(id: int, until: str) -> str:
    """Move a reminder to a new time ('YYYY-MM-DDTHH:MM' or plain English like 'in 2 hours')."""
    if not db.get(id):
        return f"No reminder #{id}"
    db.snooze(id, _when(until))
    return "Snoozed " + db.describe(db.get(id))


@mcp.tool()
def update_reminder(id: int, text: str = None, due: str = None, repeat: str = None,
                    priority: int = None, notes: str = None) -> str:
    """Edit any field of a reminder. Only the fields you pass change."""
    if not db.get(id):
        return f"No reminder #{id}"
    db.update(id, text=text, due=_when(due) if due else None, repeat=repeat, priority=priority, notes=notes)
    return "Updated " + db.describe(db.get(id))


@mcp.tool()
def delete_reminder(id: int) -> str:
    """Delete a reminder."""
    if not db.get(id):
        return f"No reminder #{id}"
    db.delete(id)
    return f"Deleted #{id}"


if __name__ == "__main__":
    mcp.run()
