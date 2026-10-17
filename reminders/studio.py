"""AI Studio — create with the models already on this PC:
images (SDXL-Turbo, local GPU), your cloned voice (Coqui XTTS from the Ori Brazil project),
Higgsfield AI (40+ cloud image & video models via @higgsfield/cli), and
optional Gemini images (cloud; needs billing on your Google key). Creations save to D:\\Daybook\\Creations."""
import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from . import claude_link, db, paths

bp = Blueprint("studio", __name__)
ROOT = Path(__file__).resolve().parent.parent
OUT = paths.USER_DIR / "Creations"
WORKER = "http://127.0.0.1:8504"
AI_PY = Path(r"D:\projects\ori-brazil\venv\Scripts\python.exe")
VOICE_DIRS = [Path(r"D:\TBG Voice Samples"), paths.USER_DIR / "Voices"]
AUDIO = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
VIDEO = {".mp4", ".mov"}
STYLES = {"none": "", "photo": ", professional photo, natural light, sharp focus, 35mm",
          "cinematic": ", cinematic still, dramatic lighting, film grain, anamorphic",
          "anime": ", anime key visual, vibrant, clean line art, studio quality",
          "thumbnail": ", eye-catching YouTube thumbnail, bold, high contrast, expressive face, vivid colors",
          "logo": ", minimal vector logo, flat design, centered, plain background",
          "3d": ", 3d render, octane, soft studio lighting, high detail",
          "art": ", digital painting, concept art, rich colors, trending on artstation",
          "spiritual": ", ethereal, sacred geometry, golden light, mystical, ancient"}

HIGGSFIELD_IMAGE_MODELS = [
    {"id": "gpt_image_2_5", "name": "GPT Image 2.5 (Default · High-Fidelity & Text)"},
    {"id": "nano_banana_flash", "name": "Nano Banana 2 (Characters & Illustrations)"},
    {"id": "nano_banana_2", "name": "Nano Banana Pro (Top-Tier Realism)"},
    {"id": "text2image_soul_v2", "name": "Higgsfield Soul 2.0 (Editorial, Fashion & UGC)"},
    {"id": "soul_cinematic", "name": "Soul Cinema (Cinematic Stills)"},
    {"id": "flux_2", "name": "FLUX.2 (Black Forest Labs)"},
    {"id": "seedream_v5_pro", "name": "Seedream 5.0 Pro (Faces & Character Sheets)"},
    {"id": "recraft_v4_1", "name": "Recraft V4.1 (Logos, Icons & Vector)"},
    {"id": "z_image", "name": "Z Image (Fastest Drafts)"},
    {"id": "image_auto", "name": "Auto (Smart Model Routing)"},
]

HIGGSFIELD_VIDEO_MODELS = [
    {"id": "seedance_2_5", "name": "Seedance 2.5 (SOTA Default · Cinematic & Motion)"},
    {"id": "kling3_0", "name": "Kling 3.0 (Motion & Audio Sync)"},
    {"id": "kling3_0_turbo", "name": "Kling 3.0 Turbo (Fast Motion)"},
    {"id": "veo3_1", "name": "Google Veo 3.1 (Ultra-Realistic Cinematic)"},
    {"id": "veo3_1_lite", "name": "Google Veo 3.1 Lite (Fast & Cost-Effective)"},
    {"id": "cinematic_studio_video_4_0", "name": "Cinema Studio 4.0 (Film Camera & Lighting)"},
    {"id": "gemini_omni", "name": "Gemini Omni Flash (Multimodal Video)"},
    {"id": "seedance_2_0", "name": "Seedance 2.0 (Up to 4K + Native Audio)"},
]


def _req(path, body=None, timeout=900):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(WORKER + path, data=data, headers={"Content-Type": "application/json"}, method="POST" if data else "GET")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read())


def worker_up():
    if not paths.port_open(8504):
        return None
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
    log = open(paths.DATA / "ai_worker.log", "a", encoding="utf-8")
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
    files = sorted((p for p in OUT.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".mp4"}), key=lambda p: -p.stat().st_mtime)
    out = []
    for p in files[:limit]:
        suf = p.suffix.lower()
        kind = "image" if suf in {".png", ".jpg", ".jpeg", ".webp"} else ("video" if suf == ".mp4" else "audio")
        item = {"name": p.name, "kind": kind,
                "created": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%dT%H:%M"), "size": p.stat().st_size, "prompt": ""}
        if suf == ".png":
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


def higgsfield_generate(model: str, prompt: str, aspect_ratio: str = "1:1", duration: int | None = None,
                        start_image: str | None = None, kind: str = "image"):
    """Run `higgsfield generate create <model> ... --wait` and download resulting media into D:\\Daybook\\Creations."""
    exe = claude_link._higgsfield_exe()
    if not exe:
        raise RuntimeError("Higgsfield CLI isn't installed yet — click '⚡ 1-Click Setup Higgsfield' above.")
    info = claude_link._higgsfield_info(exe)
    if not info.get("signed_in"):
        claude_link.login_higgsfield()
        raise RuntimeError("Higgsfield isn't signed in yet — complete the login in the browser window that just opened, then press Create again.")

    cmd = [exe, "generate", "create", model, "--prompt", prompt, "--aspect_ratio", aspect_ratio]
    if kind == "video":
        if duration:
            cmd += ["--duration", str(duration)]
        if start_image:
            img_path = OUT / Path(start_image).name
            if img_path.exists():
                cmd += ["--start-image", str(img_path)]
    cmd.append("--wait")

    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=claude_link.NO_WINDOW)
    combined = (r.stdout or "") + "\n" + (r.stderr or "")
    if r.returncode != 0 and "No workspace selected" in combined:
        claude_link._ensure_higgsfield_workspace(exe)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=claude_link.NO_WINDOW)
        combined = (r.stdout or "") + "\n" + (r.stderr or "")
    if r.returncode != 0:
        err_msg = (r.stderr or r.stdout or "Higgsfield generation failed").strip()
        if "Not authenticated" in err_msg or "Session expired" in err_msg:
            claude_link.login_higgsfield()
            raise RuntimeError("Your Higgsfield session expired — sign in in the browser window that just opened, then try again.")
        raise RuntimeError(err_msg[:300])

    urls = []
    for u in re.findall(r"https://[^\s\"'<>]+", combined):
        u_clean = u.rstrip(".,;)]}")
        if u_clean not in urls:
            urls.append(u_clean)
    if not urls:
        raise RuntimeError(f"Higgsfield finished without a download URL: {combined.strip()[:240]}")

    OUT.mkdir(parents=True, exist_ok=True)
    saved = []
    default_ext = ".mp4" if kind == "video" else ".png"
    for idx, u in enumerate(urls):
        ext = default_ext
        path_part = u.split("?")[0].lower()
        for cand_ext in (".mp4", ".png", ".jpg", ".jpeg", ".webp"):
            if path_part.endswith(cand_ext):
                ext = cand_ext
                break
        req = urllib.request.Request(u, headers={"User-Agent": "Daybook/1.8"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        name = f"higgsfield-{model}-{datetime.now():%Y%m%d-%H%M%S}-{idx}{ext}"
        (OUT / name).write_bytes(data)
        saved.append(name)

    elapsed = round(time.perf_counter() - t0, 1)
    return {"files": saved, "urls": urls, "seconds": elapsed, "device": f"Higgsfield ({model})"}


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
    hf = claude_link._higgsfield_info()
    return jsonify(worker=s, image_model=(paths.DATA / "ai-models" / "sdxl-turbo" / "model_index.json").exists(),
                   tts_model=Path(r"D:\coqui-models\tts\tts_models--multilingual--multi-dataset--xtts_v2").exists(),
                   gemini=bool(os.environ.get("GEMINI_API_KEY") or _user_env("GEMINI_API_KEY")),
                   higgsfield={**hf, "image_models": HIGGSFIELD_IMAGE_MODELS, "video_models": HIGGSFIELD_VIDEO_MODELS},
                   styles=list(STYLES), voices=voices(), creations=creations(60), out=str(OUT))


@bp.post("/api/studio/image")
def st_image():
    j = request.get_json() or {}
    prompt = (j.get("prompt") or "").strip() + STYLES.get(j.get("style", "none"), "")
    try:
        if j.get("engine") == "higgsfield":
            hf_model = j.get("hf_model") or "gpt_image_2_5"
            ar = j.get("aspect_ratio") or "1:1"
            res = higgsfield_generate(hf_model, prompt, aspect_ratio=ar, kind="image")
            return jsonify(**res, engine="higgsfield")
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


@bp.post("/api/studio/video")
def st_video():
    j = request.get_json() or {}
    prompt = (j.get("prompt") or "").strip()
    if not prompt:
        return jsonify(error="Please enter a video prompt"), 400
    try:
        hf_model = j.get("hf_model") or "seedance_2_5"
        ar = j.get("aspect_ratio") or "16:9"
        dur = int(j.get("duration") or 5)
        start_img = j.get("start_image") or None
        res = higgsfield_generate(hf_model, prompt, aspect_ratio=ar, duration=dur, start_image=start_img, kind="video")
        return jsonify(**res, engine="higgsfield")
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400


@bp.post("/api/studio/higgsfield/setup")
def st_hf_setup():
    d = request.get_json(force=True, silent=True) or {}
    try:
        msg = claude_link.connect_higgsfield(login=bool(d.get("login", True)))
        return jsonify(ok=True, message=msg, higgsfield=claude_link._higgsfield_info())
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400


@bp.post("/api/studio/higgsfield/login")
def st_hf_login():
    try:
        msg = claude_link.login_higgsfield()
        return jsonify(ok=True, message=msg, higgsfield=claude_link._higgsfield_info())
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
    return send_from_directory(OUT, Path(name).name, conditional=True)

