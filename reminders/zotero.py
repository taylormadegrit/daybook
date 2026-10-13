"""Zotero integration — your research library inside Daybook.
Reads through Zotero's own local API (Zotero running, 'Allow other applications on this computer to
communicate with Zotero' on — Daybook switches it on at install), and when Zotero is closed it reads a
read-only snapshot of zotero.sqlite so search still works. New items go in through Zotero's connector
import (DOI / ISBN / arXiv / BibTeX / RIS), exactly like the browser extension does."""
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from flask import Blueprint, jsonify, request

from . import db

bp = Blueprint("zotero", __name__)
API = "http://127.0.0.1:23119"
EXE = [r"D:\Applications\Zotero\zotero.exe", r"C:\Program Files\Zotero\zotero.exe"]
STYLES = [("apa", "APA 7th"), ("modern-language-association", "MLA 9th"), ("chicago-note-bibliography", "Chicago (notes)"),
          ("chicago-author-date", "Chicago (author-date)"), ("ieee", "IEEE"), ("elsevier-harvard", "Harvard"), ("nature", "Nature")]
TYPE_ICON = {"journalArticle": "📄", "book": "📕", "bookSection": "📖", "webpage": "🌐", "videoRecording": "🎬", "podcast": "🎙",
             "thesis": "🎓", "report": "📊", "conferencePaper": "🗣", "preprint": "🧪", "blogPost": "✍", "magazineArticle": "📰",
             "newspaperArticle": "📰", "film": "🎬", "presentation": "📽", "note": "🗒", "document": "📄"}


def exe():
    return next((p for p in EXE if os.path.exists(p)), None)


def data_dir():
    """Where the library lives: Zotero's prefs (dataDir) or the default ~/Zotero."""
    prof = Path(os.environ.get("APPDATA", "")) / "Zotero" / "Zotero" / "Profiles"
    for f in list(prof.glob("*/prefs.js")) + list(prof.glob("*/user.js")):
        m = re.search(r'user_pref\("extensions\.zotero\.dataDir",\s*"([^"]+)"\)', f.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return Path(m.group(1).replace("\\\\", "\\"))
    return Path.home() / "Zotero"


def _get(path, params=None, raw=False, timeout=8):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Zotero-API-Version": "3"}), timeout=timeout) as r:
        body = r.read()
        return (body.decode("utf-8", "replace"), r.headers) if raw else json.loads(body)


def status():
    s = {"installed": bool(exe()), "running": False, "api": False, "data_dir": str(data_dir()), "items": 0}
    try:
        urllib.request.urlopen(API + "/connector/ping", timeout=2)
        s["running"] = True
        _, h = _get("/api/users/0/items/top", {"limit": 1}, raw=True, timeout=4)
        s["api"], s["items"] = True, int(h.get("Total-Results") or 0)
    except urllib.error.HTTPError as e:
        s["api_error"] = "Local API is off — Zotero → Settings → Advanced → 'Allow other applications on this computer to communicate with Zotero'" if e.code in (403, 404) else str(e)
    except Exception:
        pass
    return s


def launch():
    e = exe()
    if not e:
        raise RuntimeError("Zotero isn't installed")
    subprocess.Popen([e], cwd=os.path.dirname(e), creationflags=0x00000008)


def _authors(creators, n=3):
    names = [c.get("lastName") or c.get("name") or "" for c in creators if c.get("creatorType") in ("author", "editor", "director", "podcaster", "presenter", "contributor")]
    names = [x for x in names if x]
    if not names:
        return ""
    return ", ".join(names[:n]) + (" et al." if len(names) > n else "")


def _slim(it):
    d = it.get("data", it)
    return {"key": d["key"], "type": d.get("itemType"), "icon": TYPE_ICON.get(d.get("itemType"), "📄"), "title": d.get("title") or d.get("note", "")[:80] or "Untitled",
            "authors": _authors(d.get("creators", [])), "year": (re.search(r"\d{4}", d.get("date", "") or "") or [""])[0],
            "venue": d.get("publicationTitle") or d.get("bookTitle") or d.get("websiteTitle") or d.get("publisher") or "",
            "tags": [t["tag"] for t in d.get("tags", [])][:8], "added": d.get("dateAdded", ""),
            "attachments": (it.get("meta") or {}).get("numChildren", 0), "bib": it.get("bib", "")}


# ---------------- reading: API, or a snapshot when Zotero is closed ----------------

def _snapshot():
    """Zotero locks its database while open; when it's closed we read a temporary copy."""
    src = data_dir() / "zotero.sqlite"
    if not src.exists():
        return None
    tmp = Path(tempfile.gettempdir()) / "daybook-zotero.sqlite"
    if not tmp.exists() or tmp.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, tmp)
    con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _offline_search(q, limit=60):
    con = _snapshot()
    if not con:
        return []
    like = f"%{q}%"
    rows = con.execute("""
        SELECT i.key, t.typeName, i.dateAdded,
          (SELECT v.value FROM itemData d JOIN itemDataValues v USING(valueID) JOIN fields f USING(fieldID) WHERE d.itemID=i.itemID AND f.fieldName='title') AS title,
          (SELECT v.value FROM itemData d JOIN itemDataValues v USING(valueID) JOIN fields f USING(fieldID) WHERE d.itemID=i.itemID AND f.fieldName='date') AS date,
          (SELECT group_concat(c.lastName, ', ') FROM itemCreators ic JOIN creators c USING(creatorID) WHERE ic.itemID=i.itemID) AS authors
        FROM items i JOIN itemTypes t USING(itemTypeID)
        WHERE t.typeName NOT IN ('attachment','note','annotation') AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
          AND (? = '' OR EXISTS (SELECT 1 FROM itemData d JOIN itemDataValues v USING(valueID) WHERE d.itemID=i.itemID AND v.value LIKE ?)
               OR EXISTS (SELECT 1 FROM itemCreators ic JOIN creators c USING(creatorID) WHERE ic.itemID=i.itemID AND c.lastName LIKE ?))
        ORDER BY i.dateModified DESC LIMIT ?""", (q, like, like, limit)).fetchall()
    con.close()
    return [{"key": r["key"], "type": r["typeName"], "icon": TYPE_ICON.get(r["typeName"], "📄"), "title": r["title"] or "Untitled",
             "authors": r["authors"] or "", "year": (re.search(r"\d{4}", r["date"] or "") or [""])[0], "venue": "", "tags": [],
             "added": r["dateAdded"], "attachments": 0, "bib": ""} for r in rows]


def search(q="", collection="", tag="", limit=60, style="apa"):
    params = {"limit": limit, "sort": "dateModified", "direction": "desc", "include": "data,bib", "style": style}
    if q:
        params.update(q=q, qmode="everything")
    if tag:
        params["tag"] = tag
    path = f"/api/users/0/collections/{collection}/items/top" if collection else "/api/users/0/items/top"
    try:
        return [_slim(it) for it in _get(path, params, timeout=15)], "live"
    except Exception:
        return _offline_search(q, limit), "offline"


def collections():
    try:
        cols = _get("/api/users/0/collections", {"limit": 100})
        return [{"key": c["key"], "name": c["data"]["name"], "parent": c["data"].get("parentCollection") or "", "count": c.get("meta", {}).get("numItems", 0)} for c in cols]
    except Exception:
        return []


def _html_text(s):
    s = re.sub(r"<(br|/p|/li|/h\d|/div)[^>]*>", "\n", s or "", flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def item(key, style="apa"):
    it = _get(f"/api/users/0/items/{key}", {"include": "data,bib,citation", "style": style})
    d = it["data"]
    kids = []
    try:
        kids = _get(f"/api/users/0/items/{key}/children", {"include": "data"})
    except Exception:
        pass
    notes, files = [], []
    for k in kids:
        kd = k["data"]
        if kd["itemType"] == "note":
            notes.append(_html_text(kd.get("note", "")))
        elif kd["itemType"] == "attachment":
            path = ""
            if kd.get("linkMode") in ("imported_file", "imported_url") and kd.get("filename"):
                path = str(data_dir() / "storage" / kd["key"] / kd["filename"])
            elif kd.get("linkMode") == "linked_file" and kd.get("path"):
                path = kd["path"].replace("attachments:", "")
            files.append({"key": kd["key"], "title": kd.get("title") or kd.get("filename") or "Attachment", "type": kd.get("contentType", ""),
                          "path": path if path and os.path.exists(path) else "", "url": kd.get("url", "")})
    out = _slim(it)
    out.update(abstract=d.get("abstractNote", ""), url=d.get("url", ""), doi=d.get("DOI", ""), date=d.get("date", ""),
               creators=[(c.get("firstName", "") + " " + c.get("lastName", "")).strip() or c.get("name", "") for c in d.get("creators", [])],
               citation=_html_text(it.get("citation", "")), bib_text=_html_text(it.get("bib", "")), notes=notes, files=files,
               zotero_link=f"zotero://select/library/items/{key}")
    return out


def export(keys, fmt="bibtex"):
    body, _ = _get("/api/users/0/items", {"itemKey": ",".join(keys), "format": fmt}, raw=True)
    return body


# ---------------- adding: DOI, ISBN, arXiv, BibTeX/RIS ----------------
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.I)
ARXIV_RE = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:\s*)?(\d{4}\.\d{4,5})(v\d+)?", re.I)
ISBN_RE = re.compile(r"^(?:ISBN[:\s]*)?([0-9Xx][0-9Xx\- ]{8,16})$")


def _fetch(url, accept="*/*"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "Daybook (local app) mailto:none"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def identify(text):
    """Turn whatever was pasted into BibTeX/RIS that Zotero can import. Returns (data, what)."""
    t = text.strip()
    if t.startswith("@") or "TY  -" in t[:200]:
        return t.encode(), "BibTeX/RIS"
    m = DOI_RE.search(t)
    if m:
        doi = m.group(0).rstrip(".,;)")
        return _fetch(f"https://doi.org/{urllib.parse.quote(doi)}", "application/x-bibtex"), f"DOI {doi}"
    m = ARXIV_RE.search(t)
    if m and ("arxiv" in t.lower() or re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", t)):
        return _fetch(f"https://arxiv.org/bibtex/{m.group(1)}"), f"arXiv {m.group(1)}"
    m = ISBN_RE.match(t)
    if m:
        isbn = re.sub(r"[^0-9Xx]", "", m.group(1))
        j = json.loads(_fetch(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"))
        b = j.get(f"ISBN:{isbn}")
        if not b:
            raise ValueError("No book found for that ISBN")
        year = (re.search(r"\d{4}", b.get("publish_date", "")) or [""])[0]
        ris = ["TY  - BOOK", f"TI  - {b.get('title', '')}"] + [f"AU  - {a['name']}" for a in b.get("authors", [])] + \
              [f"PY  - {year}", f"PB  - {', '.join(p['name'] for p in b.get('publishers', []))}",
               f"SN  - {isbn}", f"UR  - {b.get('url', '')}", f"SP  - {b.get('number_of_pages', '')}", "ER  - "]
        return "\n".join(ris).encode(), f"ISBN {isbn}"
    raise ValueError("Paste a DOI, ISBN, arXiv ID or link, or BibTeX/RIS text")


def add(text):
    data, what = identify(text)
    req = urllib.request.Request(API + "/connector/import?session=daybook-" + os.urandom(4).hex(), data=data, method="POST",
                                 headers={"Content-Type": "text/plain"})
    with urllib.request.urlopen(req, timeout=30) as r:
        items = json.loads(r.read() or b"[]")
    return what, [{"key": i.get("key"), "title": i.get("title")} for i in items]


def to_note(key, style="apa"):
    from . import notes
    it = item(key, style)
    body = (f"**{it['title']}**\n{', '.join(it['creators'])}{' · ' + it['date'] if it['date'] else ''}{' · ' + it['venue'] if it['venue'] else ''}\n\n"
            f"## Citation\n{it['bib_text']}\n\n" + (f"## Abstract\n{it['abstract']}\n\n" if it["abstract"] else "")
            + ("## Zotero notes\n" + "\n\n".join(it["notes"]) + "\n\n" if it["notes"] else "")
            + "## My notes\n- \n\n" + f"Open in Zotero: {it['zotero_link']}" + (f"\nDOI: https://doi.org/{it['doi']}" if it["doi"] else ""))
    return notes.add(body, it["title"], "YouTube / Learning", ["research", "zotero"] + [t.lower() for t in it["tags"][:4]], organize=False)


# ---------------- routes ----------------

@bp.get("/api/zotero")
def z_state():
    s = status()
    s["styles"] = STYLES
    if s["api"]:
        s["collections"] = collections()
    return jsonify(s)


@bp.get("/api/zotero/items")
def z_items():
    items, mode = search(request.args.get("q", ""), request.args.get("collection", ""), request.args.get("tag", ""),
                         style=request.args.get("style", "apa"))
    return jsonify(items=items, mode=mode)


@bp.get("/api/zotero/items/<key>")
def z_item(key):
    try:
        return jsonify(item(key, request.args.get("style", "apa")))
    except Exception as e:
        return jsonify(error="Open Zotero to see full details" if isinstance(e, urllib.error.URLError) else str(e)[:200]), 400


@bp.post("/api/zotero/<action>")
def z_action(action):
    j = request.get_json(silent=True) or {}
    try:
        if action == "launch":
            launch()
            return jsonify(ok=True)
        if action == "add":
            what, items = add(j.get("text", ""))
            return jsonify(ok=True, what=what, items=items)
        if action == "note":
            return jsonify(ok=True, note_id=to_note(j["key"], j.get("style", "apa")))
        if action == "open":
            p = j.get("path", "")
            if p and os.path.isfile(p):  # an attachment from your library (PDF, EPUB, snapshot…)
                os.startfile(p)
            elif j.get("key"):
                os.startfile(f"zotero://select/library/items/{j['key']}")
            return jsonify(ok=True)
        if action == "export":
            return jsonify(ok=True, text=export(j.get("keys", []), j.get("format", "bibtex")))
    except urllib.error.URLError:
        return jsonify(error="Zotero isn't running — press Open Zotero"), 400
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400
    return jsonify(error="unknown action"), 400
