"""
Acquisition REST API — 流量引擎 + 客户转化 完整 REST 端点

覆盖页面:
  流量引擎: /intercept, /search, /comments, /monitor, /ab-test
  客户转化: /auto-reply, /leads, /dm
  自动化:   /ab-results
  账号管理: /strategy, /settings
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])

logger = logging.getLogger(__name__)


@router.on_event("startup")
async def start_enabled_listening() -> None:
    """Resume persisted opportunity monitoring without a manual API call."""
    engine = _get_listen()
    targets = await engine.list_targets()
    if any(bool(item.get("enabled", True)) for item in targets):
        await engine.start(300)


@router.on_event("shutdown")
async def stop_enabled_listening() -> None:
    await _get_listen().stop()

# ── Lazy imports ──────────────────────────────────────────────────────

def _get_intercept():
    from szyg.intercept_engine import get_intercept_engine
    return get_intercept_engine()


def _get_listen():
    from szyg.listen_engine import get_listen_engine
    return get_listen_engine()


def _get_convert():
    from szyg.convert_engine import get_convert_engine
    return get_convert_engine()


def _get_queue():
    from szyg.comment_engine import get_comment_queue
    return get_comment_queue()


def _get_limiter():
    from szyg.comment_engine import get_comment_rate_limiter
    return get_comment_rate_limiter()


# ═══════════════════════════════════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════════════════════════════════

class SearchRequest(BaseModel):
    keyword: str
    platforms: list[str] = Field(default_factory=lambda: ["douyin", "xhs", "bilibili", "kuaishou"])
    limit: int = 20
    min_score: int = 40


class InterceptRequest(BaseModel):
    keyword: str
    platforms: list[str] = Field(default_factory=lambda: ["douyin", "xhs"])
    comment_count: int = 5
    strategy: str = "balanced"
    deai: bool = True
    confirmed: bool = False


class BatchCommentRequest(BaseModel):
    platform: str
    comments: list[dict]
    strategy: str = "balanced"
    deai: bool = True
    confirmed: bool = False


class EnqueueCommentRequest(BaseModel):
    platform: str
    account_id: str = ""
    video_id: str = ""
    video_title: str = ""
    video_url: str = ""
    text: str = Field(..., min_length=1)
    strategy: str = "balanced"
    deai: bool = False
    confirmed: bool = False


class EnqueueBatchCommentTarget(BaseModel):
    platform: str
    account_id: str = ""
    video_id: str = ""
    video_title: str = ""
    video_url: str = ""


class EnqueueBatchCommentRequest(BaseModel):
    targets: list[EnqueueBatchCommentTarget] = Field(..., min_length=1, max_length=5)
    text: str = Field(..., min_length=1)
    strategy: str = "balanced"
    deai: bool = False
    confirmed: bool = False


class CommentCampaignPlanRequest(BaseModel):
    objective: str = Field(..., min_length=4, max_length=500)
    platforms: list[str] = Field(default_factory=lambda: ["douyin", "xhs", "bilibili", "kuaishou"])
    max_targets: int = Field(default=5, ge=1, le=8)
    min_score: int = Field(default=35, ge=0, le=100)
    strategy: str = "balanced"


class CommentCampaignItem(BaseModel):
    platform: str
    account_id: str
    video_id: str = ""
    video_title: str = ""
    video_url: str = ""
    comment_text: str = Field(..., min_length=1, max_length=300)


class CommentCampaignExecuteRequest(BaseModel):
    items: list[CommentCampaignItem] = Field(..., min_length=1, max_length=8)
    strategy: str = "balanced"
    confirmed: bool = False
    monitor_replies: bool = True


class GenerateCommentRequest(BaseModel):
    video_title: str
    video_description: str = ""
    count: int = 3
    strategy: str = "balanced"
    shared_across_targets: bool = False


class DeAIRequest(BaseModel):
    text: str
    platform: str = "douyin"


class PreflightRequest(BaseModel):
    text: str


class MonitorTargetRequest(BaseModel):
    platform: str
    video_id: str = ""
    video_title: str = ""
    video_url: str = ""
    owner: str = "own"
    poll_interval: int = 300


class ABTestStartRequest(BaseModel):
    strategy_a: str
    strategy_b: str
    platform: str = "douyin"
    video_count: int = 10


class ABTestRecordRequest(BaseModel):
    group: str  # "A" or "B"
    sent: int = 0
    success: int = 0
    likes: int = 0
    replies: int = 0


class AutoReplyRequest(BaseModel):
    platform: str = "douyin"
    comments: list[dict]
    dry_run: bool = False


class GenerateReplyRequest(BaseModel):
    comment_text: str
    author_name: str = ""
    platform: str = "douyin"


class LeadUpdateRequest(BaseModel):
    status: Optional[str] = None
    grade: Optional[str] = None
    notes: Optional[str] = None


class DMRequest(BaseModel):
    platform: str
    user_id: str = ""
    user_name: str = ""
    message: str


class StrategyRequest(BaseModel):
    platform: str
    strategy: str = "balanced"


def _search_platform_statuses(platforms: list[str]) -> list[dict]:
    """Expose collector state so an empty platform never looks like a silent failure."""
    from szyg.integrations.acquisition_adapters import get_acquisition_adapter

    statuses: list[dict] = []
    for platform in platforms:
        try:
            diagnostics = get_acquisition_adapter(platform).search_diagnostics()
        except Exception:
            diagnostics = {}
        statuses.append({
            "platform": platform,
            "status": diagnostics.get("status") or "unknown",
            "error_code": diagnostics.get("error_code") or "",
            "message": diagnostics.get("message") or "",
        })
    return statuses


# ═══════════════════════════════════════════════════════════════════════
# 📈 流量引擎 — 视频搜索
# ═══════════════════════════════════════════════════════════════════════

@router.post("/search")
async def search_videos(req: SearchRequest):
    """多平台视频搜索 + 质量评分"""
    engine = _get_intercept()
    results = await engine.search(req.keyword, req.platforms, req.limit)
    all_videos = []
    for sr in results:
        for v in sr.videos:
            all_videos.append({
                "video_id": v.video_id,
                "platform": v.platform,
                "title": v.title,
                "description": v.description[:200] if v.description else "",
                "author": v.author,
                "author_followers": v.author_followers,
                "url": v.url,
                "cover": v.cover,
                "plays": v.plays,
                "likes": v.likes,
                "comments_count": v.comments_count,
                "shares": v.shares,
                "published_at": v.published_at,
                "quality_score": v.quality_score,
                "score_detail": v.score_detail,
            })
    return {
        "keyword": req.keyword,
        "total": len(all_videos),
        "videos": all_videos,
        "platforms": _search_platform_statuses(req.platforms),
    }


@router.post("/search/aggregate")
async def search_aggregated(req: SearchRequest):
    """搜索并按质量评分排序的聚合结果"""
    engine = _get_intercept()
    targets = await engine.find_targets(req.keyword, req.platforms, req.min_score, req.limit)
    return {
        "keyword": req.keyword,
        "total": len(targets),
        "platforms": _search_platform_statuses(req.platforms),
        "targets": [
            {
                "video_id": t.video_id, "platform": t.platform,
                "title": t.title, "author": t.author,
                "plays": t.plays, "likes": t.likes,
                "comments_count": t.comments_count,
                "quality_score": t.quality_score,
                "score_detail": t.score_detail,
                "url": t.url,
            }
            for t in targets
        ]
    }


# ═══════════════════════════════════════════════════════════════════════
# 📈 流量引擎 — 智能截流
# ═══════════════════════════════════════════════════════════════════════

@router.post("/intercept")
async def run_intercept(req: InterceptRequest):
    """一键截流流水线: 搜索→筛选→生成→发送"""
    if not req.confirmed:
        raise HTTPException(status_code=400, detail="发送评论前需要人工确认")
    engine = _get_intercept()
    result = await engine.run_pipeline(
        keyword=req.keyword,
        platforms=req.platforms,
        comment_count=req.comment_count,
        strategy=req.strategy,
        deai=req.deai,
        confirmed=req.confirmed,
    )
    return result


@router.post("/intercept/find-targets")
async def find_targets(req: SearchRequest):
    """只搜索目标，不发送 (预览模式)"""
    engine = _get_intercept()
    targets = await engine.find_targets(req.keyword, req.platforms, req.min_score, req.limit)
    return {
        "keyword": req.keyword,
        "total": len(targets),
        "platforms": _search_platform_statuses(req.platforms),
        "targets": [
            {
                "video_id": t.video_id, "platform": t.platform,
                "title": t.title, "description": t.description,
                "author": t.author, "author_followers": t.author_followers,
                "quality_score": t.quality_score,
                "score_detail": t.score_detail,
                "url": t.url, "cover": t.cover,
                "plays": t.plays, "likes": t.likes,
                "comments_count": t.comments_count, "shares": t.shares,
            }
            for t in targets
        ]
    }


@router.get("/intercept/history")
async def intercept_history():
    """截流历史统计"""
    engine = _get_intercept()
    return await engine.stats()


# ═══════════════════════════════════════════════════════════════════════
# 📈 流量引擎 — 评论管理
# ═══════════════════════════════════════════════════════════════════════

@router.post("/comments/generate")
async def generate_comments(req: GenerateCommentRequest):
    """AI 生成评论"""
    from szyg.comment_engine import generate_comments_with_llm
    comments = await generate_comments_with_llm(
        req.video_title, req.video_description, req.count, req.strategy, req.shared_across_targets
    )
    return {"comments": comments, "count": len(comments)}


async def _campaign_brief(objective: str, platforms: list[str]) -> dict:
    """Turn a business objective into a focused public-content search brief."""
    from szyg.integrations.volcengine_client import VolcEngineClient

    profile_text = ""
    try:
        from szyg.competitor_intelligence import list_business_profiles

        profiles = list_business_profiles()
        profile = profiles[0] if profiles else {}
        profile_text = json.dumps({
            "business": profile.get("product_name") or profile.get("business_name") or "",
            "description": profile.get("description") or profile.get("business_description") or "",
            "customers": profile.get("target_customers") or [],
            "products": profile.get("products") or [],
        }, ensure_ascii=False)
    except Exception:
        profile_text = ""

    prompt = f"""你是公开评论获客任务的规划Agent。把业务目标转换成适合在公开视频平台搜索的短查询。

业务目标：{objective}
企业资料：{profile_text or '未配置'}
可选平台：{', '.join(platforms)}

要求：
- search_query 使用客户会讨论的痛点、需求或场景词，不要只写企业品牌名
- audience 用一句话说明目标客户
- engagement_angle 说明评论应该从什么自然讨论角度切入，禁止硬广、联系方式和虚假体验
- 只返回 JSON 对象

格式：{{"search_query":"...","audience":"...","engagement_angle":"..."}}"""
    try:
        response = await VolcEngineClient(timeout=60).responses_text(
            [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            model="doubao-seed-2-0-lite-260428",
            max_output_tokens=500,
            reasoning_effort="minimal",
        )
        raw = str((response.get("message") or {}).get("content") or "").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        match = __import__("re").search(r"\{[\s\S]*\}", raw)
        payload = json.loads(match.group(0) if match else raw)
        search_query = str(payload.get("search_query") or "").strip()
        if not search_query:
            raise ValueError("search_query missing")
        return {
            "search_query": search_query[:120],
            "audience": str(payload.get("audience") or objective).strip()[:200],
            "engagement_angle": str(payload.get("engagement_angle") or "围绕真实需求自然交流").strip()[:240],
            "source": "agent",
        }
    except Exception as exc:
        logger.warning("Campaign brief planning failed: %s", exc)
        return {
            "search_query": objective[:120],
            "audience": objective[:200],
            "engagement_angle": "围绕目标客户的真实问题自然交流",
            "source": "objective_fallback",
            "warning": "本轮使用原始业务目标搜索",
        }


def _comment_account(platform: str) -> dict:
    from szyg.channel_accounts import get_default_account_for_platform

    account = get_default_account_for_platform(platform) or {}
    session = account.get("session") if isinstance(account.get("session"), dict) else {}
    ready = bool(session.get("valid")) and str(account.get("status") or "") == "connected"
    return {
        "id": str(account.get("id") or ""),
        "label": str(account.get("nickname") or account.get("label") or "未配置账号"),
        "platform": platform,
        "ready": ready,
        "status": "ready" if ready else "needs_login",
    }


@router.post("/comment-campaigns/plan")
async def plan_comment_campaign(req: CommentCampaignPlanRequest):
    """Agent discovers public content and prepares one grounded comment per target."""
    from szyg.comment_engine import DeAIProcessor, generate_comments_with_llm, preflight_check

    supported = [item for item in dict.fromkeys(req.platforms) if item in {"douyin", "xhs", "bilibili", "kuaishou"}]
    if not supported:
        raise HTTPException(status_code=400, detail="请选择支持公开评论获客的平台")

    brief = await _campaign_brief(req.objective.strip(), supported)
    engine = _get_intercept()
    targets = await engine.find_targets(
        brief["search_query"],
        supported,
        min_score=req.min_score,
        limit=req.max_targets,
    )
    account_map = {platform: _comment_account(platform) for platform in supported}

    async def prepare(target):
        account = account_map[target.platform]
        description = "\n".join(filter(None, [
            target.description,
            f"目标客户：{brief['audience']}",
            f"交流角度：{brief['engagement_angle']}",
        ]))
        try:
            generated = await generate_comments_with_llm(
                target.title,
                description,
                count=1,
                strategy=req.strategy,
                shared_across_targets=False,
            )
            comment = DeAIProcessor.process(generated[0], target.platform)
            check = preflight_check(comment)
            generation_error = ""
        except Exception as exc:
            comment = ""
            check = {"pass": False, "decision": "needs_human", "risk_level": "unknown"}
            generation_error = str(exc)[:200]
        return {
            "platform": target.platform,
            "account_id": account["id"],
            "account_label": account["label"],
            "account_ready": account["ready"],
            "video_id": target.video_id,
            "video_title": target.title,
            "video_description": target.description,
            "video_url": target.url,
            "author": target.author,
            "cover": target.cover,
            "plays": target.plays,
            "likes": target.likes,
            "comments_count": target.comments_count,
            "quality_score": target.quality_score,
            "score_detail": target.score_detail,
            "comment_text": comment,
            "preflight": check,
            "generation_error": generation_error,
        }

    semaphore = asyncio.Semaphore(3)

    async def limited_prepare(target):
        async with semaphore:
            return await prepare(target)

    items = await asyncio.gather(*(limited_prepare(target) for target in targets))
    return {
        "plan_id": f"comment_plan_{uuid.uuid4().hex[:10]}",
        "objective": req.objective,
        "brief": brief,
        "platforms": _search_platform_statuses(supported),
        "accounts": list(account_map.values()),
        "items": items,
        "total": len(items),
        "ready_to_send": len([
            item for item in items
            if item["account_ready"] and item["comment_text"] and item["preflight"].get("decision") not in {"needs_human", "skip"}
        ]),
    }


@router.post("/comment-campaigns/execute")
async def execute_comment_campaign(req: CommentCampaignExecuteRequest):
    """Queue individually tailored comments after one explicit batch confirmation."""
    if not req.confirmed:
        raise HTTPException(status_code=400, detail="批量评论前需要人工确认")

    from szyg.channel_accounts import get_account
    from szyg.comment_engine import enqueue_confirmed_comment, preflight_check

    for item in req.items:
        account = get_account(item.account_id)
        session = (account or {}).get("session") if isinstance((account or {}).get("session"), dict) else {}
        if not account or account.get("platform") != item.platform:
            raise HTTPException(status_code=400, detail=f"{item.platform} 未选择有效经营账号")
        if not session.get("valid") or account.get("status") != "connected":
            raise HTTPException(status_code=400, detail=f"账号“{account.get('label') or item.account_id}”需要重新登录")
        check = preflight_check(item.comment_text)
        if check.get("decision") in {"needs_human", "skip"} or check.get("risk_level") == "high":
            raise HTTPException(status_code=400, detail=f"《{item.video_title[:30]}》的评论需要修改后再发送")

    batch_id = f"comment_campaign_{uuid.uuid4().hex[:10]}"
    queued = []

    for index, item in enumerate(req.items):
        queued_item = await enqueue_confirmed_comment(
            item.platform,
            {
                "account_id": item.account_id,
                "video_id": item.video_id,
                "video_title": item.video_title,
                "video_url": item.video_url,
                "text": item.comment_text,
                "batch_id": batch_id,
                "monitor_replies": req.monitor_replies,
            },
            strategy=req.strategy,
            deai=False,
            delay_seconds=index * 45,
        )
        queued.append({
            **queued_item,
            "platform": item.platform,
            "video_title": item.video_title,
            "account_id": item.account_id,
        })

    return {
        "ok": True,
        "batch_id": batch_id,
        "items": queued,
        "monitoring_enabled": req.monitor_replies,
        "monitoring_state": "starts_after_verified_send" if req.monitor_replies else "disabled",
    }


@router.post("/comments/deai")
async def deai_process(req: DeAIRequest):
    """DeAI 去AI味处理"""
    from szyg.comment_engine import DeAIProcessor
    result = DeAIProcessor.process(req.text, req.platform)
    return {"original": req.text, "processed": result}


@router.post("/comments/preflight")
async def preflight(req: PreflightRequest):
    """评论发前检查"""
    from szyg.comment_engine import preflight_check
    result = preflight_check(req.text)
    return result


@router.post("/comments/batch-send")
async def batch_send(req: BatchCommentRequest):
    """批量发送评论"""
    if not req.confirmed:
        raise HTTPException(status_code=400, detail="发送评论前需要人工确认")
    from szyg.comment_engine import batch_send
    comments = [{**item, "human_confirmed": True} for item in req.comments]
    results = await batch_send(req.platform, comments, req.strategy, req.deai)
    counts = {}
    for item in results:
        status = item.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "total": len(results),
        "sent": counts.get("sent", 0),
        "failed": counts.get("failed", 0),
        "skipped": counts.get("skipped", 0),
        "delayed": counts.get("delayed", 0),
        "retrying": counts.get("retrying", 0),
        "needs_human": counts.get("needs_human", 0),
        "auto_repaired": len([r for r in results if r.get("decision") == "auto_repair_then_send"]),
        "results": results,
    }


@router.post("/comments/enqueue")
async def enqueue_comment(req: EnqueueCommentRequest):
    """Persist one explicitly confirmed comment and execute it asynchronously."""
    if not req.confirmed:
        raise HTTPException(status_code=400, detail="发送评论前需要人工确认")
    from szyg.comment_engine import enqueue_confirmed_comment

    try:
        result = await enqueue_confirmed_comment(
            req.platform,
            {
                "account_id": req.account_id,
                "video_id": req.video_id,
                "video_title": req.video_title,
                "video_url": req.video_url,
                "text": req.text,
            },
            strategy=req.strategy,
            deai=req.deai,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "item": result}


@router.post("/comments/enqueue-batch")
async def enqueue_comment_batch(req: EnqueueBatchCommentRequest):
    """Queue one confirmed comment for multiple targets with staggered execution."""
    if not req.confirmed:
        raise HTTPException(status_code=400, detail="群发评论前需要人工确认")
    from szyg.comment_engine import enqueue_confirmed_comment

    batch_id = f"comment_batch_{uuid.uuid4().hex[:10]}"
    items = []
    for index, target in enumerate(req.targets):
        try:
            item = await enqueue_confirmed_comment(
                target.platform,
                {
                    "account_id": target.account_id,
                    "video_id": target.video_id,
                    "video_title": target.video_title,
                    "video_url": target.video_url,
                    "text": req.text,
                    "batch_id": batch_id,
                },
                strategy=req.strategy,
                deai=req.deai,
                delay_seconds=index * 45,
            )
            items.append({**item, "platform": target.platform, "video_title": target.video_title})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "batch_id": batch_id, "items": items}


@router.get("/comments/queue")
async def comment_queue(status: str = "", platform: str = "", archived: bool = False,
                        limit: int = 50, offset: int = 0):
    """评论队列列表"""
    queue = _get_queue()
    if archived:
        items = await queue.list_archived(status, platform, limit, offset)
        payload = []
        for item in items:
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            payload.append({
                **item,
                "batch_id": str(item.get("batch_id") or metadata.get("batch_id") or ""),
                "target_url": str(item.get("video_url") or item.get("target_url") or ""),
                "archived": True,
            })
        return {
            "items": payload,
            "total": len(items),
            "archive": queue.archive_stats(),
        }
    items = await queue.list(status, platform, limit, offset)
    payload = []
    for item in items:
        row = dict(item.__dict__)
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        row["batch_id"] = str(metadata.get("batch_id") or "")
        row["target_url"] = str(row.get("video_url") or "")
        payload.append(row)
    return {"items": payload, "total": len(items)}


@router.get("/comments/stats")
async def comment_stats():
    """评论队列统计"""
    queue = _get_queue()
    stats = await queue.stats()
    limiter = _get_limiter()
    rate_status = await limiter.status()
    return {
        "queue": stats.__dict__,
        "rate_limits": rate_status,
        "archive": queue.archive_stats(),
    }


@router.post("/comments/process-due")
async def process_due_comments(limit: int = 20):
    """处理已到期的延后/重试评论任务"""
    from szyg.comment_engine import process_due_comments as run_due_comments
    return await run_due_comments(limit=limit)


@router.delete("/comments/queue/{item_id}")
async def delete_comment(item_id: str):
    queue = _get_queue()
    await queue.delete(item_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# 📈 流量引擎 — 舆情监听
# ═══════════════════════════════════════════════════════════════════════

@router.get("/monitor/targets")
async def list_monitor_targets():
    """监听目标列表"""
    engine = _get_listen()
    targets = await engine.list_targets()
    return {"targets": targets, "total": len(targets)}


@router.post("/monitor/targets")
async def add_monitor_target(req: MonitorTargetRequest):
    """添加监听目标"""
    from szyg.listen_engine import MonitorTarget
    target = MonitorTarget(
        target_id="",
        platform=req.platform,
        video_id=req.video_id,
        video_title=req.video_title,
        video_url=req.video_url,
        owner=req.owner,
        poll_interval=req.poll_interval,
    )
    tid = await _get_listen().add_target(target)
    await _get_listen().start(min(max(req.poll_interval, 60), 3600))
    return {"target_id": tid, "ok": True}


@router.delete("/monitor/targets/{target_id}")
async def remove_monitor_target(target_id: str):
    await _get_listen().remove_target(target_id)
    return {"ok": True}


@router.get("/monitor/targets/{target_id}")
async def get_monitor_target(target_id: str):
    target = await _get_listen().get_target(target_id)
    if not target:
        raise HTTPException(404, "Target not found")
    return target


@router.post("/monitor/start")
async def start_monitor(interval: int = 300):
    await _get_listen().start(interval)
    return {"ok": True, "message": f"Monitor started (interval={interval}s)"}


@router.post("/monitor/stop")
async def stop_monitor():
    await _get_listen().stop()
    return {"ok": True, "message": "Monitor stopped"}


# ═══════════════════════════════════════════════════════════════════════
# 📈 流量引擎 — A/B 测试
# ═══════════════════════════════════════════════════════════════════════

@router.post("/ab-test/start")
async def start_ab_test(req: ABTestStartRequest):
    test = await _get_intercept().start_ab_test(
        req.strategy_a, req.strategy_b, req.platform, req.video_count
    )
    return test.__dict__


@router.post("/ab-test/{test_id}/record")
async def record_ab_result(test_id: str, req: ABTestRecordRequest):
    await _get_intercept().record_ab_result(
        test_id, req.group, req.sent, req.success, req.likes, req.replies
    )
    return {"ok": True}


@router.get("/ab-test/{test_id}")
async def get_ab_test(test_id: str):
    result = await _get_intercept().get_ab_test(test_id)
    if not result:
        raise HTTPException(404, "A/B test not found")
    return result


@router.get("/ab-test")
async def list_ab_tests(status: str = ""):
    tests = await _get_intercept().list_ab_tests(status)
    return {"tests": tests, "total": len(tests)}


@router.post("/ab-test/{test_id}/stop")
async def stop_ab_test(test_id: str):
    """停止 A/B 测试"""
    result = await _get_intercept().get_ab_test(test_id)
    if not result:
        raise HTTPException(404, "A/B test not found")
    if hasattr(result, 'status'):
        result.status = "completed"
    elif isinstance(result, dict):
        result["status"] = "completed"
    return {"ok": True, "test_id": test_id, "status": "completed"}


# ═══════════════════════════════════════════════════════════════════════
# 💬 客户转化 — 自动回复
# ═══════════════════════════════════════════════════════════════════════

@router.post("/auto-reply")
async def auto_reply(req: AutoReplyRequest):
    """批量自动回复评论"""
    engine = _get_convert()
    results = await engine.auto_reply(req.comments, req.platform, req.dry_run)
    sent = len([r for r in results if r.get("sent")])
    return {"total": len(results), "sent": sent, "results": results}


@router.post("/auto-reply/generate")
async def generate_single_reply(req: GenerateReplyRequest):
    """生成单条回复文本"""
    engine = _get_convert()
    score = engine.score_lead(req.comment_text, req.author_name)
    reply = engine.generate_reply(req.comment_text, req.author_name, req.platform)
    return {
        "reply": reply,
        "lead_score": score.total,
        "grade": score.grade,
        "score_detail": {
            "intent": score.intent_score,
            "engagement": score.engagement_score,
            "urgency": score.urgency_score,
            "value": score.value_score,
        },
    }


@router.post("/auto-reply/score")
async def score_comment(req: GenerateReplyRequest):
    """评论线索评分"""
    engine = _get_convert()
    score = engine.score_lead(req.comment_text, req.author_name)
    return score.__dict__


# ═══════════════════════════════════════════════════════════════════════
# 💬 客户转化 — 线索管理
# ═══════════════════════════════════════════════════════════════════════

@router.get("/leads")
async def list_leads(status: str = "", grade: str = "",
                     platform: str = "", limit: int = 50):
    """线索列表"""
    leads = await _get_listen().list_leads(status, grade, platform, limit)
    return {"leads": leads, "total": len(leads)}


@router.put("/leads/{lead_id}")
async def update_lead(lead_id: str, req: LeadUpdateRequest):
    """更新线索状态/等级"""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    await _get_listen().update_lead(lead_id, **updates)
    return {"ok": True}


@router.get("/leads/stats")
async def lead_stats():
    """线索统计"""
    return await _get_listen().lead_stats()


@router.get("/leads/funnel")
async def conversion_funnel():
    """转化漏斗"""
    return await _get_convert().get_funnel()


@router.get("/conversions")
async def list_conversions(stage: str = "", platform: str = "", limit: int = 50):
    """转化记录列表"""
    items = await _get_convert().list_conversions(stage, platform, limit)
    return {"conversions": items, "total": len(items)}


# ═══════════════════════════════════════════════════════════════════════
# 💬 客户转化 — 私信跟进
# ═══════════════════════════════════════════════════════════════════════

@router.post("/dm/send")
async def send_dm(req: DMRequest):
    """发送私信"""
    try:
        from szyg.platforms.registry import get_registry
        from szyg.publisher import Platform

        p = Platform(req.platform)
        registry = get_registry()
        if not registry.is_registered(p):
            raise HTTPException(400, f"Platform not registered: {req.platform}")

        adapter = await registry.get(p)
        if not hasattr(adapter, 'send_dm'):
            raise HTTPException(400, f"Platform {req.platform} does not support DM")

        result = await adapter.send_dm(
            user_id=req.user_id,
            user_name=req.user_name,
            message=req.message,
        )
        return {"ok": True, "result": result}
    except ValueError:
        raise HTTPException(400, f"Unknown platform: {req.platform}")


# ═══════════════════════════════════════════════════════════════════════
# 🔐 账号管理 — 行为策略
# ═══════════════════════════════════════════════════════════════════════

@router.get("/strategy")
async def get_strategy(platform: str = "douyin"):
    """获取当前行为策略配置"""
    from szyg.platforms.anti_detect import BehaviorStrategy, STRATEGY_CONFIG
    strategies = {}
    for st in BehaviorStrategy:
        cfg = STRATEGY_CONFIG[st]
        strategies[st.value] = {
            "type_delay": cfg["type_delay"],
            "click_delay": cfg["click_delay"],
            "scroll_delay": cfg["scroll_delay"],
            "think_pause": cfg["think_pause"],
            "between_actions": cfg["between_actions"],
            "typo_rate": cfg["typo_rate"],
            "hourly_limit": cfg["hourly_limit"],
            "daily_limit": cfg["daily_limit"],
            "mouse_natural": str(cfg["mouse_params"]),
        }
    return {"platform": platform, "strategies": strategies}


@router.post("/strategy/apply")
async def apply_strategy(req: StrategyRequest):
    """应用行为策略到平台的频率限制"""
    limiter = _get_limiter()
    limiter.apply_strategy(req.strategy)
    remaining = await limiter.remaining(req.platform)
    return {
        "ok": True,
        "platform": req.platform,
        "strategy": req.strategy,
        "limits": remaining,
    }


# ═══════════════════════════════════════════════════════════════════════
# 🔐 账号管理 — 系统配置
# ═══════════════════════════════════════════════════════════════════════

@router.get("/settings")
async def get_settings():
    """获取完整系统配置 (脱敏)"""
    try:
        from szyg.config.loader import load_config
        cfg = load_config()
        # Mask API keys
        masked = _mask_config(cfg)
        return masked
    except Exception as e:
        raise HTTPException(500, str(e))


def _mask_config(cfg: dict, depth: int = 0) -> dict:
    """递归脱敏配置中的 API key"""
    result = {}
    for k, v in cfg.items():
        if isinstance(v, dict):
            result[k] = _mask_config(v, depth + 1)
        elif isinstance(v, str) and ("key" in k.lower() or "secret" in k.lower() or "token" in k.lower()):
            if len(v) > 8:
                result[k] = v[:4] + "****" + v[-4:]
            else:
                result[k] = "****"
        else:
            result[k] = v
    return result


# ═══════════════════════════════════════════════════════════════════════
# 附加 — 视频剪辑 REST API
# ═══════════════════════════════════════════════════════════════════════

_video_router = APIRouter(prefix="/api/video-edit", tags=["video-edit"])


class VideoCutRequest(BaseModel):
    file_path: str
    start: float
    duration: float


class VideoConcatRequest(BaseModel):
    files: list[str]


class VideoSpeedRequest(BaseModel):
    file_path: str
    speed: float


class VideoTitleRequest(BaseModel):
    file_path: str
    text: str
    font_size: int = 48
    font_color: str = "white"


class VideoAudioRequest(BaseModel):
    video_path: str
    audio_path: str


class VideoMixAudioRequest(BaseModel):
    video_path: str
    bgm_path: str
    video_volume: float = 0.3
    bgm_volume: float = 1.0


class VideoFrameRequest(BaseModel):
    file_path: str
    time_sec: float
    width: int = 0
    height: int = 0


@_video_router.get("/templates")
async def video_templates():
    from szyg.video_cut_engine import list_templates
    templates = list_templates()
    return {"templates": templates, "count": len(templates)}


@_video_router.get("/fonts")
async def video_fonts():
    from szyg.video_cut_engine import list_fonts
    fonts = list_fonts()
    return {"fonts": fonts, "count": len(fonts)}


@_video_router.post("/info")
async def video_info(file_path: str = Query(...)):
    from szyg.video_cut_engine import get_video_info
    try:
        return get_video_info(file_path)
    except Exception as e:
        raise HTTPException(500, str(e))


@_video_router.post("/cut")
async def video_cut(req: VideoCutRequest):
    from szyg.video_cut_engine import cut_video
    import tempfile
    output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = cut_video(req.file_path, req.start, req.duration, output)
        return {"output": result, "start": req.start, "duration": req.duration}
    except Exception as e:
        raise HTTPException(500, str(e))


@_video_router.post("/concat")
async def video_concat(req: VideoConcatRequest):
    from szyg.video_cut_engine import concat_videos
    import tempfile
    output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = concat_videos(req.files, output)
        return {"output": result, "segments": len(req.files)}
    except Exception as e:
        raise HTTPException(500, str(e))


@_video_router.post("/speed")
async def video_speed(req: VideoSpeedRequest):
    from szyg.video_cut_engine import change_speed
    import tempfile
    output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = change_speed(req.file_path, req.speed, output)
        return {"output": result, "speed": req.speed}
    except Exception as e:
        raise HTTPException(500, str(e))


@_video_router.post("/title")
async def video_add_title(req: VideoTitleRequest):
    from szyg.video_cut_engine import add_text_overlay
    import tempfile
    output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = add_text_overlay(req.file_path, output, req.text,
                                   font_size=req.font_size, font_color=req.font_color)
        return {"output": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@_video_router.post("/replace-audio")
async def video_replace_audio(req: VideoAudioRequest):
    from szyg.video_cut_engine import replace_audio
    import tempfile
    output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = replace_audio(req.video_path, req.audio_path, output)
        return {"output": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@_video_router.post("/mix-audio")
async def video_mix_audio(req: VideoMixAudioRequest):
    from szyg.video_cut_engine import mix_audio
    import tempfile
    output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = mix_audio(req.video_path, req.bgm_path, output,
                            video_vol=req.video_volume, audio_vol=req.bgm_volume)
        return {"output": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@_video_router.post("/extract-frame")
async def video_extract_frame(req: VideoFrameRequest):
    from szyg.video_cut_engine import extract_frame
    import tempfile
    output = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    try:
        result = extract_frame(req.file_path, req.time_sec, output, req.width, req.height)
        return {"output": result, "time": req.time_sec}
    except Exception as e:
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════════════
# 附加 — 线索跟进 / 客户管理 / 消息记录
# ═══════════════════════════════════════════════════════════════════════

import json as _json
from pathlib import Path as _Path
from szyg.data_path import DATA_DIR as _DATA_DIR

_CUSTOMERS_FILE = _DATA_DIR / "customers.json"
_MESSAGES_FILE = _DATA_DIR / "messages.json"
_SOP_EXEC_FILE = _DATA_DIR / "sop_executions.json"


def _load_json_safe(path: _Path) -> list:
    if path.exists():
        return _json.loads(path.read_text(encoding="utf-8"))
    return []


def _save_json_safe(path: _Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/leads/{lead_id}/follow")
async def follow_lead(lead_id: str):
    """记录线索跟进"""
    return {"ok": True, "lead_id": lead_id, "followed_at": __import__("datetime").datetime.now().isoformat()}


@router.get("/customers")
async def list_customers(search: str = "", limit: int = 50):
    """客户列表"""
    items = _load_json_safe(_CUSTOMERS_FILE)
    if search:
        q = search.lower()
        items = [c for c in items if q in c.get("name", "").lower() or q in c.get("lastMessage", "").lower()]
    return {"customers": items[:limit], "total": len(items)}


@router.post("/customers")
async def create_customer(body: dict):
    """创建客户"""
    items = _load_json_safe(_CUSTOMERS_FILE)
    import uuid
    item = {"id": str(uuid.uuid4())[:8], **body, "created_at": __import__("datetime").datetime.now().isoformat()}
    items.append(item)
    _save_json_safe(_CUSTOMERS_FILE, items)
    return item


@router.get("/messages")
async def list_messages(customer_id: str = ""):
    """消息记录列表"""
    items = _load_json_safe(_MESSAGES_FILE)
    if customer_id:
        items = [m for m in items if m.get("customer_id") == customer_id]
    return {"messages": items, "total": len(items)}


@router.post("/messages/{customer_id}")
async def send_message(customer_id: str, body: dict):
    """发送消息"""
    items = _load_json_safe(_MESSAGES_FILE)
    import uuid
    item = {
        "id": str(uuid.uuid4())[:8],
        "customer_id": customer_id,
        "sender": body.get("sender", "assistant"),
        "text": body.get("text", ""),
        "time": body.get("time", __import__("datetime").datetime.now().strftime("%H:%M")),
    }
    items.append(item)
    _save_json_safe(_MESSAGES_FILE, items)
    return item


# ═══════════════════════════════════════════════════════════════════════
# 附加 — 回复模板管理
# ═══════════════════════════════════════════════════════════════════════

_REPLY_TEMPLATES_FILE = _DATA_DIR / "reply_templates.json"


@router.get("/reply-templates")
async def list_reply_templates():
    """回复模板列表"""
    items = _load_json_safe(_REPLY_TEMPLATES_FILE)
    return {"templates": items, "total": len(items)}


@router.post("/reply-templates")
async def create_reply_template(body: dict):
    """创建回复模板"""
    items = _load_json_safe(_REPLY_TEMPLATES_FILE)
    import uuid
    item = {
        "id": str(uuid.uuid4())[:8],
        "name": body.get("name", ""),
        "keywords": body.get("keywords", []),
        "content": body.get("content", ""),
        "enabled": body.get("enabled", True),
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }
    items.append(item)
    _save_json_safe(_REPLY_TEMPLATES_FILE, items)
    return item


@router.delete("/reply-templates/{template_id}")
async def delete_reply_template(template_id: str):
    """删除回复模板"""
    items = _load_json_safe(_REPLY_TEMPLATES_FILE)
    items = [t for t in items if t.get("id") != template_id]
    _save_json_safe(_REPLY_TEMPLATES_FILE, items)
    return {"ok": True}
