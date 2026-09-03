from pathlib import Path

from ...conf import COOKIES_DIR

Path(COOKIES_DIR / "ks_uploader").mkdir(parents=True, exist_ok=True)
