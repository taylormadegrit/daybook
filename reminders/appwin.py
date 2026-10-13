"""The Daybook app window: Chrome in --app mode (own window, no tabs). Reused instead of duplicated."""
import ctypes
import subprocess
import time
import webbrowser
from ctypes import wintypes
from pathlib import Path

URL = "http://localhost:8503/"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
TITLE = "Daybook"


def find_window():
    u = ctypes.windll.user32
    found = []

    def cb(h, _):
        buf = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(h, buf, 256)
        if buf.value == TITLE and u.IsWindowVisible(h):
            found.append(h)
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return found[0] if found else None


def fit_to_screen(h):
    """Keep the whole window on its monitor (a remembered size can be taller than the screen)."""
    u = ctypes.windll.user32

    class MI(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("flags", wintypes.DWORD)]
    if u.IsZoomed(h):
        return
    mi = MI(); mi.cb = ctypes.sizeof(MI)
    u.GetMonitorInfoW(u.MonitorFromWindow(h, 2), ctypes.byref(mi))
    r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
    wk = mi.rcWork
    w, ht = min(r.right - r.left, wk.right - wk.left), min(r.bottom - r.top, wk.bottom - wk.top)
    x, y = min(max(r.left, wk.left), wk.right - w), min(max(r.top, wk.top), wk.bottom - ht)
    if (x, y, w, ht) != (r.left, r.top, r.right - r.left, r.bottom - r.top):
        u.SetWindowPos(h, None, x, y, w, ht, 0x0004 | 0x0010)


def raise_window(h):
    u = ctypes.windll.user32
    fit_to_screen(h)
    u.ShowWindow(h, 9)  # SW_RESTORE
    u.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0003)  # pop over everything once...
    u.SetWindowPos(h, -2, 0, 0, 0, 0, 0x0003)  # ...then back to normal
    u.SetForegroundWindow(h)


def open_app(view="today", wait=True):
    """Bring Daybook forward (opening it if needed). `view`: today, chat, notes…"""
    h = find_window()
    if h and view == "today":
        raise_window(h)
        return
    url = URL + "#" + view
    if CHROME.exists():
        subprocess.Popen([str(CHROME), f"--app={url}", "--window-size=1320,880"])
        if wait:
            for _ in range(20):
                time.sleep(0.5)
                h = find_window()
                if h:
                    raise_window(h)
                    break
    else:
        webbrowser.open(url)
