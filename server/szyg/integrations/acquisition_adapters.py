"""
Acquisition Adapters — 统一采集适配层

集成开源项目实现各平台的 search / send_comment / get_comments / send_dm 功能:
  - B站: bilibili-api-python (API方式，无需浏览器)
  - 小红书: Playwright 浏览器自动化 (复用现有 BrowserPool)
  - 抖音: Playwright 浏览器自动化 (复用现有 BrowserPool)
  - 快手: Playwright 浏览器自动化 (复用现有 BrowserPool)

每个适配器返回统一格式的数据结构，供 MCP Server 和引擎层调用。
"""
import asyncio
import logging
import re
import json
from typing import Optional

logger = logging.getLogger(__name__)


# ── Unified Data Structures ──────────────────────────────────────────────

def _normalize_search_result(item: dict, platform: str) -> dict:
    """将各平台搜索结果统一为标准格式"""
    return {
        "video_id": str(item.get("video_id", item.get("id", item.get("bvid", "")))),
        "platform": platform,
        "title": item.get("title", item.get("desc", ""))[:200],
        "description": item.get("description", item.get("desc", ""))[:500],
        "author": item.get("author", item.get("name", item.get("nickname", ""))),
        "author_followers": item.get("author_followers", item.get("followers", 0)),
        "url": item.get("url", item.get("link", "")),
        "cover": item.get("cover", item.get("pic", item.get("cover_url", ""))),
        "plays": item.get("plays", item.get("play", item.get("view_count", 0))),
        "likes": item.get("likes", item.get("like", item.get("digg_count", 0))),
        "comments_count": item.get("comments_count", item.get("comment", item.get("comment_count", 0))),
        "shares": item.get("shares", item.get("share", item.get("share_count", 0))),
        "published_at": item.get("published_at", item.get("pubdate", item.get("create_time", ""))),
    }


def _normalize_comment(item: dict, platform: str) -> dict:
    """将各平台评论统一为标准格式"""
    return {
        "comment_id": str(item.get("comment_id", item.get("rpid", item.get("cid", "")))),
        "platform": platform,
        "author": item.get("author", item.get("name", item.get("nickname", item.get("member", {}).get("uname", "")))),
        "author_id": str(item.get("author_id", item.get("mid", item.get("uid", "")))),
        "text": item.get("text", item.get("content", item.get("message", ""))),
        "likes": item.get("likes", item.get("like", item.get("digg_count", 0))),
        "created_at": item.get("created_at", item.get("ctime", item.get("create_time", ""))),
        "reply_count": item.get("reply_count", item.get("replies", item.get("sub_comment_count", 0))),
        "ip_location": item.get("ip_location", item.get("ip_location", "")),
    }


# ── Base Acquisition Adapter ─────────────────────────────────────────────

class BaseAcquisitionAdapter:
    """统一采集接口 — 各平台子类实现具体方法"""

    platform: str = ""

    async def search(self, keyword: str, limit: int = 20) -> list[dict]:
        raise NotImplementedError(f"{self.platform} search() not implemented")

    async def send_comment(self, video_url: str, comment_text: str) -> dict:
        raise NotImplementedError(f"{self.platform} send_comment() not implemented")

    async def get_comments(self, video_url: str, limit: int = 30) -> list[dict]:
        raise NotImplementedError(f"{self.platform} get_comments() not implemented")

    async def send_dm(self, user_id: str, text: str) -> dict:
        raise NotImplementedError(f"{self.platform} send_dm() not implemented")

    def status(self) -> dict:
        return {"platform": self.platform, "ready": True, "message": "ok"}


# ── Bilibili Acquisition Adapter (API-based) ─────────────────────────────

class BilibiliAcquisitionAdapter(BaseAcquisitionAdapter):
    """B站采集适配器 — 基于 bilibili-api-python 库，纯API调用无需浏览器"""

    platform = "bilibili"

    def __init__(self):
        self._credential = None
        self._cred_ready = False

    def _get_credential(self):
        """从 config 或 session 文件加载 B站凭证"""
        if self._cred_ready:
            return self._credential

        try:
            from bilibili_api import Credential
            from szyg.data_path import DATA_DIR
            cred_path = DATA_DIR / "sessions" / "bilibili_credential.json"
            if cred_path.exists():
                with open(cred_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._credential = Credential(
                    sessdata=data.get("sessdata", ""),
                    bili_jct=data.get("bili_jct", ""),
                    buvid3=data.get("buvid3", ""),
                    dedeuserid=data.get("dedeuserid", ""),
                )
                logger.info("Bilibili credential loaded from file")
            else:
                logger.warning("Bilibili credential file not found, API calls will be limited to public data")
                self._credential = None
        except Exception as e:
            logger.warning(f"Failed to load Bilibili credential: {e}")
            self._credential = None

        self._cred_ready = True
        return self._credential

    async def search(self, keyword: str, limit: int = 20) -> list[dict]:
        """搜索B站视频"""
        from bilibili_api import search as bili_search
        from bilibili_api.search import SearchObjectType

        try:
            result = await bili_search.search_by_type(
                keyword=keyword,
                search_type=SearchObjectType.VIDEO,
                page=1,
                page_size=min(limit, 42),
            )
            raw_results = result.get("result", [])
            videos = []
            for item in raw_results[:limit]:
                bvid = item.get("bvid", "")
                videos.append(_normalize_search_result({
                    "video_id": bvid,
                    "title": re.sub(r'<[^>]+>', '', item.get("title", "")),
                    "description": re.sub(r'<[^>]+>', '', item.get("description", "")),
                    "author": item.get("author", ""),
                    "author_followers": 0,
                    "url": f"https://www.bilibili.com/video/{bvid}" if bvid else "",
                    "cover": item.get("pic", ""),
                    "plays": item.get("play", 0),
                    "likes": 0,
                    "comments_count": item.get("video_review", 0),
                    "shares": 0,
                    "published_at": item.get("pubdate", ""),
                    "duration": item.get("duration", 0),
                }, "bilibili"))
            return videos
        except Exception as e:
            logger.error(f"Bilibili search error: {e}")
            return []

    async def get_comments(self, video_url: str, limit: int = 30) -> list[dict]:
        """获取B站视频评论"""
        from bilibili_api import comment as bili_comment, video as bili_video

        try:
            bvid = self._extract_bvid(video_url)
            if not bvid:
                return []

            v = bili_video.Video(bvid=bvid)
            aid = v.get_aid()

            cred = self._get_credential()
            result = await bili_comment.get_comments(
                oid=aid,
                type_=bili_comment.CommentResourceType.VIDEO,
                page_index=1,
                credential=cred,
            )

            raw_comments = result.get("replies") or []
            comments = []
            for item in raw_comments[:limit]:
                comments.append(_normalize_comment({
                    "comment_id": item.get("rpid", 0),
                    "author": item.get("member", {}).get("uname", ""),
                    "author_id": item.get("mid", 0),
                    "text": item.get("content", {}).get("message", ""),
                    "likes": item.get("like", 0),
                    "created_at": item.get("ctime", 0),
                    "reply_count": item.get("replies", 0) if isinstance(item.get("replies"), int) else len(item.get("replies", [])),
                    "ip_location": item.get("reply_control", {}).get("location", ""),
                }, "bilibili"))
            return comments
        except Exception as e:
            logger.error(f"Bilibili get_comments error: {e}")
            return []

    async def send_comment(self, video_url: str, comment_text: str) -> dict:
        """发送B站评论"""
        from bilibili_api import comment as bili_comment, video as bili_video

        try:
            bvid = self._extract_bvid(video_url)
            if not bvid:
                return {"success": False, "error": "无法从URL提取BVID"}

            v = bili_video.Video(bvid=bvid)
            aid = v.get_aid()

            cred = self._get_credential()
            if not cred or not cred.sessdata:
                return {"success": False, "error": "B站未登录，无法发送评论"}

            result = await bili_comment.send_comment(
                text=comment_text,
                oid=aid,
                type_=bili_comment.CommentResourceType.VIDEO,
                credential=cred,
            )
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Bilibili send_comment error: {e}")
            return {"success": False, "error": str(e)}

    async def send_dm(self, user_id: str, text: str) -> dict:
        """发送B站私信"""
        from bilibili_api import session as bili_session

        try:
            cred = self._get_credential()
            if not cred or not cred.sessdata:
                return {"success": False, "error": "B站未登录，无法发送私信"}

            result = await bili_session.send_msg(
                credential=cred,
                receiver_id=int(user_id),
                msg_type=bili_session.EventType.TEXT,
                content=text,
            )
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Bilibili send_dm error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _extract_bvid(url: str) -> str:
        """从URL中提取BVID"""
        match = re.search(r'BV[a-zA-Z0-9]{10}', url)
        if match:
            return match.group(0)
        match = re.search(r'av(\d+)', url, re.IGNORECASE)
        if match:
            return f"av{match.group(1)}"
        return ""


# ── Playwright-based Acquisition Adapter (Douyin/XHS/Kuaishou) ──────────

class PlaywrightAcquisitionAdapter(BaseAcquisitionAdapter):
    """基于 Playwright 的采集适配器 — 用于抖音/小红书/快手

    复用现有平台适配器的 BrowserPool 和 SessionManager，
    在浏览器中执行搜索、评论获取和评论发送操作。
    """

    def __init__(self, platform: str):
        self.platform = platform
        self._pool = None
        self._context = None
        self._page = None
        self._session = None

    async def _ensure_browser(self):
        """确保浏览器上下文已初始化"""
        if self._page:
            return self._page

        from szyg.platforms.browser_pool import get_browser_pool
        from szyg.platforms.session_manager import get_session_manager
        from szyg.publisher import Platform

        self._pool = get_browser_pool()
        await self._pool.start()
        self._session = get_session_manager()

        platform_map = {
            "douyin": Platform.DOUYIN,
            "xhs": Platform.XHS,
            "bilibili": Platform.BILIBILI,
            "kuaishou": Platform.KUAISHOU,
        }
        p = platform_map.get(self.platform)
        if not p:
            raise ValueError(f"Unknown platform: {self.platform}")

        storage_state = self._session.load(p)
        self._context = await self._pool.get_context(
            platform_key=self.platform,
            storage_state=storage_state,
        )
        self._page = await self._context.new_page()
        return self._page

    async def _close_browser(self):
        """归还浏览器上下文到池中"""
        if self._context:
            try:
                from szyg.publisher import Platform
                platform_map = {
                    "douyin": Platform.DOUYIN,
                    "xhs": Platform.XHS,
                    "bilibili": Platform.BILIBILI,
                    "kuaishou": Platform.KUAISHOU,
                }
                p = platform_map.get(self.platform)
                if p:
                    self._session.save(p, await self._context.storage_state())
            except Exception:
                pass
            try:
                await self._pool.return_context(self.platform)
            except Exception:
                pass
        self._page = None
        self._context = None

    async def search(self, keyword: str, limit: int = 20) -> list[dict]:
        """在平台搜索视频 — 子类可覆盖实现平台特定逻辑"""
        page = await self._ensure_browser()
        results = []

        try:
            if self.platform == "douyin":
                results = await self._search_douyin(page, keyword, limit)
            elif self.platform == "xhs":
                results = await self._search_xhs(page, keyword, limit)
            elif self.platform == "kuaishou":
                results = await self._search_kuaishou(page, keyword, limit)
        except Exception as e:
            logger.error(f"{self.platform} search error: {e}")
        finally:
            await self._close_browser()

        return results

    async def _search_douyin(self, page, keyword: str, limit: int) -> list[dict]:
        """抖音搜索"""
        await page.goto(f"https://www.douyin.com/search/{keyword}", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        video_items = await page.query_selector_all('[data-e2e="search-video-item"]')
        results = []
        for item in video_items[:limit]:
            try:
                link = await item.query_selector("a")
                href = await link.get_attribute("href") if link else ""
                title = await item.inner_text() if link else ""
                aweme_id = re.search(r'/video/(\d+)', href or "")
                results.append(_normalize_search_result({
                    "video_id": aweme_id.group(1) if aweme_id else "",
                    "title": title[:200],
                    "url": f"https://www.douyin.com{href}" if href.startswith("/") else href,
                }, "douyin"))
            except Exception:
                continue
        return results

    async def _search_xhs(self, page, keyword: str, limit: int) -> list[dict]:
        """小红书搜索"""
        await page.goto(f"https://www.xiaohongshu.com/search_result?keyword={keyword}", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        note_items = await page.query_selector_all('.note-item, [data-v-*] section.note-item')
        results = []
        for item in note_items[:limit]:
            try:
                link = await item.query_selector("a")
                href = await link.get_attribute("href") if link else ""
                title_el = await item.query_selector(".title, .note-title")
                title = await title_el.inner_text() if title_el else ""
                note_id = re.search(r'/note/([a-zA-Z0-9]+)', href or "")
                results.append(_normalize_search_result({
                    "video_id": note_id.group(1) if note_id else "",
                    "title": title[:200],
                    "url": href if href.startswith("http") else f"https://www.xiaohongshu.com{href}",
                }, "xhs"))
            except Exception:
                continue
        return results

    async def _search_kuaishou(self, page, keyword: str, limit: int) -> list[dict]:
        """快手搜索"""
        await page.goto(f"https://www.kuaishou.com/search/video?searchKey={keyword}", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        video_items = await page.query_selector_all('.video-item, [class*="video-card"]')
        results = []
        for item in video_items[:limit]:
            try:
                link = await item.query_selector("a")
                href = await link.get_attribute("href") if link else ""
                title = await item.inner_text()
                video_id = re.search(r'/short-video/([a-zA-Z0-9]+)', href or "")
                results.append(_normalize_search_result({
                    "video_id": video_id.group(1) if video_id else "",
                    "title": title[:200],
                    "url": href if href.startswith("http") else f"https://www.kuaishou.com{href}",
                }, "kuaishou"))
            except Exception:
                continue
        return results

    async def get_comments(self, video_url: str, limit: int = 30) -> list[dict]:
        """获取视频评论 — 通过浏览器抓取"""
        page = await self._ensure_browser()
        comments = []

        try:
            await page.goto(video_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            if self.platform == "douyin":
                comments = await self._get_comments_douyin(page, limit)
            elif self.platform == "xhs":
                comments = await self._get_comments_xhs(page, limit)
            elif self.platform == "kuaishou":
                comments = await self._get_comments_kuaishou(page, limit)
        except Exception as e:
            logger.error(f"{self.platform} get_comments error: {e}")
        finally:
            await self._close_browser()

        return comments

    async def _get_comments_douyin(self, page, limit: int) -> list[dict]:
        """获取抖音视频评论"""
        comment_items = await page.query_selector_all('[data-e2e="comment-list"] > div')
        comments = []
        for item in comment_items[:limit]:
            try:
                text_el = await item.query_selector('[data-e2e="comment-content"] p, .comment-content')
                text = await text_el.inner_text() if text_el else ""
                author_el = await item.query_selector('[data-e2e="comment-user-name"], .nickname')
                author = await author_el.inner_text() if author_el else ""
                comments.append(_normalize_comment({
                    "text": text,
                    "author": author,
                }, "douyin"))
            except Exception:
                continue
        return comments

    async def _get_comments_xhs(self, page, limit: int) -> list[dict]:
        """获取小红书笔记评论"""
        comment_items = await page.query_selector_all('.comment-item, [class*="comment"]')
        comments = []
        for item in comment_items[:limit]:
            try:
                text_el = await item.query_selector('.content, .comment-content')
                text = await text_el.inner_text() if text_el else ""
                author_el = await item.query_selector('.name, .author')
                author = await author_el.inner_text() if author_el else ""
                comments.append(_normalize_comment({
                    "text": text,
                    "author": author,
                }, "xhs"))
            except Exception:
                continue
        return comments

    async def _get_comments_kuaishou(self, page, limit: int) -> list[dict]:
        """获取快手视频评论"""
        comment_items = await page.query_selector_all('.comment-item, [class*="comment"]')
        comments = []
        for item in comment_items[:limit]:
            try:
                text_el = await item.query_selector('.comment-content, .content')
                text = await text_el.inner_text() if text_el else ""
                author_el = await item.query_selector('.user-name, .author')
                author = await author_el.inner_text() if author_el else ""
                comments.append(_normalize_comment({
                    "text": text,
                    "author": author,
                }, "kuaishou"))
            except Exception:
                continue
        return comments

    async def send_comment(self, video_url: str, comment_text: str) -> dict:
        """在视频页面发送评论 — 通过浏览器操作"""
        page = await self._ensure_browser()

        try:
            await page.goto(video_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            if self.platform == "douyin":
                return await self._send_comment_douyin(page, comment_text)
            elif self.platform == "xhs":
                return await self._send_comment_xhs(page, comment_text)
            elif self.platform == "kuaishou":
                return await self._send_comment_kuaishou(page, comment_text)
            else:
                return {"success": False, "error": f"Unsupported platform: {self.platform}"}
        except Exception as e:
            logger.error(f"{self.platform} send_comment error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            await self._close_browser()

    async def _send_comment_douyin(self, page, comment_text: str) -> dict:
        """在抖音视频页面发送评论"""
        try:
            comment_input = await page.wait_for_selector(
                '[data-e2e="comment-input"] textarea, [data-e2e="comment-input"] input, .comment-input textarea',
                timeout=5000,
            )
            await comment_input.fill(comment_text)
            await page.wait_for_timeout(500)

            send_btn = await page.query_selector(
                '[data-e2e="comment-post"] button, .comment-input button[type="submit"]'
            )
            if send_btn:
                await send_btn.click()
                await page.wait_for_timeout(2000)
                return {"success": True, "message": "评论已发送"}
            return {"success": False, "error": "未找到评论发送按钮"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _send_comment_xhs(self, page, comment_text: str) -> dict:
        """在小红书笔记页面发送评论"""
        try:
            comment_input = await page.wait_for_selector(
                '#comment-textarea, .comment-input textarea, [placeholder*="评论"]',
                timeout=5000,
            )
            await comment_input.fill(comment_text)
            await page.wait_for_timeout(500)

            send_btn = await page.query_selector(
                '.comment-input .submit, button:has-text("发送")'
            )
            if send_btn:
                await send_btn.click()
                await page.wait_for_timeout(2000)
                return {"success": True, "message": "评论已发送"}
            return {"success": False, "error": "未找到评论发送按钮"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _send_comment_kuaishou(self, page, comment_text: str) -> dict:
        """在快手视频页面发送评论"""
        try:
            comment_input = await page.wait_for_selector(
                '.comment-input textarea, [placeholder*="评论"]',
                timeout=5000,
            )
            await comment_input.fill(comment_text)
            await page.wait_for_timeout(500)

            send_btn = await page.query_selector(
                '.comment-input .submit, button:has-text("发送")'
            )
            if send_btn:
                await send_btn.click()
                await page.wait_for_timeout(2000)
                return {"success": True, "message": "评论已发送"}
            return {"success": False, "error": "未找到评论发送按钮"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_dm(self, user_id: str, text: str) -> dict:
        """发送私信 — 浏览器平台暂不支持，需平台API"""
        return {"success": False, "error": f"{self.platform} send_dm not supported via Playwright"}

    def status(self) -> dict:
        return {
            "platform": self.platform,
            "ready": True,
            "type": "playwright",
            "message": "Playwright-based adapter",
        }


# ── Adapter Registry ─────────────────────────────────────────────────────

_adapters: dict[str, BaseAcquisitionAdapter] = {}


def get_acquisition_adapter(platform: str) -> BaseAcquisitionAdapter:
    """获取指定平台的采集适配器实例 (单例)"""
    if platform in _adapters:
        return _adapters[platform]

    if platform == "bilibili":
        adapter = BilibiliAcquisitionAdapter()
    elif platform in ("douyin", "xhs", "kuaishou"):
        adapter = PlaywrightAcquisitionAdapter(platform)
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    _adapters[platform] = adapter
    return adapter


def list_acquisition_platforms() -> list[dict]:
    """列出所有支持的采集平台"""
    platforms = ["bilibili", "douyin", "xhs", "kuaishou"]
    result = []
    for p in platforms:
        try:
            adapter = get_acquisition_adapter(p)
            result.append(adapter.status())
        except Exception as e:
            result.append({"platform": p, "ready": False, "error": str(e)})
    return result
