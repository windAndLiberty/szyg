from pathlib import Path

from ...conf import COOKIES_DIR

Path(COOKIES_DIR / "xiaohongshu_uploader").mkdir(parents=True, exist_ok=True)
