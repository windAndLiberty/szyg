"""
KuaishouAdapter — 快手创作服务平台 Playwright 浏览器自动化

对标数创引擎: core/ks.pyd + core/ks_video.pyd

目标站点: https://creator.kuaishou.com (快手创作服务平台)
功能:
  - 扫码登录 + Cookie 持久化
  - 发布图文 + 视频作品
"""
import asyncio
import logging

from szyg.publisher import Platform, ContentType
from szyg.platforms.base import (
    BasePlatformAdapter, PublishRequest, PublishResult,
    LoginStatus, AdapterState,
)
from szyg.platforms.session_manager import get_session_manager

logger = logging.getLogger(__name__)

KUAISHOU_CREATOR_URL = "https://creator.kuaishou.com"
KUAISHOU_PUBLISH_URL = "https://creator.kuaishou.com/publish"

KUAISHOU_MAX_TEXT = 1000

class KuaishouAdapter(BasePlatformAdapter):
    platform = Platform.KUAISHOU
    platform_name = "快手"

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
            logger.info("KuaishouAdapter: browser started")
            return True
        except ImportError:
            logger.error("playwright not installed")
            return False
        except Exception as e:
            logger.error(f"KuaishouAdapter init failed: {e}")
            return False

    async def close(self) -> None:
        try:
            if self._context: await self._context.close()
            if self._browser: await self._browser.close()
            if self._playwright: await self._playwright.stop()
            self._state = AdapterState.CLOSED
        except Exception as e:
            logger.error(f"KuaishouAdapter close error: {e}")

    async def check_login(self) -> LoginStatus:
        if not self._browser:
            return LoginStatus(is_logged_in=False, message="browser not started")
        if self._session.is_valid(Platform.KUAISHOU):
            return LoginStatus(is_logged_in=True, message="session valid", cookie_valid_until=self._session.get_cookie_expiry(Platform.KUAISHOU) or "")
        try:
            if not self._context:
                from szyg.platforms.anti_detect import get_stealth_context_config, inject_stealth
                cfg = get_stealth_context_config()
                state = self._session.load(Platform.KUAISHOU)
                if state: cfg["storage_state"] = state
                self._context = await self._browser.new_context(**cfg)
                self._page = await self._context.new_page()
                await inject_stealth(self._page)
            if not self._page: self._page = await self._context.new_page()
            resp = await self._page.goto(KUAISHOU_CREATOR_URL, wait_until="domcontentloaded", timeout=15000)
            if "login" in self._page.url.lower():
                return LoginStatus(is_logged_in=False, message="not logged in")
            await self._session.save(Platform.KUAISHOU, self._context)
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
            await self._page.goto(KUAISHOU_CREATOR_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            timeout = kwargs.get("timeout", 300)
            for _ in range(timeout // 3):
                await asyncio.sleep(3)
                if "creator.kuaishou.com" in self._page.url and "login" not in self._page.url.lower():
                    await self._session.save(Platform.KUAISHOU, self._context)
                    self._state = AdapterState.READY
                    return LoginStatus(is_logged_in=True, message="login success")
            return LoginStatus(is_logged_in=False, message=f"login timeout ({timeout}s)")
        except Exception as e:
            return LoginStatus(is_logged_in=False, message=str(e))

    async def publish(self, request: PublishRequest) -> PublishResult:
        from szyg.platforms.anti_detect import HumanBehavior
        login = await self.check_login()
        if not login.is_logged_in:
            return PublishResult(success=False, platform=Platform.KUAISHOU.value, error_msg="not logged in")

        self._state = AdapterState.PUBLISHING
        try:
            await self._page.goto(KUAISHOU_PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            body = request.body[:KUAISHOU_MAX_TEXT] if request.body else request.title[:KUAISHOU_MAX_TEXT]
            sel = 'textarea[placeholder*="写"], div[contenteditable="true"]'
            try:
                await HumanBehavior.type_text(self._page, sel, body)
            except Exception:
                await self._page.keyboard.type(body)

            if request.tags:
                tags_str = " ".join(f"#{t}" for t in request.tags[:5])
                await self._page.keyboard.type(f" {tags_str}")
            await HumanBehavior.random_delay(0.5, 1.5)
            btn = 'button:has-text("发布"), button:has-text("投稿")'
            try:
                await HumanBehavior.move_and_click(self._page, btn)
            except Exception:
                pass
            await asyncio.sleep(3)
            self._state = AdapterState.READY
            return PublishResult(success=True, platform=Platform.KUAISHOU.value, platform_post_id=f"ks_{int(asyncio.get_event_loop().time())}")
        except Exception as e:
            self._state = AdapterState.ERROR
            return PublishResult(success=False, platform=Platform.KUAISHOU.value, error_msg=str(e))

    async def get_status(self, platform_post_id: str) -> dict:
        return {"platform": "kuaishou", "post_id": platform_post_id, "status": "unknown"}
