"""Desktop sticky notes: borderless windows with no taskbar button. Each note lives either on the
desktop layer (behind every app, never in the way) or pinned on top. Text autosaves to SQLite."""
import ctypes
import os
import queue
import re
import tkinter as tk
from datetime import datetime
from pathlib import Path

from . import db, paths

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
from ctypes import wintypes as _wt  # noqa: E402
# Declare HWND-sized arguments: passing -1 (HWND_TOPMOST) as a plain int is misread on 64-bit Windows.
u32.SetWindowPos.argtypes = [_wt.HWND, _wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
u32.SetWindowPos.restype = _wt.BOOL
IMG_DIR = paths.DATA / "sticky_images"
IMG_RE = re.compile(r"\[\[img:([^\]]+)\]\]")  # pasted pictures are stored in the text as [[img:file.png]]
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def _con():
    con = db.connect()
    con.execute("""CREATE TABLE IF NOT EXISTS stickies (id INTEGER PRIMARY KEY, text TEXT NOT NULL DEFAULT '',
        color TEXT NOT NULL DEFAULT 'lemon', x INTEGER, y INTEGER, w INTEGER NOT NULL DEFAULT 260, h INTEGER NOT NULL DEFAULT 220,
        mode TEXT NOT NULL DEFAULT 'top', collapsed INTEGER NOT NULL DEFAULT 0, closed INTEGER NOT NULL DEFAULT 0,
        created TEXT NOT NULL, updated TEXT NOT NULL)""")
    return con


def _now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def create(text="", color="lemon", x=None, y=None, mode="top"):
    with _con() as con:
        cur = con.execute("INSERT INTO stickies (text, color, x, y, mode, created, updated) VALUES (?,?,?,?,?,?,?)",
                          (text, color if color in COLORS else "lemon", x, y, mode if mode in ("top", "desktop") else "top", _now(), _now()))
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


def images_in(text):
    return IMG_RE.findall(text or "")


def preview(text):
    return IMG_RE.sub("🖼", text or "")


def delete_forever(sid):
    row = get(sid)
    for f in images_in(row["text"] if row else ""):
        try:
            (IMG_DIR / Path(f).name).unlink()
        except OSError:
            pass
    with _con() as con:
        con.execute("DELETE FROM stickies WHERE id=?", (sid,))


# ---------------- windows ----------------

def force_foreground(hwnd):
    """Windows only lets the active app hand out focus; borrow the active thread's input so a note can take it."""
    k32 = ctypes.windll.kernel32
    fg = u32.GetForegroundWindow()
    fg_tid = u32.GetWindowThreadProcessId(fg, None) if fg else 0
    me = k32.GetCurrentThreadId()
    if fg_tid and fg_tid != me:
        u32.AttachThreadInput(me, fg_tid, True)
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    if fg_tid and fg_tid != me:
        u32.AttachThreadInput(me, fg_tid, False)


class Tip:
    def __init__(self, widget, text):
        self.w, self.text, self.tw = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _e=None):
        if self.tw or not self.text:
            return
        x, y = self.w.winfo_rootx() + 4, self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tw = tk.Toplevel(self.w)
        self.tw.overrideredirect(True)
        self.tw.attributes("-topmost", True)
        tk.Label(self.tw, text=self.text, bg="#20232b", fg="#eceef4", font=(FONT, 9), padx=7, pady=3).pack()
        self.tw.geometry(f"+{x}+{y}")

    def hide(self, _e=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None

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
        for key, sym, tip in (("close", "✕", "Close (restore it from Daybook → Desktop)"), ("collapse", "–", "Collapse / expand"),
                              ("pin", "📌", ""), ("new", "＋", "New note")):
            b = tk.Label(self.head, text=sym, font=(FONT, 10), cursor="hand2", padx=5)
            b.pack(side="right")
            b.bind("<Button-1>", lambda e, k=key: self.action(k))
            self.btns[key] = b
            b._tip = Tip(b, tip)
        self.text = tk.Text(self, wrap="word", relief="flat", bd=0, padx=10, pady=8, font=(FONT, 11),
                            undo=True, highlightthickness=0)
        self.photos, self.imgfiles = [], {}  # Tk image name → file in IMG_DIR
        self.load_text(row["text"])
        self.text.pack(fill="both", expand=True)
        self.grip = tk.Label(self, text="◢", font=(FONT, 8), cursor="size_nw_se")
        self.grip.place(relx=1, rely=1, anchor="se")

        for w in (self.head, self.title_lbl):
            w.bind("<ButtonPress-1>", self._start_move)
            w.bind("<B1-Motion>", self._move)
            w.bind("<ButtonRelease-1>", self._save_geom)
            w.bind("<Double-Button-1>", lambda e: self.action("collapse"))
        Tip(self.dot, "Color & options")
        self.dot.bind("<Button-1>", self._color_menu)
        self.head.bind("<Button-3>", self._color_menu)
        self.grip.bind("<ButtonPress-1>", self._start_move)
        self.grip.bind("<B1-Motion>", self._resize)
        self.grip.bind("<ButtonRelease-1>", self._save_geom)
        self.text.bind("<<Modified>>", self._changed)
        self.text.bind("<Button-1>", lambda e: self.take_focus(), add="+")
        self.bind("<FocusOut>", lambda e: self.after(400, self._settle))
        self.text.bind("<Escape>", lambda e: self.mgr.root.focus())
        for seq in ("<Control-v>", "<Control-V>", "<Shift-Insert>"):
            self.text.bind(seq, self._paste)
        self.text.tag_bind("img", "<Double-Button-1>", self._open_image)
        self.text.tag_bind("img", "<Enter>", lambda e: self.text.configure(cursor="hand2"))
        self.text.tag_bind("img", "<Leave>", lambda e: self.text.configure(cursor="xterm"))

        x = row["x"] if row["x"] is not None else mgr.next_pos()[0]
        y = row["y"] if row["y"] is not None else mgr.next_pos()[1]
        self.update_idletasks()
        self.geometry(f"{self.w}x{self.head_h() if self.collapsed else self.h}+{x}+{y}")
        if row["x"] is None:
            update(self.sid, x=x, y=y)
        self.paint()
        self.update_idletasks()
        self.apply_layer()  # right away, so a new note never flickers behind your windows
        self.after(60, self.apply_layer)

    # --- text + pictures ---
    def load_text(self, raw):
        self.text.delete("1.0", "end")
        self.photos.clear()
        self.imgfiles.clear()
        pos = 0
        for m in IMG_RE.finditer(raw or ""):
            self.text.insert("end", raw[pos:m.start()])
            self.insert_image(m.group(1), "end")
            pos = m.end()
        self.text.insert("end", (raw or "")[pos:])
        self.text.edit_modified(False)
        self.text.edit_reset()

    def serialize(self):
        out = []
        for kind, value, _ in self.text.dump("1.0", "end-1c", text=True, image=True):
            if kind == "text":
                out.append(value)
            elif kind == "image" and value in self.imgfiles:
                out.append(f"[[img:{self.imgfiles[value]}]]")
        return "".join(out)

    def insert_image(self, fname, index="insert"):
        from PIL import Image, ImageTk
        try:
            im = Image.open(IMG_DIR / Path(fname).name)
            im.load()
        except Exception:
            self.text.insert(index, "[missing picture]")
            return
        maxw = max(120, self.w - 34)
        if im.width > maxw:
            im = im.resize((maxw, max(1, round(im.height * maxw / im.width))), Image.LANCZOS)
        photo = ImageTk.PhotoImage(im, master=self)
        name = self.text.image_create(index, image=photo, padx=1, pady=4)
        self.text.tag_add("img", name)
        self.photos.append(photo)
        self.imgfiles[name] = Path(fname).name

    def _paste(self, e=None):
        """Ctrl+V: a copied picture (screenshot, Snipping Tool, image file from Explorer) goes into the note."""
        from PIL import Image, ImageGrab
        try:
            clip = ImageGrab.grabclipboard()
        except Exception:
            clip = None
        imgs = []
        if isinstance(clip, Image.Image):
            imgs = [clip]
        elif isinstance(clip, list):
            for f in clip:
                if Path(f).suffix.lower() in IMG_EXT:
                    try:
                        imgs.append(Image.open(f))
                    except Exception:
                        pass
        if not imgs:
            return None  # plain text: let Tk paste normally
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            self.text.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for i, im in enumerate(imgs):
            fname = f"sticky{self.sid}_{stamp}_{i}.png"
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA")
            im.save(IMG_DIR / fname)
            if self.text.compare("insert", "!=", "insert linestart"):
                self.text.insert("insert", "\n")
            self.insert_image(fname)
            self.text.insert("insert", "\n")
        self.text.see("insert")
        self._changed()
        return "break"

    def _open_image(self, e):
        idx = self.text.index(f"@{e.x},{e.y}")
        for kind, value, _ in self.text.dump(idx, f"{idx}+1c", image=True):
            if kind == "image" and value in self.imgfiles:
                os.startfile(IMG_DIR / self.imgfiles[value])  # full size in the Photos app
                return "break"

    def head_h(self):
        return max(26, self.head.winfo_reqheight())

    def take_focus(self):
        """Click/new note: bring it forward and put the cursor in it (works even when Daybook isn't the active app)."""
        try:
            force_foreground(int(self.wm_frame(), 16))
        except Exception:
            pass
        self.lift()
        self.text.focus_set()

    def _settle(self):
        """When you leave a desktop-layer note it slips back under your apps."""
        try:
            if self.mode != "top" and not self.mgr.peeking and self.focus_get() is None:
                self.apply_layer()
        except Exception:
            pass

    # --- look ---
    def paint(self):
        paper, head, ink = COLORS.get(self.color, COLORS["lemon"])
        self.head.configure(bg=head)
        for w in (self.dot, self.title_lbl, *self.btns.values()):
            w.configure(bg=head, fg=ink)
        self.text.configure(bg=paper, fg=ink, insertbackground=ink, selectbackground=head)
        self.grip.configure(bg=paper, fg=head)
        self.btns["pin"].configure(text="📌" if self.mode == "top" else "⇩", fg=ink)
        self.btns["pin"]._tip.text = "Pinned on top — click to tuck it under your apps" if self.mode == "top" else "On the desktop layer — click to pin it on top"
        if self.collapsed:
            self.grip.place_forget()
        else:
            self.grip.place(relx=1, rely=1, anchor="se")
        first = preview(self.text.get("1.0", "1.end")).strip() or ("🖼 picture" if self.imgfiles else "")
        self.title_lbl.configure(text=(first[:28] + "…" if len(first) > 28 else first) if self.collapsed else "")

    def apply_layer(self):
        """Desktop mode: sit under every app window. Top mode: float above everything."""
        try:
            hwnd = int(self.wm_frame(), 16)
            if self.mode == "top" or self.mgr.peeking:
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
            self.geometry(f"{self.w}x{self.head_h() if self.collapsed else self.h}")
            self.paint()
        elif key == "close":
            self._flush()
            update(self.sid, closed=1)  # recoverable from Daybook → Desktop
            self.mgr.windows.pop(self.sid, None)
            self.destroy()

    def _color_menu(self, e):
        m = tk.Menu(self, tearoff=0)
        for name in COLORS:
            m.add_command(label=("● " if name == self.color else "   ") + name.title(), command=lambda n=name: self._set_color(n))
        m.add_separator()
        m.add_command(label="Send to desktop layer" if self.mode == "top" else "Pin on top", command=lambda: self.action("pin"))
        m.add_command(label="Expand" if self.collapsed else "Collapse", command=lambda: self.action("collapse"))
        m.add_command(label="New note", command=lambda: self.action("new"))
        m.add_separator()
        m.add_command(label="Close note", command=lambda: self.action("close"))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

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
        if e is None or self.text.edit_modified():
            self.text.edit_modified(False)
            if getattr(self, "_pending", None):
                self.after_cancel(self._pending)
            self._pending = self.after(700, self._flush)

    def _flush(self):
        self._pending = None
        update(self.sid, text=self.serialize())
        if self.collapsed:
            self.paint()


class Manager:
    def __init__(self, root):
        self.root, self.windows, self.peeking = root, {}, False
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
        sid = create(text, color or (near.color if near else "lemon"), x, y, "top")
        w = self.open(get(sid))
        w.after(120, w.take_focus)
        return sid

    def pump(self):
        try:
            while True:
                cmd, sid = COMMANDS.get_nowait()
                row = get(sid) if sid else None
                if cmd == "new":
                    w = self.open(row)
                    w.after(120, w.take_focus)
                elif cmd == "show" and row:
                    update(sid, closed=0)
                    w = self.open(get(sid))
                    if w.collapsed:
                        w.action("collapse")
                    u32.SetWindowPos(int(w.wm_frame(), 16), HWND_TOPMOST, 0, 0, 0, 0, 0x0013)  # up front until you click away
                    w.after(150, w.take_focus)
                    if w.mode != "top":
                        u32.SetWindowPos(int(w.wm_frame(), 16), HWND_NOTOPMOST, 0, 0, 0, 0, 0x0013)
                elif cmd == "close" and sid in self.windows:
                    self.windows[sid].action("close")
                elif cmd == "peek":
                    self.peek()
                elif cmd == "reload" and row and sid in self.windows:
                    w = self.windows[sid]
                    w.color, w.mode = row["color"], row["mode"]
                    w.load_text(row["text"])
                    w.paint()
                    w.apply_layer()
        except queue.Empty:
            pass
        self.root.after(300, self.pump)

    def peek(self):
        """Ctrl+Alt+W: lift every note above your apps to read/edit/move them; press again to tuck them back."""
        self.peeking = not self.peeking and bool(self.windows)
        for w in list(self.windows.values()):
            try:
                w.deiconify()
                w.apply_layer()
            except Exception:
                pass
        if self.peeking:
            first = next(iter(self.windows.values()))
            first.after(80, first.focus_force)

    def keep_layers(self):
        """Desktop-mode notes drift up when clicked — quietly push them back under the apps."""
        try:
            focused = self.root.focus_get()
        except Exception:  # focus is in a menu/tooltip — Tk can't name it
            focused = None
        for w in list(self.windows.values()):
            try:
                if not self.peeking and w.mode != "top" and (focused is None or focused.winfo_toplevel() is not w):
                    w.apply_layer()
            except Exception:
                pass
        self.root.after(4000, self.keep_layers)  # always reschedule
