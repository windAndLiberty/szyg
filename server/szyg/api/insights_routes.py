"""Unified data-insights API."""

from fastapi import APIRouter, Query

from szyg.insights_service import get_insights_service


router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/overview")
def insights_overview(days: int = Query(default=30, ge=1, le=365)):
    return get_insights_service().overview(days=days)


@router.get("/content")
def content_insights(days: int = Query(default=30, ge=1, le=365)):
    return get_insights_service().content(days=days)
