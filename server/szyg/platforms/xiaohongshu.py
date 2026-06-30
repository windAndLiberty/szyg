"""
XiaohongshuAdapter — 小红书创作服务平台 Playwright 浏览器自动化

对标数创引擎: core/xhs.pyd, core/xhs_video.pyd

目标站点: https://creator.xiaohongshu.com (小红书创作服务平台)

架构:
  登录: 打开浏览器 → 用户手动登录 → 保存 Cookie → 关闭浏览器
  发布: 加载 Cookie → 打开浏览器 → 自动发布 → 关闭浏览器
"""
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from szyg.publisher import Platform, ContentType
from szyg.platforms.base import (
    BasePlatformAdapter, PublishRequest, PublishResult,
    LoginStatus, AdapterState,
)
from szyg.platforms.session_manager import get_session_manager

logger = logging.getLogger(__name__)

XHS_CREATOR_URL = "https://creator.xiaohongshu.com"
XHS_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"

XHS_MAX_TITLE_LEN = 20
XHS_MAX_BODY_LEN = 1000
XHS_MAX_IMAGES = 18
XHS_MAX_TAG_COUNT = 5


class XiaohongshuAdapter(BasePlatformAdapter):
    platform = Platform.XHS
    platform_name = "小红书"

    def __init__(self):
        super().__init__()
        self._pool = None
        self._context = None
        self._page = None
        self._session = get_session_manager()
        self._account_name = ""

    # ── Lifecycle ─────────────────────────────────────────

    async def _do_initialize(self) -> bool:
        try:
            from szyg.platforms.browser_pool import get_browser_pool
            self._pool = get_browser_pool()
            await self._pool.start()
            logger.info("XiaohongshuAdapter: using shared BrowserPool")
            return True
        except ImportError:
            logger.error("请安装 playwright: pip install playwright && playwright install")
            return False
        except Exception as e:
            logger.error(f"XiaohongshuAdapter 初始化失败: {e}")
            return False

    async def _ensure_browser_context(self, storage_state: dict | None = None):
        if self._context:
            try:
                await self._pool.invalidate_context("xhs")
            except Exception:
                pass
        self._context = await self._pool.get_context("xhs", storage_state=storage_state)
        self._page = await self._context.new_page()
        from szyg.platforms.anti_detect import inject_stealth
        await inject_stealth(self._page)

    async def _close_browser_context(self):
        if self._context:
            try:
                await self._pool.invalidate_context("xhs")
            except Exception:
                pass
        self._context = None
        self._page = None

    async def close(self) -> None:
        await self._close_browser_context()
        self._state = AdapterState.CLOSED

    # ── Login Detection ───────────────────────────────────

    async def _is_on_login_page(self) -> bool:
        """小红书非 SPA — 未登录时 URL 包含 /login。"""
        if not self._page:
            return True
        try:
            return "login" in self._page.url.lower()
        except Exception:
            return True

    # ── Login ─────────────────────────────────────────────

    async def check_login(self) -> LoginStatus:
        """轻量级检查 — 仅检查本地 Cookie。"""
        if self._session.is_valid(Platform.XHS):
            return LoginStatus(
                is_logged_in=True,
                account_name=self._account_name,
                message="登录态有效",
                cookie_valid_until=self._session.get_cookie_expiry(Platform.XHS) or "",
            )
        return LoginStatus(is_logged_in=False, message="未登录")

    async def login(self, **kwargs) -> LoginStatus:
        """打开浏览器 → 用户手动登录 → 保存 Cookie → 关闭浏览器。"""
        if not self._pool:
            await self.initialize()
            if not self._pool:
                return LoginStatus(is_logged_in=False, message="BrowserPool 启动失败")

        try:
            from szyg.platforms.anti_detect import warm_up_navigation

            await self._close_browser_context()
            await self._ensure_browser_context(storage_state=None)

            await warm_up_navigation(self._page)
            await self._page.goto(XHS_CREATOR_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            logger.info("⏳ 等待用户在浏览器中手动登录小红书… (任意方式皆可)")

            timeout = kwargs.get("timeout", 600)
            for i in range(timeout // 3):
                await asyncio.sleep(3)

                if not await self._is_on_login_page():
                    await self._session.save(Platform.XHS, self._context)
                    self._state = AdapterState.READY

                    try:
                        name_el = await self._page.wait_for_selector(
                            ".creator-name, .user-name, .name", timeout=3000
                        )
                        self._account_name = await name_el.inner_text() if name_el else ""
                    except Exception:
                        pass

                    await self._close_browser_context()
                    logger.info(f"✓ 小红书登录成功! ({self._account_name or '未知账号'}) 浏览器已关闭")
                    return LoginStatus(
                        is_logged_in=True,
                        account_name=self._account_name,
                        message=f"登录成功{' — ' + self._account_name if self._account_name else ''}",
                    )

                if i % 20 == 0 and i > 0:
                    logger.info(f"  等待手动登录中… ({i * 3}s / {timeout}s)")

            await self._close_browser_context()
            return LoginStatus(
                is_logged_in=False,
                message=f"登录超时 ({timeout}s)，请在浏览器窗口中手动完成登录后重试",
            )

        except Exception as e:
            logger.error(f"登录异常: {e}")
            await self._close_browser_context()
            return LoginStatus(is_logged_in=False, message=f"登录失败: {str(e)[:100]}")

    # ── Publish ───────────────────────────────────────────

    async def publish(self, request: PublishRequest) -> PublishResult:
        """加载 Cookie → 打开浏览器 → 自动发布 → 关闭浏览器。"""
        from szyg.platforms.anti_detect import HumanBehavior

        storage_state = self._session.load(Platform.XHS)
        if not storage_state or not storage_state.get("cookies"):
            return PublishResult(
                success=False, platform=Platform.XHS.value,
                error_msg="未登录 — 请先在「平台管理」中扫码登录小红书",
            )

        try:
            await self._close_browser_context()
            await self._ensure_browser_context(storage_state=storage_state)

            logger.info(f"导航到发布页: {XHS_PUBLISH_URL}")
            await self._page.goto(XHS_PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            if await self._is_on_login_page():
                await self._session.invalidate(Platform.XHS)
                await self._close_browser_context()
                return PublishResult(
                    success=False, platform=Platform.XHS.value,
                    error_msg="登录态已过期 — 请重新扫码登录",
                )

            self._state = AdapterState.PUBLISHING

            # 上传图片
            if request.media_urls:
                await self._upload_images(request.media_urls[:XHS_MAX_IMAGES])
                await asyncio.sleep(3)

            # 标题 (≤20字)
            title = request.title[:XHS_MAX_TITLE_LEN]
            title_sel = 'input[placeholder*="标题"], [data-e2e="title-input"], .title-input input, #title'
            try:
                await HumanBehavior.type_text(self._page, title_sel, title)
            except Exception:
                logger.warning("无法定位标题输入框")

            await HumanBehavior.random_delay(0.5, 1)

            # 正文
            if request.body:
                body = request.body[:XHS_MAX_BODY_LEN]
                body_sel = 'div[contenteditable="true"], #content, .ql-editor, textarea[placeholder*="正文"]'
                try:
                    body_el = await self._page.wait_for_selector(body_sel, state="visible", timeout=5000)
                    await body_el.click()
                    await HumanBehavior.type_in_element(body_el, body)
                except Exception:
                    pass

            # 话题标签
            if request.tags:
                await self._add_tags(request.tags[:XHS_MAX_TAG_COUNT])

            await HumanBehavior.random_scroll(self._page)

            # 定时发布
            if request.scheduled_at:
                await self._set_schedule(request.scheduled_at)

            # 点击发布
            await HumanBehavior.random_delay(1, 2)
            publish_sel = 'button:has-text("发布"), button:has-text("发布笔记"), [data-e2e="publish-btn"]'
            try:
                await HumanBehavior.move_and_click(self._page, publish_sel)
            except Exception:
                await self._close_browser_context()
                return PublishResult(
                    success=False, platform=Platform.XHS.value,
                    error_msg="无法定位发布按钮",
                )

            await asyncio.sleep(4)

            # 检查结果
            success, msg = await self._check_result()

            await self._close_browser_context()
            self._state = AdapterState.READY

            return PublishResult(
                success=success,
                platform=Platform.XHS.value,
                platform_post_id=f"xhs_{int(asyncio.get_event_loop().time())}" if success else "",
                error_msg=msg if not success else "",
            )

        except Exception as e:
            logger.error(f"小红书发布异常: {e}")
            await self._close_browser_context()
            self._state = AdapterState.ERROR
            return PublishResult(success=False, platform=Platform.XHS.value, error_msg=str(e))

    # ── Helpers ───────────────────────────────────────────

    async def _upload_images(self, media_urls: list[str]) -> None:
        from szyg.platforms.anti_detect import HumanBehavior
        for i, url in enumerate(media_urls):
            try:
                upload_sel = 'input[type="file"][accept*="image"]'
                file_input = await self._page.wait_for_selector(upload_sel, state="attached", timeout=5000)
                local_path = url
                if url.startswith(("http://", "https://")):
                    import tempfile
                    import httpx
                    async with httpx.AsyncClient(trust_env=False) as client:
                        resp = await client.get(url, timeout=30)
                        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                            f.write(resp.content)
                            local_path = f.name
                await file_input.set_input_files(local_path)
                await HumanBehavior.random_delay(1, 3)
                logger.info(f"上传图片 [{i+1}/{len(media_urls)}]: {url}")
            except Exception as e:
                logger.warning(f"上传图片失败 [{i}]: {e}")

    async def _add_tags(self, tags: list[str]) -> None:
        from szyg.platforms.anti_detect import HumanBehavior
        for tag in tags:
            if not tag.startswith("#"):
                tag = f"#{tag}"
            try:
                tag_sel = 'input[placeholder*="话题"], input[placeholder*="标签"]'
                tag_input = await self._page.wait_for_selector(tag_sel, timeout=3000)
                await tag_input.click()
                await HumanBehavior.type_in_element(tag_input, f"{tag} ")
                await asyncio.sleep(1)
            except Exception:
                try:
                    body = await self._page.wait_for_selector('div[contenteditable="true"]', timeout=3000)
                    await body.click()
                    await body.type(f" {tag}", delay=100)
                except Exception:
                    pass

    async def _set_schedule(self, scheduled_at: str) -> None:
        try:
            schedule_sel = '[data-e2e="schedule-publish"], .schedule-toggle, input[type="checkbox"][name*="schedule"]'
            schedule_btn = await self._page.wait_for_selector(schedule_sel, timeout=3000)
            await schedule_btn.click()
            await asyncio.sleep(1)
        except Exception:
            pass

    async def _check_result(self) -> tuple[bool, str]:
        try:
            page_text = (await self._page.inner_text('body'))[:300] or ""
            if '发布成功' in page_text or 'success' in page_text.lower():
                return True, ""
            if '失败' in page_text or 'error' in page_text.lower():
                return False, "发布可能失败"
            return True, ""
        except Exception:
            return True, ""

    async def get_status(self, platform_post_id: str) -> dict:
        return {"platform": "xhs", "post_id": platform_post_id, "status": "unknown"}
