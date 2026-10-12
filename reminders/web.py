"""Daybook dashboard — http://localhost:8503 (local only). Runs inside daemon.pyw."""
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory

from . import db, nlp, notes

PORT = 8503
STATIC = Path(__file__).resolve().parent.parent / "web"
app = Flask(__name__, static_folder=None)

from .chat import bp as chat_bp  # noqa: E402

app.register_blueprint(chat_bp)


STARTED = datetime.now()
VERSION = "1.0"


@app.get("/chat")
def chat_page():  # chat now lives inside the main app
    return redirect("/#chat")


@app.get("/brand/<path:name>")
def brand(name):
    return send_from_directory(STATIC / "brand", name)


@app.get("/manifest.webmanifest")
def manifest():
    return jsonify(name="Daybook", short_name="Daybook", description="Local AI Hub for Notes, Reminders & Scheduling",
                   start_url="/#today", display="standalone", background_color="#0a0b10", theme_color="#0a0b10",
                   icons=[{"src": "/brand/icon-192.png", "sizes": "192x192", "type": "image/png"},
                          {"src": "/brand/icon-256.png", "sizes": "256x256", "type": "image/png"}])


@app.get("/api/settings")
def get_settings():
    return jsonify(db.settings())


@app.patch("/api/settings")
def save_settings():
    j = request.get_json() or {}
    if "agenda_hour" in j and not (0 <= int(j["agenda_hour"]) <= 23):
        return jsonify(error="Agenda hour must be 0–23"), 400
    if "nag_minutes" in j and not (1 <= int(j["nag_minutes"]) <= 120):
        return jsonify(error="Nag interval must be 1–120 minutes"), 400
    db.set_settings(j)
    return jsonify(db.settings())


@app.get("/api/status")
def status():
    from . import chat as chat_mod
    models = chat_mod.model_list()
    mcp = False
    try:
        mcp = '"reminders"' in (Path.home() / ".claude.json").read_text(encoding="utf-8")
    except Exception:
        pass
    open_now = db.list_open()
    return jsonify(
        version=VERSION, started=db.fmt(STARTED), ollama=bool(models), models=models,
        orca=Path(r"D:\Applications\Orca\resources\bin\orca.exe").exists(), claude_mcp=mcp,
        data=str(db.DB_PATH), counts={"reminders": len(open_now), "routine": sum(1 for r in open_now if r["repeat"]),
                                       "notes": sum(notes.category_counts().values()), "ai": notes.stats()})


@app.get("/api/calendar")
def calendar_range():
    start = date.fromisoformat(request.args.get("start") or date.today().isoformat())
    days = min(int(request.args.get("days", 7)), 42)
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        out.append({"date": d.isoformat(), "items": [_rem(r, w) for w, r in db.occurrences_on(d)],
                    "log": bool(notes.find_daily_log(d))})
    return jsonify(out)


@app.get("/api/search")
def search_all():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(notes=[], reminders=[], chats=[])
    from . import chat as chat_mod
    ql = q.lower()
    try:
        found = notes.search(q, limit=8)
    except Exception:
        found = []
    with chat_mod._con() as con:
        chats = [dict(r) for r in con.execute("SELECT id, title FROM chats WHERE title LIKE ? ORDER BY updated DESC LIMIT 5",
                                              (f"%{q}%",))]
    return jsonify(notes=[{"id": n["id"], "title": n["title"], "category": n["category"], "date": n["note_date"]} for n in found],
                   reminders=[_rem(r) for r in db.list_open() if ql in r["text"].lower()][:8], chats=chats)


@app.get("/api/hardware")
def hardware():
    from . import models_hub
    return jsonify(models_hub.scan())


@app.get("/api/models/recommend")
def model_recs():
    from . import models_hub
    try:
        return jsonify(models_hub.recommend(models_hub.scan(), force=request.args.get("refresh") == "1"))
    except Exception as e:
        return jsonify(error=f"Couldn't reach Hugging Face — check your internet connection. ({e})"), 503


@app.get("/api/models/installed")
def models_installed():
    from . import chat as chat_mod
    try:
        tags = chat_mod.ollama("/api/tags")["models"]
    except Exception:
        return jsonify(ollama=False, models=[])
    return jsonify(ollama=True, models=[{"name": m["name"], "size_gb": round(m["size"] / 1e9, 2),
                                         "params": m["details"].get("parameter_size"), "quant": m["details"].get("quantization_level"),
                                         "modified": m.get("modified_at", "")[:10]} for m in tags])


@app.post("/api/models/pull")
def model_pull():
    """Stream Ollama's download progress as server-sent events."""
    import json as _json
    from . import chat as chat_mod
    name = (request.get_json() or {}).get("name", "")
    if not name.startswith("hf.co/") and ":" not in name:
        return jsonify(error="bad model name"), 400

    def gen():
        try:
            with chat_mod.ollama("/api/pull", {"model": name, "stream": True}, stream=True) as resp:
                for line in resp:
                    if line.strip():
                        j = _json.loads(line)
                        if j.get("error"):
                            yield f"event: error\ndata: {_json.dumps({'message': j['error']})}\n\n"
                            return
                        yield f"event: progress\ndata: {_json.dumps(j)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"
    return app.response_class(gen(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.delete("/api/models/<path:name>")
def model_delete(name):
    import json as _json
    import urllib.request as _u
    req = _u.Request("http://localhost:11434/api/delete", _json.dumps({"model": name}).encode(),
                     {"Content-Type": "application/json"}, method="DELETE")
    try:
        _u.urlopen(req, timeout=30).read()
    except Exception as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True)


@app.get("/api/claude")
def claude_status():
    from . import claude_link
    return jsonify(claude_link.status())


@app.post("/api/claude/<action>/<target>")
def claude_action(action, target):
    from . import claude_link
    try:
        if action == "connect":
            msg = claude_link.connect_code() if target == "code" else claude_link.connect_desktop()
        elif action == "disconnect":
            msg = claude_link.disconnect(target)
        else:
            return jsonify(error="unknown action"), 400
    except Exception as e:
        return jsonify(error=str(e)), 400
    return jsonify(message=msg, status=claude_link.status())


@app.post("/api/notes/reorganize-all")
def reorganize_all():
    with notes._con() as con:
        n = con.execute("UPDATE notes SET ai_status='pending' WHERE trim(body) != ''").rowcount
    return jsonify(queued=n)


@app.post("/api/test-popup")
def test_popup():
    rid = db.add("Test pop-up — press Done", datetime.now() + timedelta(seconds=5),
                 notes="If you can see this, pop-ups are working.")
    return jsonify(id=rid)


@app.post("/api/parse")
def parse_preview():
    """Live preview of a plain-English reminder before saving it."""
    text = (request.get_json() or {}).get("text", "").strip()
    if len(text) < 3:
        return jsonify(ok=False)
    p = nlp.parse(text)
    return jsonify(ok=True, text=p["text"], due=db.fmt(p["due"]), repeat=p["repeat"], priority=p["priority"],
                   guessed=bool(p.get("guessed_time")))


def _rem(r, when=None):
    due = when or db.parse_dt(r["due"])
    return {"id": r["id"], "text": r["text"], "due": db.fmt(due), "repeat": r["repeat"], "ends": r["ends"],
            "priority": r["priority"], "notes": r["notes"],
            "is_current": db.parse_dt(r["due"]) == due}  # only the live occurrence can be ticked off


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/api/today")
def today():
    day = date.fromisoformat(request.args.get("date") or date.today().isoformat())
    now = datetime.now()
    overdue = [_rem(r) for r in db.list_open(until=now) if db.parse_dt(r["due"]).date() < day] \
        if day == date.today() else []
    log_id = notes.find_daily_log(day)  # don't create empty logs just by looking at a day
    log = notes.get(log_id) if log_id else {"id": None, "body": "", "tags": []}
    return jsonify(date=day.isoformat(), now=db.fmt(now), overdue=overdue,
                   timeline=[_rem(r, when) for when, r in db.occurrences_on(day)], log=log)


@app.get("/api/reminders")
def reminders():
    if request.args.get("status") == "done":
        return jsonify([_rem(r) | {"completed": r["completed"]} for r in db.list_recent_done(100)])
    return jsonify([_rem(r) for r in db.list_open()])


@app.post("/api/reminders")
def add_reminder():
    j = request.get_json()
    try:
        if j.get("natural"):
            p = nlp.parse(j["natural"])
            rid = db.add(p["text"], p["due"], p["repeat"], p["priority"], ends=j.get("ends", ""))
        else:
            due = db.parse_dt(j["due"]) if "T" in j["due"] else nlp.when(j["due"])
            rid = db.add(j["text"], due, j.get("repeat", ""), j.get("priority", 0), j.get("notes", ""), j.get("ends", ""))
    except Exception as e:
        return jsonify(error=str(e)), 400
    return jsonify(_rem(db.get(rid)))


@app.patch("/api/reminders/<int:rid>")
def edit_reminder(rid):
    j = request.get_json()
    try:
        if j.get("due"):
            j["due"] = db.parse_dt(j["due"])
        db.update(rid, **j)
    except Exception as e:
        return jsonify(error=str(e)), 400
    return jsonify(_rem(db.get(rid)))


@app.post("/api/reminders/<int:rid>/done")
def done_reminder(rid):
    return jsonify(result=db.complete(rid))


@app.post("/api/reminders/<int:rid>/snooze")
def snooze_reminder(rid):
    minutes = int(request.get_json().get("minutes", 10))
    db.snooze(rid, datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=minutes))
    return jsonify(_rem(db.get(rid)))


@app.delete("/api/reminders/<int:rid>")
def delete_reminder(rid):
    db.delete(rid)
    return jsonify(ok=True)


@app.get("/api/meta")
def meta():
    return jsonify(categories=notes.CATEGORIES, templates=notes.TEMPLATES, tags=notes.all_tags()[:60],
                   counts=notes.category_counts(), ai=notes.stats())


@app.get("/api/notes")
def list_notes():
    a = request.args
    return jsonify(notes.search(a.get("q", ""), a.get("category", ""), a.get("tag", ""),
                                a.get("from", ""), a.get("to", "")))


@app.get("/api/notes/<int:nid>")
def get_note(nid):
    return jsonify(notes.get(nid))


@app.post("/api/notes")
def add_note():
    j = request.get_json()
    nid = notes.add(j.get("body", ""), j.get("title", ""), j.get("category", ""), j.get("tags", []),
                    j.get("note_date") or None)
    return jsonify(notes.get(nid))


@app.patch("/api/notes/<int:nid>")
def edit_note(nid):
    j = request.get_json()
    notes.update(nid, **j)
    if "body" in j and j.get("reorganize", True):
        notes.reorganize(nid)
    return jsonify(notes.get(nid))


@app.delete("/api/notes/<int:nid>")
def delete_note(nid):
    notes.delete(nid)
    return jsonify(ok=True)


@app.post("/api/notes/<int:nid>/organize")
def organize_note(nid):
    return jsonify(notes.organize(nid))


@app.post("/api/notes/<int:nid>/remind")
def action_to_reminder(nid):
    """Turn an action item into a reminder: {"text": "...", "when": "tomorrow 9am"}"""
    j = request.get_json()
    due = nlp.when(j.get("when") or "tomorrow 9am")
    rid = db.add(j["text"], due, notes=f"From note #{nid}")
    return jsonify(_rem(db.get(rid)))


@app.post("/api/log")
def log():
    nid = notes.append_to_log(request.get_json()["text"])
    return jsonify(notes.get(nid))


@app.post("/api/import")
def run_import():
    added, skipped = notes.import_folder()
    return jsonify(added=len(added), skipped=skipped)


def serve():
    app.run(host="127.0.0.1", port=PORT, threaded=True, use_reloader=False)
