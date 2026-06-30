"""
KuaishouAdapter — 快手创作服务平台 Playwright 浏览器自动化

目标站点: https://creator.kuaishou.com

架构:
  登录: 打开浏览器 → 用户手动登录 → 保存 Cookie → 关闭浏览器
  发布: 加载 Cookie → 打开浏览器 → 自动发布 → 关闭浏览器
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
        self._pool = None
        self._context = None
        self._page = None
        self._session = get_session_manager()

    async def _do_initialize(self) -> bool:
        try:
            from szyg.platforms.browser_pool import get_browser_pool
            self._pool = get_browser_pool()
            await self._pool.start()
            logger.info("KuaishouAdapter: using shared BrowserPool")
            return True
        except ImportError:
            logger.error("playwright not installed")
            return False
        except Exception as e:
            logger.error(f"KuaishouAdapter init failed: {e}")
            return False

    async def _ensure_browser_context(self, storage_state: dict | None = None):
        if self._context:
            try:
                await self._pool.invalidate_context("kuaishou")
            except Exception:
                pass
        self._context = await self._pool.get_context("kuaishou", storage_state=storage_state)
        self._page = await self._context.new_page()
        from szyg.platforms.anti_detect import inject_stealth
        await inject_stealth(self._page)

    async def _close_browser_context(self):
        if self._context:
            try:
                await self._pool.invalidate_context("kuaishou")
            except Exception:
                pass
        self._context = None
        self._page = None

    async def close(self) -> None:
        await self._close_browser_context()
        self._state = AdapterState.CLOSED

    async def check_login(self) -> LoginStatus:
        if self._session.is_valid(Platform.KUAISHOU):
            return LoginStatus(
                is_logged_in=True, message="logged in",
                cookie_valid_until=self._session.get_cookie_expiry(Platform.KUAISHOU) or "",
            )
        return LoginStatus(is_logged_in=False, message="not logged in")

    async def login(self, **kwargs) -> LoginStatus:
        """打开浏览器 → 用户手动登录 → 保存 Cookie → 关闭浏览器。"""
        if not self._pool:
            await self.initialize()
            if not self._pool:
                return LoginStatus(is_logged_in=False, message="BrowserPool not started")

        try:
            from szyg.platforms.anti_detect import warm_up_navigation

            await self._close_browser_context()
            await self._ensure_browser_context(storage_state=None)

            await warm_up_navigation(self._page)
            await self._page.goto(KUAISHOU_CREATOR_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            logger.info("等待用户手动登录快手…")

            timeout = kwargs.get("timeout", 600)
            for _ in range(timeout // 3):
                await asyncio.sleep(3)
                if "creator.kuaishou.com" in self._page.url and "login" not in self._page.url.lower():
                    await self._session.save(Platform.KUAISHOU, self._context)
                    self._state = AdapterState.READY
                    await self._close_browser_context()
                    logger.info("✓ 快手登录成功! 浏览器已关闭")
                    return LoginStatus(is_logged_in=True, message="login success")

            await self._close_browser_context()
            return LoginStatus(is_logged_in=False, message=f"login timeout ({timeout}s)")

        except Exception as e:
            logger.error(f"login error: {e}")
            await self._close_browser_context()
            return LoginStatus(is_logged_in=False, message=f"login failed: {str(e)[:100]}")

    async def publish(self, request: PublishRequest) -> PublishResult:
        """加载 Cookie → 打开浏览器 → 自动发布 → 关闭浏览器。"""
        from szyg.platforms.anti_detect import HumanBehavior

        storage_state = self._session.load(Platform.KUAISHOU)
        if not storage_state or not storage_state.get("cookies"):
            return PublishResult(
                success=False, platform=Platform.KUAISHOU.value,
                error_msg="未登录 — 请先扫码登录快手",
            )

        try:
            await self._close_browser_context()
            await self._ensure_browser_context(storage_state=storage_state)

            await self._page.goto(KUAISHOU_PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            if "login" in self._page.url.lower():
                await self._session.invalidate(Platform.KUAISHOU)
                await self._close_browser_context()
                return PublishResult(
                    success=False, platform=Platform.KUAISHOU.value,
                    error_msg="登录态已过期 — 请重新扫码登录",
                )

            self._state = AdapterState.PUBLISHING

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

            await self._close_browser_context()
            self._state = AdapterState.READY

            return PublishResult(
                success=True,
                platform=Platform.KUAISHOU.value,
                platform_post_id=f"ks_{int(asyncio.get_event_loop().time())}",
            )

        except Exception as e:
            logger.error(f"publish error: {e}")
            await self._close_browser_context()
            self._state = AdapterState.ERROR
            return PublishResult(success=False, platform=Platform.KUAISHOU.value, error_msg=str(e))

    async def get_status(self, platform_post_id: str) -> dict:
        return {"platform": "kuaishou", "post_id": platform_post_id, "status": "unknown"}
