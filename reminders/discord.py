"""Send to Discord. Two ways:
1. Webhook (automatic): Daybook posts the file straight into a channel you picked. Discord caps webhook
   uploads by the server's boost level (10 MB, 50 MB at level 2, 100 MB at level 3). Bigger audio/video is
   compressed with ffmpeg to fit; other big files can't go by webhook.
2. 'Copy for the Discord app': the file goes on the clipboard and Discord opens — paste it into any chat.
   That uses YOUR account's limit (up to 500 MB with Nitro)."""
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

from . import db

bp = Blueprint("discord", __name__)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "outbox"
HOOK_RE = re.compile(r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
MEDIA = {".mp3", ".m4a", ".wav", ".webm", ".ogg", ".opus", ".aac", ".flac", ".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts"}
NITRO_MAX = 500 * 1024 * 1024


def hooks():
    try:
        return json.loads(db.setting("discord_hooks") or "[]")
    except Exception:
        return []


def _ffmpeg():
    return shutil.which("ffmpeg") or next((str(p) for p in Path(os.environ.get("LOCALAPPDATA", "")).glob(
        "Microsoft/WinGet/Packages/*FFmpeg*/**/bin/ffmpeg.exe")), None)


def _post(url, path, content):
    """multipart/form-data POST of one file + message. Returns (ok, status, text)."""
    boundary = uuid.uuid4().hex
    fname = Path(path).name
    ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    payload = json.dumps({"content": content[:1900], "username": "Daybook"}).encode()
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\nContent-Type: application/json\r\n\r\n").encode() + payload + \
        (f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"{fname}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    size = len(head) + os.path.getsize(path) + len(tail)

    def body():
        yield head
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                yield chunk
        yield tail
    req = urllib.request.Request(url, data=b"".join(body()), method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(size),
                                          "User-Agent": "Daybook (local app, 1.3)"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return True, r.status, ""
    except urllib.error.HTTPError as e:
        return False, e.code, e.read().decode(errors="ignore")[:300]


def compress(path, target_bytes):
    """Re-encode audio/video so it fits under target_bytes (keeps it watchable/listenable)."""
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg isn't installed, so Daybook can't shrink this file")
    import av
    with av.open(str(path)) as c:
        dur = (c.duration or 0) / 1_000_000 or 60
        has_video = any(s.type == "video" for s in c.streams)
    total_kbps = max(48, int(target_bytes * 8 * 0.92 / dur / 1000))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if has_video:
        a_kbps = 96 if total_kbps > 600 else 64
        v_kbps = max(150, total_kbps - a_kbps)
        height = 1080 if v_kbps > 3500 else 720 if v_kbps > 1200 else 480
        out = OUT_DIR / (Path(path).stem + "-discord.mp4")
        args = [ff, "-y", "-loglevel", "error", "-i", str(path), "-vf", f"scale=-2:'min({height},ih)'", "-c:v", "libx264", "-preset", "veryfast",
                "-b:v", f"{v_kbps}k", "-maxrate", f"{v_kbps}k", "-bufsize", f"{v_kbps * 2}k", "-c:a", "aac", "-b:a", f"{a_kbps}k", "-movflags", "+faststart", str(out)]
    else:
        out = OUT_DIR / (Path(path).stem + "-discord.m4a")
        args = [ff, "-y", "-loglevel", "error", "-i", str(path), "-vn", "-c:a", "aac", "-b:a", f"{min(160, max(24, total_kbps))}k", str(out)]
    subprocess.run(args, check=True, creationflags=0x08000000, timeout=3600)
    return out


def send(hook_url, path, message=""):
    """Send one file via webhook; shrinks media that's too big. Returns a short status string."""
    if not HOOK_RE.match(hook_url or ""):
        raise ValueError("That doesn't look like a Discord webhook link")
    path = Path(path)
    ok, code, txt = _post(hook_url, path, message)
    if ok:
        return "sent"
    if code == 413 and path.suffix.lower() in MEDIA:
        for limit in (95, 48, 9.5):  # try the biggest tier first: level 3, level 2, no boost
            if path.stat().st_size <= limit * 1024 * 1024:
                continue
            small = compress(path, int(limit * 1024 * 1024))
            ok, code, txt = _post(hook_url, small, message + f"\n(compressed to fit Discord: {small.stat().st_size / 1048576:.1f} MB)")
            small.unlink(missing_ok=True)
            if ok:
                return "sent (compressed)"
            if code != 413:
                break
    if code == 413:
        raise RuntimeError("Too big for this server's upload limit — use 'Copy for Discord app' instead (up to 500 MB with Nitro)")
    raise RuntimeError(f"Discord said {code}: {txt[:160]}")


def copy_for_app(path):
    """Put the file on the clipboard and open Discord: paste (Ctrl+V) into any chat."""
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -LiteralPath $args[0]", str(path)],
                   creationflags=0x08000000, timeout=20)
    try:
        os.startfile("discord://")
    except OSError:
        pass


# ---------------- files to send: notes as .txt / .pdf ----------------

def _safe(name):
    return re.sub(r'[\\/:*?"<>|]+', "", name).strip()[:80] or "note"


def note_file(nid, fmt="txt"):
    from . import notes
    n = notes.get(nid)
    if not n:
        raise ValueError("Note not found")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    title = n["title"] or "Untitled note"
    if fmt == "txt":
        p = OUT_DIR / f"{_safe(title)}.txt"
        p.write_text(f"{title}\n{n['note_date']}{'  ·  ' + n['category'] if n['category'] else ''}\n\n{n['body']}\n", encoding="utf-8")
        return p
    return note_pdf(title, n)


def note_pdf(title, n):
    from fpdf import FPDF
    pdf = FPDF(format="Letter")
    pdf.set_auto_page_break(True, 18)
    pdf.add_page()
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    pdf.add_font("ui", "", str(fonts / "segoeui.ttf"))
    pdf.add_font("ui", "B", str(fonts / "segoeuib.ttf"))
    clean = lambda s: "".join(ch for ch in s if ord(ch) < 0x10000)  # drop emoji the font can't draw
    pdf.set_font("ui", "B", 20)
    pdf.multi_cell(0, 10, clean(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("ui", "", 10)
    pdf.set_text_color(110, 110, 120)
    pdf.cell(0, 7, f"{n['note_date']}{'  ·  ' + n['category'] if n['category'] else ''}  ·  Daybook", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_text_color(20, 20, 25)
    for line in n["body"].splitlines():
        t = clean(line.rstrip())
        if t.startswith("#"):
            lvl = len(t) - len(t.lstrip("#"))
            pdf.ln(2)
            pdf.set_font("ui", "B", {1: 16, 2: 13}.get(lvl, 12))
            pdf.multi_cell(0, 8, t.lstrip("#").strip().replace("**", ""), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("ui", "", 11)
        else:
            pdf.set_font("ui", "", 11)
            t = re.sub(r"^- \[ \]", "☐", t)
            t = re.sub(r"^- \[x\]", "☑", t, flags=re.I)
            t = re.sub(r"^- ", "•  ", t)
            pdf.multi_cell(0, 6.2, t.replace("**", "") or " ", new_x="LMARGIN", new_y="NEXT")
    p = OUT_DIR / f"{_safe(title)}.pdf"
    pdf.output(str(p))
    return p


def resolve(kind, ref, fmt="txt"):
    """What file are we sending? kind: note | memo | file | creation | annotation"""
    if kind == "note":
        return note_file(int(ref), fmt)
    if kind == "memo":
        from . import memos
        m = memos.get(int(ref))
        if not m:
            raise ValueError("Memo not found")
        src = memos.media(m)
        if m["title"] and not m["path"]:  # give it a readable name in Discord
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            named = OUT_DIR / (_safe(m["title"]) + src.suffix)
            shutil.copy2(src, named)
            return named
        return src
    if kind == "annotation":
        from . import annotate_store
        return annotate_store.folder() / Path(ref).name
    if kind == "creation":
        from . import studio
        return studio.OUT / Path(ref).name
    if kind == "file":
        p = Path(ref)
        if not p.is_file():
            raise ValueError("File not found")
        return p
    raise ValueError("Unknown item")


@bp.get("/api/discord")
def dc_state():
    return jsonify(hooks=[{"name": h["name"], "id": i} for i, h in enumerate(hooks())], nitro_mb=500)


@bp.post("/api/discord/hooks")
def dc_hooks():
    """Replace the saved channel list. Each: {name, url} — url kept only on this PC."""
    j = request.get_json() or {}
    out, old = [], hooks()
    for h in j.get("hooks", []):
        url = (h.get("url") or "").strip() or (old[h["id"]]["url"] if isinstance(h.get("id"), int) and h["id"] < len(old) else "")
        if not HOOK_RE.match(url):
            return jsonify(error=f"“{h.get('name') or 'Channel'}”: paste the full webhook link (https://discord.com/api/webhooks/…)"), 400
        out.append({"name": (h.get("name") or "Discord").strip()[:40], "url": url})
    db.set_settings({"discord_hooks": json.dumps(out)})
    return jsonify(ok=True, count=len(out))


@bp.post("/api/discord/test/<int:i>")
def dc_test(i):
    hs = hooks()
    if i >= len(hs):
        return jsonify(error="No such channel"), 404
    req = urllib.request.Request(hs[i]["url"], data=json.dumps({"content": "✅ Daybook is connected to this channel.", "username": "Daybook"}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Daybook (local app, 1.3)"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=20)
    except urllib.error.HTTPError as e:
        return jsonify(error=f"Discord said {e.code} — is the webhook still there?"), 400
    return jsonify(ok=True)


SECRET_RE = re.compile(r"AIza[0-9A-Za-z_-]{30,}|\bAQ\.[0-9A-Za-z_-]{20,}|\bsk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|xox[abps]-[A-Za-z0-9-]{10,}|"
                       r"discord(?:app)?\.com/api/webhooks/\d+/[\w-]+|\b(?:password|passwd|api[ _-]?key|secret|token)\b\s*[:=]?\s*\S{6,}", re.I)


def secret_warning(kind, ref):
    """Notes sometimes hold keys/passwords — warn before they leave this PC."""
    if kind != "note":
        return ""
    from . import notes
    n = notes.get(int(ref)) or {}
    hits = SECRET_RE.findall((n.get("body") or "") + " " + (n.get("title") or ""))
    return f"This note looks like it contains {len(hits)} key/password{'s' if len(hits) > 1 else ''}. Remove it before sharing." if hits else ""


@bp.post("/api/discord/info")
def dc_info():
    j = request.get_json() or {}
    try:
        p = resolve(j.get("kind"), j.get("ref"), j.get("fmt", "txt"))
    except Exception as e:
        return jsonify(error=str(e)), 400
    return jsonify(name=p.name, size=p.stat().st_size, media=p.suffix.lower() in MEDIA, nitro_ok=p.stat().st_size <= NITRO_MAX,
                   warning=secret_warning(j.get("kind"), j.get("ref")))


@bp.post("/api/discord/send")
def dc_send():
    j = request.get_json() or {}
    try:
        p = resolve(j.get("kind"), j.get("ref"), j.get("fmt", "txt"))
        if j.get("mode") == "app":
            if p.stat().st_size > NITRO_MAX:
                return jsonify(error="Over 500 MB — too big even with Nitro"), 400
            copy_for_app(p)
            return jsonify(ok=True, result="copied")
        hs = hooks()
        i = int(j.get("hook", 0))
        if i >= len(hs):
            return jsonify(error="Add a Discord channel first (Settings → Discord)"), 400
        return jsonify(ok=True, result=send(hs[i]["url"], p, j.get("message", "")))
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400
