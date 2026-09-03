"""Bounded browser element grounding used by platform adapters.

The previous local model service was removed with the legacy desktop stack.
Browser publishers already own a Playwright page, so this module derives
stable element geometry from the live accessibility/DOM surface and keeps the
same small API consumed by platform adapters.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class DetectedElement:
    index: int
    label: str
    bbox: tuple[int, int, int, int]
    confidence: float = 1.0
    role: str = ""

    def center(self) -> tuple[int, int]:
        x, y, width, height = self.bbox
        return x + width // 2, y + height // 2


class VisionGrounding:
    """Resolve visible browser controls without a second local model stack."""

    _SELECTOR = ",".join((
        "button",
        "input",
        "textarea",
        "select",
        "a[href]",
        "[contenteditable='true']",
        "[role='button']",
        "[role='tab']",
        "[role='textbox']",
        "[role='checkbox']",
        "[role='radio']",
        "[role='link']",
        "[tabindex]:not([tabindex='-1'])",
    ))

    def __init__(self, *_: Any, **__: Any) -> None:
        self._cache: dict[str, list[DetectedElement]] = {}

    async def detect(self, page, *, use_cache: bool = True) -> list[DetectedElement]:
        cache_key = f"detect:{page.url}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        locator = page.locator(self._SELECTOR)
        count = min(await locator.count(), 240)
        elements: list[DetectedElement] = []
        for position in range(count):
            item = locator.nth(position)
            try:
                if not await item.is_visible():
                    continue
                bounds = await item.bounding_box()
                if not bounds or bounds["width"] < 3 or bounds["height"] < 3:
                    continue
                metadata = await item.evaluate(
                    """element => ({
                      text: (element.innerText || element.value || '').trim(),
                      aria: element.getAttribute('aria-label') || '',
                      placeholder: element.getAttribute('placeholder') || '',
                      title: element.getAttribute('title') || '',
                      role: element.getAttribute('role') || element.tagName.toLowerCase()
                    })"""
                )
                label = next((
                    str(metadata.get(key) or "").strip()
                    for key in ("aria", "placeholder", "text", "title")
                    if str(metadata.get(key) or "").strip()
                ), str(metadata.get("role") or "element"))
                elements.append(DetectedElement(
                    index=len(elements) + 1,
                    label=label[:220],
                    bbox=(
                        round(bounds["x"]),
                        round(bounds["y"]),
                        round(bounds["width"]),
                        round(bounds["height"]),
                    ),
                    role=self._normalize_role(str(metadata.get("role") or "")),
                ))
            except Exception:
                continue
        self._cache[cache_key] = elements
        return elements

    async def find_element(self, page, description: str, *, role: str | None = None) -> DetectedElement | None:
        best: DetectedElement | None = None
        best_score = 0.0
        for element in await self.detect(page, use_cache=False):
            score = self._match_score(element, description, role)
            if score > best_score:
                best, best_score = element, score
        return best if best_score >= 0.3 else None

    async def find_and_click(self, page, description: str, *, role: str | None = None) -> bool:
        element = await self.find_element(page, description, role=role)
        if element is None:
            return False
        try:
            await page.mouse.click(*element.center())
            self.clear_cache()
            return True
        except Exception:
            logger.debug("Browser control click failed: %s", description, exc_info=True)
            return False

    async def find_and_type(self, page, description: str, text: str, *, role: str | None = None) -> bool:
        element = await self.find_element(page, description, role=role or "input")
        if element is None:
            return False
        try:
            await page.mouse.click(*element.center())
            await asyncio.sleep(0.15)
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Backspace")
            await page.keyboard.insert_text(text)
            self.clear_cache()
            return True
        except Exception:
            logger.debug("Browser control typing failed: %s", description, exc_info=True)
            return False

    async def find_and_upload(self, page, description: str, file_path: str) -> bool:
        del description
        try:
            file_input = page.locator('input[type="file"]').first
            await file_input.wait_for(state="attached", timeout=5000)
            await file_input.set_input_files(file_path)
            return True
        except Exception:
            logger.debug("Browser file input was not available", exc_info=True)
            return False

    async def fallback_click(self, page, selectors: list[str], description: str = "") -> bool:
        del description
        for selector in selectors:
            try:
                target = page.locator(selector).first
                await target.wait_for(state="visible", timeout=3000)
                await target.click()
                self.clear_cache()
                return True
            except Exception:
                continue
        return False

    async def fallback_type(self, page, selectors: list[str], text: str, description: str = "") -> bool:
        del description
        for selector in selectors:
            try:
                target = page.locator(selector).first
                await target.wait_for(state="visible", timeout=3000)
                await target.fill(text)
                self.clear_cache()
                return True
            except Exception:
                continue
        return False

    def clear_cache(self) -> None:
        self._cache.clear()

    @staticmethod
    def _normalize_role(value: str) -> str:
        lowered = value.casefold()
        if lowered in {"input", "textarea", "textbox"}:
            return "input"
        if lowered in {"button", "tab", "checkbox", "radio", "link", "select"}:
            return lowered
        return "element"

    @staticmethod
    def _match_score(element: DetectedElement, query: str, role_filter: str | None) -> float:
        if role_filter:
            expected = "input" if role_filter in {"textbox", "text"} else role_filter
            if element.role != expected:
                return 0.0
        label = element.label.casefold()
        query_value = query.casefold().strip()
        if not query_value:
            return 0.0
        if query_value == label:
            return 1.0
        score = 0.65 if query_value in label else 0.0
        if label and label in query_value:
            score = max(score, 0.55)
        tokens = [token for token in query_value.replace("/", " ").split() if token]
        if tokens:
            score += 0.35 * sum(token in label for token in tokens) / len(tokens)
        chinese = {char for char in query_value if ord(char) > 127}
        if chinese:
            score += 0.35 * len(chinese.intersection(label)) / len(chinese)
        return min(score, 1.0)


_vision_grounding: VisionGrounding | None = None


def get_vision_grounding() -> VisionGrounding:
    global _vision_grounding
    if _vision_grounding is None:
        _vision_grounding = VisionGrounding()
    return _vision_grounding
