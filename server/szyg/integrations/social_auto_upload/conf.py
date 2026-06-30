"""sau 配置模块 — 替代原 conf.py，路径指向 szyg data 目录。"""
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
XHS_SERVER = "http://127.0.0.1:11901"
LOCAL_CHROME_PATH = ""
LOCAL_CHROME_HEADLESS = True
DEBUG_MODE = True
YT_PROXY = None

# 确保 cookies 目录存在（各 uploader __init__.py 会在此下建子目录）
_cookies = BASE_DIR / "cookies"
_cookies.mkdir(exist_ok=True)
for _sub in ("douyin_uploader", "xiaohongshu_uploader", "ks_uploader", "tencent_uploader", "youtube_uploader", "tk_uploader", "baijiahao_uploader", "bilibili_uploader"):
    (_cookies / _sub).mkdir(exist_ok=True)
