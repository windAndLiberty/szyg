from pathlib import Path

from ...conf import COOKIES_DIR

Path(COOKIES_DIR / "tk_uploader").mkdir(parents=True, exist_ok=True)
