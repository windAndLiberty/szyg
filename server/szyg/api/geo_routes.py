"""User-facing GEO brand growth API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from szyg.geo_service import get_geo_service


router = APIRouter(prefix="/api/geo", tags=["geo"])


class GeoProfileRequest(BaseModel):
    product_name: str = Field(min_length=1, max_length=120)
    website: str = Field(default="", max_length=500)
    industry: str = Field(default="", max_length=120)
    audience: str = Field(default="", max_length=300)
    region: str = Field(default="", max_length=120)
    brand_aliases: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["zh-CN"])
    geo_providers: list[str] = Field(default_factory=list)


class GeoQuestionsRequest(BaseModel):
    questions: list[str] = Field(default_factory=list, max_length=100)
    items: list[dict] = Field(default_factory=list, max_length=100)


class GeoQuestionSuggestionRequest(BaseModel):
    limit: int = Field(default=12, ge=1, le=30)


class GeoFactsRequest(BaseModel):
    items: list[dict] = Field(default_factory=list, max_length=200)


class GeoAuditRequest(BaseModel):
    provider_ids: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    question_ids: list[str] = Field(default_factory=list)
    sample_count: int | None = Field(default=None, ge=1, le=5)
    mode: str = Field(default="diagnostic", pattern="^(diagnostic|scheduled|verification)$")


class GeoRecommendationUpdateRequest(BaseModel):
    status: str = Field(pattern="^(open|in_progress|done|dismissed)$")


class GeoSpotCheckRequest(BaseModel):
    question_ids: list[str] = Field(default_factory=list, max_length=5)


class GeoSpotCaptureRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    answer: str = Field(min_length=1, max_length=50000)
    citations: list[str | dict] = Field(default_factory=list, max_length=100)


@router.get("/profile")
async def geo_profile():
    return get_geo_service().get_profile()


@router.put("/profile")
async def update_geo_profile(req: GeoProfileRequest):
    try:
        return get_geo_service().update_profile(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/questions")
async def geo_questions():
    service = get_geo_service()
    return {"items": service.get_questions(), "details": service.list_question_details()}


@router.put("/questions")
async def update_geo_questions(req: GeoQuestionsRequest):
    try:
        values = req.items or req.questions
        items = get_geo_service().update_questions(values)
        return {"items": items, "details": get_geo_service().list_question_details()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/questions/suggest")
async def suggest_geo_questions(req: GeoQuestionSuggestionRequest):
    return {"items": await get_geo_service().suggest_questions(req.limit)}


@router.get("/facts")
async def geo_facts():
    items = get_geo_service().get_facts()
    return {"items": items, "total": len(items)}


@router.put("/facts")
async def update_geo_facts(req: GeoFactsRequest):
    items = get_geo_service().update_facts(req.items)
    return {"items": items, "total": len(items)}


@router.post("/audits", status_code=202)
async def create_geo_audit(req: GeoAuditRequest):
    service = get_geo_service()
    try:
        audit = service.create_audit(
            req.provider_ids or None,
            req.questions or None,
            question_ids=req.question_ids or None,
            sample_count=req.sample_count,
            mode=req.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return audit


@router.get("/audits/{audit_id}")
async def geo_audit(audit_id: str):
    try:
        return get_geo_service().get_audit(audit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="GEO检测任务不存在") from exc


@router.post("/audits/{audit_id}/cancel")
async def cancel_geo_audit(audit_id: str):
    try:
        return get_geo_service().cancel_audit(audit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="GEO检测任务不存在") from exc


@router.get("/overview")
async def geo_overview(days: int = Query(default=30, ge=1, le=365)):
    return get_geo_service().overview(days)


@router.get("/observations")
async def geo_observations(
    audit_id: str = Query(default=""),
    provider_id: str = Query(default=""),
    question_id: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=1000),
):
    items = get_geo_service().list_observations(audit_id=audit_id, provider_id=provider_id, question_id=question_id, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/recommendations")
async def geo_recommendations(limit: int = Query(default=100, ge=1, le=500)):
    items = get_geo_service().list_recommendations(limit)
    return {"items": items, "total": len(items)}


@router.get("/recommendations/{recommendation_id}")
async def geo_recommendation(recommendation_id: str):
    try:
        return get_geo_service().get_recommendation(recommendation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="GEO优化建议不存在") from exc


@router.patch("/recommendations/{recommendation_id}")
async def update_geo_recommendation(recommendation_id: str, req: GeoRecommendationUpdateRequest):
    try:
        return get_geo_service().update_recommendation(recommendation_id, req.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="GEO优化建议不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recommendations/{recommendation_id}/verify", status_code=202)
async def verify_geo_recommendation(recommendation_id: str):
    try:
        return get_geo_service().verify_recommendation(recommendation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="GEO优化建议不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sources")
async def geo_sources(limit: int = Query(default=100, ge=1, le=500)):
    items = get_geo_service().list_sources(limit)
    return {"items": items, "total": len(items)}


@router.post("/site-review")
async def geo_site_review():
    try:
        return await get_geo_service().review_site()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/spot-checks", status_code=202)
async def create_geo_spot_check(req: GeoSpotCheckRequest):
    try:
        return get_geo_service().create_spot_check(req.question_ids or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/spot-checks/{audit_id}/capture")
async def capture_geo_spot_check(audit_id: str, req: GeoSpotCaptureRequest):
    try:
        return await get_geo_service().capture_spot_check(audit_id, req.question_id, req.answer, req.citations)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="GEO抽检任务不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
