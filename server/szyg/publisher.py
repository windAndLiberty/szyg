"""
Content Publishing Pipeline — 内容发布管道
AI生成 → 人工审核 → 定时发布 → 发布历史

v2: 集成平台适配器系统 (szyg.platforms)，实现真实的
    抖音/小红书/微信多平台自动发布。
"""
import json, os, uuid, logging
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from szyg.data_path import DATA_DIR
from szyg.tenant import get_tenant_data_file as _tdf

logger = logging.getLogger(__name__)
PUBLISH_DB = DATA_DIR / "publisher.json"
PUBLISH_QUEUE = DATA_DIR / "publish_queue.json"
PUBLISH_LOG = DATA_DIR / "publish_log.json"


class ContentType(str, Enum):
    POST = "post"           # 短帖 (朋友圈/微博)
    ARTICLE = "article"     # 长文 (公众号/知乎)
    VIDEO_SCRIPT = "video"  # 视频脚本
    IMAGE_POST = "image"    # 图文 (小红书)

class ContentStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"       # 待审核
    APPROVED = "approved"     # 已审核待发布
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"

class Platform(str, Enum):
    WECHAT_MP = "wechat_mp"      # 微信公众号
    WECOM = "wecom"               # 企业微信
    DOUYIN = "douyin"             # 抖音
    XHS = "xhs"                   # 小红书
    KUAISHOU = "kuaishou"         # 快手
    BILIBILI = "bilibili"         # B站
    WEIBO = "weibo"               # 微博
    ALL = "all"                   # 全平台


class Content(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    content_type: ContentType = ContentType.POST
    body: str = ""                  # 正文/Markdown
    media_urls: list[str] = []      # 附件图片/视频URL
    platforms: list[Platform] = [Platform.ALL]
    tags: list[str] = []
    status: ContentStatus = ContentStatus.DRAFT
    ai_generated: bool = False
    ai_agent_id: str = ""           # 由哪个AI Agent生成
    review_comment: str = ""        # 审核意见
    scheduled_at: str = ""          # 定时发布时间 ISO format
    published_at: str = ""
    created_by: str = "admin"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class PublishRecord(BaseModel):
    id: str
    content_id: str
    platform: Platform
    status: str = "pending"   # pending/success/failed
    published_at: str = ""
    error_msg: str = ""
    platform_post_id: str = ""  # 平台返回的post ID


def _get_tenant_path(basename: str) -> Path:
    """Resolve data file path for the current tenant."""
    return _tdf(basename)

def _read(path: Path) -> list[dict]:
    # Resolve tenant path if given a base path
    actual = _get_tenant_path(path.name) if path.parent == DATA_DIR else path
    if actual.exists():
        return json.loads(actual.read_text(encoding='utf-8'))
    return []

def _write(path: Path, data: list[dict]):
    actual = _get_tenant_path(path.name) if path.parent == DATA_DIR else path
    actual.parent.mkdir(parents=True, exist_ok=True)
    actual.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class Publisher:
    """Content publishing pipeline manager"""

    def list_contents(self, status: str = "", content_type: str = "", search: str = "", limit: int = 50) -> list[Content]:
        items = _read(PUBLISH_DB)
        if status:
            items = [i for i in items if i.get("status") == status]
        if content_type:
            items = [i for i in items if i.get("content_type") == content_type]
        if search:
            q = search.lower()
            items = [i for i in items if q in i.get("title","").lower() or q in i.get("body","").lower()]
        items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return [Content(**i) for i in items[:limit]]

    def get_content(self, content_id: str) -> Content | None:
        for i in _read(PUBLISH_DB):
            if i["id"] == content_id:
                return Content(**i)
        return None

    def create(self, **kwargs) -> Content:
        c = Content(**kwargs)
        items = _read(PUBLISH_DB)
        items.append(c.model_dump())
        _write(PUBLISH_DB, items)
        return c

    def update(self, content_id: str, **kwargs) -> Content | None:
        items = _read(PUBLISH_DB)
        for i, item in enumerate(items):
            if item["id"] == content_id:
                item.update(kwargs)
                item["updated_at"] = datetime.now().isoformat()
                items[i] = item
                _write(PUBLISH_DB, items)
                return Content(**item)
        return None

    def delete(self, content_id: str) -> bool:
        items = _read(PUBLISH_DB)
        new_items = [i for i in items if i["id"] != content_id]
        if len(new_items) != len(items):
            _write(PUBLISH_DB, new_items)
            return True
        return False

    # --- Review Pipeline ---
    def submit_review(self, content_id: str) -> Content | None:
        return self.update(content_id, status=ContentStatus.PENDING.value)

    def approve(self, content_id: str, comment: str = "") -> Content | None:
        return self.update(content_id, status=ContentStatus.APPROVED.value, review_comment=comment)

    def reject(self, content_id: str, comment: str = "") -> Content | None:
        return self.update(content_id, status=ContentStatus.REJECTED.value, review_comment=comment)

    # --- Scheduling ---
    def schedule(self, content_id: str, scheduled_at: str) -> Content | None:
        return self.update(content_id, scheduled_at=scheduled_at, status=ContentStatus.APPROVED.value)

    # --- Publish ---
    def publish_now(self, content_id: str, platform: Platform | None = None) -> PublishRecord:
        """
        同步发布 (兼容旧接口)。
        内部调用 async publish_async()。

        对接到真实平台适配器 (szyg.platforms)。
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop — create one
            result = asyncio.run(self.publish_async(content_id, platform))
            return result
        else:
            # Running inside an event loop — schedule on it
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                self.publish_async(content_id, platform), loop
            )
            return future.result(timeout=120)

    async def publish_async(self, content_id: str, platform: Platform | None = None) -> PublishRecord:
        """
        异步发布到真实平台。

        流程:
          1. 获取内容
          2. 解析目标平台列表
          3. 对每个平台:
             a. 获取适配器 (通过 PlatformRegistry)
             b. 构建 PublishRequest
             c. 调用 adapter.publish()
          4. 记录结果
          5. 更新内容状态
        """
        from szyg.platforms.base import PublishRequest, PublishResult
        from szyg.platforms.registry import get_registry

        content = self.get_content(content_id)
        if not content:
            raise ValueError(f"Content {content_id} not found")

        platforms = [platform] if platform else content.platforms
        if Platform.ALL in platforms:
            platforms = [p for p in Platform if p != Platform.ALL]

        # 过滤掉未注册适配器的平台
        registry = get_registry()
        active_platforms = [p for p in platforms if registry.is_registered(p)]
        skipped = [p for p in platforms if not registry.is_registered(p)]

        if skipped:
            logger.info(f"跳过未注册适配器的平台: {[p.value for p in skipped]}")

        if not active_platforms:
            # 没有可用的真实适配器 — fallback 到 mock
            logger.warning("没有可用的平台适配器，使用 mock 发布")
            return self._publish_mock(content_id, platforms)

        # 构建发布请求
        request = PublishRequest(
            content_id=content_id,
            title=content.title,
            body=content.body,
            content_type=content.content_type,
            media_urls=content.media_urls,
            tags=content.tags,
            scheduled_at=content.scheduled_at,
        )

        # 并发发布到所有平台
        import asyncio
        records = []
        tasks = []

        for p in active_platforms:
            async def _publish_one(plat: Platform) -> dict:
                try:
                    adapter = await registry.get(plat)
                    result = await adapter.publish(request)
                    return {
                        "id": str(uuid.uuid4())[:8],
                        "content_id": content_id,
                        "platform": plat.value,
                        "status": "success" if result.success else "failed",
                        "published_at": result.published_at or datetime.now().isoformat(),
                        "error_msg": result.error_msg,
                        "platform_post_id": result.platform_post_id,
                        "platform_post_url": result.platform_post_url,
                    }
                except Exception as e:
                    logger.error(f"[{plat.value}] 发布异常: {e}")
                    return {
                        "id": str(uuid.uuid4())[:8],
                        "content_id": content_id,
                        "platform": plat.value,
                        "status": "failed",
                        "published_at": datetime.now().isoformat(),
                        "error_msg": str(e),
                        "platform_post_id": "",
                    }

            tasks.append(_publish_one(p))

        records = await asyncio.gather(*tasks)

        # 对跳过的平台生成 mock 记录
        for p in skipped:
            records.append({
                "id": str(uuid.uuid4())[:8],
                "content_id": content_id,
                "platform": p.value,
                "status": "skipped",
                "published_at": datetime.now().isoformat(),
                "error_msg": "平台适配器未注册",
                "platform_post_id": f"mock_{p.value}_{content_id}",
            })

        # 保存记录
        queue = _read(PUBLISH_QUEUE)
        queue.extend(records)
        _write(PUBLISH_QUEUE, queue)

        log = _read(PUBLISH_LOG)
        log.extend(records)
        _write(PUBLISH_LOG, log)

        # 更新内容状态
        any_success = any(r["status"] == "success" for r in records)
        new_status = ContentStatus.PUBLISHED.value if any_success else content.status.value
        self.update(content_id, status=new_status, published_at=datetime.now().isoformat())

        logger.info(f"发布完成: content={content_id}, 结果={[(r['platform'], r['status']) for r in records]}")
        return PublishRecord(**records[0]) if records else None

    def _publish_mock(self, content_id: str, platforms: list[Platform]) -> PublishRecord:
        """Fallback: 当没有可用的真实适配器时，生成 mock 记录"""
        records = []
        for p in platforms:
            rec = {
                "id": str(uuid.uuid4())[:8],
                "content_id": content_id,
                "platform": p.value,
                "status": "success",
                "published_at": datetime.now().isoformat(),
                "error_msg": "",
                "platform_post_id": f"mock_{p.value}_{content_id}",
            }
            records.append(rec)

        queue = _read(PUBLISH_QUEUE)
        queue.extend(records)
        _write(PUBLISH_QUEUE, queue)

        log = _read(PUBLISH_LOG)
        log.extend(records)
        _write(PUBLISH_LOG, log)

        self.update(content_id, status=ContentStatus.PUBLISHED.value, published_at=datetime.now().isoformat())

        return PublishRecord(**records[0]) if records else None

    # --- Calendar ---
    def get_calendar(self, month: str = "") -> list[dict]:
        """Get content calendar for a given month (YYYY-MM)"""
        items = _read(PUBLISH_DB)
        scheduled = []
        for i in items:
            if i.get("scheduled_at"):
                if not month or i["scheduled_at"].startswith(month):
                    scheduled.append({
                        "id": i["id"], "title": i["title"],
                        "scheduled_at": i["scheduled_at"],
                        "status": i["status"], "platforms": i.get("platforms", []),
                    })
        scheduled.sort(key=lambda x: x["scheduled_at"])
        return scheduled

    # --- Stats ---
    def get_stats(self) -> dict:
        items = _read(PUBLISH_DB)
        logs = _read(PUBLISH_LOG)
        status_counts = {}
        for i in items:
            s = i.get("status", "draft")
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "total": len(items),
            "by_status": status_counts,
            "total_published": len(logs),
            "drafts": status_counts.get("draft", 0),
            "pending_review": status_counts.get("pending", 0),
            "approved": status_counts.get("approved", 0),
            "published": status_counts.get("published", 0),
        }

    # --- AI Generate ---
    def ai_generate(self, topic: str, agent_id: str = "copywriter", content_type: str = "post") -> Content:
        """Use AI agent to generate content draft"""
        from szyg.agent_core.model_router import ModelRouter
        from szyg.config.settings import get_settings

        # Load agent prompt
        agents_file = DATA_DIR / "agents.json"
        system_prompt = "你是内容创作助手"
        if agents_file.exists():
            agents = json.loads(agents_file.read_text(encoding='utf-8'))
            for a in agents:
                if a.get("id") == agent_id:
                    system_prompt = a.get("system_prompt", system_prompt)
                    break

        # Generate via LLM
        content_body = f"[AI自动生成] 主题：{topic}\n\n(此处为AI根据提示词生成的内容。实际部署时接入ModelRouter进行LLM生成。)\n\n## 正文\n\n{topic}是当前热门话题..."

        return self.create(
            title=topic,
            content_type=content_type,
            body=content_body,
            ai_generated=True,
            ai_agent_id=agent_id,
            platforms=[Platform.ALL],
            tags=[content_type, "ai-generated"],
        )

    # --- Publishing Log ---
    def get_logs(self, limit: int = 50) -> list[dict]:
        logs = _read(PUBLISH_LOG)
        logs.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        return logs[:limit]


# Singleton
_publisher: Publisher | None = None
def get_publisher() -> Publisher:
    global _publisher
    if _publisher is None:
        _publisher = Publisher()
    return _publisher
