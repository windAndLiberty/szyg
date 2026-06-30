"""
Version-Locked Browser Pool — Persistent-context Playwright automation.

Uses Playwright's bundled Chromium (not system Chrome) for version-locked
protocol compliance. Each platform account gets a dedicated persistent context
with isolated storage for automatic cookie/session persistence.

Key capabilities:
  - launch_persistent_context with storage isolation per account
  - QR code login handler (navigate, capture QR, await scan, save state)
  - Anti-detection: navigator.webdriver override, stealth injection
  - Crash recovery and idle context cleanup
"""
import asyncio
import base64
import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────

IDLE_TIMEOUT = 600       # 10 min idle before auto-close
MAX_CONTEXTS = 6         # Max concurrent persistent contexts
CLEANUP_INTERVAL = 300   # Every 5 min
QR_TIMEOUT_SECONDS = 120 # QR login scan window

# ── Platform login URLs ──────────────────────────────────

PLATFORM_LOGIN_URLS = {
    "douyin": "https://creator.douyin.com/creator-micro/home",
    "xhs": "https://creator.xiaohongshu.com/login",
    "kuaishou": "https://cp.kuaishou.com/",
    "bilibili": "https://member.bilibili.com/platform/home",
    "weibo": "https://weibo.com/login.php",
}

# ── QR code selectors per platform ───────────────────────

QR_SELECTORS = {
    "douyin": [
        'img[class*="qrcode"]',
        'img[src*="qrcode"]',
        'img[src*="qr"]',
        '.qrcode-img img',
        '.qrcode img',
        'img[class*="qr"]',
    ],
    "xhs": [
        'img[class*="qr"]',
        'img[src*="qrcode"]',
        '.qrcode-img img',
        '.login-qr img',
    ],
    "kuaishou": [
        'img[class*="qr"]',
        'img[src*="qr"]',
        '.qrcode img',
    ],
    "bilibili": [
        'img[class*="qr"]',
        'img[src*="qrcode"]',
        '.qrcode-img img',
        '.login-qrcode img',
    ],
    "weibo": [
        'img[class*="qr"]',
        'img[src*="qrcode"]',
        '.qrcode img',
        '.WB_qrcode img',
    ],
}

# ── Post-login success indicators ────────────────────────

LOGIN_SUCCESS_INDICATORS = [
    '//span[contains(text(), "创作者")]',
    '//div[contains(@class, "creator")]',
    '//div[contains(@class, "user-info")]',
    '//span[contains(text(), "发布")]',
    '//a[contains(text(), "首页")]',
    '//div[contains(@class, "home")]',
]


class VersionLockedBrowserPool:
    """
    Singleton browser pool using Playwright's native bundled Chromium.

    Each platform account gets a launch_persistent_context with its own
    user_data_dir → cookies/storage auto-persisted to disk.
    """

    def __init__(self, storage_root: str = None):
        self._playwright = None
        self._contexts: dict[str, dict] = {}  # key → {context, last_used}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._storage_root = Path(storage_root or os.path.join(
            os.path.dirname(__file__), "..", "..", "storage", "profiles"
        )).resolve()
        self._chromium_exe: Optional[str] = None  # Cached executable path

    def _resolve_chromium_path(self) -> str | None:
        """Resolve bundled or system Chromium executable path."""
        if self._chromium_exe:
            return self._chromium_exe

        # 1. Bundled: server/szyg/storage/chromium/
        bundled_base = Path(__file__).resolve().parent.parent / "storage" / "chromium"
        if bundled_base.exists():
            for d in sorted(bundled_base.iterdir(), reverse=True):
                if d.is_dir() and d.name.startswith("chromium-"):
                    for sub in ["chrome-win64", "chrome-win"]:
                        exe = d / sub / "chrome.exe"
                        if exe.exists():
                            self._chromium_exe = str(exe)
                            logger.info(f"BrowserPoolV2: bundled Chromium → {exe}")
                            return self._chromium_exe

        # 2. System: %LOCALAPPDATA%/ms-playwright/
        try:
            from szyg.api.infra_routes import get_chromium_executable_path
            exe = get_chromium_executable_path()
            if exe:
                self._chromium_exe = exe
                logger.info(f"BrowserPoolV2: system Chromium → {exe}")
                return self._chromium_exe
        except Exception:
            pass

        # 3. Let Playwright auto-resolve
        logger.info("BrowserPoolV2: letting Playwright auto-resolve Chromium")
        return None

    # ── Context management ───────────────────────────────

    def _profile_dir(self, platform: str, account_id: str) -> Path:
        """Return the isolated storage directory for a platform account."""
        return self._storage_root / f"{platform}_{account_id}"

    async def get_context(self, platform: str, account_id: str = "default") -> object:
        """
        Get or create a persistent browser context for the given account.

        Uses launch_persistent_context so cookies, localStorage, and sessions
        are automatically persisted to disk — no manual save/restore needed.
        """
        key = f"{platform}_{account_id}"
        async with self._lock:
            # Return existing if alive
            if key in self._contexts:
                entry = self._contexts[key]
                ctx = entry["context"]
                try:
                    _ = ctx.pages
                    entry["last_used"] = time.time()
                    logger.debug(f"BrowserPoolV2: reuse context for {key}")
                    return ctx
                except Exception:
                    logger.info(f"BrowserPoolV2: context {key} dead, recreating")
                    del self._contexts[key]

            # Enforce max contexts
            if len(self._contexts) >= MAX_CONTEXTS:
                oldest = min(self._contexts, key=lambda k: self._contexts[k]["last_used"])
                logger.info(f"BrowserPoolV2: evicting {oldest}")
                try:
                    await self._contexts[oldest]["context"].close()
                except Exception:
                    pass
                del self._contexts[oldest]

            # Lazy-start playwright
            if not self._playwright:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()

            # Create persistent context
            profile_dir = self._profile_dir(platform, account_id)
            profile_dir.mkdir(parents=True, exist_ok=True)

            from szyg.platforms.anti_detect import get_persistent_context_config
            config = get_persistent_context_config(
                str(profile_dir),
                executable_path=self._resolve_chromium_path(),
            )

            ctx = await self._playwright.chromium.launch_persistent_context(**config)

            # Inject webdriver override into every new page
            ctx.on("page", lambda page: asyncio.ensure_future(
                self._on_page_created(page)
            ))

            self._contexts[key] = {
                "context": ctx,
                "last_used": time.time(),
            }
            logger.info(f"BrowserPoolV2: persistent context for {key} (dir={profile_dir})")
            return ctx

    async def _on_page_created(self, page):
        """Inject anti-detection into every newly created page."""
        try:
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        except Exception:
            pass

    async def close_context(self, platform: str, account_id: str = "default"):
        """Close and remove a persistent context."""
        key = f"{platform}_{account_id}"
        async with self._lock:
            if key in self._contexts:
                try:
                    await self._contexts[key]["context"].close()
                except Exception:
                    pass
                del self._contexts[key]
                logger.info(f"BrowserPoolV2: closed {key}")

    # ── QR Code Login ────────────────────────────────────

    async def handle_qr_login(
        self,
        platform: str,
        account_id: str = "default",
        timeout: int = QR_TIMEOUT_SECONDS,
    ) -> dict:
        """
        Open the platform login page, extract QR code image, wait for user
        to scan, and return the result.

        Returns:
            {"success": True, "account_id": str, "cookies": int}
         or
            {"success": False, "error": str}
        """
        ctx = await self.get_context(platform, account_id)
        pages = ctx.pages
        page = pages[0] if pages else await ctx.new_page()

        login_url = PLATFORM_LOGIN_URLS.get(platform)
        if not login_url:
            return {"success": False, "error": f"Unknown platform: {platform}"}

        try:
            # Navigate to login page
            await page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # Let JS render the QR code

            # Try to find QR code image
            qr_data = None
            selectors = QR_SELECTORS.get(platform, QR_SELECTORS["douyin"])
            for sel in selectors:
                try:
                    el = await page.wait_for_selector(sel, state="attached", timeout=5000)
                    if el:
                        qr_src = await el.get_attribute("src")
                        if qr_src:
                            qr_data = {
                                "type": "url" if qr_src.startswith("http") else "base64",
                                "data": qr_src,
                            }
                            break
                except Exception:
                    continue

            if not qr_data:
                # Fallback: screenshot the whole page as a QR reference
                screenshot_bytes = await page.screenshot(type="png")
                qr_data = {
                    "type": "screenshot",
                    "data": base64.b64encode(screenshot_bytes).decode("utf-8"),
                }

            # Wait for login success (poll for indicators)
            logged_in = False
            deadline = time.time() + timeout
            while time.time() < deadline:
                await asyncio.sleep(2)
                for indicator in LOGIN_SUCCESS_INDICATORS:
                    try:
                        el = await page.wait_for_selector(indicator, state="attached", timeout=2000)
                        if el:
                            logged_in = True
                            break
                    except Exception:
                        continue
                if logged_in:
                    break
                # Also check URL change (e.g., redirected away from login)
                current_url = page.url
                if "login" not in current_url.lower() and "signin" not in current_url.lower():
                    logged_in = True
                    break

            if logged_in:
                # Storage auto-persisted by persistent context — no manual save needed
                return {"success": True, "account_id": account_id, "cookies": "persisted"}
            else:
                return {"success": False, "error": f"QR scan timeout ({timeout}s)"}

        except Exception as e:
            logger.error(f"QR login error ({platform}/{account_id}): {e}")
            return {"success": False, "error": str(e)}

    # ── Credential (Account/Password) Login ──────────────

    async def handle_credential_login(
        self,
        platform: str,
        username: str,
        password: str,
        account_id: str = "default",
    ) -> dict:
        """
        Perform account/password credential login on the target platform.

        1. Open login page with persistent context
        2. Switch from QR default to password/credentials tab
        3. Fill username + password with human-like typing
        4. Handle captcha interception (pause for manual solve)
        5. Detect login success and flush session state

        Returns:
            {"success": True, "account_id": str}
         or {"success": False, "error": str, "captcha_required": bool}
        """
        ctx = await self.get_context(platform, account_id)
        pages = ctx.pages
        page = pages[0] if pages else await ctx.new_page()

        login_url = PLATFORM_LOGIN_URLS.get(platform)
        if not login_url:
            return {"success": False, "error": f"Unknown platform: {platform}"}

        from szyg.platforms.anti_detect import HumanBehavior

        try:
            # 1. Navigate to login page
            await page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)  # Let JS fully render the login form

            # Dismiss any initial overlays
            await self._dismiss_overlays(page)

            # 2. Switch to password/credentials tab
            password_tab_selectors = [
                'text=密码登录',
                'text=账号密码',
                'text=密码',
                'text=验证码登录',
                'text=短信登录',
                '[class*="password"]',
                '[class*="pwd"]',
                'a:has-text("密码")',
                'span:has-text("密码")',
                'div:has-text("密码")',
            ]
            switched = False
            for sel in password_tab_selectors:
                try:
                    el = await page.wait_for_selector(sel, state="visible", timeout=3000)
                    if el:
                        await el.click(timeout=3000)
                        await asyncio.sleep(1.5)
                        switched = True
                        logger.info(f"CredentialLogin: switched to password tab via '{sel}'")
                        break
                except Exception:
                    continue

            if not switched:
                logger.info("CredentialLogin: no password tab found, assuming form already visible")

            # 3. Locate and fill username field
            username_selectors = [
                'input[type="text"]',
                'input[name*="user"]',
                'input[name*="account"]',
                'input[name*="phone"]',
                'input[name*="mobile"]',
                'input[placeholder*="手机"]',
                'input[placeholder*="账号"]',
                'input[placeholder*="用户名"]',
                'input[placeholder*="邮箱"]',
                'input[class*="user"]',
                'input[class*="phone"]',
            ]
            username_el = None
            for sel in username_selectors:
                try:
                    username_el = await page.wait_for_selector(sel, state="visible", timeout=3000)
                    if username_el:
                        break
                except Exception:
                    continue

            if not username_el:
                return {"success": False, "error": "无法定位用户名输入框 — 平台UI可能已变更"}

            await HumanBehavior.type_in_element(username_el, username, min_delay=60, max_delay=180)

            # 4. Locate and fill password field
            password_selectors = [
                'input[type="password"]',
                'input[name*="password"]',
                'input[name*="pwd"]',
                'input[placeholder*="密码"]',
                'input[class*="password"]',
                'input[class*="pwd"]',
            ]
            password_el = None
            for sel in password_selectors:
                try:
                    password_el = await page.wait_for_selector(sel, state="visible", timeout=3000)
                    if password_el:
                        break
                except Exception:
                    continue

            if not password_el:
                return {"success": False, "error": "无法定位密码输入框 — 平台UI可能已变更"}

            await HumanBehavior.type_in_element(password_el, password, min_delay=60, max_delay=180)

            # 5. Click submit/login button
            submit_selectors = [
                'button:has-text("登录")',
                'button:has-text("登 录")',
                'button:has-text("立即登录")',
                '[class*="login-btn"]',
                '[class*="submit"]',
                'button[type="submit"]',
                'a:has-text("登录")',
                'div:has-text("登录")',
            ]
            submitted = False
            for sel in submit_selectors:
                try:
                    el = await page.wait_for_selector(sel, state="visible", timeout=3000)
                    if el:
                        await el.click(timeout=3000)
                        await asyncio.sleep(2)
                        submitted = True
                        logger.info(f"CredentialLogin: clicked submit via '{sel}'")
                        break
                except Exception:
                    continue

            if not submitted:
                # Fallback: press Enter in the password field
                await password_el.press("Enter")
                await asyncio.sleep(2)

            # 6. Check for captcha
            from szyg.platforms.anti_detect import detect_slider
            captcha_detected = await detect_slider(page)
            if captcha_detected:
                logger.warning(f"CredentialLogin: captcha detected for {platform}/{account_id}")
                return {
                    "success": False,
                    "error": "检测到验证码，请使用扫码登录或手动在浏览器中完成验证",
                    "captcha_required": True,
                }

            # 7. Wait for login success
            logged_in = False
            deadline = time.time() + 60  # 60s timeout for password login

            while time.time() < deadline:
                await asyncio.sleep(2)
                for indicator in LOGIN_SUCCESS_INDICATORS:
                    try:
                        el = await page.wait_for_selector(indicator, state="attached", timeout=2000)
                        if el:
                            logged_in = True
                            break
                    except Exception:
                        continue
                if logged_in:
                    break
                current_url = page.url
                if "login" not in current_url.lower() and "signin" not in current_url.lower():
                    logged_in = True
                    break

            if logged_in:
                # Wait for network idle so storage is fully flushed
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await asyncio.sleep(2)
                return {"success": True, "account_id": account_id, "cookies": "persisted"}
            else:
                return {"success": False, "error": "登录超时 — 可能是账号密码错误或需要额外验证"}

        except Exception as e:
            logger.error(f"CredentialLogin error ({platform}/{account_id}): {e}")
            return {"success": False, "error": str(e)}

    async def _dismiss_overlays(self, page):
        """Dismiss popups/overlays on the page."""
        overlay_selectors = [
            'div[class*="close"]', 'span[class*="close"]',
            'button[class*="close"]', 'div[class*="mask"]',
            '[aria-label="关闭"]', '[aria-label="close"]',
            '.modal-close', '.dialog-close',
        ]
        for sel in overlay_selectors:
            try:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    try:
                        if await el.is_visible():
                            await el.click(timeout=2000)
                            await asyncio.sleep(0.3)
                    except Exception:
                        continue
            except Exception:
                continue

    # ── Cleanup ──────────────────────────────────────────

    async def _cleanup_loop(self):
        """Periodically close idle contexts."""
        while self._running:
            await asyncio.sleep(CLEANUP_INTERVAL)
            now = time.time()
            async with self._lock:
                to_remove = [
                    k for k, v in self._contexts.items()
                    if now - v["last_used"] > IDLE_TIMEOUT
                ]
                for key in to_remove:
                    try:
                        await self._contexts[key]["context"].close()
                    except Exception:
                        pass
                    del self._contexts[key]
                    logger.info(f"BrowserPoolV2: auto-closed idle {key}")
                if to_remove:
                    logger.info(
                        f"BrowserPoolV2: cleaned {len(to_remove)} idle, "
                        f"{len(self._contexts)} remaining"
                    )

    async def start(self):
        """Start the cleanup loop."""
        if not self._running:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("BrowserPoolV2: started")

    async def stop(self):
        """Close all contexts and stop."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            for key, entry in list(self._contexts.items()):
                try:
                    await entry["context"].close()
                except Exception:
                    pass
            self._contexts.clear()

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        logger.info("BrowserPoolV2: stopped")

    @property
    def context_count(self) -> int:
        return len(self._contexts)

    def __repr__(self) -> str:
        return f"<VersionLockedBrowserPool contexts={len(self._contexts)}>"


# ── Singleton ────────────────────────────────────────────

_pool_v2: Optional[VersionLockedBrowserPool] = None


def get_browser_pool_v2() -> VersionLockedBrowserPool:
    """Get the singleton version-locked browser pool."""
    global _pool_v2
    if _pool_v2 is None:
        _pool_v2 = VersionLockedBrowserPool()
    return _pool_v2
