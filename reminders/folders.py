"""Folders: pin the folders you use all the time, browse them inside Daybook, and start 'workflows' —
one button that opens a set of folders, apps and websites together (e.g. Editing = OBS recordings + CapCut)."""
import ctypes
import json
import os
import shutil
import string
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


_DRIVES = {"t": 0, "list": None, "busy": False}


def _scan_drives():
    """Drive names + free space. Slow when a hard drive is asleep (it has to spin up), so it runs in the background."""
    k32 = ctypes.windll.kernel32
    out = []
    mask = k32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not mask & (1 << i):
            continue
        root = f"{letter}:\\"
        kind = k32.GetDriveTypeW(root)  # 2 removable, 3 fixed, 4 network, 5 cd-rom
        if kind not in (2, 3, 4):
            continue
        label = ctypes.create_unicode_buffer(128)
        total = free = 0
        if kind == 3 or kind == 2:
            try:
                if k32.GetVolumeInformationW(root, label, 128, None, None, None, None, 0):
                    total, _, free = shutil.disk_usage(root)
                elif kind == 2:
                    continue  # empty card reader / USB slot
            except Exception:
                pass
        out.append({"name": label.value or ("USB drive" if kind == 2 else "Network drive" if kind == 4 else "Local Disk"), "path": root,
                    "letter": letter, "total": total, "free": free})
    return out


def _refresh_drives():
    import threading
    import time

    def run():
        try:
            _DRIVES["list"] = _scan_drives()
            _DRIVES["t"] = time.time()
            try:
                db.set_settings({"drives_cache": json.dumps(_DRIVES["list"])})
            except Exception:
                pass
        finally:
            _DRIVES["busy"] = False
    if not _DRIVES["busy"]:
        _DRIVES["busy"] = True
        threading.Thread(target=run, daemon=True).start()


def places():
    """Quick places + every drive, for the Files hub sidebar — answered instantly from the last scan."""
    import time
    quick = [("Desktop", HOME / "Desktop"), ("Downloads", HOME / "Downloads"), ("Documents", HOME / "Documents"),
             ("Pictures", HOME / "Pictures"), ("Videos", HOME / "Videos"), ("Music", HOME / "Music")]
    if _DRIVES["list"] is None:
        try:
            _DRIVES["list"] = json.loads(db.setting("drives_cache") or "null")
        except Exception:
            _DRIVES["list"] = None
    if _DRIVES["list"] is None:  # very first run: a quick letters-only list, details fill in on the next visit
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        _DRIVES["list"] = [{"name": "Local Disk", "path": f"{c}:\\", "letter": c, "total": 0, "free": 0}
                           for i, c in enumerate(string.ascii_uppercase) if mask & (1 << i) and ctypes.windll.kernel32.GetDriveTypeW(f"{c}:\\") == 3]
    if time.time() - _DRIVES["t"] > 120:
        _refresh_drives()
    return {"quick": [{"name": n, "path": str(q)} for n, q in quick if q.exists()], "drives": _DRIVES["list"]}


def _free_name(dest_dir, name):
    """'clip.mp4' → 'clip (2).mp4' when it already exists there."""
    target = Path(dest_dir) / name
    if not target.exists():
        return target
    stem, suf = (target.stem, target.suffix) if target.is_file() or "." in name else (name, "")
    n = 2
    while (Path(dest_dir) / f"{stem} ({n}){suf}").exists():
        n += 1
    return Path(dest_dir) / f"{stem} ({n}){suf}"


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint), ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int), ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", ctypes.c_wchar_p)]


def recycle(paths):
    """Send to the Recycle Bin (undoable), never a permanent delete."""
    op = _SHFILEOPSTRUCTW(None, 3, "\0".join(paths) + "\0\0", None, 0x0040 | 0x0010 | 0x0004 | 0x0400, 0, None, None)  # DELETE, ALLOWUNDO|NOCONFIRMATION|SILENT|NOERRORUI
    r = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if r or op.fAnyOperationsAborted:
        raise OSError(f"Couldn't move to the Recycle Bin (code {r})")


def file_op(op, paths, dest="", name=""):
    done = []
    if op in ("move", "copy"):
        d = Path(dest)
        if not d.is_dir():
            raise ValueError("Destination folder not found")
        for src in map(Path, paths):
            if not src.exists():
                continue
            if src.parent == d and op == "move":
                continue  # already there
            if d == src or src in d.parents:
                raise ValueError(f"Can't put “{src.name}” inside itself")
            target = _free_name(d, src.name)
            if op == "move":
                shutil.move(str(src), str(target))
            elif src.is_dir():
                shutil.copytree(src, target)
            else:
                shutil.copy2(src, target)
            done.append(str(target))
    elif op == "rename":
        src = Path(paths[0])
        name = name.strip()
        if not name or any(c in name for c in '\\/:*?"<>|'):
            raise ValueError('A name can\'t be empty or contain \\ / : * ? " < > |')
        target = src.with_name(name)
        if target.exists() and target.name.lower() != src.name.lower():
            raise ValueError("Something with that name is already there")
        src.rename(target)
        done.append(str(target))
    elif op == "delete":
        ok = [p for p in paths if os.path.exists(p) and len(Path(p).parts) > 1]
        if ok:
            recycle(ok)
        done = ok
    elif op == "mkdir":
        target = _free_name(dest, name.strip() or "New folder")
        target.mkdir()
        done.append(str(target))
    else:
        raise ValueError("Unknown action")
    return done


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
    return jsonify(pins=pins(), workflows=workflows(), suggestions=suggestions(), places=places())


@bp.post("/api/folders/op")
def f_op():
    j = request.get_json() or {}
    try:
        return jsonify(done=file_op(j.get("op"), j.get("paths") or [], j.get("dest", ""), j.get("name", "")))
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400


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
    if (request.get_json(silent=True) or {}).get("hub"):  # Daybook opens folders/sites itself; only apps launch here
        apps = {"items": [x for x in ws[i].get("items", []) if x.get("type") == "app"]}
        return jsonify(opened=run_workflow(apps))
    return jsonify(opened=run_workflow(ws[i]))
