"""
DouyinAdapter — 抖音创作服务平台 Playwright 浏览器自动化

对标数创引擎: core/douyin.pyd, core/douyin_video.pyd

目标站点: https://creator.douyin.com (抖音创作服务平台)
功能:
  - 扫码登录 + 登录态持久化
  - 发布图文内容 (标题 + 正文 + 图片)
  - 定时发布
  - 查询发布状态

技术栈:
  - Playwright (pip install playwright)
  - stealth.min.js 反检测
  - a_bogus/x_bogus 签名 (可选, 用于 API 请求)
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

DOUYIN_CREATOR_URL = "https://creator.douyin.com"
DOUYIN_CREATOR_PUBLISH = "https://creator.douyin.com/creator-micro/content/upload"
DOUYIN_LOGIN_URL = "https://creator.douyin.com/creator-micro/home"

# 内容限制
DOUYIN_MAX_TITLE_LEN = 1000    # 抖音标题最大字数
DOUYIN_MAX_TAG_COUNT = 5       # 最多话题标签数


class DouyinAdapter(BasePlatformAdapter):
    """
    抖音创作服务平台适配器

    使用 Playwright 控制浏览器完成:
      1. 扫码登录 (首次) / Cookie 恢复登录
      2. 图文/视频内容发布
      3. 定时发布

    Usage:
        adapter = DouyinAdapter()
        await adapter.initialize()
        status = await adapter.check_login()
        if not status.is_logged_in:
            await adapter.login()  # 等待扫码
        result = await adapter.publish(request)
    """

    platform = Platform.DOUYIN
    platform_name = "抖音"

    def __init__(self):
        super().__init__()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._session = get_session_manager()

    # ── Lifecycle ─────────────────────────────────────────

    async def _do_initialize(self) -> bool:
        """初始化 Playwright browser"""
        try:
            from playwright.async_api import async_playwright
            from szyg.platforms.anti_detect import get_launch_config

            self._playwright = await async_playwright().start()

            launch_config = get_launch_config(headless=False)
            self._browser = await self._playwright.chromium.launch(**launch_config)

            logger.info("DouyinAdapter: Playwright 浏览器已启动")
            return True
        except ImportError:
            logger.error("请安装 playwright: pip install playwright && playwright install chromium")
            return False
        except Exception as e:
            logger.error(f"DouyinAdapter 初始化失败: {e}")
            return False

    async def close(self) -> None:
        """释放浏览器资源"""
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
            logger.info("DouyinAdapter: 已关闭")
        except Exception as e:
            logger.error(f"DouyinAdapter 关闭异常: {e}")

    # ── Login ─────────────────────────────────────────────

    async def check_login(self) -> LoginStatus:
        """检查抖音创作平台登录态"""
        if not self._browser:
            return LoginStatus(is_logged_in=False, message="浏览器未启动")

        # 先检查本地存储的 cookie
        if self._session.is_valid(Platform.DOUYIN):
            return LoginStatus(
                is_logged_in=True,
                message="登录态有效 (本地缓存)",
                cookie_valid_until=self._session.get_cookie_expiry(Platform.DOUYIN) or "",
            )

        # 尝试访问创作者平台检查重定向
        try:
            if not self._context:
                from szyg.platforms.anti_detect import get_stealth_context_config
                config = get_stealth_context_config()
                state = self._session.load(Platform.DOUYIN)
                if state:
                    config["storage_state"] = state
                self._context = await self._browser.new_context(**config)

                # 注入 stealth
                from szyg.platforms.anti_detect import inject_stealth
                if not self._page:
                    self._page = await self._context.new_page()
                await inject_stealth(self._page)

            if not self._page:
                self._page = await self._context.new_page()

            response = await self._page.goto(DOUYIN_CREATOR_URL, wait_until="domcontentloaded", timeout=15000)

            # 如果跳转到登录页，说明未登录
            current_url = self._page.url
            if "login" in current_url.lower() or "passport" in current_url.lower():
                return LoginStatus(
                    is_logged_in=False,
                    message="未登录 — 需要扫码",
                )

            # 在创作者平台首页 — 已登录
            # 获取账号信息
            account_name = ""
            try:
                name_el = await self._page.wait_for_selector(
                    '[data-e2e="user-name"], .account-name, .creator-name',
                    timeout=3000
                )
                if name_el:
                    account_name = await name_el.inner_text()
            except Exception:
                pass

            # 保存登录态
            await self._session.save(Platform.DOUYIN, self._context)
            self._state = AdapterState.READY

            return LoginStatus(
                is_logged_in=True,
                account_name=account_name.strip(),
                message="已登录抖音创作平台",
            )

        except Exception as e:
            logger.warning(f"登录检查异常: {e}")
            return LoginStatus(is_logged_in=False, message=f"检查失败: {e}")

    async def login(self, **kwargs) -> LoginStatus:
        """
        执行登录 — 打开浏览器等待用户扫码。

        流程:
          1. 打开 creator.douyin.com
          2. 页面自动跳转到抖音登录页
          3. 展示二维码 (用户用抖音APP扫描)
          4. 每2秒检查是否登录成功
          5. 成功后保存 storage_state
        """
        if not self._browser:
            await self.initialize()
            if not self._browser:
                return LoginStatus(is_logged_in=False, message="浏览器启动失败")

        try:
            # 创建新的 context (不加载旧 cookie)
            from szyg.platforms.anti_detect import get_stealth_context_config, inject_stealth

            if self._context:
                await self._context.close()
            self._context = await self._browser.new_context(**get_stealth_context_config())
            self._page = await self._context.new_page()
            await inject_stealth(self._page)

            # 导航到创作者平台 (会自动跳转到登录页)
            await self._page.goto(DOUYIN_CREATOR_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # 等待用户扫码登录 (最多 5 分钟)
            logger.info("等待用户扫码登录抖音… (5分钟超时)")
            timeout = kwargs.get("timeout", 300)  # 默认 5 分钟

            for i in range(timeout // 3):
                await asyncio.sleep(3)
                current_url = self._page.url

                # 检查是否已跳转到创作者平台 (登录成功)
                if "creator.douyin.com" in current_url and "login" not in current_url.lower():
                    # 保存登录态
                    await self._session.save(Platform.DOUYIN, self._context)
                    self._state = AdapterState.READY
                    logger.info("✓ 抖音登录成功!")
                    return LoginStatus(
                        is_logged_in=True,
                        message="登录成功!",
                    )

                if i % 20 == 0 and i > 0:  # 每60秒提示一次
                    logger.info(f"  等待扫码中… ({i * 3}s / {timeout}s)")

            return LoginStatus(
                is_logged_in=False,
                message=f"登录超时 ({timeout}s) — 请重试",
            )

        except Exception as e:
            logger.error(f"登录异常: {e}")
            return LoginStatus(is_logged_in=False, message=f"登录失败: {e}")

    # ── Publish ───────────────────────────────────────────

    async def publish(self, request: PublishRequest) -> PublishResult:
        """
        发布内容到抖音创作平台。

        流程:
          1. 确保已登录
          2. 导航到发布页面
          3. 上传图片 (如有)
          4. 填入标题和正文
          5. 添加话题标签
          6. 设置定时发布 (如有)
          7. 点击发布
        """
        from szyg.platforms.anti_detect import HumanBehavior

        # 1. 登录检查
        login_status = await self.check_login()
        if not login_status.is_logged_in:
            return PublishResult(
                success=False,
                platform=Platform.DOUYIN.value,
                error_msg="未登录抖音创作平台，请先扫码登录",
            )

        self._state = AdapterState.PUBLISHING

        try:
            # 2. 确保 page 可用
            if not self._page or self._page.is_closed():
                self._page = await self._context.new_page()
                from szyg.platforms.anti_detect import inject_stealth
                await inject_stealth(self._page)

            # 3. 导航到发布页
            logger.info(f"导航到发布页: {DOUYIN_CREATOR_PUBLISH}")
            await self._page.goto(DOUYIN_CREATOR_PUBLISH, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # 4. 上传图片 (如有)
            if request.media_urls and request.content_type != ContentType.VIDEO_SCRIPT:
                await self._upload_images(request.media_urls)
                await asyncio.sleep(2)

            # 5. 填入标题
            title = request.title[:DOUYIN_MAX_TITLE_LEN]
            title_selectors = [
                'input[placeholder*="标题"]',
                'div[contenteditable="true"][data-placeholder*="标题"]',
                '.title-input input',
                '[data-e2e="title-input"] input',
            ]
            title_filled = False
            for sel in title_selectors:
                try:
                    await HumanBehavior.type_text(self._page, sel, title)
                    title_filled = True
                    break
                except Exception:
                    continue

            if not title_filled:
                logger.warning("无法定位标题输入框，尝试键盘输入")
                await self._page.keyboard.type(title)

            await HumanBehavior.random_delay(0.5, 1.5)

            # 6. 填入正文 (如有)
            if request.body:
                body_text = request.to_plain_text()
                body_selectors = [
                    'div[contenteditable="true"][data-placeholder*="描述"]',
                    'div[contenteditable="true"][data-placeholder*="视频"]',
                    'textarea[placeholder*="描述"]',
                    '.ql-editor',
                ]
                body_filled = False
                for sel in body_selectors:
                    try:
                        body_el = await self._page.wait_for_selector(sel, state="visible", timeout=5000)
                        await body_el.click()
                        await HumanBehavior.type_in_element(body_el, body_text)
                        body_filled = True
                        break
                    except Exception:
                        continue

            # 7. 添加话题标签
            if request.tags:
                await self._add_tags(request.tags)

            await HumanBehavior.random_scroll(self._page)

            # 8. 设置定时发布
            if request.scheduled_at:
                await self._set_schedule(request.scheduled_at)

            # 9. 点击发布按钮
            await HumanBehavior.random_delay(1, 3)
            publish_selectors = [
                'button:has-text("发布")',
                'button:has-text("投稿")',
                '[data-e2e="publish-btn"]',
                '.publish-btn button',
            ]
            published = False
            for sel in publish_selectors:
                try:
                    btn = await self._page.wait_for_selector(sel, state="visible", timeout=5000)
                    await HumanBehavior.move_and_click(self._page, sel)
                    published = True
                    break
                except Exception:
                    continue

            if not published:
                return PublishResult(
                    success=False,
                    platform=Platform.DOUYIN.value,
                    error_msg="无法定位发布按钮",
                )

            # 10. 等待发布结果
            await asyncio.sleep(3)
            success, post_id = await self._check_publish_result()

            self._state = AdapterState.READY

            return PublishResult(
                success=success,
                platform=Platform.DOUYIN.value,
                platform_post_id=post_id,
                platform_post_url=f"https://www.douyin.com/video/{post_id}" if post_id else "",
                error_msg="" if success else "发布可能失败，请检查抖音创作平台",
            )

        except Exception as e:
            logger.error(f"抖音发布异常: {e}")
            self._state = AdapterState.ERROR
            return PublishResult(
                success=False,
                platform=Platform.DOUYIN.value,
                error_msg=str(e),
            )

    # ── Helpers ───────────────────────────────────────────

    async def _upload_images(self, media_urls: list[str]) -> None:
        """上传图片到抖音发布页"""
        from szyg.platforms.anti_detect import HumanBehavior

        for i, url in enumerate(media_urls[:12]):  # 抖音限制最多12张图
            try:
                # 找到上传 input
                upload_sel = 'input[type="file"][accept*="image"]'
                file_input = await self._page.wait_for_selector(upload_sel, state="attached", timeout=5000)

                # 如果是本地路径，直接上传; 否则需要下载
                local_path = url
                if url.startswith(("http://", "https://")):
                    import tempfile, httpx
                    async with httpx.AsyncClient() as client:
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
        """添加话题标签"""
        from szyg.platforms.anti_detect import HumanBehavior

        for tag in tags[:DOUYIN_MAX_TAG_COUNT]:
            # 确保标签以 # 开头
            if not tag.startswith("#"):
                tag = f"#{tag}"

            try:
                # 尝试找到标签输入框并输入
                tag_sel = 'input[placeholder*="话题"], input[placeholder*="标签"]'
                tag_input = await self._page.wait_for_selector(tag_sel, timeout=3000)
                await tag_input.click()
                await HumanBehavior.type_in_element(tag_input, f"{tag} ")
                await asyncio.sleep(1)
            except Exception:
                # 如果找不到独立标签输入，追加到正文末尾
                try:
                    body_sel = 'div[contenteditable="true"]'
                    body = await self._page.wait_for_selector(body_sel, timeout=3000)
                    await body.click()
                    await body.type(f" {tag}", delay=100)
                except Exception:
                    pass

    async def _set_schedule(self, scheduled_at: str) -> None:
        """设置定时发布"""
        try:
            # 找到定时发布选项
            schedule_sel = '[data-e2e="schedule-publish"], .schedule-toggle, input[type="checkbox"][name*="schedule"]'
            schedule_btn = await self._page.wait_for_selector(schedule_sel, timeout=3000)
            await schedule_btn.click()
            await asyncio.sleep(1)

            # 设置日期时间 (格式因平台而异)
            dt = datetime.fromisoformat(scheduled_at)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")

            # 填入日期
            date_sel = 'input[type="date"], [data-e2e="schedule-date"] input'
            try:
                date_input = await self._page.wait_for_selector(date_sel, timeout=3000)
                await date_input.fill(date_str)
            except Exception:
                pass

            # 填入时间
            time_sel = 'input[type="time"], [data-e2e="schedule-time"] input'
            try:
                time_input = await self._page.wait_for_selector(time_sel, timeout=3000)
                await time_input.fill(time_str)
            except Exception:
                pass

            logger.info(f"设置定时发布: {scheduled_at}")

        except Exception as e:
            logger.warning(f"设置定时发布失败 (可能平台不支持): {e}")

    async def _check_publish_result(self) -> tuple[bool, str]:
        """检查发布结果"""
        try:
            await asyncio.sleep(3)
            current_url = self._page.url

            # 发布成功通常跳转到内容管理页
            if "content" in current_url or "work" in current_url.lower():
                return True, ""

            # 检查成功提示
            success_indicators = [
                'text="发布成功"',
                'text="投稿成功"',
                '.success-tip',
                '[class*="success"]',
            ]
            for sel in success_indicators:
                try:
                    el = await self._page.wait_for_selector(sel, timeout=2000)
                    if el:
                        return True, ""
                except Exception:
                    continue

            # 检查错误提示
            error_indicators = [
                '[class*="error"]',
                'text="发布失败"',
                '.error-tip',
            ]
            for sel in error_indicators:
                try:
                    el = await self._page.wait_for_selector(sel, timeout=2000)
                    if el:
                        err_text = await el.inner_text()
                        return False, err_text[:200]
                except Exception:
                    continue

            return False, ""  # 不确定

        except Exception as e:
            return False, str(e)[:200]

    async def get_status(self, platform_post_id: str) -> dict:
        """查询已发布内容的状态"""
        return {
            "platform": "douyin",
            "post_id": platform_post_id,
            "status": "unknown",
            "message": "状态查询功能尚未实现",
        }
