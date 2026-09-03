"""
Anti-bot Signature Module — 反爬签名算法

对标数创引擎 core/downloader/douyin_utils/:
  - a_bogus.js → get_abogus()
  - x_bogus.js → get_xbogus()
  - bogus_sign_utils.py → CommonUtils class

用于绕过抖音/字节跳动系平台的反爬检测，
生成合法的 a_bogus 和 x_bogus 请求参数。
"""
from szyg.platforms.signatures.douyin_sign import (
    DouyinSigner,
    get_douyin_signer,
)

__all__ = ["DouyinSigner", "get_douyin_signer"]
