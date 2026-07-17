"""Optional wxauto bridge for the local WeChat desktop client."""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_WXAUTO_ROOT = REPO_ROOT / "external" / "wxauto-main"


@dataclass
class WxautoProbeResult:
    available: bool
    connected: bool = False
    nickname: str = ""
    message: str = ""


class WxautoBridge:
    """Thin optional wrapper around wxauto.

    wxauto is used only for the currently logged-in desktop WeChat session.
    Multi-account isolation is intentionally handled outside this bridge.
    """

    def __init__(self) -> None:
        self._wechat_class: Any | None = None
        self._client: Any | None = None
        self._load_error: str = ""

    def _load_wechat_class(self) -> Any | None:
        if self._wechat_class is not None:
            return self._wechat_class

        modern_weixin = self._detect_modern_weixin()
        legacy_wechat = self._detect_legacy_wechat()
        if modern_weixin and not legacy_wechat:
            self._load_error = (
                "current WeChat desktop window is the newer Weixin/mmui client; "
                "wxauto supports the legacy WeChatMainWndForPC client, using UIA fallback"
            )
            return None

        try:
            module = importlib.import_module("wxauto")
        except Exception as first_error:
            if LOCAL_WXAUTO_ROOT.exists():
                root = str(LOCAL_WXAUTO_ROOT)
                if root not in sys.path:
                    sys.path.insert(0, root)
                try:
                    module = importlib.import_module("wxauto")
                except Exception as second_error:
                    self._load_error = str(second_error)
                    logger.debug("wxauto import failed from local source: %s", second_error)
                    return None
            else:
                self._load_error = str(first_error)
                logger.debug("wxauto import failed: %s", first_error)
                return None

        self._wechat_class = getattr(module, "WeChat", None)
        if self._wechat_class is None:
            self._load_error = "wxauto.WeChat is unavailable"
        return self._wechat_class

    def _detect_legacy_wechat(self) -> bool:
        try:
            import uiautomation as uia

            window = uia.WindowControl(ClassName="WeChatMainWndForPC", searchDepth=1)
            return bool(window.Exists(maxSearchSeconds=0.2))
        except Exception:
            return False

    def _detect_modern_weixin(self) -> bool:
        try:
            import uiautomation as uia

            window = uia.WindowControl(ClassName="mmui::MainWindow", searchDepth=1)
            if window.Exists(maxSearchSeconds=0.2):
                return True
        except Exception:
            pass

        try:
            completed = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Weixin.exe"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return "Weixin.exe" in completed.stdout
        except Exception:
            return False

    def is_available(self) -> bool:
        return self._load_wechat_class() is not None

    def connect(self) -> WxautoProbeResult:
        wechat_class = self._load_wechat_class()
        if wechat_class is None:
            return WxautoProbeResult(
                available=False,
                connected=False,
                message=self._load_error or "wxauto is unavailable",
            )

        try:
            if self._client is None:
                self._client = wechat_class(language="cn", debug=False)
            nickname = str(getattr(self._client, "nickname", "") or "").strip()
            return WxautoProbeResult(
                available=True,
                connected=True,
                nickname=nickname,
                message="wxauto connected",
            )
        except Exception as exc:
            logger.debug("wxauto connect failed: %s", exc)
            self._client = None
            return WxautoProbeResult(
                available=True,
                connected=False,
                message=str(exc),
            )

    def current_account(self) -> WxautoProbeResult:
        return self.connect()

    def get_sessions(self, limit: int = 20) -> list[str]:
        result = self.connect()
        if not result.connected or self._client is None:
            return []
        try:
            sessions = self._client.GetSessionList(reset=False)
            names: list[str] = []
            for item in sessions[: max(0, limit)]:
                name = getattr(item, "Name", None) or str(item)
                if name:
                    names.append(str(name))
            return names
        except Exception as exc:
            logger.debug("wxauto get sessions failed: %s", exc)
            return []

    def write_and_send_message(self, contact: str, text: str) -> bool:
        result = self.connect()
        if not result.connected or self._client is None:
            return False
        try:
            return bool(self._client.SendMsg(text, who=contact))
        except Exception as exc:
            logger.debug("wxauto send message failed: %s", exc)
            return False
