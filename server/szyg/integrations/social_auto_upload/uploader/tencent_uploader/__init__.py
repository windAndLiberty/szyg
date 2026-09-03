from pathlib import Path

from ...conf import COOKIES_DIR

Path(COOKIES_DIR / "tencent_uploader").mkdir(parents=True, exist_ok=True)

from .main import TENCENT_PUBLISH_STRATEGY_IMMEDIATE
from .main import TENCENT_PUBLISH_STRATEGY_SCHEDULED
from .main import TencentBaseUploader
from .main import TencentNote
from .main import TencentVideo
from .main import cookie_auth
from .main import format_str_for_short_title
from .main import get_tencent_cookie
from .main import tencent_cookie_gen
from .main import tencent_setup
from .main import weixin_setup

__all__ = [
    "TENCENT_PUBLISH_STRATEGY_IMMEDIATE",
    "TENCENT_PUBLISH_STRATEGY_SCHEDULED",
    "TencentBaseUploader",
    "TencentNote",
    "TencentVideo",
    "cookie_auth",
    "format_str_for_short_title",
    "get_tencent_cookie",
    "tencent_cookie_gen",
    "tencent_setup",
    "weixin_setup",
]
