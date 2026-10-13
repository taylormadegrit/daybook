"""Saved links: one click in Daybook's browser saves a YouTube video or any page — with its real title, channel and
thumbnail — into the Library. Organize them into collections and attach them to notes. Thumbnails are stored
locally so the library looks right offline."""
import json
import re
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from . import db, paths

bp = Blueprint("links", __name__)
THUMBS = paths.DATA / "link_thumbs"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _con():
    con = db.connect()
    con.execute("""CREATE TABLE IF NOT EXISTS links (id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, title TEXT NOT NULL DEFAULT '',
        kind TEXT NOT NULL DEFAULT 'web', site TEXT NOT NULL DEFAULT '', channel TEXT NOT NULL DEFAULT '', video_id TEXT NOT NULL DEFAULT '',
        collection TEXT NOT NULL DEFAULT '', note_id INTEGER, memo TEXT NOT NULL DEFAULT '', starred INTEGER NOT NULL DEFAULT 0,
        watched INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, opened TEXT)""")
    return con


def youtube_id(url):
    m = re.search(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)([\w-]{11})", url)
    return m.group(1) if m else ""


def clean_url(url):
    vid = youtube_id(url)
    if vid:  # one entry per video, whatever playlist/time/tracking junk was in the address
        t = re.search(r"[?&]t=(\d+)", url)
        return f"https://www.youtube.com/watch?v={vid}" + (f"&t={t.group(1)}" if t else "")
    u = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query) if not k.lower().startswith(("utm_", "fbclid", "gclid", "si"))]
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, urllib.parse.urlencode(q), ""))


def clean_title(title, kind):
    t = re.sub(r"^\(\d+\)\s*", "", (title or "").strip())  # "(3) Video title - YouTube" → "Video title"
    if kind == "youtube":
        t = re.sub(r"\s*-\s*YouTube$", "", t)
    return t[:300]


def _row(r):
    d = dict(r)
    d["thumb"] = f"/link-thumb/{d['id']}" if d["video_id"] and (THUMBS / f"{d['video_id']}.jpg").exists() else ""
    return d


def _enrich(lid, url, vid):
    """Background: YouTube title/channel via oEmbed, and a local thumbnail copy. Silently skipped when offline."""
    try:
        if vid:
            THUMBS.mkdir(parents=True, exist_ok=True)
            f = THUMBS / f"{vid}.jpg"
            if not f.exists():
                for size in ("mqdefault", "hqdefault", "default"):
                    try:
                        f.write_bytes(urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/{size}.jpg", timeout=10).read())
                        break
                    except Exception:
                        continue
            # YouTube's own title + channel beat the browser tab's title ("(3) YouTube", notification counts…)
            j = json.loads(urllib.request.urlopen(f"https://www.youtube.com/oembed?format=json&url={urllib.parse.quote(url)}", timeout=10).read())
            with _con() as con:
                r = con.execute("SELECT title, channel FROM links WHERE id=?", (lid,)).fetchone()
                con.execute("UPDATE links SET title=?, channel=? WHERE id=?", (j.get("title") or r["title"], j.get("author_name", r["channel"]), lid))
        else:
            with _con() as con:
                r = con.execute("SELECT title FROM links WHERE id=?", (lid,)).fetchone()
            if not r["title"] or r["title"].startswith("http"):
                html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=10).read(300_000).decode("utf-8", "replace")
                m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
                if m:
                    import html as h
                    with _con() as con:
                        con.execute("UPDATE links SET title=? WHERE id=?", (h.unescape(m.group(1)).strip()[:300], lid))
    except Exception:
        pass


def save(url, title="", collection="", note_id=None, memo=""):
    if not re.match(r"^https?://", url or ""):
        raise ValueError("Only web links (http/https) can be saved")
    url = clean_url(url)
    vid = youtube_id(url)
    kind = "youtube" if vid else "web"
    site = urllib.parse.urlsplit(url).netloc.removeprefix("www.")
    with _con() as con:
        old = con.execute("SELECT id FROM links WHERE url=?", (url,)).fetchone()
        if old:
            sets = {"title": clean_title(title, kind)} if title else {}
            if collection:
                sets["collection"] = collection
            if note_id:
                sets["note_id"] = note_id
            if sets:
                con.execute(f"UPDATE links SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), old["id"]))
            lid, new = old["id"], False
        else:
            lid = con.execute("INSERT INTO links (url, title, kind, site, video_id, collection, note_id, memo, created) VALUES (?,?,?,?,?,?,?,?,?)",
                              (url, clean_title(title, kind) or url, kind, site, vid, collection.strip(), note_id, memo, datetime.now().isoformat(timespec="seconds"))).lastrowid
            new = True
    threading.Thread(target=_enrich, args=(lid, url, vid), daemon=True).start()
    return lid, new


def search(q="", collection="", note_id=None, kind=""):
    where, args = [], []
    if q:
        for w in q.lower().split():
            where.append("(lower(title) LIKE ? OR lower(channel) LIKE ? OR lower(site) LIKE ? OR lower(memo) LIKE ? OR lower(url) LIKE ?)")
            args += [f"%{w}%"] * 5
    if collection:
        where.append("collection=?"); args.append("" if collection == "_none" else collection)
    if note_id:
        where.append("note_id=?"); args.append(note_id)
    if kind:
        where.append("kind=?"); args.append(kind)
    with _con() as con:
        rows = con.execute(f"SELECT * FROM links {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY starred DESC, created DESC LIMIT 1000", args).fetchall()
        cols = con.execute("SELECT collection, COUNT(*) n FROM links GROUP BY collection ORDER BY collection").fetchall()
    return [_row(r) for r in rows], [{"name": c["collection"], "count": c["n"]} for c in cols]


@bp.get("/api/links")
def l_list():
    items, cols = search(request.args.get("q", ""), request.args.get("collection", ""), request.args.get("note", type=int), request.args.get("kind", ""))
    return jsonify(items=items, collections=cols)


@bp.post("/api/links")
def l_save():
    j = request.get_json() or {}
    try:
        lid, new = save(j.get("url", ""), j.get("title", ""), j.get("collection", ""), j.get("note_id"), j.get("memo", ""))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    with _con() as con:
        return jsonify(link=_row(con.execute("SELECT * FROM links WHERE id=?", (lid,)).fetchone()), new=new)


@bp.get("/api/links/check")
def l_check():
    try:
        url = clean_url(request.args.get("url", ""))
    except Exception:
        return jsonify(saved=False)
    with _con() as con:
        r = con.execute("SELECT id, collection FROM links WHERE url=?", (url,)).fetchone()
    return jsonify(saved=bool(r), id=r["id"] if r else None, collection=r["collection"] if r else "")


@bp.patch("/api/links/<int:lid>")
def l_edit(lid):
    j = request.get_json() or {}
    sets = {k: j[k] for k in ("title", "collection", "note_id", "memo", "starred", "watched") if k in j}
    if "opened" in j:
        sets["opened"] = datetime.now().isoformat(timespec="seconds")
    if sets:
        with _con() as con:
            con.execute(f"UPDATE links SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), lid))
    return jsonify(ok=True)


@bp.delete("/api/links/<int:lid>")
def l_delete(lid):
    with _con() as con:
        con.execute("DELETE FROM links WHERE id=?", (lid,))
    return jsonify(ok=True)


@bp.get("/link-thumb/<int:lid>")
def l_thumb(lid):
    with _con() as con:
        r = con.execute("SELECT video_id FROM links WHERE id=?", (lid,)).fetchone()
    f = THUMBS / f"{r['video_id']}.jpg" if r and r["video_id"] else None
    if not f or not f.exists():
        return ("", 404)
    return send_file(f, max_age=86400 * 30)
