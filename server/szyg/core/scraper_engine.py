"""
Scraper Engine — Viral video discovery and comment extraction.

Uses the VersionLockedBrowserPool for stealth browser automation.
Targets Douyin, Xiaohongshu, Kuaishou, Bilibili, Weibo.

Key operations:
  - scrape_trending_videos: keyword search with infinite scroll
  - scrape_video_comments:  per-video comment extraction with auto-expand
"""
import asyncio
import logging
import random
import re
import time
from typing import Optional

from playwright.async_api import Page

from szyg.core.browser_pool import get_browser_pool_v2
from szyg.platforms.anti_detect import HumanBehavior, inject_stealth

logger = logging.getLogger(__name__)

# ── Platform search URLs ─────────────────────────────────

PLATFORM_SEARCH_URLS = {
    "douyin": "https://www.douyin.com/search/{}",
    "xhs": "https://www.xiaohongshu.com/search_result?keyword={}",
    "kuaishou": "https://www.kuaishou.com/search/video?searchKey={}",
    "bilibili": "https://search.bilibili.com/all?keyword={}",
    "weibo": "https://s.weibo.com/weibo?q={}",
}

# ── Overlay / popup dismiss selectors ────────────────────

OVERLAY_SELECTORS = [
    'div[class*="close"]',
    'span[class*="close"]',
    'button[class*="close"]',
    'div[class*="mask"]',
    '[aria-label="关闭"]',
    '[aria-label="close"]',
    '.modal-close',
    '.dialog-close',
]

# ── Comment selectors per platform ───────────────────────

COMMENT_SELECTORS = {
    "douyin": {
        "container": '[class*="comment"]',
        "username":  '[class*="name"], [class*="nickname"], [class*="author"]',
        "text":      '[class*="content"], [class*="text"], [class*="desc"]',
        "likes":     '[class*="like"], [class*="digg"]',
        "avatar":    'img[class*="avatar"], img[class*="head"]',
    },
    "xhs": {
        "container": '.comment-item, [class*="comment"]',
        "username":  '.username, [class*="nickname"], [class*="name"]',
        "text":      '.content, [class*="text"], [class*="desc"]',
        "likes":     '.like-count, [class*="like"]',
        "avatar":    '.avatar img, img[class*="avatar"]',
    },
    "kuaishou": {
        "container": '[class*="comment"]',
        "username":  '[class*="name"], [class*="nickname"]',
        "text":      '[class*="content"], [class*="text"]',
        "likes":     '[class*="like"], [class*="up"]',
        "avatar":    'img[class*="avatar"], img[class*="head"]',
    },
    "bilibili": {
        "container": '.reply-item, [class*="comment"]',
        "username":  '.user-name, [class*="name"]',
        "text":      '.reply-content, [class*="content"]',
        "likes":     '.like-count, [class*="like"]',
        "avatar":    '.user-avatar img, img[class*="avatar"]',
    },
    "weibo": {
        "container": '.comment-item, [class*="comment"]',
        "username":  '.user-name, [class*="nickname"]',
        "text":      '.comment-text, [class*="content"]',
        "likes":     '.like-count, [class*="like"]',
        "avatar":    '.head-img img, img[class*="avatar"]',
    },
}


class ScraperEngine:
    """
    Commercial scraping engine using the version-locked browser pool.

    Usage:
        engine = ScraperEngine()
        videos = await engine.scrape_trending_videos("美妆", max_results=20)
        comments = await engine.scrape_video_comments("https://...", max_comments=50)
    """

    def __init__(self, platform: str = "douyin", account_id: str = "scraper"):
        self._platform = platform
        self._account_id = account_id
        self._pool = get_browser_pool_v2()

    # ── Helpers ──────────────────────────────────────────

    def _clean_text(self, text: str) -> str:
        """Normalize scraped text: strip whitespace and HTML artifacts."""
        if not text:
            return ""
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'<[^>]+>', '', text)
        return text

    def _safe_int(self, value, default: int = 0) -> int:
        """Parse integer from potentially formatted strings like '1.2万'."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        if not text:
            return default
        try:
            if '万' in text or 'w' in text.lower():
                num = float(re.sub(r'[万w]', '', text, flags=re.IGNORECASE).strip())
                return int(num * 10000)
            if '亿' in text:
                num = float(re.sub(r'亿', '', text).strip())
                return int(num * 100000000)
            return int(float(text))
        except (ValueError, TypeError):
            return default

    async def _get_stealth_page(self) -> Page:
        """Get a stealth-configured page from the pool."""
        ctx = await self._pool.get_context(self._platform, self._account_id)
        pages = ctx.pages
        page = pages[0] if pages else await ctx.new_page()
        # Inject full stealth on first use
        try:
            await inject_stealth(page)
        except Exception as e:
            logger.debug("Stealth injection failed: %s", e)
        return page

    async def _dismiss_overlays(self, page: Page) -> None:
        """Attempt to close any overlay/popup/modals on the page."""
        for sel in OVERLAY_SELECTORS:
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

    async def _human_scroll(self, page: Page, scrolls: int = 4) -> None:
        """Simulate human scrolling to trigger infinite scroll."""
        for i in range(scrolls):
            distance = random.randint(400, 900)
            await page.evaluate(f"window.scrollBy(0, {distance})")
            await asyncio.sleep(random.uniform(0.8, 2.0))
            # Occasionally scroll up slightly (human-like)
            if random.random() < 0.3:
                await page.evaluate(f"window.scrollBy(0, {-random.randint(50, 150)})")
                await asyncio.sleep(random.uniform(0.3, 0.7))

    # ── Trending Video Scraping ──────────────────────────

    async def scrape_trending_videos(
        self,
        keyword: str,
        max_results: int = 20,
    ) -> list[dict]:
        """
        Search for trending videos by keyword.

        Opens a stealth page, navigates to the platform search, scrolls to
        trigger infinite scroll, and extracts video metadata from the DOM.

        Returns list of dicts with keys:
            title, play_count, like_count, comment_count, share_count,
            cover_url, video_url, author_name, platform
        """
        search_url = PLATFORM_SEARCH_URLS.get(self._platform)
        if not search_url:
            return [{"error": f"Unsupported platform: {self._platform}"}]

        page = await self._get_stealth_page()
        results: list[dict] = []

        try:
            url = search_url.format(keyword)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)  # Let JS framework render

            await self._dismiss_overlays(page)

            # Scroll to load more results
            scroll_rounds = max(1, max_results // 5)
            await self._human_scroll(page, scrolls=scroll_rounds)
            await asyncio.sleep(2)

            # Extract video cards from DOM — use broad selectors
            video_selectors = [
                '[class*="video-card"]',
                '[class*="video-item"]',
                '[class*="search-card"]',
                '[class*="result-item"]',
                'li[class*="item"]',
                'div[class*="card"]',
                '.video-card',
                '.search-result-item',
            ]

            cards = []
            for sel in video_selectors:
                try:
                    cards = await page.query_selector_all(sel)
                    if cards:
                        break
                except Exception:
                    continue

            for card in cards[:max_results]:
                try:
                    result = await self._extract_video_card(card)
                    if result and result.get("title"):
                        result["platform"] = self._platform
                        result["keyword"] = keyword
                        results.append(result)
                except Exception as e:
                    logger.debug(f"Skipping card: {e}")
                    continue

        except Exception as e:
            logger.error(f"scrape_trending_videos error: {e}")
            return [{"error": str(e)}]

        return results[:max_results]

    async def _extract_video_card(self, card) -> Optional[dict]:
        """Extract metadata from a single video card element."""
        data = {}

        # Title
        for title_sel in ['[class*="title"]', 'h3', 'h4', 'a[class*="title"]', '[class*="name"]']:
            try:
                el = await card.query_selector(title_sel)
                if el:
                    data["title"] = self._clean_text(await el.inner_text())
                    break
            except Exception:
                continue

        # Cover image
        try:
            img = await card.query_selector("img")
            data["cover_url"] = await img.get_attribute("src") if img else ""
        except Exception:
            data["cover_url"] = ""

        # Video URL
        try:
            link = await card.query_selector("a[href]")
            href = await link.get_attribute("href") if link else ""
            data["video_url"] = href
        except Exception:
            data["video_url"] = ""

        # Counts — try multiple label patterns
        counts = await self._extract_counts(card)
        data.update(counts)

        # Author
        for author_sel in ['[class*="author"]', '[class*="nickname"]', '[class*="name"]', '[class*="user"]']:
            try:
                el = await card.query_selector(author_sel)
                if el:
                    data["author_name"] = self._clean_text(await el.inner_text())
                    break
            except Exception:
                continue

        return data

    async def _extract_counts(self, card) -> dict:
        """Extract play/like/comment/share counts from a card."""
        counts = {
            "play_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "share_count": 0,
        }
        try:
            full_text = self._clean_text(await card.inner_text())
        except Exception:
            return counts

        # Pattern: 数字+单位 (e.g., "播放 1.2万", "点赞 340", "评论 56")
        patterns = [
            (r'(?:播放|观看)[^\d]*([\d.]+[万亿w]?)', "play_count"),
            (r'(?:点赞|赞)[^\d]*([\d.]+[万亿w]?)', "like_count"),
            (r'(?:评论|回复)[^\d]*([\d.]+[万亿w]?)', "comment_count"),
            (r'(?:分享|转发)[^\d]*([\d.]+[万亿w]?)', "share_count"),
        ]
        for pattern, key in patterns:
            m = re.search(pattern, full_text)
            if m:
                counts[key] = self._safe_int(m.group(1))

        return counts

    # ── Comment Scraping ─────────────────────────────────

    async def scrape_video_comments(
        self,
        video_url: str,
        max_comments: int = 50,
    ) -> list[dict]:
        """
        Extract comments from a specific video page.

        Navigates to the video, dismisses overlays, scrolls the comments
        section to load more, and extracts structured comment data.

        Returns list of dicts with keys:
            username, avatar, text, like_count, timestamp, platform
        """
        page = await self._get_stealth_page()
        comments: list[dict] = []

        try:
            await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            await self._dismiss_overlays(page)

            # Scroll to load comments
            await self._human_scroll(page, scrolls=3)
            await asyncio.sleep(1)

            # Try to click "展开更多评论" / "load more comments" if present
            expand_selectors = [
                'text=展开更多',
                'text=查看更多',
                'text=加载更多',
                'text=load more',
                '[class*="more-comment"]',
                '[class*="load-more"]',
            ]
            for _ in range(3):
                clicked = False
                for sel in expand_selectors:
                    try:
                        el = await page.wait_for_selector(sel, timeout=2000)
                        if el and await el.is_visible():
                            await el.click(timeout=3000)
                            await asyncio.sleep(1)
                            clicked = True
                    except Exception:
                        continue
                if not clicked:
                    break

            # Extract comments
            selectors = COMMENT_SELECTORS.get(self._platform, COMMENT_SELECTORS["douyin"])
            container_sel = selectors["container"]

            comment_elements = []
            try:
                comment_elements = await page.query_selector_all(container_sel)
            except Exception as e:
                logger.debug("Failed to find comment elements with %s: %s", container_sel, e)

            for el in comment_elements[:max_comments]:
                try:
                    comment = await self._extract_comment(el, selectors)
                    if comment and comment.get("text"):
                        comment["platform"] = self._platform
                        comment["video_url"] = video_url
                        comments.append(comment)
                except Exception as e:
                    logger.debug(f"Skipping comment: {e}")
                    continue

        except Exception as e:
            logger.error(f"scrape_video_comments error: {e}")
            return [{"error": str(e)}]

        return comments[:max_comments]

    async def _extract_comment(self, el, selectors: dict) -> Optional[dict]:
        """Extract data from a single comment element."""
        data = {}

        # Username
        try:
            u = await el.query_selector(selectors["username"])
            data["username"] = self._clean_text(await u.inner_text()) if u else ""
        except Exception:
            data["username"] = ""

        # Avatar
        try:
            a = await el.query_selector(selectors["avatar"])
            data["avatar"] = await a.get_attribute("src") if a else ""
        except Exception:
            data["avatar"] = ""

        # Text
        try:
            t = await el.query_selector(selectors["text"])
            data["text"] = self._clean_text(await t.inner_text()) if t else ""
        except Exception:
            data["text"] = ""

        # Like count
        try:
            l = await el.query_selector(selectors["likes"])
            data["like_count"] = self._safe_int(await l.inner_text()) if l else 0
        except Exception:
            data["like_count"] = 0

        # Timestamp
        for ts_sel in ['[class*="time"]', '[class*="date"]', 'time']:
            try:
                ts = await el.query_selector(ts_sel)
                if ts:
                    data["timestamp"] = self._clean_text(await ts.inner_text())
                    break
            except Exception:
                continue

        data.setdefault("timestamp", "")
        return data
