"""
MediaCrawler Bridge — 连接 szyg 与 MediaCrawler

集成 NanmiCoder/MediaCrawler 实现多平台搜索/详情/评论功能:
  - 抖音: DouYinClient (搜索/详情/评论)
  - 小红书: XhsClient (搜索/详情/评论)
  - 快手: KuaishouClient (搜索/详情/评论)
  - B站: BilibiliClient (搜索/详情/评论)

桥接层负责:
  1. 从 SessionManager 加载 storage_state
  2. 通过 BrowserPool 创建 BrowserContext
  3. 提取 Cookie 和 User-Agent
  4. 初始化 MediaCrawler Client
  5. 调用 MediaCrawler API 并返回统一格式数据
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# 添加 MediaCrawler 到 Python 路径
mediacrawler_path = Path(__file__).parent.parent.parent.parent / "vendor" / "MediaCrawler"
if str(mediacrawler_path) not in sys.path:
    sys.path.insert(0, str(mediacrawler_path))

try:
    from media_platform.douyin.client import DouYinClient
    from media_platform.douyin.field import SearchChannelType, SearchSortType, PublishTimeType
    MEDIACRAWLER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"MediaCrawler import failed: {e}")
    MEDIACRAWLER_AVAILABLE = False

from szyg.platforms.session_manager import SessionManager
from szyg.platforms.browser_pool import get_browser_pool
from szyg.publisher import Platform
from .normalize_utils import _normalize_search_result


# 模块级别单例
_bridge_instance: Optional["MediaCrawlerBridge"] = None


def get_mediacrawler_bridge() -> "MediaCrawlerBridge":
    """获取 MediaCrawlerBridge 单例"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = MediaCrawlerBridge()
    return _bridge_instance


class MediaCrawlerBridge:
    """MediaCrawler 桥接层 — 连接 szyg 与 MediaCrawler"""

    # 平台到域名的映射表
    _PLATFORM_DOMAINS = {
        "douyin": [".douyin.com", "douyin.com"],
        "xhs": [".xiaohongshu.com", "xiaohongshu.com"],
        "kuaishou": [".kuaishou.com", "kuaishou.com"],
        "bilibili": [".bilibili.com", "bilibili.com"],
    }

    def __init__(self):
        self.session_manager = SessionManager()
        self.browser_pool = get_browser_pool(headless=True)
        self._clients: Dict[str, Any] = {}

    async def _prepare_browser_context(self, platform: Platform) -> tuple:
        """
        从 SessionManager 加载 storage_state → 创建 BrowserContext

        Returns:
            (context, page, cookie_dict, user_agent)
        """
        # 加载 storage_state
        state = self.session_manager.load(platform)
        if not state:
            logger.warning(f"[MediaCrawler] No storage_state for {platform.value}")
            return None, None, {}, ""

        # 创建 BrowserContext
        context = await self.browser_pool.get_context(platform.value, storage_state=state)
        page = await context.new_page()

        # 提取 Cookie
        cookies = state.get("cookies", [])
        domains = self._PLATFORM_DOMAINS.get(platform.value, [platform.value])
        cookie_dict = {c["name"]: c["value"] for c in cookies if any(c.get("domain", "").endswith(d) for d in domains)}

        # 获取 User-Agent
        user_agent = await page.evaluate("() => navigator.userAgent")

        logger.info(f"[MediaCrawler] Browser context prepared for {platform.value} ({len(cookie_dict)} cookies)")
        return context, page, cookie_dict, user_agent

    async def _get_douyin_client(self) -> Optional[DouYinClient]:
        """获取或创建 DouYinClient"""
        if not MEDIACRAWLER_AVAILABLE:
            return None

        # 检查缓存的 client 是否仍然有效
        if "douyin" in self._clients:
            client = self._clients["douyin"]
            try:
                # 检查 page 是否仍然连接
                if client.playwright_page and not client.playwright_page.is_closed():
                    return client
                else:
                    logger.warning("[MediaCrawler] Cached client page is closed, recreating")
                    self._clients.pop("douyin", None)
            except Exception as e:
                logger.warning(f"[MediaCrawler] Cached client check failed: {e}, recreating")
                self._clients.pop("douyin", None)

        context, page, cookie_dict, user_agent = await self._prepare_browser_context(Platform.DOUYIN)
        if not context:
            return None

        # 构造请求头
        headers = {
            "User-Agent": user_agent,
            "Cookie": "; ".join([f"{k}={v}" for k, v in cookie_dict.items()]),
            "Host": "www.douyin.com",
            "Origin": "https://www.douyin.com/",
            "Referer": "https://www.douyin.com/",
            "Content-Type": "application/json;charset=UTF-8",
        }

        # 创建 DouYinClient
        client = DouYinClient(
            timeout=60,
            headers=headers,
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        self._clients["douyin"] = client
        logger.info("[MediaCrawler] DouYinClient initialized")
        return client

    async def search_douyin(
        self,
        keyword: str,
        limit: int = 15,
        sort_type: int = 0,
        publish_time: int = 0,
    ) -> list[dict]:
        """
        抖音搜索

        Args:
            keyword: 搜索关键词
            limit: 返回数量
            sort_type: 0=综合, 1=最多点赞, 2=最新发布
            publish_time: 0=不限, 1=一天内, 7=一周内, 180=半年内

        Returns:
            统一格式的搜索结果列表
        """
        if not MEDIACRAWLER_AVAILABLE:
            logger.warning("[MediaCrawler] MediaCrawler not available")
            return []

        client = await self._get_douyin_client()
        if not client:
            logger.warning("[MediaCrawler] Failed to get DouYinClient")
            return []

        results = []
        offset = 0
        page_size = 15  # MediaCrawler 固定每页 15 条

        try:
            # 分页获取直到达到 limit
            while len(results) < limit:
                # 调用 MediaCrawler 搜索 API
                response = await client.search_info_by_keyword(
                    keyword=keyword,
                    offset=offset,
                    search_channel=SearchChannelType.GENERAL,
                    sort_type=SearchSortType(sort_type),
                    publish_time=PublishTimeType(publish_time),
                )

                # 解析响应（兼容 dict/list）
                if not response or "data" not in response:
                    logger.warning(f"[MediaCrawler] Invalid response at offset {offset}")
                    break

                raw = response.get("data", [])
                if isinstance(raw, dict):
                    raw = raw.get("aweme_list", raw.get("data", []))
                if not isinstance(raw, list):
                    logger.warning(f"[MediaCrawler] Response data is not list: {type(raw)}")
                    break

                if not raw:
                    logger.info(f"[MediaCrawler] No more results at offset {offset}")
                    break

                for item in raw:
                    aweme_info = item.get("aweme_info", {})
                    if not aweme_info:
                        continue

                    # 提取数据
                    video_id = str(aweme_info.get("aweme_id", ""))
                    desc = aweme_info.get("desc", "")
                    author_obj = aweme_info.get("author", {})
                    stats = aweme_info.get("statistics", {})
                    video_obj = aweme_info.get("video", {})
                    cover_obj = video_obj.get("cover", video_obj.get("origin_cover", {}))

                    # 转换为统一格式
                    normalized = _normalize_search_result({
                        "video_id": video_id,
                        "title": desc[:200],
                        "description": desc[:500],
                        "author": author_obj.get("nickname", author_obj.get("name", "")) if isinstance(author_obj, dict) else "",
                        "author_followers": author_obj.get("follower_count", 0) if isinstance(author_obj, dict) else 0,
                        "url": f"https://www.douyin.com/video/{video_id}",
                        "cover": cover_obj.get("url_list", [None])[0] if isinstance(cover_obj, dict) else "",
                        "plays": stats.get("play_count", stats.get("digg_count", 0)) if isinstance(stats, dict) else 0,
                        "likes": stats.get("digg_count", 0) if isinstance(stats, dict) else 0,
                        "comments_count": stats.get("comment_count", 0) if isinstance(stats, dict) else 0,
                        "shares": stats.get("share_count", 0) if isinstance(stats, dict) else 0,
                        "published_at": aweme_info.get("create_time", ""),
                    }, "douyin")

                    results.append(normalized)
                    if len(results) >= limit:
                        break

                # 更新 offset 继续下一页
                offset += page_size

            logger.info(f"[MediaCrawler] Douyin search: {len(results)} results for '{keyword}'")
            return results

        except Exception as e:
            logger.error(f"[MediaCrawler] Douyin search failed: {e}", exc_info=True)
            # 异常时清除缓存 client
            self._clients.pop("douyin", None)
            return []
        finally:
            # 归还 browser context 避免泄漏
            try:
                await self.browser_pool.return_context(Platform.DOUYIN.value)
                logger.debug("[MediaCrawler] Browser context returned")
            except Exception as e:
                logger.warning(f"[MediaCrawler] Failed to return context: {e}")

    async def get_douyin_detail(self, aweme_id: str) -> Optional[dict]:
        """获取抖音视频详情"""
        if not MEDIACRAWLER_AVAILABLE:
            return None

        client = await self._get_douyin_client()
        if not client:
            return None

        try:
            response = await client.get_video_by_id(aweme_id)
            logger.info(f"[MediaCrawler] Douyin detail: {aweme_id}")
            return response
        except Exception as e:
            logger.error(f"[MediaCrawler] Douyin detail failed: {e}", exc_info=True)
            return None
        finally:
            # 归还 browser context 避免泄漏
            try:
                await self.browser_pool.return_context(Platform.DOUYIN.value)
                logger.debug("[MediaCrawler] Browser context returned")
            except Exception as e:
                logger.warning(f"[MediaCrawler] Failed to return context: {e}")

    async def get_douyin_comments(self, aweme_id: str, count: int = 20) -> list[dict]:
        """获取抖音视频评论"""
        if not MEDIACRAWLER_AVAILABLE:
            return []

        client = await self._get_douyin_client()
        if not client:
            return []

        try:
            # MediaCrawler 方法名是 get_aweme_comments，参数是 cursor
            response = await client.get_aweme_comments(aweme_id, cursor=0)
            logger.info(f"[MediaCrawler] Douyin comments: {len(response.get('comments', []))} for {aweme_id}")
            comments = response.get("comments", [])
            # 截取前 count 条
            return comments[:count] if count < len(comments) else comments
        except Exception as e:
            logger.error(f"[MediaCrawler] Douyin comments failed: {e}", exc_info=True)
            return []
        finally:
            # 归还 browser context 避免泄漏
            try:
                await self.browser_pool.return_context(Platform.DOUYIN.value)
                logger.debug("[MediaCrawler] Browser context returned")
            except Exception as e:
                logger.warning(f"[MediaCrawler] Failed to return context: {e}")

    # 后续可扩展其他平台的搜索方法
    async def search_xhs(self, keyword: str, limit: int = 15) -> list[dict]:
        """小红书搜索（待实现）"""
        logger.warning("[MediaCrawler] Xhs search not implemented yet")
        return []

    async def search_kuaishou(self, keyword: str, limit: int = 15) -> list[dict]:
        """快手搜索（待实现）"""
        logger.warning("[MediaCrawler] Kuaishou search not implemented yet")
        return []

    async def search_bilibili(self, keyword: str, limit: int = 15) -> list[dict]:
        """B站搜索（待实现）"""
        logger.warning("[MediaCrawler] Bilibili search not implemented yet")
        return []
