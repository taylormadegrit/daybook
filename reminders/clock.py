"""Clock: alarms and countdown timers that live in the background service, so they ring with a
sound + pop-up even when the Daybook window is closed. The stopwatch and world clock are client-side."""
import math
import struct
import wave
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from . import db, paths

bp = Blueprint("clock", __name__)
SOUND_DIR = paths.DATA / "sounds"
SOUNDS = ["Radar", "Chimes", "Beacon", "Bell", "Gentle", "Pulse"]
TS = "%Y-%m-%dT%H:%M:%S"


def _con():
    con = db.connect()
    con.execute("""CREATE TABLE IF NOT EXISTS alarms (id INTEGER PRIMARY KEY, time TEXT NOT NULL, label TEXT NOT NULL DEFAULT '',
        days TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1, sound TEXT NOT NULL DEFAULT 'Radar',
        snooze INTEGER NOT NULL DEFAULT 1, snoozed_until TEXT, last_fired TEXT, ringing INTEGER NOT NULL DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS timers (id INTEGER PRIMARY KEY, label TEXT NOT NULL DEFAULT '', seconds INTEGER NOT NULL,
        ends TEXT, remaining INTEGER, state TEXT NOT NULL DEFAULT 'running', sound TEXT NOT NULL DEFAULT 'Chimes',
        created TEXT NOT NULL, finished TEXT)""")
    return con


def _now():
    return datetime.now().replace(microsecond=0)


# ---------------- sounds (generated once, no downloads) ----------------

def ensure_sounds():
    SOUND_DIR.mkdir(parents=True, exist_ok=True)
    rate = 22050

    def tone(freq, dur, vol=0.5, decay=4.0, harm=(1.0,)):
        n = int(rate * dur)
        return [vol * math.exp(-decay * i / rate) * sum(a * math.sin(2 * math.pi * freq * (k + 1) * i / rate)
                                                         for k, a in enumerate(harm)) / sum(harm) for i in range(n)]

    def silence(d):
        return [0.0] * int(rate * d)

    recipes = {
        "Radar": lambda: (tone(1320, .12, .55, 6) + silence(.06) + tone(1320, .12, .55, 6) + silence(.06)
                          + tone(1320, .12, .55, 6) + silence(.06) + tone(1320, .12, .55, 6) + silence(.7)),
        "Chimes": lambda: tone(1046.5, .45, .5, 5, (1, .4, .2)) + tone(1318.5, .45, .5, 5, (1, .4, .2))
                          + tone(1568, .9, .5, 3.5, (1, .4, .2)) + silence(.5),
        "Beacon": lambda: tone(880, .25, .5, 2) + tone(660, .25, .5, 2) + tone(880, .25, .5, 2) + silence(.8),
        "Bell": lambda: tone(523.25, 1.8, .6, 1.8, (1, .6, .35, .2, .1)) + silence(.3),
        "Gentle": lambda: tone(523.25, .7, .35, 2.5, (1, .3)) + tone(659.25, .7, .35, 2.5, (1, .3))
                          + tone(783.99, 1.2, .35, 2, (1, .3)) + silence(1.2),
        "Pulse": lambda: (tone(740, .09, .5, 3) + silence(.09)) * 6 + silence(.6),
    }
    for name, make in recipes.items():
        p = SOUND_DIR / f"{name}.wav"
        if p.exists():
            continue
        data = make()
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in data))


# ---------------- alarms ----------------

def _alarm_dict(r):
    d = dict(r)
    d["days"] = [int(x) for x in d["days"].split(",") if x != ""]  # 0=Mon … 6=Sun; [] = once
    d["next"] = next_ring(d)
    return d


def next_ring(a, now=None):
    """Next datetime this alarm rings (None when disabled)."""
    if not a["enabled"]:
        return None
    now = now or _now()
    if a.get("snoozed_until"):
        return a["snoozed_until"]
    h, m = map(int, a["time"].split(":"))
    days = a["days"] if isinstance(a["days"], list) else [int(x) for x in a["days"].split(",") if x != ""]
    for add in range(8):
        cand = (now + timedelta(days=add)).replace(hour=h, minute=m, second=0)
        if cand > now and (not days or cand.weekday() in days):
            return cand.strftime(TS)
    return None


def alarms():
    with _con() as con:
        return [_alarm_dict(r) for r in con.execute("SELECT * FROM alarms ORDER BY time")]


def alarm_save(j, aid=None):
    fields = {}
    if "time" in j:
        datetime.strptime(j["time"], "%H:%M")
        fields["time"] = j["time"]
    if "label" in j:
        fields["label"] = str(j["label"])[:80]
    if "days" in j:
        fields["days"] = ",".join(str(int(d)) for d in sorted(set(j["days"])) if 0 <= int(d) <= 6)
    if "enabled" in j:
        fields["enabled"] = int(bool(j["enabled"]))
        fields["snoozed_until"] = None
    if "sound" in j and j["sound"] in SOUNDS:
        fields["sound"] = j["sound"]
    if "snooze" in j:
        fields["snooze"] = int(bool(j["snooze"]))
    if "time" in fields or fields.get("enabled"):  # don't ring for a minute that already started
        with _con() as con:
            cur_t = fields.get("time") or (con.execute("SELECT time FROM alarms WHERE id=?", (aid,)).fetchone() or ["07:00"])[0]
        h, m = map(int, cur_t.split(":"))
        slot = _now().replace(hour=h, minute=m, second=0)
        fields["last_fired"] = slot.strftime(TS) if slot <= _now() else None
        fields["ringing"] = 0
    with _con() as con:
        if aid is None:
            fields.setdefault("time", "07:00")
            cur = con.execute(f"INSERT INTO alarms ({', '.join(fields)}) VALUES ({', '.join('?' * len(fields))})",
                              tuple(fields.values()))
            aid = cur.lastrowid
        elif fields:
            con.execute(f"UPDATE alarms SET {', '.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), aid))
        return _alarm_dict(con.execute("SELECT * FROM alarms WHERE id=?", (aid,)).fetchone())


def alarm_stop(aid, snooze_min=0):
    with _con() as con:
        a = con.execute("SELECT * FROM alarms WHERE id=?", (aid,)).fetchone()
        if not a:
            return
        if snooze_min:
            con.execute("UPDATE alarms SET ringing=0, snoozed_until=? WHERE id=?",
                        ((_now() + timedelta(minutes=snooze_min)).strftime(TS), aid))
        else:  # one-time alarms switch themselves off after ringing, like the iPhone
            con.execute("UPDATE alarms SET ringing=0, snoozed_until=NULL, enabled=CASE WHEN days='' THEN 0 ELSE enabled END "
                        "WHERE id=?", (aid,))


# ---------------- timers ----------------

def _timer_dict(r):
    d = dict(r)
    if d["state"] == "running":
        d["left"] = max(0, round((datetime.strptime(d["ends"], TS) - datetime.now()).total_seconds()))
    elif d["state"] == "paused":
        d["left"] = d["remaining"]
    else:
        d["left"] = 0
    return d


def timers(include_old=False):
    with _con() as con:
        q = "SELECT * FROM timers" + ("" if include_old else " WHERE state IN ('running','paused','ringing')") + " ORDER BY id DESC"
        return [_timer_dict(r) for r in con.execute(q)]


def recents(limit=8):
    """Recently used durations (iPhone 'Recents') — distinct label+length."""
    seen, out = set(), []
    with _con() as con:
        for r in con.execute("SELECT label, seconds, sound FROM timers ORDER BY id DESC LIMIT 60"):
            k = (r["label"], r["seconds"])
            if k not in seen:
                seen.add(k)
                out.append(dict(r))
            if len(out) >= limit:
                break
    return out


def timer_start(seconds, label="", sound="Chimes"):
    seconds = max(1, min(int(seconds), 99 * 3600))
    with _con() as con:
        cur = con.execute("INSERT INTO timers (label, seconds, ends, state, sound, created) VALUES (?,?,?,?,?,?)",
                          (str(label)[:80], seconds, (_now() + timedelta(seconds=seconds)).strftime(TS), "running",
                           sound if sound in SOUNDS else "Chimes", _now().strftime(TS)))
        return cur.lastrowid


def timer_action(tid, action, amount=60):
    with _con() as con:
        t = con.execute("SELECT * FROM timers WHERE id=?", (tid,)).fetchone()
        if not t:
            return None
        left = _timer_dict(t)["left"]
        if action == "pause" and t["state"] == "running":
            con.execute("UPDATE timers SET state='paused', remaining=?, ends=NULL WHERE id=?", (left, tid))
        elif action == "resume" and t["state"] == "paused":
            con.execute("UPDATE timers SET state='running', ends=?, remaining=NULL WHERE id=?",
                        ((_now() + timedelta(seconds=t["remaining"])).strftime(TS), tid))
        elif action == "add":  # +1 min (also works while ringing → restarts it)
            if t["state"] == "paused":
                con.execute("UPDATE timers SET remaining=remaining+? WHERE id=?", (amount, tid))
            else:
                con.execute("UPDATE timers SET state='running', ends=? WHERE id=?",
                            ((_now() + timedelta(seconds=left + amount)).strftime(TS), tid))
        elif action == "repeat":
            con.execute("UPDATE timers SET state='running', ends=?, remaining=NULL, finished=NULL WHERE id=?",
                        ((_now() + timedelta(seconds=t["seconds"])).strftime(TS), tid))
        elif action in ("stop", "cancel"):
            con.execute("UPDATE timers SET state=?, finished=? WHERE id=?",
                        ("done" if t["state"] == "ringing" else "cancelled", _now().strftime(TS), tid))
        elif action == "delete":
            con.execute("DELETE FROM timers WHERE id=?", (tid,))
        return True


# ---------------- what should ring right now (polled by the daemon every second) ----------------

def due():
    """Mark newly-due alarms/timers as ringing and return everything that is ringing."""
    now = _now()
    out = []
    with _con() as con:
        con.execute("UPDATE timers SET state='ringing', finished=? WHERE state='running' AND ends<=?",
                    (now.strftime(TS), now.strftime(TS)))
        for t in con.execute("SELECT * FROM timers WHERE state='ringing'"):
            out.append(("timer", t["id"], t["label"] or "Timer", t["sound"], 0))
        for a in con.execute("SELECT * FROM alarms WHERE enabled=1"):
            a = dict(a)
            if not a["ringing"]:
                h, m = map(int, a["time"].split(":"))
                days = [int(x) for x in a["days"].split(",") if x != ""]
                slot = now.replace(hour=h, minute=m, second=0)
                fire = False
                if a["snoozed_until"] and a["snoozed_until"] <= now.strftime(TS):
                    fire = True
                elif not a["snoozed_until"] and slot <= now < slot + timedelta(minutes=2) \
                        and (not days or now.weekday() in days) and a["last_fired"] != slot.strftime(TS):
                    fire = True
                if fire:
                    con.execute("UPDATE alarms SET ringing=1, snoozed_until=NULL, last_fired=? WHERE id=?",
                                (slot.strftime(TS) if not a["snoozed_until"] else a["last_fired"], a["id"]))
                    a["ringing"] = 1
            if a["ringing"]:
                out.append(("alarm", a["id"], a["label"] or "Alarm", a["sound"], a["snooze"]))
    return out


def stop(kind, rid, snooze_min=0):
    if kind == "alarm":
        alarm_stop(rid, snooze_min)
    else:
        timer_action(rid, "stop")


# ---------------- routes ----------------

@bp.get("/api/clock")
def clock_state():
    return jsonify(alarms=alarms(), timers=timers(), recents=recents(), sounds=SOUNDS, now=_now().strftime(TS),
                   ringing=[dict(kind=k, id=i, label=lbl, snooze=s) for k, i, lbl, _, s in due()])


@bp.post("/api/alarms")
def alarm_new():
    try:
        return jsonify(alarm_save(request.get_json() or {}))
    except ValueError:
        return jsonify(error="Time must be HH:MM"), 400


@bp.patch("/api/alarms/<int:aid>")
def alarm_edit(aid):
    try:
        return jsonify(alarm_save(request.get_json() or {}, aid))
    except ValueError:
        return jsonify(error="Time must be HH:MM"), 400


@bp.delete("/api/alarms/<int:aid>")
def alarm_delete(aid):
    with _con() as con:
        con.execute("DELETE FROM alarms WHERE id=?", (aid,))
    return jsonify(ok=True)


@bp.post("/api/alarms/<int:aid>/<action>")
def alarm_act(aid, action):
    alarm_stop(aid, 9 if action == "snooze" else 0)
    return jsonify(ok=True)


@bp.post("/api/timers")
def timer_new():
    j = request.get_json() or {}
    tid = timer_start(j.get("seconds", 300), j.get("label", ""), j.get("sound", "Chimes"))
    return jsonify(id=tid)


@bp.post("/api/timers/<int:tid>/<action>")
def timer_act(tid, action):
    if not timer_action(tid, action, int((request.get_json(silent=True) or {}).get("seconds", 60))):
        return jsonify(error="no such timer"), 404
    return jsonify(ok=True)


@bp.get("/clock-sounds/<name>")
def sound_file(name):
    ensure_sounds()
    return send_from_directory(SOUND_DIR, Path(name).name)
