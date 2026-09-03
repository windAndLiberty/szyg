"""Portable configuration for the bundled social publishing runtime."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()


def _default_runtime_home() -> Path:
    local_app_data = (os.environ.get("LOCALAPPDATA", "") or "").strip()
    if local_app_data:
        return Path(local_app_data) / "SZYG" / "social_auto_upload"
    return Path.home() / ".szyg" / "social_auto_upload"


RUNTIME_HOME = Path(
    os.environ.get("SZYG_SAU_RUNTIME_HOME")
    or (Path(os.environ["SZYG_DATA_DIR"]) / "social_auto_upload" if os.environ.get("SZYG_DATA_DIR") else _default_runtime_home())
).expanduser().resolve()
COOKIES_DIR = RUNTIME_HOME / "cookies"
DB_DIR = RUNTIME_HOME / "db"
XHS_SERVER = "http://127.0.0.1:11901"
LOCAL_CHROME_PATH = ""
LOCAL_CHROME_HEADLESS = True
DEBUG_MODE = True
YT_PROXY = None

# Runtime state must never be written beside packaged source files.
COOKIES_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
for _sub in ("douyin_uploader", "xiaohongshu_uploader", "ks_uploader", "tencent_uploader", "youtube_uploader", "tk_uploader", "baijiahao_uploader", "bilibili_uploader"):
    (COOKIES_DIR / _sub).mkdir(exist_ok=True)
