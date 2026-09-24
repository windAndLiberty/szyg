"""GEO consumer-surface sampling through the existing visible sidebar browser.

This module deliberately reuses the Electron ``WebContentsView`` controlled by
``szyg_browser``. It does not launch Playwright, a headless browser, or a cloud
inference request. Login cookies stay in Electron's persistent browser session.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any

from szyg.hermes_browser import _browser_action


PLATFORMS: dict[str, dict[str, str]] = {
    "deepseek": {"label": "DeepSeek", "url": "https://chat.deepseek.com/"},
    "doubao": {"label": "豆包", "url": "https://www.doubao.com/chat/"},
    "openai": {"label": "ChatGPT", "url": "https://chatgpt.com/"},
    "perplexity": {"label": "Perplexity", "url": "https://www.perplexity.ai/"},
    "gemini": {"label": "Google Gemini", "url": "https://gemini.google.com/app"},
}

COMPOSER_WORDS = (
    "问点什么", "输入问题", "发送消息", "向 deepseek", "向 chatgpt", "询问 gemini",
    "ask anything", "ask a follow-up", "message", "prompt", "type your",
)
SEND_WORDS = ("发送", "提交", "send", "submit", "ask")
NOISE_TEXT = re.compile(
    r"^(?:新对话|历史记录|登录|注册|分享|复制|重新生成|停止生成|deepseek|chatgpt|perplexity|gemini|豆包)$",
    re.I,
)


class GeoBrowserError(RuntimeError):
    def __init__(self, message: str, *, code: str = "browser_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class BrowserAnswer:
    answer: str
    citations: list[dict[str, str]]
    url: str
    title: str


def _clean(value: Any, limit: int = 30000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _answer_text(value: Any, limit: int = 30000) -> str:
    lines = [re.sub(r"[\t ]+", " ", line).strip() for line in str(value or "").replace("\r", "").split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:limit]


def _composer_score(item: dict[str, Any]) -> int:
    if item.get("disabled"):
        return -100
    tag = str(item.get("tag") or "").lower()
    role = str(item.get("role") or "").lower()
    item_type = str(item.get("type") or "").lower()
    text = _clean(item.get("text"), 300).lower()
    if item_type in {"search", "password", "email"}:
        return -50
    score = 0
    if tag == "textarea":
        score += 30
    if item.get("contenteditable"):
        score += 25
    if role == "textbox":
        score += 20
    if tag == "input" and item_type in {"", "text"}:
        score += 8
    if any(word in text for word in COMPOSER_WORDS):
        score += 20
    return score


def _pick_composer(observation: dict[str, Any]) -> dict[str, Any] | None:
    rows = list(observation.get("elements") or [])
    ranked = sorted(((row, _composer_score(row)) for row in rows), key=lambda pair: pair[1], reverse=True)
    return ranked[0][0] if ranked and ranked[0][1] > 0 else None


def _pick_send_button(observation: dict[str, Any]) -> dict[str, Any] | None:
    for row in reversed(list(observation.get("elements") or [])):
        if row.get("disabled"):
            continue
        role, tag = str(row.get("role") or "").lower(), str(row.get("tag") or "").lower()
        text = _clean(row.get("text"), 300).lower()
        if (role == "button" or tag == "button") and any(word in text for word in SEND_WORDS):
            return row
    return None


def _citation_rows(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        url = str(item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        result.append({
            "url": url,
            "title": _clean(item.get("title") or item.get("text"), 500),
            "snippet": "",
            "cited_text": _clean(item.get("text"), 1000),
        })
    return result[:80]


def _answer_from_snapshot(
    snapshot: dict[str, Any],
    baseline: set[str],
    question: str,
    provider_id: str = "",
) -> BrowserAnswer | None:
    candidates: list[tuple[int, int, dict[str, Any], str]] = []
    normalized_question = _clean(question).casefold()
    for index, block in enumerate(snapshot.get("content_blocks") or []):
        text = _answer_text(block.get("text"))
        compact = _clean(text)
        folded = compact.casefold()
        if len(compact) < 6 or compact in baseline or folded == normalized_question or NOISE_TEXT.match(compact):
            continue
        if normalized_question and folded.startswith(normalized_question):
            first_index = text.casefold().find(question.casefold())
            if first_index >= 0:
                text = text[first_index + len(question):].strip(" ：:-\n")
            compact = _clean(text)
            folded = compact.casefold()
        if len(compact) < 6:
            continue
        author = str(block.get("author") or "").lower()
        class_name = str(block.get("class_name") or "").lower()
        score = index
        if author == "assistant":
            score += 1000
        if any(word in class_name for word in ("markdown", "answer", "response", "prose", "assistant")):
            score += 500
        tag = str(block.get("tag") or "").lower()
        if provider_id == "deepseek" and "ds-markdown" in class_name:
            score += 1000
        elif provider_id == "openai" and author == "assistant":
            score += 1000
        elif provider_id == "gemini" and tag == "model-response":
            score += 1000
        elif provider_id == "perplexity" and any(word in class_name for word in ("prose", "answer")):
            score += 700
        elif provider_id == "doubao" and "markdown" in class_name:
            score += 700
        if normalized_question and normalized_question in folded:
            score -= 100
        score += min(len(compact), 8000) // 20
        candidates.append((score, index, block, text))
    if not candidates:
        return None
    _, _, block, answer = max(candidates, key=lambda item: (item[0], item[1]))
    links = _citation_rows(list(block.get("links") or []))
    if not links:
        links = _citation_rows(list(snapshot.get("links") or []))
    return BrowserAnswer(
        answer=answer,
        citations=links,
        url=str(snapshot.get("url") or ""),
        title=str(snapshot.get("title") or ""),
    )


class GeoSidebarBrowser:
    """Sequential consumer-AI sampler using the super employee browser."""

    async def available(self) -> bool:
        try:
            state = await _browser_action({"action": "state"})
            return bool(state.get("available"))
        except Exception:
            return False

    async def visible(self) -> bool:
        try:
            state = await _browser_action({"action": "state"})
            return bool(state.get("available") and state.get("visible"))
        except Exception:
            return False

    async def provider_status(self) -> list[dict[str, Any]]:
        available = await self.available()
        return [
            {
                "id": provider_id,
                "label": config["label"],
                "configured": available,
                "mode": "consumer_surface",
                "availability": "available" if available else "desktop_required",
            }
            for provider_id, config in PLATFORMS.items()
        ]

    async def _wait_until_visible(self, timeout: float = 30) -> None:
        """Do not turn the shared WebContentsView into an implicit headless worker."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = await _browser_action({"action": "state"})
            # Older test/dev controllers did not expose ``visible``; treating a
            # missing value as visible keeps the browser protocol compatible.
            if state.get("visible", True):
                return
            await asyncio.sleep(0.4)
        raise GeoBrowserError(
            "请在GEO页面打开右侧检测现场后继续",
            code="browser_not_visible",
        )

    async def _wait_for_user(self, timeout: float = 300) -> None:
        await _browser_action({"action": "takeover"})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(1.5)
            state = await _browser_action({"action": "state"})
            if state.get("owner") == "none":
                raise GeoBrowserError("你已停止本次浏览器检测", code="user_cancelled")
            if state.get("owner") != "user":
                return
        raise GeoBrowserError("等待登录超时，请完成登录后重新开始检测", code="login_timeout")

    async def _prepare_composer(self, timeout: float = 30) -> tuple[dict[str, Any], dict[str, Any]]:
        deadline = time.monotonic() + timeout
        login_requested = False
        last_snapshot: dict[str, Any] = {}
        while time.monotonic() < deadline:
            state = await _browser_action({"action": "state"})
            if state.get("owner") == "none":
                raise GeoBrowserError("你已停止本次浏览器检测", code="user_cancelled")
            if state.get("loading"):
                await asyncio.sleep(0.6)
                continue
            try:
                last_snapshot = await _browser_action({"action": "read"})
                observation = await _browser_action({"action": "observe"})
            except RuntimeError as exc:
                if "用户正在操作" in str(exc):
                    await asyncio.sleep(0.8)
                    continue
                raise
            composer = _pick_composer(observation)
            if composer:
                return last_snapshot, composer
            if last_snapshot.get("auth_hint") and not login_requested:
                login_requested = True
                await self._wait_for_user()
                # Give the consumer site a fresh loading window after login.
                deadline = time.monotonic() + timeout
                continue
            await asyncio.sleep(0.8)
        raise GeoBrowserError("没有找到AI提问框，请确认已登录且页面可以正常使用", code="composer_missing")

    async def query(self, provider_id: str, question: str, *, timeout: float = 150) -> dict[str, Any]:
        provider = PLATFORMS.get(provider_id)
        if not provider:
            raise GeoBrowserError("暂不支持这个AI平台", code="unsupported_provider")
        if not await self.available():
            raise GeoBrowserError("请使用数字员工桌面版进行实际界面检测", code="desktop_required")

        await self._wait_until_visible()
        await _browser_action({"action": "navigate", "url": provider["url"]})
        await asyncio.sleep(0.7)
        baseline_snapshot, composer = await self._prepare_composer()
        baseline = {_clean(block.get("text")) for block in baseline_snapshot.get("content_blocks") or []}
        for attempt in range(2):
            try:
                await _browser_action({"action": "type", "ref": composer["ref"], "text": question, "clear": True})
                break
            except RuntimeError as exc:
                if attempt or "页面已经变化" not in str(exc):
                    raise
                refreshed, composer = await self._prepare_composer()
                baseline.update(_clean(block.get("text")) for block in refreshed.get("content_blocks") or [])
        await _browser_action({"action": "press", "key": "Enter"})

        deadline = time.monotonic() + timeout
        last_answer = ""
        stable_count = 0
        send_fallback_used = False
        started = time.monotonic()
        while time.monotonic() < deadline:
            await asyncio.sleep(1.2)
            try:
                state = await _browser_action({"action": "state"})
                if state.get("owner") == "none":
                    raise GeoBrowserError("你已停止本次浏览器检测", code="user_cancelled")
                snapshot = await _browser_action({"action": "read"})
            except RuntimeError as exc:
                if "用户正在操作" in str(exc):
                    await asyncio.sleep(1.5)
                    continue
                raise
            answer = _answer_from_snapshot(snapshot, baseline, question, provider_id)
            if answer and answer.answer == last_answer:
                stable_count += 1
            elif answer:
                last_answer, stable_count = answer.answer, 0
            if answer and stable_count >= 2 and not snapshot.get("busy"):
                return {
                    "answer": answer.answer,
                    "citations": answer.citations,
                    "search_queries": [],
                    "provider_model": f"{provider_id}-consumer-web",
                    "fidelity": "consumer_surface",
                    "capture_method": "sidebar_browser",
                    "request_id": "",
                    "page_url": answer.url,
                    "page_title": answer.title,
                    "usage": {},
                }
            if not answer and not send_fallback_used and time.monotonic() - started > 5:
                observation = await _browser_action({"action": "observe"})
                send = _pick_send_button(observation)
                if send:
                    await _browser_action({"action": "click", "ref": send["ref"]})
                send_fallback_used = True
        raise GeoBrowserError("等待AI回答超时，本次问题未保存为有效结果", code="answer_timeout")


_BROWSER: GeoSidebarBrowser | None = None


def get_geo_sidebar_browser() -> GeoSidebarBrowser:
    global _BROWSER
    if _BROWSER is None:
        _BROWSER = GeoSidebarBrowser()
    return _BROWSER
