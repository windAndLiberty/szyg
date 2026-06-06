"""
Anti-Detection Module — 浏览器反检测 + 人类行为模拟

对标数创引擎:
  - core/stealth.min.js → inject_stealth()
  - core/browser_helper.pyd → human_type(), human_mouse_move()
  - core/input_guard.pyd → keyboard_lock 概念 (简化为 async lock)

实现策略:
  1. 注入 stealth.min.js (puppeteer-extra stealth 插件)
  2. 模拟人类打字速度 (100-300ms/字符随机变化)
  3. 模拟人类鼠标移动 (贝塞尔曲线轨迹)
  4. 随机页面滚动 (模拟浏览行为)
  5. 浏览器指纹伪装 (WebGL, Canvas, 语言, 时区等)
"""
import asyncio
import random
import math
import os
from pathlib import Path
from typing import Optional

_STEALTH_JS: str | None = None


def _load_stealth_js() -> str:
    """加载 stealth.min.js 内容 (缓存)"""
    global _STEALTH_JS
    if _STEALTH_JS is not None:
        return _STEALTH_JS

    # 查找 stealth.min.js
    search_paths = [
        Path(__file__).parent / "stealth.min.js",
        Path(__file__).parent.parent.parent / "core" / "stealth.min.js",
    ]
    for p in search_paths:
        if p.exists():
            _STEALTH_JS = p.read_text(encoding="utf-8")
            return _STEALTH_JS

    # Fallback: 内置精简版 stealth 脚本
    _STEALTH_JS = _BUILTIN_STEALTH
    return _STEALTH_JS


# ── 反检测 Context 配置 ─────────────────────────────────────

def get_stealth_context_config() -> dict:
    """
    返回 Playwright browser.new_context() 的反检测配置。

    对标数创引擎 state.json 中的设备指纹数据。
    """
    return {
        "viewport": {"width": 1536, "height": 864},
        "device_scale_factor": 1,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "geolocation": {"longitude": 121.4737, "latitude": 31.2304},  # Shanghai
        "permissions": ["geolocation"],
        "color_scheme": "light",
        "extra_http_headers": {
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    }


def get_launch_config(headless: bool = False) -> dict:
    """
    返回 Playwright browser.launch() 配置。

    headless=False: 使用有头模式避免检测 (对标数创引擎做法)
    """
    return {
        "headless": headless,
        "channel": "chrome",  # 使用系统安装的 Chrome (而非 Chromium)
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--window-size=1536,864",
            "--window-position=0,0",
        ],
    }


# ── Stealth 注入 ────────────────────────────────────────────

async def inject_stealth(page) -> None:
    """
    注入 stealth.min.js 到页面。

    调用时机: page.goto() 之前 (通过 page.add_init_script())
    对标: 数创引擎 core/douyin.pyd 中的 set_init_script()

    覆盖的检测点:
    - navigator.webdriver → false
    - navigator.plugins → 非空数组
    - navigator.languages → ['zh-CN', 'zh', 'en']
    - window.chrome → { runtime: {} }
    - Permissions.query → 正常返回值
    - WebGL vendor → "Google Inc."
    - Canvas fingerprint → 添加轻微噪声
    """
    stealth_js = _load_stealth_js()
    await page.add_init_script(stealth_js)


# ── 人类行为模拟 ────────────────────────────────────────────

class HumanBehavior:
    """模拟人类操作行为，绕过行为检测"""

    @staticmethod
    async def type_text(page, selector: str, text: str,
                        min_delay: int = 80, max_delay: int = 300) -> None:
        """
        模拟人类打字: 逐字符输入，带随机延迟。

        Args:
            page: Playwright Page
            selector: 目标元素选择器
            text: 要输入的文本
            min_delay: 最小字符间延迟 (ms)
            max_delay: 最大字符间延迟 (ms)
        """
        element = await page.wait_for_selector(selector, state="visible", timeout=10000)
        await element.click()
        await asyncio.sleep(random.uniform(0.2, 0.5))

        for i, char in enumerate(text):
            await page.keyboard.type(char, delay=random.randint(min_delay, max_delay))

            # 偶尔模拟思考停顿 (每 20-40 个字符)
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.5, 1.5))

            # 极低概率模拟打错字 + 退格 (每 ~200 字符)
            if random.random() < 0.005:
                wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                await page.keyboard.type(wrong_char, delay=50)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.1, 0.2))

    @staticmethod
    async def type_in_element(element, text: str,
                               min_delay: int = 80, max_delay: int = 300) -> None:
        """在已定位的 Playwright ElementHandle 上逐字符输入文本"""
        await element.click()
        await asyncio.sleep(random.uniform(0.1, 0.3))
        for char in text:
            await element.type(char, delay=random.randint(min_delay, max_delay))

    @staticmethod
    async def mouse_move_to(page, target_selector: str,
                            steps: int = 25, duration_ms: int = 500) -> None:
        """
        模拟人类鼠标移动 (贝塞尔曲线)。

        Args:
            page: Playwright Page
            target_selector: 目标元素
            steps: 移动步数
            duration_ms: 总移动时间
        """
        target = await page.wait_for_selector(target_selector, state="visible", timeout=10000)
        box = await target.bounding_box()
        if not box:
            return

        # 起点: 页面随机位置
        viewport = page.viewport_size or {"width": 1536, "height": 864}
        start_x = random.randint(0, viewport["width"])
        start_y = random.randint(0, viewport["height"])

        # 终点: 目标元素中心 + 随机偏移
        end_x = box["x"] + box["width"] / 2 + random.uniform(-10, 10)
        end_y = box["y"] + box["height"] / 2 + random.uniform(-5, 5)

        # 控制点: 贝塞尔曲线弯曲
        cp_x = (start_x + end_x) / 2 + random.uniform(-100, 100)
        cp_y = (start_y + end_y) / 2 + random.uniform(-50, 50)

        step_time = duration_ms / steps
        for i in range(steps + 1):
            t = i / steps
            # Quadratic Bezier: B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2
            x = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * cp_x + t ** 2 * end_x
            y = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * cp_y + t ** 2 * end_y
            await page.mouse.move(x, y)
            await asyncio.sleep(step_time / 1000)

    @staticmethod
    async def random_scroll(page, min_scrolls: int = 2, max_scrolls: int = 5) -> None:
        """
        模拟人类随机滚动页面。
        使用场景: 发布前浏览"确认"页面内容。
        """
        for _ in range(random.randint(min_scrolls, max_scrolls)):
            direction = random.choice([-1, 1])
            distance = random.randint(200, 600) * direction
            await page.evaluate(f"window.scrollBy(0, {distance})")
            await asyncio.sleep(random.uniform(0.5, 1.5))

    @staticmethod
    async def random_delay(min_seconds: float = 0.3, max_seconds: float = 2.0) -> None:
        """随机等待 (模拟思考/阅读时间)"""
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))

    @staticmethod
    async def move_and_click(page, selector: str) -> None:
        """先移动到元素再点击 (更人类化)"""
        await HumanBehavior.mouse_move_to(page, selector, steps=random.randint(15, 30))
        element = await page.wait_for_selector(selector, state="visible", timeout=10000)
        await element.click(delay=random.randint(50, 200))


# ── 内置精简版 Stealth 脚本 ─────────────────────────────────

_BUILTIN_STEALTH = r"""
// Mini stealth.js — 覆盖最常见的自动化检测点
// 完整版请使用 stealth.min.js (从数创引擎提取的 puppeteer-extra stealth)

(function() {
    'use strict';

    // 1. navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => false,
    });

    // 2. chrome runtime
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {},
    };

    // 3. plugins
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });

    // 4. languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en'],
    });

    // 5. Permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
    );

    // 6. 覆盖 navigator.hardwareConcurrency
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8,
    });

    // 7. 覆盖 deviceMemory
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
    });

    // 8. 覆盖 platform
    Object.defineProperty(navigator, 'platform', {
        get: () => 'Win32',
    });

    console.log('[stealth] injected');
})();
"""
