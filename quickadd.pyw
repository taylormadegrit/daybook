"""Quick-add box (Ctrl+Alt+R via the Start Menu shortcut). `quickadd.pyw agenda` opens the agenda instead."""
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reminders import ui  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else ""
if mode in ("dashboard", "chat"):  # Ctrl+Alt+D / Ctrl+Alt+C
    from reminders import appwin
    appwin.open_app("chat" if mode == "chat" else "today")
    sys.exit(0)

root = tk.Tk()
root.withdraw()
try:  # Daybook icon on every pop-up window
    root.iconbitmap(default=str(Path(__file__).resolve().parent / "web" / "brand" / "daybook.ico"))
except Exception:
    pass
if mode == "agenda":    # Ctrl+Alt+A
    ui.AgendaWindow(root)
elif mode == "note":    # Ctrl+Alt+N
    ui.QuickNote(root)
else:                   # Ctrl+Alt+R
    ui.QuickAdd(root)


def exit_when_no_windows():
    # QuickAdd may hand off to the agenda window, so quit only once every window is closed
    if not [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]:
        root.destroy()
    else:
        root.after(300, exit_when_no_windows)


root.after(300, exit_when_no_windows)
root.mainloop()
