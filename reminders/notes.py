"""Notes: SQLite + full-text search, daily log, read-only import of old notes, and free local AI
organizing (Ollama qwen2.5:7b): title, category, tags, summary, topics and action items."""
import json
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree

from . import db, nlp

CATEGORIES = ["Meeting", "YouTube / Learning", "Idea", "To-do", "Journal", "Business", "Content", "Tech", "Personal"]

# Templates for "New note" — structure makes notes easy to scan and easy for the AI to organize
TEMPLATES = {
    "Meeting": "Who: \nWhere: (Discord / Zoom / in person)\nTopic: \n\n## Notes\n- \n\n## Decisions\n- \n\n## Action items\n- [ ] \n",
    "YouTube / Learning": "Video / source: \nLink: \nCreator: \n\n## Key points\n- \n\n## Quotes\n- \n\n## How I'll use this\n- \n",
    "Idea": "## The idea\n\n## Why it matters\n\n## Next step\n- [ ] \n",
    "To-do": "- [ ] \n- [ ] \n- [ ] \n",
    "Journal": "## Today\n\n## Wins\n- \n\n## Lessons\n- \n\n## Tomorrow\n- [ ] \n",
    "Business": "Project / client: \n\n## Notes\n- \n\n## Numbers\n- \n\n## Action items\n- [ ] \n",
    "Content": "Platform: \nFormat: (Short / video / post)\n\n## Hook\n\n## Script / outline\n- \n\n## CTA\n",
}

# Old notes on F: are read, never modified. Anything that looks like a credential is never read.
IMPORT_DIR = Path("F:/28HRTZ")
IMPORT_EXTS = {".txt", ".odt", ".md", ".docx"}
SECRET_WORDS = re.compile(r"key|login|password|passwd|secret|token|recovery|2fa|credential", re.I)


def _con():
    con = db.connect()
    con.execute("""CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        topics TEXT NOT NULL DEFAULT '[]',
        actions TEXT NOT NULL DEFAULT '[]',
        note_date TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT '',
        pinned INTEGER NOT NULL DEFAULT 0,
        ai_status TEXT NOT NULL DEFAULT 'pending',
        created TEXT NOT NULL,
        updated TEXT NOT NULL
    )""")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS notes_source ON notes(source) WHERE source != ''")
    con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
        title, body, tags, summary, content='notes', content_rowid='id')""")
    for name, sql in {
        "notes_ai": "AFTER INSERT ON notes BEGIN INSERT INTO notes_fts(rowid, title, body, tags, summary) "
                    "VALUES (new.id, new.title, new.body, new.tags, new.summary); END",
        "notes_ad": "AFTER DELETE ON notes BEGIN INSERT INTO notes_fts(notes_fts, rowid, title, body, tags, summary) "
                    "VALUES ('delete', old.id, old.title, old.body, old.tags, old.summary); END",
        "notes_au": "AFTER UPDATE ON notes BEGIN INSERT INTO notes_fts(notes_fts, rowid, title, body, tags, summary) "
                    "VALUES ('delete', old.id, old.title, old.body, old.tags, old.summary); "
                    "INSERT INTO notes_fts(rowid, title, body, tags, summary) "
                    "VALUES (new.id, new.title, new.body, new.tags, new.summary); END",
    }.items():
        con.execute(f"CREATE TRIGGER IF NOT EXISTS {name} {sql}")
    return con


def _row(r):
    if r is None:
        return None
    d = dict(r)
    d["topics"] = json.loads(d.get("topics") or "[]")
    d["actions"] = json.loads(d.get("actions") or "[]")
    d["tags"] = [t for t in (d.get("tags") or "").split(",") if t]
    return d


def now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


# ---------- CRUD ----------

def add(body, title="", category="", tags=(), note_date=None, source="", organize=True):
    with _con() as con:
        cur = con.execute(
            "INSERT INTO notes (title, body, category, tags, note_date, source, ai_status, created, updated) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (title.strip(), body, category, ",".join(t.strip() for t in tags if t.strip()),
             note_date or date.today().isoformat(), source, "pending" if organize else "manual", now(), now()))
        return cur.lastrowid


def get(nid):
    with _con() as con:
        return _row(con.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone())


def update(nid, **fields):
    allowed = {k: v for k, v in fields.items()
               if k in ("title", "body", "category", "tags", "note_date", "pinned", "summary") and v is not None}
    if "tags" in allowed and not isinstance(allowed["tags"], str):
        allowed["tags"] = ",".join(t.strip() for t in allowed["tags"] if t.strip())
    if not allowed:
        return
    allowed["updated"] = now()
    with _con() as con:
        con.execute(f"UPDATE notes SET {', '.join(k + '=?' for k in allowed)} WHERE id=?", (*allowed.values(), nid))


def delete(nid):
    with _con() as con:
        con.execute("DELETE FROM notes WHERE id=?", (nid,))


def search(query="", category="", tag="", date_from="", date_to="", limit=200):
    sql, args = "SELECT n.* FROM notes n", []
    where = []
    if query.strip():
        # each word must match (prefix search), so "jocko disc" finds "Jocko ... discipline"
        terms = " ".join(f'"{w}"*' for w in re.findall(r"\w+", query))
        sql += " JOIN notes_fts f ON f.rowid = n.id"
        where.append("notes_fts MATCH ?")
        args.append(terms)
    if category:
        where.append("n.category = ?")
        args.append(category)
    if tag:
        where.append("(',' || n.tags || ',') LIKE ?")
        args.append(f"%,{tag},%")
    if date_from:
        where.append("n.note_date >= ?")
        args.append(date_from)
    if date_to:
        where.append("n.note_date <= ?")
        args.append(date_to)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY n.pinned DESC, n.note_date DESC, n.id DESC LIMIT ?"
    args.append(limit)
    with _con() as con:
        return [_row(r) for r in con.execute(sql, args).fetchall()]


def all_tags():
    counts = {}
    with _con() as con:
        for (tags,) in con.execute("SELECT tags FROM notes"):
            for t in filter(None, tags.split(",")):
                counts[t] = counts.get(t, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])


def category_counts():
    with _con() as con:
        return dict(con.execute("SELECT category, COUNT(*) FROM notes GROUP BY category").fetchall())


# ---------- daily log ----------

def find_daily_log(day=None):
    day = (day or date.today()).isoformat()
    with _con() as con:
        r = con.execute("SELECT id FROM notes WHERE source=?", (f"daily:{day}",)).fetchone()
    return r["id"] if r else None


def daily_log(day=None):
    """One 'Journal' note per day; quick notes are appended to it with a timestamp. Created on first write."""
    day = (day or date.today()).isoformat()
    src = f"daily:{day}"
    existing = find_daily_log(date.fromisoformat(day))
    if existing:
        return existing
    title = "Daily log — " + datetime.strptime(day, "%Y-%m-%d").strftime("%A %b %d, %Y").replace(" 0", " ")
    return add("", title=title, category="Journal", tags=["daily-log"], note_date=day, source=src, organize=False)


def append_to_log(text, day=None):
    nid = daily_log(day)
    n = get(nid)
    stamp = datetime.now().strftime("%I:%M %p").lstrip("0")
    body = (n["body"].rstrip() + "\n" if n["body"].strip() else "") + f"- {stamp} — {text.strip()}"
    update(nid, body=body)
    with _con() as con:  # re-organize later so tags/actions pick up the new line
        con.execute("UPDATE notes SET ai_status='pending' WHERE id=?", (nid,))
    return nid


# ---------- import old notes (read-only) ----------

def _read_office(path, xml_name):
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read(xml_name))
    paras = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("p", "h"):  # odt paragraphs / headings, docx <w:p>
            paras.append("".join(el.itertext()).strip())
    return "\n".join(p for p in paras if p)


def read_note_file(path):
    ext = path.suffix.lower()
    if ext == ".odt":
        return _read_office(path, "content.xml")
    if ext == ".docx":
        return _read_office(path, "word/document.xml")
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def date_from_name(name, mtime):
    """'notes 9-25.txt' → 2026-09-25, 'notes 072226' → 2026-07-22; falls back to the file's date."""
    year = mtime.year
    m = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)", name)
    if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
        return date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat()
    m = re.search(r"(?<!\d)(\d{1,2})\s*[-_=/]\s*(\d{1,2})(?:\s*[-_=/]\s*(\d{2,4}))?(?!\d)", name)
    if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
        y = int(m.group(3)) if m.group(3) else year
        y = y + 2000 if y < 100 else y
        if not 2015 <= y <= year + 1:  # "10-5 - 10-6": the second date isn't a year
            y = year
        try:
            d = date(y, int(m.group(1)), int(m.group(2)))
            if d > mtime.date():  # "12-30" saved in January belongs to last year
                d = d.replace(year=d.year - 1)
            return d.isoformat()
        except ValueError:
            pass
    return mtime.date().isoformat()


def import_folder(folder=IMPORT_DIR, top_level_only=True):
    """Copy note text into the Daybook. Files on F: are only read. Re-running skips what's already imported."""
    folder = Path(folder)
    files = folder.iterdir() if top_level_only else folder.rglob("*")
    added, skipped = [], []
    for p in sorted(files):
        if not p.is_file() or p.suffix.lower() not in IMPORT_EXTS:
            continue
        if SECRET_WORDS.search(p.name):
            skipped.append((p.name, "looks like a credential"))
            continue
        src = f"file:{p}"
        if search_source(src):
            continue
        try:
            text = read_note_file(p).strip()
        except Exception as e:
            skipped.append((p.name, f"unreadable: {e}"))
            continue
        if not text:
            skipped.append((p.name, "empty"))
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        nid = add(text, title=p.stem, tags=["imported"], note_date=date_from_name(p.stem, mtime), source=src)
        added.append((nid, p.name))
    return added, skipped


def search_source(src):
    with _con() as con:
        return con.execute("SELECT id FROM notes WHERE source=?", (src,)).fetchone()


# ---------- local AI organizing ----------

def organize(nid):
    """qwen reads the note and fills title / category / tags / summary / topics / action items.
    The note body itself is never changed."""
    n = get(nid)
    if not n or not n["body"].strip():
        with _con() as con:
            con.execute("UPDATE notes SET ai_status='done' WHERE id=?", (nid,))
        return n
    keep_title = n["source"].startswith("daily:") or (n["title"] and not n["source"].startswith("file:"))
    prompt = f"""You organize a person's personal notes. They are a content creator (YouTube, TikTok, Facebook),
take notes during Discord calls and meetings, while watching YouTube, and jot down ideas and reminders.
Notes are messy, may mix several topics, and have typos. Note date: {n['note_date']}. File/title: "{n['title']}".

NOTE:
\"\"\"{n['body'][:6000]}\"\"\"

Return JSON:
- "title": short clear title (max 60 chars) naming the main subject(s)
- "category": exactly one of {json.dumps(CATEGORIES)}. Pick by what MOST of the note is:
    Meeting = notes from a call/meeting/Discord with other people (names, decisions, follow-ups)
    YouTube / Learning = lessons, quotes or takeaways from a video, book, course or teacher
    Idea = new business/app/product ideas and brainstorming
    To-do = mostly a list of tasks or reminders
    Journal = personal reflections, feelings, mindset, daily life
    Business = clients, money, marketing, sales, affiliate, partnerships
    Content = planning his own videos/posts/scripts/thumbnails
    Tech = code, AI tools, apps, setup, automation
    Personal = health, family, errands, anything else
- "tags": 3-6 lowercase tags (people, projects, platforms, themes), single words or hyphenated
- "summary": 1-2 sentences, what this note is about
- "topics": list of the separate subjects covered, each 2-6 words (1 item if the note is about one thing)
- "actions": list of concrete to-dos found in the note (imperative, short). [] if none. Do not invent any.
JSON only."""
    out = None
    for _ in range(3):
        try:
            out = nlp._ask_ollama(prompt)
            if out.get("category") in CATEGORIES:
                break
        except Exception:
            out = None
    if not out:
        with _con() as con:
            con.execute("UPDATE notes SET ai_status='failed' WHERE id=?", (nid,))
        return n
    raw_tags = out.get("tags") or []
    if isinstance(raw_tags, str):  # qwen sometimes returns "a, b, c" instead of a list
        raw_tags = re.split(r"[,;#]", raw_tags)
    tags = {re.sub(r"[^a-z0-9\-]", "", str(t).strip().lower().replace(" ", "-")).strip("-") for t in raw_tags}
    tags = sorted(t for t in tags if len(t) >= 2)
    tags = sorted(set(tags) | set(n["tags"]))
    fields = {
        "category": out.get("category") if out.get("category") in CATEGORIES else (n["category"] or "Personal"),
        "tags": ",".join(tags[:8]),
        "summary": str(out.get("summary", "")).strip()[:400],
        "topics": json.dumps([str(t).strip()[:60] for t in (out.get("topics") or [])][:8]),
        "actions": json.dumps([str(a).strip()[:140] for a in (out.get("actions") or []) if str(a).strip()][:12]),
        "ai_status": "done",
    }
    if not keep_title and str(out.get("title", "")).strip():
        fields["title"] = str(out["title"]).strip()[:80]
    if n["source"].startswith("daily:"):
        fields["category"] = "Journal"
    with _con() as con:
        con.execute(f"UPDATE notes SET {', '.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), nid))
    return get(nid)


def next_pending():
    with _con() as con:
        r = con.execute("SELECT id FROM notes WHERE ai_status='pending' ORDER BY id LIMIT 1").fetchone()
        return r["id"] if r else None


def reorganize(nid):
    with _con() as con:
        con.execute("UPDATE notes SET ai_status='pending' WHERE id=?", (nid,))


def stats():
    with _con() as con:
        return dict(con.execute("SELECT ai_status, COUNT(*) FROM notes GROUP BY ai_status").fetchall())
