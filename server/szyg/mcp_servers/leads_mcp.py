#!/usr/bin/env python3
"""MCP Server: Lead Manager — AI 销冠线索引擎。

挂载到 Hermes，提供线索搜索、评分、创建、更新能力。
Hermes 可以通过这些工具自动完成「发现线索→评分→跟进」闭环。
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer
from szyg.lead_store import get_lead_store
from szyg.lead_scoring import score_intent
from szyg.models.lead import IntentScoringRequest, LeadProfile, LeadSource, IntentLevel, ConversionStage

server = MCPServer("szyg-leads", "AI-powered lead scoring and management pipeline")

store = get_lead_store()


@server.tool("lead_search", "Search leads by keyword, intent level, stage, or platform")
def lead_search(query: str = "", intent_level: str = "", stage: str = "", platform: str = "", limit: int = 20):
    if query:
        leads = store.search(query, limit)
    else:
        il = IntentLevel(intent_level) if intent_level else None
        cs = ConversionStage(stage) if stage else None
        ps = LeadSource(platform) if platform else None
        leads = store.list_leads(intent_level=il, stage=cs, platform=ps, limit=limit, offset=0)
    return [
        {"id": l.id, "name": l.name, "platform": l.platform.value,
         "company": l.company, "industry": l.industry,
         "intent_score": l.intent_score, "intent_level": l.intent_level.value,
         "stage": l.conversion_stage.value, "tags": l.tags,
         "created": l.created_at.isoformat()}
        for l in leads
    ]


@server.tool("lead_score", "Score a user comment or message for purchase intent")
def lead_score(platform: str, content: str, context: str = ""):
    try:
        ps = LeadSource(platform)
    except ValueError:
        ps = LeadSource.MANUAL
    req = IntentScoringRequest(platform=ps, interaction_content=content, context=context)
    result = score_intent(req)
    return {
        "intent_score": result.intent_score,
        "intent_level": result.intent_level.value,
        "signals": result.intent_signals,
        "suggested_reply": result.suggested_reply,
        "should_follow_up": result.should_follow_up,
        "tags": result.tags,
    }


@server.tool("lead_create", "Create a new lead manually")
def lead_create(platform: str, account: str = "", name: str = "", content: str = "", tags: str = ""):
    try:
        ps = LeadSource(platform)
    except ValueError:
        ps = LeadSource.MANUAL
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    lead = LeadProfile(
        name=name or account,
        platform=ps,
        platform_account=account,
        source_content=content,
        tags=tag_list,
    )
    stored = store.create(lead)
    return {"id": stored.id, "name": stored.name, "platform": stored.platform.value,
            "intent_level": stored.intent_level.value, "created": stored.created_at.isoformat()}


@server.tool("lead_update", "Update lead status, notes, or stage")
def lead_update(lead_id: str, stage: str = "", notes: str = "", assigned_to: str = "",
                intent_score: float = -1.0):
    kwargs = {}
    if stage:
        try:
            kwargs["conversion_stage"] = ConversionStage(stage)
        except ValueError:
            pass
    if notes:
        kwargs["notes"] = notes
    if assigned_to:
        kwargs["assigned_to"] = assigned_to
    if intent_score >= 0:
        kwargs["intent_score"] = intent_score
        if intent_score >= 0.6:
            kwargs["intent_level"] = IntentLevel.HIGH
        elif intent_score >= 0.35:
            kwargs["intent_level"] = IntentLevel.MEDIUM
        elif intent_score >= 0.15:
            kwargs["intent_level"] = IntentLevel.LOW
        else:
            kwargs["intent_level"] = IntentLevel.COLD
    updated = store.update(lead_id, **kwargs)
    if not updated:
        return {"error": f"Lead {lead_id} not found"}
    return {"id": updated.id, "intent_score": updated.intent_score,
            "intent_level": updated.intent_level.value,
            "stage": updated.conversion_stage.value, "notes": updated.notes}


@server.tool("lead_stats", "Get lead statistics overview")
def lead_stats():
    stats = store.stats()
    return {
        "total": stats["total"],
        "today_new": stats["today_new"],
        "by_intent": stats.get("by_intent", {}),
        "by_stage": stats.get("by_stage", {}),
    }


if __name__ == "__main__":
    server.run()
