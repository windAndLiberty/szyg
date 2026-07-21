"""
Acquisition Adapters — 统一采集适配层

集成开源项目实现各平台的 search / send_comment / get_comments / send_dm 功能:
  - B站: bilibili-api-python (API方式，无需浏览器)
  - 小红书: Playwright 浏览器自动化 (复用现有 BrowserPool)
  - 抖音: Playwright 浏览器自动化 (复用现有 BrowserPool)
  - 快手: Playwright 浏览器自动化 (复用现有 BrowserPool)
  - 微博: Playwright 浏览器自动化 (公开搜索页)

每个适配器返回统一格式的数据结构，供 MCP Server 和引擎层调用。
"""
import asyncio
import html
import logging
import re
import json
from typing import Optional

logger = logging.getLogger(__name__)

from .normalize_utils import _normalize_search_result, _normalize_comment


def _parse_social_number(value: str) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except Exception:
        digits = re.sub(r"\D+", "", text)
        return int(digits) if digits else 0


def _reply_count(value) -> int:
    if isinstance(value, int):
        return value
    return len(value or [])


def _search_failure_diagnostics(message: str) -> dict:
    text = str(message or "").lower()
    if any(token in text for token in ("login", "cookie", "登录", "扫码", "unauthorized", "forbidden")):
        return {"status": "needs_login", "error_code": "login_required", "message": "需要登录后才能读取公开内容"}
    if any(token in text for token in ("captcha", "verify", "risk", "风控", "验证", "访问频繁", "安全检查")):
        return {"status": "restricted", "error_code": "platform_restricted", "message": "平台需要人工验证，本轮已停止读取"}
    if any(token in text for token in ("not implemented", "unsupported", "not available")):
        return {"status": "unavailable", "error_code": "collector_unavailable", "message": "该渠道采集能力暂不可用"}
    return {"status": "failed", "error_code": "collection_failed", "message": str(message or "公开信息读取失败")[:200]}


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

    def _set_search_diagnostics(self, status: str, message: str = "", error_code: str = "") -> None:
        self._last_search_diagnostics = {
            "status": status,
            "message": message,
            "error_code": error_code,
        }

    def search_diagnostics(self) -> dict:
        return dict(getattr(self, "_last_search_diagnostics", {}))

    def status(self) -> dict:
        return {"platform": self.platform, "ready": True, "message": "ok"}


# ── Bilibili Acquisition Adapter (API-based) ─────────────────────────────

class BilibiliAcquisitionAdapter(BaseAcquisitionAdapter):
    """B站采集适配器 — 基于 bilibili-api-python 库，纯API调用无需浏览器"""

    platform = "bilibili"

    def __init__(self):
        self._credential = None
        self._cred_ready = False

    @staticmethod
    def _credential_values_from_storage_state(storage_state: dict) -> dict:
        """Map a Playwright storage state to bilibili-api credential fields."""
        cookies = {
            str(item.get("name", "")): str(item.get("value", ""))
            for item in storage_state.get("cookies", [])
            if isinstance(item, dict)
        }
        return {
            "sessdata": cookies.get("SESSDATA", ""),
            "bili_jct": cookies.get("bili_jct", ""),
            "buvid3": cookies.get("buvid3", ""),
            "dedeuserid": cookies.get("DedeUserID", ""),
        }

    def _load_credential_values(self) -> tuple[dict, str]:
        """Load legacy credentials first, then the active channel account session."""
        from szyg.data_path import DATA_DIR

        cred_path = DATA_DIR / "sessions" / "bilibili_credential.json"
        if cred_path.exists():
            with open(cred_path, "r", encoding="utf-8") as f:
                return json.load(f), "legacy credential file"

        from szyg.channel_accounts import get_default_account_for_platform

        account = get_default_account_for_platform("bilibili") or {}
        session_path = str(account.get("session_path") or "").strip()
        if not session_path:
            return {}, ""
        from pathlib import Path

        path = Path(session_path)
        if not path.exists():
            return {}, ""
        with open(path, "r", encoding="utf-8") as f:
            storage_state = json.load(f)
        values = self._credential_values_from_storage_state(storage_state)
        if values.get("sessdata") and values.get("bili_jct"):
            return values, f"channel account {account.get('id', '')}"
        return {}, ""

    def _get_credential(self):
        """Load Bilibili credentials from the shared channel-account session."""
        if self._cred_ready:
            return self._credential

        try:
            from bilibili_api import Credential
            data, source = self._load_credential_values()
            if data:
                self._credential = Credential(
                    sessdata=data.get("sessdata", ""),
                    bili_jct=data.get("bili_jct", ""),
                    buvid3=data.get("buvid3", ""),
                    dedeuserid=data.get("dedeuserid", ""),
                )
                logger.info("Bilibili credential loaded from %s", source)
            else:
                logger.warning("Bilibili account session not found, API calls will be limited to public data")
                self._credential = None
        except Exception as e:
            logger.warning(f"Failed to load Bilibili credential: {e}")
            self._credential = None

        self._cred_ready = True
        return self._credential

    def _invalidate_credential(self) -> None:
        """Force the next operation to reload the shared account session."""
        self._credential = None
        self._cred_ready = False

    async def search(self, keyword: str, limit: int = 20) -> list[dict]:
        """搜索B站视频"""
        self._set_search_diagnostics("running")
        try:
            from bilibili_api import search as bili_search
            from bilibili_api.search import SearchObjectType

            result = await bili_search.search_by_type(
                keyword=keyword,
                search_type=SearchObjectType.VIDEO,
                page=1,
                page_size=min(limit, 42),
            )
            raw_results = result.get("result", [])
            videos = []
            for item in raw_results[:limit]:
                source_url = str(item.get("arcurl") or item.get("url") or "")
                bvid = str(item.get("bvid") or "")
                if not bvid:
                    match = re.search(r"/(BV[a-zA-Z0-9]+)", source_url)
                    bvid = match.group(1) if match else ""
                if not source_url and bvid:
                    source_url = f"https://www.bilibili.com/video/{bvid}"
                cover = str(item.get("pic") or "")
                if cover.startswith("//"):
                    cover = f"https:{cover}"
                videos.append(_normalize_search_result({
                    "video_id": bvid,
                    "title": re.sub(r'<[^>]+>', '', item.get("title", "")),
                    "description": re.sub(r'<[^>]+>', '', item.get("description", "")),
                    "author": item.get("author", ""),
                    "author_followers": 0,
                    "url": source_url,
                    "cover": cover,
                    "plays": item.get("play", 0),
                    "likes": 0,
                    "comments_count": item.get("video_review", 0),
                    "shares": 0,
                    "published_at": item.get("pubdate", ""),
                    "duration": item.get("duration", 0),
                }, "bilibili"))
            enriched = await asyncio.gather(
                *[self._enrich_public_video(row) for row in videos[:10]],
                return_exceptions=True,
            )
            complete = [
                original if isinstance(detail, Exception) else detail
                for original, detail in zip(videos[:10], enriched)
            ]
            rows = [*complete, *videos[10:]]
            self._set_search_diagnostics("success" if rows else "no_data")
            return rows
        except ModuleNotFoundError:
            logger.warning("bilibili-api-python not installed, using public HTML fallback")
            rows = await self._search_public_html(keyword, limit)
            self._set_search_diagnostics("success" if rows else "no_data")
            return rows
        except Exception as e:
            logger.error(f"Bilibili search error: {e}")
            fallback = await self._search_public_html(keyword, limit)
            if fallback:
                self._set_search_diagnostics("success", "已通过公开页面读取")
            else:
                diagnostics = _search_failure_diagnostics(str(e))
                self._set_search_diagnostics(**diagnostics)
            return fallback

    async def search_public(self, keyword: str, limit: int = 20) -> list[dict]:
        """Read visible public search results without the optional SDK."""
        self._set_search_diagnostics("running")
        rows = await self._search_public_html(keyword, limit)
        self._set_search_diagnostics("success" if rows else "no_data")
        return rows

    async def _search_public_html(self, keyword: str, limit: int = 20) -> list[dict]:
        """Search Bilibili public HTML as a dependency-free fallback."""
        from urllib.parse import quote
        from urllib.request import Request, urlopen

        def _fetch() -> str:
            url = f"https://search.bilibili.com/all?keyword={quote(keyword)}"
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            with urlopen(req, timeout=12) as resp:
                return resp.read().decode("utf-8", "ignore")

        try:
            page = await asyncio.to_thread(_fetch)
        except Exception as exc:
            logger.warning("Bilibili public HTML fallback failed: %s", exc)
            return []

        rows: list[dict] = []
        seen: set[str] = set()
        for match in re.finditer(r'href="(?:https?:)?//www\.bilibili\.com/video/(BV[a-zA-Z0-9]+)/?[^"]*"', page):
            bvid = match.group(1)
            if bvid in seen:
                continue
            seen.add(bvid)
            window = page[max(0, match.start() - 300): min(len(page), match.end() + 2200)]
            alt_match = re.search(r'<img[^>]+alt="([^"]+)"', window)
            title = html.unescape(alt_match.group(1)).strip() if alt_match else bvid
            cover_match = re.search(r'<img[^>]+src="([^"]+)"', window)
            cover = html.unescape(cover_match.group(1)).strip() if cover_match else ""
            if cover.startswith("//"):
                cover = f"https:{cover}"
            author_match = re.search(r'class="[^"]*bili-video-card__info--author[^"]*"[^>]*>(.*?)</span>', window, re.S)
            author = re.sub(r"<[^>]+>", "", html.unescape(author_match.group(1))).strip() if author_match else ""
            rows.append(_normalize_search_result({
                "video_id": bvid,
                "title": title[:200],
                "description": title[:500],
                "author": author,
                "url": f"https://www.bilibili.com/video/{bvid}/",
                "cover": cover,
            }, "bilibili"))
            if len(rows) >= limit:
                break

        enriched = await asyncio.gather(
            *[self._enrich_public_video(row) for row in rows],
            return_exceptions=True,
        )
        next_rows = []
        for original, item in zip(rows, enriched):
            next_rows.append(original if isinstance(item, Exception) else item)
        return next_rows

    async def _enrich_public_video(self, row: dict) -> dict:
        """Fetch public Bilibili video metadata by BV id."""
        from urllib.parse import quote
        from urllib.request import Request, urlopen

        bvid = str(row.get("video_id") or "")
        if not bvid:
            return row

        def _fetch() -> dict:
            url = f"https://api.bilibili.com/x/web-interface/view?bvid={quote(bvid)}"
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
                "Referer": "https://www.bilibili.com",
                "Accept": "application/json,text/plain,*/*",
            })
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", "ignore"))
            if data.get("code") != 0:
                return {}
            return data.get("data") or {}

        try:
            detail = await asyncio.to_thread(_fetch)
        except Exception as exc:
            logger.debug("Bilibili detail fallback failed for %s: %s", bvid, exc)
            return row
        if not detail:
            return row

        stat = detail.get("stat") or {}
        owner = detail.get("owner") or {}
        owner_mid = str(owner.get("mid") or "")
        author_stat: dict = {}
        if owner_mid:
            def _fetch_author_stat() -> dict:
                url = f"https://api.bilibili.com/x/relation/stat?vmid={quote(owner_mid)}"
                req = Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
                    "Referer": f"https://space.bilibili.com/{owner_mid}",
                    "Accept": "application/json,text/plain,*/*",
                })
                with urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8", "ignore"))
                if data.get("code") != 0:
                    return {}
                return data.get("data") or {}

            try:
                author_stat = await asyncio.to_thread(_fetch_author_stat)
            except Exception as exc:
                logger.debug("Bilibili author stat fallback failed for %s: %s", owner_mid, exc)
        enriched = dict(row)
        enriched.update(_normalize_search_result({
            "video_id": bvid,
            "title": detail.get("title") or row.get("title") or "",
            "description": detail.get("desc") or row.get("description") or row.get("title") or "",
            "author": owner.get("name") or row.get("author") or "",
            "author_followers": author_stat.get("follower", 0),
            "url": f"https://www.bilibili.com/video/{bvid}/",
            "cover": detail.get("pic") or row.get("cover") or "",
            "plays": stat.get("view", 0),
            "likes": stat.get("like", 0),
            "comments_count": stat.get("reply", 0),
            "shares": stat.get("share", 0),
            "published_at": detail.get("pubdate", ""),
            "duration": detail.get("duration", 0),
        }, "bilibili"))
        enriched["favorites"] = stat.get("favorite", 0)
        enriched["coins"] = stat.get("coin", 0)
        enriched["danmaku"] = stat.get("danmaku", 0)
        enriched["author_id"] = owner_mid
        enriched["author_profile_url"] = f"https://space.bilibili.com/{owner_mid}" if owner_mid else ""
        enriched["author_following"] = author_stat.get("following", 0)
        return enriched

    async def get_comments(self, video_url: str, limit: int = 30) -> list[dict]:
        """获取B站视频评论"""
        try:
            from bilibili_api import comment as bili_comment, video as bili_video

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
                    "reply_count": _reply_count(item.get("replies")),
                    "ip_location": item.get("reply_control", {}).get("location", ""),
                }, "bilibili"))
            return comments
        except ModuleNotFoundError:
            logger.warning("bilibili-api-python not installed, using public comment fallback")
            return await self._get_comments_public(video_url, limit)
        except Exception as e:
            logger.error(f"Bilibili get_comments error: {e}")
            return await self._get_comments_public(video_url, limit)

    async def _get_comments_public(self, video_url: str, limit: int = 30) -> list[dict]:
        """Fetch public Bilibili comments without bilibili-api-python."""
        from urllib.parse import quote
        from urllib.request import Request, urlopen

        bvid = self._extract_bvid(video_url)
        if not bvid:
            return []

        def _fetch_json(url: str) -> dict:
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
                "Referer": f"https://www.bilibili.com/video/{bvid}/",
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))

        try:
            detail = await asyncio.to_thread(
                _fetch_json,
                f"https://api.bilibili.com/x/web-interface/view?bvid={quote(bvid)}",
            )
            if detail.get("code") != 0:
                return []
            aid = (detail.get("data") or {}).get("aid")
            if not aid:
                return []
        except Exception as exc:
            logger.debug("Bilibili public comment detail failed for %s: %s", bvid, exc)
            return []

        ps = max(1, min(int(limit or 30), 20))
        endpoints = [
            f"https://api.bilibili.com/x/v2/reply?type=1&oid={aid}&sort=2&pn=1&ps={ps}",
            f"https://api.bilibili.com/x/v2/reply/main?type=1&oid={aid}&mode=3&next=0&ps={ps}",
        ]
        raw_comments: list[dict] = []
        for endpoint in endpoints:
            try:
                data = await asyncio.to_thread(_fetch_json, endpoint)
            except Exception as exc:
                logger.debug("Bilibili public comments failed for %s: %s", bvid, exc)
                continue
            if data.get("code") != 0:
                continue
            payload = data.get("data") or {}
            raw_comments = payload.get("replies") or []
            if raw_comments:
                break

        comments: list[dict] = []
        for item in raw_comments[:limit]:
            comments.append(_normalize_comment({
                "comment_id": item.get("rpid", 0),
                "author": item.get("member", {}).get("uname", ""),
                "author_id": item.get("member", {}).get("mid", item.get("mid", "")),
                "text": item.get("content", {}).get("message", ""),
                "likes": item.get("like", 0),
                "created_at": item.get("ctime", 0),
                "reply_count": item.get("rcount", 0) or len(item.get("replies") or []),
                "ip_location": item.get("reply_control", {}).get("location", ""),
            }, "bilibili"))
        return comments

    async def send_comment(self, video_url: str, comment_text: str) -> dict:
        """发送B站评论"""
        try:
            from bilibili_api import comment as bili_comment, video as bili_video

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
            comment_id = str(
                (result or {}).get("rpid")
                or ((result or {}).get("reply") or {}).get("rpid")
                or ""
            )
            return {
                "success": True,
                "message": "评论已发送",
                "comment_id": comment_id,
                "source_url": video_url,
                "evidence": "platform_api",
                "result": result,
            }
        except Exception as e:
            logger.error(f"Bilibili send_comment error: {e}")
            if any(token in str(e).lower() for token in ("credential", "sessdata", "csrf", "-101", "-111", "登录")):
                self._invalidate_credential()
            return {"success": False, "error": str(e)}

    async def send_dm(self, user_id: str, text: str) -> dict:
        """发送B站私信"""
        try:
            from bilibili_api import session as bili_session

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
    """基于 Playwright 的采集适配器 — 用于抖音/小红书/快手/微博

    复用现有平台适配器的 BrowserPool 和 SessionManager，
    在浏览器中执行搜索、评论获取和评论发送操作。
    """

    def __init__(self, platform: str):
        self.platform = platform
        self._pool = None
        self._context = None
        self._page = None
        self._session = None
        self._context_key = platform

    def _load_account_storage_state(self) -> dict | None:
        """Load the connected account session without mutating its source file."""
        try:
            from pathlib import Path
            from szyg.channel_accounts import get_default_account_for_platform

            account = get_default_account_for_platform(self.platform)
            path = Path(str((account or {}).get("session_path") or ""))
            if not path.is_file():
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._context_key = f"{self.platform}:{(account or {}).get('id') or 'default'}"
            return {
                "cookies": payload.get("cookies") or [],
                "origins": payload.get("origins") or [],
            }
        except Exception as exc:
            logger.debug("Failed to load account session for %s: %s", self.platform, exc)
            return None

    async def _ensure_browser(self):
        """确保浏览器上下文已初始化（headless 模式，无可见窗口）"""
        if self._page:
            return self._page

        from szyg.platforms.browser_pool import get_browser_pool
        from szyg.platforms.session_manager import get_session_manager
        from szyg.publisher import Platform

        self._pool = get_browser_pool(headless=True)
        await self._pool.start()
        self._session = get_session_manager()

        platform_map = {
            "douyin": Platform.DOUYIN,
            "xhs": Platform.XHS,
            "bilibili": Platform.BILIBILI,
            "kuaishou": Platform.KUAISHOU,
            "weibo": Platform.WEIBO,
        }
        p = platform_map.get(self.platform)
        if not p:
            raise ValueError(f"Unknown platform: {self.platform}")

        storage_state = self._load_account_storage_state() or self._session.load(p)
        self._context = await self._pool.get_context(
            platform_key=self._context_key,
            storage_state=storage_state,
        )
        self._page = await self._context.new_page()
        return self._page

    async def _close_browser(self):
        """归还浏览器上下文到池中"""
        if self._page:
            try:
                await self._page.close()
            except Exception as e:
                logger.debug("Failed to close collector page for %s: %s", self.platform, e)
        if self._context:
            try:
                await self._pool.return_context(self._context_key)
            except Exception as e:
                logger.debug("Failed to return browser context for %s: %s", self.platform, e)
        self._page = None
        self._context = None

    async def search(self, keyword: str, limit: int = 20) -> list[dict]:
        """在平台搜索视频 — 子类可覆盖实现平台特定逻辑"""
        self._set_search_diagnostics("running")
        try:
            page = await self._ensure_browser()
        except Exception as e:
            logger.error(f"{self.platform} _ensure_browser failed: {e}", exc_info=True)
            self._set_search_diagnostics(**_search_failure_diagnostics(str(e)))
            return []
        results = []

        try:
            if self.platform == "douyin":
                results = await self._search_douyin(page, keyword, limit)
            elif self.platform == "xhs":
                results = await self._search_xhs(page, keyword, limit)
            elif self.platform == "kuaishou":
                results = await self._search_kuaishou(page, keyword, limit)
            elif self.platform == "weibo":
                results = await self._search_weibo(page, keyword, limit)
        except Exception as e:
            logger.error(f"{self.platform} search error: {e}", exc_info=True)
            self._set_search_diagnostics(**_search_failure_diagnostics(str(e)))
        finally:
            if not results and self.search_diagnostics().get("status") == "running":
                self._set_search_diagnostics(**await self._detect_visible_state(page))
            elif results:
                self._set_search_diagnostics("success")
            await self._close_browser()

        return results

    async def _search_douyin(self, page, keyword: str, limit: int) -> list[dict]:
        """抖音搜索 — 优先 MediaCrawler 桥接模式，fallback 到浏览器拦截模式"""
        # ── 策略 1: MediaCrawler 桥接模式 ─────────────────────────────
        try:
            from .mediacrawler_bridge import get_mediacrawler_bridge
            bridge = get_mediacrawler_bridge()
            if bridge.available:
                mc_results = await bridge.search_douyin(keyword, limit)
                if mc_results:
                    logger.info(f"[MediaCrawler] Douyin search succeeded: {len(mc_results)} results")
                    return mc_results
                logger.warning("[MediaCrawler] Douyin search returned 0 results, falling back to browser mode")
        except Exception as e:
            logger.warning(f"[MediaCrawler] Douyin search failed: {e}, falling back to browser mode")

        # ── 策略 2: 浏览器拦截模式 (fallback) ─────────────────────────
        logger.info("[BrowserFallback] Using browser interception mode")
        results: list[dict] = []
        seen_ids: set[str] = set()

        def _extract_from_api_data(data: dict) -> list[dict]:
            """从抖音搜索 API JSON 响应中提取视频列表"""
            # 保存原始 JSON 用于调试
            import json
            import os
            os.makedirs("data/audit/douyin", exist_ok=True)
            with open("data/audit/douyin/last_api_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            items = []
            # 抖音搜索 API 返回结构: { data: [ { aweme_info: {...}, ... } ] }
            raw = data.get("data", [])
            if isinstance(raw, dict):
                raw = raw.get("aweme_list", raw.get("data", []))
            if not isinstance(raw, list):
                return items
            for entry in raw:
                aweme = entry.get("aweme_info") or entry.get("aweme") or entry
                if not aweme or not isinstance(aweme, dict):
                    continue
                vid = str(aweme.get("aweme_id", aweme.get("id", "")))
                if not vid or vid in seen_ids:
                    continue
                desc = aweme.get("desc", "")
                author_obj = aweme.get("author", aweme.get("author_info", {}))
                stats = aweme.get("statistics", aweme.get("stats", {}))
                video_obj = aweme.get("video", {})
                cover_obj = video_obj.get("cover", video_obj.get("origin_cover", {}))
                play_url = video_obj.get("play_addr", {}).get("url_list", [None])
                items.append({
                    "video_id": vid,
                    "title": desc[:200],
                    "description": desc[:500],
                    "author": author_obj.get("nickname", author_obj.get("name", "")) if isinstance(author_obj, dict) else "",
                    "author_followers": author_obj.get("follower_count", 0) if isinstance(author_obj, dict) else 0,
                    "url": f"https://www.douyin.com/video/{vid}",
                    "cover": cover_obj.get("url_list", [None])[0] if isinstance(cover_obj, dict) else "",
                    "plays": stats.get("play_count", stats.get("digg_count", 0)) if isinstance(stats, dict) else 0,
                    "likes": stats.get("digg_count", 0) if isinstance(stats, dict) else 0,
                    "comments_count": stats.get("comment_count", 0) if isinstance(stats, dict) else 0,
                    "shares": stats.get("share_count", 0) if isinstance(stats, dict) else 0,
                    "published_at": aweme.get("create_time", ""),
                })
            return items

        # ── 策略 1: 拦截网络响应 ──────────────────────────────────
        api_results: list[dict] = []

        async def _on_response(response):
            url = response.url
            logger.info("Douyin response url: %s", url)
            if "/aweme/v1/web/general/search/" in url or "/aweme/v1/web/search/item/" in url:
                try:
                    body = await response.json()
                    logger.info("Douyin API matched, body keys: %s", list(body.keys()))
                    extracted = _extract_from_api_data(body)
                    api_results.extend(extracted)
                    logger.info("Douyin API intercept: got %d items from %s", len(extracted), url)
                except Exception as e:
                    logger.warning("Douyin API response parse failed: %s | url=%s", e, url)

        page.on("response", _on_response)
        try:
            await page.goto(
                f"https://www.douyin.com/search/{keyword}",
                wait_until="domcontentloaded",
            )
            # 等待 API 响应或滚动触发加载
            await page.wait_for_timeout(2000)

            # 滚动几次触发懒加载
            for i in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(2000)

            # 新增：截图 + 保存 HTML
            import os
            os.makedirs("data/audit/douyin", exist_ok=True)
            await page.screenshot(path="data/audit/douyin/search_page.png", full_page=True)
            html = await page.content()
            with open("data/audit/douyin/search_page.html", "w", encoding="utf-8") as f:
                f.write(html)

            # 新增：统计各种可能的选择器
            selectors = [
                '[data-e2e="search-video-item"]',
                '[data-e2e="search-result-video"]',
                'ul[data-e2e="search-result-list"] li',
                'a[href*="/video/"]',
                'a[href*="/video/"] img',
                '[class*="search-result"]',
                '[class*="video-card"]',
            ]
            for sel in selectors:
                count = len(await page.query_selector_all(sel))
                logger.info("Douyin selector %s => %d", sel, count)

            # 如果 API 拦截已拿到足够数据，直接返回
            if api_results:
                for item in api_results:
                    vid = item["video_id"]
                    if vid in seen_ids:
                        continue
                    seen_ids.add(vid)
                    results.append(_normalize_search_result(item, "douyin"))
                    if len(results) >= limit:
                        break
                logger.info("Douyin search via API intercept: %d results", len(results))
                return results

            # ── 策略 2: DOM 选择器 fallback ────────────────────────
            logger.warning("Douyin API intercept got 0 results, falling back to DOM scraping")
            video_items = await page.query_selector_all('[data-e2e="search-video-item"]')
            if not video_items:
                video_items = await page.query_selector_all('[data-e2e="search-result-video"]')
            if not video_items:
                video_items = await page.query_selector_all('ul[data-e2e="search-result-list"] li')
            if not video_items:
                video_items = await page.query_selector_all('a[href*="/video/"]')

            for item in video_items[:limit * 2]:
                try:
                    if await item.evaluate("el => el.tagName") == "A":
                        link = item
                    else:
                        link = await item.query_selector("a[href*='/video/']") or await item.query_selector("a")
                    if not link:
                        continue
                    href = await link.get_attribute("href") or ""
                    if "/video/" not in href:
                        continue
                    aweme_id = re.search(r'/video/(\d+)', href)
                    vid = aweme_id.group(1) if aweme_id else ""
                    if vid in seen_ids:
                        continue
                    seen_ids.add(vid)
                    title = (await item.inner_text()).strip()[:200]
                    results.append(_normalize_search_result({
                        "video_id": vid,
                        "title": title,
                        "url": f"https://www.douyin.com{href}" if href.startswith("/") else href,
                    }, "douyin"))
                    if len(results) >= limit:
                        break
                except Exception:
                    continue
            logger.info("Douyin search via DOM fallback: %d results", len(results))
        finally:
            page.remove_listener("response", _on_response)
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
        """快手搜索，优先读取页面自身的结构化响应。"""
        from urllib.parse import quote

        api_results: list[dict] = []

        async def _on_response(response):
            if "graphql" not in str(response.url).lower():
                return
            try:
                payload = await response.json()
                api_results.extend(self._normalize_kuaishou_search_payload(payload, limit))
            except Exception:
                return

        page.on("response", _on_response)
        try:
            await page.goto(
                f"https://www.kuaishou.com/search/video?searchKey={quote(keyword)}",
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(2500)
            await page.evaluate("window.scrollBy(0, 900)")
            await page.wait_for_timeout(1500)
        finally:
            page.remove_listener("response", _on_response)

        if api_results:
            unique = {item["video_id"]: item for item in api_results if item.get("video_id")}
            return list(unique.values())[:limit]

        video_items = await page.query_selector_all(
            '.video-item, [class*="video-card"], a[href*="/short-video/"]'
        )
        results: list[dict] = []
        seen_ids: set[str] = set()
        for item in video_items[:limit * 3]:
            try:
                tag_name = await item.evaluate("el => el.tagName")
                link = item if tag_name == "A" else await item.query_selector('a[href*="/short-video/"]')
                href = await link.get_attribute("href") if link else ""
                video_id = re.search(r'/short-video/([a-zA-Z0-9]+)', href or "")
                vid = video_id.group(1) if video_id else ""
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)
                title = (await item.inner_text()).strip()
                results.append(_normalize_search_result({
                    "video_id": vid,
                    "title": title[:200],
                    "url": href if href.startswith("http") else f"https://www.kuaishou.com{href}",
                }, "kuaishou"))
                if len(results) >= limit:
                    break
            except Exception:
                continue
        return results

    @staticmethod
    def _normalize_kuaishou_search_payload(payload: dict, limit: int = 20) -> list[dict]:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        search = (data or {}).get("visionSearchPhoto") or {}
        if search.get("result") not in (None, 1):
            return []
        rows: list[dict] = []
        for feed in (search.get("feeds") or [])[:limit]:
            photo = feed.get("photo") or {}
            author = feed.get("author") or {}
            video_id = str(photo.get("id") or "")
            if not video_id:
                continue
            rows.append(_normalize_search_result({
                "video_id": video_id,
                "title": str(photo.get("caption") or "")[:200],
                "description": str(photo.get("caption") or "")[:500],
                "author": author.get("name") or author.get("nickname") or "",
                "url": f"https://www.kuaishou.com/short-video/{video_id}",
                "cover": photo.get("coverUrl") or photo.get("cover_url") or "",
                "plays": photo.get("viewCount") or photo.get("view_count") or 0,
                "likes": photo.get("realLikeCount") or photo.get("likeCount") or 0,
                "comments_count": photo.get("commentCount") or 0,
                "published_at": photo.get("timestamp") or "",
            }, "kuaishou"))
        return rows

    async def _detect_visible_state(self, page) -> dict:
        url = str(getattr(page, "url", "") or "").lower()
        if any(token in url for token in ("login", "passport", "signin", "sso")):
            return {"status": "needs_login", "error_code": "login_required", "message": "需要登录后才能读取公开内容"}
        try:
            body = (await page.locator("body").inner_text(timeout=2000))[:5000]
        except Exception:
            body = ""
        if any(token in body for token in ("安全验证", "访问频繁", "验证码", "完成验证", "异常访问")):
            return {"status": "restricted", "error_code": "platform_restricted", "message": "平台需要人工验证，本轮已停止读取"}
        if any(token in body for token in ("登录后查看", "请先登录", "扫码登录", "登录即可享受")):
            return {"status": "needs_login", "error_code": "login_required", "message": "需要登录后才能读取公开内容"}
        return {"status": "no_data", "error_code": "", "message": "本轮未发现匹配的公开内容"}

    async def _search_weibo(self, page, keyword: str, limit: int) -> list[dict]:
        """Weibo public search.

        Weibo frequently changes markup and may require login or verification.
        This parser only returns visible public evidence and never fabricates
        account metrics.
        """
        from urllib.parse import quote

        await page.goto(f"https://s.weibo.com/weibo?q={quote(keyword)}", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        visible_state = await self._detect_visible_state(page)
        if visible_state.get("status") in {"needs_login", "restricted"}:
            self._set_search_diagnostics(**visible_state)
            return []

        cards = await page.query_selector_all(".card-wrap, div[action-type='feed_list_item']")
        if not cards:
            cards = await page.query_selector_all("div[class*='card']")
        results = []
        seen_urls: set[str] = set()
        for item in cards[: limit * 2]:
            try:
                text = (await item.inner_text()).strip()
                if not text or len(text) < 8:
                    continue
                link = await item.query_selector("a[href*='weibo.com/']")
                href = await link.get_attribute("href") if link else ""
                if href.startswith("//"):
                    href = f"https:{href}"
                elif href.startswith("/"):
                    href = f"https://weibo.com{href}"
                href = href.split("?")[0] if href else ""
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                author = ""
                author_el = await item.query_selector(".name, a.name, [nick-name], a[action-type='feed_list_item']")
                if author_el:
                    author = (await author_el.inner_text()).strip()[:80]

                like_count = 0
                comment_count = 0
                share_count = 0
                numbers = re.findall(r"(转发|评论|赞)\s*([0-9万\.]+)", text)
                for label, value in numbers:
                    normalized = _parse_social_number(value)
                    if label == "转发":
                        share_count = normalized
                    elif label == "评论":
                        comment_count = normalized
                    elif label == "赞":
                        like_count = normalized

                results.append(_normalize_search_result({
                    "video_id": href or f"weibo_{len(results)}",
                    "title": text[:200],
                    "description": text[:500],
                    "author": author,
                    "url": href or f"https://s.weibo.com/weibo?q={quote(keyword)}",
                    "likes": like_count,
                    "comments_count": comment_count,
                    "shares": share_count,
                }, "weibo"))
                if len(results) >= limit:
                    break
            except Exception:
                continue
        return results

    async def get_comments(self, video_url: str, limit: int = 30) -> list[dict]:
        """获取视频评论，优先结构化响应，浏览器 DOM 作为兜底。"""
        if self.platform == "douyin":
            aweme_id = self._extract_platform_video_id(video_url, "douyin")
            if aweme_id:
                try:
                    from .mediacrawler_bridge import get_mediacrawler_bridge
                    bridge = get_mediacrawler_bridge()
                    if bridge.available:
                        raw = await bridge.get_douyin_comments(aweme_id, limit)
                        normalized = self._normalize_douyin_api_comments(raw, limit)
                        if normalized:
                            return normalized
                except Exception as exc:
                    logger.info("Douyin structured comment read unavailable: %s", exc)

        page = await self._ensure_browser()
        comments: list[dict] = []
        api_comments: list[dict] = []

        async def _on_response(response):
            url = str(response.url).lower()
            relevant = (
                self.platform == "douyin" and "/comment/list" in url
            ) or (
                self.platform == "kuaishou" and "/photo/comment/list" in url
            )
            if not relevant:
                return
            try:
                payload = await response.json()
                if self.platform == "douyin":
                    api_comments.extend(self._normalize_douyin_api_comments(payload.get("comments") or [], limit))
                else:
                    api_comments.extend(self._normalize_kuaishou_api_comments(payload, limit))
            except Exception:
                return

        try:
            page.on("response", _on_response)
            await page.goto(video_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            if api_comments:
                unique = {item["comment_id"] or f"{item['author']}:{item['text']}": item for item in api_comments}
                return list(unique.values())[:limit]

            if self.platform == "douyin":
                comments = await self._get_comments_douyin(page, limit)
            elif self.platform == "xhs":
                comments = await self._get_comments_xhs(page, limit)
            elif self.platform == "kuaishou":
                comments = await self._get_comments_kuaishou(page, limit)
        except Exception as e:
            logger.error(f"{self.platform} get_comments error: {e}")
        finally:
            page.remove_listener("response", _on_response)
            await self._close_browser()

        return comments

    @staticmethod
    def _normalize_douyin_api_comments(raw_comments, limit: int = 30) -> list[dict]:
        rows: list[dict] = []
        for item in list(raw_comments or [])[:limit]:
            user = item.get("user") or {}
            rows.append(_normalize_comment({
                "comment_id": item.get("cid") or item.get("comment_id") or "",
                "author": user.get("nickname") or item.get("nickname") or "",
                "author_id": user.get("uid") or user.get("sec_uid") or item.get("uid") or "",
                "text": item.get("text") or item.get("content") or "",
                "likes": item.get("digg_count") or item.get("like_count") or 0,
                "reply_count": item.get("reply_comment_total") or item.get("reply_count") or 0,
                "created_at": item.get("create_time") or "",
                "ip_location": item.get("ip_label") or "",
            }, "douyin"))
        return [row for row in rows if row.get("text")]

    @staticmethod
    def _normalize_kuaishou_api_comments(payload: dict, limit: int = 30) -> list[dict]:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        raw = (data or {}).get("rootCommentsV2") or (data or {}).get("comments") or []
        rows: list[dict] = []
        for item in raw[:limit]:
            rows.append(_normalize_comment({
                "comment_id": item.get("comment_id") or item.get("commentId") or "",
                "author": item.get("author_name") or item.get("authorName") or "",
                "author_id": item.get("author_id") or item.get("authorId") or "",
                "text": item.get("content") or item.get("text") or "",
                "likes": item.get("like_count") or item.get("likeCount") or 0,
                "reply_count": item.get("commentCount") or item.get("subCommentCount") or 0,
                "created_at": item.get("timestamp") or "",
            }, "kuaishou"))
        return [row for row in rows if row.get("text")]

    @staticmethod
    def _extract_platform_video_id(video_url: str, platform: str) -> str:
        patterns = {
            "douyin": r"/video/(\d+)",
            "kuaishou": r"/short-video/([a-zA-Z0-9]+)",
        }
        match = re.search(patterns.get(platform, r"$^"), str(video_url or ""))
        return match.group(1) if match else ""

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

            blocker = await self._detect_visible_state(page)
            if blocker.get("status") in {"needs_login", "restricted"}:
                return {
                    "success": False,
                    "status": "needs_human",
                    "error_code": blocker.get("error_code", ""),
                    "error": blocker.get("message", "需要人工处理平台页面"),
                }

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
        return await self._submit_comment_with_evidence(
            page,
            comment_text,
            '[data-e2e="comment-input"] textarea, [data-e2e="comment-input"] input, '
            '.comment-input textarea, textarea[placeholder*="评论"]',
            '[data-e2e="comment-post"] button, .comment-input button[type="submit"], '
            'button:has-text("发送")',
        )

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
        return await self._submit_comment_with_evidence(
            page,
            comment_text,
            '.comment-input textarea, textarea[placeholder*="评论"], '
            '[contenteditable="true"][data-placeholder*="评论"]',
            '.comment-input .submit, button:has-text("发送"), button:has-text("评论")',
        )

    async def _submit_comment_with_evidence(
        self,
        page,
        comment_text: str,
        input_selector: str,
        button_selector: str,
    ) -> dict:
        """Submit once and only report success when the page provides evidence."""
        response_evidence: dict = {}

        async def _on_response(response):
            url = str(response.url).lower()
            if not any(token in url for token in (
                "comment/publish", "comment/add", "comment/create", "reply/add", "reply/publish",
            )):
                return
            try:
                payload = await response.json()
            except Exception:
                return
            if self._response_indicates_comment_success(payload):
                response_evidence.update({"type": "platform_response", "url": response.url})

        page.on("response", _on_response)
        try:
            comment_input = await page.wait_for_selector(input_selector, timeout=8000)
            await comment_input.fill(comment_text)
            await page.wait_for_timeout(500)

            send_btn = await page.query_selector(button_selector)
            if not send_btn:
                return {"success": False, "error_code": "send_control_missing", "error": "未找到评论发送按钮"}
            await send_btn.click()

            for _ in range(8):
                await page.wait_for_timeout(500)
                if response_evidence:
                    return {
                        "success": True,
                        "message": "评论已发送",
                        "source_url": page.url,
                        "evidence": response_evidence,
                    }
                if await self._has_visible_send_success(page, comment_text):
                    return {
                        "success": True,
                        "message": "评论已发送",
                        "source_url": page.url,
                        "evidence": {"type": "visible_confirmation"},
                    }
            return {
                "success": False,
                "error_code": "send_unverified",
                "error": "发送结果未确认，任务未标记为成功",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            page.remove_listener("response", _on_response)

    @staticmethod
    def _response_indicates_comment_success(payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        candidates = [payload]
        if isinstance(payload.get("data"), dict):
            candidates.append(payload["data"])
        return any(
            item.get("success") is True
            or item.get("result") == 1
            or item.get("code") == 0
            or item.get("status_code") == 0
            for item in candidates
        )

    @staticmethod
    async def _has_visible_send_success(page, comment_text: str) -> bool:
        try:
            exact = page.get_by_text(comment_text, exact=True)
            if await exact.count() and await exact.first.is_visible():
                return True
        except Exception:
            pass
        for phrase in ("评论成功", "发送成功", "发表成功"):
            try:
                notice = page.get_by_text(phrase, exact=False)
                if await notice.count() and await notice.first.is_visible():
                    return True
            except Exception:
                continue
        return False

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
    elif platform in ("douyin", "xhs", "kuaishou", "weibo"):
        adapter = PlaywrightAcquisitionAdapter(platform)
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    _adapters[platform] = adapter
    return adapter


def list_acquisition_platforms() -> list[dict]:
    """列出所有支持的采集平台"""
    platforms = ["bilibili", "douyin", "xhs", "kuaishou", "weibo"]
    result = []
    for p in platforms:
        try:
            adapter = get_acquisition_adapter(p)
            result.append(adapter.status())
        except Exception as e:
            result.append({"platform": p, "ready": False, "error": str(e)})
    return result
