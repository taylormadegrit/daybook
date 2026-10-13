"""Models hub: scan this PC's hardware (built-in Windows info only, works offline) and recommend
Hugging Face GGUF models that fit it (needs internet), installable through Ollama with `hf.co/<repo>:<quant>`."""
import ctypes
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import winreg
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import paths

HF = "https://huggingface.co/api/models"
# Publishers that package mainstream models properly for home PCs (standard GGUF quant names)
PUBLISHERS = ["bartowski", "unsloth", "lmstudio-community", "ggml-org"]
CACHE = paths.DATA / "hf_cache.json"
CACHE_HOURS = 6
SKIP_TAGS = {"text-to-image", "image-text-to-video", "text-to-video", "feature-extraction", "text-to-speech",
             "automatic-speech-recognition", "sentence-similarity", "image-to-image"}
SKIP_WORDS = re.compile(r"uncensor|abliterat|heretic|nsfw|embed|rerank|moved|lora|draft|-tts|whisper|guard|ltx|wan2|flux|sdxl|"
                        r"hunyuan|video|image-|stable-diff|-ocr|minimax-h", re.I)
LLM_TASKS = {"text-generation", "image-text-to-text", "any-to-any", "conversational", ""}
# Best quality first. We pick the best one that fits.
QUANTS = ["Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "IQ4_XS", "Q3_K_M", "IQ3_M", "Q2_K"]
QUALITY = {"Q8_0": "Near-full quality", "Q6_K": "Excellent quality", "Q5_K_M": "Great quality", "Q4_K_M": "Great balance",
           "IQ4_XS": "Good balance", "Q3_K_M": "Smaller · some quality loss", "IQ3_M": "Smaller · some quality loss",
           "Q2_K": "Smallest · noticeable quality loss"}
OVERHEAD_GB = 1.2  # context window + runtime on top of the file size
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ---------------- hardware (offline, nothing to install) ----------------

def _ram_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return round(m.ullTotalPhys / 1024 ** 3, 1), round(m.ullAvailPhys / 1024 ** 3, 1)


def _cpu():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            name = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
    except OSError:
        name = "Unknown CPU"
    return {"name": re.sub(r"\s+", " ", name), "threads": os.cpu_count()}


_GPU_CACHE = {"t": 0, "v": None}


def _gpus():
    import time
    if _GPU_CACHE["v"] is not None and time.time() - _GPU_CACHE["t"] < 300:
        return _GPU_CACHE["v"]
    _GPU_CACHE["v"], _GPU_CACHE["t"] = _gpus_scan(), time.time()
    return _GPU_CACHE["v"]


def _gpus_scan():
    """NVIDIA via nvidia-smi (ships with the driver); every other GPU via the display-adapter registry keys."""
    gpus = []
    smi = shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
    try:
        out = subprocess.run([smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW).stdout
        for line in out.strip().splitlines():
            name, mem = [x.strip() for x in line.split(",")]
            gpus.append({"name": name, "vram_gb": round(int(mem) / 1024, 1), "vendor": "NVIDIA", "cuda": True})
    except Exception:
        pass
    base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as cls:
            for i in range(64):
                try:
                    sub = winreg.EnumKey(cls, i)
                except OSError:
                    break
                if not sub.isdigit():
                    continue
                try:
                    with winreg.OpenKey(cls, sub) as k:
                        name = winreg.QueryValueEx(k, "DriverDesc")[0]
                        try:
                            mem = winreg.QueryValueEx(k, "HardwareInformation.qwMemorySize")[0]
                        except OSError:
                            mem = winreg.QueryValueEx(k, "HardwareInformation.MemorySize")[0]
                        if isinstance(mem, bytes):
                            mem = int.from_bytes(mem, "little")
                except OSError:
                    continue
                if any(g["name"] == name for g in gpus) or re.search(r"basic|virtual|remote|parsec|mirror", name, re.I):
                    continue
                vram = round(int(mem) / 1024 ** 3, 1)
                integrated = bool(re.search(r"intel.*(uhd|iris|hd graphics)|radeon\(tm\) graphics|vega \d+ graphics", name, re.I))
                gpus.append({"name": name, "vram_gb": vram, "vendor": name.split()[0], "cuda": False,
                             "integrated": integrated})
    except OSError:
        pass
    return gpus


def _models_dir():
    d = os.environ.get("OLLAMA_MODELS")
    if not d:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                d = winreg.QueryValueEx(k, "OLLAMA_MODELS")[0]
        except OSError:
            d = str(Path.home() / ".ollama" / "models")
    return d


def scan():
    total, avail = _ram_gb()
    gpus = _gpus()
    dedicated = [g for g in gpus if not g.get("integrated") and g["vram_gb"] >= 2]
    best = max((g["vram_gb"] for g in dedicated), default=0)
    total_vram = round(sum(g["vram_gb"] for g in dedicated), 1)
    mdir = _models_dir()
    probe = Path(mdir)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    free = round(shutil.disk_usage(probe).free / 1024 ** 3, 1)
    if best:
        fast = round(best - OVERHEAD_GB, 1)
        summary = f"Models up to ~{fast:g} GB run fast on your {max(dedicated, key=lambda g: g['vram_gb'])['name']}"
    else:
        fast = 0
        summary = "No dedicated graphics card found — small models will run on your CPU"
    return {"ram_gb": total, "ram_free_gb": avail, "cpu": _cpu(), "gpus": gpus, "best_vram_gb": best,
            "total_vram_gb": total_vram, "fast_budget_gb": max(fast, 0), "models_dir": mdir, "disk_free_gb": free,
            "summary": summary, "scanned_at": time.strftime("%Y-%m-%dT%H:%M")}


# ---------------- Hugging Face (online) ----------------

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Daybook/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def _family(repo):
    """'bartowski/google_gemma-4-12b-it-GGUF' → 'gemma-4-12b-it' (to merge the same model across publishers)."""
    n = repo.split("/")[1].lower()
    n = re.sub(r"-gguf$", "", n)
    n = re.sub(r"^(google|meta-llama|mistralai|qwen|microsoft|deepseek-ai|ibm-granite|nvidia|thudm|zai-org)_", "", n)
    return re.sub(r"-(qat|instruct)$", "", n)


def _details(repo):
    m = _get(f"{HF}/{repo}?blobs=true&expand[]=gguf&expand[]=siblings&expand[]=downloads&expand[]=pipeline_tag"
             f"&expand[]=lastModified&expand[]=likes")
    quants = {}
    for s in m.get("siblings", []):
        f = s["rfilename"]
        if not f.endswith(".gguf") or "mmproj" in f.lower() or re.search(r"-\d{5}-of-\d{5}", f):
            continue  # skip vision projectors and split files
        for q in QUANTS:
            if re.search(rf"[-_.]{q}\.gguf$", f, re.I) or re.search(rf"[-_.]{q}[-_.]", f, re.I):
                quants.setdefault(q, round((s.get("size") or 0) / 1e9, 2))
                break
    g = m.get("gguf") or {}
    params = g.get("total") or 0
    if params:  # a real quant of an N-billion model is at least ~0.28 bytes/param — drops stubs and pointer files
        quants = {q: sz for q, sz in quants.items() if sz >= params / 1e9 * 0.28}
    return {"arch": g.get("architecture", ""), "repo": repo, "name": repo.split("/")[1].replace("-GGUF", "").replace("_", " "), "publisher": repo.split("/")[0],
            "params_b": round(params / 1e9, 1) if params else None, "context": g.get("context_length"),
            "downloads": m.get("downloads", 0), "likes": m.get("likes", 0), "updated": (m.get("lastModified") or "")[:10],
            "task": m.get("pipeline_tag") or "", "quants": quants, "url": f"https://huggingface.co/{repo}"}


def catalog(force=False):
    if not force and CACHE.exists() and time.time() - CACHE.stat().st_mtime < CACHE_HOURS * 3600:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    repos, seen = [], {}
    for pub in PUBLISHERS:
        q = urllib.parse.urlencode({"author": pub, "filter": "gguf", "sort": "downloads", "direction": -1, "limit": 40})
        for m in _get(f"{HF}?{q}"):
            if m.get("pipeline_tag") in SKIP_TAGS or SKIP_WORDS.search(m["id"]):
                continue
            fam = _family(m["id"])
            if fam not in seen:  # same model from several publishers: keep the most downloaded
                seen[fam] = m["id"]
                repos.append(m["id"])
    with ThreadPoolExecutor(8) as ex:
        items = [d for d in ex.map(lambda r: _safe(_details, r), repos[:80]) if d and d["quants"]]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(items), encoding="utf-8")
    return items


def _safe(f, *a):
    try:
        return f(*a)
    except Exception:
        return None


def _category(m):
    n = m["repo"].lower()
    if "coder" in n or "code" in n or "devstral" in n:
        return "coding"
    if re.search(r"r1|reason|think|qwq|magistral|phi-4-reasoning", n):
        return "reasoning"
    if m["task"] in ("image-text-to-text", "any-to-any") or re.search(r"vl|vision|llava", n):
        return "vision"
    return "general"


def recommend(hw, force=False):
    items = catalog(force)
    fast, total_gpu, ram = hw["fast_budget_gb"], hw["total_vram_gb"], hw["ram_gb"]
    out = []
    for m in items:
        if m["task"] not in LLM_TASKS or not m.get("context"):
            continue
        pick = None
        for q in QUANTS:  # best quality that fits fully on the biggest GPU
            if q in m["quants"] and m["quants"][q] + OVERHEAD_GB <= hw["best_vram_gb"]:
                pick, fit = q, "fast"
                break
        if not pick:  # otherwise a mid quant that fits across all GPUs, or GPU + RAM
            q = next((q for q in ("Q4_K_M", "IQ4_XS", "Q3_K_M") if q in m["quants"]), None)
            if not q:
                continue
            size = m["quants"][q] + OVERHEAD_GB
            if total_gpu and size <= total_gpu:
                pick, fit = q, "multi"
            elif size <= (total_gpu + ram * 0.5) and (total_gpu or m["quants"][q] <= 6):
                pick, fit = q, "split" if total_gpu else "cpu"
            else:
                continue
        size = m["quants"][pick]
        out.append(m | {"quant": pick, "size_gb": size, "fit": fit, "quality": QUALITY[pick],
                        "category": _category(m), "ollama": f"hf.co/{m['repo']}:{pick}",
                        "disk_ok": size < hw["disk_free_gb"] - 2})
    rank = {"fast": 0, "multi": 1, "split": 2, "cpu": 3}
    year_ago = time.strftime("%Y-%m-%d", time.localtime(time.time() - 365 * 86400))

    def score(x):  # bigger = smarter, newer = better, popularity as a small tie-breaker
        recent = 1.0 if x["updated"] >= year_ago else 0.55
        return (x["params_b"] or x["size_gb"]) * recent + min(x["downloads"], 5e6) / 2e6
    out.sort(key=lambda x: (rank[x["fit"]], -score(x)))
    best = next((x for x in out if x["fit"] == "fast" and x["category"] == "general"), out[0] if out else None)
    groups = {c: [x for x in out if x["category"] == c][:6] for c in ("general", "coding", "reasoning", "vision")}
    groups["small"] = sorted([x for x in out if x["size_gb"] <= 3.5], key=lambda x: -score(x))[:6]
    return {"best": best, "groups": groups, "count": len(out), "fetched": time.strftime("%Y-%m-%d %H:%M")}
