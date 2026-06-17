"""Lead API Routes — 线索管家 REST 接口。

对标: 探迹B2B Agent / 销氪AIsales 线索管理
"""

from fastapi import APIRouter, HTTPException, Query

from szyg.lead_scoring import score_intent
from szyg.lead_store import get_lead_store
from szyg.models.lead import (
    ConversionStage, IntentLevel, IntentScoringRequest,
    LeadProfile, LeadSource,
)

router = APIRouter(prefix="/api/leads", tags=["leads"])


# ── CRUD ─────────────────────────────────────────────────

@router.post("", response_model=LeadProfile)
def create_lead(lead: LeadProfile):
    """手动创建线索。"""
    store = get_lead_store()
    return store.create(lead)


@router.get("/{lead_id}", response_model=LeadProfile)
def get_lead(lead_id: str):
    """获取线索详情。"""
    store = get_lead_store()
    lead = store.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadProfile)
def update_lead(lead_id: str, updates: dict):
    """更新线索（部分更新）。"""
    store = get_lead_store()
    lead = store.update(lead_id, **updates)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.delete("/{lead_id}")
def delete_lead(lead_id: str):
    """删除线索。"""
    store = get_lead_store()
    if not store.delete(lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"ok": True}


# ── 列表 / 搜索 ──────────────────────────────────────────

@router.get("")
def list_leads(
    intent_level: str | None = Query(None, description="high|medium|low|cold"),
    stage: str | None = Query(None),
    platform: str | None = Query(None),
    industry: str | None = Query(None),
    search: str | None = Query(None, description="FTS5 全文搜索"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """线索列表，支持筛选和全文搜索。"""
    store = get_lead_store()
    if search:
        leads = store.search(search, limit)
        return {"total": len(leads), "items": leads}

    leads = store.list_leads(
        intent_level=IntentLevel(intent_level) if intent_level else None,
        stage=ConversionStage(stage) if stage else None,
        platform=LeadSource(platform) if platform else None,
        industry=industry,
        limit=limit,
        offset=offset,
    )
    stats = store.stats()
    return {"total": stats["total"], "items": leads, "stats": stats}


# ── AI 意向评分 ──────────────────────────────────────────

@router.post("/score-intent")
def score_lead_intent(request: IntentScoringRequest):
    """AI 意向评分 — 分析用户互动内容，判断意向等级。

    输入: 平台 + 用户评论/私信内容 + 可选上下文
    输出: 意向分数、等级、信号、建议回复、是否需要跟进
    """
    result = score_intent(request)
    return result


# ── 统计 ─────────────────────────────────────────────────

@router.get("/stats/overview")
def get_stats():
    """线索统计总览。"""
    store = get_lead_store()
    return store.stats()
