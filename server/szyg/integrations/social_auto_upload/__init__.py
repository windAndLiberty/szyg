"""SZYG's self-contained social publishing provider."""

from .conf import COOKIES_DIR

COOKIES_DIR.mkdir(parents=True, exist_ok=True)
