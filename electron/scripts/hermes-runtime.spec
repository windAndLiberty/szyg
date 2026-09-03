from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules


REPO_ROOT = Path(SPECPATH).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
HERMES_ROOT = SERVER_ROOT / "vendor" / "hermes_agent"

hiddenimports = []
for package in (
    "agent", "cron", "gateway", "hermes_cli", "plugins", "providers",
    "skills", "tools", "tui_gateway", "acp_adapter",
):
    hiddenimports.extend(collect_submodules(package))

# Uvicorn loads the runtime app by import string, and the business registry
# loads capability modules lazily. PyInstaller cannot discover either path
# without explicit hidden imports.
hiddenimports.extend([
    "szyg.hermes_runtime_app",
    "szyg.hermes_business_tools",
    "szyg.hermes_capabilities",
    "szyg.hermes_windows_computer",
])

# vendor/hermes_agent is imported from the sys.path-inserted data directory
# (not from the analyzed tree), so its Windows-only import of
# concurrent_log_handler is invisible to static analysis. The CLH chain
# (concurrent_log_handler -> portalocker) must be pinned explicitly.
hiddenimports.extend([
    "concurrent_log_handler",
    "portalocker",
])

datas = [
    (str(HERMES_ROOT), "vendor/hermes_agent"),
]
binaries = collect_dynamic_libs("nemo_relay")

a = Analysis(
    [str(SERVER_ROOT / "hermes_runtime_entry.py")],
    pathex=[str(SERVER_ROOT), str(HERMES_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff", "torch", "tensorflow"],
    optimize=2,
    noarchive=False,
)

# Keep the complete runtime code and licenses, but never distribute upstream
# environment templates that could encourage client-side secret storage.
a.datas = [
    entry for entry in a.datas
    if not entry[0].replace("\\", "/").lower().endswith(
        ("vendor/hermes_agent/.env.example", "vendor/hermes_agent/.envrc")
    )
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="hermes-runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="hermes-runtime",
)
