"""Chat with local Ollama models: saved conversations, streaming, personas and tools
(Daybook reminders / schedule / notes, and Orca projects — Orca actions need a confirm click)."""
import re
import html
import json
from pathlib import Path
import subprocess
import tempfile
import os
import threading
import urllib.request
import uuid
from datetime import date, datetime

from flask import Blueprint, Response, jsonify, request

from . import db, nlp, notes, orca

OLLAMA = "http://127.0.0.1:11434"
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


_OLLAMA_TRY = {"t": 0}


def ensure_ollama():
    """If Ollama is installed but not running, start it quietly (at most once a minute)."""
    import shutil
    import time
    if time.time() - _OLLAMA_TRY["t"] < 60:
        return
    _OLLAMA_TRY["t"] = time.time()
    try:
        urllib.request.urlopen(OLLAMA + "/api/version", timeout=1)
        return
    except Exception:
        pass
    cands = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama app.exe", Path(r"D:\Applications\Ollama\ollama app.exe")]
    exe = next((c for c in cands if c.exists()), None)
    if exe:
        subprocess.Popen([str(exe)], cwd=str(exe.parent), creationflags=0x00000008 | 0x08000000)
    elif shutil.which("ollama"):
        subprocess.Popen([shutil.which("ollama"), "serve"], creationflags=0x00000008 | 0x08000000)


def _ollama_up():
    """Fast check: on Windows a refused localhost connection otherwise takes ~2 s."""
    import socket
    try:
        socket.create_connection(("127.0.0.1", 11434), timeout=0.3).close()
        return True
    except OSError:
        return False


def model_list(include_claude=True):
    try:
        if not _ollama_up():
            raise ConnectionError("Ollama isn't running")
        local = [{"name": m["name"], "size": m["size"], "params": m["details"].get("parameter_size"),
                  "tools": "tools" in (m.get("capabilities") or []), "vision": "vision" in (m.get("capabilities") or [])}
                 for m in ollama("/api/tags")["models"]]
    except Exception:
        local = []
        threading.Thread(target=ensure_ollama, daemon=True).start()
    if include_claude and claude_cli():
        local += [{"name": f"claude:{k}", "label": label, "params": "Claude", "tools": True, "vision": False, "cloud": True}
                  for k, label in CLAUDE_MODELS]
    if include_claude and (gemini_cli() or os.environ.get("GEMINI_API_KEY") or _user_env("GEMINI_API_KEY")):
        local += [{"name": "gemini:default", "label": "Gemini — Cloud AI (Free, Fast)", "params": "Gemini", "tools": False, "vision": False, "cloud": True}]
    if not local and include_claude:
        local = [{"name": "gemini:default", "label": "Gemini — Cloud AI (Zero GPU Needed)", "params": "Gemini", "tools": False, "vision": False, "cloud": True}]
    return local


# ---------- Gemini (through the Gemini CLI the user is signed in to — installed from Chat → Terminal) ----------
GEMINI_TIMEOUT_S = 300  # a stuck CLI (waiting for sign-in, network…) is stopped after this


def gemini_cli():
    from . import claude_link
    return claude_link._gemini_exe()


def generate_gemini(cid):
    """Non-interactive Gemini CLI: the conversation goes in on stdin, the answer streams back as plain text."""
    chat = get_chat(cid)
    msgs = [m for m in history(cid) if m["role"] in ("user", "assistant")][-20:]
    system = BASE.format(now=datetime.now().strftime("%A %Y-%m-%d %H:%M")) + "\n\n" + PERSONAS.get(chat["persona"], PERSONAS["Assistant"])
    convo = "\n".join(f"{m['role'].upper()}: {m['content'][:4000]}" for m in msgs)
    prompt = f"{system}\n\nReply in Markdown to the last USER message.\n\n{convo}\nASSISTANT:"
    exe = gemini_cli()
    if not exe:
        yield sse("error", {"message": "Gemini CLI isn't installed — open Chat → Terminal → + → Gemini CLI to install it and sign in."})
        return
    STOP[cid] = False
    errf = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")  # an unread stderr pipe can fill up and freeze the CLI
    env = {**os.environ, "GEMINI_CLI_NO_RELAUNCH": "true"}  # skip the CLI restarting itself in a second Node process
    try:  # read-only: no tools may change files from here
        proc = subprocess.Popen([exe, "--skip-trust", "--approval-mode", "default", "-p", "Answer the conversation given on stdin."], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=errf, text=True, encoding="utf-8", errors="replace",
                                cwd=str(db.DB_PATH.parent), env=env, creationflags=0x08000000)
    except Exception as e:
        errf.close()
        yield sse("error", {"message": f"Couldn't start Gemini: {e}"})
        return
    PROCS[cid] = proc
    killer = threading.Timer(GEMINI_TIMEOUT_S, proc.kill)
    killer.daemon = True
    killer.start()
    proc.stdin.write(prompt)
    proc.stdin.close()
    text = ""
    noise = re.compile(r"^(Warning: Windows|Ripgrep is not available|Loaded cached credentials|Data collection is disabled)", re.I)
    for line in iter(proc.stdout.readline, ""):  # line by line, so the CLI's own status lines can be dropped
        if STOP.get(cid):
            proc.kill()
            break
        if not text and (not line.strip() or noise.match(line.strip())):
            continue
        if noise.match(line.strip()):
            continue
        text += line
        yield sse("token", {"t": line})
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    killer.cancel()
    PROCS.pop(cid, None)
    errf.seek(0)
    err = errf.read()[-400:]
    errf.close()
    if proc.returncode not in (0, None) and not text.strip():
        yield sse("error", {"message": "Gemini didn't answer — " + (err.strip() or "sign in once: Chat → Terminal → Gemini CLI.")})
        return
    if text.strip():
        add_msg(cid, "assistant", text.strip(), {"model": chat["model"]})
    yield sse("done", {"stats": {}})


# ---------- Claude (through the Claude Code CLI the user is signed in to) ----------
CLAUDE_MODELS = [("sonnet", "Claude Sonnet — your Claude account"), ("opus", "Claude Opus — your Claude account"),
                 ("haiku", "Claude Haiku — fast, your Claude account")]
CLAUDE_TOOLS = "mcp__reminders WebSearch WebFetch"            # Daybook's own tools + web lookups
CLAUDE_BLOCKED = "Bash Edit Write NotebookEdit MultiEdit"      # never touch files or run commands from chat
PROCS = {}


def claude_cli():
    from . import claude_link
    return claude_link._claude_exe()


def generate_claude(cid):
    chat = get_chat(cid)
    alias = chat["model"].split(":", 1)[1] or "sonnet"
    msgs = [m for m in history(cid) if m["role"] in ("user", "assistant")]
    last_user = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
    session = next((m["meta"].get("claude_session") for m in reversed(history(cid)) if m["meta"].get("claude_session")), None)
    if session:
        prompt = last_user
    else:  # first Claude turn in this chat: include the conversation so far (it may have started on a local model)
        earlier = msgs[:-1][-20:]
        prompt = ("Conversation so far:\n" + "\n".join(f"{m['role'].upper()}: {m['content'][:2000]}" for m in earlier) + "\n\nUSER: " + last_user) if earlier else last_user
    system = (BASE.format(now=datetime.now().strftime("%A %Y-%m-%d %H:%M")) + "\n\n" + PERSONAS.get(chat["persona"], PERSONAS["Assistant"])
              + "\n\nYou are inside the user's Daybook app. Use the `reminders` tools for their schedule, reminders and notes. Reply in Markdown.")
    cmd = [claude_cli(), "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages", "--model", alias,
           "--append-system-prompt", system, "--allowedTools", *CLAUDE_TOOLS.split(), "--disallowedTools", *CLAUDE_BLOCKED.split()]
    if session:
        cmd += ["--resume", session]
    STOP[cid] = False
    text, sid, usage = "", session, {}
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                errors="replace", cwd=str(db.DB_PATH.parent), creationflags=0x08000000)
    except Exception as e:
        yield sse("error", {"message": f"Couldn't start Claude: {e}"})
        return
    PROCS[cid] = proc
    proc.stdin.write(prompt)
    proc.stdin.close()
    for line in proc.stdout:
        if STOP.get(cid):
            proc.kill()
            break
        try:
            j = json.loads(line)
        except Exception:
            continue
        t = j.get("type")
        if t == "system" and j.get("session_id"):
            sid = j["session_id"]
        elif t == "stream_event":
            ev = j.get("event", {})
            if ev.get("type") == "content_block_delta":
                d = ev.get("delta", {})
                if d.get("type") == "text_delta":
                    text += d["text"]
                    yield sse("token", {"t": d["text"]})
                elif d.get("type") == "thinking_delta":
                    yield sse("think", {"t": d.get("thinking", "")})
            elif ev.get("type") == "message_stop" and text and not text.endswith("\n\n"):
                text += "\n\n"
                yield sse("token", {"t": "\n\n"})
        elif t == "assistant":
            for c in j.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    name = c.get("name", "").replace("mcp__reminders__", "")
                    yield sse("tool", {"name": name, "args": c.get("input", {})})
        elif t == "user":
            for c in j.get("message", {}).get("content", []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    res = c.get("content")
                    res = res if isinstance(res, str) else " ".join(x.get("text", "") for x in (res or []) if isinstance(x, dict))
                    yield sse("tool_result", {"name": "", "result": res[:600]})
        elif t == "result":
            sid = j.get("session_id") or sid
            usage = {"cost_usd": j.get("total_cost_usd"), "turns": j.get("num_turns"), "duration_ms": j.get("duration_ms")}
            if j.get("is_error") and not text:
                yield sse("error", {"message": "Claude: " + str(j.get("result") or j.get("subtype"))[:300]})
    proc.wait(timeout=10)
    PROCS.pop(cid, None)
    if proc.returncode not in (0, None) and not text:
        err = (proc.stderr.read() or "")[-400:]
        yield sse("error", {"message": "Claude didn't answer — " + (err.strip() or "is Claude Code signed in? Run `claude` once in a terminal.")})
        return
    if text.strip():
        add_msg(cid, "assistant", text.strip(), {"model": chat["model"], "claude_session": sid, "stats": usage})
    yield sse("done", {"stats": usage})


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
    if chat["model"].startswith("claude:"):
        yield from generate_claude(cid)
        return
    if chat["model"].startswith("gemini:"):
        yield from generate_gemini(cid)
        return
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
        local = chat["model"] if not chat["model"].startswith(("claude:", "gemini:")) else (model_list(False) or [{"name": "qwen2.5:7b"}])[0]["name"]
        r = ollama("/api/generate", {"model": local, "stream": False, "options": {"num_ctx": 2048},
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
                          (j.get("model") or db.setting("chat_model") or (model_list(False) or [{"name": "qwen2.5:7b"}])[0]["name"],
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
    if cid in PROCS:
        try:  # gemini.cmd / claude.cmd run node under cmd.exe: end the whole tree, not just cmd.exe
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(PROCS[cid].pid)], capture_output=True, timeout=10,
                           creationflags=0x08000000)
            PROCS[cid].kill()
        except Exception:
            pass
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
