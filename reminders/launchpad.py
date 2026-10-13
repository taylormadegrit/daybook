"""Launchpad: browser profiles (and the account signed in to each) + your apps, launched in one click.
Only profile *names, account name/email and picture* are read (from each browser's 'Local State' /
profiles.ini) — never cookies, history or passwords. Apps come from the Start Menu."""
import configparser
import json
import os
import subprocess
import time
import winreg
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from . import db

bp = Blueprint("launchpad", __name__)
LA, RA, PF, PF86 = (os.environ.get(k, "") for k in ("LOCALAPPDATA", "APPDATA", "ProgramFiles", "ProgramFiles(x86)"))
ICON_DIR = Path(__file__).resolve().parent.parent / "data" / "appicons"
APPS_CACHE = Path(__file__).resolve().parent.parent / "data" / "apps_cache.json"

# Chromium-family browsers: (id, name, user-data dir, exe candidates, brand color)
CHROMIUM = [
    ("chrome", "Google Chrome", rf"{LA}\Google\Chrome\User Data", [rf"{PF}\Google\Chrome\Application\chrome.exe", rf"{PF86}\Google\Chrome\Application\chrome.exe", rf"{LA}\Google\Chrome\Application\chrome.exe"], "#4285f4"),
    ("edge", "Microsoft Edge", rf"{LA}\Microsoft\Edge\User Data", [rf"{PF86}\Microsoft\Edge\Application\msedge.exe", rf"{PF}\Microsoft\Edge\Application\msedge.exe"], "#0c8fd8"),
    ("brave", "Brave", rf"{LA}\BraveSoftware\Brave-Browser\User Data", [rf"{PF}\BraveSoftware\Brave-Browser\Application\brave.exe", rf"{LA}\BraveSoftware\Brave-Browser\Application\brave.exe"], "#fb542b"),
    ("comet", "Comet", rf"{LA}\Perplexity\Comet\User Data", [rf"{LA}\Perplexity\Comet\Application\comet.exe"], "#20b8cd"),
    ("vivaldi", "Vivaldi", rf"{LA}\Vivaldi\User Data", [rf"{LA}\Vivaldi\Application\vivaldi.exe", rf"{PF}\Vivaldi\Application\vivaldi.exe"], "#ef3939"),
    ("opera", "Opera", rf"{RA}\Opera Software\Opera Stable", [rf"{LA}\Programs\Opera\opera.exe"], "#ff1b2d"),
    ("operagx", "Opera GX", rf"{RA}\Opera Software\Opera GX Stable", [rf"{LA}\Programs\Opera GX\opera.exe"], "#fa1e4e"),
    ("chromium", "Chromium", rf"{LA}\Chromium\User Data", [rf"{LA}\Chromium\Application\chrome.exe"], "#5f8ff2"),
    ("thorium", "Thorium", rf"{LA}\Thorium\User Data", [rf"{LA}\Thorium\Application\thorium.exe"], "#3b82f6"),
    ("arc", "Arc", rf"{LA}\Packages\TheBrowserCompany.Arc_ttt1ap7aakyb4\LocalCache\Local\Arc\User Data", [], "#fc5f5f"),
]
FIREFOX = [("firefox", "Firefox", rf"{RA}\Mozilla\Firefox", [rf"{PF}\Mozilla Firefox\firefox.exe", rf"{PF86}\Mozilla Firefox\firefox.exe"], "#ff7139"),
           ("zen", "Zen", rf"{RA}\zen", [rf"{PF}\Zen Browser\zen.exe"], "#f2b544"),
           ("librewolf", "LibreWolf", rf"{RA}\librewolf", [rf"{PF}\LibreWolf\librewolf.exe"], "#00acff")]
QUICK_LINKS = [("Gmail", "https://mail.google.com"), ("YouTube", "https://www.youtube.com"), ("YouTube Studio", "https://studio.youtube.com"),
               ("Drive", "https://drive.google.com"), ("Calendar", "https://calendar.google.com"), ("Facebook", "https://www.facebook.com")]


def _exe(cands, regname=None):
    for c in cands:
        if c and os.path.exists(c):
            return c
    if regname:  # App Paths registry (where installers register the real location)
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{regname}") as k:
                    p = winreg.QueryValue(k, None)
                    if p and os.path.exists(p):
                        return p
            except OSError:
                pass
    return None


def _argb(n):
    try:
        n = int(n) & 0xFFFFFFFF
        return f"#{(n >> 16) & 255:02x}{(n >> 8) & 255:02x}{n & 255:02x}"
    except Exception:
        return None


def browsers():
    out = []
    for bid, name, udir, cands, color in CHROMIUM:
        ls = Path(udir) / "Local State"
        if not ls.exists():
            continue
        exe = _exe(cands, {"chrome": "chrome.exe", "edge": "msedge.exe", "brave": "brave.exe"}.get(bid))
        try:
            cache = json.loads(ls.read_text(encoding="utf-8")).get("profile", {}).get("info_cache", {})
        except Exception:
            cache = {}
        profiles = []
        for pdir, v in cache.items():
            pic = Path(udir) / pdir / "Google Profile Picture.png"
            profiles.append({"id": pdir, "name": v.get("name") or pdir, "account": v.get("gaia_name") or "",
                             "email": v.get("user_name") or "", "picture": pic.exists(),
                             "color": _argb(v.get("default_avatar_fill_color")) or color,
                             "last": v.get("active_time", 0)})
        profiles.sort(key=lambda p: (p["id"] != "Default", p["id"].startswith("Profile") and int("0" + "".join(c for c in p["id"] if c.isdigit()))))
        out.append({"id": bid, "name": name, "color": color, "exe": exe, "profiles": profiles})
    for bid, name, root, cands, color in FIREFOX:
        ini = Path(root) / "profiles.ini"
        if not ini.exists():
            continue
        cp = configparser.ConfigParser()
        cp.read(ini, encoding="utf-8")
        profiles = [{"id": cp[s]["Name"], "name": cp[s]["Name"], "account": "", "email": "", "picture": False, "color": color, "last": 0}
                    for s in cp.sections() if s.startswith("Profile") and "Name" in cp[s]]
        out.append({"id": bid, "name": name, "color": color, "exe": _exe(cands, "firefox.exe" if bid == "firefox" else None), "profiles": profiles})
    return out


def launch_browser(bid, profile, url=""):
    b = next((x for x in browsers() if x["id"] == bid), None)
    if not b or not b["exe"]:
        raise ValueError("That browser isn't installed where Daybook can find it")
    if bid in {f[0] for f in FIREFOX}:
        args = [b["exe"], "-P", profile] + ([url] if url else [])
    else:
        args = [b["exe"], f"--profile-directory={profile}"] + ([url] if url else [])
    subprocess.Popen(args, close_fds=True, creationflags=0x00000008)  # DETACHED_PROCESS


def avatar_path(bid, profile):
    for x in CHROMIUM:
        if x[0] == bid:
            p = Path(x[2]) / Path(profile).name / "Google Profile Picture.png"
            return p if p.exists() else None
    return None


# ---------------- apps (Start Menu) ----------------
PS_SCAN = r"""
$ws = New-Object -ComObject WScript.Shell
$dirs = @("$env:APPDATA\Microsoft\Windows\Start Menu\Programs", "$env:ProgramData\Microsoft\Windows\Start Menu\Programs")
$out = foreach ($d in $dirs) { Get-ChildItem $d -Recurse -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
  try { $l = $ws.CreateShortcut($_.FullName); [pscustomobject]@{name=$_.BaseName; lnk=$_.FullName; target=$l.TargetPath; args=$l.Arguments; icon=$l.IconLocation; folder=$_.Directory.Name} } catch {} } }
$out | ConvertTo-Json -Compress
"""
SKIP = ("uninstall", "readme", "help", "documentation", "release notes", "website", "license", "manual", "debug", "safe mode",
        "repair", "support", "changelog", "what's new", "visit", "send feedback", "report")
CATEGORY_HINTS = {  # name keyword → shelf
    "Create": ["davinci", "resolve", "obs", "capcut", "premiere", "after effects", "photoshop", "blender", "studio one", "audacity",
               "fl studio", "ableton", "artcraft", "gimp", "krita", "fusion", "lightroom", "canva", "streamlabs", "elgato", "presonus", "arturia", "openscad", "orcaslicer"],
    "Work": ["word", "excel", "powerpoint", "outlook", "onenote", "libreoffice", "notion", "obsidian", "code", "pycharm", "visual studio",
             "orca", "antigravity", "claude", "ollama", "grammarly", "git", "terminal", "ghidra", "metatrader", "webull", "tradelocker"],
    "Play": ["steam", "epic", "pcsx2", "cemu", "rpcs3", "remote play", "play games", "battle.net", "xbox", "roblox", "riot"],
    "Social": ["discord", "telegram", "whatsapp", "slack", "zoom", "teams", "spotify"],
}


def scan_apps(force=False):
    if not force and APPS_CACHE.exists() and time.time() - APPS_CACHE.stat().st_mtime < 6 * 3600:
        return json.loads(APPS_CACHE.read_text(encoding="utf-8"))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", PS_SCAN], capture_output=True, text=True, timeout=90,
                       creationflags=0x08000000)
    try:
        raw = json.loads(r.stdout or "[]")
    except Exception:
        raw = []
    if isinstance(raw, dict):
        raw = [raw]
    seen, apps = set(), []
    for a in raw:
        n = (a.get("name") or "").strip()
        low = n.lower()
        if not n or any(s in low for s in SKIP) or low in seen or a.get("folder", "").lower() == "startup":
            continue
        tgt = a.get("target") or ""
        if tgt and not tgt.lower().endswith((".exe", ".bat", ".cmd", ".url", ".pyw", ".msc")) and not a.get("args"):
            continue
        seen.add(low)
        shelf = next((c for c, keys in CATEGORY_HINTS.items() if any(k in low for k in keys)), "Other")
        apps.append({"id": _app_id(n), "name": n, "lnk": a["lnk"], "target": tgt, "icon": a.get("icon") or "", "shelf": shelf})
    for name, exe, shelf in EXTRA_APPS:  # apps that live outside the Start Menu (e.g. unpacked into D:\Applications)
        if os.path.exists(exe) and _app_id(name) not in {a["id"] for a in apps}:
            apps.append({"id": _app_id(name), "name": name, "lnk": exe, "target": exe, "icon": "", "shelf": shelf})
    apps.sort(key=lambda x: x["name"].lower())
    APPS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    APPS_CACHE.write_text(json.dumps(apps), encoding="utf-8")
    return apps


def _app_id(name):
    return "".join(c for c in name.lower() if c.isalnum())[:40]


def app_icon(app_id):
    """256px icon pulled from the app's exe (or .ico), cached as PNG."""
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    out = ICON_DIR / f"{app_id}.png"
    if out.exists():
        return out
    app = next((a for a in scan_apps() if a["id"] == app_id), None)
    if not app:
        return None
    src = (app["icon"].split(",")[0].strip() if app["icon"] and not app["icon"].startswith(",") else "") or app["target"]
    src = os.path.expandvars(src)
    try:
        from PIL import Image
        if src.lower().endswith(".ico"):
            im = Image.open(src)
        else:
            from icoextract import IconExtractor
            tmp = ICON_DIR / f"{app_id}.ico"
            IconExtractor(src).export_icon(str(tmp))  # first (main) icon group, every size
            im = Image.open(tmp)
            im.load()
        if hasattr(im, "ico"):
            size = max(im.ico.sizes())
            im = im.ico.getimage(size)
        im.convert("RGBA").resize((128, 128), Image.LANCZOS).save(out)
        return out
    except Exception:
        return None


def pinned():
    try:
        return json.loads(db.setting("launch_apps") or "[]")
    except Exception:
        return []


EXTRA_APPS = [("DaVinci Resolve", r"D:\Applications\Resolve.exe", "Create"),
              ("DaVinci Resolve", r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe", "Create"),
              ("ArtCraft", r"D:\Applications\ArtCraft\artcraft.exe", "Create")]
DEFAULT_PINS = ["davinciresolve", "obsstudio", "capcut", "discord", "steam", "blender", "studioone7", "orca", "visualstudiocode", "spotify"]


# ---------------- routes ----------------

@bp.get("/api/launchpad")
def lp_state():
    apps = scan_apps(request.args.get("rescan") == "1")
    pins = pinned()
    if not pins:  # first run: pin the creative/productivity apps you actually have
        have = {a["id"] for a in apps}
        pins = [p for p in DEFAULT_PINS if p in have]
        if not any("resolve" in p for p in pins):
            pins += [a["id"] for a in apps if "resolve" in a["id"]][:1]
        db.set_settings({"launch_apps": json.dumps(pins)})
    by_id = {a["id"]: a for a in apps}
    return jsonify(browsers=browsers(), apps=apps, pinned=[by_id[p] for p in pins if p in by_id], quick_links=QUICK_LINKS)


@bp.post("/api/launchpad/browser")
def lp_browser():
    j = request.get_json() or {}
    try:
        launch_browser(j.get("browser"), j.get("profile"), j.get("url", ""))
    except Exception as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True)


@bp.post("/api/launchpad/app/<app_id>")
def lp_app(app_id):
    a = next((x for x in scan_apps() if x["id"] == app_id), None)
    if not a:
        return jsonify(error="App not found — try Rescan"), 404
    os.startfile(a["lnk"])  # the shortcut keeps the app's own working folder + arguments
    return jsonify(ok=True)


@bp.post("/api/launchpad/pins")
def lp_pins():
    db.set_settings({"launch_apps": json.dumps((request.get_json() or {}).get("pins", [])[:40])})
    return jsonify(ok=True)


@bp.get("/app-icon/<app_id>.png")
def lp_icon(app_id):
    p = app_icon(app_id)
    return send_file(p) if p else ("", 404)


@bp.get("/browser-avatar/<bid>/<path:profile>")
def lp_avatar(bid, profile):
    p = avatar_path(bid, profile)
    return send_file(p, max_age=3600) if p else ("", 404)
