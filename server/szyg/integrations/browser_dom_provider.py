"""Managed Playwright DOM provider for computer-use browser tasks."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from szyg.data_path import DATA_DIR

BROWSER_KEY = "computer_use"
ARTIFACT_DIR = DATA_DIR / "computer_use"
SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"


def _now() -> str:
    return datetime.now().isoformat()


class BrowserDomProvider:
    """DOM-level browser automation through the shared Playwright browser pool."""

    def __init__(self) -> None:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._context = None
        self._page = None

    async def health(self) -> dict:
        try:
            import playwright  # noqa: F401

            return {
                "available": True,
                "managed": self._page is not None,
                "message": "Playwright 浏览器 DOM 能力可用",
            }
        except Exception as exc:
            return {
                "available": False,
                "managed": False,
                "message": f"Playwright 不可用：{exc}",
            }

    async def _ensure_page(self, url: str = ""):
        if self._page:
            try:
                if not self._page.is_closed():
                    if url:
                        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    return self._page
            except Exception:
                self._page = None
        from szyg.platforms.browser_pool import get_browser_pool

        pool = get_browser_pool(headless=False)
        self._context = await pool.get_context(BROWSER_KEY)
        pages = [page for page in self._context.pages if not page.is_closed()]
        self._page = pages[0] if pages else await self._context.new_page()
        if url:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return self._page

    async def _invalidate_page(self) -> None:
        self._page = None
        self._context = None
        try:
            from szyg.platforms.browser_pool import get_browser_pool

            await get_browser_pool(headless=False).invalidate_context(BROWSER_KEY)
        except Exception:
            pass

    async def open_url(self, url: str) -> dict:
        if not url:
            return {"success": False, "message": "缺少 URL", "error_code": "invalid_request"}
        try:
            await self._ensure_page(url)
            observation = await self.observe()
            return {"success": True, "message": f"已打开网页：{url}", "url": url, "observation": observation}
        except Exception as first_exc:
            await self._invalidate_page()
            try:
                await self._ensure_page(url)
                observation = await self.observe()
                return {
                    "success": True,
                    "message": f"已重新启动托管浏览器并打开网页：{url}",
                    "url": url,
                    "observation": observation,
                    "recovered_from": str(first_exc),
                }
            except Exception as exc:
                return {"success": False, "message": str(exc), "error_code": "browser_open_failed", "url": url}

    async def observe(self, limit: int = 120) -> dict:
        health = await self.health()
        if not health.get("available"):
            return {"ok": False, "elements": [], "source_counts": {}, "message": health.get("message", "Playwright 不可用")}
        if not self._page:
            return {"ok": False, "elements": [], "source_counts": {}, "message": "尚无托管浏览器页面"}
        try:
            page = await self._ensure_page()
            elements = await page.evaluate(
                """
                (limit) => {
                  const selectorParts = (el) => {
                    if (el.id) return [`#${CSS.escape(el.id)}`];
                    if (el.getAttribute('data-testid')) return [`[data-testid="${CSS.escape(el.getAttribute('data-testid'))}"]`];
                    if (el.getAttribute('aria-label')) return [`${el.tagName.toLowerCase()}[aria-label="${CSS.escape(el.getAttribute('aria-label'))}"]`];
                    if (el.getAttribute('name')) return [`${el.tagName.toLowerCase()}[name="${CSS.escape(el.getAttribute('name'))}"]`];
                    const path = [];
                    let node = el;
                    while (node && node.nodeType === Node.ELEMENT_NODE && path.length < 5) {
                      let part = node.tagName.toLowerCase();
                      if (node.classList && node.classList.length) {
                        part += '.' + Array.from(node.classList).slice(0, 2).map((v) => CSS.escape(v)).join('.');
                      }
                      const parent = node.parentElement;
                      if (parent) {
                        const same = Array.from(parent.children).filter((child) => child.tagName === node.tagName);
                        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
                      }
                      path.unshift(part);
                      node = parent;
                    }
                    return [path.join(' > ')];
                  };
                  const roleOf = (el) => {
                    const explicit = el.getAttribute('role');
                    if (explicit) return explicit;
                    const tag = el.tagName.toLowerCase();
                    if (tag === 'a') return 'link';
                    if (tag === 'button') return 'button';
                    if (tag === 'textarea') return 'textbox';
                    if (tag === 'select') return 'combobox';
                    if (tag === 'input') {
                      const type = (el.getAttribute('type') || 'text').toLowerCase();
                      if (['button', 'submit', 'reset'].includes(type)) return 'button';
                      if (['checkbox', 'radio', 'range'].includes(type)) return type;
                      return 'textbox';
                    }
                    return tag;
                  };
                  const nameOf = (el) => {
                    return (
                      el.getAttribute('aria-label') ||
                      el.getAttribute('placeholder') ||
                      el.getAttribute('title') ||
                      el.innerText ||
                      el.value ||
                      el.textContent ||
                      ''
                    ).trim().replace(/\\s+/g, ' ').slice(0, 160);
                  };
                  const candidates = Array.from(document.querySelectorAll(
                    'a,button,input,textarea,select,[role],[contenteditable="true"],[tabindex],[onclick],[data-testid]'
                  ));
                  const rows = [];
                  for (const el of candidates) {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const visible = style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
                    if (!visible) continue;
                    rows.push({
                      source: 'dom',
                      role: roleOf(el),
                      name: nameOf(el),
                      selector: selectorParts(el)[0],
                      bounds: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
                      confidence: 0.95,
                      actionable: true,
                    });
                    if (rows.length >= limit) break;
                  }
                  return rows;
                }
                """,
                limit,
            )
            screenshot = await self.screenshot()
            return {
                "ok": True,
                "url": page.url,
                "title": await page.title(),
                "elements": elements,
                "element_count": len(elements),
                "source_counts": {"dom": len(elements)},
                "screenshot": screenshot,
                "summary": f"网页：{await page.title() or page.url}；DOM 控件 {len(elements)} 个",
                "created_at": _now(),
            }
        except Exception as exc:
            return {"ok": False, "elements": [], "source_counts": {}, "message": str(exc), "error_code": "browser_observe_failed"}

    async def screenshot(self) -> dict:
        if not self._page:
            return {"ok": False, "path": "", "message": "尚无托管浏览器页面"}
        path = SCREENSHOT_DIR / f"browser_{uuid.uuid4().hex[:10]}.png"
        try:
            await self._page.screenshot(path=str(path), full_page=False)
            return {"ok": True, "path": str(path), "created_at": _now()}
        except Exception as exc:
            return {"ok": False, "path": "", "message": str(exc), "created_at": _now()}

    async def click(self, target: str) -> dict:
        if not target:
            return {"success": False, "message": "缺少点击目标", "error_code": "invalid_request"}
        try:
            page = await self._ensure_page()
            locator = page.locator(target).first
            await locator.click(timeout=10000)
            return {"success": True, "message": f"已点击网页元素：{target}", "provider": "playwright", "selector": target}
        except Exception as exc:
            return {"success": False, "message": str(exc), "error_code": "click_failed", "provider": "playwright", "selector": target}

    async def type_text(self, target: str, text: str) -> dict:
        if not target:
            return {"success": False, "message": "缺少输入目标", "error_code": "invalid_request"}
        try:
            page = await self._ensure_page()
            locator = page.locator(target).first
            await locator.fill(text, timeout=10000)
            return {"success": True, "message": "已向网页输入文字", "provider": "playwright", "selector": target}
        except Exception:
            try:
                page = await self._ensure_page()
                await page.locator(target).first.click(timeout=10000)
                await page.keyboard.type(text)
                return {"success": True, "message": "已向网页输入文字", "provider": "playwright", "selector": target}
            except Exception as exc:
                return {"success": False, "message": str(exc), "error_code": "type_failed", "provider": "playwright", "selector": target}

    async def upload_file(self, target: str, file_path: str) -> dict:
        if not target or not file_path:
            return {"success": False, "message": "缺少上传控件或文件路径", "error_code": "invalid_request"}
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "message": f"文件不存在：{file_path}", "error_code": "material_missing"}
        try:
            page = await self._ensure_page()
            await page.locator(target).first.set_input_files(str(path), timeout=10000)
            return {"success": True, "message": "已选择网页上传文件", "provider": "playwright", "selector": target, "file_path": str(path)}
        except Exception as exc:
            return {"success": False, "message": str(exc), "error_code": "upload_failed", "provider": "playwright", "selector": target}

    async def wait_for(self, target: str, timeout_ms: int = 10000) -> dict:
        try:
            page = await self._ensure_page()
            if target:
                await page.locator(target).first.wait_for(state="visible", timeout=timeout_ms)
                message = f"已等待网页元素出现：{target}"
            else:
                await page.wait_for_load_state("networkidle", timeout=timeout_ms)
                message = "已等待网页加载稳定"
            return {"success": True, "message": message, "provider": "playwright", "selector": target}
        except Exception as exc:
            return {"success": False, "message": str(exc), "error_code": "wait_failed", "provider": "playwright", "selector": target}

    async def verify(self, expected_result: str = "", target: str = "") -> dict:
        try:
            page = await self._ensure_page()
            if target:
                visible = await page.locator(target).first.is_visible(timeout=5000)
                return {"success": bool(visible), "message": "网页目标元素可见" if visible else "网页目标元素不可见", "provider": "playwright", "selector": target}
            if expected_result:
                visible = await page.get_by_text(expected_result, exact=False).first.is_visible(timeout=5000)
                return {"success": bool(visible), "message": "网页文本验证通过" if visible else "未找到预期网页文本", "provider": "playwright", "expected_result": expected_result}
            return {"success": True, "message": "未配置网页验证条件，已记录执行后观察", "provider": "playwright"}
        except Exception as exc:
            return {"success": False, "message": str(exc), "error_code": "verification_uncertain", "provider": "playwright"}

    async def execute_action(self, action: dict[str, Any]) -> dict:
        kind = str(action.get("action") or "").strip()
        target = str(action.get("target") or action.get("selector") or "").strip()
        if kind == "open_url":
            return await self.open_url(str(action.get("url") or action.get("value") or target))
        if kind == "click":
            return await self.click(target)
        if kind == "type":
            return await self.type_text(target, str(action.get("text") or action.get("value") or ""))
        if kind == "upload_file":
            return await self.upload_file(target, str(action.get("file_path") or action.get("value") or ""))
        if kind == "wait_for":
            return await self.wait_for(target)
        if kind == "verify":
            return await self.verify(str(action.get("value") or ""), target)
        return {"success": False, "message": f"浏览器不支持动作：{kind}", "error_code": "unsupported_action", "provider": "playwright"}

    async def cleanup(self) -> dict:
        try:
            from szyg.platforms.browser_pool import get_browser_pool

            await get_browser_pool(headless=False).return_context(BROWSER_KEY)
            return {"success": True, "message": "browser DOM provider cleaned up"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}


_provider: BrowserDomProvider | None = None


def get_browser_dom_provider() -> BrowserDomProvider:
    global _provider
    if _provider is None:
        _provider = BrowserDomProvider()
    return _provider
