"""Ringing alarms/timers on the desktop: a big always-on-top card with a looping sound.
Polled every second from the daemon's Tk loop; stopping from the Daybook window closes it here too."""
import tkinter as tk
import winsound
from datetime import datetime

from . import clock, ui

RING_LIMIT_S = 15 * 60  # stop ringing on its own after 15 minutes, like a phone


class RingWindow(tk.Toplevel):
    def __init__(self, ringer, kind, rid, label, snooze, slot):
        super().__init__(ringer.root)
        self.ringer, self.key, self.started = ringer, (kind, rid), datetime.now()
        self.title("Alarm" if kind == "alarm" else "Timer")
        self.configure(bg=ui.BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.stop)
        tk.Label(self, text=("⏰  ALARM" if kind == "alarm" else "⏱  TIMER DONE"), bg=ui.BG, fg=ui.ACCENT,
                 font=(ui.FONT, 10, "bold")).pack(anchor="w", padx=22, pady=(18, 0))
        tk.Label(self, text=datetime.now().strftime("%I:%M %p").lstrip("0"), bg=ui.BG, fg=ui.FG,
                 font=(ui.FONT, 34, "bold")).pack(anchor="w", padx=20)
        tk.Label(self, text=label, bg=ui.BG, fg=ui.FG, font=(ui.FONT, 13), wraplength=340, justify="left").pack(anchor="w", padx=22)
        row = tk.Frame(self, bg=ui.BG)
        row.pack(fill="x", padx=20, pady=(16, 18))
        ui._btn(row, "Stop", self.stop, ui.ACCENT, "#000").pack(side="left")
        if kind == "alarm" and snooze:
            ui._btn(row, "Snooze 9 min", lambda: self.stop(9)).pack(side="left", padx=8)
        if kind == "timer":
            ui._btn(row, "+1 min", lambda: self._timer("add")).pack(side="left", padx=8)
            ui._btn(row, "Repeat", lambda: self._timer("repeat")).pack(side="left")
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        self.geometry(f"+{sw - self.winfo_width() - 30}+{40 + slot * 200}")
        self.lift()
        ui.calm(self)  # already topmost; asking for focus from the background only flashes the taskbar

    def _timer(self, action):
        clock.timer_action(self.key[1], action)
        self.close()

    def stop(self, snooze_min=0):
        clock.stop(*self.key, snooze_min=snooze_min)
        self.close()

    def close(self):
        self.ringer.windows.pop(self.key, None)
        self.destroy()
        self.ringer.update_sound()


class Ringer:
    def __init__(self, root):
        self.root, self.windows, self.playing = root, {}, None
        clock.ensure_sounds()
        root.after(1500, self.tick)

    def tick(self):
        try:
            ringing = {(k, i): (lbl, snd, sn) for k, i, lbl, snd, sn in clock.due()}
            for key, (lbl, snd, sn) in ringing.items():
                if key not in self.windows:
                    slot = next(s for s in range(10) if s not in {w.slot for w in self.windows.values()})
                    w = RingWindow(self, key[0], key[1], lbl, sn, slot)
                    w.slot, w.sound = slot, snd
                    self.windows[key] = w
            for key, w in list(self.windows.items()):
                if key not in ringing:  # stopped from the Daybook window
                    w.close()
                elif (datetime.now() - w.started).total_seconds() > RING_LIMIT_S:
                    w.stop()
            self.update_sound()
        except Exception as e:  # log, never crash the service
            with open(clock.SOUND_DIR.parent / "daemon.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} clock: {e!r}\n")
        self.root.after(1000, self.tick)

    def update_sound(self):
        want = next(iter(self.windows.values())).sound if self.windows else None
        if want == self.playing:
            return
        self.playing = want
        if want:
            winsound.PlaySound(str(clock.SOUND_DIR / f"{want}.wav"),
                               winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
        else:
            winsound.PlaySound(None, 0)
