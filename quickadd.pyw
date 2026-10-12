"""Quick-add box (Ctrl+Alt+R via the Start Menu shortcut). `quickadd.pyw agenda` opens the agenda instead."""
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reminders import ui  # noqa: E402

root = tk.Tk()
root.withdraw()
if len(sys.argv) > 1 and sys.argv[1] == "agenda":
    ui.AgendaWindow(root)
else:
    ui.QuickAdd(root)


def exit_when_no_windows():
    # QuickAdd may hand off to the agenda window, so quit only once every window is closed
    if not [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]:
        root.destroy()
    else:
        root.after(300, exit_when_no_windows)


root.after(300, exit_when_no_windows)
root.mainloop()
