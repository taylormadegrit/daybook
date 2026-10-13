"""Where Daybook keeps things — the same code runs from source (this PC) or as the installed app on any PC.
- APP: Daybook's own read-only files (web UI, scripts). Inside the installed app that's the unpacked bundle.
- DATA: the database, caches, recordings… From source: ./data. Installed: %LOCALAPPDATA%\\Daybook (or DAYBOOK_DATA).
- USER_DIR: visible folder for things you make (annotations, AI creations): D:\\Daybook if it exists, else Documents\\Daybook."""
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
APP = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parent.parent
if os.environ.get("DAYBOOK_DATA"):
    DATA = Path(os.environ["DAYBOOK_DATA"])
elif FROZEN:
    DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Daybook"
else:
    DATA = APP / "data"
DATA.mkdir(parents=True, exist_ok=True)
WEB = APP / "web"
HOME = Path.home()
DOCS = HOME / "Documents"
USER_DIR = Path(r"D:\Daybook") if Path(r"D:\Daybook").exists() else DOCS / "Daybook"
GAMES_DIR = Path(r"D:\Games\Daybook") if Path(r"D:\Games").exists() else HOME / "Games" / "Daybook"
IMPORT_DIR = r"F:\28HRTZ" if Path(r"F:\28HRTZ").exists() else ""


def helper_cmd(*args, console=False):
    """Command that runs one of Daybook's helper modes (annotate, sticky, note, mcp…)."""
    if FROZEN:
        if args and args[0] == "mcp":  # Claude talks to the MCP server over stdin/stdout → the console build
            return [str(Path(sys.executable).with_name("daybook-mcp.exe")), *args]
        return [sys.executable, *args]
    py = APP / "venv" / "Scripts" / ("python.exe" if console else "pythonw.exe")
    if args and args[0] == "mcp":
        return [str(py), str(APP / "mcp_server.py"), *args[1:]]
    return [str(py), str(APP / "quickadd.pyw"), *args]
