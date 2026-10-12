"""Where screen annotations are saved (kept on D:, never C:)."""
from datetime import datetime
from pathlib import Path

from . import db

DEFAULT = r"D:\Daybook\Annotations"


def folder():
    p = Path(db.setting("annotations_dir") or DEFAULT)
    p.mkdir(parents=True, exist_ok=True)
    return p


def new_path():
    return folder() / f"Annotation {datetime.now():%Y-%m-%d %H-%M-%S}.png"


def listing(limit=60):
    files = sorted(folder().glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [{"name": f.name, "size_kb": round(f.stat().st_size / 1024),
             "taken": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%dT%H:%M")} for f in files]
