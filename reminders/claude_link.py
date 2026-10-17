"""Detect Claude (Claude Code CLI + Claude desktop app), Node.js, Gemini, and connect Daybook's MCP server."""
import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from . import paths

GET_CLAUDE_URL = "https://claude.ai/download"
ROOT = Path(__file__).resolve().parent.parent
SERVER_CMD, *SERVER_ARGS = paths.helper_cmd("mcp", console=True)
NAME = "reminders"  # MCP server name Claude sees
GEMINI_MCP_NAME = "daybook"  # MCP server name Gemini CLI sees
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_MCP_HANDSHAKE_CACHE = {"ts": 0.0, "result": None}
MCP_CACHE_TTL_S = 600.0  # 10 minutes


def _claude_exe():
    """Locate claude executable across native Anthropic install, local bins, and npm."""
    candidates = [
        shutil.which("claude"),
        Path.home() / ".local" / "bin" / "claude.exe",
        Path.home() / ".claude" / "bin" / "claude.exe",
        Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs" / "claude.cmd",
        Path(os.environ.get("ProgramFiles", "")) / "nodejs" / "claude.cmd",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None


def _node_exe():
    """Locate node.exe across standard PATH and Daybook's portable directories."""
    candidates = [
        Path(r"D:\Applications\nodejs\node.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Daybook-tools" / "nodejs" / "node.exe",
        shutil.which("node"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs" / "node.exe",
        Path(os.environ.get("ProgramFiles", "")) / "nodejs" / "node.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None


def _gemini_exe():
    """Locate gemini CLI executable."""
    candidates = [
        Path(r"D:\Applications\gemini-cli\gemini.cmd"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Daybook-tools" / "gemini-cli" / "gemini.cmd",
        shutil.which("gemini"),
        Path.home() / ".local" / "bin" / "gemini.cmd",
        Path(os.environ.get("APPDATA", "")) / "npm" / "gemini.cmd",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs" / "gemini.cmd",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None


def _agy_exe():
    """Locate Antigravity (agy) CLI executable (PATH first, then fixed folders)."""
    candidates = [
        shutil.which("agy"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "agy.exe",
        Path.home() / ".gemini" / "antigravity-ide" / "bin" / "agy.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "bin" / "agy.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None


HIGGSFIELD_MCP_NAME = "higgsfield"
HIGGSFIELD_MCP_URL = "https://mcp.higgsfield.ai/mcp"


def _higgsfield_exe():
    """Locate higgsfield CLI executable across PATH, npm global dirs, and Daybook-tools."""
    candidates = [
        shutil.which("higgsfield"),
        Path(os.environ.get("APPDATA", "")) / "npm" / "higgsfield.cmd",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Daybook-tools" / "nodejs" / "higgsfield.cmd",
        Path(r"D:\Applications\nodejs\higgsfield.cmd"),
        Path.home() / ".local" / "bin" / "higgsfield.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs" / "higgsfield.cmd",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None


def _desktop_config():
    return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"


def _desktop_installed():
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    return (local / "AnthropicClaude").exists() or _desktop_config().parent.exists()


def _entry_args_ok(entry: dict) -> bool:
    """True when an MCP server entry passes 'mcp' (for daybook-mcp.exe) or 'mcp_server.py' (for dev python)."""
    if not isinstance(entry, dict):
        return False
    args = entry.get("args") or []
    if isinstance(args, str):
        args = [args]
    return "mcp" in args or any("mcp_server.py" in str(a) for a in args)


def _claude_mcp_info():
    """Inspect ~/.claude.json for the 'reminders' MCP server entry."""
    registered = False
    args_ok = False
    try:
        cfg_file = Path.home() / ".claude.json"
        if cfg_file.exists():
            cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
            servers = cfg.get("mcpServers") or {}
            entry = servers.get(NAME)
            if isinstance(entry, dict):
                registered = True
                args_ok = _entry_args_ok(entry)
    except Exception:
        pass
    return {"registered": registered, "args_ok": args_ok, "connected": bool(registered and args_ok)}


def _home_key() -> str:
    return str(Path.home()).replace("\\", "/").lower()


def gemini_trust_status() -> bool:
    """Return True if the user's home folder is trusted in ~/.gemini/trustedFolders.json."""
    try:
        tf = Path.home() / ".gemini" / "trustedFolders.json"
        if not tf.exists():
            return False
        data = json.loads(tf.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            return False
        hk = _home_key()
        for k, v in data.items():
            if str(k).replace("\\", "/").lower().rstrip("/") == hk.rstrip("/") and v in ("TRUST_FOLDER", "TRUST_PARENT"):
                return True
    except Exception:
        pass
    return False


def set_gemini_trust(trust: bool) -> bool:
    """Merge or remove home-folder trust in ~/.gemini/trustedFolders.json without clobbering other entries."""
    gem_dir = Path.home() / ".gemini"
    gem_dir.mkdir(parents=True, exist_ok=True)
    tf = gem_dir / "trustedFolders.json"
    data = {}
    if tf.exists():
        raw = tf.read_text(encoding="utf-8-sig")
        if raw.strip():
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise RuntimeError("trustedFolders.json is not a JSON object")
        (gem_dir / "trustedFolders.json.daybook-backup").write_text(raw, encoding="utf-8")
    hk = _home_key()
    if trust:
        data[hk] = "TRUST_FOLDER"
    else:
        for k in list(data.keys()):
            if str(k).replace("\\", "/").lower().rstrip("/") == hk.rstrip("/"):
                data.pop(k, None)
    tf.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return gemini_trust_status()


def _gemini_mcp_info():
    """Inspect ~/.gemini/settings.json for the 'daybook' MCP server entry and sign-in status."""
    registered = False
    args_ok = False
    signed_in = bool(os.environ.get("GEMINI_API_KEY"))
    try:
        cfg_file = Path.home() / ".gemini" / "settings.json"
        if cfg_file.exists():
            cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
            servers = cfg.get("mcpServers") or {}
            entry = servers.get(GEMINI_MCP_NAME)
            if isinstance(entry, dict):
                registered = True
                args_ok = _entry_args_ok(entry)
            sel = ((cfg.get("security") or {}).get("auth") or {}).get("selectedType")
            if sel:
                signed_in = True
    except Exception:
        pass
    return {
        "registered": registered,
        "args_ok": args_ok,
        "connected": bool(registered and args_ok),
        "signed_in": signed_in,
        "trusted_home": gemini_trust_status(),
    }


def _agy_mcp_files():
    return [
        Path.home() / ".gemini" / "config" / "mcp_config.json",
        Path.home() / ".gemini" / "antigravity" / "mcp_config.json",
    ]


def _agy_mcp_info():
    """Inspect ~/.gemini/config/mcp_config.json and ~/.gemini/antigravity/mcp_config.json for 'daybook'."""
    registered = False
    args_ok = False
    for cfg_file in _agy_mcp_files():
        try:
            if cfg_file.exists():
                cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
                servers = cfg.get("mcpServers") or {}
                entry = servers.get(GEMINI_MCP_NAME)
                if isinstance(entry, dict):
                    registered = True
                    if _entry_args_ok(entry):
                        args_ok = True
        except Exception:
            pass
    return {
        "registered": registered,
        "args_ok": args_ok,
        "connected": bool(registered and args_ok),
    }


def _ensure_higgsfield_workspace(exe=None, select: bool = False) -> dict:
    """Return the selected Higgsfield workspace; with select=True, pick the first one if none is selected."""
    if exe is None:
        exe = _higgsfield_exe()
    info = {"workspace_id": None, "plan": None, "credits": None}
    if not exe:
        return info
    try:
        r = subprocess.run([exe, "workspace", "list", "--json"], capture_output=True, text=True, timeout=6, creationflags=NO_WINDOW)
        if r.returncode == 0 and r.stdout.strip().startswith("["):
            ws_list = json.loads(r.stdout.strip())
            if isinstance(ws_list, list) and ws_list:
                selected = next((w for w in ws_list if isinstance(w, dict) and w.get("is_selected")), None)
                if not selected and select:
                    first = ws_list[0] if isinstance(ws_list[0], dict) else None
                    if first and first.get("id"):
                        subprocess.run([exe, "workspace", "set", str(first["id"])], capture_output=True, text=True, timeout=6, creationflags=NO_WINDOW)
                        selected = first
                if selected:
                    info["workspace_id"] = selected.get("id")
                    info["plan"] = selected.get("plan_type")
                    info["credits"] = selected.get("credits")
    except Exception:
        pass
    return info


def _higgsfield_info(exe=None, select_workspace: bool = False):
    """Inspect Higgsfield CLI installation, OAuth token status, workspace, companion skills, and MCP registration."""
    if exe is None:
        exe = _higgsfield_exe()
    version = None
    signed_in = False
    ws_info = {"workspace_id": None, "plan": None, "credits": None}
    if exe:
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW).stdout.strip()
            if out:
                # e.g. "higgsfield 1.2.2 (...) built ..."
                parts = out.splitlines()[0].split()
                version = parts[1] if len(parts) > 1 else parts[0]
        except Exception:
            pass
        try:
            r = subprocess.run([exe, "auth", "token"], capture_output=True, text=True, timeout=4, creationflags=NO_WINDOW)
            signed_in = r.returncode == 0 and bool(r.stdout.strip())
        except Exception:
            pass
        if signed_in:
            ws_info = _ensure_higgsfield_workspace(exe, select=select_workspace)

    claude_sk = Path.home() / ".claude" / "skills"
    gem_sk = Path.home() / ".gemini" / "config" / "skills"
    skill_names = set()
    for base in (claude_sk, gem_sk):
        try:
            if base.exists():
                for d in base.glob("higgsfield-*"):
                    if (d / "SKILL.md").exists():
                        skill_names.add(d.name)
        except Exception:
            pass
    skills_count = len(skill_names)
    skills_installed = skills_count > 0

    mcp_registered = False
    for cfg_file in [Path.home() / ".gemini" / "settings.json", *_agy_mcp_files(), Path.home() / ".claude.json"]:
        try:
            if cfg_file.exists():
                cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
                if isinstance((cfg.get("mcpServers") or {}).get(HIGGSFIELD_MCP_NAME), dict):
                    mcp_registered = True
                    break
        except Exception:
            pass

    return {
        "installed": bool(exe),
        "version": version,
        "signed_in": signed_in,
        "workspace_id": ws_info["workspace_id"],
        "plan": ws_info["plan"],
        "credits": ws_info["credits"],
        "skills_installed": skills_installed,
        "skills_count": skills_count,
        "registered": mcp_registered,
        "args_ok": True,
        "connected": mcp_registered,
        "path": exe,
    }


def test_mcp_handshake(force: bool = False, timeout: float = 90.0) -> dict:
    """Start daybook-mcp.exe mcp (or dev mcp_server.py), send initialize, and wait up to `timeout` s. Cached 10 min."""
    now = time.monotonic()
    if not force and _MCP_HANDSHAKE_CACHE["result"] is not None and (now - _MCP_HANDSHAKE_CACHE["ts"]) < MCP_CACHE_TTL_S:
        return dict(_MCP_HANDSHAKE_CACHE["result"])

    cmd = [SERVER_CMD, *SERVER_ARGS]
    if Path(SERVER_CMD).stem.lower() == "daybook-mcp" and "mcp" not in SERVER_ARGS:
        cmd.append("mcp")

    t0 = time.perf_counter()
    handshake_ok = False
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=NO_WINDOW,
        )
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "daybook-check", "version": "1.8.1"},
            },
        }) + "\n"
        proc.stdin.write(req)
        proc.stdin.flush()

        # Read first non-empty stdout line with a timeout thread
        import threading
        line_box = []

        def _reader():
            try:
                for ln in proc.stdout:
                    if ln and ln.strip():
                        line_box.append(ln.strip())
                        break
            except Exception:
                pass

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        t.join(timeout=timeout)
        if line_box:
            msg = json.loads(line_box[0])
            handshake_ok = msg.get("jsonrpc") == "2.0" and ("result" in msg)
    except Exception:
        handshake_ok = False
    finally:
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=2)
            except Exception:
                pass

    startup_ms = int(round((time.perf_counter() - t0) * 1000))
    res = {"handshake_ok": handshake_ok, "startup_ms": startup_ms}
    _MCP_HANDSHAKE_CACHE["ts"] = time.monotonic()
    _MCP_HANDSHAKE_CACHE["result"] = res
    return dict(res)


def hardware_info():
    """Detect hardware capacity (RAM, GPU) to advise on laptop vs desktop AI mode."""
    total_ram_gb = 8
    has_gpu = False
    try:
        import ctypes
        c_ulonglong = ctypes.c_ulonglong
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong),
                ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', c_ulonglong),
                ('ullAvailPhys', c_ulonglong),
                ('ullTotalPageFile', c_ulonglong),
                ('ullAvailPageFile', c_ulonglong),
                ('ullTotalVirtual', c_ulonglong),
                ('ullAvailVirtual', c_ulonglong),
                ('ullAvailExtendedVirtual', c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_ram_gb = round(stat.ullTotalPhys / (1024 ** 3))
    except Exception:
        pass

    try:
        out = subprocess.check_output(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            text=True, creationflags=NO_WINDOW, timeout=3
        )
        for line in out.splitlines():
            line_u = line.upper()
            if any(k in line_u for k in ["NVIDIA", "GEFORCE", "RTX", "GTX", "RADEON RX", "ARC A"]):
                has_gpu = True
                break
    except Exception:
        pass

    laptop_mode = not has_gpu or total_ram_gb < 16
    return {
        "ram_gb": total_ram_gb,
        "has_gpu": has_gpu,
        "laptop_mode": laptop_mode,
        "recommended_cloud": laptop_mode,
        "recommended_model": "qwen3.5:2b" if laptop_mode else "qwen3.5:9b"
    }


def status():
    exe = _claude_exe()
    version = None
    if exe:
        try:
            version = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=15,
                                     creationflags=NO_WINDOW).stdout.strip().split(" ")[0] or None
        except Exception:
            pass

    claude_mcp = _claude_mcp_info()

    desk_connected = False
    try:
        desk_connected = NAME in (json.loads(_desktop_config().read_text(encoding="utf-8")).get("mcpServers") or {})
    except Exception:
        pass

    node_e = _node_exe()
    node_ver = None
    if node_e:
        try:
            node_ver = subprocess.run([node_e, "-v"], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW).stdout.strip()
        except Exception:
            pass

    gem_e = _gemini_exe()
    gem_ver = None
    if gem_e:
        try:
            gem_ver = subprocess.run([gem_e, "--version"], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW).stdout.strip()
        except Exception:
            pass
    gem_mcp = _gemini_mcp_info()

    agy_e = _agy_exe()
    agy_ver = None
    if agy_e:
        try:
            out = subprocess.run([agy_e, "--version"], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW).stdout.strip()
            agy_ver = out.splitlines()[0].strip() if out else None
        except Exception:
            pass
    agy_mcp = _agy_mcp_info()

    hf_info = _higgsfield_info()

    hw = hardware_info()

    return {
        "get_url": GET_CLAUDE_URL,
        "code": {
            "installed": bool(exe),
            "version": version,
            "registered": claude_mcp["registered"],
            "args_ok": claude_mcp["args_ok"],
            "connected": claude_mcp["connected"],
            "path": exe,
        },
        "desktop": {"installed": _desktop_installed(), "connected": desk_connected},
        "node": {"installed": bool(node_e), "version": node_ver},
        "gemini": {
            "installed": bool(gem_e),
            "version": gem_ver,
            "registered": gem_mcp["registered"],
            "args_ok": gem_mcp["args_ok"],
            "connected": gem_mcp["connected"],
            "signed_in": gem_mcp["signed_in"],
            "trusted_home": gem_mcp["trusted_home"],
        },
        "agy": {
            "installed": bool(agy_e),
            "version": agy_ver,
            "registered": agy_mcp["registered"],
            "args_ok": agy_mcp["args_ok"],
            "connected": agy_mcp["connected"],
            "path": agy_e,
        },
        "higgsfield": hf_info,
        "hardware": hw
    }


def connect_code():
    exe = _claude_exe()
    if not exe:
        raise RuntimeError("Claude Code isn't installed. Run 1-Click Install first.")
    args = list(SERVER_ARGS)
    if Path(SERVER_CMD).stem.lower() == "daybook-mcp" and "mcp" not in args:
        args.append("mcp")
    subprocess.run([exe, "mcp", "remove", "--scope", "user", NAME],
                   capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
    r = subprocess.run([exe, "mcp", "add", "--scope", "user", NAME, "--", SERVER_CMD, *args],
                       capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
    if r.returncode != 0 and "already exists" not in (r.stdout + r.stderr):
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    os.environ["MCP_TIMEOUT"] = "90000"
    if os.name == "nt":
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", '[Environment]::SetEnvironmentVariable("MCP_TIMEOUT", "90000", "User")'],
                capture_output=True, timeout=10, creationflags=NO_WINDOW,
            )
        except Exception:
            pass
    return "Connected to Claude Code — start a new Claude session to use it."


def connect_gemini(trust_home: bool = True):
    """Merge the 'daybook' MCP server entry into ~/.gemini/settings.json (UTF-8 without BOM)."""
    gem_dir = Path.home() / ".gemini"
    gem_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = gem_dir / "settings.json"
    cfg = {}
    if cfg_file.exists():
        raw = cfg_file.read_text(encoding="utf-8-sig")
        if raw.strip():
            try:
                cfg = json.loads(raw)
            except Exception as e:
                raise RuntimeError("settings.json isn't plain JSON, so Daybook left it alone. Add the 'daybook' entry by hand.") from e
        (gem_dir / "settings.json.daybook-backup").write_text(raw, encoding="utf-8")
    args = list(SERVER_ARGS)
    if Path(SERVER_CMD).stem.lower() == "daybook-mcp" and "mcp" not in args:
        args.append("mcp")
    cfg.setdefault("mcpServers", {})[GEMINI_MCP_NAME] = {
        "command": SERVER_CMD,
        "args": args,
        "timeout": 90000,
    }
    cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    if trust_home:
        set_gemini_trust(True)
    return "Connected to Gemini CLI — start a new Gemini session to use it."


def connect_agy():
    """Register Daybook's MCP server with Antigravity (agy mcp add + merge into mcp_config.json files)."""
    args = list(SERVER_ARGS)
    if Path(SERVER_CMD).stem.lower() == "daybook-mcp" and "mcp" not in args:
        args.append("mcp")
    agy_e = _agy_exe()
    if agy_e:
        try:
            subprocess.run([agy_e, "mcp", "add", GEMINI_MCP_NAME, SERVER_CMD, *args],
                           capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        except Exception:
            pass
    for cfg_file in _agy_mcp_files():
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg = {}
        if cfg_file.exists():
            raw = cfg_file.read_text(encoding="utf-8-sig")
            if raw.strip():
                try:
                    cfg = json.loads(raw)
                except Exception as e:
                    raise RuntimeError(f"{cfg_file.name} isn't plain JSON, so Daybook left it alone.") from e
                if not isinstance(cfg, dict):
                    raise RuntimeError(f"{cfg_file.name} is not a JSON object.")
            (cfg_file.parent / f"{cfg_file.name}.daybook-backup").write_text(raw, encoding="utf-8")
        if not isinstance(cfg.get("mcpServers"), dict):
            cfg["mcpServers"] = {}
        cfg["mcpServers"][GEMINI_MCP_NAME] = {
            "command": SERVER_CMD,
            "args": args,
        }
        cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return "Connected to Antigravity (AGY) — start a new Antigravity session to use it."


def login_higgsfield():
    """Launch `higgsfield auth login` in the background and explicitly open the sign-in.html page in the default browser."""
    import re
    import threading
    import urllib.parse
    exe = _higgsfield_exe()
    if not exe:
        raise RuntimeError("Higgsfield CLI isn't installed yet. Click 1-Click Setup first.")
    proc = subprocess.Popen(
        [exe, "auth", "login"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=NO_WINDOW,
    )
    url_box = []

    def _drain():
        try:
            for line in proc.stdout:
                m = re.search(r"(file:///[^\s]+)", line)
                if m and not url_box:
                    u = m.group(1).strip()
                    url_box.append(u)
                    if os.name == "nt":
                        try:
                            local_p = urllib.parse.unquote(u.replace("file:///", "")).replace("/", "\\")
                            if Path(local_p).exists():
                                os.startfile(local_p)
                        except Exception:
                            pass
        except Exception:
            pass

    t = threading.Thread(target=_drain, daemon=True)
    t.start()
    for _ in range(25):
        if url_box:
            break
        time.sleep(0.1)
    return "Browser opened for Higgsfield sign-in — complete the login in your browser."


def connect_higgsfield(login: bool = False):
    """Install @higgsfield/cli + companion skills if missing, register Higgsfield MCP, and optionally start browser login."""
    node_e = _node_exe()
    npm_cmd = shutil.which("npm")
    if not npm_cmd and node_e:
        cand = Path(node_e).parent / "npm.cmd"
        if cand.exists():
            npm_cmd = str(cand)
    npx_cmd = shutil.which("npx")
    if not npx_cmd and node_e:
        cand = Path(node_e).parent / "npx.cmd"
        if cand.exists():
            npx_cmd = str(cand)

    exe = _higgsfield_exe()
    if not exe:
        if not npm_cmd:
            raise RuntimeError("Node.js / npm not found. Run 1-Click Install first.")
        r = subprocess.run([npm_cmd, "i", "-g", "@higgsfield/cli"], capture_output=True, text=True, timeout=180, creationflags=NO_WINDOW)
        exe = _higgsfield_exe()
        if not exe and r.returncode != 0:
            raise RuntimeError(f"Failed to install @higgsfield/cli: {(r.stderr or r.stdout).strip()[:240]}")

    # Install companion skills if not yet present
    claude_skills = Path.home() / ".claude" / "skills"
    gem_skills = Path.home() / ".gemini" / "config" / "skills"
    if not (claude_skills / "higgsfield-generate" / "SKILL.md").exists() and npx_cmd:
        try:
            subprocess.run(
                [npx_cmd, "-y", "skills", "add", "higgsfield-ai/skills", "-g", "--all", "--copy"],
                capture_output=True, text=True, timeout=180, creationflags=NO_WINDOW,
            )
        except Exception:
            pass
    # Ensure Antigravity / Gemini skills directory also has the Higgsfield skills
    if claude_skills.exists():
        gem_skills.mkdir(parents=True, exist_ok=True)
        for sk in claude_skills.glob("higgsfield-*"):
            if sk.is_dir():
                dst = gem_skills / sk.name
                try:
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(sk, dst)
                except Exception:
                    pass

    # Merge Higgsfield MCP server into Gemini & Antigravity config files (UTF-8 without BOM)
    for cfg_file in [Path.home() / ".gemini" / "settings.json", *_agy_mcp_files()]:
        try:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            cfg = {}
            if cfg_file.exists():
                raw = cfg_file.read_text(encoding="utf-8-sig")
                if raw.strip():
                    cfg = json.loads(raw)
                (cfg_file.parent / f"{cfg_file.name}.daybook-backup").write_text(raw, encoding="utf-8")
            if isinstance(cfg, dict):
                if not isinstance(cfg.get("mcpServers"), dict):
                    cfg["mcpServers"] = {}
                cfg["mcpServers"][HIGGSFIELD_MCP_NAME] = {"httpUrl": HIGGSFIELD_MCP_URL}
                cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except Exception:
            pass

    info = _higgsfield_info(exe, select_workspace=True)
    if login or not info["signed_in"]:
        try:
            login_higgsfield()
            return "Higgsfield CLI, MCP & 8 Skills installed! Complete sign-in in the browser window that just opened."
        except Exception:
            pass
    return "Higgsfield CLI, MCP & 8 Companion Skills connected and ready!"


def connect_desktop():
    path = _desktop_config()
    if not _desktop_installed():
        raise RuntimeError("The Claude desktop app isn't installed")
    cfg = {}
    if path.exists():
        raw = path.read_text(encoding="utf-8")
        cfg = json.loads(raw) if raw.strip() else {}
        backup = path.with_name(f"claude_desktop_config.backup-{datetime.now():%Y%m%d-%H%M%S}.json")
        backup.write_text(raw, encoding="utf-8")
    cfg.setdefault("mcpServers", {})[NAME] = {"command": SERVER_CMD, "args": SERVER_ARGS}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return "Connected to the Claude app — fully quit Claude (tray icon → Quit) and reopen it."


def disconnect(target):
    if target == "code":
        exe = _claude_exe()
        if exe:
            subprocess.run([exe, "mcp", "remove", NAME, "--scope", "user"], capture_output=True, timeout=60,
                           creationflags=NO_WINDOW)
        return "Disconnected from Claude Code."
    if target == "gemini":
        cfg_file = Path.home() / ".gemini" / "settings.json"
        if cfg_file.exists():
            cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig") or "{}")
            if (cfg.get("mcpServers") or {}).pop(GEMINI_MCP_NAME, None) is not None:
                cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return "Disconnected from Gemini CLI."
    if target == "agy":
        for cfg_file in _agy_mcp_files():
            if cfg_file.exists():
                cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig") or "{}")
                if (cfg.get("mcpServers") or {}).pop(GEMINI_MCP_NAME, None) is not None:
                    cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return "Disconnected from Antigravity (AGY)."
    if target == "higgsfield":
        for cfg_file in [Path.home() / ".gemini" / "settings.json", *_agy_mcp_files()]:
            if cfg_file.exists():
                try:
                    cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig") or "{}")
                    if (cfg.get("mcpServers") or {}).pop(HIGGSFIELD_MCP_NAME, None) is not None:
                        cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
                except Exception:
                    pass
        return "Disconnected Higgsfield MCP."
    path = _desktop_config()
    if path.exists():
        cfg = json.loads(path.read_text(encoding="utf-8") or "{}")
        if (cfg.get("mcpServers") or {}).pop(NAME, None) is not None:
            path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return "Disconnected from the Claude app."


def find_stack_installer():
    candidates = [
        paths.APP / "install-ai-stack.bat",
        paths.APP / "_internal" / "install-ai-stack.bat",
        paths.APP.parent / "install-ai-stack.bat",
        paths.APP / "resources" / "backend" / "install-ai-stack.bat",
        paths.APP / "resources" / "backend" / "_internal" / "install-ai-stack.bat",
        ROOT / "install-ai-stack.bat",
        Path(__file__).resolve().parent.parent / "install-ai-stack.bat",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def stack_status(check_handshake: bool = True):
    import urllib.request as _urllib
    s = status()
    node_stat = s["node"]
    claude_stat = s["code"]
    gemini_stat = s["gemini"]
    agy_stat = s["agy"]
    hf_stat = s["higgsfield"]

    ollama_exe = shutil.which("ollama")
    if not ollama_exe:
        cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if cand.exists():
            ollama_exe = str(cand)
    ollama_ver = None
    if ollama_exe:
        try:
            ollama_ver = subprocess.run([ollama_exe, "--version"], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW).stdout.strip().replace("ollama version is ", "")
        except Exception:
            pass

    ollama_running = False
    models = []
    try:
        req = _urllib.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "Daybook/1.7"})
        with _urllib.urlopen(req, timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8"))
            models = [m.get("name") for m in data.get("models", [])]
            ollama_running = True
    except Exception:
        pass

    # 30 s, not 90: this runs while Settings waits for the status card (the connector now answers in ~1 s)
    mcp_stat = test_mcp_handshake(timeout=30.0) if check_handshake else {"handshake_ok": False, "startup_ms": 0}
    installer = find_stack_installer()
    return {
        "node": node_stat,
        "claude": claude_stat,
        "gemini": gemini_stat,
        "agy": agy_stat,
        "higgsfield": hf_stat,
        "mcp": mcp_stat,
        "ollama": {"installed": bool(ollama_exe), "version": ollama_ver, "running": ollama_running, "models": models},
        "hardware": s["hardware"],
        "ready": bool(node_stat["installed"] and claude_stat["installed"] and (ollama_running or gemini_stat["installed"])),
        "installer_exists": installer is not None
    }


def launch_stack_installer():
    installer = find_stack_installer()
    if not installer:
        raise RuntimeError("install-ai-stack.bat not found in app directory")
    if os.name == "nt":
        os.startfile(str(installer))
    else:
        subprocess.Popen(["cmd.exe", "/c", str(installer)])
    return "1-Click AI Stack Installer launched in a new window."
