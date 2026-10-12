"""Tk windows: the reminder pop-up, the agenda (calendar) window and the quick-add box."""
import ctypes
import tkinter as tk
import winsound
from datetime import datetime, timedelta

from . import db, nlp

BG, CARD, FG, MUTED, ACCENT, OK, WARN = "#16181d", "#20232b", "#f2f3f5", "#9aa0ab", "#7c9cff", "#3ecf8e", "#ffb454"
FONT = "Segoe UI"
NAG_EVERY_MS = 5 * 60 * 1000   # ring again every 5 min until you act
NAG_MAX = 12                   # ...for up to an hour

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


def _btn(parent, text, cmd, color=CARD, fg=FG):
    b = tk.Button(parent, text=text, command=cmd, bg=color, fg=fg, activebackground=ACCENT,
                  activeforeground="#000", relief="flat", font=(FONT, 10), padx=10, pady=4, cursor="hand2", bd=0)
    return b


def _snooze_targets(now):
    tonight = now.replace(hour=20, minute=0)
    if tonight <= now + timedelta(minutes=30):
        tonight = None
    tomorrow = (now + timedelta(days=1)).replace(hour=9, minute=0)
    opts = [("10 min", now + timedelta(minutes=10)), ("1 hour", now + timedelta(hours=1))]
    if tonight:
        opts.append(("Tonight 8 PM", tonight))
    opts.append(("Tomorrow 9 AM", tomorrow))
    return opts


class ReminderPopup(tk.Toplevel):
    """Stays on top and keeps ringing until Done or Snooze — the 'can't miss it' behaviour."""

    def __init__(self, master, row, slot, on_close):
        super().__init__(master)
        self.rid, self.on_close, self.nags = row["id"], on_close, 0
        self.title("Reminder")
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: self._snooze(datetime.now() + timedelta(minutes=10)))

        due = db.parse_dt(row["due"])
        late = datetime.now() - due
        when = due.strftime("%a %b %d, %I:%M %p").replace(" 0", " ")
        if late > timedelta(minutes=5):
            mins = int(late.total_seconds() // 60)
            when += f"  ·  missed by {mins // 60}h {mins % 60}m" if mins >= 60 else f"  ·  missed by {mins}m"

        tk.Label(self, text="⏰  REMINDER" + ("  ·  IMPORTANT" if row["priority"] else ""), bg=BG,
                 fg=WARN if row["priority"] else ACCENT, font=(FONT, 9, "bold")).pack(anchor="w", padx=18, pady=(14, 0))
        tk.Label(self, text=row["text"], bg=BG, fg=FG, font=(FONT, 15, "bold"), wraplength=380,
                 justify="left").pack(anchor="w", padx=18, pady=(4, 0))
        if row["notes"]:
            tk.Label(self, text=row["notes"], bg=BG, fg=MUTED, font=(FONT, 10), wraplength=380,
                     justify="left").pack(anchor="w", padx=18)
        rep = f"   ·   repeats {row['repeat']}" if row["repeat"] else ""
        tk.Label(self, text=when + rep, bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=18, pady=(2, 10))

        row1 = tk.Frame(self, bg=BG)
        row1.pack(fill="x", padx=18)
        _btn(row1, "✓  Done", self._done, OK, "#000").pack(side="left")
        tk.Label(row1, text="  Snooze:", bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left")
        for label, until in _snooze_targets(datetime.now()):
            _btn(row1, label, lambda u=until: self._snooze(u)).pack(side="left", padx=(4, 0))

        row2 = tk.Frame(self, bg=BG)
        row2.pack(fill="x", padx=18, pady=(8, 14))
        self.custom = tk.Entry(row2, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=(FONT, 10), width=26)
        self.custom.insert(0, "or type: in 3 hours / friday 2pm")
        self.custom.bind("<FocusIn>", lambda e: self.custom.delete(0, "end"))
        self.custom.bind("<Return>", lambda e: self._snooze_custom())
        self.custom.pack(side="left", ipady=4)
        _btn(row2, "Snooze", self._snooze_custom).pack(side="left", padx=(4, 0))

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{sw - w - 24}+{max(10, sh - h - 70 - slot * (h + 12))}")
        self._ring()

    def _ring(self):
        if not self.winfo_exists():
            return
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.nags += 1
        if self.nags < NAG_MAX:
            self.after(NAG_EVERY_MS, self._ring)

    def _done(self):
        db.complete(self.rid)
        self._close()

    def _snooze(self, until):
        db.snooze(self.rid, until)
        self._close()

    def _snooze_custom(self):
        text = self.custom.get().strip()
        if not text:
            return
        try:
            until = nlp.when(text)
        except Exception:
            until = datetime.now() + timedelta(minutes=10)
        self._snooze(until)

    def _close(self):
        self.on_close(self.rid)
        self.destroy()


class AgendaWindow(tk.Toplevel):
    """Calendar-style list: overdue + the next 14 days grouped by day, with Done / Delete."""

    def __init__(self, master, title="Your agenda"):
        super().__init__(master)
        self.title(title)
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.geometry("520x560")
        self.after(1500, lambda: self.attributes("-topmost", False))
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=16, pady=12)
        self.render()

    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        now = datetime.now()
        head = tk.Frame(self.body, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text=now.strftime("%A, %B %d").replace(" 0", " "), bg=BG, fg=FG,
                 font=(FONT, 16, "bold")).pack(side="left")
        _btn(head, "Open Daybook ↗", lambda: __import__("webbrowser").open("http://localhost:8503")).pack(side="right")
        rows = db.list_open(until=now + timedelta(days=14))
        if not rows:
            tk.Label(self.body, text="Nothing scheduled in the next 2 weeks. 🎉", bg=BG, fg=MUTED,
                     font=(FONT, 11)).pack(anchor="w", pady=20)
        canvas = tk.Canvas(self.body, bg=BG, highlightthickness=0)
        frame = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-e.delta // 120, "units"))
        canvas.pack(fill="both", expand=True, pady=(8, 0))
        last_day = None
        for r in rows:
            due = db.parse_dt(r["due"])
            day = "Overdue" if due < now else ("Today" if due.date() == now.date() else
                  "Tomorrow" if due.date() == (now + timedelta(days=1)).date() else due.strftime("%A %b %d").replace(" 0", " "))
            if day != last_day:
                tk.Label(frame, text=day.upper(), bg=BG, fg=WARN if day == "Overdue" else ACCENT,
                         font=(FONT, 9, "bold")).pack(anchor="w", pady=(10, 2))
                last_day = day
            card = tk.Frame(frame, bg=CARD)
            card.pack(fill="x", pady=2)
            ends = "–" + datetime.strptime(r["ends"], "%H:%M").strftime("%I:%M %p").lstrip("0") if r["ends"] else ""
            txt = due.strftime("%I:%M %p").lstrip("0") + ends + "   " + r["text"] + ("   ↻" if r["repeat"] else "")
            tk.Label(card, text=txt, bg=CARD, fg=FG, font=(FONT, 10), anchor="w", width=40,
                     wraplength=330, justify="left").pack(side="left", padx=8, pady=6)
            _btn(card, "✕", lambda i=r["id"]: (db.delete(i), self.render())).pack(side="right", padx=(0, 6))
            _btn(card, "✓", lambda i=r["id"]: (db.complete(i), self.render()), OK, "#000").pack(side="right", padx=4)


class QuickNote(tk.Toplevel):
    """Ctrl+Alt+N: one line straight into today's daily log (the AI tags it later)."""

    def __init__(self, master, on_exit=None):
        super().__init__(master)
        from . import notes
        self.notes = notes
        self.title("Quick note")
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        tk.Label(self, text="Note to today's log", bg=BG, fg=MUTED, font=(FONT, 10)).pack(anchor="w", padx=16, pady=(12, 2))
        self.entry = tk.Entry(self, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=(FONT, 14), width=44)
        self.entry.pack(padx=16, ipady=6)
        self.status = tk.Label(self, text="Enter = save · keep typing more · Esc = close", bg=BG, fg=MUTED, font=(FONT, 9))
        self.status.pack(anchor="w", padx=16, pady=(6, 12))
        self.entry.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        self.geometry(f"+{(self.winfo_screenwidth() - self.winfo_reqwidth()) // 2}+{self.winfo_screenheight() // 3}")
        self.after(50, lambda: (self.lift(), self.focus_force(), self.entry.focus_set()))

    def save(self):
        text = self.entry.get().strip()
        if text:
            self.notes.append_to_log(text)
            self.status.config(text=f"✓ Logged: {text[:60]}", fg=OK)
            self.entry.delete(0, "end")


class QuickAdd(tk.Toplevel):
    """Type a reminder in plain English. Enter = save. 'agenda' = open the agenda."""

    def __init__(self, master, on_exit=None):
        super().__init__(master)
        self.on_exit = on_exit
        self.title("New reminder")
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        tk.Label(self, text="Remind me to…", bg=BG, fg=MUTED, font=(FONT, 10)).pack(anchor="w", padx=16, pady=(12, 2))
        self.entry = tk.Entry(self, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=(FONT, 14), width=38)
        self.entry.pack(padx=16, ipady=6)
        self.status = tk.Label(self, text="e.g.  call mom sunday 5pm  ·  take meds every day at 9am  ·  type 'agenda'",
                               bg=BG, fg=MUTED, font=(FONT, 9), wraplength=440, justify="left")
        self.status.pack(anchor="w", padx=16, pady=(6, 12))
        self.entry.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.update_idletasks()
        self.geometry(f"+{(self.winfo_screenwidth() - self.winfo_reqwidth()) // 2}+{self.winfo_screenheight() // 3}")
        self.after(50, self._focus)
        self.last_id = None

    def _focus(self):
        self.lift()
        self.focus_force()
        self.entry.focus_set()

    def save(self):
        text = self.entry.get().strip()
        if not text:
            return
        if text.lower() in ("agenda", "list", "calendar"):
            AgendaWindow(self.master)
            return self.close()
        if text.lower() == "undo" and self.last_id:
            db.delete(self.last_id)
            self.status.config(text="Removed.", fg=MUTED)
            self.entry.delete(0, "end")
            return
        self.status.config(text="Thinking…", fg=MUTED)
        self.update()
        p = nlp.parse(text)
        self.last_id = db.add(p["text"], p["due"], p["repeat"], p["priority"])
        when = p["due"].strftime("%a %b %d at %I:%M %p").replace(" 0", " ")
        extra = f", repeats {p['repeat']}" if p["repeat"] else ""
        guess = "  (no time given — picked tomorrow 9 AM)" if p.get("guessed_time") else ""
        self.status.config(text=f"✓  {p['text']} — {when}{extra}{guess}\nType another, 'undo', or Esc to close.", fg=OK)
        self.entry.delete(0, "end")

    def close(self):
        self.destroy()
        if self.on_exit:
            self.on_exit()
