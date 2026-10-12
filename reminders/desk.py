"""Desktop sticky notes: borderless windows with no taskbar button. Each note lives either on the
desktop layer (behind every app, never in the way) or pinned on top. Text autosaves to SQLite."""
import ctypes
import queue
import tkinter as tk
from datetime import datetime

from . import db

COLORS = {  # name: (paper, header, text)
    "lemon": ("#fff3a8", "#ffe566", "#3b3410"), "peach": ("#ffd6b8", "#ffbe8f", "#43260f"),
    "rose": ("#ffc7dd", "#ffa3c7", "#4a1630"), "lilac": ("#e2d4ff", "#ccb5ff", "#2c1d52"),
    "sky": ("#c9e9ff", "#9fd6ff", "#0f2f47"), "mint": ("#c8f5dc", "#9becc0", "#0f3a24"),
    "night": ("#22252f", "#2f3341", "#e9ebf2"),
}
FONT = "Segoe UI"
COMMANDS = queue.Queue()  # web thread → Tk thread ("new"|"show"|"close"|"reload", id)
HWND_BOTTOM, HWND_TOPMOST, HWND_NOTOPMOST = 1, -1, -2
u32 = ctypes.windll.user32


def _con():
    con = db.connect()
    con.execute("""CREATE TABLE IF NOT EXISTS stickies (id INTEGER PRIMARY KEY, text TEXT NOT NULL DEFAULT '',
        color TEXT NOT NULL DEFAULT 'lemon', x INTEGER, y INTEGER, w INTEGER NOT NULL DEFAULT 260, h INTEGER NOT NULL DEFAULT 220,
        mode TEXT NOT NULL DEFAULT 'desktop', collapsed INTEGER NOT NULL DEFAULT 0, closed INTEGER NOT NULL DEFAULT 0,
        created TEXT NOT NULL, updated TEXT NOT NULL)""")
    return con


def _now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def create(text="", color="lemon", x=None, y=None):
    with _con() as con:
        cur = con.execute("INSERT INTO stickies (text, color, x, y, created, updated) VALUES (?,?,?,?,?,?)",
                          (text, color if color in COLORS else "lemon", x, y, _now(), _now()))
        return cur.lastrowid


def get(sid):
    with _con() as con:
        r = con.execute("SELECT * FROM stickies WHERE id=?", (sid,)).fetchone()
        return dict(r) if r else None


def all_notes(include_closed=False):
    with _con() as con:
        q = "SELECT * FROM stickies" + ("" if include_closed else " WHERE closed=0") + " ORDER BY updated DESC"
        return [dict(r) for r in con.execute(q)]


def update(sid, **f):
    f = {k: v for k, v in f.items() if k in ("text", "color", "x", "y", "w", "h", "mode", "collapsed", "closed")}
    if f:
        f["updated"] = _now()
        with _con() as con:
            con.execute(f"UPDATE stickies SET {', '.join(k + '=?' for k in f)} WHERE id=?", (*f.values(), sid))


def delete_forever(sid):
    with _con() as con:
        con.execute("DELETE FROM stickies WHERE id=?", (sid,))


# ---------------- windows ----------------

class Sticky(tk.Toplevel):
    def __init__(self, mgr, row):
        super().__init__(mgr.root)
        self.mgr, self.sid = mgr, row["id"]
        self.mode, self.collapsed, self.color = row["mode"], bool(row["collapsed"]), row["color"]
        self.w, self.h = row["w"], row["h"]
        self.overrideredirect(True)  # no title bar, no taskbar button, not in Alt+Tab
        self.configure(bg="#000")
        self.attributes("-alpha", 0.97)

        paper, head, ink = COLORS.get(self.color, COLORS["lemon"])
        self.head = tk.Frame(self, height=26, cursor="fleur")
        self.head.pack(fill="x")
        self.dot = tk.Label(self.head, text="●", font=(FONT, 9), cursor="hand2")
        self.dot.pack(side="left", padx=(8, 2))
        self.title_lbl = tk.Label(self.head, text="", font=(FONT, 8, "bold"))
        self.title_lbl.pack(side="left")
        self.btns = {}
        for key, sym, tip in (("close", "✕", "Close note"), ("collapse", "–", "Collapse"),
                              ("pin", "📌", "Pin on top / send to desktop"), ("new", "＋", "New note")):
            b = tk.Label(self.head, text=sym, font=(FONT, 10), cursor="hand2", padx=5)
            b.pack(side="right")
            b.bind("<Button-1>", lambda e, k=key: self.action(k))
            self.btns[key] = b
        self.text = tk.Text(self, wrap="word", relief="flat", bd=0, padx=10, pady=8, font=(FONT, 11),
                            undo=True, highlightthickness=0)
        self.text.insert("1.0", row["text"])
        self.text.pack(fill="both", expand=True)
        self.grip = tk.Label(self, text="◢", font=(FONT, 8), cursor="size_nw_se")
        self.grip.place(relx=1, rely=1, anchor="se")

        for w in (self.head, self.title_lbl):
            w.bind("<ButtonPress-1>", self._start_move)
            w.bind("<B1-Motion>", self._move)
            w.bind("<ButtonRelease-1>", self._save_geom)
            w.bind("<Double-Button-1>", lambda e: self.action("collapse"))
        self.dot.bind("<Button-1>", self._color_menu)
        self.head.bind("<Button-3>", self._color_menu)
        self.grip.bind("<ButtonPress-1>", self._start_move)
        self.grip.bind("<B1-Motion>", self._resize)
        self.grip.bind("<ButtonRelease-1>", self._save_geom)
        self.text.bind("<<Modified>>", self._changed)
        self.text.bind("<Button-1>", lambda e: (self.focus_force(), self.text.focus_set()))
        self.text.bind("<Escape>", lambda e: self.mgr.root.focus())

        x = row["x"] if row["x"] is not None else mgr.next_pos()[0]
        y = row["y"] if row["y"] is not None else mgr.next_pos()[1]
        self.geometry(f"{self.w}x{26 if self.collapsed else self.h}+{x}+{y}")
        if row["x"] is None:
            update(self.sid, x=x, y=y)
        self.paint()
        self.after(60, self.apply_layer)

    # --- look ---
    def paint(self):
        paper, head, ink = COLORS.get(self.color, COLORS["lemon"])
        self.head.configure(bg=head)
        for w in (self.dot, self.title_lbl, *self.btns.values()):
            w.configure(bg=head, fg=ink)
        self.text.configure(bg=paper, fg=ink, insertbackground=ink, selectbackground=head)
        self.grip.configure(bg=paper, fg=head)
        self.btns["pin"].configure(text="📌" if self.mode == "top" else "⇣", fg=ink)
        first = self.text.get("1.0", "1.end").strip()
        self.title_lbl.configure(text=(first[:28] + "…" if len(first) > 28 else first) if self.collapsed else "")

    def apply_layer(self):
        """Desktop mode: sit under every app window. Top mode: float above everything."""
        try:
            hwnd = int(self.wm_frame(), 16)
            if self.mode == "top":
                u32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, 0x0013)  # NOSIZE|NOMOVE|NOACTIVATE
            else:
                u32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, 0x0013)
                u32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, 0x0013)
        except Exception:
            pass

    # --- actions ---
    def action(self, key):
        if key == "new":
            self.mgr.new_note(near=self)
        elif key == "pin":
            self.mode = "desktop" if self.mode == "top" else "top"
            update(self.sid, mode=self.mode)
            self.paint()
            self.apply_layer()
        elif key == "collapse":
            self.collapsed = not self.collapsed
            update(self.sid, collapsed=int(self.collapsed))
            self.geometry(f"{self.w}x{26 if self.collapsed else self.h}")
            self.paint()
        elif key == "close":
            self._flush()
            update(self.sid, closed=1)  # recoverable from Daybook → Desktop
            self.mgr.windows.pop(self.sid, None)
            self.destroy()

    def _color_menu(self, e):
        m = tk.Menu(self, tearoff=0)
        for name in COLORS:
            m.add_command(label=name.title(), command=lambda n=name: self._set_color(n))
        m.tk_popup(e.x_root, e.y_root)

    def _set_color(self, n):
        self.color = n
        update(self.sid, color=n)
        self.paint()

    # --- move / resize / save ---
    def _start_move(self, e):
        self._sx, self._sy = e.x_root, e.y_root
        self._gx, self._gy, self._gw, self._gh = self.winfo_x(), self.winfo_y(), self.winfo_width(), self.winfo_height()

    def _move(self, e):
        self.geometry(f"+{self._gx + e.x_root - self._sx}+{self._gy + e.y_root - self._sy}")

    def _resize(self, e):
        self.w = max(160, self._gw + e.x_root - self._sx)
        self.h = max(90, self._gh + e.y_root - self._sy)
        self.collapsed = False
        self.geometry(f"{self.w}x{self.h}")

    def _save_geom(self, e=None):
        update(self.sid, x=self.winfo_x(), y=self.winfo_y(), w=self.w, h=self.h, collapsed=int(self.collapsed))
        self.apply_layer()

    def _changed(self, e=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            if getattr(self, "_pending", None):
                self.after_cancel(self._pending)
            self._pending = self.after(700, self._flush)

    def _flush(self):
        self._pending = None
        update(self.sid, text=self.text.get("1.0", "end-1c"))
        if self.collapsed:
            self.paint()


class Manager:
    def __init__(self, root):
        self.root, self.windows = root, {}
        for row in all_notes():
            self.open(row)
        root.after(300, self.pump)
        root.after(3000, self.keep_layers)

    def open(self, row):
        if row["id"] in self.windows:
            w = self.windows[row["id"]]
            w.deiconify()
            w.lift()
            return w
        w = Sticky(self, row)
        self.windows[row["id"]] = w
        return w

    def next_pos(self):
        n = len(self.windows)
        sw = self.root.winfo_screenwidth()
        return sw - 300 - (n % 5) * 30, 120 + (n % 5) * 30

    def new_note(self, near=None, text="", color=None):
        x = y = None
        if near is not None:
            x, y = near.winfo_x() + 30, near.winfo_y() + 30
        sid = create(text, color or (near.color if near else "lemon"), x, y)
        w = self.open(get(sid))
        w.after(80, lambda: (w.focus_force(), w.text.focus_set()))
        return sid

    def pump(self):
        try:
            while True:
                cmd, sid = COMMANDS.get_nowait()
                row = get(sid) if sid else None
                if cmd == "new":
                    w = self.open(row)
                    w.after(80, lambda w=w: (w.focus_force(), w.text.focus_set()))
                elif cmd == "show" and row:
                    update(sid, closed=0)
                    w = self.open(get(sid))
                    w.mode = "top"  # bring it into view once
                    w.apply_layer()
                    w.mode = row["mode"]
                    w.after(1500, w.apply_layer)
                elif cmd == "close" and sid in self.windows:
                    self.windows[sid].action("close")
                elif cmd == "reload" and row and sid in self.windows:
                    w = self.windows[sid]
                    w.color, w.mode = row["color"], row["mode"]
                    w.text.delete("1.0", "end")
                    w.text.insert("1.0", row["text"])
                    w.text.edit_modified(False)
                    w.paint()
                    w.apply_layer()
        except queue.Empty:
            pass
        self.root.after(300, self.pump)

    def keep_layers(self):
        """Desktop-mode notes drift up when clicked — quietly push them back under the apps."""
        focused = self.root.focus_get()
        for w in list(self.windows.values()):
            try:
                if w.mode != "top" and (focused is None or focused.winfo_toplevel() is not w):
                    w.apply_layer()
            except Exception:
                pass
        self.root.after(4000, self.keep_layers)
