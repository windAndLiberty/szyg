from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


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
datas = [
    item
    for item in datas
    if "integrations/social_auto_upload/logs" not in str(item[0]).replace("\\", "/")
]

datas.extend([
    (
        str(SERVER_ROOT / "szyg" / "integrations" / "wxauto_vendor" / "LICENSE"),
        "third_party_licenses/wxauto",
    ),
    (
        str(SERVER_ROOT / "szyg" / "integrations" / "wxauto_vendor" / "UPSTREAM_README.md"),
        "third_party_licenses/wxauto",
    ),
    (
        str(SERVER_ROOT / "szyg" / "integrations" / "social_auto_upload" / "UPSTREAM_README.md"),
        "third_party_licenses/social-auto-upload",
    ),
])
binaries = collect_dynamic_libs("uiautomation")

hiddenimports = [
    name for name in collect_submodules("szyg")
    if not name.startswith("szyg.integrations.omniparser_vendor")
]

a = Analysis(
    [str(SERVER_ROOT / "szyg_backend_entry.py")],
    pathex=[str(SERVER_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytest_asyncio", "ruff"],
    optimize=2,
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

sau_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sau-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    sau_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="szyg-backend",
)
