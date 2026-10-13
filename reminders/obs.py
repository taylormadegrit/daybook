"""OBS Studio integration for video notes: start/stop recording from Daybook over OBS's built-in
WebSocket server (localhost). When a recording stops it lands in Voice memos as a video note and is
transcribed like any memo. The connection details come from OBS's own config file."""
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint("obs", __name__)
CFG = Path(os.environ.get("APPDATA", "")) / "obs-studio" / "plugin_config" / "obs-websocket" / "config.json"
EXE_CANDIDATES = [r"D:\Applications\obs-studio\bin\64bit\obs64.exe", r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"]
STATE = {"title": "", "labels": []}


def exe():
    return next((p for p in EXE_CANDIDATES if os.path.exists(p)), None)


def running():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/NH"], capture_output=True, text=True, creationflags=0x08000000)
    return "obs64.exe" in r.stdout


def config():
    try:
        return json.loads(CFG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def client():
    import obsws_python as obs
    c = config()
    return obs.ReqClient(host="localhost", port=int(c.get("server_port", 4455)),
                         password=c.get("server_password", "") if c.get("auth_required", True) else "", timeout=3)


def status():
    c = config()
    out = {"installed": bool(exe()), "running": False, "enabled": bool(c.get("server_enabled")), "connected": False,
           "recording": False, "paused": False, "timecode": "", "record_dir": "", "error": ""}
    if not out["installed"]:
        return out
    out["running"] = running()
    if out["running"] and out["enabled"]:
        try:
            cl = client()
            st = cl.get_record_status()
            out.update(connected=True, recording=st.output_active, paused=st.output_paused, timecode=st.output_timecode.split(".")[0])
            out["record_dir"] = cl.get_record_directory().record_directory
            cl.disconnect()
        except Exception as e:
            out["error"] = str(e)[:200]
    return out


def enable():
    """Turn on OBS's local WebSocket server (keeps password protection). OBS must be closed first,
    because OBS rewrites this file when it exits."""
    if running():
        raise RuntimeError("Close OBS first, then press Connect again")
    CFG.parent.mkdir(parents=True, exist_ok=True)
    c = config()
    if CFG.exists():
        shutil.copy2(CFG, CFG.with_suffix(".json.daybook-backup"))
    c.setdefault("server_port", 4455)
    c["server_enabled"] = True
    c["auth_required"] = True
    if not c.get("server_password"):
        c["server_password"] = secrets.token_urlsafe(16)
    c.setdefault("alerts_enabled", False)
    c["first_load"] = False
    CFG.write_text(json.dumps(c, indent=4), encoding="utf-8")


def launch():
    e = exe()
    if not e:
        raise RuntimeError("OBS Studio isn't installed")
    if not running():
        subprocess.Popen([e, "--disable-shutdown-check"], cwd=os.path.dirname(e), creationflags=0x00000008)


@bp.get("/api/obs")
def obs_status():
    return jsonify(status())


@bp.post("/api/obs/<action>")
def obs_action(action):
    from . import memos
    j = request.get_json(silent=True) or {}
    try:
        if action == "enable":
            enable()
        elif action == "launch":
            launch()
        elif action == "start":
            STATE.update(title=j.get("title", ""), labels=j.get("labels", []))
            cl = client(); cl.start_record(); cl.disconnect()
        elif action in ("pause", "resume"):
            cl = client(); (cl.pause_record() if action == "pause" else cl.resume_record()); cl.disconnect()
        elif action == "stop":
            cl = client(); res = cl.stop_record(); cl.disconnect()
            path = res.output_path
            mid = memos.add_file(path, STATE["title"], STATE["labels"], source="obs") if path and os.path.exists(path) else None
            return jsonify(ok=True, path=path, memo=mid)
        else:
            return jsonify(error="unknown action"), 400
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400
    return jsonify(ok=True)
