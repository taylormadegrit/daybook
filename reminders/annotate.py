"""Annotate the screen: freeze every monitor, draw on top (pen, highlighter, arrow, box, circle, text,
eraser), then save a PNG or copy it to the clipboard. Saved image = the monitor(s) you drew on.
Run in its own process (quickadd.pyw annotate) so the capture is clean."""
import ctypes
import io
import math
import sys
import time
import tkinter as tk
from ctypes import wintypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixels on every monitor
except Exception:
    pass

from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageTk  # noqa: E402

def _declare_setwindowpos():
    """HWND_TOPMOST is -1: it must be passed pointer-sized or 64-bit Windows misreads it."""
    import ctypes
    from ctypes import wintypes
    f = ctypes.windll.user32.SetWindowPos
    f.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    f.restype = wintypes.BOOL


_declare_setwindowpos()


u32 = ctypes.windll.user32
COLORS = ["#ff3b5c", "#ff9f1c", "#ffd60a", "#2ee59d", "#3aa0ff", "#9b6bff", "#ffffff", "#111111"]
SIZES = [3, 6, 12]
TOOLS = [("pen", "✎", "Pen (P)"), ("hl", "▬", "Highlighter (H)"), ("arrow", "➚", "Arrow (A)"), ("rect", "▭", "Box (B)"),
         ("oval", "◯", "Circle (C)"), ("text", "T", "Text (T)"), ("erase", "⌫", "Eraser (E)")]
BG, PANEL, FG, MUTED, ACCENT = "#14161f", "#1d2030", "#eceef4", "#8a90a3", "#8b7bff"


def monitors():
    out = []
    cb_t = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(h, dc, r, _):
        out.append((r.contents.left, r.contents.top, r.contents.right, r.contents.bottom))
        return 1
    u32.EnumDisplayMonitors(0, 0, cb_t(cb), 0)
    return out


def virtual_screen():
    return u32.GetSystemMetrics(76), u32.GetSystemMetrics(77), u32.GetSystemMetrics(78), u32.GetSystemMetrics(79)


def copy_to_clipboard(img):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "BMP")
    data = buf.getvalue()[14:]  # CF_DIB = BMP without the file header
    k32 = ctypes.windll.kernel32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    h = k32.GlobalAlloc(0x0042, len(data))
    p = k32.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    k32.GlobalUnlock(h)
    u32.OpenClipboard(0)
    u32.EmptyClipboard()
    u32.SetClipboardData(8, h)  # CF_DIB
    u32.CloseClipboard()


class Annotator:
    def __init__(self, hide_hwnd=None):
        self.hidden = hide_hwnd
        if hide_hwnd:
            u32.ShowWindow(hide_hwnd, 6)  # minimize Daybook so it isn't in the shot
            time.sleep(0.45)
        self.L, self.T, self.W, self.H = virtual_screen()
        self.shot = ImageGrab.grab(bbox=(self.L, self.T, self.L + self.W, self.T + self.H), all_screens=True)
        self.mons = monitors()
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.W}x{self.H}+{self.L}+{self.T}")
        self.root.attributes("-topmost", True)
        self.cv = tk.Canvas(self.root, width=self.W, height=self.H, highlightthickness=0, cursor="pencil", bd=0)
        self.cv.pack()
        self.photo = ImageTk.PhotoImage(self.shot)
        self.cv.create_image(0, 0, image=self.photo, anchor="nw")
        for (l, t, r, b) in self.mons:  # thin glowing frame = "you're in annotation mode"
            self.cv.create_rectangle(l - self.L + 1, t - self.T + 1, r - self.L - 2, b - self.T - 2, outline=ACCENT, width=3)
        self.tool, self.color, self.size = "pen", COLORS[0], SIZES[1]
        self.shapes, self.cur, self.saved = [], None, True
        self.cv.bind("<ButtonPress-1>", self.down)
        self.cv.bind("<B1-Motion>", self.drag)
        self.cv.bind("<ButtonRelease-1>", self.up)
        self.cv.bind("<Button-3>", lambda e: self.undo())
        for k, fn in (("<Escape>", self.escape), ("<Control-z>", self.undo), ("<Control-s>", self.save),
                      ("<Control-c>", self.copy)):
            self.root.bind(k, lambda e, f=fn: f())
        for key, (tool, *_ ) in zip("phabcte", TOOLS):
            self.root.bind(key, lambda e, t=tool: self.set_tool(t))
        self.toolbar()
        self.root.after(50, lambda: (self.root.focus_force(), self.cv.focus_set()))
        self.root.after(150, self.raise_toolbar)

    def raise_toolbar(self):
        """Both windows are topmost; keep the toolbar above the frozen screen."""
        try:
            self.tb.attributes("-topmost", True)
            self.tb.lift()
            u32.SetWindowPos(int(self.tb.wm_frame(), 16), -1, 0, 0, 0, 0, 0x0013)
        except Exception:
            pass

    # ---------- toolbar ----------
    def toolbar(self):
        tb = self.tb = tk.Toplevel(self.root)
        tb.overrideredirect(True)
        tb.attributes("-topmost", True)
        tb.configure(bg=BG)
        f = tk.Frame(tb, bg=BG, padx=8, pady=6)
        f.pack()
        grip = tk.Label(f, text="⠿", bg=BG, fg=MUTED, font=("Segoe UI", 12), cursor="fleur")
        grip.pack(side="left", padx=(0, 6))
        grip.bind("<ButtonPress-1>", lambda e: setattr(self, "_g", (e.x_root - tb.winfo_x(), e.y_root - tb.winfo_y())))
        grip.bind("<B1-Motion>", lambda e: tb.geometry(f"+{e.x_root - self._g[0]}+{e.y_root - self._g[1]}"))
        self.tbtns = {}
        for tool, sym, tip in TOOLS:
            b = tk.Label(f, text=sym, width=2, bg=PANEL, fg=FG, font=("Segoe UI Symbol", 13), cursor="hand2", padx=4, pady=2)
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda e, t=tool: self.set_tool(t))
            self.tbtns[tool] = b
        self._sep(f)
        self.cbtns = {}
        for c in COLORS:
            b = tk.Label(f, text="●", fg=c, bg=BG, font=("Segoe UI", 15), cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, c=c: self.set_color(c))
            self.cbtns[c] = b
        self._sep(f)
        self.sbtns = {}
        for s in SIZES:
            b = tk.Label(f, text="●", fg=FG, bg=BG, font=("Segoe UI", 6 + s), cursor="hand2", padx=3)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, s=s: self.set_size(s))
            self.sbtns[s] = b
        self._sep(f)
        for sym, tip, fn in (("↶", "Undo (Ctrl+Z)", self.undo), ("🗑", "Clear all", self.clear)):
            b = tk.Label(f, text=sym, bg=PANEL, fg=FG, font=("Segoe UI Symbol", 12), cursor="hand2", padx=6, pady=2)
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda e, f=fn: f())
        self._sep(f)
        for txt, fn, color in (("Save", self.save, ACCENT), ("Copy", self.copy, PANEL), ("✕", self.escape, PANEL)):
            b = tk.Label(f, text=txt, bg=color, fg="#0a0b10" if color == ACCENT else FG, font=("Segoe UI", 10, "bold"),
                         cursor="hand2", padx=10, pady=4)
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda e, f=fn: f())
        self.status = tk.Label(tb, text="Draw anywhere · right-click = undo · Esc = close", bg=BG, fg=MUTED,
                               font=("Segoe UI", 9))
        self.status.pack(pady=(0, 6))
        tb.update_idletasks()
        pl, pt, pr, pb = next((m for m in self.mons if m[0] <= 0 < m[2] and m[1] <= 0 < m[3]), self.mons[0])
        tb.geometry(f"+{pl + (pr - pl - tb.winfo_reqwidth()) // 2}+{pt + 14}")
        self.set_tool("pen")
        self.set_color(self.color)
        self.set_size(self.size)

    def _sep(self, f):
        tk.Frame(f, width=1, height=22, bg="#33374a").pack(side="left", padx=8)

    def set_tool(self, t):
        self.tool = t
        for k, b in self.tbtns.items():
            b.configure(bg=ACCENT if k == t else PANEL, fg="#0a0b10" if k == t else FG)
        self.cv.configure(cursor={"text": "xterm", "erase": "X_cursor"}.get(t, "pencil"))

    def set_color(self, c):
        self.color = c
        for k, b in self.cbtns.items():
            b.configure(bg="#3a3f55" if k == c else BG)

    def set_size(self, s):
        self.size = s
        for k, b in self.sbtns.items():
            b.configure(fg=ACCENT if k == s else MUTED)

    def flash(self, msg):
        self.status.configure(text=msg, fg="#3ee0a0")
        self.root.after(3500, lambda: self.status.configure(text="Draw anywhere · right-click = undo · Esc = close", fg=MUTED))

    # ---------- drawing ----------
    def down(self, e):
        x, y = e.x, e.y
        if self.tool == "text":
            return self.text_box(x, y)
        if self.tool == "erase":
            return self.erase(x, y)
        s = {"type": self.tool, "color": self.color, "size": self.size, "pts": [x, y, x, y], "ids": []}
        w = self.size * (4 if self.tool == "hl" else 1)
        if self.tool in ("pen", "hl"):
            kw = {"stipple": "gray50"} if self.tool == "hl" else {}
            s["ids"].append(self.cv.create_line(x, y, x + 1, y + 1, fill=self.color, width=w, capstyle="round",
                                                joinstyle="round", smooth=True, **kw))
        elif self.tool == "arrow":
            s["ids"].append(self.cv.create_line(x, y, x, y, fill=self.color, width=w, arrow="last",
                                                arrowshape=(w * 4 + 8, w * 5 + 10, w * 2 + 4), capstyle="round"))
        elif self.tool == "rect":
            s["ids"].append(self.cv.create_rectangle(x, y, x, y, outline=self.color, width=w))
        elif self.tool == "oval":
            s["ids"].append(self.cv.create_oval(x, y, x, y, outline=self.color, width=w))
        self.cur = s

    def drag(self, e):
        if self.tool == "erase":
            return self.erase(e.x, e.y)
        s = self.cur
        if not s:
            return
        if s["type"] in ("pen", "hl"):
            if math.hypot(e.x - s["pts"][-2], e.y - s["pts"][-1]) >= 2:
                s["pts"] += [e.x, e.y]
                self.cv.coords(s["ids"][0], *s["pts"])
        else:
            s["pts"][2:] = [e.x, e.y]
            self.cv.coords(s["ids"][0], *s["pts"])

    def up(self, e):
        if self.cur:
            self.shapes.append(self.cur)
            self.cur, self.saved = None, False
        self.raise_toolbar()

    def text_box(self, x, y):
        fs = 10 + self.size * 2
        ent = tk.Entry(self.cv, font=("Segoe UI", fs, "bold"), fg=self.color, bg="#111", insertbackground=self.color,
                       relief="flat", width=24)
        win = self.cv.create_window(x, y, window=ent, anchor="nw")
        ent.focus_set()

        def commit(_=None):
            t = ent.get().strip()
            self.cv.delete(win)
            if t:
                tid = self.cv.create_text(x + 3, y + 2, text=t, fill=self.color, anchor="nw", font=("Segoe UI", fs, "bold"))
                self.shapes.append({"type": "text", "color": self.color, "size": fs, "pts": [x + 3, y + 2], "text": t, "ids": [tid]})
                self.saved = False
            self.cv.focus_set()
        ent.bind("<Return>", commit)
        ent.bind("<Escape>", lambda e: (self.cv.delete(win), self.cv.focus_set(), "break")[-1])
        ent.bind("<FocusOut>", commit)

    def erase(self, x, y):
        hits = set(self.cv.find_overlapping(x - 6, y - 6, x + 6, y + 6))
        for s in reversed(self.shapes):
            if hits & set(s["ids"]):
                for i in s["ids"]:
                    self.cv.delete(i)
                self.shapes.remove(s)
                self.saved = False
                break

    def undo(self):
        if self.shapes:
            for i in self.shapes.pop()["ids"]:
                self.cv.delete(i)
            self.saved = False

    def clear(self):
        while self.shapes:
            self.undo()

    # ---------- output ----------
    def render(self):
        """Draw the shapes onto the screenshot with real transparency, cropped to the monitors used."""
        base = self.shot.convert("RGBA")
        hl = Image.new("RGBA", base.size, (0, 0, 0, 0))
        top = Image.new("RGBA", base.size, (0, 0, 0, 0))
        dh, dt = ImageDraw.Draw(hl), ImageDraw.Draw(top)
        for s in self.shapes:
            c, w, p = s["color"], s["size"], s["pts"]
            if s["type"] == "hl":
                dh.line(p, fill=c + "77", width=w * 4, joint="curve")
            elif s["type"] == "pen":
                dt.line(p, fill=c, width=w, joint="curve")
                for i in range(0, len(p), 2):
                    dt.ellipse([p[i] - w / 2, p[i + 1] - w / 2, p[i] + w / 2, p[i + 1] + w / 2], fill=c)
            elif s["type"] == "arrow":
                x0, y0, x1, y1 = p
                ang, head = math.atan2(y1 - y0, x1 - x0), w * 4 + 10
                dt.line([x0, y0, x1 - math.cos(ang) * head * .6, y1 - math.sin(ang) * head * .6], fill=c, width=w)
                dt.polygon([(x1, y1), (x1 - head * math.cos(ang - .45), y1 - head * math.sin(ang - .45)),
                            (x1 - head * math.cos(ang + .45), y1 - head * math.sin(ang + .45))], fill=c)
            elif s["type"] in ("rect", "oval"):
                box = [min(p[0], p[2]), min(p[1], p[3]), max(p[0], p[2]), max(p[1], p[3])]
                (dt.rectangle if s["type"] == "rect" else dt.ellipse)(box, outline=c, width=w)
            elif s["type"] == "text":
                try:
                    font = ImageFont.truetype("segoeuib.ttf", int(s["size"] * 1.35))
                except OSError:
                    font = ImageFont.load_default()
                dt.text((p[0], p[1]), s["text"], fill=c, font=font)
        img = Image.alpha_composite(Image.alpha_composite(base, hl), top)
        # crop to the monitors that have drawings (or the one under the mouse)
        used = []
        for (l, t, r, b) in self.mons:
            box = (l - self.L, t - self.T, r - self.L, b - self.T)
            if any(box[0] <= s["pts"][0] < box[2] and box[1] <= s["pts"][1] < box[3] for s in self.shapes):
                used.append(box)
        if not used:
            pt = wintypes.POINT()
            u32.GetCursorPos(ctypes.byref(pt))
            used = [next(((l - self.L, t - self.T, r - self.L, b - self.T) for (l, t, r, b) in self.mons
                          if l <= pt.x < r and t <= pt.y < b), (0, 0, self.W, self.H))]
        crop = (min(b[0] for b in used), min(b[1] for b in used), max(b[2] for b in used), max(b[3] for b in used))
        return img.crop(crop).convert("RGB")

    def save(self):
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
        from reminders import annotate_store
        path = annotate_store.new_path()
        self.render().save(path, "PNG")
        self.saved = True
        self.flash(f"Saved ✓  {path.name}  — find it in Daybook → Desktop")

    def copy(self):
        copy_to_clipboard(self.render())
        self.flash("Copied ✓ — paste it anywhere (Ctrl+V)")

    def escape(self):
        if self.shapes and not self.saved and not getattr(self, "_warned", False):
            self._warned = True
            self.status.configure(text="Not saved — press Esc again to discard, or Save / Copy", fg="#ffbe5c")
            return
        self.close()

    def close(self):
        self.root.destroy()
        if self.hidden:
            u32.ShowWindow(self.hidden, 9)

    def run(self):
        self.root.mainloop()


def main(hide_daybook=False):
    hwnd = None
    if hide_daybook:
        from reminders import appwin
        hwnd = appwin.find_window()
    Annotator(hwnd).run()
