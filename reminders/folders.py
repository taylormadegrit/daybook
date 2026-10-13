"""Folders: pin the folders you use all the time, browse them inside Daybook, and start 'workflows' —
one button that opens a set of folders, apps and websites together (e.g. Editing = OBS recordings + CapCut)."""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from . import db

bp = Blueprint("folders", __name__)
HOME = Path.home()
THUMB = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def pins():
    try:
        return json.loads(db.setting("folders") or "[]")
    except Exception:
        return []


def workflows():
    try:
        return json.loads(db.setting("workflows") or "[]")
    except Exception:
        return []


def suggestions():
    cands = [("Desktop", HOME / "Desktop"), ("Downloads", HOME / "Downloads"), ("Documents", HOME / "Documents"), ("Videos", HOME / "Videos"),
             ("Pictures", HOME / "Pictures"), ("Projects", Path(r"D:\projects")), ("Video Projects", Path(r"D:\Video Projects")),
             ("Screenshots", Path(r"D:\Screenshots")), ("Old notes", Path(r"F:\28HRTZ")), ("Ori TikToks", Path(r"F:\ORi tiktok")),
             ("Annotations", Path(r"D:\Daybook\Annotations")), ("Daybook creations", Path(r"D:\Daybook\Creations"))]
    try:
        from . import obs
        c = obs.config()
    except Exception:
        c = {}
    have = {p["path"].lower() for p in pins()}
    return [{"name": n, "path": str(p)} for n, p in cands if p.exists() and str(p).lower() not in have]


def listing(path, show_hidden=False):
    p = Path(path)
    if not p.is_dir():
        raise ValueError("Folder not found")
    items = []
    with os.scandir(p) as it:
        for e in it:
            if not show_hidden and (e.name.startswith(".") or e.name.lower() in ("desktop.ini", "thumbs.db")):
                continue
            try:
                st = e.stat()
                items.append({"name": e.name, "path": e.path, "dir": e.is_dir(), "size": 0 if e.is_dir() else st.st_size,
                              "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%dT%H:%M"), "ext": Path(e.name).suffix.lower()})
            except OSError:
                pass
    items.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "items": items[:2000], "total": len(items)}


def run_workflow(w):
    from . import launchpad
    opened = 0
    for it in w.get("items", []):
        try:
            if it["type"] == "folder" and os.path.isdir(it["path"]):
                os.startfile(it["path"])
            elif it["type"] == "app":
                a = next((x for x in launchpad.scan_apps() if x["id"] == it["id"]), None)
                if a:
                    os.startfile(a["lnk"])
            elif it["type"] == "url":
                if it.get("browser") and it.get("profile"):
                    launchpad.launch_browser(it["browser"], it["profile"], it["url"])
                else:
                    os.startfile(it["url"])
            elif it["type"] == "profile":
                launchpad.launch_browser(it["browser"], it["profile"])
            opened += 1
        except Exception:
            pass
    return opened


@bp.get("/api/folders")
def f_state():
    return jsonify(pins=pins(), workflows=workflows(), suggestions=suggestions())


@bp.post("/api/folders/pins")
def f_pins():
    out = []
    for f in (request.get_json() or {}).get("pins", []):
        if os.path.isdir(f.get("path", "")):
            out.append({"name": (f.get("name") or Path(f["path"]).name or f["path"])[:40], "path": f["path"], "color": f.get("color", "")})
    db.set_settings({"folders": json.dumps(out[:60])})
    return jsonify(pins=out)


@bp.get("/api/folders/list")
def f_list():
    try:
        return jsonify(listing(request.args.get("path", ""), request.args.get("hidden") == "1"))
    except Exception as e:
        return jsonify(error=str(e)), 400


@bp.post("/api/folders/open")
def f_open():
    j = request.get_json() or {}
    p = j.get("path", "")
    if not os.path.exists(p):
        return jsonify(error="Not found"), 404
    if j.get("reveal"):
        subprocess.Popen(["explorer", "/select,", p])
    else:
        os.startfile(p)
    return jsonify(ok=True)


@bp.post("/api/folders/pick")
def f_pick():
    """Windows' own folder picker (shown on top), so nobody has to type paths."""
    ps = ("Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; "
          "$f.Description = 'Pick a folder for Daybook'; $f.ShowNewFolderButton = $true; "
          "$w = New-Object System.Windows.Forms.Form -Property @{TopMost=$true}; "
          "if ($f.ShowDialog($w) -eq 'OK') { $f.SelectedPath }")
    r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True, timeout=600, creationflags=0x08000000)
    return jsonify(path=r.stdout.strip())


@bp.get("/api/folders/thumb")
def f_thumb():
    p = request.args.get("path", "")
    if Path(p).suffix.lower() in THUMB and os.path.isfile(p):
        return send_file(p, max_age=3600)
    return ("", 404)


@bp.post("/api/workflows")
def wf_save():
    db.set_settings({"workflows": json.dumps((request.get_json() or {}).get("workflows", [])[:30])})
    return jsonify(ok=True)


@bp.post("/api/workflows/<int:i>/run")
def wf_run(i):
    ws = workflows()
    if i >= len(ws):
        return jsonify(error="No such workflow"), 404
    return jsonify(opened=run_workflow(ws[i]))
