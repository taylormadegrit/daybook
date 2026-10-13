"""Browser workspace: real Chrome / Edge / Brave / Comet windows (with their profiles, tabs and logins) docked
inside the Daybook window. Daybook draws an empty 'stage'; this module keeps the docked windows tiled exactly
over it, owned by the Daybook window (so they move, minimize and stack with it) and hides them when you leave
the Browser page. Nothing is injected into the browser — it's ordinary window management.
Docked windows are kept just above Daybook in the stacking order (not 'owned' by it), so closing Daybook
never closes a browser window — they simply return to the desktop."""
import ctypes
import subprocess
import threading
import time
from ctypes import wintypes

from flask import Blueprint, jsonify, request

from . import appwin

bp = Blueprint("dock", __name__)
u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
u32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
GWLP_HWNDPARENT = -8
SWP = 0x0004 | 0x0010 | 0x0040  # NOZORDER | NOACTIVATE | SHOWWINDOW
BROWSER_EXES = {"chrome.exe", "msedge.exe", "brave.exe", "comet.exe", "vivaldi.exe", "opera.exe", "firefox.exe", "thorium.exe", "zen.exe"}
LOCK = threading.RLock()
S = {"docked": [], "stage": None, "visible": False, "layout": "auto", "focus": None, "shown": None, "last": {}}


class RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


def _title(h):
    buf = ctypes.create_unicode_buffer(512)
    u32.GetWindowTextW(h, buf, 512)
    return buf.value


def _exe(h):
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    hp = k32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
    if not hp:
        return ""
    buf, n = ctypes.create_unicode_buffer(520), wintypes.DWORD(520)
    ok = k32.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(n))
    k32.CloseHandle(hp)
    return buf.value.rsplit("\\", 1)[-1].lower() if ok else ""


def _cls(h):
    buf = ctypes.create_unicode_buffer(128)
    u32.GetClassNameW(h, buf, 128)
    return buf.value


def browser_windows():
    """Top-level, visible browser windows (not Daybook itself)."""
    me, out = appwin.find_window(), []

    def cb(h, _):
        if h != me and u32.IsWindowVisible(h) and _cls(h) in ("Chrome_WidgetWin_1", "MozillaWindowClass") and _title(h):
            exe = _exe(h)
            if exe in BROWSER_EXES and not (u32.GetWindowLongPtrW(h, -20) & 0x80):  # skip tool windows
                out.append({"hwnd": int(h), "title": _title(h), "exe": exe})
        return True
    u32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return out


def viewport_origin(me):
    """Top-left of the Daybook page itself (Chrome draws the app title bar inside the window, so the page's
    render widget is the reliable reference)."""
    found = []

    def cb(h, _):
        if _cls(h) == "Chrome_RenderWidgetHostHWND" and u32.IsWindowVisible(h):
            found.append(h)
        return True
    u32.EnumChildWindows(me, ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    if found:
        r = RECT()
        u32.GetWindowRect(found[0], ctypes.byref(r))
        return r.l, r.t
    pt = wintypes.POINT(0, 0)
    u32.ClientToScreen(me, ctypes.byref(pt))
    return pt.x, pt.y


def _frame_pad(h):
    """Windows 10/11 windows have invisible resize borders; return (left, top, right, bottom) to compensate."""
    r, f = RECT(), RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(f), ctypes.sizeof(f)) != 0:
        return 0, 0, 0, 0
    return f.l - r.l, f.t - r.t, r.r - f.r, r.b - f.b


def _rect(h):
    r = RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    return [r.l, r.t, r.r - r.l, r.b - r.t]


def attach(hwnd, label=""):
    with LOCK:
        if any(d["hwnd"] == hwnd for d in S["docked"]) or not u32.IsWindow(hwnd):
            return
        S["docked"].append({"hwnd": hwnd, "label": label, "orig": _rect(hwnd), "exe": _exe(hwnd)})
        S["focus"] = hwnd
        S["last"].pop(hwnd, None)


def detach(hwnd, restore=True):
    with LOCK:
        d = next((x for x in S["docked"] if x["hwnd"] == hwnd), None)
        if not d:
            return
        S["docked"].remove(d)
        S["last"].pop(hwnd, None)
    if u32.IsWindow(hwnd):
        if u32.GetWindowLongPtrW(hwnd, GWLP_HWNDPARENT):
            u32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, 0)
        u32.ShowWindow(hwnd, 5)
        if restore:
            x, y, w, h = d["orig"]
            u32.SetWindowPos(hwnd, None, x + 30, y + 30, max(w, 900), max(h, 650), 0x0004 | 0x0040)
        u32.SetForegroundWindow(hwnd)


def open_profile(browser, profile, url="", dock=True):
    """Start a new window for that profile and dock it as soon as it appears."""
    from . import launchpad
    before = {w["hwnd"] for w in browser_windows()}
    b = next((x for x in launchpad.browsers() if x["id"] == browser), None)
    if not b or not b["exe"]:
        raise ValueError("Browser not found")
    p = next((x for x in b["profiles"] if x["id"] == profile), {"name": profile})
    args = [b["exe"], "-P", profile, "-new-window"] if browser in ("firefox", "zen", "librewolf") else \
        [b["exe"], f"--profile-directory={profile}", "--new-window"]
    subprocess.Popen(args + ([url] if url else []), creationflags=0x00000008)
    for _ in range(60):
        time.sleep(0.2)
        new = [w for w in browser_windows() if w["hwnd"] not in before]
        if new:
            time.sleep(0.4)  # let it finish creating before we move it
            if dock:
                attach(new[0]["hwnd"], f"{p.get('name', profile)} · {b['name'].replace('Google ', '')}")
            return new[0]["hwnd"]
    raise RuntimeError("The browser window didn't appear")


def _tiles(n, x, y, w, h, layout, gap):
    if n == 0:
        return []
    if layout == "auto":
        layout = "cols" if n <= 3 else "grid"
    if layout == "rows":
        hh = (h - gap * (n - 1)) / n
        return [(x, y + i * (hh + gap), w, hh) for i in range(n)]
    if layout == "focus" and n > 1:
        bw = (w - gap) * 0.66
        sh = (h - gap * (n - 2)) / (n - 1)
        return [(x, y, bw, h)] + [(x + bw + gap, y + i * (sh + gap), w - bw - gap, sh) for i in range(n - 1)]
    if layout == "grid":
        import math
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        out = []
        ch = (h - gap * (rows - 1)) / rows
        for i in range(n):
            r, c = divmod(i, cols)
            in_row = min(cols, n - r * cols)  # last row stretches to fill
            cw = (w - gap * (in_row - 1)) / in_row
            out.append((x + c * (cw + gap), y + r * (ch + gap), cw, ch))
        return out
    cw = (w - gap * (n - 1)) / n  # columns
    return [(x + i * (cw + gap), y, cw, h) for i in range(n)]


def _loop():
    try:
        u32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2: real pixels everywhere
    except Exception:
        pass
    while True:
        time.sleep(0.15)
        try:
            with LOCK:
                S["docked"] = [d for d in S["docked"] if u32.IsWindow(d["hwnd"])]
                docked = list(S["docked"])
                st, visible, layout, focus = S["stage"], S["visible"], S["layout"], S["focus"]
            if not docked:
                continue
            me = appwin.find_window()
            if not me:  # Daybook window closed → give every window back to the desktop, visible
                for d in docked:
                    detach(d["hwnd"], restore=True)
                S["shown"] = None
                continue
            show = bool(st and visible and not u32.IsIconic(me))
            if not show:
                if S["shown"] is not False:
                    for d in docked:
                        u32.ShowWindow(d["hwnd"], 0)  # SW_HIDE
                    S["shown"], S["last"] = False, {}
                continue
            ox, oy = viewport_origin(me)
            dpr = st["dpr"]
            x, y, w, h = ox + st["x"] * dpr, oy + st["y"] * dpr, st["w"] * dpr, st["h"] * dpr
            order = sorted(docked, key=lambda d: d["hwnd"] != focus) if layout == "focus" else docked
            above = _above_set(me)
            for d, (tx, ty, tw, th) in zip(order, _tiles(len(order), x, y, w, h, layout, int(6 * dpr))):
                hw = d["hwnd"]
                if u32.IsZoomed(hw) or u32.IsIconic(hw):
                    u32.ShowWindow(hw, 9)  # SW_RESTORE
                pl, pt_, pr, pb = _frame_pad(hw)  # make the *visible* edges line up with the tile
                want = (round(tx - pl), round(ty - pt_), round(tw + pl + pr), round(th + pt_ + pb))
                if S["last"].get(hw) != want or not u32.IsWindowVisible(hw):
                    u32.SetWindowPos(hw, None, *want, SWP)
                    S["last"][hw] = want
                if hw not in above:  # Daybook got clicked and jumped over this one → slip it back just above Daybook
                    prev = u32.GetWindow(me, 3)
                    if not prev or u32.GetWindowLongPtrW(prev, -20) & 0x8:  # never borrow topmost status
                        prev = 0  # HWND_TOP of the normal windows
                    u32.SetWindowPos(hw, prev, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
                    above = _above_set(me)
            S["shown"] = True
        except Exception:
            pass


def _above_set(me):
    """Every window currently stacked above the Daybook window."""
    out, h = set(), u32.GetWindow(me, 3)  # GW_HWNDPREV
    while h and len(out) < 2000:
        out.add(h)
        h = u32.GetWindow(h, 3)
    return out


def start():
    threading.Thread(target=_loop, daemon=True).start()


# ---------------- routes ----------------

def _state():
    with LOCK:
        return [{"hwnd": d["hwnd"], "label": d["label"], "title": _title(d["hwnd"]), "exe": d["exe"], "focus": d["hwnd"] == S["focus"]}
                for d in S["docked"] if u32.IsWindow(d["hwnd"])]


@bp.get("/api/dock")
def d_state():
    docked = {d["hwnd"] for d in S["docked"]}
    return jsonify(docked=_state(), layout=S["layout"], available=[w for w in browser_windows() if w["hwnd"] not in docked])


@bp.post("/api/dock/stage")
def d_stage():
    j = request.get_json() or {}
    with LOCK:
        S["visible"] = bool(j.get("visible"))
        if all(k in j for k in ("x", "y", "w", "h")):
            S["stage"] = {k: float(j[k]) for k in ("x", "y", "w", "h")} | {"dpr": float(j.get("dpr", 1))}
    return jsonify(ok=True)


@bp.post("/api/dock/<action>")
def d_action(action):
    j = request.get_json() or {}
    try:
        if action == "open":
            hw = open_profile(j.get("browser"), j.get("profile"), j.get("url", ""))
            return jsonify(ok=True, hwnd=hw)
        if action == "attach":
            w = next((x for x in browser_windows() if x["hwnd"] == int(j.get("hwnd", 0))), None)
            if not w:
                return jsonify(error="That window is gone"), 404
            attach(w["hwnd"], j.get("label", ""))
        elif action == "undock":
            for hw in ([d["hwnd"] for d in S["docked"]] if j.get("all") else [int(j.get("hwnd", 0))]):
                detach(hw)
        elif action == "close":
            u32.PostMessageW(int(j.get("hwnd", 0)), 0x0010, 0, 0)  # WM_CLOSE — the browser asks if tabs need saving
        elif action == "layout":
            S["layout"] = j.get("layout", "auto") if j.get("layout") in ("auto", "cols", "rows", "grid", "focus") else "auto"
            S["last"] = {}
        elif action == "focus":
            with LOCK:
                S["focus"] = int(j.get("hwnd", 0))
                S["last"] = {}
            u32.SetForegroundWindow(S["focus"])
        else:
            return jsonify(error="unknown action"), 400
    except Exception as e:
        return jsonify(error=str(e)[:200]), 400
    return jsonify(ok=True)


# ---------------- desktop app: real Chrome windows embedded as panes ----------------
# The Chrome window becomes a child of the Daybook window (SetParent), so it moves, hides and minimizes with Daybook
# instantly. Its frame styles are saved and restored when you pop it back out.
EMB = {}  # hwnd → {"style", "exstyle", "rect", "label", "browser", "profile"}
WS_CHILD, WS_POPUP, WS_CAPTION, WS_THICK, WS_SYS, WS_MIN, WS_MAX = 0x40000000, 0x80000000, 0x00C00000, 0x00040000, 0x00080000, 0x00020000, 0x00010000


def _daybook():
    return appwin.find_window()


NORMAL_STYLE = 0x16CF0000  # visible overlapped window with caption, frame, min/max — how browsers start out


def adopt():
    """After a service restart: pick up browser windows that are still inside the Daybook window."""
    me = _daybook()
    if not me:
        return
    found = []

    def cb(h, _):
        if u32.GetParent(h) == me and _cls(h) in ("Chrome_WidgetWin_1", "MozillaWindowClass") and _exe(h) in BROWSER_EXES:
            found.append(h)
        return True
    u32.EnumChildWindows(me, ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    for h in found:
        if h not in EMB:
            EMB[h] = {"style": NORMAL_STYLE, "exstyle": u32.GetWindowLongPtrW(h, -20) | 0x40000, "rect": [200, 120, 1100, 760],
                      "label": "Chrome", "browser": "chrome", "profile": "", "shown": None}


def embed(hwnd, label="", browser="", profile=""):
    me = _daybook()
    if not me or not u32.IsWindow(hwnd) or hwnd in EMB:
        return
    style, ex = u32.GetWindowLongPtrW(hwnd, -16), u32.GetWindowLongPtrW(hwnd, -20)
    EMB[hwnd] = {"style": style, "exstyle": ex, "rect": _rect(hwnd), "label": label, "browser": browser, "profile": profile, "shown": None}
    if u32.IsZoomed(hwnd) or u32.IsIconic(hwnd):
        u32.ShowWindow(hwnd, 9)
    u32.ShowWindow(hwnd, 0)
    new = (style & ~(WS_POPUP | WS_CAPTION | WS_THICK | WS_SYS | WS_MIN | WS_MAX)) | WS_CHILD
    u32.SetWindowLongPtrW(hwnd, -16, new)
    u32.SetParent(hwnd, me)
    u32.SetWindowPos(hwnd, None, 0, 0, 10, 10, 0x0020 | 0x0004 | 0x0010)  # FRAMECHANGED | NOZORDER | NOACTIVATE


def release(hwnd, close=False):
    e = EMB.pop(hwnd, None)
    if not e or not u32.IsWindow(hwnd):
        return
    u32.SetParent(hwnd, None)
    u32.SetWindowLongPtrW(hwnd, -16, e["style"])
    u32.SetWindowLongPtrW(hwnd, -20, e["exstyle"])
    x, y, w, h = e["rect"]
    u32.SetWindowPos(hwnd, None, x, y, max(w, 900), max(h, 650), 0x0020 | 0x0004 | 0x0040)
    if close:
        u32.PostMessageW(hwnd, 0x0010, 0, 0)
    else:
        u32.SetForegroundWindow(hwnd)


def place(items, visible, dpr):
    """items: [{hwnd, x, y, w, h}] in page CSS pixels (the Daybook page fills the window's client area)."""
    me = _daybook()
    for hw in list(EMB):
        if not u32.IsWindow(hw):  # closed from inside Chrome
            EMB.pop(hw, None)
    want = {int(i["hwnd"]): i for i in items}
    for hw, e in EMB.items():
        i = want.get(hw)
        if not visible or not i or not me:
            if e["shown"] is not False:
                u32.ShowWindow(hw, 0)
                e["shown"] = False
            continue
        if u32.GetParent(hw) != me:
            u32.SetParent(hw, me)
        # HWND_TOP among Daybook's child windows, so it sits above the page's own render surface
        u32.SetWindowPos(hw, 0, round(i["x"] * dpr), round(i["y"] * dpr), round(i["w"] * dpr), round(i["h"] * dpr), 0x0010 | 0x0040)
        e["shown"] = True


def open_embedded(browser, profile, url=""):
    hw = open_profile(browser, profile, url, dock=False)
    from . import launchpad
    b = next((x for x in launchpad.browsers() if x["id"] == browser), {"name": browser, "profiles": []})
    p = next((x for x in b["profiles"] if x["id"] == profile), {"name": profile, "color": b.get("color", "#888")})
    embed(hw, p.get("name", profile), browser, profile)
    return hw


@bp.get("/api/dock/embedded")
def d_embedded():
    if not EMB:
        adopt()
    return jsonify([{"hwnd": hw, "label": e["label"], "browser": e["browser"], "profile": e["profile"], "title": _title(hw)}
                    for hw, e in list(EMB.items()) if u32.IsWindow(hw)])


@bp.post("/api/dock/embed/<action>")
def d_embed(action):
    j = request.get_json() or {}
    try:
        if action == "open":
            return jsonify(hwnd=open_embedded(j.get("browser"), j.get("profile"), j.get("url", "")))
        if action == "place":
            place(j.get("items", []), bool(j.get("visible")), float(j.get("dpr", 1)))
        elif action == "release":
            for hw in ([*EMB] if j.get("all") else [int(j.get("hwnd", 0))]):
                release(hw, close=bool(j.get("close")))
        else:
            return jsonify(error="unknown action"), 400
    except Exception as e:
        return jsonify(error=str(e)[:200]), 400
    return jsonify(ok=True)
