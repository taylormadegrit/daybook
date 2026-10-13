"""Daybook AI worker — runs with the Ori Brazil Python (its CUDA PyTorch + Coqui XTTS), plus diffusers from
./ai-libs, so nothing in that project is changed. Started on demand by Daybook on 127.0.0.1:8504; models load
on first use and are unloaded after 10 idle minutes to free the GPU."""
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "ai-libs"))
os.environ.setdefault("TTS_HOME", r"D:\coqui-models")
os.environ.setdefault("COQUI_TOS_AGREED", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from flask import Flask, jsonify, request  # noqa: E402

import torch  # noqa: E402

app = Flask(__name__)
MODELS = {}
LOCK = threading.Lock()
LAST = {"t": time.time()}
SDXL = ROOT / "data" / "ai-models" / "sdxl-turbo"
OUT = Path(os.environ.get("DAYBOOK_CREATIONS", r"D:\Daybook\Creations"))
IDLE_S = 600


def pick_device(fast_fp16=False):
    """The GPU with the most free memory. For half-precision models (SDXL) only cards that are fast at it
    (RTX / compute 7.0+) count — a GTX 10-series card would be many times slower."""
    if not torch.cuda.is_available():
        return "cpu"
    cands = [i for i in range(torch.cuda.device_count()) if not fast_fp16 or torch.cuda.get_device_capability(i)[0] >= 7]
    cands = cands or list(range(torch.cuda.device_count()))
    best = max(cands, key=lambda i: torch.cuda.mem_get_info(i)[0])
    return f"cuda:{best}"


def image_pipe():
    if "img" not in MODELS:
        from diffusers import AutoPipelineForText2Image
        dev = pick_device(fast_fp16=True)
        pipe = AutoPipelineForText2Image.from_pretrained(str(SDXL), torch_dtype=torch.float16 if dev != "cpu" else torch.float32,
                                                         variant="fp16", use_safetensors=True)
        free = torch.cuda.mem_get_info(int(dev.split(":")[1]))[0] / 2**30 if dev != "cpu" else 0
        if dev != "cpu" and free < 9:  # card is shared with other apps → keep only the active part on the GPU
            pipe.enable_model_cpu_offload(gpu_id=int(dev.split(":")[1]))
            dev += " (low-memory mode)"
        else:
            pipe.to(dev)
        pipe.set_progress_bar_config(disable=True)
        try:
            pipe.enable_vae_slicing()
        except Exception:
            pass
        MODELS["img"], MODELS["img_dev"] = pipe, dev
    return MODELS["img"]


def tts_model():
    if "tts" not in MODELS:
        from TTS.api import TTS
        dev = pick_device()
        MODELS["tts"], MODELS["tts_dev"] = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(dev), dev
    return MODELS["tts"]


def unload(which=None):
    for k in ([which] if which else ["img", "tts"]):
        MODELS.pop(k, None)
        MODELS.pop(k + "_dev", None)
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def idle_watch():
    while True:
        time.sleep(30)
        if MODELS and time.time() - LAST["t"] > IDLE_S and not LOCK.locked():
            with LOCK:
                unload()


@app.get("/status")
def status():
    return jsonify(ok=True, image=("img" in MODELS), image_device=MODELS.get("img_dev"), tts=("tts" in MODELS),
                   image_model=SDXL.exists(), gpus=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])


@app.post("/image")
def image():
    j = request.get_json() or {}
    prompt = (j.get("prompt") or "").strip()
    if not prompt:
        return jsonify(error="Describe the image first"), 400
    w, h = int(j.get("width", 512)), int(j.get("height", 512))
    n, steps = max(1, min(int(j.get("count", 2)), 4)), max(1, min(int(j.get("steps", 2)), 6))
    seed = int(j.get("seed") or int(time.time()) % 2**31)
    with LOCK:
        LAST["t"] = time.time()
        pipe = image_pipe()
        gen = torch.Generator(device="cpu").manual_seed(seed)
        t0 = time.time()
        imgs = pipe(prompt=prompt, negative_prompt=j.get("negative") or None, num_inference_steps=steps, guidance_scale=0.0,
                    width=w, height=h, num_images_per_prompt=n, generator=gen).images
        LAST["t"] = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    stamp, files = datetime.now().strftime("%Y%m%d-%H%M%S"), []
    for i, im in enumerate(imgs):
        if j.get("upscale", True):
            from PIL import Image
            im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
        name = f"img-{stamp}-{seed}-{i}.png"
        im.save(OUT / name, pnginfo=_meta(prompt, seed, steps))
        files.append(name)
    return jsonify(files=files, seed=seed, seconds=round(time.time() - t0, 1), device=MODELS["img_dev"])


def _meta(prompt, seed, steps):
    from PIL.PngImagePlugin import PngInfo
    m = PngInfo()
    m.add_text("prompt", prompt)
    m.add_text("seed", str(seed))
    m.add_text("model", f"SDXL-Turbo, {steps} steps")
    return m


@app.post("/tts")
def tts():
    j = request.get_json() or {}
    text, voice = (j.get("text") or "").strip(), j.get("voice") or ""
    if not text:
        return jsonify(error="Type something to say"), 400
    if not os.path.isfile(voice):
        return jsonify(error="Pick a voice sample"), 400
    with LOCK:
        LAST["t"] = time.time()
        m = tts_model()
        OUT.mkdir(parents=True, exist_ok=True)
        name = f"voice-{datetime.now():%Y%m%d-%H%M%S}.wav"
        t0 = time.time()
        m.tts_to_file(text=text[:3000], speaker_wav=voice, language=j.get("language", "en"), file_path=str(OUT / name), split_sentences=True)
        LAST["t"] = time.time()
    return jsonify(files=[name], seconds=round(time.time() - t0, 1), device=MODELS["tts_dev"])


@app.post("/unload")
def do_unload():
    with LOCK:
        unload()
    return jsonify(ok=True)


if __name__ == "__main__":
    threading.Thread(target=idle_watch, daemon=True).start()
    app.run(host="127.0.0.1", port=8504, threaded=True, use_reloader=False)
