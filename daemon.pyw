"""Background reminder daemon — started at logon by the LocalRemindersDaemon scheduled task.
Every 15 s it pops up anything due (including reminders missed while the PC was off),
and once a day after 8 AM it shows the morning agenda.
"""
import socket
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reminders import db, ui  # noqa: E402

POLL_MS = 15_000
AGENDA_HOUR = 8
MAX_POPUPS = 5  # more than this at once → the agenda window lists the rest

# Single instance: a second copy exits immediately
_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock.bind(("127.0.0.1", 47321))
except OSError:
    sys.exit(0)

root = tk.Tk()
root.withdraw()
open_popups = {}  # reminder id → popup


def closed(rid):
    open_popups.pop(rid, None)


def poll():
    try:
        due = [r for r in db.due_now() if r["id"] not in open_popups]
        for r in due:
            if len(open_popups) >= MAX_POPUPS:
                ui.AgendaWindow(root, "More reminders are due")
                break
            slot = next(i for i in range(MAX_POPUPS + 1) if i not in {p.slot for p in open_popups.values()})
            p = ui.ReminderPopup(root, r, slot, closed)
            p.slot = slot
            open_popups[r["id"]] = p

        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if now.hour >= AGENDA_HOUR and db.meta_get("agenda_shown") != today:
            db.meta_set("agenda_shown", today)
            if db.list_open(until=now.replace(hour=23, minute=59)):
                ui.AgendaWindow(root, "Good morning — today's agenda")
    except Exception as e:  # never let one bad row kill the daemon
        log = Path(__file__).resolve().parent / "data" / "daemon.log"
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {e!r}\n")
    root.after(POLL_MS, poll)


root.after(1000, poll)
root.mainloop()
