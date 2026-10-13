"""Chat with local Ollama models: saved conversations, streaming, personas and tools
(Daybook reminders / schedule / notes, and Orca projects — Orca actions need a confirm click)."""
import re
import html
import json
import threading
import urllib.request
import uuid
from datetime import date, datetime

from flask import Blueprint, Response, jsonify, request

from . import db, nlp, notes, orca

OLLAMA = "http://localhost:11434"
NUM_CTX = 8192
bp = Blueprint("chat", __name__)

PERSONAS = {
    "Assistant": "You are a warm, sharp personal assistant. Be concise and practical.",
    "Coder": "You are a senior software engineer. Give working code, explain briefly, prefer simple solutions.",
    "Content strategist": "You are a short-form video and YouTube growth strategist. Think hooks, retention, titles, "
                          "thumbnails, posting cadence. Be specific and punchy.",
    "Ori script writer": "You write spiritual / motivational short-form scripts in ORI's voice (Styx River): "
                         "direct, mystical, empowering, ancient-wisdom references. Hook in the first line.",
    "Thinking partner": "You are a thoughtful sounding board. Ask one good question at a time and help the user "
                        "think things through. Keep replies short.",
}

BASE = """Current local time: {now}.
The user is Taylor, a content creator (YouTube @TarnishedByGrace28, ORI / Styx River channels, Facebook pages).
Daily routine: 3:00 wake, 3:30 Unleash U, 4:30-6:00 schedule Facebook uploads, 6:00 walk.
You run fully locally on his PC. You have tools for his reminders, schedule, notes (Daybook) and his Orca coding
projects. Use a tool only when it clearly helps; otherwise just answer. When you create something, say what you did.
Format answers in Markdown."""

# ---------- tools ----------

TOOLS = [
    ("day_schedule", "Get the user's schedule (routine blocks + reminders) for a day.",
     {"day": ("string", "the day exactly as the user said it: 'today', 'tomorrow', 'friday', or YYYY-MM-DD")}, ["day"]),
    ("add_reminder", "Create a desktop pop-up reminder.",
     {"text": ("string", "what to remind, short"), "when": ("string", "plain English time, e.g. 'tomorrow 10am'"),
      "repeat": ("string", "'' or daily, weekdays, weekly, monthly"), "ends": ("string", "optional HH:MM end time")},
     ["text", "when"]),
    ("list_reminders", "List upcoming reminders with ids.", {}, []),
    ("search_notes", "Search the user's notes (meetings, YouTube notes, ideas, daily logs).",
     {"query": ("string", "search words"), "category": ("string", "optional category")}, ["query"]),
    ("search_research", "Search the user's Zotero research library (papers, books, articles, videos) and get citations.",
     {"query": ("string", "search words — title, author, topic")}, ["query"]),
    ("get_note", "Read one note in full.", {"id": ("integer", "note id")}, ["id"]),
    ("add_note", "Save a new note.", {"title": ("string", "title"), "body": ("string", "note text"),
                                       "category": ("string", "optional category")}, ["body"]),
    ("log_to_today", "Append a line to today's daily log.", {"text": ("string", "the line")}, ["text"]),
    ("orca_list_projects", "List the user's coding projects in Orca.", {}, []),
    ("orca_new_project", "Create a NEW coding project in Orca and start an AI coding agent on it. "
                         "Use when the user wants to start/build a new project or app.",
     {"name": ("string", "short project name"), "description": ("string", "one paragraph what it is"),
      "prompt": ("string", "detailed first instructions for the coding agent"),
      "agent": ("string", "claude (default) or codex")}, ["name", "prompt"]),
    ("orca_start_task", "Start an AI coding agent on a task inside an EXISTING Orca project.",
     {"project": ("string", "project name"), "prompt": ("string", "detailed instructions for the agent"),
      "agent": ("string", "claude (default) or codex")}, ["project", "prompt"]),
]
CONFIRM = {"orca_new_project", "orca_start_task"}  # never run without the user clicking Confirm


def tool_schemas(enabled):
    out = []
    for name, desc, props, req in TOOLS:
        if name.startswith("orca") and "orca" not in enabled or not name.startswith("orca") and "daybook" not in enabled:
            continue
        out.append({"type": "function", "function": {"name": name, "description": desc, "parameters": {
            "type": "object", "required": req,
            "properties": {k: {"type": t, "description": d} for k, (t, d) in props.items()}}}})
    return out


def run_tool(name, a):
    if name == "day_schedule":
        said = str(a.get("day") or a.get("date") or "today").strip().lower()
        try:
            day = date.fromisoformat(said)
        except ValueError:
            day = date.today() if said in ("", "today") else (nlp.resolve_when(said, datetime.now()) or datetime.now()).date()
        items = db.occurrences_on(day)
        lines = "\n".join(f"{w:%I:%M %p}{' to ' + r['ends'] if r['ends'] else ''}  {r['text']}" for w, r in items)
        return f"{day:%A %B %d}:\n" + (lines or "Nothing scheduled.")
    if name == "add_reminder":
        rid = db.add(a["text"], nlp.when(a["when"]), a.get("repeat") or "", 0, "", a.get("ends") or "")
        return "Created " + db.describe(db.get(rid))
    if name == "list_reminders":
        return "\n".join(db.describe(r) for r in db.list_open()[:40]) or "No reminders."
    if name == "search_notes":
        rows = notes.search(a.get("query", ""), a.get("category", ""), limit=10)
        return "\n".join(f"#{n['id']} {n['note_date']} [{n['category']}] {n['title']} — {n['summary']}" for n in rows) or "No matches."
    if name == "search_research":
        from . import zotero
        items, mode = zotero.search(a.get("query", ""), limit=8)
        return "\n".join(f"{i['title']} — {i['authors']} ({i['year']}){' · ' + i['venue'] if i['venue'] else ''}"
                         + (f"\n  {html.unescape(re.sub('<[^>]+>', '', i['bib'])).strip()}" if i.get("bib") else "") for i in items) or "Nothing in the Zotero library matches."
    if name == "get_note":
        n = notes.get(int(a["id"]))
        return f"{n['title']} ({n['note_date']})\n{n['body'][:4000]}" if n else "Not found."
    if name == "add_note":
        nid = notes.add(a["body"], a.get("title", ""), a.get("category", ""))
        return f"Saved note #{nid}"
    if name == "log_to_today":
        notes.append_to_log(a["text"])
        return "Logged."
    if name == "orca_list_projects":
        return "\n".join(p["name"] for p in orca.list_projects())
    if name == "orca_new_project":
        r = orca.new_project(a["name"], a.get("description", ""), a.get("prompt", ""), a.get("agent", "claude"))
        return f"Created project {r['project']} at {r['path']}" + (f"; {r['agent']['agent']} started on it in Orca" if r["agent"] else "")
    if name == "orca_start_task":
        r = orca.start_task(a["project"], a["prompt"], a.get("agent", "claude"))
        return f"Started {r['agent']} in Orca on {a['project']} (worktree {r['task']})"
    return f"Unknown tool {name}"


# ---------- storage ----------

def _con():
    con = db.connect()
    con.execute("""CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT 'New chat',
        model TEXT NOT NULL, persona TEXT NOT NULL DEFAULT 'Assistant', tools TEXT NOT NULL DEFAULT 'daybook,orca',
        created TEXT NOT NULL, updated TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL,
        role TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', meta TEXT NOT NULL DEFAULT '{}', created TEXT NOT NULL)""")
    return con


def _now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def history(cid):
    with _con() as con:
        return [dict(r) | {"meta": json.loads(r["meta"])} for r in
                con.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY id", (cid,))]


def add_msg(cid, role, content, meta=None):
    with _con() as con:
        con.execute("INSERT INTO messages (chat_id, role, content, meta, created) VALUES (?,?,?,?,?)",
                    (cid, role, content, json.dumps(meta or {}), _now()))
        con.execute("UPDATE chats SET updated=? WHERE id=?", (_now(), cid))


def get_chat(cid):
    with _con() as con:
        r = con.execute("SELECT * FROM chats WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None


# ---------- ollama ----------

def ollama(path, body=None, stream=False):
    req = urllib.request.Request(OLLAMA + path, json.dumps(body).encode() if body else None,
                                 {"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=600)
    if stream:
        return resp
    with resp:
        return json.loads(resp.read())


def model_list():
    try:
        return [{"name": m["name"], "size": m["size"], "params": m["details"].get("parameter_size"),
                 "tools": "tools" in (m.get("capabilities") or []), "vision": "vision" in (m.get("capabilities") or [])}
                for m in ollama("/api/tags")["models"]]
    except Exception:
        return []


def build_messages(chat):
    msgs = [{"role": "system", "content": BASE.format(now=datetime.now().strftime("%A %Y-%m-%d %H:%M"))
             + "\n\n" + PERSONAS.get(chat["persona"], PERSONAS["Assistant"])}]
    for m in history(chat["id"]):
        if m["role"] == "tool":
            msgs.append({"role": "tool", "content": m["content"], "tool_name": m["meta"].get("name", "")})
        elif m["role"] == "assistant" and m["meta"].get("tool_calls"):
            msgs.append({"role": "assistant", "content": m["content"], "tool_calls": m["meta"]["tool_calls"]})
        elif m["role"] in ("user", "assistant"):
            msgs.append({"role": m["role"], "content": m["content"]})
    return msgs[:1] + msgs[1:][-40:]  # keep the recent window


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


STOP = {}  # chat id → stop flag
PENDING = {}  # confirm id → (chat id, tool name, args)


def generate(cid):
    chat = get_chat(cid)
    model_has_tools = next((m["tools"] for m in model_list() if m["name"] == chat["model"]), False)
    tools = tool_schemas(chat["tools"].split(",")) if model_has_tools else []
    STOP[cid] = False
    for _round in range(5):  # tool loop
        body = {"model": chat["model"], "messages": build_messages(chat), "stream": True,
                "options": {"num_ctx": NUM_CTX}}
        if tools:
            body["tools"] = tools
        text, calls, stats = "", [], {}
        try:
            with ollama("/api/chat", body, stream=True) as resp:
                for line in resp:
                    if STOP.get(cid):
                        break
                    if not line.strip():
                        continue
                    j = json.loads(line)
                    msg = j.get("message", {})
                    if msg.get("thinking"):
                        yield sse("think", {"t": msg["thinking"]})
                    if msg.get("content"):
                        text += msg["content"]
                        yield sse("token", {"t": msg["content"]})
                    calls += msg.get("tool_calls") or []
                    if j.get("done"):
                        stats = {k: j.get(k) for k in ("eval_count", "eval_duration", "total_duration")}
        except Exception as e:
            yield sse("error", {"message": f"Ollama error: {e}"})
            return
        if not calls or STOP.get(cid):
            if text:
                add_msg(cid, "assistant", text, {"model": chat["model"], "stats": stats})
            yield sse("done", {"stats": stats})
            return
        add_msg(cid, "assistant", text, {"tool_calls": calls, "model": chat["model"]})
        for c in calls:
            fn = c["function"]["name"]
            args = c["function"].get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            if fn in CONFIRM:
                pid = uuid.uuid4().hex[:10]
                PENDING[pid] = (cid, fn, args)
                add_msg(cid, "action", "", {"pending": pid, "name": fn, "args": args})
                yield sse("confirm", {"id": pid, "name": fn, "args": args})
                yield sse("done", {"stats": stats})
                return
            yield sse("tool", {"name": fn, "args": args})
            try:
                result = run_tool(fn, args)
            except Exception as e:
                result = f"Error: {e}"
            add_msg(cid, "tool", result, {"name": fn, "args": args})
            yield sse("tool_result", {"name": fn, "result": result})
    yield sse("done", {})


def auto_title(cid):
    try:
        chat = get_chat(cid)
        first = next((m["content"] for m in history(cid) if m["role"] == "user"), "")
        r = ollama("/api/generate", {"model": chat["model"], "stream": False, "options": {"num_ctx": 2048},
                                     "prompt": f"Give a 2-5 word title for a chat that starts with: \"{first[:500]}\". "
                                               "Reply with the title only, no quotes."})
        title = r["response"].strip().strip('"').split("\n")[0][:60]
        if title:
            with _con() as con:
                con.execute("UPDATE chats SET title=? WHERE id=?", (title, cid))
    except Exception:
        pass


# ---------- routes ----------

@bp.get("/api/chat/models")
def models():
    return jsonify(models=model_list(), personas=list(PERSONAS))


@bp.get("/api/chats")
def chats():
    with _con() as con:
        return jsonify([dict(r) for r in con.execute("SELECT * FROM chats ORDER BY updated DESC LIMIT 200")])


@bp.post("/api/chats")
def new_chat():
    j = request.get_json() or {}
    with _con() as con:
        cur = con.execute("INSERT INTO chats (model, persona, tools, created, updated) VALUES (?,?,?,?,?)",
                          (j.get("model") or db.setting("chat_model") or (model_list() or [{"name": "qwen2.5:7b"}])[0]["name"],
                           j.get("persona", "Assistant"), j.get("tools", "daybook,orca"), _now(), _now()))
    return jsonify(get_chat(cur.lastrowid))


@bp.get("/api/chats/<int:cid>")
def open_chat(cid):
    return jsonify(chat=get_chat(cid), messages=history(cid))


@bp.patch("/api/chats/<int:cid>")
def edit_chat(cid):
    j = request.get_json()
    allowed = {k: v for k, v in j.items() if k in ("title", "model", "persona", "tools")}
    with _con() as con:
        for k, v in allowed.items():
            con.execute(f"UPDATE chats SET {k}=? WHERE id=?", (v, cid))
    return jsonify(get_chat(cid))


@bp.delete("/api/chats/<int:cid>")
def delete_chat(cid):
    with _con() as con:
        con.execute("DELETE FROM messages WHERE chat_id=?", (cid,))
        con.execute("DELETE FROM chats WHERE id=?", (cid,))
    return jsonify(ok=True)


@bp.post("/api/chats/<int:cid>/send")
def send(cid):
    text = (request.get_json() or {}).get("content", "").strip()
    if text:
        add_msg(cid, "user", text)
        if get_chat(cid)["title"] == "New chat":  # name the chat from its first message
            threading.Thread(target=auto_title, args=(cid,), daemon=True).start()
    return Response(generate(cid), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


@bp.post("/api/chats/<int:cid>/regenerate")
def regenerate(cid):
    with _con() as con:  # drop everything after the last user message
        last = con.execute("SELECT MAX(id) FROM messages WHERE chat_id=? AND role='user'", (cid,)).fetchone()[0]
        if last:
            con.execute("DELETE FROM messages WHERE chat_id=? AND id>?", (cid, last))
    return Response(generate(cid), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


@bp.post("/api/chats/<int:cid>/stop")
def stop(cid):
    STOP[cid] = True
    return jsonify(ok=True)


@bp.post("/api/actions/<pid>")
def confirm(pid):
    """User clicked Confirm/Cancel on an Orca action card."""
    if pid not in PENDING:
        return jsonify(error="This action expired — ask again."), 404
    cid, fn, args = PENDING.pop(pid)
    approve = (request.get_json() or {}).get("approve")
    if approve:
        try:
            result = run_tool(fn, args)
        except Exception as e:
            result = f"Error: {e}"
    else:
        result = "Cancelled by the user."
    add_msg(cid, "tool", result, {"name": fn, "args": args, "resolved": pid})
    add_msg(cid, "assistant", ("✅ " if approve and not result.startswith("Error") else "") + result, {"action_result": True})
    return jsonify(result=result)
