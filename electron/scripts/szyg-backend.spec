from pathlib import Path

import json
import os
import tomllib
from importlib.metadata import distribution

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
    (str(SERVER_ROOT / "szyg" / "resources" / "openmontage" / "worker.py"), "szyg/resources/openmontage"),
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
    (
        str(SERVER_ROOT / "szyg" / "integrations" / "social_auto_upload" / "LICENSE"),
        "third_party_licenses/social-auto-upload",
    ),
])

# Freeze the exact browser builds installed by this Python Playwright driver.
_playwright = distribution("playwright")
_locked = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
_expected = next(item["version"] for item in _locked["package"] if item["name"] == "playwright")
if _playwright.version != _expected:
    raise SystemExit(f"Playwright {_playwright.version} installed; uv.lock requires {_expected}")

_driver = Path(_playwright.locate_file("playwright/driver/package"))
_manifest = _driver / "browsers.json"
_browsers = {item["name"]: item for item in json.loads(_manifest.read_text(encoding="utf-8"))["browsers"]}
_browser_root = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
for _name, _executable in (
    ("chromium", "chrome-win64/chrome.exe"),
    ("chromium-headless-shell", "chrome-headless-shell-win64/chrome-headless-shell.exe"),
    ("ffmpeg", "ffmpeg-win64.exe"),
    ("winldd", "PrintDeps.exe"),
):
    _browser = _browsers[_name]
    _directory = f"{_name.replace('-', '_')}-{_browser['revision']}"
    _source = _browser_root / _directory
    if not (_source / _executable).is_file() or not (_source / "INSTALLATION_COMPLETE").is_file():
        raise SystemExit(f"Incomplete Playwright browser installation: {_source}")
    datas.append((str(_source), f"playwright/driver/package/.local-browsers/{_directory}"))
datas.append((str(_manifest), "playwright/driver/package"))
binaries = collect_dynamic_libs("uiautomation")

# Digital presenter renders are normalized locally. Bundle one audited FFmpeg
# executable so customer machines never depend on a system installation.
_ffmpeg_root = Path(os.environ.get("SZYG_FFMPEG_BUILD_DIR", r"D:\tools\ffmpeg"))
_ffmpeg_exe = _ffmpeg_root / "bin" / "ffmpeg.exe"
_ffprobe_exe = _ffmpeg_root / "bin" / "ffprobe.exe"
_ffmpeg_license = _ffmpeg_root / "LICENSE.txt"
if not _ffmpeg_exe.is_file() or not _ffprobe_exe.is_file() or not _ffmpeg_license.is_file():
    raise SystemExit(
        "Bundled FFmpeg source is missing. Set SZYG_FFMPEG_BUILD_DIR to a licensed FFmpeg distribution."
    )
binaries.append((str(_ffmpeg_exe), "third_party/ffmpeg"))
binaries.append((str(_ffprobe_exe), "third_party/ffmpeg"))
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
