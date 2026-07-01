"""
Content Publishing Pipeline — 内容发布管道
AI生成 → 人工审核 → 定时发布 → 发布历史

v2: 集成平台适配器系统 (szyg.platforms)，实现真实的
    抖音/小红书/微信多平台自动发布。
"""
import json, os, uuid, logging, tempfile
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from szyg.data_path import DATA_DIR
from szyg.tenant import get_tenant_data_file as _tdf
from szyg.atomic_file import atomic_read, atomic_write
from szyg.atomic_file import atomic_read_async, atomic_write_async

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
    platform_post_url: str = ""  # 平台返回的post URL


def _get_tenant_path(basename: str) -> Path:
    """Resolve data file path for the current tenant."""
    return _tdf(basename)

def _resolve(path: Path) -> Path:
    """Resolve tenant path if given a base path, ensuring parent dirs exist."""
    actual = _get_tenant_path(path.name) if path.parent == DATA_DIR else path
    actual.parent.mkdir(parents=True, exist_ok=True)
    return actual


def _read(path: Path) -> list[dict]:
    """Sync read with path resolution. Thread-safe via atomic_file."""
    return atomic_read(_resolve(path))


def _write(path: Path, data: list[dict]) -> None:
    """Sync atomic write with path resolution. Thread-safe via atomic_file."""
    atomic_write(_resolve(path), data)


async def _read_async(path: Path) -> list[dict]:
    """Non-blocking read — runs file I/O in thread pool."""
    return await atomic_read_async(_resolve(path))


async def _write_async(path: Path, data: list[dict]) -> None:
    """Non-blocking write — runs file I/O in thread pool."""
    await atomic_write_async(_resolve(path), data)


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
                # ── social-auto-upload 优先 ──
                sau_platform_map = {
                    Platform.DOUYIN: "douyin",
                    Platform.XHS: "xhs",
                    Platform.KUAISHOU: "kuaishou",
                }
                sau_platform = sau_platform_map.get(plat)
                if sau_platform and content.media_urls:
                    try:
                        from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
                        sau = get_sau_adapter()
                        # 判断是视频还是图文
                        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm", ".flv"}
                        first_media = content.media_urls[0]
                        is_video = any(first_media.lower().endswith(ext) for ext in video_exts)

                        if is_video:
                            sau_result = await sau.upload_video(
                                platform=sau_platform,
                                file_path=first_media,
                                title=content.title,
                                desc=content.body,
                                tags=content.tags,
                            )
                        else:
                            sau_result = await sau.upload_note(
                                platform=sau_platform,
                                image_paths=content.media_urls,
                                title=content.title,
                                note=content.body,
                                tags=content.tags,
                            )

                        if sau_result.get("success"):
                            return {
                                "id": str(uuid.uuid4())[:8],
                                "content_id": content_id,
                                "platform": plat.value,
                                "status": "success",
                                "published_at": datetime.now().isoformat(),
                                "error_msg": "",
                                "platform_post_id": f"sau_{plat.value}_{content_id}",
                                "platform_post_url": "",
                                "published_via": "social-auto-upload",
                            }
                        else:
                            logger.info(f"[sau] {plat.value} 发布失败, fallback到原生适配器: {sau_result.get('message')}")
                    except Exception as sau_err:
                        logger.info(f"[sau] {plat.value} 异常, fallback到原生适配器: {sau_err}")

                # ── 原生适配器 fallback ──
                try:
                    adapter = await registry.get(plat)
                    result = await adapter.safe_publish(request)
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

        # 保存记录 (non-blocking)
        queue = await _read_async(PUBLISH_QUEUE)
        queue.extend(records)
        await _write_async(PUBLISH_QUEUE, queue)

        log = await _read_async(PUBLISH_LOG)
        log.extend(records)
        await _write_async(PUBLISH_LOG, log)

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
    async def ai_generate(self, topic: str, agent_id: str = "copywriter",
                          content_type: str = "post") -> Content:
        """使用 AI 智能体生成内容草稿。

        通过 ModelRouter 调用已配置的 LLM (默认 Ollama 本地模型)，
        根据 agent 的 system_prompt 和用户主题生成内容。
        """
        from szyg.agent_core.model_router import ModelRouter

        # 1. 加载智能体 system prompt
        agents_file = DATA_DIR / "agents.json"
        system_prompt = "你是一个专业的内容创作助手，擅长撰写各类文案。"
        if agents_file.exists():
            try:
                agents = json.loads(agents_file.read_text(encoding='utf-8'))
                for a in agents:
                    if a.get("id") == agent_id:
                        system_prompt = a.get("system_prompt", system_prompt)
                        break
            except Exception:
                logger.debug("Failed to load agents.json, using default system prompt", exc_info=True)

        # 2. 根据内容类型调整提示词
        type_guidance = {
            "post": "写一段适合社交媒体的短帖，要求简洁有力、有互动感。",
            "article": "写一篇结构完整的文章，包含引言、正文和总结。",
            "image": "描述一张适合生成图像的视觉画面，偏重场景和氛围。",
            "video": "写一份视频脚本，包含镜头描述和旁白。",
        }
        guidance = type_guidance.get(content_type, type_guidance["post"])

        # 3. 调用 LLM 生成内容
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"主题：{topic}\n\n{guidance}\n\n请直接输出创作内容，不要输出元信息。"},
        ]

        content_body = ""
        try:
            # 优先使用火山引擎 (有配置 + 已验证可用)
            try:
                from szyg.integrations.volcengine_client import VolcEngineClient
                vc = VolcEngineClient()
                resp = await vc.chat(messages=messages, model="doubao-pro-128k", max_tokens=1024)
                content_body = resp.get("message", {}).get("content", "").strip()
                await vc.close()
            except Exception as e:
                logger.debug("VolcEngine primary LLM failed, trying fallback: %s", e)

            # Fallback: ModelRouter (VolcEngine / Ollama)
            if not content_body or len(content_body) < 10:
                try:
                    router = ModelRouter()
                    resp = await router.chat(messages)
                    content_body = resp.content.strip()
                except Exception:
                    logger.debug("ModelRouter fallback also failed", exc_info=True)

            if not content_body or len(content_body) < 10:
                raise ValueError("All LLM backends returned empty content")
        except Exception as e:
            logger.warning(f"AI 生成失败 [agent={agent_id}]: {e}")
            content_body = (
                f"## {topic}\n\n"
                f"*AI 生成暂时不可用（{str(e)[:80]}）。*\n\n"
                f"请确认：\n"
                f"1. 火山引擎 API Key 有效\n"
                f"2. 或 Ollama 已启动且模型已下载：`ollama pull qwen3:0.6B`\n\n"
                f"点击「重试」可再次生成。"
            )

        # 4. 创建内容草稿
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
