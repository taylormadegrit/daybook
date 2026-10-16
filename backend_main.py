"""Entry point for the packaged Daybook backend (daybook-backend.exe).
  daybook-backend.exe                → the background service (web UI on :8503, pop-ups, stickies, timers…)
  daybook-backend.exe annotate|sticky|peek|note|agenda|add|dashboard|chat → the helper windows / hotkey actions
  daybook-backend.exe arcade         → the 8-Bit Retro Terminal Arcade
  daybook-backend.exe mcp            → the MCP server Claude uses to reach Daybook"""
import runpy
import sys
from pathlib import Path

import reminders.paths as paths

if False:  # Bundling hint for PyInstaller static analysis; loaded lazily at runtime so mcp/helpers start fast
    import reminders.annotate  # noqa: F401
    import reminders.annotate_store  # noqa: F401
    import reminders.appwin  # noqa: F401
    import reminders.chat  # noqa: F401
    import reminders.claude_link  # noqa: F401
    import reminders.clock  # noqa: F401
    import reminders.clock_ui  # noqa: F401
    import reminders.db  # noqa: F401
    import reminders.desk  # noqa: F401
    import reminders.discord  # noqa: F401
    import reminders.dock  # noqa: F401
    import reminders.folders  # noqa: F401
    import reminders.games  # noqa: F401
    import reminders.launchpad  # noqa: F401
    import reminders.memos  # noqa: F401
    import reminders.models_hub  # noqa: F401
    import reminders.nlp  # noqa: F401
    import reminders.notes  # noqa: F401
    import reminders.obs  # noqa: F401
    import reminders.orca  # noqa: F401
    import reminders.pdflib  # noqa: F401
    import reminders.stt  # noqa: F401
    import reminders.studio  # noqa: F401
    import reminders.templates  # noqa: F401
    import reminders.ui  # noqa: F401
    import reminders.web  # noqa: F401
    import reminders.winlist  # noqa: F401
    import reminders.zotero  # noqa: F401

HELPERS = {"annotate", "sticky", "peek", "note", "agenda", "add", "dashboard", "chat"}


def main():
    # daybook-mcp.exe is only ever an MCP server: never fall through to the daemon (which exits silently
    # when Daybook is already running — AI clients saw that as "connection closed" in 1.7.9)
    if Path(sys.executable).stem.lower() == "daybook-mcp" and (len(sys.argv) < 2 or sys.argv[1] != "mcp"):
        sys.argv.insert(1, "mcp")
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if paths.FROZEN:
        from reminders import shortcuts
        shortcuts.ensure()  # Start-menu hotkeys pointing at this install (first run / after updates)
    if mode == "mcp":
        sys.argv = [str(paths.APP / "mcp_server.py")] + sys.argv[2:]
        runpy.run_path(str(paths.APP / "mcp_server.py"), run_name="__main__")
    elif mode == "arcade":
        if sys.stdout is None and sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.kernel32.AttachConsole(-1)
                sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
            except Exception:
                pass
        sys.argv = [str(paths.APP / "arcade.py")] + sys.argv[2:]
        runpy.run_path(str(paths.APP / "arcade.py"), run_name="__main__")
    elif mode in HELPERS:
        sys.argv = [str(paths.APP / "quickadd.pyw")] + sys.argv[1:]
        runpy.run_path(str(paths.APP / "quickadd.pyw"), run_name="__main__")
    else:
        sys.argv = [str(paths.APP / "daemon.pyw")] + sys.argv[1:]
        runpy.run_path(str(paths.APP / "daemon.pyw"), run_name="__main__")


if __name__ == "__main__":
    main()
