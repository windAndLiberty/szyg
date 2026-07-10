"""
DouyinAdapter — 抖音创作服务平台 Playwright 浏览器自动化

对标数创引擎: core/douyin.pyd, core/douyin_video.pyd

目标站点: https://creator.douyin.com (抖音创作服务平台)

架构:
  登录: 打开浏览器 → 用户手动登录 → 保存 Cookie → 关闭浏览器
  发布: 加载 Cookie → 打开浏览器 → 自动发布 → 关闭浏览器
  每次操作独立、自包含，保证操作连续性且不残留浏览器窗口。
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
from szyg.vision_grounding import VisionGrounding, get_vision_grounding

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

DOUYIN_CREATOR_URL = "https://creator.douyin.com"
DOUYIN_CREATOR_PUBLISH = "https://creator.douyin.com/creator-micro/content/upload"

# 内容限制
DOUYIN_MAX_TITLE_LEN = 1000
DOUYIN_MAX_TAG_COUNT = 5

# ── Verified Real Selectors (from DOM exploration 2026-06) ──
# These are the actual selectors on creator.douyin.com/creator-micro/content/upload
# Update if Douyin redesigns their creator platform.

# 图文 tab (not active by default — video tab is default)
#   Tried individually by _switch_to_image_text_tab()
SELECTOR_TAB_IMAGE_TEXT = [
    '[class*="tab-item"]:has-text("发布图文")',
    ':has-text("发布图文")',
    'text=发布图文',
]
SELECTOR_TAB_VIDEO = [
    '[class*="tab-item"]:has-text("发布视频")',
    ':has-text("发布视频")',
    'text=发布视频',
]

# Tutorial overlay (appears first time you switch to 图文 tab)
SELECTOR_TUTORIAL_DISMISS = [
    'button:has-text("我知道了")',
    'text=我知道了',
    '[class*="shepherd"] button',
]

# Title input — appears AFTER image upload in 图文 mode
# Real: <input placeholder="添加作品标题" class="semi-input">
SELECTOR_TITLE = (
    'input[placeholder*="标题"], '
    'input.semi-input[placeholder*="添加"], '
    'input[class*="semi-input"]'
)

# Body editor — appears AFTER image upload in 图文 mode
# Real: <div contenteditable="true" class="editor-kit-container">
SELECTOR_BODY = (
    'div.editor-kit-container[contenteditable="true"], '
    'div[contenteditable="true"][class*="editor"], '
    'div[contenteditable="true"]:not([data-placeholder*="标题"])'
)

# Publish button — the main "发布" button in the form
# Real: <button class="button-dhlUZE primary-cECiOj">发布</button>
SELECTOR_PUBLISH = (
    'button:has-text("发布"):not(:has-text("高清")):not(:has-text("定时")):not(:has-text("一键")), '
    'button[class*="primary"]:has-text("发布")'
)

# Alternate publish button (video mode): 高清发布
SELECTOR_PUBLISH_VIDEO = (
    'button:has-text("高清发布"), '
    '[class*="master-button-primary"]:has-text("发布")'
)

# Image file input
# Real: <input type="file" accept="image/*">
SELECTOR_IMAGE_UPLOAD = 'input[type="file"][accept*="image"]'

# Video file input
SELECTOR_VIDEO_UPLOAD = 'input[type="file"][accept*="video"]'


class DouyinAdapter(BasePlatformAdapter):
    """
    抖音创作服务平台适配器

    使用 Playwright 控制浏览器完成:
      1. 手动登录 (用户扫码/密码) → 保存 Cookie → 关闭浏览器
      2. 加载 Cookie → 自动发布图文/视频 → 关闭浏览器

    Usage:
        adapter = DouyinAdapter()
        await adapter.initialize()

        # 登录 (打开浏览器，用户手动操作后自动关闭)
        status = await adapter.login()

        # 发布 (从缓存 Cookie 打开浏览器，自动执行后关闭)
        result = await adapter.publish(request)
    """

    platform = Platform.DOUYIN
    platform_name = "抖音"

    def __init__(self):
        super().__init__()
        self._pool = None
        self._context = None
        self._page = None
        self._session = get_session_manager()
        self._vg: VisionGrounding | None = None  # lazy init
        self._lock = asyncio.Lock()  # protect concurrent login/publish access
        self._tmp_files: list[str] = []

    # ── Lifecycle ─────────────────────────────────────────

    async def _do_initialize(self) -> bool:
        """Initialize via shared BrowserPool."""
        try:
            from szyg.platforms.browser_pool import get_browser_pool
            self._pool = get_browser_pool()
            await self._pool.start()
            logger.info("DouyinAdapter: using shared BrowserPool")
            return True
        except ImportError:
            logger.error("请安装 playwright: pip install playwright && playwright install chromium")
            return False
        except Exception as e:
            logger.error(f"DouyinAdapter 初始化失败: {e}")
            return False

    async def _ensure_browser_context(self, storage_state: dict | None = None):
        """获取浏览器上下文（优先复用池中已有上下文）。

        每次操作创建新 Page 以保证隔离性，但复用 BrowserContext 以提升性能。
        """
        # _close_browser_context 已将上下文归还池中，此处获取复用
        self._context = await self._pool.get_context("douyin", storage_state=storage_state)
        self._page = await self._context.new_page()
        from szyg.platforms.anti_detect import inject_stealth
        await inject_stealth(self._page)

    async def _close_browser_context(self, *, invalidate: bool = False):
        """关闭/归还浏览器窗口。

        Args:
            invalidate: True=强制销毁上下文 (session过期、登出),
                        False=归还池中复用 (默认，提升性能)
        """
        # Clean up any residual temp files
        for tmp in getattr(self, '_tmp_files', []):
            try:
                from pathlib import Path
                Path(tmp).unlink(missing_ok=True)
            except OSError as e:
                logger.debug("Failed to clean up temp file %s: %s", tmp, e)
        self._tmp_files = []

        if self._context:
            try:
                if invalidate:
                    await self._pool.invalidate_context("douyin")
                else:
                    await self._pool.return_context("douyin")
            except Exception as e:
                logger.debug("Failed to release browser context: %s", e)
        self._context = None
        self._page = None

    async def close(self) -> None:
        """Close adapter and release resources."""
        await self._close_browser_context(invalidate=True)
        self._state = AdapterState.CLOSED
        logger.info("DouyinAdapter: closed")

    # ── Login Detection ───────────────────────────────────

    async def _is_login_overlay_visible(self) -> bool:
        """
        检测抖音创作平台 SPA 登录浮层是否可见。

        未登录时，抖音在任何页面内嵌显示登录浮层，包含:
          - QR 码 canvas
          - 手机号输入框
          - 验证码输入框
          - 登录/注册按钮
          - 滑块验证码
        """
        if not self._page:
            return True
        try:
            # A publish-page file input is a stronger signal than generic overlays.
            upload_input = await self._page.query_selector(
                f"{SELECTOR_VIDEO_UPLOAD}, {SELECTOR_IMAGE_UPLOAD}"
            )
            if upload_input is not None:
                return False

            # QR 码 canvas
            qr_canvas = await self._page.query_selector(
                'canvas[class*="qrcode"], canvas[class*="main-animation"], '
                '[class*="qrcode"] canvas, .scan_qrcode_login canvas'
            )
            # 手机号输入框
            phone_input = await self._page.query_selector(
                'input[type="tel"][placeholder*="手机号"], '
                'input[name="normal-input"], '
                'input[placeholder*="手机"]'
            )
            # 验证码输入框 (也是登录浮层标志)
            code_input = await self._page.query_selector(
                'input[placeholder*="验证码"]'
            )
            # 登录/注册按钮 (登录浮层特有)
            login_btn = await self._page.query_selector(
                'button:has-text("登录/注册"), '
                '[class*="login-btn"], '
                '[class*="submit_btn"]'
            )
            # 滑块验证码 (登录浮层的伴随物)
            from szyg.platforms.anti_detect import detect_slider
            slider_detected = await detect_slider(self._page)
            if slider_detected:
                logger.info("检测到滑块验证码 — 请手动完成验证")

            page_url = self._page.url.lower()
            visible = (
                phone_input is not None
                or code_input is not None
                or login_btn is not None
                or slider_detected
                or (qr_canvas is not None and "login" in page_url)
            )
            if visible:
                logger.debug("检测到登录浮层 (QR=%s, phone=%s, code=%s, btn=%s, slider=%s)",
                             qr_canvas is not None, phone_input is not None,
                             code_input is not None, login_btn is not None,
                             slider_detected)
            return visible
        except Exception:
            return True  # 异常时保守返回需登录

    async def _get_account_name(self) -> str:
        """获取当前登录的创作者账号名。"""
        if not self._page:
            return ""
        # 抖音创作平台首页会显示创作者名称
        name_selectors = [
            '[class*="user-name"]',
            '[class*="nickname"]',
            '[class*="account-name"]',
            '[class*="creator-name"]',
            'span[class*="name"]',
            '[class*="Name"]',
        ]
        for sel in name_selectors:
            try:
                name_el = await self._page.wait_for_selector(sel, timeout=2000)
                if name_el:
                    name = (await name_el.inner_text()).strip()
                    if name and 1 < len(name) < 50:
                        return name
            except Exception:
                continue
        return ""

    # ── Login ─────────────────────────────────────────────

    async def check_login(self) -> LoginStatus:
        """
        轻量级登录态检查 — 仅检查本地 Cookie 文件有效性，
        不打开浏览器（避免不必要的浏览器启动）。
        """
        if self._session.is_valid(Platform.DOUYIN):
            return LoginStatus(
                is_logged_in=True,
                message="登录态有效",
                cookie_valid_until=self._session.get_cookie_expiry(Platform.DOUYIN) or "",
            )
        return LoginStatus(is_logged_in=False, message="未登录")

    async def login(self, **kwargs) -> LoginStatus:
        """
        打开浏览器 → 用户手动登录 → 保存 Cookie → 关闭浏览器。

        支持任意登录方式 (扫码 / 手机号+密码 / 验证码 / 滑块)，
        用户只需在浏览器中自行完成。程序仅检测登录浮层是否消失。
        一旦检测到登录成功，立即保存 storage_state 并关闭浏览器。

        Thread-safe: 使用 asyncio.Lock 防止并发 login/publish 冲突。
        """
        async with self._lock:
            if not self._pool:
                await self.initialize()
                if not self._pool:
                    return LoginStatus(is_logged_in=False, message="BrowserPool 启动失败")

            try:
                from szyg.platforms.anti_detect import warm_up_navigation

                # 创建全新浏览器上下文 (不加载旧 cookie)
                await self._close_browser_context(invalidate=True)
                await self._ensure_browser_context(storage_state=None)

                # 预热导航
                await warm_up_navigation(self._page)

                # 打开抖音创作平台
                await self._page.goto(DOUYIN_CREATOR_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                logger.info("⏳ 等待用户在浏览器中手动登录抖音… (任意方式皆可)")

                timeout = kwargs.get("timeout", 600)
                for i in range(timeout // 2):
                    await asyncio.sleep(2)

                    if not await self._is_login_overlay_visible():
                        await asyncio.sleep(1)
                        await self._session.save(Platform.DOUYIN, self._context)
                        account = await self._get_account_name()
                        # Persist account metadata for the frontend account card.
                        if account:
                            self._session.save_account_meta(Platform.DOUYIN, {
                                "nickname": account,
                                "followers": 0,  # Later refreshed via get_status.
                            })
                        self._state = AdapterState.READY

                        # ── 关闭浏览器 ──
                        await self._close_browser_context()

                        logger.info(f"✓ 抖音登录成功! ({account or '未知账号'}) 浏览器已关闭")
                        return LoginStatus(
                            is_logged_in=True,
                            account_name=account,
                            message=f"登录成功{' — ' + account if account else ''}",
                        )

                    if i % 30 == 0 and i > 0:
                        logger.info(f"  等待手动登录中… ({i * 2}s / {timeout}s)")

                await self._close_browser_context(invalidate=True)
                return LoginStatus(
                    is_logged_in=False,
                    message=f"登录超时 ({timeout}s)，请在浏览器窗口中手动完成登录后重试",
                )

            except Exception as e:
                logger.error(f"登录异常: {e}")
                await self._close_browser_context(invalidate=True)
                return LoginStatus(is_logged_in=False, message=f"登录失败: {str(e)[:100]}")

    # ── Publish ───────────────────────────────────────────

    async def preflight_publish(self, request: PublishRequest) -> dict:
        """Open the publish page and validate prerequisites without clicking publish."""
        async with self._lock:
            checks = {
                "local_session": False,
                "media_files": True,
                "publish_page": False,
                "logged_in": False,
                "upload_input": False,
            }
            errors: list[str] = []

            storage_state = self._session.load(Platform.DOUYIN)
            if not storage_state or not storage_state.get("cookies"):
                errors.append("missing local douyin session")
                return {
                    "ok": False,
                    "platform": Platform.DOUYIN.value,
                    "content_type": request.content_type.value,
                    "checks": checks,
                    "errors": errors,
                }
            checks["local_session"] = True

            if request.media_urls:
                from pathlib import Path
                missing = [
                    path for path in request.media_urls
                    if not path.startswith(("http://", "https://"))
                    and not Path(path).exists()
                ]
                if missing:
                    checks["media_files"] = False
                    errors.extend(f"media file not found: {path}" for path in missing)

            try:
                if not self._pool:
                    await self.initialize()

                await self._close_browser_context()
                await self._ensure_browser_context(storage_state=storage_state)
                await self._page.goto(DOUYIN_CREATOR_PUBLISH, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                await self._resume_draft_if_present()
                try:
                    await self._page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                checks["publish_page"] = "creator.douyin.com" in self._page.url

                if await self._is_login_overlay_visible():
                    checks["logged_in"] = False
                    errors.append("douyin session expired or login overlay visible")
                else:
                    checks["logged_in"] = True

                is_video = request.content_type == ContentType.VIDEO_SCRIPT
                if not is_video:
                    await self._switch_to_image_text_tab()
                    await self._dismiss_tutorial()

                upload_selector = SELECTOR_VIDEO_UPLOAD if is_video else SELECTOR_IMAGE_UPLOAD
                try:
                    upload = await self._page.wait_for_selector(
                        upload_selector, state="attached", timeout=45000
                    )
                    checks["upload_input"] = upload is not None
                except Exception:
                    errors.append("upload input not found on publish page")

                await self._audit_screenshot("publish_preflight")
                await self._close_browser_context()
                self._state = AdapterState.READY
            except Exception as e:
                errors.append(str(e)[:200])
                await self._close_browser_context(invalidate=True)
                self._state = AdapterState.ERROR

            return {
                "ok": all(checks.values()) and not errors,
                "platform": Platform.DOUYIN.value,
                "content_type": request.content_type.value,
                "checks": checks,
                "errors": errors,
            }

    async def publish(self, request: PublishRequest) -> PublishResult:
        """
        加载 Cookie → 打开浏览器 → 自动发布 → 关闭浏览器。

        流程:
          1. 从本地加载 storage_state
          2. 创建全新浏览器上下文 (带 Cookie)
          3. 导航到发布页面
          4. 验证登录态
          5. 上传媒体文件 (图片/视频)
          6. 填入标题 + 正文
          7. 添加话题标签
          8. 设置定时发布 (如有)
          9. 点击发布
          10. 关闭浏览器，返回结果

        Thread-safe: 使用 asyncio.Lock 防止并发 login/publish 冲突。
        """
        async with self._lock:
            return await self._publish_with_social_auto_upload(request)

    async def _publish_with_social_auto_upload(self, request: PublishRequest) -> PublishResult:
        """Publish through the external social-auto-upload project."""
        storage_state = self._session.load(Platform.DOUYIN)
        if not storage_state or not storage_state.get("cookies"):
            return PublishResult(
                success=False,
                platform=Platform.DOUYIN.value,
                error_msg="Douyin is not logged in. Please scan and log in from platform management first.",
            )

        if not request.media_urls:
            return PublishResult(
                success=False,
                platform=Platform.DOUYIN.value,
                error_msg="Douyin publishing through social-auto-upload requires at least one local media file.",
            )

        from szyg.integrations.social_auto_upload_adapter import get_sau_adapter

        sau = get_sau_adapter()
        first_media = request.media_urls[0]
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm", ".flv"}
        is_video = request.content_type == ContentType.VIDEO_SCRIPT or any(
            first_media.lower().endswith(ext) for ext in video_exts
        )

        self._state = AdapterState.PUBLISHING
        headless = bool(request.extra.get("headless", True))
        try:
            if is_video:
                result = await sau.upload_video(
                    platform="douyin",
                    file_path=first_media,
                    title=request.title[:DOUYIN_MAX_TITLE_LEN],
                    desc=request.to_plain_text() if request.body else "",
                    tags=request.tags[:DOUYIN_MAX_TAG_COUNT],
                    headless=headless,
                )
            else:
                result = await sau.upload_note(
                    platform="douyin",
                    image_paths=request.media_urls,
                    title=request.title[:DOUYIN_MAX_TITLE_LEN],
                    note=request.to_plain_text() if request.body else "",
                    tags=request.tags[:DOUYIN_MAX_TAG_COUNT],
                    headless=headless,
                )

            self._state = AdapterState.READY if result.get("success") else AdapterState.ERROR
            return PublishResult(
                success=bool(result.get("success")),
                platform=Platform.DOUYIN.value,
                platform_post_id="",
                platform_post_url="",
                error_msg="" if result.get("success") else result.get("message", "social-auto-upload failed"),
                extra=result,
            )
        except Exception as e:
            logger.error("Douyin social-auto-upload publish failed: %s", e, exc_info=True)
            self._state = AdapterState.ERROR
            return PublishResult(
                success=False,
                platform=Platform.DOUYIN.value,
                error_msg=str(e),
            )

    async def _publish_with_native_playwright(self, request: PublishRequest) -> PublishResult:
        async with self._lock:
            from szyg.platforms.anti_detect import HumanBehavior

            # ── 0. 加载 Cookie ──
            storage_state = self._session.load(Platform.DOUYIN)
            if not storage_state or not storage_state.get("cookies"):
                return PublishResult(
                    success=False,
                    platform=Platform.DOUYIN.value,
                    error_msg="未登录 — 请先在「平台管理」中扫码登录抖音",
                )

            try:
                # ── 1. 打开浏览器 (带 Cookie) ──
                await self._close_browser_context()
                await self._ensure_browser_context(storage_state=storage_state)

                # ── 2. 导航到发布页面 ──
                logger.info(f"导航到发布页: {DOUYIN_CREATOR_PUBLISH}")
                await self._page.goto(DOUYIN_CREATOR_PUBLISH, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)

                # ── 3. 验证登录态 ──
                if await self._is_login_overlay_visible():
                    # Cookie 可能过期了 — 清除会话和浏览器上下文
                    await self._session.invalidate(Platform.DOUYIN)
                    await self._close_browser_context(invalidate=True)
                    return PublishResult(
                        success=False,
                        platform=Platform.DOUYIN.value,
                        error_msg="登录态已过期 — 请重新在「平台管理」中扫码登录抖音",
                    )

                self._state = AdapterState.PUBLISHING

                # ── 3.5 切换 图文 tab (non-video content) ──
                is_video = request.content_type == ContentType.VIDEO_SCRIPT
                if not is_video:
                    await self._switch_to_image_text_tab()
                    await self._dismiss_tutorial()

                # ── 4. 上传媒体文件 ──
                if request.media_urls:
                    if is_video:
                        await self._upload_video(request.media_urls)
                        await asyncio.sleep(3)  # 等待视频上传完成 (文件较大)
                    else:
                        await self._upload_images(request.media_urls)
                        await asyncio.sleep(2)
                        # After image upload, title/body fields appear. Dismiss any tutorial again.
                        await self._dismiss_tutorial()

                # ── 5. 填入标题 ──
                title = request.title[:DOUYIN_MAX_TITLE_LEN]
                await self._fill_title(title)

                await HumanBehavior.random_delay(0.5, 1.5)

                # ── 6. 填入正文 ──
                if request.body:
                    body_text = request.to_plain_text()
                    await self._fill_body(body_text)

                # ── 7. 添加话题标签 ──
                if request.tags:
                    await self._add_tags(request.tags)

                await HumanBehavior.random_scroll(self._page)

                # ── 8. 设置定时发布 ──
                if request.scheduled_at:
                    await self._set_schedule(request.scheduled_at)

                # ── 9. 点击发布 ──
                await HumanBehavior.random_delay(1, 3)
                published = await self._click_publish_button()
                if not published:
                    await self._close_browser_context()
                    return PublishResult(
                        success=False,
                        platform=Platform.DOUYIN.value,
                        error_msg="无法定位发布按钮 — 页面结构可能已变更",
                    )

                # ── 10. 等待发布结果 ──
                await asyncio.sleep(3)
                await self._audit_screenshot("after_publish_click")
                await self._wait_for_publish_complete()
                success, post_id, msg = await self._check_publish_result()

                # ── 11. 关闭浏览器 ──
                await self._close_browser_context()
                self._state = AdapterState.READY

                return PublishResult(
                    success=success,
                    platform=Platform.DOUYIN.value,
                    platform_post_id=post_id,
                    platform_post_url=f"https://www.douyin.com/video/{post_id}" if post_id else "",
                    error_msg=msg if not success else "",
                )

            except Exception as e:
                logger.error(f"抖音发布异常: {e}")
                await self._close_browser_context(invalidate=True)
                self._state = AdapterState.ERROR
                return PublishResult(
                    success=False,
                    platform=Platform.DOUYIN.value,
                    error_msg=str(e),
            )

    # ── Publish Helpers ───────────────────────────────────

    async def _switch_to_image_text_tab(self) -> bool:
        """Switch from default video tab to 图文 (image+text) tab. Returns True if switched."""
        # Check if already on 图文 tab
        try:
            active_tab = await self._page.query_selector(
                '[class*="tab-item"][class*="active"]:has-text("图文")'
            )
            if active_tab:
                logger.debug("Already on 图文 tab")
                return True
        except Exception:
            pass

        # Tier 1: Vision-based tab finding
        if self._vg is None:
            self._vg = get_vision_grounding()
        clicked = await self._vg.find_and_click(self._page, "发布图文", role="tab")
        if clicked:
            await asyncio.sleep(1.5)
            logger.info("Switched to 图文 tab (vision)")
            return True

        # Tier 2: CSS selector fallback (try each selector individually)
        for sel in SELECTOR_TAB_IMAGE_TEXT:
            try:
                tab = await self._page.wait_for_selector(
                    sel, state="visible", timeout=3000
                )
                if tab:
                    await tab.click()
                    await asyncio.sleep(1.5)
                    logger.info(f"Switched to 图文 tab (CSS): {sel[:60]}")
                    return True
            except Exception:
                continue

        # Tier 3: Generic click on anything with "图文" text
        try:
            await self._page.click('text=图文', timeout=3000)
            await asyncio.sleep(1.5)
            logger.info("Switched to 图文 tab (fallback)")
            return True
        except Exception:
            pass

        logger.warning("Switch to 图文 tab failed — all methods exhausted")
        return False

    async def _dismiss_tutorial(self) -> bool:
        """Dismiss the '我知道了' shepherd tutorial overlay. Returns True if dismissed."""
        for sel in SELECTOR_TUTORIAL_DISMISS:
            try:
                dismiss_btn = await self._page.wait_for_selector(
                    sel, state="visible", timeout=3000
                )
                if dismiss_btn:
                    await dismiss_btn.click()
                    await asyncio.sleep(1)
                    logger.info(f"Tutorial dismissed ({sel[:50]})")
                    return True
            except Exception:
                continue
        # No tutorial showing — that's fine
        return False

    async def _fill_title(self, title: str):
        """填入标题到发布表单。视觉优先，CSS 回退。"""
        from szyg.platforms.anti_detect import HumanBehavior

        # Tier 1: Vision-based input finding
        if self._vg is None:
            self._vg = get_vision_grounding()
        typed = await self._vg.find_and_type(self._page, "标题输入框", title)
        if typed:
            logger.info(f"标题已填入 (vision): {title[:30]}...")
            return

        # Tier 2: Verified CSS selectors (real DOM)
        try:
            title_el = await self._page.wait_for_selector(
                SELECTOR_TITLE, state="visible", timeout=8000
            )
            if title_el:
                await HumanBehavior.type_in_element(title_el, title)
                logger.info(f"标题已填入 (CSS): {title[:30]}...")
                return
        except Exception:
            pass

        # Tier 3: Generic fallback
        try:
            await HumanBehavior.type_text(
                self._page,
                'input[placeholder*="标题"], textarea[placeholder*="标题"]',
                title,
            )
            logger.info(f"标题已填入 (fallback): {title[:30]}...")
            return
        except Exception:
            pass

        logger.warning("无法定位标题输入框，使用键盘输入")
        await self._page.keyboard.type(title)

    async def _fill_body(self, body: str):
        """填入正文到发布表单。视觉优先，CSS 回退。"""
        from szyg.platforms.anti_detect import HumanBehavior

        # Tier 1: Vision-based input finding
        if self._vg is None:
            self._vg = get_vision_grounding()
        typed = await self._vg.find_and_type(self._page, "正文输入框 内容编辑区", body)
        if typed:
            logger.info(f"正文已填入 (vision): {body[:30]}...")
            return

        # Tier 2: Verified CSS selectors (real DOM)
        try:
            body_el = await self._page.wait_for_selector(
                SELECTOR_BODY, state="visible", timeout=8000
            )
            if body_el:
                await body_el.click()
                await asyncio.sleep(0.3)
                await HumanBehavior.type_in_element(body_el, body)
                logger.info(f"正文已填入 (CSS): {body[:30]}...")
                return
        except Exception:
            pass

        # Tier 3: Generic fallback
        try:
            fallback_el = await self._page.wait_for_selector(
                'div[contenteditable="true"]', state="visible", timeout=5000
            )
            if fallback_el:
                await fallback_el.click()
                await HumanBehavior.type_in_element(fallback_el, body)
                logger.info(f"正文已填入 (fallback): {body[:30]}...")
                return
        except Exception:
            logger.warning("无法定位正文编辑器")

    async def _click_publish_button(self) -> bool:
        """点击发布按钮，返回是否成功。视觉优先，CSS 回退。"""
        from szyg.platforms.anti_detect import HumanBehavior

        await self._scroll_to_publish_controls()

        # Tier 1: Final publish controls near the bottom of the form.
        bottom_selectors = [
            'button:has-text("高清发布")',
            'button:has-text("发布"):not(:has-text("发布视频")):not(:has-text("发布图文"))',
            '[class*="primary"]:has-text("发布")',
            '[class*="button"]:has-text("高清发布")',
        ]
        for sel in bottom_selectors:
            try:
                btn = await self._page.wait_for_selector(sel, state="visible", timeout=5000)
                if btn:
                    await HumanBehavior.move_and_click(self._page, sel)
                    logger.info(f"publish button clicked: {sel}")
                    return True
            except Exception:
                continue

        # Tier 2: Vision-based button finding
        if self._vg is None:
            self._vg = get_vision_grounding()
        clicked = await self._vg.find_and_click(self._page, "发布按钮")
        if clicked:
            logger.info("发布按钮已点击 (vision)")
            return True

        # Tier 2: Verified CSS selectors (real DOM)
        #   图文: <button class="button-dhlUZE primary-cECiOj">发布</button>
        #   视频: <button class="douyin-creator-master-button-primary">高清发布</button>
        for sel in [SELECTOR_PUBLISH, SELECTOR_PUBLISH_VIDEO]:
            try:
                btn = await self._page.wait_for_selector(sel, state="visible", timeout=5000)
                if btn:
                    await HumanBehavior.move_and_click(self._page, sel)
                    logger.info(f"发布按钮已点击 (CSS): {sel}")
                    return True
            except Exception:
                continue

        # Tier 3: Last resort
        try:
            btn = await self._page.wait_for_selector(
                'button:has-text("发布")', state="visible", timeout=3000
            )
            if btn:
                await btn.click()
                logger.info("发布按钮已点击 (fallback)")
                return True
        except Exception:
            pass
        return False

    async def _resume_draft_if_present(self) -> bool:
        """Continue editing an unfinished Douyin draft when the banner appears."""
        selectors = [
            'text=继续编辑',
            'button:has-text("继续编辑")',
            'a:has-text("继续编辑")',
        ]
        for sel in selectors:
            try:
                el = await self._page.wait_for_selector(sel, state="visible", timeout=3000)
                if el:
                    await el.click()
                    await asyncio.sleep(5)
                    logger.info("continued editing an unfinished Douyin draft")
                    return True
            except Exception:
                continue
        return False

    async def _scroll_to_publish_controls(self) -> None:
        """Move the viewport to the bottom area where Douyin renders final publish controls."""
        try:
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            await self._page.mouse.wheel(0, 5000)
            await asyncio.sleep(1)
        except Exception as e:
            logger.debug("failed to scroll to publish controls: %s", e)

    async def _wait_for_publish_complete(self):
        """等待发布完成（loading 消失）。"""
        try:
            for _ in range(15):
                loading = await self._page.query_selector(
                    '[class*="loading"], [class*="spin"], .loading-icon, [class*="uploading"]'
                )
                if not loading:
                    break
                await asyncio.sleep(1)
        except Exception:
            pass

    async def _upload_images(self, media_urls: list[str]) -> None:
        """上传图片到抖音发布页 (仅 图文 模式)。视觉优先，CSS 回退。"""
        from szyg.platforms.anti_detect import HumanBehavior

        if not hasattr(self, '_tmp_files'):
            self._tmp_files: list[str] = []

        for i, url in enumerate(media_urls[:12]):  # max 12 images per post
            tmp_path = ""
            try:
                # Tier 1: Locate file input via CSS (file inputs are hidden, CSS is reliable)
                file_input = await self._page.wait_for_selector(
                    SELECTOR_IMAGE_UPLOAD, state="attached", timeout=10000
                )

                local_path = url
                if url.startswith(("http://", "https://")):
                    import tempfile
                    import httpx
                    async with httpx.AsyncClient(trust_env=False) as client:
                        resp = await client.get(url, timeout=30)
                        with tempfile.NamedTemporaryFile(
                            suffix=".jpg", delete=False
                        ) as f:
                            f.write(resp.content)
                            local_path = f.name
                            tmp_path = f.name
                        # Track for cleanup
                        self._tmp_files.append(tmp_path)

                await file_input.set_input_files(local_path)
                await HumanBehavior.random_delay(1, 3)
                logger.info(f"上传图片 [{i+1}/{len(media_urls)}]: {url}")

            except Exception as e:
                logger.warning(f"上传图片失败 [{i}]: {e}")
            finally:
                # Clean up temp file immediately after upload to browser
                if tmp_path:
                    try:
                        from pathlib import Path
                        Path(tmp_path).unlink(missing_ok=True)
                        self._tmp_files.remove(tmp_path)
                    except Exception:
                        pass

    async def _upload_video(self, media_urls: list[str]) -> None:
        """上传视频到抖音发布页 (视频模式)。视觉优先，CSS 回退。

        抖音视频发布页默认就是视频 tab，不需要切换。
        上传第一个视频文件，等待上传进度条完成。
        """
        from szyg.platforms.anti_detect import HumanBehavior

        if not hasattr(self, '_tmp_files'):
            self._tmp_files: list[str] = []

        # Only one video per post — use the first media_url
        url = media_urls[0]
        tmp_path = ""
        try:
            # Tier 1: Locate file input via CSS (file inputs are hidden, CSS is reliable)
            file_input = await self._page.wait_for_selector(
                SELECTOR_VIDEO_UPLOAD, state="attached", timeout=15000
            )

            local_path = url
            if url.startswith(("http://", "https://")):
                import tempfile
                import httpx
                async with httpx.AsyncClient(trust_env=False) as client:
                    resp = await client.get(url, timeout=120)  # videos are larger
                    suffix = ".mp4"
                    if url.lower().endswith((".mov", ".avi", ".mkv")):
                        suffix = url.rsplit(".", 1)[-1]
                    with tempfile.NamedTemporaryFile(
                        suffix=suffix, delete=False
                    ) as f:
                        f.write(resp.content)
                        local_path = f.name
                        tmp_path = f.name
                    self._tmp_files.append(tmp_path)

            # Upload the video file
            await file_input.set_input_files(local_path)
            logger.info(f"视频文件已选择: {url}")

            # Wait for upload progress to complete
            # Douyin shows a progress bar with class like "progress" or "upload-progress"
            await asyncio.sleep(3)
            for i in range(60):  # wait up to 120s for video upload + processing
                try:
                    progress_el = await self._page.query_selector(
                        '[class*="progress"], [class*="upload"], '
                        '[class*="processing"], [class*="transcode"]'
                    )
                    if not progress_el:
                        # Progress element disappeared — upload complete
                        logger.info("视频上传进度已消失，上传完成")
                        break

                    # Check if "uploading" or "processing" text is visible
                    progress_text = (await progress_el.inner_text())[:50] or ""
                    if "失败" in progress_text:
                        raise Exception(f"视频上传失败: {progress_text}")
                except Exception as check_err:
                    if "视频上传失败" in str(check_err):
                        raise
                    # Element gone or error — likely upload complete
                    break
                await asyncio.sleep(2)
            else:
                logger.warning("视频上传等待超时 (120s)，继续发布流程")

            await HumanBehavior.random_delay(1, 3)

        except Exception as e:
            logger.error(f"视频上传失败: {e}")
            raise  # Video upload failure is fatal — abort publish
        finally:
            # Clean up temp file immediately after upload to browser
            if tmp_path:
                try:
                    from pathlib import Path
                    Path(tmp_path).unlink(missing_ok=True)
                    self._tmp_files.remove(tmp_path)
                except Exception:
                    pass

    async def _add_tags(self, tags: list[str]) -> None:
        """添加话题标签。视觉优先，CSS 回退。"""
        from szyg.platforms.anti_detect import HumanBehavior

        for tag in tags[:DOUYIN_MAX_TAG_COUNT]:
            if not tag.startswith("#"):
                tag = f"#{tag}"

            # Tier 1: Vision-based tag input finding
            if self._vg is None:
                self._vg = get_vision_grounding()
            typed = await self._vg.find_and_type(self._page, "话题标签输入框", f"{tag} ")
            if typed:
                await asyncio.sleep(0.5)
                continue

            # Tier 2: CSS selector fallback
            try:
                tag_sel = 'input[placeholder*="话题"], input[placeholder*="标签"]'
                tag_input = await self._page.wait_for_selector(tag_sel, timeout=3000)
                if tag_input:
                    await tag_input.click()
                    await HumanBehavior.type_in_element(tag_input, f"{tag} ")
                    await asyncio.sleep(0.5)
                    continue
            except Exception:
                pass

            # Tier 3: Append to body
            try:
                body = await self._page.wait_for_selector(
                    'div[contenteditable="true"]', timeout=3000
                )
                if body:
                    await body.click()
                    await body.type(f" {tag}", delay=100)
            except Exception:
                pass

    async def _set_schedule(self, scheduled_at: str) -> None:
        """设置定时发布。"""
        try:
            schedule_sel = (
                '[data-e2e="schedule-publish"], '
                '.schedule-toggle, '
                'input[type="checkbox"][name*="schedule"]'
            )
            schedule_btn = await self._page.wait_for_selector(schedule_sel, timeout=3000)
            await schedule_btn.click()
            await asyncio.sleep(1)

            dt = datetime.fromisoformat(scheduled_at)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")

            date_sel = 'input[type="date"], [data-e2e="schedule-date"] input'
            try:
                date_input = await self._page.wait_for_selector(date_sel, timeout=3000)
                await date_input.fill(date_str)
            except Exception:
                pass

            time_sel = 'input[type="time"], [data-e2e="schedule-time"] input'
            try:
                time_input = await self._page.wait_for_selector(time_sel, timeout=3000)
                await time_input.fill(time_str)
            except Exception:
                pass

            logger.info(f"设置定时发布: {scheduled_at}")

        except Exception as e:
            logger.warning(f"设置定时发布失败: {e}")

    async def _check_publish_result(self) -> tuple[bool, str, str]:
        """检查发布结果，返回 (success, post_id, error_msg)。

        发布成功后抖音会跳转到内容管理页。
        本方法从该页面提取真实 post_id 用于追踪。
        """
        import re
        try:
            # 等待页面跳转完成 (最多等待 15s)
            post_id = ""
            for _ in range(15):
                await asyncio.sleep(1)
                current_url = self._page.url
                page_text = ""

                # ── 提取 post_id ──
                # 策略1: URL中直接包含视频/图文ID
                #   例: creator.douyin.com/creator-micro/content/video/{19位ID}
                url_match = re.search(
                    r'(?:video|content|work)/(\d{15,25})', current_url
                )
                if url_match:
                    post_id = url_match.group(1)
                    logger.info(f"从URL提取到 post_id: {post_id}")
                    return True, post_id, ""

                # 策略2: 页面元素链接中的ID
                #   内容管理页上第一个内容卡片的链接
                id_selectors = [
                    'a[href*="/video/"]',
                    'a[href*="/content/"]',
                    '[data-content-id]',
                    '[data-video-id]',
                    '[data-item-id]',
                ]
                for sel in id_selectors:
                    try:
                        el = await self._page.query_selector(sel)
                        if el:
                            href = await el.get_attribute("href") or ""
                            data_id = (
                                await el.get_attribute("data-content-id")
                                or await el.get_attribute("data-video-id")
                                or await el.get_attribute("data-item-id")
                                or ""
                            )
                            # 从 href 提取
                            href_match = re.search(r'(\d{15,25})', href)
                            if href_match:
                                post_id = href_match.group(1)
                                break
                            # 从 data 属性提取
                            if data_id and data_id.isdigit() and len(data_id) >= 15:
                                post_id = data_id
                                break
                    except Exception:
                        continue

                if post_id:
                    logger.info(f"从页面元素提取到 post_id: {post_id}")

                # ── 检查成功/失败状态 ──
                try:
                    page_text = (await self._page.inner_text('body'))[:500] or ""
                except Exception:
                    pass

                combined = page_text.lower()

                # 成功关键词
                success_keywords = ['发布成功', '投稿成功', '已发布', 'success']
                for kw in success_keywords:
                    if kw in combined:
                        return True, post_id, ""

                # 如果已在内容管理页 (跳转完成) 且没有失败提示
                if ("content" in current_url or "work" in current_url.lower()):
                    if post_id:
                        return True, post_id, ""
                    # 在内容管理页但没提取到ID — 再等一轮
                    continue

                # 失败关键词
                fail_keywords = ['发布失败', '投稿失败', '请重试', '违规', '敏感', '审核不通过']
                for kw in fail_keywords:
                    if kw in combined:
                        # 尝试获取更详细的错误信息
                        error_text = ""
                        try:
                            toast_el = await self._page.query_selector(
                                '.toast, .notification, [class*="toast"], [class*="message"], [class*="error"]'
                            )
                            if toast_el:
                                error_text = (await toast_el.inner_text())[:200] or ""
                        except Exception:
                            pass
                        return False, "", error_text or f"检测到失败提示: {kw}"

                # 还在上传页 — 继续等待
                if "upload" in current_url:
                    continue

                # 页面已跳转但不确定状态 — 如果有 post_id 就认为成功
                if post_id:
                    return True, post_id, ""

            # 超时 — 最后检查一次
            current_url = self._page.url
            if False and ("content" in current_url or "work" in current_url.lower()):
                return True, post_id, f"发布完成但未能提取 post_id (url={current_url[:120]})"
            return False, "", "等待发布结果超时"

        except Exception as e:
            return False, "", str(e)[:200]

    async def get_status(self, platform_post_id: str) -> dict:
        """查询已发布内容的实时数据（播放量/点赞/评论/分享）。

        用已登录的浏览器访问创作者内容管理页，抓取统计数据。
        """
        if not platform_post_id:
            return {
                "platform": "douyin",
                "post_id": "",
                "status": "unknown",
                "message": "缺少 post_id",
            }

        try:
            from szyg.platforms.anti_detect import inject_stealth
            from szyg.platforms.session_manager import get_session_manager

            session = get_session_manager()
            storage_state = session.load(Platform.DOUYIN)
            if not storage_state:
                return {
                    "platform": "douyin",
                    "post_id": platform_post_id,
                    "status": "unknown",
                    "message": "未登录抖音 — 请先在平台管理中扫码登录",
                }

            # 打开浏览器查看内容详情
            await self._close_browser_context()
            await self._ensure_browser_context(storage_state=storage_state)

            detail_url = (
                f"https://creator.douyin.com/creator-micro/content/video/"
                f"{platform_post_id}"
            )
            logger.info(f"查询状态: {detail_url}")
            await self._page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)

            stats = {"play_count": 0, "like_count": 0, "comment_count": 0, "share_count": 0}

            # 策略1: 从页面文本中提取数字
            try:
                page_text = (await self._page.inner_text("body"))[:3000] or ""
            except Exception:
                page_text = ""

            # 策略2: 查找数据卡片元素
            stat_selectors = {
                "play_count": [
                    '[class*="play"] [class*="count"]', '[class*="播放"]',
                    '[class*="view"] [class*="num"]',
                ],
                "like_count": [
                    '[class*="like"] [class*="count"]', '[class*="点赞"]',
                    '[class*="digg"] [class*="num"]',
                ],
                "comment_count": [
                    '[class*="comment"] [class*="count"]', '[class*="评论"]',
                    '[class*="reply"] [class*="num"]',
                ],
                "share_count": [
                    '[class*="share"] [class*="count"]', '[class*="分享"]',
                    '[class*="forward"] [class*="num"]',
                ],
            }

            import re
            for stat_name, sel_list in stat_selectors.items():
                for sel in sel_list:
                    try:
                        el = await self._page.wait_for_selector(sel, timeout=3000)
                        if el:
                            text = (await el.inner_text()).strip()
                            # Extract numbers: "1.2万" → 12000, "3,456" → 3456
                            nums = re.findall(r'[\d,.]+万?', text)
                            if nums:
                                val_str = nums[0].replace(",", "")
                                if "万" in val_str:
                                    stats[stat_name] = int(float(val_str.replace("万", "")) * 10000)
                                else:
                                    stats[stat_name] = int(float(val_str))
                            break
                    except Exception:
                        continue

            # 策略3: 从 URL 确认内容状态
            current_url = self._page.url
            if "404" in page_text.lower() or "不存在" in page_text or "已删除" in page_text:
                status = "deleted"
            elif "审核" in page_text and ("通过" not in page_text):
                status = "under_review"
            elif any(kw in page_text.lower() for kw in ["禁止", "违规", "下架"]):
                status = "violation"
            elif stats["play_count"] > 0:
                status = "published"
            elif "content" in current_url or "video" in current_url:
                status = "published"  # 内容页存在但数据未加载
            else:
                status = "unknown"

            await self._close_browser_context()

            return {
                "platform": "douyin",
                "post_id": platform_post_id,
                "status": status,
                "post_url": f"https://www.douyin.com/video/{platform_post_id}",
                "stats": stats,
                "message": (
                    f"播放={stats['play_count']}, 点赞={stats['like_count']}, "
                    f"评论={stats['comment_count']}, 分享={stats['share_count']}"
                ),
            }

        except Exception as e:
            logger.warning(f"get_status 失败: {e}")
            await self._close_browser_context()
            return {
                "platform": "douyin",
                "post_id": platform_post_id,
                "status": "unknown",
                "message": f"状态查询失败: {str(e)[:100]}",
            }
