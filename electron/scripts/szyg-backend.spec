from pathlib import Path

import os

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

# patchright (`n`) resolves its browser registry to
# `<driver>/package/.local-browsers` when PLAYWRIGHT_BROWSERS_PATH is unset/0
# (see lib/server/registry/index.js). The bundled Chromium version is pinned by
# patchright's browsers.json — installing the revision at build time and shipping
# it under .local-browsers keeps the packaged runtime self-contained. Without
# this, account login / publishing fails with "Executable doesn't exist".
#
# Two binaries are required: the full Chromium (headed launches) and the
# headless shell (headless launches, which the publisher uses with
# LOCAL_CHROME_HEADLESS=True). Both are pinned to the same revision (1208).
_patchright_browser_names = [
    "chromium-1208",
    "chromium_headless_shell-1208",
]
_patchright_browser_candidates = [
    Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")) / name
    for name in _patchright_browser_names
] + [
    Path.home() / "AppData" / "Local" / "ms-playwright" / name
    for name in _patchright_browser_names
]
_missing_browsers = []
for _name in _patchright_browser_names:
    _rel_exe = (
        "chrome-win64/chrome.exe"
        if _name.startswith("chromium-1")
        else "chrome-headless-shell-win64/chrome-headless-shell.exe"
    )
    _src = next(
        (
            p
            for p in _patchright_browser_candidates
            if p.name == _name and (p / _rel_exe).exists()
        ),
        None,
    )
    if _src is None:
        _missing_browsers.append(_name)
        continue
    datas.extend([
        (str(_src), f"patchright/driver/package/.local-browsers/{_name}"),
    ])
if _missing_browsers:
    raise SystemExit(
        "patchright bundled Chromium missing: "
        + ", ".join(_missing_browsers)
        + " — run `n install chromium` first."
    )
binaries = collect_dynamic_libs("uiautomation")

# Digital presenter renders are normalized locally. Bundle one audited FFmpeg
# executable so customer machines never depend on a system installation.
_ffmpeg_root = Path(os.environ.get("SZYG_FFMPEG_BUILD_DIR", r"D:\tools\ffmpeg"))
_ffmpeg_exe = _ffmpeg_root / "bin" / "ffmpeg.exe"
_ffmpeg_license = _ffmpeg_root / "LICENSE.txt"
if not _ffmpeg_exe.is_file() or not _ffmpeg_license.is_file():
    raise SystemExit(
        "Bundled FFmpeg source is missing. Set SZYG_FFMPEG_BUILD_DIR to a licensed FFmpeg distribution."
    )
binaries.append((str(_ffmpeg_exe), "third_party/ffmpeg"))
datas.append((str(_ffmpeg_license), "third_party_licenses/ffmpeg"))

hiddenimports = [
    name for name in collect_submodules("szyg")
    if not name.startswith("szyg.integrations.omniparser_vendor")
]

# vendor/hermes_agent is loaded from a data directory (sys.path insertion),
# not the analyzed tree, so its Windows-only import of concurrent_log_handler
# escapes static analysis. Pin the whole CLH chain (-> portalocker).
hiddenimports.extend([
    "concurrent_log_handler",
    "portalocker",
])

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
