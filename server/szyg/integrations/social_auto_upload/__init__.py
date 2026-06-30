"""social-auto-upload 集成包 — 初始化时将自身加入 sys.path。"""
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).parent.resolve()
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from conf import BASE_DIR  # noqa: E402

Path(BASE_DIR / "cookies").mkdir(exist_ok=True)