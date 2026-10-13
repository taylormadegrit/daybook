"""Installed app only: create the Start-menu shortcuts that give Daybook its global hotkeys
(Ctrl+Alt+R reminder, N note, S sticky, W show stickies, P annotate, A agenda, C chat), pointing at this install."""
import os
import subprocess
import sys
from pathlib import Path

from . import paths

HOTKEYS = [("New Reminder", "add", "R"), ("Quick Note", "note", "N"), ("Agenda", "agenda", "A"), ("Daybook Chat", "chat", "C"),
           ("Sticky Note", "sticky", "S"), ("Show Sticky Notes", "peek", "W"), ("Annotate Screen", "annotate", "P")]
MARK = paths.DATA / "shortcuts.v2"  # v2: no .lnk hotkeys (the Daybook app registers them itself)


def ensure():
    if os.environ.get("DAYBOOK_NO_SHORTCUTS") or (MARK.exists() and MARK.read_text() == sys.executable):
        return
    folder = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Daybook"
    folder.mkdir(parents=True, exist_ok=True)
    ico = str(paths.WEB / "brand" / "daybook.ico")
    lines = ["$ws = New-Object -ComObject WScript.Shell"]
    for name, mode, key in HOTKEYS:
        lines.append(f"$l = $ws.CreateShortcut('{folder / (name + '.lnk')}'); $l.TargetPath = '{sys.executable}'; $l.Arguments = '{mode}'; "
                     f"$l.Hotkey = ''; $l.IconLocation = '{ico},0'; $l.WorkingDirectory = '{Path(sys.executable).parent}'; $l.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", "; ".join(lines)], creationflags=0x08000000, timeout=60)
    MARK.write_text(sys.executable)
