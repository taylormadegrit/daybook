"""Custom categories for reminders/tasks, automatic categorizing, and "Plan my day": today's flexible tasks
placed into free time (between routine blocks) by importance."""
import json
import re
import threading
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from . import db

bp = Blueprint("categories", __name__)
DEFAULTS = [{"name": "Work", "color": "#4fd1ff"}, {"name": "Content", "color": "#ff7ac6"}, {"name": "Personal", "color": "#3ee0a0"},
            {"name": "Health", "color": "#ffbe5c"}, {"name": "Learning", "color": "#8b7bff"}, {"name": "Errands", "color": "#a3e635"}]
KEYWORDS = {"Health": r"\b(meds?|insulin|doctor|dentist|gym|workout|walk|run|sleep|water|pills?|therapy|appointment)\b",
            "Content": r"\b(upload|post|video|shorts?|tiktok|youtube|reel|thumbnail|edit|record|stream|script|channel)\b",
            "Work": r"\b(client|meeting|call|email|invoice|contract|sponsor|deadline|report|project|team)\b",
            "Learning": r"\b(study|learn|read|course|class|lesson|homework|practice|research)\b",
            "Errands": r"\b(buy|pick up|groceries|store|pay|bill|bank|clean|laundry|order|return)\b"}


def categories():
    try:
        cats = json.loads(db.setting("categories") or "null")
    except Exception:
        cats = None
    return cats if isinstance(cats, list) and cats else DEFAULTS


def guess(text):
    """Pick one of the user's categories for a task: local AI (or Claude) if available, else keywords."""
    names = [c["name"] for c in categories()]
    try:
        from . import nlp
        out = nlp.ask_json(f'Pick the best category for this task from {json.dumps(names)}. Task: "{text[:300]}". '
                           'Also rate importance: "high", "normal" or "low". Return JSON {"category": "...", "importance": "..."}.')
        got = str(out.get("category", "")).strip().strip(".\"'").lower()
        cat = next((n for n in names if n.lower() == got), "") or (
            next((n for n in names if len(got) >= 3 and (n.lower() in got or got in n.lower())), "") if got else "")
        imp = {"high": 80, "normal": 50, "low": 25}.get(str(out.get("importance", "")).lower())
        if cat:
            return cat, imp
    except Exception:
        pass
    for name, pat in KEYWORDS.items():
        if name in names and re.search(pat, text, re.I):
            return name, None
    for name in names:  # custom categories: a word of the name in the task ("Ori uploads" ← "upload the ori short")
        if name not in KEYWORDS and any(len(w) >= 4 and re.search(r"\b" + re.escape(w[:max(4, len(w) - 1)].lower()), text, re.I)
                                        for w in re.findall(r"\w+", name)):
            return name, None
    return "", None


def auto_categorize(rid):
    """Background: give a new reminder a category (and an importance guess) unless the user picked one."""
    def run():
        r = db.get(rid)
        if not r or r["category"]:
            return
        cat, imp = guess(r["text"])
        fields = {}
        if cat:
            fields["category"] = cat
        if imp is not None and r["importance"] == 50 and not r["priority"]:
            fields["importance"] = imp
        if fields:
            db.update(rid, **fields)
    threading.Thread(target=run, daemon=True).start()


# ---------- Plan my day ----------
DAY_START, DAY_END, SLOT_MIN = 8, 22, 30


def plan(day, order=None, include=None, minutes=None):
    """Flexible tasks = one-off, not a time block, still open, due that day (or overdue if planning today).
    They're placed in importance order (or the order you dragged them into) into free gaps between blocks."""
    now = datetime.now().replace(second=0, microsecond=0)
    start = datetime(day.year, day.month, day.day, DAY_START)
    if day == now.date():
        start = max(start, now + timedelta(minutes=15 - now.minute % 15))
    end = datetime(day.year, day.month, day.day, DAY_END)
    busy, tasks = [], []
    for when, r in db.occurrences_on(day):
        if r["ends"]:
            h, m = map(int, r["ends"].split(":"))
            busy.append((when, when.replace(hour=h, minute=m)))
        elif not r["repeat"]:
            tasks.append((when, r))
    if day == now.date():  # overdue one-off tasks get planned into today too
        with db.connect() as con:
            for r in con.execute("SELECT * FROM reminders WHERE status='open' AND repeat='' AND ends='' AND due < ?", (db.fmt(start.replace(hour=0, minute=0)),)):
                tasks.append((db.parse_dt(r["due"]), r))
    by_id = {r["id"]: (w, r) for w, r in tasks}
    ids = list(by_id)
    if order:
        ids = [i for i in order if i in by_id] + [i for i in ids if i not in order]
    else:
        ids.sort(key=lambda i: (-by_id[i][1]["importance"], by_id[i][0]))
    busy.sort()
    out, cursor = [], start
    for i in ids:
        when, r = by_id[i]
        use = include is None or i in include
        dur = timedelta(minutes=int((minutes or {}).get(str(i), SLOT_MIN)))
        slot = None
        if use:
            t = cursor
            while t + dur <= end:
                clash = next((b for b in busy if t < b[1] and t + dur > b[0]), None)
                if not clash:
                    slot = t
                    break
                t = clash[1]
            if slot:
                busy.append((slot, slot + dur))
                busy.sort()
                cursor = slot + dur
        out.append({"id": i, "text": r["text"], "category": r["category"], "importance": r["importance"], "now": db.fmt(when),
                    "slot": db.fmt(slot) if slot else None, "include": use, "minutes": int(dur.total_seconds() // 60)})
    blocks = [{"from": db.fmt(a), "to": db.fmt(b)} for a, b in busy]
    return {"date": day.isoformat(), "start": db.fmt(start), "end": db.fmt(end), "tasks": out, "busy": blocks}


@bp.get("/api/categories")
def c_list():
    with db.connect() as con:
        counts = {r["category"]: r["n"] for r in con.execute("SELECT category, COUNT(*) n FROM reminders WHERE status='open' GROUP BY category")}
    return jsonify(categories=categories(), counts=counts)


@bp.post("/api/categories")
def c_save():
    """Save the list. {"rename": {"old": "new"}} also moves reminders; deleted categories leave their reminders uncategorized."""
    j = request.get_json() or {}
    cats = [{"name": str(c.get("name", "")).strip()[:40], "color": str(c.get("color", "#8b7bff"))[:9]} for c in j.get("categories", []) if str(c.get("name", "")).strip()]
    seen, clean = set(), []
    for c in cats:
        if c["name"].lower() not in seen:
            seen.add(c["name"].lower())
            clean.append(c)
    with db.connect() as con:
        for old, new in (j.get("rename") or {}).items():
            con.execute("UPDATE reminders SET category=? WHERE category=?", (str(new).strip()[:40], old))
        for gone in j.get("removed") or []:
            con.execute("UPDATE reminders SET category='' WHERE category=?", (gone,))
    db.set_settings({"categories": json.dumps(clean)})
    return jsonify(categories=clean)


@bp.post("/api/plan")
def p_plan():
    j = request.get_json() or {}
    day = date.fromisoformat(j.get("date") or date.today().isoformat())
    include = set(j["include"]) if isinstance(j.get("include"), list) else None
    return jsonify(plan(day, j.get("order"), include, j.get("minutes")))


@bp.post("/api/plan/apply")
def p_apply():
    """Move the included tasks to their slots. Importance changes only if you dragged the list into a new order,
    and only for the tasks you kept in the plan (top = most important)."""
    j = request.get_json() or {}
    day, include = date.fromisoformat(j["date"]), set(j.get("include") or [])
    p = plan(day, j.get("order"), include, j.get("minutes"))
    picked = [t["id"] for t in p["tasks"] if t["include"]]
    default = [t["id"] for t in plan(day, None, include, j.get("minutes"))["tasks"] if t["include"]]
    reordered = picked != default
    n = len(picked)
    for t in p["tasks"]:
        fields = {}
        if reordered and t["include"] and n > 1:
            fields["importance"] = round(90 - picked.index(t["id"]) * (70 / (n - 1)))
        if t["include"] and t["slot"]:
            fields["due"] = db.parse_dt(t["slot"])
        if fields:
            db.update(t["id"], **fields)
    p["reordered"] = reordered
    return jsonify(p)
