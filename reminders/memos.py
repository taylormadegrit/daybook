"""Voice memos: record in Daybook or import audio from a phone (m4a/mp3/wav/…). Each memo gets a name,
labels and a date like a journal entry, and is transcribed locally in the background (faster-whisper).
Untitled memos get a short title + labels from the local AI once the transcript is ready."""
import json
import queue
import threading
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from . import db

bp = Blueprint("memos", __name__)
MEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "memos"
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".webm", ".ogg", ".opus", ".aac", ".flac", ".mp4", ".3gp", ".amr", ".caf", ".qta", ".mkv", ".mov"}
VIDEO_EXT = {".mkv", ".mov", ".mp4"}  # .webm can be either — the uploader says which
LABELS = ["Journal", "Idea", "Meeting", "To-do", "Lyrics", "Content", "Personal", "Learning"]
JOBS = queue.Queue()
TS = "%Y-%m-%dT%H:%M:%S"


def _con():
    con = db.connect()
    con.execute("""CREATE TABLE IF NOT EXISTS memos (id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
        labels TEXT NOT NULL DEFAULT '[]', memo_date TEXT NOT NULL, file TEXT NOT NULL, original TEXT NOT NULL DEFAULT '',
        duration REAL NOT NULL DEFAULT 0, size INTEGER NOT NULL DEFAULT 0, transcript TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', source TEXT NOT NULL DEFAULT 'recorded',
        starred INTEGER NOT NULL DEFAULT 0, auto_title INTEGER NOT NULL DEFAULT 0, note_id INTEGER, created TEXT NOT NULL)""")
    cols = {r["name"] for r in con.execute("PRAGMA table_info(memos)")}
    if "kind" not in cols:  # video notes (built-in recorder / OBS) share the library
        con.execute("ALTER TABLE memos ADD COLUMN kind TEXT NOT NULL DEFAULT 'audio'")
        con.execute("ALTER TABLE memos ADD COLUMN path TEXT NOT NULL DEFAULT ''")  # external file (OBS) — left in place
    return con


def media(m):
    return Path(m["path"]) if m.get("path") else MEMO_DIR / m["file"]


def _dict(r):
    d = dict(r)
    d["labels"] = json.loads(d["labels"] or "[]")
    return d


def get(mid):
    with _con() as con:
        r = con.execute("SELECT * FROM memos WHERE id=?", (mid,)).fetchone()
        return _dict(r) if r else None


def _duration(path):
    try:
        import av
        with av.open(str(path)) as c:
            if c.duration:
                return round(c.duration / 1_000_000, 1)
            s = c.streams.audio[0]
            return round(float(s.duration * s.time_base), 1)
    except Exception:
        return 0


def add(data, filename, title="", labels=(), memo_date=None, source="recorded", kind=None):
    ext = Path(filename).suffix.lower() or ".webm"
    kind = kind if kind in ("audio", "video") else ("video" if ext in VIDEO_EXT else "audio")
    if ext not in AUDIO_EXT:
        raise ValueError(f"{ext} isn't an audio format Daybook knows")
    MEMO_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime(TS)
    with _con() as con:
        cur = con.execute("INSERT INTO memos (title, labels, memo_date, file, original, size, source, auto_title, created, kind) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (title.strip(), json.dumps([lbl for lbl in labels if lbl]), memo_date or now, "", filename,
                           len(data), source, int(not title.strip()), now, kind))
        mid = cur.lastrowid
        fname = f"memo{mid}{ext}"
        (MEMO_DIR / fname).write_bytes(data)
        con.execute("UPDATE memos SET file=?, duration=? WHERE id=?", (fname, _duration(MEMO_DIR / fname), mid))
    JOBS.put(mid)
    return mid


def add_file(path, title="", labels=(), source="obs"):
    """Index a recording that already exists on disk (e.g. OBS output) without copying it."""
    p = Path(path)
    now = datetime.now().strftime(TS)
    with _con() as con:
        cur = con.execute("INSERT INTO memos (title, labels, memo_date, file, original, size, source, auto_title, created, kind, path, duration) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                          (title.strip(), json.dumps([lbl for lbl in labels if lbl]),
                           datetime.fromtimestamp(p.stat().st_mtime).strftime(TS), p.name, p.name, p.stat().st_size, source,
                           int(not title.strip()), now, "video" if p.suffix.lower() in VIDEO_EXT | {".webm", ".flv", ".ts"} else "audio",
                           str(p), _duration(p)))
        mid = cur.lastrowid
    JOBS.put(mid)
    return mid


def update(mid, **f):
    f = {k: v for k, v in f.items() if k in ("title", "labels", "memo_date", "transcript", "notes", "starred")}
    if "labels" in f:
        f["labels"] = json.dumps([str(x).strip() for x in f["labels"] if str(x).strip()][:12])
    if "title" in f:
        f["auto_title"] = 0
    if f:
        with _con() as con:
            con.execute(f"UPDATE memos SET {', '.join(k + '=?' for k in f)} WHERE id=?", (*f.values(), mid))


def delete(mid):
    m = get(mid)
    if m:
        if not m["path"]:  # OBS recordings stay where OBS saved them
            (MEMO_DIR / m["file"]).unlink(missing_ok=True)
        with _con() as con:
            con.execute("DELETE FROM memos WHERE id=?", (mid,))


def listing(q="", label="", kind=""):
    sql, args = "SELECT * FROM memos WHERE 1=1", []
    if kind:
        sql += " AND kind=?"
        args.append(kind)
    if q:
        sql += " AND (title LIKE ? OR transcript LIKE ? OR notes LIKE ? OR labels LIKE ?)"
        args += [f"%{q}%"] * 4
    if label:
        sql += " AND labels LIKE ?"
        args.append(f'%"{label}"%')
    with _con() as con:
        return [_dict(r) for r in con.execute(sql + " ORDER BY memo_date DESC", args)]


def all_labels():
    seen = {}
    for m in listing():
        for lbl in m["labels"]:
            seen[lbl] = seen.get(lbl, 0) + 1
    return sorted(seen.items(), key=lambda x: -x[1])


def _auto_title(mid, transcript):
    from . import nlp
    try:
        out = nlp._ask_ollama(
            "Give this voice memo a short title (max 6 words) and 1-2 labels chosen from "
            f"{LABELS}. Reply as JSON {{\"title\": \"...\", \"labels\": [\"...\"]}}.\n\nMemo:\n{transcript[:3000]}")
        title = str(out.get("title", "")).strip().strip('"')[:70]
        labels = [lbl for lbl in out.get("labels", []) if lbl in LABELS][:2]
        m = get(mid)
        if title and m and m["auto_title"]:
            with _con() as con:
                con.execute("UPDATE memos SET title=?, labels=CASE WHEN labels='[]' THEN ? ELSE labels END WHERE id=?",
                            (title, json.dumps(labels), mid))
    except Exception:
        pass


def worker():
    """Background thread: transcribe new memos one at a time."""
    from . import stt
    with _con() as con:  # anything left over from last run
        for r in con.execute("SELECT id FROM memos WHERE status IN ('pending','working')"):
            JOBS.put(r["id"])
    while True:
        mid = JOBS.get()
        m = get(mid)
        if not m:
            continue
        with _con() as con:
            con.execute("UPDATE memos SET status='working' WHERE id=?", (mid,))
        try:
            p = media(m)
            res = stt.transcribe(p, p.suffix)
            with _con() as con:
                con.execute("UPDATE memos SET transcript=?, status='done', duration=CASE WHEN duration=0 THEN ? ELSE duration END "
                            "WHERE id=?", (res["text"], res["seconds"], mid))
            if m["auto_title"] and res["text"]:
                _auto_title(mid, res["text"])
        except Exception as e:
            with _con() as con:
                con.execute("UPDATE memos SET status='error', notes=CASE WHEN notes='' THEN ? ELSE notes END WHERE id=?",
                            (f"Couldn't transcribe: {e}", mid))


def start_worker():
    threading.Thread(target=worker, daemon=True).start()


# ---------------- routes ----------------

@bp.get("/api/memos")
def memos_list():
    return jsonify(items=listing(request.args.get("q", ""), request.args.get("label", ""), request.args.get("kind", "")),
                   labels=all_labels(), suggested=LABELS)


@bp.post("/api/memos")
def memos_add():
    files = request.files.getlist("audio")
    if not files:
        return jsonify(error="No audio file"), 400
    added, errors = [], []
    for f in files:
        try:
            when = request.form.get("date") or ""
            lm = request.form.get(f"modified_{f.filename}")  # phone files keep their recording time
            if not when and lm:
                when = datetime.fromtimestamp(int(lm) / 1000).strftime(TS)
            title = request.form.get("title", "")
            if not title and request.form.get("source") == "imported":
                stem = Path(f.filename).stem
                title = "" if stem.lower().startswith(("new recording", "recording", "voice", "audio", "memo", "rec_", "ptt-")) else stem
            added.append(add(f.read(), f.filename, title, json.loads(request.form.get("labels", "[]")),
                             when or None, request.form.get("source", "recorded"), request.form.get("kind")))
        except Exception as e:
            errors.append(f"{f.filename}: {e}")
    return jsonify(added=added, errors=errors)


@bp.get("/api/memos/<int:mid>")
def memo_get(mid):
    m = get(mid)
    return (jsonify(m), 200) if m else (jsonify(error="not found"), 404)


@bp.patch("/api/memos/<int:mid>")
def memo_edit(mid):
    update(mid, **(request.get_json() or {}))
    return jsonify(get(mid))


@bp.delete("/api/memos/<int:mid>")
def memo_delete(mid):
    delete(mid)
    return jsonify(ok=True)


@bp.post("/api/memos/<int:mid>/retranscribe")
def memo_retranscribe(mid):
    with _con() as con:
        con.execute("UPDATE memos SET status='pending' WHERE id=?", (mid,))
    JOBS.put(mid)
    return jsonify(ok=True)


@bp.post("/api/memos/<int:mid>/to-note")
def memo_to_note(mid):
    from . import notes
    m = get(mid)
    if not m:
        return jsonify(error="not found"), 404
    when = datetime.strptime(m["memo_date"][:19], TS)
    body = (f"{'🎬 Video note' if m['kind'] == 'video' else '🎙️ Voice memo'} · {when:%b %d, %Y %I:%M %p} · {int(m['duration'] // 60)}:{int(m['duration'] % 60):02d}\n\n"
            + (m["transcript"] or "") + (f"\n\n## My notes\n{m['notes']}" if m["notes"] else ""))
    cat = {"Journal": "Journal", "Idea": "Idea", "Meeting": "Meeting", "To-do": "To-do", "Content": "Content",
           "Learning": "YouTube / Learning", "Personal": "Personal"}
    nid = notes.add(body, m["title"], next((cat[lbl] for lbl in m["labels"] if lbl in cat), "Journal"),
                    [lbl.lower() for lbl in m["labels"]] + ["video-note" if m["kind"] == "video" else "voice-memo"], when.date().isoformat())
    with _con() as con:
        con.execute("UPDATE memos SET note_id=? WHERE id=?", (nid, mid))
    return jsonify(note_id=nid)


@bp.get("/memo-media/<int:mid>")
def memo_media(mid):
    from flask import send_file
    m = get(mid)
    if not m or not media(m).exists():
        return ("", 404)
    return send_file(media(m), conditional=True)


@bp.get("/memo-audio/<path:name>")
def memo_audio(name):
    return send_from_directory(MEMO_DIR, Path(name).name, conditional=True)
