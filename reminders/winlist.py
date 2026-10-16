"""Top-level app windows (for "annotate this window"). No Tk / PIL / DPI side effects, so the web
server can import it safely; the annotation overlay imports the same helpers."""
import ctypes
import os
import sys
from ctypes import wintypes

u32 = ctypes.windll.user32 if sys.platform == "win32" else None


def get_window_box(hwnd):
    if not hwnd or sys.platform != "win32":
        return None
    try:
        dwmapi = ctypes.windll.dwmapi
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        r = wintypes.RECT()
        res = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r))
        if res == 0:
            return (r.left, r.top, r.right, r.bottom)
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        return (r.left, r.top, r.right, r.bottom)
    except Exception:
        return None


def get_window_title(hwnd):
    if not hwnd or sys.platform != "win32":
        return ""
    try:
        l = u32.GetWindowTextLengthW(hwnd)
        if l == 0:
            return ""
        buf = ctypes.create_unicode_buffer(l + 1)
        u32.GetWindowTextW(hwnd, buf, l + 1)
        return buf.value.strip()
    except Exception:
        return ""


def get_open_windows():
    if sys.platform != "win32":
        return []
    try:
        # plain EnumWindows: the server runs in the user's session already, and swapping the
        # process window station / thread desktop here would affect every other request
        all_h = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
        def cb(h, lp):
            if h:
                all_h.append(h)
            return 1

        cb_inst = WNDENUMPROC(cb)
        u32.EnumWindows(cb_inst, 0)
        own_pid = os.getpid()

        apps = []
        ignored_classes = {
            "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
            "Windows.UI.Core.CoreWindow", "TopLevelWindowForOverflowXamlIsland",
            "IME", "MSCTFIME UI", "TaskListThumbnailWnd"
        }

        for h in all_h:
            if not u32.IsWindowVisible(h):
                continue
            ex = u32.GetWindowLongW(h, -20)
            if ex & 0x00000080:  # WS_EX_TOOLWINDOW
                continue
            len_ = u32.GetWindowTextLengthW(h)
            if len_ == 0:
                continue
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value == own_pid:
                continue
            buf = ctypes.create_unicode_buffer(len_ + 1)
            u32.GetWindowTextW(h, buf, len_ + 1)
            title = buf.value.strip()
            if not title:
                continue

            cbuf = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(h, cbuf, 256)
            cls = cbuf.value
            if cls in ignored_classes:
                continue

            r = wintypes.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            w = r.right - r.left
            ht = r.bottom - r.top
            if w < 160 or ht < 100:
                continue

            if u32.GetWindow(h, 4):  # GW_OWNER
                continue

            apps.append({
                "hwnd": int(h),
                "title": title,
                "class": cls,
                "width": w,
                "height": ht,
                "rect": [r.left, r.top, r.right, r.bottom]
            })
        return apps
    except Exception:
        return []
