"""Games: your installed Steam + Epic games (launched through their own launchers, so your accounts and
offline mode work as usual) and a library of free, open-source games downloaded from their official
GitHub releases into a folder on D:."""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import winreg
import zipfile
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from . import db, paths

bp = Blueprint("games", __name__)
CACHE = paths.DATA / "games"
UA = {"User-Agent": "Daybook-games (local app)", "Accept": "application/vnd.github+json"}

# Free & open-source. 'own' = an open-source engine that needs files from a game you own.
CATALOG = [
    dict(id="supertuxkart", name="SuperTuxKart", repo="supertuxkart/stk-code", genre="Racing", asset=r"-win\.zip$", desc="Kart racing with online play, story mode and battle arenas."),
    dict(id="supertux", name="SuperTux", repo="SuperTux/supertux", genre="Platformer", asset=r"win64\.msi$|windows.*64.*\.msi$", desc="Classic side-scrolling platformer in the spirit of Super Mario."),
    dict(id="mindustry", name="Mindustry", repo="Anuken/Mindustry", genre="Strategy", asset=r"^Mindustry\.jar$", java=True, desc="Factory-building tower defense. Huge, polished, endlessly replayable."),
    dict(id="shatteredpd", name="Shattered Pixel Dungeon", repo="00-Evan/shattered-pixel-dungeon", genre="Roguelike", asset=r"windows.*\.(zip|msi)$|win.*\.zip$", desc="Award-winning pixel-art dungeon crawler."),
    dict(id="luanti", name="Luanti (Minetest)", repo="luanti-org/luanti", genre="Sandbox", asset=r"win64\.zip$", desc="Open-source Minecraft-style voxel sandbox with thousands of mods."),
    dict(id="unciv", name="Unciv", repo="yairm210/Unciv", genre="Strategy", asset=r"windows64\.zip$|win.*64.*\.zip$", desc="Open-source remake of Civilization V."),
    dict(id="endlesssky", name="Endless Sky", repo="endless-sky/endless-sky", genre="Space", asset=r"win64.*\.zip$|windows.*\.zip$", desc="Space trading and combat, inspired by Escape Velocity."),
    dict(id="pixelwheels", name="Pixel Wheels", repo="agateau/pixelwheels", genre="Racing", asset=r"windows.*\.zip$|win.*\.zip$", desc="Retro top-down racing with up to 4-player split screen."),
    dict(id="teeworlds", name="Teeworlds", repo="teeworlds/teeworlds", genre="Shooter", asset=r"win64\.zip$", desc="Fast 2D online multiplayer shooter."),
    dict(id="openspades", name="OpenSpades", repo="yvt/openspades", genre="Shooter", asset=r"windows.*\.zip$|win.*\.zip$", desc="Voxel FPS, compatible with Ace of Spades servers."),
    dict(id="taisei", name="Taisei Project", repo="taisei-project/taisei", genre="Shmup", asset=r"windows.*64.*\.(zip|exe)$|win64.*\.(zip|exe)$", desc="Bullet-hell shooter in the Touhou style."),
    dict(id="powdertoy", name="The Powder Toy", repo="The-Powder-Toy/The-Powder-Toy", genre="Sandbox", asset=r"^powder(?!.*steam).*x86_64-windows-msvc\.exe$", portable=True, desc="Physics sandbox — fire, electricity, explosions."),
    dict(id="cdda", name="Cataclysm: Dark Days Ahead", repo="CleverRaven/Cataclysm-DDA", genre="Survival", asset=r"windows-with-graphics-and-sounds-x64.*\.zip$|windows-tiles-sounds-x64.*\.zip$", desc="Deep post-apocalyptic survival roguelike."),
    dict(id="openra", name="OpenRA", repo="OpenRA/OpenRA", genre="RTS", asset=r"x64\.exe$|win.*\.exe$", desc="Classic Command & Conquer, Red Alert and Dune 2000 rebuilt (game files download free in-game)."),
    dict(id="openrct2", name="OpenRCT2", repo="OpenRCT2/OpenRCT2", genre="Sim", own="RollerCoaster Tycoon 2", asset=r"windows-portable-x64\.zip$|windows.*x64.*\.zip$", desc="Improved RollerCoaster Tycoon 2 engine."),
    dict(id="openmw", name="OpenMW", repo="OpenMW/openmw", genre="RPG", own="Morrowind", asset=r"win64\.exe$|windows.*\.exe$", desc="Modern engine for The Elder Scrolls III: Morrowind."),
    dict(id="fheroes2", name="fheroes2", repo="ihhub/fheroes2", genre="Strategy", own="Heroes of Might and Magic II (free demo works)", asset=r"windows.*x64.*\.zip$", desc="Heroes of Might and Magic II remake."),
    dict(id="julius", name="Julius", repo="bvschaik/julius", genre="City builder", own="Caesar III", asset=r"windows.*64.*\.zip$|win.*\.zip$", desc="Caesar III, rebuilt and bug-fixed."),
    dict(id="shipwright", name="Ship of Harkinian", repo="HarbourMasters/Shipwright", genre="Adventure", own="your own Ocarina of Time ROM", asset=r"win.*\.zip$", desc="PC port of Ocarina of Time — 60 fps, widescreen, mods."),
]
CAT = {g["id"]: g for g in CATALOG}
JOBS = {}  # id → {"state", "pct", "msg"}


def games_dir():
    return Path(db.setting("games_dir") or r"D:\Games\Daybook")


# ---------------- Steam ----------------

def steam_root():
    for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"), (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
        try:
            with winreg.OpenKey(hive, key) as k:
                for v in ("SteamPath", "InstallPath"):
                    try:
                        p = Path(winreg.QueryValueEx(k, v)[0])
                        if p.exists():
                            return p
                    except OSError:
                        pass
        except OSError:
            pass
    return None


SKIP_APPS = {"228980", "1070560", "1391110", "1628350", "1493710", "250820", "1826330"}  # redistributables, runtimes, SteamVR


def steam_games():
    root = steam_root()
    if not root:
        return []
    libs = {root / "steamapps"}
    vdf = root / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for p in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore")):
            libs.add(Path(p.replace("\\\\", "\\")) / "steamapps")
    out = []
    for lib in libs:
        for acf in lib.glob("appmanifest_*.acf"):
            t = acf.read_text(encoding="utf-8", errors="ignore")
            g = dict(re.findall(r'"(appid|name|installdir|SizeOnDisk|LastPlayed|StateFlags)"\s+"([^"]*)"', t))
            if not g.get("appid") or g["appid"] in SKIP_APPS or "redistributable" in g.get("name", "").lower():
                continue
            out.append({"id": "steam-" + g["appid"], "src": "steam", "appid": g["appid"], "name": g.get("name", g["appid"]),
                        "dir": str(lib / "common" / g.get("installdir", "")), "size": int(g.get("SizeOnDisk") or 0),
                        "last": int(g.get("LastPlayed") or 0), "ready": g.get("StateFlags") == "4"})
    return out


def steam_art(appid):
    root = steam_root()
    if not root:
        return None
    lc = root / "appcache" / "librarycache"
    for p in (lc / f"{appid}_library_600x900.jpg", lc / appid / "library_600x900.jpg", lc / f"{appid}_header.jpg", lc / appid / "header.jpg"):
        if p.exists():
            return p
    hits = list((lc / appid).glob("*/library_600x900.jpg")) if (lc / appid).exists() else []
    return hits[0] if hits else None


# ---------------- Epic ----------------

def epic_games():
    out = []
    man = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    for item in man.glob("*.item"):
        try:
            j = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if not j.get("bIsApplication", True) or j.get("bIsIncompleteInstall"):
            continue
        out.append({"id": "epic-" + j.get("AppName", item.stem), "src": "epic", "name": j.get("DisplayName") or j.get("AppName"),
                    "dir": j.get("InstallLocation", ""), "exe": str(Path(j.get("InstallLocation", "")) / j.get("LaunchExecutable", "")),
                    "uri": f"com.epicgames.launcher://apps/{j.get('CatalogNamespace')}%3A{j.get('CatalogItemId')}%3A{j.get('AppName')}?action=launch&silent=true",
                    "size": int(j.get("InstallSize") or 0), "last": 0, "ready": True})
    return out


# ---------------- free / open-source ----------------

def _state():
    p = CACHE / "installed.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(s):
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "installed.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


def release(gid):
    """Latest release + the Windows download, from GitHub (cached 6 h)."""
    g = CAT[gid]
    cp = CACHE / f"rel-{gid}.json"
    if cp.exists() and time.time() - cp.stat().st_mtime < 6 * 3600:
        return json.loads(cp.read_text(encoding="utf-8"))
    req = urllib.request.Request(f"https://api.github.com/repos/{g['repo']}/releases?per_page=8", headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        rels = json.loads(r.read())
    pat = re.compile(g["asset"], re.I)
    pick = None
    for rel in rels:  # newest release that actually ships a Windows build (prefer stable)
        if rel.get("draft"):
            continue
        a = next((a for a in rel.get("assets", []) if pat.search(a["name"]) and not re.search(r"debug|symbols|pdb|arm64", a["name"], re.I)), None)
        if a and (not rel.get("prerelease") or not pick):
            pick = {"version": rel.get("tag_name"), "date": rel.get("published_at", "")[:10], "asset": a["name"], "url": a["browser_download_url"],
                    "size": a["size"], "page": rel.get("html_url"), "pre": rel.get("prerelease", False)}
            if not rel.get("prerelease"):
                break
    CACHE.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(pick), encoding="utf-8")
    return pick


def _find_exe(folder, name):
    exes = [p for p in Path(folder).rglob("*.exe") if not re.search(r"unins|setup|crash|update|vc_?redist|dxsetup|install", p.name, re.I)]
    if not exes:
        return None
    key = re.sub(r"[^a-z]", "", name.lower())[:6]
    exes.sort(key=lambda p: (key not in p.stem.lower().replace(" ", ""), len(p.parts), -p.stat().st_size))
    return str(exes[0])


def _download(gid):
    g, job = CAT[gid], JOBS[gid]
    try:
        rel = release(gid)
        if not rel:
            raise RuntimeError("No Windows download in the latest releases")
        dest = games_dir() / gid
        dest.mkdir(parents=True, exist_ok=True)
        tmp = dest / rel["asset"]
        job.update(state="downloading", msg=f"Downloading {rel['asset']}")
        with urllib.request.urlopen(urllib.request.Request(rel["url"], headers={"User-Agent": UA["User-Agent"]}), timeout=60) as r, open(tmp, "wb") as f:
            total, done = int(r.headers.get("Content-Length") or rel["size"] or 0), 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                job["pct"] = round(done * 100 / total) if total else 0
        st = _state()
        entry = {"version": rel["version"], "dir": str(dest), "installed": time.strftime("%Y-%m-%d"), "exe": None, "installer": None}
        if tmp.suffix.lower() == ".zip":
            job.update(state="extracting", msg="Unpacking…")
            with zipfile.ZipFile(tmp) as z:
                z.extractall(dest)
            tmp.unlink()
            entry["exe"] = _find_exe(dest, g["name"])
        elif g.get("portable") or g.get("java"):  # the download IS the game
            entry["exe"] = str(tmp)
        else:  # .exe / .msi installer — the user runs it (it asks where to install)
            entry["installer"] = str(tmp)
        st[gid] = entry
        _save_state(st)
        job.update(state="done", pct=100, msg="Ready" if entry["exe"] else "Downloaded — run the installer")
    except Exception as e:
        job.update(state="error", msg=str(e)[:200])


def _java():
    for p in [*Path(r"D:\Applications").glob("jdk-*/bin/javaw.exe"), shutil.which("javaw"), shutil.which("java")]:
        if p and os.path.exists(p):
            return str(p)
    raise RuntimeError("This game needs Java — install it from adoptium.net")


def _installed_shortcut(g):
    from . import launchpad
    key = re.sub(r"[^a-z0-9]", "", g["name"].lower())[:8]
    stale = not launchpad.APPS_CACHE.exists() or time.time() - launchpad.APPS_CACHE.stat().st_mtime > 60
    for a in launchpad.scan_apps(force=stale):
        if key and key in a["id"] and not re.search(r"unins|setup|readme|server|editor", a["name"], re.I):
            return a["lnk"]
    return None


def library():
    st = _state()
    free = []
    changed = False
    for g in CATALOG:
        e = st.get(g["id"])
        if e and e.get("installer") and not e.get("exe"):  # installer-based: find the shortcut it created
            lnk = _installed_shortcut(g)
            if lnk:
                e["exe"], changed = lnk, True
        free.append({**g, "installed": bool(e), "exe": (e or {}).get("exe"), "installer": (e or {}).get("installer"),
                     "version": (e or {}).get("version"), "job": JOBS.get(g["id"])})
    if changed:
        _save_state(st)
    return free


# ---------------- routes ----------------

@bp.get("/api/games")
def g_list():
    free = library()
    st = _state()
    owned = steam_games() + epic_games()
    for g in free:  # downloaded free games live in your library too
        if g["exe"]:
            e = st.get(g["id"], {})
            owned.append({"id": g["id"], "src": "free", "name": g["name"], "dir": e.get("dir", ""), "size": _dir_size(e.get("dir", "")),
                          "last": e.get("last", 0), "ready": True, "added": e.get("installed", "")})
    for g in owned:
        g["kind"] = kind_of(g["name"])
    for g in free:  # size of the download, if we've looked it up already
        cp = CACHE / f"rel-{g['id']}.json"
        try:
            g["dl_size"] = (json.loads(cp.read_text(encoding="utf-8")) or {}).get("size", 0) if cp.exists() else 0
        except Exception:
            g["dl_size"] = 0
    owned.sort(key=lambda x: -x["last"])
    return jsonify(owned=owned, free=free, games_dir=str(games_dir()), steam=bool(steam_root()))


def _dir_size(d):
    try:
        return sum(f.stat().st_size for f in Path(d).rglob("*") if f.is_file()) if d and len(d) > 3 else 0
    except Exception:
        return 0


@bp.get("/api/games/release/<gid>")
def g_release(gid):
    if gid not in CAT:
        return jsonify(error="unknown game"), 404
    try:
        return jsonify(release(gid) or {})
    except Exception as e:
        return jsonify(error=f"GitHub: {e}"[:200]), 502


@bp.post("/api/games/<gid>/<action>")
def g_action(gid, action):
    j = request.get_json(silent=True) or {}
    try:
        if action == "download" and gid in CAT:
            if JOBS.get(gid, {}).get("state") in ("downloading", "extracting"):
                return jsonify(ok=True)
            JOBS[gid] = {"state": "starting", "pct": 0, "msg": "Starting…"}
            threading.Thread(target=_download, args=(gid,), daemon=True).start()
        elif action == "play":
            if gid.startswith("steam-"):
                os.startfile(f"steam://rungameid/{gid[6:]}")
            elif gid.startswith("epic-"):
                g = next(x for x in epic_games() if x["id"] == gid)
                if j.get("direct") and os.path.exists(g["exe"]):
                    subprocess.Popen([g["exe"]], cwd=os.path.dirname(g["exe"]), creationflags=0x00000008)
                else:
                    os.startfile(g["uri"])
            else:
                e = _state().get(gid) or {}
                st2 = _state()
                if gid in st2:
                    st2[gid]["last"] = int(time.time())
                    _save_state(st2)
                if e.get("exe", "").endswith(".lnk") and os.path.exists(e["exe"]):
                    os.startfile(e["exe"])  # installed with its own installer → its Start Menu shortcut
                elif e.get("exe") and os.path.exists(e["exe"]):
                    cmd = [_java(), "-jar", e["exe"]] if e["exe"].endswith(".jar") else [e["exe"]]
                    subprocess.Popen(cmd, cwd=os.path.dirname(e["exe"]), creationflags=0x00000008)
                elif e.get("installer") and os.path.exists(e["installer"]):
                    os.startfile(e["installer"])  # opens the game's own installer
                else:
                    return jsonify(error="Not downloaded yet"), 400
        elif action == "setexe":
            st = _state()
            if gid in st and os.path.isfile(j.get("exe", "")):
                st[gid]["exe"] = j["exe"]
                _save_state(st)
        elif action == "folder":
            path = (_state().get(gid) or {}).get("dir") or next((x["dir"] for x in steam_games() + epic_games() if x["id"] == gid), "")
            if path and os.path.isdir(path):
                os.startfile(path)
        elif action == "remove" and gid in CAT:
            st = _state()
            st.pop(gid, None)
            _save_state(st)
            d = games_dir() / gid
            if d.exists() and str(d).startswith(str(games_dir())):
                shutil.rmtree(d, ignore_errors=True)
        else:
            return jsonify(error="unknown action"), 400
    except Exception as e:
        return jsonify(error=str(e)[:200]), 400
    return jsonify(ok=True)


ART = CACHE / "art"
TOOLS = {"lossless scaling", "wallpaper engine", "steamvr", "soundpad", "blender", "rpg maker", "aseprite", "fpsvr", "ovr toolkit"}
CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/{file}"


def kind_of(name):
    n = name.lower()
    if any(t in n for t in TOOLS):
        return "tool"
    if re.search(r"\bdemo\b|\bplaytest\b|\bprologue\b", n):
        return "demo"
    return "game"


def _norm(t):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"[™®©]|\(.*?\)", "", t.lower()))


def _art_map():
    try:
        return json.loads((ART / "map.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def steam_appid_for(name):
    """Find the same game on the Steam store (most Epic and open-source games are there) — for cover art."""
    m = _art_map()
    key = _norm(name)
    if key in m:
        return m[key]
    appid = None
    try:
        q = urllib.parse.quote(re.sub(r"[™®©]|\(.*?\)", "", name).strip())
        with urllib.request.urlopen(urllib.request.Request(f"https://store.steampowered.com/api/storesearch/?term={q}&l=english&cc=US",
                                                           headers={"User-Agent": UA["User-Agent"]}), timeout=10) as r:
            items = json.loads(r.read()).get("items", [])
        exact = [it for it in items if _norm(it["name"]) == key]
        close = [it for it in items if key and (key in _norm(it["name"]) or _norm(it["name"]) in key)
                 and min(len(key), len(_norm(it["name"]))) / max(len(key), len(_norm(it["name"]))) >= 0.85]
        pick = (exact or close or [None])[0]
        appid = str(pick["id"]) if pick else None
    except Exception:
        return None  # offline: try again later
    m[key] = appid
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "map.json").write_text(json.dumps(m, indent=0), encoding="utf-8")
    return appid


def _cdn(appid, wide):
    """Download (once) the official store artwork for a Steam app id."""
    out = ART / f"{appid}-{'wide' if wide else 'tall'}.jpg"
    if out.exists():
        return out if out.stat().st_size > 1000 else None
    ART.mkdir(parents=True, exist_ok=True)
    for f in (["header.jpg"] if wide else ["library_600x900_2x.jpg", "library_600x900.jpg"]):
        try:
            with urllib.request.urlopen(urllib.request.Request(CDN.format(appid=appid, file=f), headers={"User-Agent": UA["User-Agent"]}), timeout=12) as r:
                out.write_bytes(r.read())
                return out
        except Exception:
            continue
    out.write_bytes(b"")  # remember there's none
    return None


def art_for(gid, name, wide=False):
    if gid.startswith("steam-"):
        appid = gid[6:]
        if not wide:
            p = steam_art(appid)
            if p and "header" not in p.name:
                return p
        else:
            root = steam_root()
            for lp in ((root / "appcache" / "librarycache" / f"{appid}_header.jpg"), (root / "appcache" / "librarycache" / appid / "header.jpg")) if root else ():
                if lp.exists():
                    return lp
        return _cdn(appid, wide)
    appid = steam_appid_for(name)
    return _cdn(appid, wide) if appid else None


@bp.get("/game-art/<gid>")
def g_art(gid):
    wide = request.args.get("wide") == "1"
    name = request.args.get("name", "")
    if not name:
        name = next((x["name"] for x in steam_games() + epic_games() if x["id"] == gid), CAT.get(gid, {}).get("name", ""))
    p = art_for(gid, name, wide)
    if p:
        return send_file(p, max_age=86400 * 7)
    if gid.startswith("epic-") and not wide:  # last resort: the game's own icon
        g = next((x for x in epic_games() if x["id"] == gid), None)
        out = CACHE / f"{gid}.png"
        if g and os.path.exists(g["exe"]) and not out.exists():
            try:
                from icoextract import IconExtractor
                from PIL import Image
                ico = CACHE / f"{gid}.ico"
                IconExtractor(g["exe"]).export_icon(str(ico))
                im = Image.open(ico)
                im.ico.getimage(max(im.ico.sizes())).convert("RGBA").save(out)
                ico.unlink(missing_ok=True)
            except Exception:
                pass
        if out.exists():
            return send_file(out, max_age=86400)
    return ("", 404)
