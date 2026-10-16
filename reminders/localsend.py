"""LocalSend integration & cross-device media sharing.
Detects LocalSend on port 53317 / Windows disk, and provides direct LAN sharing for voice notes and media.
Also includes the Claude-to-Gemini context exporter for rapid AI persona migration.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, jsonify, request

from . import db, paths

bp = Blueprint("localsend", __name__)

LOCALSEND_PORT = 53317
LOCALSEND_PATHS = [
    r"C:\Program Files\LocalSend\localsend_app.exe",
    r"C:\Program Files\LocalSend\localsend.exe",
    r"C:\Program Files (x86)\LocalSend\localsend_app.exe",
    r"C:\Program Files (x86)\LocalSend\localsend.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\LocalSend\localsend_app.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\LocalSend\localsend_app.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\LocalSend\localsend.exe"),
    os.path.expandvars(r"%ProgramFiles%\LocalSend\localsend_app.exe"),
    os.path.expandvars(r"%ProgramFiles%\LocalSend\localsend.exe"),
    os.path.expandvars(r"%USERPROFILE%\scoop\apps\localsend\current\localsend_app.exe"),
]


def find_localsend_exe():
    which = shutil.which("localsend") or shutil.which("localsend_app")
    if which:
        return which
    for p in LOCALSEND_PATHS:
        if os.path.exists(p):
            return p
    return None


def is_port_open(port=LOCALSEND_PORT, host="127.0.0.1", timeout=0.3):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@bp.get("/api/localsend/status")
def localsend_status():
    exe = find_localsend_exe()
    running = is_port_open(LOCALSEND_PORT)
    lan_ip = get_lan_ip()
    return jsonify({
        "installed": exe is not None,
        "running": running,
        "exe": exe or "",
        "port": LOCALSEND_PORT,
        "web_url": f"http://localhost:{LOCALSEND_PORT}",
        "lan_ip": lan_ip,
        "lan_url": f"http://{lan_ip}:8503",
    })


@bp.post("/api/localsend/launch")
def localsend_launch():
    exe = find_localsend_exe()
    if not exe:
        return jsonify(error="LocalSend is not installed. You can install it via winget install LocalSend.LocalSend or use the Web Wrapper."), 404
    try:
        subprocess.Popen([exe], creationflags=0x00000008 if os.name == "nt" else 0)
        return jsonify(ok=True, message="LocalSend opened.")
    except Exception as e:
        return jsonify(error=str(e)), 500


@bp.post("/api/localsend/share")
def localsend_share():
    data = request.get_json() or {}
    memo_id = data.get("memo_id")
    file_path = data.get("path")
    target_path = None

    if memo_id:
        memos_dir = paths.DATA / "memos"
        row = db.memo_get(int(memo_id)) if hasattr(db, "memo_get") else None
        if not row:
            for ext in (".webm", ".wav", ".mp3", ".m4a", ".mp4"):
                candidate = memos_dir / f"{memo_id}{ext}"
                if candidate.exists():
                    target_path = str(candidate)
                    break
        else:
            cand = memos_dir / (row.get("filename") or f"{memo_id}.webm")
            if cand.exists():
                target_path = str(cand)

    elif file_path and os.path.exists(file_path):
        target_path = file_path

    lan_ip = get_lan_ip()
    download_url = f"http://{lan_ip}:8503/api/memos/{memo_id}/audio" if memo_id else ""

    exe = find_localsend_exe()
    launched = False
    if exe and target_path:
        try:
            subprocess.Popen([exe, target_path], creationflags=0x00000008 if os.name == "nt" else 0)
            launched = True
        except Exception:
            pass

    return jsonify({
        "ok": True,
        "target_path": target_path,
        "launched_localsend": launched,
        "lan_download_url": download_url,
        "lan_ip": lan_ip,
        "message": "Ready to share via LocalSend or direct LAN download.",
    })


@bp.get("/api/ai/claude-to-gemini")
def export_claude_to_gemini():
    """Compiles Claude project context, user persona, and instructions into a Gemini Gem system prompt."""
    from . import chat
    now_str = datetime_str = ""
    try:
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass

    user_name = db.setting("user_name") or "Taylor"
    custom_persona = db.setting("chat_persona") or chat.BASE.format(now=now_str)

    gemini_prompt = f"""# System Instructions for Gemini (Exported from Claude Training)

## Core Identity & Role
You are the primary AI intelligence, creative director, and operational co-pilot for {user_name}.
You operate with the directness, nuance, and depth developed across previous Claude training iterations.

## User Context & Profile
- Name: {user_name}
- Focus: Content Creator, YouTube Strategist (@TarnishedByGrace28, ORI / Styx River channels, Facebook pages), Software Developer.
- Daily Architecture: 3:00 AM wake-up, 3:30 Unleash U training, 4:30-6:00 Facebook/YouTube scheduling, 6:00 morning walk.
- Philosophy: Intentional reality engineering, subconscious mastery (Dispenza template approach), rigorous architecture applied to life and tech.

## Interaction Principles
1. Be punchy, actionable, and specific. Cut fluff and boilerplate.
2. In coding: Provide working, production-grade code without missing imports or placeholder syntax.
3. In content strategy: Focus on retention hooks, high-CTR angles, pacing, and viral packaging.
4. Format output cleanly in GitHub-flavored Markdown.

## Integrated Context & Tools
{custom_persona.strip()}

---
*Generated by Daybook Local AI Hub in under 5 minutes for instant paste into Gemini Gems / System Instructions.*
"""
    return jsonify({
        "ok": True,
        "title": f"Gemini Custom Gem: {user_name} Co-Pilot",
        "gemini_prompt": gemini_prompt,
        "char_count": len(gemini_prompt),
        "target_url": "https://gemini.google.com/app",
    })
