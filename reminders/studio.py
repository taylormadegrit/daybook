"""AI Studio — create with the models already on this PC:
images (SDXL-Turbo, local GPU), your cloned voice (Coqui XTTS from the Ori Brazil project), and
optional Gemini images (cloud; needs billing on your Google key). Creations save to D:\\Daybook\\Creations."""
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from . import db

bp = Blueprint("studio", __name__)
ROOT = Path(__file__).resolve().parent.parent
OUT = Path(r"D:\Daybook\Creations")
WORKER = "http://127.0.0.1:8504"
AI_PY = Path(r"D:\projects\ori-brazil\venv\Scripts\python.exe")
VOICE_DIRS = [Path(r"D:\TBG Voice Samples"), Path(r"D:\Daybook\Voices")]
AUDIO = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
STYLES = {"none": "", "photo": ", professional photo, natural light, sharp focus, 35mm",
          "cinematic": ", cinematic still, dramatic lighting, film grain, anamorphic",
          "anime": ", anime key visual, vibrant, clean line art, studio quality",
          "thumbnail": ", eye-catching YouTube thumbnail, bold, high contrast, expressive face, vivid colors",
          "logo": ", minimal vector logo, flat design, centered, plain background",
          "3d": ", 3d render, octane, soft studio lighting, high detail",
          "art": ", digital painting, concept art, rich colors, trending on artstation",
          "spiritual": ", ethereal, sacred geometry, golden light, mystical, ancient"}


def _req(path, body=None, timeout=900):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(WORKER + path, data=data, headers={"Content-Type": "application/json"}, method="POST" if data else "GET")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read())


def worker_up():
    try:
        return _req("/status", timeout=2)
    except Exception:
        return None


def ensure_worker():
    s = worker_up()
    if s:
        return s
    if not AI_PY.exists():
        raise RuntimeError("The AI Python (Ori Brazil project) isn't on this PC")
    env = {**os.environ, "DAYBOOK_CREATIONS": str(OUT)}
    log = open(ROOT / "data" / "ai_worker.log", "a", encoding="utf-8")
    subprocess.Popen([str(AI_PY), str(ROOT / "ai_worker.py")], cwd=str(ROOT), env=env, stdout=log, stderr=log,
                     creationflags=0x08000000 | 0x00000200)
    for _ in range(90):
        time.sleep(1)
        s = worker_up()
        if s:
            return s
    raise RuntimeError("The AI worker didn't start — see data/ai_worker.log")


def voices():
    out = []
    for d in VOICE_DIRS:
        if d.exists():
            out += [{"name": p.stem, "path": str(p), "src": d.name} for p in sorted(d.iterdir()) if p.suffix.lower() in AUDIO]
    from . import memos
    for m in memos.listing(kind="audio")[:15]:  # any voice memo can be a voice sample
        if m["duration"] >= 6:
            out.append({"name": f"Memo: {m['title'] or 'untitled'}", "path": str(memos.media(m)), "src": "Voice memos"})
    return out


def creations(limit=200):
    if not OUT.exists():
        return []
    files = sorted((p for p in OUT.iterdir() if p.suffix.lower() in {".png", ".jpg", ".wav", ".mp3"}), key=lambda p: -p.stat().st_mtime)
    out = []
    for p in files[:limit]:
        item = {"name": p.name, "kind": "image" if p.suffix.lower() in {".png", ".jpg"} else "audio",
                "created": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%dT%H:%M"), "size": p.stat().st_size, "prompt": ""}
        if p.suffix.lower() == ".png":
            try:
                from PIL import Image
                with Image.open(p) as im:
                    item["prompt"] = im.text.get("prompt", "") if hasattr(im, "text") else ""
            except Exception:
                pass
        out.append(item)
    return out


def gemini_image(prompt):
    key = os.environ.get("GEMINI_API_KEY") or _user_env("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("No GEMINI_API_KEY on this PC")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    r = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent",
                               data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            j = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="ignore")
        if e.code == 429 or "quota" in msg.lower():
            raise RuntimeError("Gemini images need billing turned on for your Google AI key (free tier has no image quota)")
        raise RuntimeError(f"Gemini said {e.code}")
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    for part in j.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "inlineData" in part:
            name = f"gemini-{datetime.now():%Y%m%d-%H%M%S}-{len(files)}.png"
            (OUT / name).write_bytes(base64.b64decode(part["inlineData"]["data"]))
            files.append(name)
    if not files:
        raise RuntimeError("Gemini returned no image")
    return files


def _werr(e):
    """Readable message from an AI-worker HTTP error (JSON or an HTML traceback page)."""
    raw = e.read() or b""
    try:
        return json.loads(raw).get("error", f"AI worker error {e.code}")
    except Exception:
        return f"AI worker error {e.code} — details in data/ai_worker.log"


def _user_env(name):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return ""


@bp.get("/api/studio")
def st_state():
    s = worker_up()
    return jsonify(worker=s, image_model=(ROOT / "data" / "ai-models" / "sdxl-turbo" / "model_index.json").exists(),
                   tts_model=Path(r"D:\coqui-models\tts\tts_models--multilingual--multi-dataset--xtts_v2").exists(),
                   gemini=bool(os.environ.get("GEMINI_API_KEY") or _user_env("GEMINI_API_KEY")),
                   styles=list(STYLES), voices=voices(), creations=creations(60), out=str(OUT))


@bp.post("/api/studio/image")
def st_image():
    j = request.get_json() or {}
    prompt = (j.get("prompt") or "").strip() + STYLES.get(j.get("style", "none"), "")
    try:
        if j.get("engine") == "gemini":
            return jsonify(files=gemini_image(prompt), engine="gemini")
        ensure_worker()
        res = _req("/image", {"prompt": prompt, "negative": j.get("negative", "blurry, low quality, watermark, text, deformed"),
                              "width": j.get("width", 512), "height": j.get("height", 512), "count": j.get("count", 2), "steps": j.get("steps", 2),
                              "seed": j.get("seed")})
        return jsonify(res)
    except urllib.error.HTTPError as e:
        return jsonify(error=_werr(e)), 400
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400


@bp.post("/api/studio/tts")
def st_tts():
    j = request.get_json() or {}
    try:
        ensure_worker()
        return jsonify(_req("/tts", {"text": j.get("text", ""), "voice": j.get("voice", ""), "language": j.get("language", "en")}))
    except urllib.error.HTTPError as e:
        return jsonify(error=_werr(e)), 400
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400


@bp.post("/api/studio/unload")
def st_unload():
    try:
        _req("/unload", {})
    except Exception:
        pass
    return jsonify(ok=True)


@bp.delete("/api/studio/creations/<path:name>")
def st_delete(name):
    (OUT / Path(name).name).unlink(missing_ok=True)
    return jsonify(ok=True)


@bp.get("/creations/<path:name>")
def st_file(name):
    return send_from_directory(OUT, Path(name).name)
