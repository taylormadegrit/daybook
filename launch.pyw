"""Desktop / taskbar launcher: open Daybook, starting the background service first if it isn't running."""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reminders import appwin  # noqa: E402


def server_up():
    try:
        urllib.request.urlopen(appwin.URL + "api/settings", timeout=2)
        return True
    except Exception:
        return False


if not server_up():
    # same task that runs at sign-in; it serves the app and keeps the pop-ups going
    subprocess.run(["schtasks", "/run", "/tn", "LocalRemindersDaemon"], capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(40):
        if server_up():
            break
        time.sleep(0.5)

appwin.open_app("today")
