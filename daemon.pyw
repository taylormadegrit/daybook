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

from reminders import db, notes, ui, web  # noqa: E402

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


def log_error(e):
    with open(Path(__file__).resolve().parent / "data" / "daemon.log", "a", encoding="utf-8") as f:
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
    """--open (passed by the logon task): show Daybook's Today page as its own app window once the server is up."""
    import subprocess
    import urllib.request
    import webbrowser
    url = f"http://localhost:{web.PORT}/#today"
    for _ in range(60):
        try:
            urllib.request.urlopen(url, timeout=2)
            break
        except Exception:
            time.sleep(1)
    if raise_window():  # already open (e.g. daemon restarted) → just bring it forward
        return
    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if chrome.exists():
        subprocess.Popen([str(chrome), f"--app={url}", "--window-size=1280,860"])
        for _ in range(20):  # a background process can't steal focus, so pop it over everything once
            time.sleep(1)
            if raise_window():
                break
    else:
        webbrowser.open(url)


def raise_window(title="Daybook"):
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    found = []

    def cb(h, _):
        buf = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(h, buf, 256)
        if buf.value == title and u.IsWindowVisible(h):
            found.append(h)
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    if not found:
        return False
    h = found[0]
    u.ShowWindow(h, 9)  # SW_RESTORE
    u.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0003)  # HWND_TOPMOST, no move/size
    u.SetWindowPos(h, -2, 0, 0, 0, 0, 0x0003)  # back to normal so it doesn't stay pinned
    u.SetForegroundWindow(h)
    return True


threading.Thread(target=web_server, daemon=True).start()
if "--open" in sys.argv:
    threading.Thread(target=open_app_window, daemon=True).start()
threading.Thread(target=ai_worker, daemon=True).start()
root.after(1000, poll)
root.mainloop()
