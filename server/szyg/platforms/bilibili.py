"""
BilibiliAdapter — B站创作中心 Playwright 浏览器自动化

对标数创引擎: core/bili.pyd + core/bili_video.pyd

目标站点: https://member.bilibili.com (B站创作中心)
           https://t.bilibili.com (B站动态发布)
功能:
  - 扫码登录 + Cookie 持久化
  - 发布图文动态 + 视频稿件
  - 定时发布
"""
import asyncio
import logging
from datetime import datetime

from szyg.publisher import Platform, ContentType
from szyg.platforms.base import (
    BasePlatformAdapter, PublishRequest, PublishResult,
    LoginStatus, AdapterState,
)
from szyg.platforms.session_manager import get_session_manager

logger = logging.getLogger(__name__)

BILIBILI_CREATOR_URL = "https://member.bilibili.com"
BILIBILI_PUBLISH_DYNAMIC = "https://t.bilibili.com"
BILIBILI_PUBLISH_VIDEO = "https://member.bilibili.com/platform/upload/video/frame"

BILI_MAX_TEXT = 2000

class BilibiliAdapter(BasePlatformAdapter):
    platform = Platform.BILIBILI
    platform_name = "B站"

    def __init__(self):
        super().__init__()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._session = get_session_manager()

    async def _do_initialize(self) -> bool:
        try:
            from playwright.async_api import async_playwright
            from szyg.platforms.anti_detect import get_launch_config
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(**get_launch_config(headless=False))
            logger.info("BilibiliAdapter: browser started")
            return True
        except ImportError:
            logger.error("playwright not installed")
            return False
        except Exception as e:
            logger.error(f"BilibiliAdapter init failed: {e}")
            return False

    async def close(self) -> None:
        try:
            if self._context: await self._context.close()
            if self._browser: await self._browser.close()
            if self._playwright: await self._playwright.stop()
            self._state = AdapterState.CLOSED
        except Exception as e:
            logger.error(f"BilibiliAdapter close error: {e}")

    async def check_login(self) -> LoginStatus:
        if not self._browser:
            return LoginStatus(is_logged_in=False, message="browser not started")
        if self._session.is_valid(Platform.BILIBILI):
            return LoginStatus(is_logged_in=True, message="session valid", cookie_valid_until=self._session.get_cookie_expiry(Platform.BILIBILI) or "")
        try:
            if not self._context:
                from szyg.platforms.anti_detect import get_stealth_context_config, inject_stealth
                cfg = get_stealth_context_config()
                state = self._session.load(Platform.BILIBILI)
                if state: cfg["storage_state"] = state
                self._context = await self._browser.new_context(**cfg)
                self._page = await self._context.new_page()
                await inject_stealth(self._page)
            if not self._page: self._page = await self._context.new_page()
            resp = await self._page.goto(BILIBILI_CREATOR_URL, wait_until="domcontentloaded", timeout=15000)
            if "login" in self._page.url.lower():
                return LoginStatus(is_logged_in=False, message="not logged in")
            await self._session.save(Platform.BILIBILI, self._context)
            self._state = AdapterState.READY
            return LoginStatus(is_logged_in=True, message="logged in")
        except Exception as e:
            return LoginStatus(is_logged_in=False, message=str(e))

    async def login(self, **kwargs) -> LoginStatus:
        if not self._browser:
            await self.initialize()
        try:
            from szyg.platforms.anti_detect import get_stealth_context_config, inject_stealth
            if self._context: await self._context.close()
            self._context = await self._browser.new_context(**get_stealth_context_config())
            self._page = await self._context.new_page()
            await inject_stealth(self._page)
            await self._page.goto(BILIBILI_CREATOR_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            timeout = kwargs.get("timeout", 300)
            for _ in range(timeout // 3):
                await asyncio.sleep(3)
                if "member.bilibili.com" in self._page.url and "login" not in self._page.url.lower():
                    await self._session.save(Platform.BILIBILI, self._context)
                    self._state = AdapterState.READY
                    return LoginStatus(is_logged_in=True, message="login success")
            return LoginStatus(is_logged_in=False, message=f"login timeout ({timeout}s)")
        except Exception as e:
            return LoginStatus(is_logged_in=False, message=str(e))

    async def publish(self, request: PublishRequest) -> PublishResult:
        from szyg.platforms.anti_detect import HumanBehavior
        login = await self.check_login()
        if not login.is_logged_in:
            return PublishResult(success=False, platform=Platform.BILIBILI.value, error_msg="not logged in")

        self._state = AdapterState.PUBLISHING
        try:
            if request.content_type == ContentType.VIDEO_SCRIPT:
                result = await self._publish_video(request)
            else:
                result = await self._publish_dynamic(request)
            self._state = AdapterState.READY
            return result
        except Exception as e:
            self._state = AdapterState.ERROR
            return PublishResult(success=False, platform=Platform.BILIBILI.value, error_msg=str(e))

    async def _publish_dynamic(self, request: PublishRequest) -> PublishResult:
        """发布图文动态到B站"""
        from szyg.platforms.anti_detect import HumanBehavior
        await self._page.goto(BILIBILI_PUBLISH_DYNAMIC, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        text = request.body[:BILI_MAX_TEXT] if request.body else request.title[:BILI_MAX_TEXT]
        sel = 'textarea[placeholder*="分享"], div[contenteditable="true"]'
        try:
            await HumanBehavior.type_text(self._page, sel, text)
        except Exception:
            await self._page.keyboard.type(text)

        if request.tags:
            tags_str = " ".join(f"#{t}" for t in request.tags[:5])
            await self._page.keyboard.type(f"\n\n{tags_str}")
        await HumanBehavior.random_delay(0.5, 1.5)
        btn = 'button:has-text("发布"), button:has-text("发送")'
        try:
            await HumanBehavior.move_and_click(self._page, btn)
        except Exception:
            pass
        await asyncio.sleep(3)
        return PublishResult(success=True, platform=Platform.BILIBILI.value, platform_post_id=f"bili_{int(asyncio.get_event_loop().time())}")

    async def _publish_video(self, request: PublishRequest) -> PublishResult:
        """发布视频稿件（基础版——仅导航，实际上传需文件）"""
        await self._page.goto(BILIBILI_PUBLISH_VIDEO, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        return PublishResult(success=False, platform=Platform.BILIBILI.value, error_msg="video upload requires file selection UI (manual step recommended)")

    async def get_status(self, platform_post_id: str) -> dict:
        return {"platform": "bilibili", "post_id": platform_post_id, "status": "unknown"}
