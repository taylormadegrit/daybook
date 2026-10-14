# PyInstaller recipe for the Daybook backend.  Build:  venv\Scripts\pyinstaller daybook-backend.spec --noconfirm
# Output: backend-dist\daybook-backend\  (daybook-backend.exe = service + helpers, daybook-mcp.exe = Claude connector)
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("web", "web"), ("daemon.pyw", "."), ("quickadd.pyw", "."), ("mcp_server.py", "."), ("arcade.py", ".")]
binaries, hidden = [], collect_submodules("reminders")
for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "av", "pypdfium2", "pypdfium2_raw", "tokenizers", "dateparser",
            "mcp", "fpdf", "icoextract", "obsws_python", "PIL", "huggingface_hub"):
    d, b, h = collect_all(pkg, filter_submodules=lambda n: not n.startswith(("mcp.cli", "onnxruntime.quantization", "onnxruntime.tools", "onnxruntime.transformers")))
    datas += d; binaries += b; hidden += h

a = Analysis(["backend_main.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=["torch", "tensorflow", "matplotlib", "pandas", "scipy", "IPython", "jupyter", "pytest"], noarchive=False)
pyz = PYZ(a.pure)
backend = EXE(pyz, a.scripts, [], exclude_binaries=True, name="daybook-backend", console=False, icon="web/brand/daybook.ico")
mcp = EXE(pyz, a.scripts, [], exclude_binaries=True, name="daybook-mcp", console=True, icon="web/brand/daybook.ico")
coll = COLLECT(backend, mcp, a.binaries, a.datas, name="daybook-backend")
