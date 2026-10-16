"""MCP server so Claude and Gemini can manage reminders: "remind me Friday at 3 to send the invoice".
Registered in Claude Code as `reminders` and in Gemini CLI as `daybook` (user scope). Pop-ups come from daemon.pyw.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp.server.mcpserver import MCPServer  # noqa: E402  (mcp 2.x; was FastMCP)

from reminders import paths  # noqa: E402

mcp = MCPServer("reminders")

BACKEND_URL = os.environ.get("DAYBOOK_BACKEND_URL", "http://127.0.0.1:8503")
BACKEND_WAIT_S = 30.0
NOT_RUNNING_MSG = "Daybook isn't running. Open Daybook and try again."
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)


def _backend_host_port():
    parsed = urllib.parse.urlparse(BACKEND_URL)
    return (parsed.hostname or "127.0.0.1"), (parsed.port or 8503)


def _start_backend_process():
    """Spawn the Daybook background service if nothing is listening on :8503."""
    try:
        if paths.FROZEN:
            exe = Path(sys.executable).with_name("daybook-backend.exe")
            if exe.exists():
                subprocess.Popen([str(exe)], close_fds=True, creationflags=NO_WINDOW)
                return True
        else:
            pyw = paths.APP / "venv" / "Scripts" / "pythonw.exe"
            if not pyw.exists():
                pyw = Path(sys.executable)
            daemon = paths.APP / "daemon.pyw"
            if daemon.exists():
                subprocess.Popen([str(pyw), str(daemon)], cwd=str(paths.APP), close_fds=True, creationflags=NO_WINDOW)
                return True
    except Exception:
        pass
    return False


def _ensure_backend(timeout: float = BACKEND_WAIT_S) -> bool:
    """Ensure Daybook is listening on BACKEND_URL; start it and wait up to `timeout` seconds if needed."""
    host, port = _backend_host_port()
    if paths.port_open(port, host):
        return True
    _start_backend_process()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if paths.port_open(port, host):
            return True
        time.sleep(0.5)
    return paths.port_open(port, host)


def _call_backend(tool_name: str, kwargs: dict) -> str:
    """Forward an MCP tool call over HTTP to the running Daybook backend on 127.0.0.1:8503."""
    if os.environ.get("DAYBOOK_MCP_DIRECT") == "1":
        return _exec_local(tool_name, kwargs)
    if not _ensure_backend():
        return NOT_RUNNING_MSG
    payload = json.dumps({"tool": tool_name, "args": kwargs}).encode("utf-8")
    req = urllib.request.Request(
        f"{BACKEND_URL.rstrip('/')}/api/mcp/tool",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and "result" in data:
                return str(data["result"])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Running backend is from before /api/mcp/tool existed: execute in-process as fallback
            return _exec_local(tool_name, kwargs)
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            if isinstance(err_body, dict) and err_body.get("error"):
                return f"Error: {err_body['error']}"
        except Exception:
            pass
        return f"Error calling Daybook ({e.code})"
    except (urllib.error.URLError, OSError):
        if not _ensure_backend(timeout=5.0):
            return NOT_RUNNING_MSG
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict) and "result" in data:
                    return str(data["result"])
        except Exception:
            return NOT_RUNNING_MSG
    return _exec_local(tool_name, kwargs)


def _when(due: str):
    """Accepts 'YYYY-MM-DDTHH:MM' (preferred) or plain English like 'friday 3pm'."""
    from reminders import db, nlp
    try:
        return db.parse_dt(due.strip())
    except ValueError:
        return nlp.when(due)


def _note_line(n):
    return f"#{n['id']} {n['note_date']} [{n['category'] or '—'}] {n['title'] or 'Untitled'}" + \
           (f" — {n['summary']}" if n["summary"] else "")


def _exec_local(tool_name: str, kwargs: dict) -> str:
    """Execute an MCP tool directly against reminders.db / nlp / notes (used by /api/mcp/tool on the backend)."""
    from reminders import db, nlp, notes

    if tool_name == "add_reminder":
        text = kwargs["text"]
        due = kwargs["due"]
        repeat = kwargs.get("repeat", "")
        priority = kwargs.get("priority", 0)
        rnotes = kwargs.get("notes", "")
        ends = kwargs.get("ends", "")
        when = _when(due)
        if when <= datetime.now():
            return f"Refused: {db.fmt(when)} is in the past. Current time is {db.fmt(datetime.now())}."
        rid = db.add(text, when, repeat, priority, rnotes, ends)
        return "Scheduled " + db.describe(db.get(rid))

    if tool_name == "day_schedule":
        from datetime import date as _date
        date = kwargs.get("date", "")
        day = _date.fromisoformat(date) if date else _date.today()
        items = db.occurrences_on(day)
        lines = [f"{day:%A %b %d}:"]
        for when, r in items:
            ends = f"–{r['ends']}" if r["ends"] else ""
            lines.append(f"  {when:%H:%M}{ends}  #{r['id']} {r['text']}" + (f" (repeats {r['repeat']})" if r["repeat"] else ""))
        return "\n".join(lines) if items else lines[0] + " nothing scheduled"

    if tool_name == "add_reminder_natural":
        p = nlp.parse(kwargs["request"])
        rid = db.add(p["text"], p["due"], p["repeat"], p["priority"])
        note = " (no time given, defaulted to tomorrow 9 AM)" if p.get("guessed_time") else ""
        return "Scheduled " + db.describe(db.get(rid)) + note

    if tool_name == "list_reminders":
        days_ahead = kwargs.get("days_ahead", 30)
        include_done = kwargs.get("include_done", False)
        now = datetime.now()
        rows = db.list_open(until=now + timedelta(days=days_ahead))
        lines = [f"Now: {now.strftime('%a %b %d %I:%M %p')}"]
        lines += [("OVERDUE " if db.parse_dt(r["due"]) < now else "") + db.describe(r) for r in rows] or ["(nothing scheduled)"]
        if include_done:
            lines += ["", "Recently done:"] + [db.describe(r) for r in db.list_recent_done()]
        return "\n".join(lines)

    if tool_name == "complete_reminder":
        rid = kwargs["id"]
        res = db.complete(rid)
        return f"#{rid}: {res}" if res else f"No reminder #{rid}"

    if tool_name == "snooze_reminder":
        rid = kwargs["id"]
        until = kwargs["until"]
        if not db.get(rid):
            return f"No reminder #{rid}"
        db.snooze(rid, _when(until))
        return "Snoozed " + db.describe(db.get(rid))

    if tool_name == "update_reminder":
        rid = kwargs["id"]
        if not db.get(rid):
            return f"No reminder #{rid}"
        due = kwargs.get("due")
        db.update(
            rid,
            text=kwargs.get("text"),
            due=_when(due) if due else None,
            repeat=kwargs.get("repeat"),
            priority=kwargs.get("priority"),
            notes=kwargs.get("notes"),
            ends=kwargs.get("ends"),
        )
        return "Updated " + db.describe(db.get(rid))

    if tool_name == "delete_reminder":
        rid = kwargs["id"]
        if not db.get(rid):
            return f"No reminder #{rid}"
        db.delete(rid)
        return f"Deleted #{rid}"

    if tool_name == "search_notes":
        rows = notes.search(
            kwargs.get("query", ""),
            kwargs.get("category", ""),
            kwargs.get("tag", ""),
            kwargs.get("date_from", ""),
            kwargs.get("date_to", ""),
            kwargs.get("limit", 30),
        )
        return "\n".join(_note_line(n) for n in rows) or "No notes match."

    if tool_name == "get_note":
        nid = kwargs["id"]
        n = notes.get(nid)
        if not n:
            return f"No note #{nid}"
        return "\n".join([
            _note_line(n), f"Tags: {', '.join(n['tags'])}", f"Topics: {'; '.join(n['topics'])}",
            "Action items:" + "".join(f"\n  - {a['text']}" + (f" ({a['when']})" if a.get('when') else "") for a in n["actions"]), "", n["body"]])

    if tool_name == "add_note":
        tags = kwargs.get("tags", "")
        note_date = kwargs.get("note_date", "")
        nid = notes.add(
            kwargs["body"],
            kwargs.get("title", ""),
            kwargs.get("category", ""),
            [t for t in tags.split(",")],
            note_date or None,
        )
        return f"Saved note #{nid}"

    if tool_name == "update_note":
        nid = kwargs["id"]
        if not notes.get(nid):
            return f"No note #{nid}"
        body = kwargs.get("body")
        tags = kwargs.get("tags")
        notes.update(
            nid,
            title=kwargs.get("title"),
            body=body,
            category=kwargs.get("category"),
            tags=[t for t in tags.split(",")] if tags is not None else None,
            note_date=kwargs.get("note_date"),
        )
        if body is not None:
            notes.reorganize(nid)
        return "Updated " + _note_line(notes.get(nid))

    if tool_name == "log_to_today":
        nid = notes.append_to_log(kwargs["text"])
        return f"Logged to daily log #{nid}"

    if tool_name == "notes_overview":
        c = notes.category_counts()
        tags = ", ".join(f"{t} ({n})" for t, n in notes.all_tags()[:25])
        return f"Categories: {c}\nTop tags: {tags}\nAI status: {notes.stats()}"

    raise ValueError(f"Unknown MCP tool: {tool_name}")


@mcp.tool()
def add_reminder(text: str, due: str, repeat: str = "", priority: int = 0, notes: str = "", ends: str = "") -> str:
    """Schedule a desktop pop-up reminder on the user's PC.
    text: what to remind (short, imperative, e.g. "Send Ori the login link").
    due: local time 'YYYY-MM-DDTHH:MM' (compute it from the current date/time) or plain English.
    repeat: '', daily, weekdays, weekly, monthly, yearly, or every:<n>:<minutes|hours|days|weeks>.
    priority: 1 = important (highlighted). notes: optional extra detail shown in the pop-up.
    ends: optional 'HH:MM' end time to make it a time block on the Daybook timeline (e.g. 4:30–06:00)."""
    return _call_backend("add_reminder", {"text": text, "due": due, "repeat": repeat, "priority": priority, "notes": notes, "ends": ends})


@mcp.tool()
def day_schedule(date: str = "") -> str:
    """The user's timeline for one day ('YYYY-MM-DD', default today): routine blocks + reminders."""
    return _call_backend("day_schedule", {"date": date})


@mcp.tool()
def add_reminder_natural(request: str) -> str:
    """Schedule from one plain-English sentence using the local AI parser,
    e.g. 'take meds every day at 9am'. Prefer add_reminder when you can compute the time yourself."""
    return _call_backend("add_reminder_natural", {"request": request})


@mcp.tool()
def list_reminders(days_ahead: int = 30, include_done: bool = False) -> str:
    """List open reminders due within `days_ahead` days (overdue included). Shows ids for other tools."""
    return _call_backend("list_reminders", {"days_ahead": days_ahead, "include_done": include_done})


@mcp.tool()
def complete_reminder(id: int) -> str:
    """Mark done. Repeating reminders roll forward to their next time."""
    return _call_backend("complete_reminder", {"id": id})


@mcp.tool()
def snooze_reminder(id: int, until: str) -> str:
    """Move a reminder to a new time ('YYYY-MM-DDTHH:MM' or plain English like 'in 2 hours')."""
    return _call_backend("snooze_reminder", {"id": id, "until": until})


@mcp.tool()
def update_reminder(id: int, text: str = None, due: str = None, repeat: str = None,
                    priority: int = None, notes: str = None, ends: str = None) -> str:
    """Edit any field of a reminder. Only the fields you pass change. ends: 'HH:MM' block end, '' to clear."""
    return _call_backend("update_reminder", {"id": id, "text": text, "due": due, "repeat": repeat, "priority": priority, "notes": notes, "ends": ends})


@mcp.tool()
def delete_reminder(id: int) -> str:
    """Delete a reminder."""
    return _call_backend("delete_reminder", {"id": id})


# ---------- notes (Daybook) ----------

@mcp.tool()
def search_notes(query: str = "", category: str = "", tag: str = "", date_from: str = "", date_to: str = "",
                 limit: int = 30) -> str:
    """Full-text search of the user's notes (meeting notes, YouTube notes, ideas, daily logs, imported F:\\28HRTZ notes).
    category: one of Meeting, YouTube / Learning, Idea, To-do, Journal, Business, Content, Tech, Personal.
    Dates are 'YYYY-MM-DD'. Returns ids + summaries; use get_note for the full text."""
    return _call_backend("search_notes", {"query": query, "category": category, "tag": tag, "date_from": date_from, "date_to": date_to, "limit": limit})


@mcp.tool()
def get_note(id: int) -> str:
    """Full note: body, tags, summary, topics and action items."""
    return _call_backend("get_note", {"id": id})


@mcp.tool()
def add_note(body: str, title: str = "", category: str = "", tags: str = "", note_date: str = "") -> str:
    """Save a new note. The local AI fills in missing title/category/tags/summary/action items shortly after.
    tags: comma separated. note_date: 'YYYY-MM-DD' (default today)."""
    return _call_backend("add_note", {"body": body, "title": title, "category": category, "tags": tags, "note_date": note_date})


@mcp.tool()
def update_note(id: int, title: str = None, body: str = None, category: str = None, tags: str = None,
                note_date: str = None) -> str:
    """Edit a note (only the fields passed change). Changing the body re-runs the local AI organizer."""
    return _call_backend("update_note", {"id": id, "title": title, "body": body, "category": category, "tags": tags, "note_date": note_date})


@mcp.tool()
def log_to_today(text: str) -> str:
    """Append a timestamped line to today's daily log note."""
    return _call_backend("log_to_today", {"text": text})


@mcp.tool()
def notes_overview() -> str:
    """Counts per category, top tags and AI-organizing status — a quick map of the notebook."""
    return _call_backend("notes_overview", {})


if __name__ == "__main__":
    mcp.run()
