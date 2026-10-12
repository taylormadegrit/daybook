"""Daybook dashboard — http://localhost:8503 (local only). Runs inside daemon.pyw."""
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from . import db, nlp, notes

PORT = 8503
STATIC = Path(__file__).resolve().parent.parent / "web"
app = Flask(__name__, static_folder=None)


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
