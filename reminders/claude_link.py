"""Detect Claude (Claude Code CLI + Claude desktop app), Node.js, Gemini, and connect Daybook's MCP server."""
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import paths

GET_CLAUDE_URL = "https://claude.ai/download"
ROOT = Path(__file__).resolve().parent.parent
SERVER_CMD, *SERVER_ARGS = paths.helper_cmd("mcp", console=True)
NAME = "reminders"  # MCP server name Claude sees
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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
        shutil.which("gemini"),
        Path.home() / ".local" / "bin" / "gemini.cmd",
        Path(os.environ.get("APPDATA", "")) / "npm" / "gemini.cmd",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs" / "gemini.cmd",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Daybook-tools" / "gemini-cli" / "gemini.cmd",
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
        "recommended_model": "qwen2.5:1.5b" if laptop_mode else "qwen2.5:7b"
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

    code_connected = False
    try:
        cfg = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
        code_connected = NAME in (cfg.get("mcpServers") or {})
    except Exception:
        pass

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

    hw = hardware_info()

    return {
        "get_url": GET_CLAUDE_URL,
        "code": {"installed": bool(exe), "version": version, "connected": code_connected, "path": exe},
        "desktop": {"installed": _desktop_installed(), "connected": desk_connected},
        "node": {"installed": bool(node_e), "version": node_ver},
        "gemini": {"installed": bool(gem_e), "version": gem_ver},
        "hardware": hw
    }


def connect_code():
    exe = _claude_exe()
    if not exe:
        raise RuntimeError("Claude Code isn't installed. Run 1-Click Install first.")
    r = subprocess.run([exe, "mcp", "add", "--scope", "user", NAME, "--", SERVER_CMD, *SERVER_ARGS],
                       capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
    if r.returncode != 0 and "already exists" not in (r.stdout + r.stderr):
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return "Connected to Claude Code — start a new Claude session to use it."


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


def stack_status():
    import urllib.request as _urllib
    s = status()
    node_stat = s["node"]
    claude_stat = s["code"]
    gemini_stat = s["gemini"]

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

    installer = find_stack_installer()
    return {
        "node": node_stat,
        "claude": claude_stat,
        "gemini": gemini_stat,
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
