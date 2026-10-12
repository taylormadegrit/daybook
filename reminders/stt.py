"""Speech to text, fully local: faster-whisper (CPU, int8). Audio recorded in the Daybook window is
posted here, transcribed, and thrown away — nothing leaves this PC. Models download once to data/whisper."""
import tempfile
import threading
from pathlib import Path

from . import db

MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "whisper"
MODELS = {  # setting value → (label, size)
    "base.en": ("Fast — base (English)", "140 MB"),
    "small.en": ("Balanced — small (English)", "460 MB"),
    "medium.en": ("Accurate — medium (English, slower)", "1.5 GB"),
    "small": ("Multilingual — small (any language)", "460 MB"),
}
_lock = threading.Lock()
_model = {"name": None, "obj": None}
STATE = {"loading": False, "error": ""}


def downloaded(name):
    return any(MODEL_DIR.glob(f"models--Systran--faster-whisper-{name}/snapshots/*/model.bin"))


def _get():
    name = db.setting("stt_model") or "small.en"
    if name not in MODELS:
        name = "small.en"
    if _model["name"] != name:
        from faster_whisper import WhisperModel
        STATE["loading"] = True
        try:
            _model["obj"] = WhisperModel(name, device="cpu", compute_type="int8", download_root=str(MODEL_DIR),
                                         cpu_threads=8)
            _model["name"] = name
            STATE["error"] = ""
        except Exception as e:
            STATE["error"] = str(e)
            raise
        finally:
            STATE["loading"] = False
    return _model["obj"]


def preload():
    """Warm the model in the background so the first dictation is quick."""
    def run():
        with _lock:
            try:
                _get()
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()


def transcribe(data, suffix=".webm"):
    lang = db.setting("stt_language") or ""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        with _lock:
            model = _get()
            name = _model["name"]
            segs, info = model.transcribe(path, beam_size=5, vad_filter=True,
                                          language=None if name.endswith(".en") else (lang or None),
                                          condition_on_previous_text=False)
            text = " ".join(s.text.strip() for s in segs).strip()
        return {"text": text, "language": info.language, "seconds": round(info.duration, 1)}
    finally:
        Path(path).unlink(missing_ok=True)


def status():
    name = db.setting("stt_model") or "small.en"
    return {"model": name, "loaded": _model["name"] == name, "loading": STATE["loading"], "error": STATE["error"],
            "models": [{"id": k, "label": v[0], "size": v[1], "downloaded": downloaded(k)} for k, v in MODELS.items()]}
