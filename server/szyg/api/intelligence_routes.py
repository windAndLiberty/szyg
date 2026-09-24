"""Competitor intelligence API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from szyg.competitor_intelligence import (
    accept_discovery_candidate,
    create_content_brief,
    create_competitor,
    content_brief_prompt,
    collect_market_news,
    create_information_source,
    delete_competitor,
    delete_information_source,
    discover_from_profile,
    latest_report,
    list_business_profiles,
    list_content_briefs,
    list_competitors,
    list_content_items,
    list_discoveries,
    list_information_sources,
    list_market_news,
    overview,
    sync_competitor,
    sync_competitors,
    upsert_business_profile,
    update_information_source,
    visualization_data,
)
from szyg.intelligence_pipeline import (
    get_intelligence_report,
    list_intelligence_reports,
    run_intelligence_query,
)
from szyg.intelligence_collectors import get_intelligence_collector_registry

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


class CompetitorCreateRequest(BaseModel):
    profile_url: str = Field(..., min_length=3)
    platform: str = ""
    name: str = ""
    tags: list[str] = Field(default_factory=list)


class BusinessProfileRequest(BaseModel):
    id: str = "default"
    product_name: str = ""
    industry: str = ""
    audience: str = ""
    region: str = ""
    website: str = ""
    brand_aliases: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["zh-CN"])
    target_questions: list[str] = Field(default_factory=list)
    geo_providers: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    seed_keywords: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=lambda: ["douyin", "xhs", "kuaishou", "bilibili", "weibo"])
    use_knowledge_base: bool = True
    knowledge_query: str = ""
    max_keywords: int = 4
    per_keyword_limit: int = 5


class DiscoveryAcceptRequest(BaseModel):
    candidate_id: str


class ContentBriefRequest(BaseModel):
    angle_index: int = 0
    title: str = ""
    notes: str = ""
    source: str = ""
    source_url: str = ""


class InformationSourceRequest(BaseModel):
    name: str = ""
    url: str = Field(..., min_length=8)
    keywords: list[str] = Field(default_factory=list)
    enabled: bool = True


class InformationSourceUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    keywords: list[str] | None = None
    enabled: bool | None = None


class MarketNewsCollectRequest(BaseModel):
    profile_id: str = "default"
    include_auto_search: bool = True


class IntelligenceQueryRequest(BaseModel):
    query: str = Field(..., min_length=4, max_length=500)
    use_enterprise_context: bool = True
    include_publish_records: bool = True


@router.post("/query")
async def intelligence_query(req: IntelligenceQueryRequest):
    try:
        report = await run_intelligence_query(
            req.query,
            use_enterprise_context=req.use_enterprise_context,
            include_publish_records=req.include_publish_records,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "report": report}


@router.get("/query-reports")
async def intelligence_query_reports(limit: int = Query(default=20, ge=1, le=100)):
    items = list_intelligence_reports(limit=limit)
    return {"ok": True, "items": items, "total": len(items)}


@router.get("/query-reports/{report_id}")
async def intelligence_query_report(report_id: str):
    try:
        report = get_intelligence_report(report_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="情报报告不存在") from exc
    return {"ok": True, "report": report}


@router.get("/collectors")
async def intelligence_collectors():
    return {
        "ok": True,
        "items": get_intelligence_collector_registry().describe(),
    }


@router.get("/overview")
async def intelligence_overview():
    return {"ok": True, "overview": overview()}


@router.get("/business-profiles")
async def intelligence_business_profiles():
    items = list_business_profiles()
    return {"ok": True, "items": items, "total": len(items)}


@router.post("/business-profile")
async def intelligence_business_profile(req: BusinessProfileRequest):
    return {"ok": True, "item": upsert_business_profile(req.model_dump())}


@router.post("/discover")
async def intelligence_discover(req: BusinessProfileRequest):
    discovery = await discover_from_profile(req.model_dump())
    return {"ok": True, "discovery": discovery}


@router.get("/discoveries")
async def intelligence_discoveries(limit: int = Query(default=20, ge=1, le=100)):
    items = list_discoveries(limit=limit)
    return {"ok": True, "items": items, "total": len(items)}


@router.get("/content-items")
async def intelligence_content_items(
    limit: int = Query(default=50, ge=1, le=200),
    platform: str = Query(default=""),
    keyword: str = Query(default=""),
):
    items = list_content_items(limit=limit, platform=platform, keyword=keyword)
    return {"ok": True, "items": items, "total": len(items)}


@router.get("/reports/daily")
async def intelligence_daily_report():
    return {"ok": True, "report": latest_report()}


@router.get("/visualization")
async def intelligence_visualization():
    return {"ok": True, "visualization": visualization_data()}


@router.get("/sources")
async def intelligence_sources():
    items = list_information_sources()
    return {"ok": True, "items": items, "total": len(items)}


@router.post("/sources")
async def intelligence_create_source(req: InformationSourceRequest):
    try:
        item = create_information_source(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "item": item}


@router.put("/sources/{source_id}")
async def intelligence_update_source(source_id: str, req: InformationSourceUpdateRequest):
    try:
        item = update_information_source(source_id, req.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="信息源不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "item": item}


@router.delete("/sources/{source_id}")
async def intelligence_delete_source(source_id: str):
    if not delete_information_source(source_id):
        raise HTTPException(status_code=404, detail="信息源不存在")
    return {"ok": True}


@router.get("/market-news")
async def intelligence_market_news(
    limit: int = Query(default=50, ge=1, le=500),
    keyword: str = Query(default=""),
    source_id: str = Query(default=""),
):
    items = list_market_news(limit=limit, keyword=keyword, source_id=source_id)
    return {"ok": True, "items": items, "total": len(items)}


@router.post("/market-news/collect")
async def intelligence_collect_market_news(req: MarketNewsCollectRequest):
    result = await collect_market_news(req.profile_id, req.include_auto_search)
    return {"ok": True, **result}


@router.get("/briefs")
async def intelligence_content_briefs(limit: int = Query(default=20, ge=1, le=100)):
    items = list_content_briefs(limit=limit)
    return {"ok": True, "items": items, "total": len(items)}


@router.post("/briefs")
async def intelligence_create_content_brief(req: ContentBriefRequest):
    try:
        brief = create_content_brief(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "brief": brief}


@router.get("/briefs/{brief_id}/prompt")
async def intelligence_content_brief_prompt(brief_id: str):
    try:
        return {"ok": True, **content_brief_prompt(brief_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="选题简报不存在") from exc


@router.post("/discoveries/{discovery_id}/accept")
async def intelligence_accept_discovery(discovery_id: str, req: DiscoveryAcceptRequest):
    try:
        row = accept_discovery_candidate(discovery_id, req.candidate_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc) or "候选项不存在") from exc
    return {"ok": True, "item": row}


@router.get("/competitors")
async def intelligence_competitors(
    platform: str = Query(default=""),
    keyword: str = Query(default=""),
):
    items = list_competitors(platform=platform, keyword=keyword)
    return {"ok": True, "items": items, "total": len(items)}


@router.post("/competitors")
async def intelligence_create_competitor(req: CompetitorCreateRequest):
    try:
        row = create_competitor(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "item": row}


@router.post("/competitors/sync-all")
async def intelligence_sync_competitors(
    platform: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=50),
):
    items = sync_competitors(platform=platform, limit=limit)
    return {"ok": True, "items": items, "total": len(items)}


@router.delete("/competitors/{competitor_id}")
async def intelligence_delete_competitor(competitor_id: str):
    if not delete_competitor(competitor_id):
        raise HTTPException(status_code=404, detail="竞品账号不存在")
    return {"ok": True}


@router.post("/competitors/{competitor_id}/sync")
async def intelligence_sync_competitor(competitor_id: str):
    try:
        row = sync_competitor(competitor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="竞品账号不存在") from exc
    return {"ok": True, "item": row}
