"""
XiaohongshuAdapter — 小红书创作服务平台 Playwright 浏览器自动化

对标数创引擎: core/xhs.pyd, core/xhs_video.pyd

目标站点: https://creator.xiaohongshu.com (小红书创作服务平台)
功能:
  - 扫码登录 + 登录态持久化
  - 发布图文笔记 (标题 + 正文 + 图片 + 话题标签)
  - 发布视频笔记
  - 定时发布

技术栈:
  - Playwright 浏览器自动化
  - stealth.min.js 反检测
  - 人类行为模拟 (避免风控)
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

# ── Constants ────────────────────────────────────────────────

XHS_CREATOR_URL = "https://creator.xiaohongshu.com"
XHS_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"
XHS_LOGIN_URL = "https://creator.xiaohongshu.com/login"

# 内容限制
XHS_MAX_TITLE_LEN = 20      # 小红书标题限制 20 字
XHS_MAX_BODY_LEN = 1000     # 小红书正文限制 1000 字
XHS_MAX_IMAGES = 18         # 最多 18 张图片
XHS_MAX_TAG_COUNT = 5       # 话题标签数


class XiaohongshuAdapter(BasePlatformAdapter):
    """
    小红书创作服务平台适配器

    使用 Playwright 控制浏览器完成:
      1. 扫码登录 (首次使用)
      2. Cookie 恢复登录态
      3. 图文笔记发布
      4. 定时发布

    Usage:
        adapter = XiaohongshuAdapter()
        await adapter.initialize()

        status = await adapter.check_login()
        if not status.is_logged_in:
            await adapter.login()  # 打开浏览器等待扫码

        result = await adapter.publish(PublishRequest(
            title="今日穿搭分享",
            body="详细内容...",
            media_urls=["/path/to/image.jpg"],
            tags=["穿搭", "日常"],
        ))
    """

    platform = Platform.XHS
    platform_name = "小红书"

    def __init__(self):
        super().__init__()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._session = get_session_manager()
        self._account_name = ""

    # ── Lifecycle ─────────────────────────────────────────

    async def _do_initialize(self) -> bool:
        """启动 Playwright 浏览器"""
        try:
            from playwright.async_api import async_playwright
            from szyg.platforms.anti_detect import get_launch_config

            self._playwright = await async_playwright().start()
            config = get_launch_config(headless=False)
            self._browser = await self._playwright.chromium.launch(**config)
            logger.info("XiaohongshuAdapter: 浏览器已启动")
            return True
        except ImportError:
            logger.error("请安装 playwright: pip install playwright && playwright install")
            return False
        except Exception as e:
            logger.error(f"XiaohongshuAdapter 初始化失败: {e}")
            return False

    async def close(self) -> None:
        """释放资源"""
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self._state = AdapterState.CLOSED
            logger.info("XiaohongshuAdapter: 已关闭")
        except Exception as e:
            logger.error(f"XiaohongshuAdapter 关闭异常: {e}")

    # ── Login ─────────────────────────────────────────────

    async def check_login(self) -> LoginStatus:
        """检查小红书登录态"""
        if not self._browser:
            return LoginStatus(is_logged_in=False, message="浏览器未启动")

        # 检查本地 session
        if self._session.is_valid(Platform.XHS):
            return LoginStatus(
                is_logged_in=True,
                account_name=self._account_name,
                message="登录态有效",
                cookie_valid_until=self._session.get_cookie_expiry(Platform.XHS) or "",
            )

        # 实际检查
        try:
            if not self._context:
                await self._create_context()

            if not self._page:
                self._page = await self._context.new_page()

            response = await self._page.goto(
                XHS_CREATOR_URL, wait_until="domcontentloaded", timeout=15000
            )

            current_url = self._page.url
            if "login" in current_url.lower():
                return LoginStatus(is_logged_in=False, message="未登录 — 需要扫码")

            # 获取账号名称
            try:
                name_el = await self._page.wait_for_selector(".creator-name, .user-name, .name", timeout=3000)
                self._account_name = await name_el.inner_text() if name_el else ""
            except Exception:
                pass

            # 保存登录态
            await self._session.save(Platform.XHS, self._context)
            self._state = AdapterState.READY

            return LoginStatus(
                is_logged_in=True,
                account_name=self._account_name,
                message="已登录小红书创作平台",
            )

        except Exception as e:
            logger.warning(f"登录检查异常: {e}")
            return LoginStatus(is_logged_in=False, message=f"检查失败: {e}")

    async def login(self, **kwargs) -> LoginStatus:
        """
        执行登录 — 打开浏览器等待用户扫码。

        小红书支持:
          - 手机号验证码登录
          - 小红书APP扫码登录 (推荐)
        """
        if not self._browser:
            await self.initialize()
            if not self._browser:
                return LoginStatus(is_logged_in=False, message="浏览器启动失败")

        try:
            from szyg.platforms.anti_detect import get_stealth_context_config, inject_stealth

            if self._context:
                await self._context.close()
            self._context = await self._browser.new_context(**get_stealth_context_config())
            self._page = await self._context.new_page()
            await inject_stealth(self._page)

            await self._page.goto(XHS_CREATOR_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            logger.info("等待用户扫码登录小红书… (5分钟超时)")
            timeout = kwargs.get("timeout", 300)

            for i in range(timeout // 3):
                await asyncio.sleep(3)
                current_url = self._page.url

                if "creator.xiaohongshu.com" in current_url and "login" not in current_url.lower():
                    await self._session.save(Platform.XHS, self._context)
                    self._state = AdapterState.READY
                    logger.info("✓ 小红书登录成功!")
                    return LoginStatus(is_logged_in=True, message="登录成功!")

                if i % 20 == 0 and i > 0:
                    logger.info(f"  等待扫码中… ({i * 3}s / {timeout}s)")

            return LoginStatus(is_logged_in=False, message=f"登录超时 ({timeout}s)")

        except Exception as e:
            logger.error(f"登录异常: {e}")
            return LoginStatus(is_logged_in=False, message=f"登录失败: {e}")

    # ── Publish ───────────────────────────────────────────

    async def publish(self, request: PublishRequest) -> PublishResult:
        """
        发布笔记到小红书。

        流程:
          1. 登录检查
          2. 导航到发布页
          3. 上传图片/视频
          4. 填写标题 (≤20字) + 正文 (≤1000字)
          5. 添加话题标签
          6. 设置定时/立即发布
        """
        from szyg.platforms.anti_detect import HumanBehavior

        # 登录检查
        login_status = await self.check_login()
        if not login_status.is_logged_in:
            return PublishResult(
                success=False, platform=Platform.XHS.value,
                error_msg="未登录小红书创作平台",
            )

        self._state = AdapterState.PUBLISHING

        try:
            if not self._page or self._page.is_closed():
                self._page = await self._context.new_page()

            # 导航到发布页
            logger.info(f"导航到发布页: {XHS_PUBLISH_URL}")
            await self._page.goto(XHS_PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # 上传图片
            if request.media_urls:
                await self._upload_images(request.media_urls[:XHS_MAX_IMAGES])
                await asyncio.sleep(3)

            # 填写标题 (≤20字)
            title = request.title[:XHS_MAX_TITLE_LEN]
            title_sel = (
                'input[placeholder*="标题"], '
                '[data-e2e="title-input"], '
                '.title-input input, '
                '#title'
            )
            try:
                await HumanBehavior.type_text(self._page, title_sel, title)
            except Exception:
                logger.warning("无法定位标题输入框")

            await HumanBehavior.random_delay(0.5, 1)

            # 填写正文
            if request.body:
                body = request.body[:XHS_MAX_BODY_LEN]
                body_sel = (
                    'div[contenteditable="true"], '
                    '#content, '
                    '.ql-editor, '
                    'textarea[placeholder*="正文"]'
                )
                try:
                    body_el = await self._page.wait_for_selector(body_sel, state="visible", timeout=5000)
                    await body_el.click()
                    await HumanBehavior.type_in_element(body_el, body)
                except Exception:
                    pass

            # 添加话题标签
            if request.tags:
                await self._add_tags(request.tags[:XHS_MAX_TAG_COUNT])

            await HumanBehavior.random_scroll(self._page)

            # 设置定时发布
            if request.scheduled_at:
                await self._set_schedule(request.scheduled_at)

            # 点击发布
            await HumanBehavior.random_delay(1, 2)
            publish_sel = (
                'button:has-text("发布"), '
                'button:has-text("发布笔记"), '
                '[data-e2e="publish-btn"]'
            )
            await HumanBehavior.move_and_click(self._page, publish_sel)

            await asyncio.sleep(5)
            success, post_id = await self._check_publish_result()

            self._state = AdapterState.READY

            return PublishResult(
                success=success,
                platform=Platform.XHS.value,
                platform_post_id=post_id,
                platform_post_url=f"https://www.xiaohongshu.com/explore/{post_id}" if post_id else "",
                error_msg="" if success else "发布可能失败，请检查小红书创作平台",
            )

        except Exception as e:
            logger.error(f"小红书发布异常: {e}")
            self._state = AdapterState.ERROR
            return PublishResult(
                success=False, platform=Platform.XHS.value, error_msg=str(e),
            )

    # ── Helpers ───────────────────────────────────────────

    async def _create_context(self) -> None:
        """创建带登录态的 browser context"""
        from szyg.platforms.anti_detect import get_stealth_context_config, inject_stealth

        config = get_stealth_context_config()
        state = self._session.load(Platform.XHS)
        if state:
            config["storage_state"] = state
        self._context = await self._browser.new_context(**config)

        if not self._page:
            self._page = await self._context.new_page()
        await inject_stealth(self._page)

    async def _upload_images(self, media_urls: list[str]) -> None:
        """上传图片"""
        from szyg.platforms.anti_detect import HumanBehavior

        for i, url in enumerate(media_urls):
            try:
                upload_sel = 'input[type="file"]'
                file_inputs = await self._page.query_selector_all(upload_sel)
                if not file_inputs:
                    # 可能通过点击触发上传
                    upload_btn = await self._page.wait_for_selector(
                        'text=上传图片, text=添加图片, .upload-btn', timeout=3000
                    )
                    if upload_btn:
                        await upload_btn.click()
                        await asyncio.sleep(1)
                    file_inputs = await self._page.query_selector_all(upload_sel)

                if file_inputs:
                    local_path = url
                    if url.startswith(("http://", "https://")):
                        import tempfile, httpx
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(url, timeout=30)
                            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                                f.write(resp.content)
                                local_path = f.name
                    await file_inputs[-1].set_input_files(local_path)
                    await HumanBehavior.random_delay(2, 4)
                    logger.info(f"上传图片 [{i+1}/{len(media_urls)}]")
            except Exception as e:
                logger.warning(f"上传图片失败 [{i}]: {e}")

    async def _add_tags(self, tags: list[str]) -> None:
        """添加话题标签"""
        from szyg.platforms.anti_detect import HumanBehavior

        for tag in tags:
            if not tag.startswith("#"):
                tag = f"#{tag}"
            try:
                tag_sel = 'input[placeholder*="话题"]'
                tag_input = await self._page.wait_for_selector(tag_sel, timeout=3000)
                await tag_input.click()
                await HumanBehavior.type_in_element(tag_input, f"{tag} ")
                await asyncio.sleep(1)
            except Exception:
                # 追加到正文区
                try:
                    body = await self._page.wait_for_selector('div[contenteditable="true"]', timeout=3000)
                    await body.type(f" {tag}", delay=100)
                except Exception:
                    pass

    async def _set_schedule(self, scheduled_at: str) -> None:
        """设置定时发布"""
        try:
            schedule_btn = await self._page.wait_for_selector(
                'text=定时发布, .schedule-btn, [data-e2e="schedule-btn"]', timeout=3000
            )
            await schedule_btn.click()
            await asyncio.sleep(1)

            dt = datetime.fromisoformat(scheduled_at)
            try:
                date_input = await self._page.wait_for_selector('input[type="date"]', timeout=3000)
                await date_input.fill(dt.strftime("%Y-%m-%d"))
            except Exception:
                pass
            try:
                time_input = await self._page.wait_for_selector('input[type="time"]', timeout=3000)
                await time_input.fill(dt.strftime("%H:%M"))
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"设置定时发布失败: {e}")

    async def _check_publish_result(self) -> tuple[bool, str]:
        """检查发布结果"""
        try:
            url = self._page.url
            if "publish/success" in url or "content" in url:
                return True, ""
            try:
                err = await self._page.wait_for_selector('[class*="error"], [class*="fail"]', timeout=2000)
                return False, (await err.inner_text())[:200] if err else ""
            except Exception:
                pass
            # 如果在发布页停留 → 可能失败
            if "publish" in url:
                return False, ""
            return True, ""
        except Exception as e:
            return False, str(e)[:200]

    async def get_status(self, platform_post_id: str) -> dict:
        return {"platform": "xhs", "post_id": platform_post_id, "status": "unknown"}
