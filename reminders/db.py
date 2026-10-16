"""SQLite store shared by the pop-up daemon, quick-add box, CLI and the Claude MCP server."""
import calendar
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from . import paths

DB_PATH = paths.DATA / "reminders.db"
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
    cols = {r["name"] for r in con.execute("PRAGMA table_info(reminders)")}
    if "ends" not in cols:  # time blocks: 'HH:MM' end time shown on the timeline (e.g. 4:30–6:00)
        con.execute("ALTER TABLE reminders ADD COLUMN ends TEXT NOT NULL DEFAULT ''")
    if "category" not in cols:  # 1.6.10: custom categories + importance (0–100) for smart time-slotting
        _backup_before("categories")
        con.execute("ALTER TABLE reminders ADD COLUMN category TEXT NOT NULL DEFAULT ''")
        con.execute("ALTER TABLE reminders ADD COLUMN importance INTEGER NOT NULL DEFAULT 50")
        con.execute("UPDATE reminders SET importance=80 WHERE priority=1")  # "Important" ones start high
        con.commit()
    return con


def _backup_before(what):
    """A full copy of the database before a schema change (data/backups/), once per change."""
    try:
        dst_dir = DB_PATH.parent / "backups"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"reminders-{datetime.now():%Y-%m-%d}-before-{what}.db"
        if not dst.exists():
            src = sqlite3.connect(DB_PATH)
            out = sqlite3.connect(dst)
            src.backup(out)
            out.close()
            src.close()
    except Exception:
        pass


def daily_backup():
    """Once a day: a copy of the database in backups\\, one file per weekday (at most 7, rolling over).
    Writes only those files; never touches the live database."""
    try:
        dst = DB_PATH.parent / "backups" / f"reminders-daily-{datetime.now():%a}.db"
        if dst.exists() and datetime.fromtimestamp(dst.stat().st_mtime).date() == datetime.now().date():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        src, out = sqlite3.connect(DB_PATH), sqlite3.connect(dst)
        try:
            src.backup(out)
        finally:
            out.close()
            src.close()
    except Exception:
        pass


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


def validate_ends(ends):
    ends = (ends or "").strip()
    if ends:
        datetime.strptime(ends, "%H:%M")  # raises on bad input
    return ends


def add(text, due, repeat="", priority=0, notes="", ends="", category="", importance=None):
    imp = int(importance) if importance is not None else (80 if int(priority) else 50)
    with connect() as con:
        cur = con.execute(
            "INSERT INTO reminders (text, due, repeat, priority, notes, created, ends, category, importance) VALUES (?,?,?,?,?,?,?,?,?)",
            (text.strip(), fmt(due), validate_repeat(repeat), int(priority) or int(imp >= 70), notes, fmt(datetime.now()),
             validate_ends(ends), (category or "").strip()[:40], max(0, min(100, imp))))
        return cur.lastrowid


def occurrences_on(day):
    """Everything scheduled on a calendar day, repeating reminders expanded — for the timeline."""
    start = datetime(day.year, day.month, day.day)
    end = start + timedelta(days=1)
    out = []
    for r in list_open():
        due = parse_dt(r["due"])
        if r["repeat"] and due < start:
            due = next_occurrence(due, r["repeat"], start - timedelta(minutes=1))
        while due < end:
            if due >= start:
                out.append((due, r))
            if not r["repeat"]:
                break
            due = next_occurrence(due, r["repeat"], due)
    return sorted(out, key=lambda x: x[0])


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
    allowed = {k: v for k, v in fields.items()
               if k in ("text", "due", "repeat", "priority", "notes", "ends", "category", "importance") and v is not None}
    if "importance" in allowed:
        allowed["importance"] = max(0, min(100, int(allowed["importance"])))
        allowed.setdefault("priority", int(allowed["importance"] >= 70))
    if "due" in allowed and isinstance(allowed["due"], datetime):
        allowed["due"] = fmt(allowed["due"])
    if "repeat" in allowed:
        allowed["repeat"] = validate_repeat(allowed["repeat"])
    if "ends" in allowed:
        allowed["ends"] = validate_ends(allowed["ends"])
    if not allowed:
        return
    with connect() as con:
        con.execute(f"UPDATE reminders SET {', '.join(k + '=?' for k in allowed)} WHERE id=?",
                    (*allowed.values(), rid))


def delete(rid):
    with connect() as con:
        con.execute("UPDATE reminders SET status='deleted' WHERE id=?", (rid,))


SETTINGS = {  # key → default (stored as text in meta, prefixed 'set:')
    "open_at_startup": "1",     # open the Daybook window at logon
    "agenda_popup": "1",        # morning agenda pop-up
    "agenda_hour": "3",         # ...after this hour
    "nag_minutes": "5",         # pop-ups ring again every N minutes
    "ai_model": "qwen2.5:7b",   # local model for parsing + organizing notes
    "ai_cloud_fallback": "1",   # '1' = ask Claude (cloud) when the local AI isn't running; '0' = stay on this PC
    "chat_model": "",           # default model for new chats ('' = first installed)
    "import_dir": paths.IMPORT_DIR,  # old-notes folder
    "user_name": "Taylor",
    "welcome_seen": "0",
    "theme": "aurora",
    "annotations_dir": str(paths.USER_DIR / "Annotations"),
    "stt_model": "small.en",    # local speech-to-text model (faster-whisper)
    "stt_language": "",         # '' = auto (multilingual model only)
    "home": "",                 # JSON: home widgets, scene, sounds
    "layout": "",               # JSON: Simple / Balanced / Power + custom sidebar, density, hints
    "launch_apps": "",          # JSON list of app ids pinned on the Launchpad
    "discord_hooks": "",        # JSON [{name, url}] — Discord channel webhooks (kept on this PC only)
    "folders": "",              # JSON pinned folders
    "workflows": "",            # JSON workflows (folders + apps + sites opened together)
    "games_dir": str(paths.GAMES_DIR),  # where free games are downloaded
    "web_profiles": "",         # JSON in-app browser profiles [{id, name, color}]
    "pdf_folders": "",          # JSON folders the PDF library scans ('' = sensible defaults)
    "startup_view": "today",    # default startup window/view (e.g. today, apps:gemini)
    "ui_style": "glass",        # glass / classic UI style
    "tour_seen": "0",           # tour completion flag
    "clock_mode": "12h",        # clock mode (12h / 24h)
    "snooze_default": "10",     # default snooze in minutes
    "chat_persona": "",         # custom AI persona instructions
    "categories": "[]",         # custom user-defined categories
    "drives_cache": "[]",       # cached drive listing
}


def setting(key):
    return meta_get("set:" + key, SETTINGS.get(key, ""))


def settings():
    res = dict(SETTINGS)
    with connect() as con:
        rows = con.execute("SELECT key, value FROM meta WHERE key LIKE 'set:%'").fetchall()
        for r in rows:
            res[r["key"][4:]] = r["value"]
    return res


def set_settings(values):
    for k, v in values.items():
        if k and isinstance(k, str) and len(k) < 80:
            meta_set("set:" + k, str(v))


def save_setting(key, value):
    set_settings({key: value})


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
    ends = f"–{datetime.strptime(r['ends'], '%H:%M').strftime('%I:%M %p')}" if r["ends"] else ""
    return f"#{r['id']} {due.strftime('%a %b %d %I:%M %p')}{ends}{rep}{pri}: {r['text']}"
