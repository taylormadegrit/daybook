"""Detect Claude (Claude Code CLI + Claude desktop app) and connect Daybook's MCP server to it."""
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import paths

GET_CLAUDE_URL = "https://taylormade420.gumroad.com/l/cfrswx"  # Claude Easy download (Gumroad)
ROOT = Path(__file__).resolve().parent.parent
SERVER_CMD, *SERVER_ARGS = paths.helper_cmd("mcp", console=True)
NAME = "reminders"  # MCP server name Claude sees
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _claude_exe():
    for c in (shutil.which("claude"), Path.home() / ".local" / "bin" / "claude.exe"):
        if c and Path(c).exists():
            return str(c)
    return None


def _desktop_config():
    return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"


def _desktop_installed():
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    return (local / "AnthropicClaude").exists() or _desktop_config().parent.exists()


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
    return {"get_url": GET_CLAUDE_URL,
            "code": {"installed": bool(exe), "version": version, "connected": code_connected},
            "desktop": {"installed": _desktop_installed(), "connected": desk_connected}}


def connect_code():
    exe = _claude_exe()
    if not exe:
        raise RuntimeError("Claude Code isn't installed")
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
        backup.write_text(raw, encoding="utf-8")  # never lose the user's existing config
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
