"""MCP server so Claude can manage reminders: "remind me Friday at 3 to send the invoice".
Registered in Claude Code as `reminders` (user scope). Pop-ups come from daemon.pyw.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp.server.mcpserver import MCPServer  # noqa: E402  (mcp 2.x; was FastMCP)

from reminders import db, nlp, notes  # noqa: E402

mcp = MCPServer("reminders")


def _when(due: str):
    """Accepts 'YYYY-MM-DDTHH:MM' (preferred) or plain English like 'friday 3pm'."""
    try:
        return db.parse_dt(due.strip())
    except ValueError:
        return nlp.when(due)


@mcp.tool()
def add_reminder(text: str, due: str, repeat: str = "", priority: int = 0, notes: str = "", ends: str = "") -> str:
    """Schedule a desktop pop-up reminder on the user's PC.
    text: what to remind (short, imperative, e.g. "Send Ori the login link").
    due: local time 'YYYY-MM-DDTHH:MM' (compute it from the current date/time) or plain English.
    repeat: '', daily, weekdays, weekly, monthly, yearly, or every:<n>:<minutes|hours|days|weeks>.
    priority: 1 = important (highlighted). notes: optional extra detail shown in the pop-up.
    ends: optional 'HH:MM' end time to make it a time block on the Daybook timeline (e.g. 4:30–06:00)."""
    when = _when(due)
    if when <= datetime.now():
        return f"Refused: {db.fmt(when)} is in the past. Current time is {db.fmt(datetime.now())}."
    rid = db.add(text, when, repeat, priority, notes, ends)
    return "Scheduled " + db.describe(db.get(rid))


@mcp.tool()
def day_schedule(date: str = "") -> str:
    """The user's timeline for one day ('YYYY-MM-DD', default today): routine blocks + reminders."""
    from datetime import date as _date
    day = _date.fromisoformat(date) if date else _date.today()
    items = db.occurrences_on(day)
    lines = [f"{day:%A %b %d}:"]
    for when, r in items:
        ends = f"–{r['ends']}" if r["ends"] else ""
        lines.append(f"  {when:%H:%M}{ends}  #{r['id']} {r['text']}" + (f" (repeats {r['repeat']})" if r["repeat"] else ""))
    return "\n".join(lines) if items else lines[0] + " nothing scheduled"


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
                    priority: int = None, notes: str = None, ends: str = None) -> str:
    """Edit any field of a reminder. Only the fields you pass change. ends: 'HH:MM' block end, '' to clear."""
    if not db.get(id):
        return f"No reminder #{id}"
    db.update(id, text=text, due=_when(due) if due else None, repeat=repeat, priority=priority, notes=notes, ends=ends)
    return "Updated " + db.describe(db.get(id))


@mcp.tool()
def delete_reminder(id: int) -> str:
    """Delete a reminder."""
    if not db.get(id):
        return f"No reminder #{id}"
    db.delete(id)
    return f"Deleted #{id}"


# ---------- notes (Daybook) ----------

def _note_line(n):
    return f"#{n['id']} {n['note_date']} [{n['category'] or '—'}] {n['title'] or 'Untitled'}" + \
           (f" — {n['summary']}" if n["summary"] else "")


@mcp.tool()
def search_notes(query: str = "", category: str = "", tag: str = "", date_from: str = "", date_to: str = "",
                 limit: int = 30) -> str:
    """Full-text search of the user's notes (meeting notes, YouTube notes, ideas, daily logs, imported F:\\28HRTZ notes).
    category: one of Meeting, YouTube / Learning, Idea, To-do, Journal, Business, Content, Tech, Personal.
    Dates are 'YYYY-MM-DD'. Returns ids + summaries; use get_note for the full text."""
    rows = notes.search(query, category, tag, date_from, date_to, limit)
    return "\n".join(_note_line(n) for n in rows) or "No notes match."


@mcp.tool()
def get_note(id: int) -> str:
    """Full note: body, tags, summary, topics and action items."""
    n = notes.get(id)
    if not n:
        return f"No note #{id}"
    return "\n".join([
        _note_line(n), f"Tags: {', '.join(n['tags'])}", f"Topics: {'; '.join(n['topics'])}",
        "Action items:" + "".join(f"\n  - {a}" for a in n["actions"]), "", n["body"]])


@mcp.tool()
def add_note(body: str, title: str = "", category: str = "", tags: str = "", note_date: str = "") -> str:
    """Save a new note. The local AI fills in missing title/category/tags/summary/action items shortly after.
    tags: comma separated. note_date: 'YYYY-MM-DD' (default today)."""
    nid = notes.add(body, title, category, [t for t in tags.split(",")], note_date or None)
    return f"Saved note #{nid}"


@mcp.tool()
def update_note(id: int, title: str = None, body: str = None, category: str = None, tags: str = None,
                note_date: str = None) -> str:
    """Edit a note (only the fields passed change). Changing the body re-runs the local AI organizer."""
    if not notes.get(id):
        return f"No note #{id}"
    notes.update(id, title=title, body=body, category=category,
                 tags=[t for t in tags.split(",")] if tags is not None else None, note_date=note_date)
    if body is not None:
        notes.reorganize(id)
    return "Updated " + _note_line(notes.get(id))


@mcp.tool()
def log_to_today(text: str) -> str:
    """Append a timestamped line to today's daily log note."""
    nid = notes.append_to_log(text)
    return f"Logged to daily log #{nid}"


@mcp.tool()
def notes_overview() -> str:
    """Counts per category, top tags and AI-organizing status — a quick map of the notebook."""
    c = notes.category_counts()
    tags = ", ".join(f"{t} ({n})" for t, n in notes.all_tags()[:25])
    return f"Categories: {c}\nTop tags: {tags}\nAI status: {notes.stats()}"


if __name__ == "__main__":
    mcp.run()
