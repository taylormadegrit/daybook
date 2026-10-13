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
import threading  # noqa: E402
import time  # noqa: E402

from reminders import db, notes, paths, ui, web  # noqa: E402

POLL_MS = 15_000
AGENDA_HOUR = 3  # the day starts at 3 AM wake-up
MAX_POPUPS = 5  # more than this at once → the agenda window lists the rest

# Single instance: a second copy exits immediately
_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock.bind(("127.0.0.1", 47321))
except OSError:
    sys.exit(0)

root = tk.Tk()
root.withdraw()
try:  # Daybook icon on every pop-up window
    root.iconbitmap(default=str(Path(__file__).resolve().parent / "web" / "brand" / "daybook.ico"))
except Exception:
    pass
open_popups = {}  # reminder id → popup

from reminders import desk  # noqa: E402

stickies = desk.Manager(root)  # desktop sticky notes live in this process too

from reminders import clock_ui  # noqa: E402

ringer = clock_ui.Ringer(root)  # alarms + timers ring here, even with the Daybook window closed


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
        agenda_hour = int(db.setting("agenda_hour") or AGENDA_HOUR)
        if db.setting("agenda_popup") == "1" and now.hour >= agenda_hour and db.meta_get("agenda_shown") != today:
            db.meta_set("agenda_shown", today)
            if db.list_open(until=now.replace(hour=23, minute=59)):
                ui.AgendaWindow(root, "Good morning — today's agenda")
    except Exception as e:  # never let one bad row kill the daemon
        log = paths.DATA / "daemon.log"
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {e!r}\n")
    root.after(POLL_MS, poll)


def log_error(e):
    with open(paths.DATA / "daemon.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {e!r}\n")


def ai_worker():
    """Organizes pending notes with the local model, one at a time, in the background."""
    while True:
        try:
            nid = notes.next_pending()
            if nid:
                notes.organize(nid)
                continue
        except Exception as e:
            log_error(e)
        time.sleep(20)


def web_server():
    try:
        web.serve()
    except Exception as e:
        log_error(e)


def open_app_window():
    """--open (passed by the logon task): show Daybook as its own app window once the server is up."""
    import urllib.request
    from reminders import appwin
    for _ in range(60):
        try:
            urllib.request.urlopen(appwin.URL, timeout=2)
            break
        except Exception:
            time.sleep(1)
    appwin.open_app("today")


threading.Thread(target=web_server, daemon=True).start()
if "--open" in sys.argv and db.setting("open_at_startup") == "1":
    threading.Thread(target=open_app_window, daemon=True).start()
threading.Thread(target=ai_worker, daemon=True).start()
from reminders import memos, stt  # noqa: E402

memos.start_worker()  # transcribes voice memos in the background
from reminders import chat as _chat  # noqa: E402

threading.Thread(target=_chat.ensure_ollama, daemon=True).start()  # local AI ready after a restart
if stt.downloaded(db.setting("stt_model") or "small.en"):
    stt.preload()  # warm the speech model so dictation is quick (never triggers a download at startup)
from reminders import dock  # noqa: E402

dock.start()  # keeps docked browser windows tiled inside the Daybook window
from reminders import pdflib  # noqa: E402

root.after(20000, pdflib.scan_bg)  # refresh the PDF library shortly after start
root.after(1000, poll)
root.mainloop()
