from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


REPO_ROOT = Path(SPECPATH).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"

datas = collect_data_files(
    "szyg",
    excludes=[
        "storage/chromium/**",
        "storage/profiles/**",
        "integrations/social_auto_upload/logs/**",
        "**/accounts.ini",
        "**/__pycache__/**",
        "**/*.pyc",
    ],
)

a = Analysis(
    [str(SERVER_ROOT / "szyg_backend_entry.py")],
    pathex=[str(SERVER_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("szyg"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytest_asyncio", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="szyg-backend",
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
    name="szyg-backend",
)
