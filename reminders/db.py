"""SQLite store shared by the pop-up daemon, quick-add box, CLI and the Claude MCP server."""
import calendar
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "reminders.db"
FMT = "%Y-%m-%dT%H:%M"  # local time, minute precision

# repeat rules: "" | daily | weekdays | weekly | monthly | yearly | every:<n>:<minutes|hours|days|weeks>
REPEAT_HELP = "'', daily, weekdays, weekly, monthly, yearly, or every:<n>:<minutes|hours|days|weeks>"


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY,
        text TEXT NOT NULL,
        due TEXT NOT NULL,
        repeat TEXT NOT NULL DEFAULT '',
        priority INTEGER NOT NULL DEFAULT 0,
        notes TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'open',
        created TEXT NOT NULL,
        completed TEXT
    )""")
    con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    return con


def fmt(dt):
    return dt.strftime(FMT)


def parse_dt(s):
    return datetime.strptime(s[:16], FMT)


def validate_repeat(rule):
    rule = (rule or "").strip().lower()
    if rule in ("", "none", "daily", "weekdays", "weekly", "monthly", "yearly"):
        return "" if rule == "none" else rule
    parts = rule.split(":")
    if len(parts) == 3 and parts[0] == "every" and parts[1].isdigit() and int(parts[1]) > 0 \
            and parts[2] in ("minutes", "hours", "days", "weeks"):
        return rule
    raise ValueError(f"bad repeat rule {rule!r}; use {REPEAT_HELP}")


def next_occurrence(due, rule, now=None):
    """Next due time strictly after `now` for a repeating reminder (skips missed occurrences)."""
    now = now or datetime.now()
    nxt = due
    while nxt <= now:
        if rule == "daily":
            nxt += timedelta(days=1)
        elif rule == "weekdays":
            nxt += timedelta(days=1)
            while nxt.weekday() >= 5:
                nxt += timedelta(days=1)
        elif rule == "weekly":
            nxt += timedelta(weeks=1)
        elif rule == "monthly":
            y, m = (nxt.year + nxt.month // 12, nxt.month % 12 + 1)
            nxt = nxt.replace(year=y, month=m, day=min(due.day, calendar.monthrange(y, m)[1]))
        elif rule == "yearly":
            y = nxt.year + 1
            nxt = nxt.replace(year=y, day=min(due.day, calendar.monthrange(y, due.month)[1]))
        elif rule.startswith("every:"):
            _, n, unit = rule.split(":")
            nxt += timedelta(**{unit: int(n)})
        else:
            break
    return nxt


def add(text, due, repeat="", priority=0, notes=""):
    with connect() as con:
        cur = con.execute(
            "INSERT INTO reminders (text, due, repeat, priority, notes, created) VALUES (?,?,?,?,?,?)",
            (text.strip(), fmt(due), validate_repeat(repeat), int(priority), notes, fmt(datetime.now())))
        return cur.lastrowid


def get(rid):
    with connect() as con:
        return con.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone()


def list_open(until=None):
    with connect() as con:
        if until:
            return con.execute("SELECT * FROM reminders WHERE status='open' AND due<=? ORDER BY due",
                               (fmt(until),)).fetchall()
        return con.execute("SELECT * FROM reminders WHERE status='open' ORDER BY due").fetchall()


def list_recent_done(limit=20):
    with connect() as con:
        return con.execute("SELECT * FROM reminders WHERE status='done' ORDER BY completed DESC LIMIT ?",
                           (limit,)).fetchall()


def due_now():
    return list_open(until=datetime.now())


def complete(rid):
    """Done: one-off reminders close; repeating ones roll forward to their next time."""
    r = get(rid)
    if not r:
        return None
    with connect() as con:
        if r["repeat"]:
            nxt = next_occurrence(parse_dt(r["due"]), r["repeat"])
            con.execute("UPDATE reminders SET due=? WHERE id=?", (fmt(nxt), rid))
            return f"next: {fmt(nxt)}"
        con.execute("UPDATE reminders SET status='done', completed=? WHERE id=?", (fmt(datetime.now()), rid))
        return "done"


def snooze(rid, until):
    with connect() as con:
        con.execute("UPDATE reminders SET due=? WHERE id=?", (fmt(until), rid))


def update(rid, **fields):
    allowed = {k: v for k, v in fields.items() if k in ("text", "due", "repeat", "priority", "notes") and v is not None}
    if "due" in allowed and isinstance(allowed["due"], datetime):
        allowed["due"] = fmt(allowed["due"])
    if "repeat" in allowed:
        allowed["repeat"] = validate_repeat(allowed["repeat"])
    if not allowed:
        return
    with connect() as con:
        con.execute(f"UPDATE reminders SET {', '.join(k + '=?' for k in allowed)} WHERE id=?",
                    (*allowed.values(), rid))


def delete(rid):
    with connect() as con:
        con.execute("UPDATE reminders SET status='deleted' WHERE id=?", (rid,))


def meta_get(key, default=None):
    with connect() as con:
        row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def meta_set(key, value):
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, value))


def describe(r):
    due = parse_dt(r["due"])
    rep = f" (repeats {r['repeat']})" if r["repeat"] else ""
    pri = " [!]" if r["priority"] else ""
    return f"#{r['id']} {due.strftime('%a %b %d %I:%M %p')}{rep}{pri}: {r['text']}"
