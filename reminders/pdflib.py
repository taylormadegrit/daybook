"""PDF library: every PDF in the folders you pick, with covers, page counts and full-text search.
Files are only read (never moved or changed). Index lives in Daybook's database; covers in data/pdf_thumbs."""
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from . import db

bp = Blueprint("pdflib", __name__)
THUMBS = Path(__file__).resolve().parent.parent / "data" / "pdf_thumbs"
SKIP_DIRS = {"$recycle.bin", "system volume information", "windows", "appdata", "node_modules", "venv", ".venv", ".git",
             "site-packages", "program files", "program files (x86)", "programdata", "__pycache__", "npm-cache", "pip-cache"}
DEFAULT_FOLDERS = [str(Path.home() / "Downloads"), str(Path.home() / "Documents"), str(Path.home() / "Desktop"),
                   r"D:\Life Organization", r"F:\28HRTZ", r"D:\Zotero\storage"]
STATE = {"scanning": False, "done": 0, "total": 0, "last": ""}
LOCK = threading.Lock()


def _con():
    con = db.connect()
    con.execute("""CREATE TABLE IF NOT EXISTS pdfs (id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
        folder TEXT NOT NULL, size INTEGER NOT NULL DEFAULT 0, mtime REAL NOT NULL DEFAULT 0, pages INTEGER NOT NULL DEFAULT 0,
        title TEXT NOT NULL DEFAULT '', author TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '', starred INTEGER NOT NULL DEFAULT 0,
        opened TEXT, status TEXT NOT NULL DEFAULT 'new')""")
    con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS pdfs_fts USING fts5(name, title, author, text, content='pdfs', content_rowid='id')""")
    for name, sql in {
        "pdfs_ai": "AFTER INSERT ON pdfs BEGIN INSERT INTO pdfs_fts(rowid, name, title, author, text) VALUES (new.id, new.name, new.title, new.author, new.text); END",
        "pdfs_ad": "AFTER DELETE ON pdfs BEGIN INSERT INTO pdfs_fts(pdfs_fts, rowid, name, title, author, text) VALUES ('delete', old.id, old.name, old.title, old.author, old.text); END",
        "pdfs_au": "AFTER UPDATE ON pdfs BEGIN INSERT INTO pdfs_fts(pdfs_fts, rowid, name, title, author, text) VALUES ('delete', old.id, old.name, old.title, old.author, old.text);"
                   " INSERT INTO pdfs_fts(rowid, name, title, author, text) VALUES (new.id, new.name, new.title, new.author, new.text); END",
    }.items():
        con.execute(f"CREATE TRIGGER IF NOT EXISTS {name} {sql}")
    return con


def folders():
    try:
        f = json.loads(db.setting("pdf_folders") or "null")
    except Exception:
        f = None
    return f if isinstance(f, list) else [d for d in DEFAULT_FOLDERS if os.path.isdir(d)]


def _walk(root, depth=6):
    root = Path(root)
    if not root.is_dir():
        return
    stack = [(root, 0)]
    while stack:
        d, lvl = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if lvl < depth and e.name.lower() not in SKIP_DIRS and not e.name.startswith("."):
                                stack.append((Path(e.path), lvl + 1))
                        elif e.name.lower().endswith(".pdf"):
                            yield e
                    except OSError:
                        pass
        except OSError:
            pass


def _extract(path, pid):
    """Pages, PDF metadata, the text of the first pages (for search) and a cover thumbnail."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(path)
    try:
        meta = pdf.get_metadata_dict() or {}
        n = len(pdf)
        text = []
        for i in range(min(n, 12)):
            try:
                tp = pdf[i].get_textpage()
                text.append(tp.get_text_range())
                tp.close()
            except Exception:
                pass
        THUMBS.mkdir(parents=True, exist_ok=True)
        if n:
            page = pdf[0]
            w, h = page.get_size()
            scale = 360 / max(w, 1)
            img = page.render(scale=scale).to_pil()
            img.convert("RGB").save(THUMBS / f"{pid}.jpg", quality=82)
        return n, (meta.get("Title") or "").strip(), (meta.get("Author") or "").strip(), " ".join(text)[:60000]
    finally:
        pdf.close()


def scan():
    """Find new/changed PDFs, drop ones that are gone, then extract details in the background."""
    if not LOCK.acquire(blocking=False):
        return
    try:
        STATE.update(scanning=True, done=0, total=0)
        seen = set()
        with _con() as con:
            known = {r["path"]: (r["id"], r["mtime"]) for r in con.execute("SELECT id, path, mtime FROM pdfs")}
            for root in folders():
                for e in _walk(root):
                    st = e.stat()
                    seen.add(e.path)
                    old = known.get(e.path)
                    if old and abs(old[1] - st.st_mtime) < 1:
                        continue
                    if old:
                        con.execute("UPDATE pdfs SET size=?, mtime=?, status='new' WHERE id=?", (st.st_size, st.st_mtime, old[0]))
                    else:
                        con.execute("INSERT OR IGNORE INTO pdfs (path, name, folder, size, mtime) VALUES (?,?,?,?,?)",
                                    (e.path, Path(e.name).stem, str(Path(e.path).parent), st.st_size, st.st_mtime))
            for path, (pid, _) in known.items():
                if path not in seen:
                    con.execute("DELETE FROM pdfs WHERE id=?", (pid,))
                    (THUMBS / f"{pid}.jpg").unlink(missing_ok=True)
            todo = [(r["id"], r["path"]) for r in con.execute("SELECT id, path FROM pdfs WHERE status='new'")]
        STATE["total"] = len(todo)
        for pid, path in todo:
            try:
                n, title, author, text = _extract(path, pid)
                status = "ok"
            except Exception:
                n, title, author, text, status = 0, "", "", "", "error"  # password-protected or damaged
            with _con() as con:
                con.execute("UPDATE pdfs SET pages=?, title=?, author=?, text=?, status=? WHERE id=?", (n, title, author, text, status, pid))
            STATE["done"] += 1
        STATE["last"] = datetime.now().strftime("%Y-%m-%dT%H:%M")
    finally:
        STATE["scanning"] = False
        LOCK.release()


def scan_bg():
    threading.Thread(target=scan, daemon=True).start()


def _row(r):
    d = dict(r)
    d.pop("text", None)
    t = (d["title"] or "").strip()
    bad = len(t) < 4 or t.lower().startswith(("microsoft word", "untitled", "(anonymous)", "document", "pdf", "slide 1")) or t.lower().endswith((".doc", ".docx", ".pdf", ".pptx"))
    d["display"] = d["name"].replace("_", " ") if bad else t
    if d["author"].strip().lower() in ("(anonymous)", "anonymous", "unknown", "user", "admin"):
        d["author"] = ""
    d["modified"] = datetime.fromtimestamp(d["mtime"]).strftime("%Y-%m-%dT%H:%M")
    d["thumb"] = (THUMBS / f"{d['id']}.jpg").exists()
    return d


def search(q="", folder="", sort="recent", limit=400):
    with _con() as con:
        args, where = [], []
        if folder:
            where.append("(p.folder = ? OR p.folder LIKE ?)")
            args += [folder, folder.rstrip("\\") + "\\%"]
        order = {"recent": "p.mtime DESC", "name": "p.name COLLATE NOCASE", "opened": "p.opened DESC NULLS LAST", "size": "p.size DESC"}.get(sort, "p.mtime DESC")
        if q:
            terms = " ".join(f'"{t}"*' for t in q.replace('"', " ").split() if t)
            sql = (f"SELECT p.*, snippet(pdfs_fts, 3, '[', ']', '…', 14) AS snip FROM pdfs_fts JOIN pdfs p ON p.id = pdfs_fts.rowid "
                   f"WHERE pdfs_fts MATCH ? {'AND ' + ' AND '.join(where) if where else ''} ORDER BY rank LIMIT ?")
            rows = con.execute(sql, [terms] + args + [limit]).fetchall()
        else:
            rows = con.execute(f"SELECT p.*, '' AS snip FROM pdfs p {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY p.starred DESC, {order} LIMIT ?",
                               args + [limit]).fetchall()
        return [_row(r) | {"snip": r["snip"]} for r in rows]


def get(pid):
    with _con() as con:
        r = con.execute("SELECT * FROM pdfs WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None


def summarize(pid):
    """Short summary + key points from the first pages, using the local AI."""
    from . import nlp
    d = get(pid)
    if not d or not d["text"].strip():
        raise ValueError("This PDF has no readable text (it may be scanned images)")
    out = nlp._ask_ollama("Summarize this document for a busy reader. Reply as JSON {\"summary\": \"3-4 sentences\", "
                          "\"key_points\": [\"...\"], \"topics\": [\"...\"]}.\n\n" + d["text"][:9000])
    return out


# ---------------- routes ----------------

@bp.get("/api/pdfs")
def p_list():
    return jsonify(items=search(request.args.get("q", ""), request.args.get("folder", ""), request.args.get("sort", "recent")),
                   folders=[{"path": f, "name": Path(f).name or f, "exists": os.path.isdir(f)} for f in folders()], state=STATE)


@bp.post("/api/pdfs/scan")
def p_scan():
    scan_bg()
    return jsonify(ok=True)


@bp.post("/api/pdfs/folders")
def p_folders():
    fs = [f for f in (request.get_json() or {}).get("folders", []) if isinstance(f, str) and os.path.isdir(f)]
    db.set_settings({"pdf_folders": json.dumps(fs)})
    scan_bg()
    return jsonify(folders=fs)


@bp.get("/pdf-file/<int:pid>")
def p_file(pid):
    d = get(pid)
    if not d or not os.path.exists(d["path"]):
        return ("Not found", 404)
    with _con() as con:
        con.execute("UPDATE pdfs SET opened=? WHERE id=?", (datetime.now().strftime("%Y-%m-%dT%H:%M"), pid))
    return send_file(d["path"], mimetype="application/pdf", conditional=True, download_name=Path(d["path"]).name)


@bp.get("/pdf-thumb/<int:pid>")
def p_thumb(pid):
    p = THUMBS / f"{pid}.jpg"
    return send_file(p, max_age=86400) if p.exists() else ("", 404)


@bp.post("/api/pdfs/<int:pid>/<action>")
def p_action(pid, action):
    d = get(pid)
    if not d:
        return jsonify(error="Not found"), 404
    try:
        if action == "open":
            os.startfile(d["path"])
        elif action == "reveal":
            import subprocess
            subprocess.Popen(["explorer", "/select,", d["path"]])
        elif action == "star":
            with _con() as con:
                con.execute("UPDATE pdfs SET starred=1-starred WHERE id=?", (pid,))
        elif action == "summary":
            return jsonify(summarize(pid))
        elif action == "note":
            from . import notes
            s = summarize(pid)
            body = (f"📕 {d['title'] or d['name']}\n{d['author']}\nFile: {d['path']}\n\n## Summary\n{s.get('summary', '')}\n\n## Key points\n"
                    + "\n".join(f"- {k}" for k in s.get("key_points", [])) + "\n\n## My notes\n- \n")
            nid = notes.add(body, d["title"] or d["name"], "YouTube / Learning", ["pdf"] + [t.lower() for t in s.get("topics", [])][:4], organize=False)
            return jsonify(note_id=nid)
        elif action == "zotero":
            return jsonify(zotero_add(d))
        else:
            return jsonify(error="unknown action"), 400
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400
    return jsonify(ok=True)


def zotero_add(d):
    """Hand the PDF to Zotero (it reads the metadata itself, like dragging a PDF into Zotero)."""
    import urllib.request
    data = Path(d["path"]).read_bytes()
    meta = json.dumps({"sessionID": "daybook-" + os.urandom(4).hex(), "title": d["title"] or d["name"], "url": Path(d["path"]).as_uri()})
    req = urllib.request.Request("http://127.0.0.1:23119/connector/saveStandaloneAttachment", data=data, method="POST",
                                 headers={"Content-Type": "application/pdf", "X-Metadata": meta})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    try:
        return json.loads(body or b"{}") | {"ok": True}
    except Exception:
        return {"ok": True}
