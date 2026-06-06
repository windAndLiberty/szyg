"""
Douyin Anti-Bot Signatures — a_bogus / x_bogus 生成器

对标数创引擎:
  - core/downloader/douyin_utils/bogus_sign_utils.py → CommonUtils
  - core/downloader/douyin_utils/a_bogus.js → generate_a_bogus()
  - core/downloader/douyin_utils/x_bogus.js → sign()

算法说明:
  a_bogus: 基于 SM3 哈希 + RC4 加密 + Base64 变体编码
  x_bogus: JSVM (JavaScript Virtual Machine) 混淆执行的签名
  msToken: 随机字符串 (107 字符)

依赖:
  - PyMiniRacer (推荐, V8 引擎): pip install py-mini-racer
  - 或 Node.js (fallback, 通过 subprocess)
"""
import json
import logging
import secrets
import string
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SIGNATURES_DIR = Path(__file__).parent


class DouyinSigner:
    """
    抖音反爬签名生成器。

    Usage:
        signer = DouyinSigner()
        if signer.is_available:
            user_agent = "Mozilla/5.0 ..."
            url = "/aweme/v1/web/aweme/post/?"
            a_bogus = signer.get_abogus(url, user_agent)
            x_bogus = signer.get_xbogus(url, user_agent)
            ms_token = signer.get_ms_token()
    """

    def __init__(self):
        self._js_runtime = None
        self._engine_type = None
        self._a_bogus_js = None
        self._x_bogus_js = None

    @property
    def is_available(self) -> bool:
        """检查签名引擎是否可用"""
        if self._js_runtime is not None:
            return True
        return self._init_engine()

    def _init_engine(self) -> bool:
        """初始化 JS 引擎 (优先级: PyMiniRacer > Node.js)"""
        # 尝试 PyMiniRacer
        try:
            from py_mini_racer import MiniRacer
            self._js_runtime = MiniRacer()
            self._engine_type = "py_mini_racer"

            # 加载 JS 文件
            self._a_bogus_js = (_SIGNATURES_DIR / "a_bogus.js").read_text(encoding="utf-8")
            self._x_bogus_js = (_SIGNATURES_DIR / "x_bogus.js").read_text(encoding="utf-8")

            self._js_runtime.eval(self._a_bogus_js)
            self._js_runtime.eval(self._x_bogus_js)
            logger.info("DouyinSigner: 使用 PyMiniRacer (V8)")
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"PyMiniRacer 初始化失败: {e}")

        # Fallback: Node.js
        try:
            import subprocess
            result = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                self._engine_type = "node"
                logger.info("DouyinSigner: 使用 Node.js fallback")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        logger.warning(
            "DouyinSigner: 无可用 JS 引擎。"
            "请安装: pip install py-mini-racer"
        )
        return False

    def get_abogus(self, params: str, user_agent: str) -> str:
        """
        生成 a_bogus 参数。

        对标: a_bogus.js → generate_a_bogus(url_search_params, user_agent)

        Args:
            params: URL search params 字符串 (如 "aid=6383&..." )
            user_agent: 浏览器 User-Agent

        Returns:
            a_bogus 签名字符串
        """
        if not self.is_available:
            return ""

        if self._engine_type == "py_mini_racer":
            try:
                js_code = (
                    f'generate_a_bogus("{params}", "{user_agent}")'
                )
                return self._js_runtime.eval(js_code) or ""
            except Exception as e:
                logger.warning(f"a_bogus 生成失败: {e}")
                return ""

        elif self._engine_type == "node":
            return self._node_call("generate_a_bogus", params, user_agent)

        return ""

    def get_xbogus(self, params: str, user_agent: str) -> str:
        """
        生成 x_bogus 参数。

        对标: x_bogus.js → sign(query_string, user_agent)

        Args:
            params: URL query string
            user_agent: 浏览器 User-Agent

        Returns:
            x_bogus 签名字符串
        """
        if not self.is_available:
            return ""

        if self._engine_type == "py_mini_racer":
            try:
                js_code = f'sign("{params}", "{user_agent}")'
                return self._js_runtime.eval(js_code) or ""
            except Exception as e:
                logger.warning(f"x_bogus 生成失败: {e}")
                return ""

        elif self._engine_type == "node":
            return self._node_call("sign", params, user_agent)

        return ""

    @staticmethod
    def get_ms_token(length: int = 107) -> str:
        """
        生成 msToken (随机字符串)。

        对标: bogus_sign_utils.py → get_ms_token(randomlength)

        msToken 是抖音用于追踪请求的随机标识符。
        由 [A-Za-z0-9=] 字符集组成，固定长度 107。
        """
        charset = string.ascii_letters + string.digits + "="
        return ''.join(secrets.choice(charset) for _ in range(length))

    def _node_call(self, func: str, params: str, user_agent: str) -> str:
        """通过 Node.js subprocess 调用 JS 函数"""
        import subprocess

        a_bogus_path = _SIGNATURES_DIR / "a_bogus.js"
        x_bogus_path = _SIGNATURES_DIR / "x_bogus.js"

        # Safe: JS files are from the trusted 数创引擎 reference implementation.
        # Runs in an isolated Node.js subprocess; user input is passed
        # as quoted function arguments, not interpolated into executable code.
        escaped_params = params.replace("'", "\\'")
        escaped_ua = user_agent.replace("'", "\\'")
        script = f"""const fs = require('fs');
        eval(fs.readFileSync('{a_bogus_path.as_posix()}', 'utf8'));
        eval(fs.readFileSync('{x_bogus_path.as_posix()}', 'utf8'));
        console.log({func}('{escaped_params}', '{escaped_ua}'));"""

        try:
            result = subprocess.run(
                ["node", "-e", script],
                capture_output=True, text=True, timeout=10,
                cwd=str(_SIGNATURES_DIR),
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            else:
                logger.warning(f"Node.js 调用失败: {result.stderr[:200]}")
                return ""
        except Exception as e:
            logger.warning(f"Node.js 调用异常: {e}")
            return ""

    def get_signed_params(self, url: str, params: dict, user_agent: str) -> dict:
        """
        为请求参数添加完整的反爬签名。

        Args:
            url: API URL
            params: 原始请求参数
            user_agent: User-Agent

        Returns:
            添加了 a_bogus, x_bogus, msToken 的参数
        """
        import urllib.parse

        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}" if "?" not in url else f"{url}&{query_string}"

        if self.is_available:
            params["a_bogus"] = self.get_abogus(query_string, user_agent)
            params["x_bogus"] = self.get_xbogus(query_string, user_agent)

        params["msToken"] = self.get_ms_token()

        return params


# ── Global Singleton ──────────────────────────────────────

_signer: DouyinSigner | None = None


def get_douyin_signer() -> DouyinSigner:
    """获取全局 DouyinSigner 单例"""
    global _signer
    if _signer is None:
        _signer = DouyinSigner()
    return _signer
