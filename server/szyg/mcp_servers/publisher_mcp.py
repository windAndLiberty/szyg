#!/usr/bin/env python3
"""MCP Server: Content Publisher"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer
from szyg.publisher import get_publisher, Platform, ContentType

server = MCPServer("szyg-publisher", "Content publishing pipeline with review workflow")

pub = get_publisher()

@server.tool("pub_list", "List all content items with optional filters")
def pub_list(status: str = "", content_type: str = "", search: str = "", limit: int = 50):
    items = pub.list_contents(status, content_type, search, limit)
    return [{"id": i.id, "title": i.title, "status": i.status.value, "type": i.content_type.value,
             "scheduled": i.scheduled_at[:16] if i.scheduled_at else "", "tags": i.tags} for i in items]

@server.tool("pub_get", "Get a single content item by ID")
def pub_get(content_id: str):
    c = pub.get_content(content_id)
    if not c: return {"error": "Content not found"}
    return {"id": c.id, "title": c.title, "body": c.body, "status": c.status.value,
            "type": c.content_type.value, "platforms": [p.value for p in c.platforms],
            "created_at": c.created_at[:19], "ai_generated": c.ai_generated}

@server.tool("pub_create", "Create a new content draft")
def pub_create(title: str, body: str = "", content_type: str = "post", platforms: str = "all", tags: str = ""):
    plat_list = [Platform(p) for p in platforms.split(",")] if platforms != "all" else [Platform.ALL]
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    c = pub.create(title=title, body=body, content_type=content_type, platforms=plat_list, tags=tag_list)
    return {"id": c.id, "title": c.title, "status": c.status.value}

@server.tool("pub_submit", "Submit content for review")
def pub_submit(content_id: str):
    c = pub.submit_review(content_id)
    return {"id": c.id, "status": c.status.value} if c else {"error": "Not found"}

@server.tool("pub_approve", "Approve content for publishing")
def pub_approve(content_id: str, comment: str = ""):
    c = pub.approve(content_id, comment)
    return {"id": c.id, "status": c.status.value} if c else {"error": "Not found"}

@server.tool("pub_reject", "Reject content with comment")
def pub_reject(content_id: str, comment: str = ""):
    c = pub.reject(content_id, comment)
    return {"id": c.id, "status": c.status.value} if c else {"error": "Not found"}

@server.tool("pub_schedule", "Schedule content for future publishing (ISO datetime)")
def pub_schedule(content_id: str, scheduled_at: str):
    c = pub.schedule(content_id, scheduled_at)
    return {"id": c.id, "scheduled_at": c.scheduled_at} if c else {"error": "Not found"}

@server.tool("pub_publish", "Publish content now to specified platforms")
def pub_publish(content_id: str, platform: str = ""):
    p = Platform(platform) if platform else None
    result = pub.publish_now(content_id, p)
    return {"published": len(result), "platforms": [r["platform"] for r in result]}

@server.tool("pub_ai_generate", "Use AI agent to generate content draft")
async def pub_ai_generate(topic: str, agent_id: str = "copywriter", content_type: str = "post"):
    c = await pub.ai_generate(topic, agent_id, content_type)
    return {"id": c.id, "title": c.title, "body_preview": c.body[:200]}

@server.tool("pub_stats", "Get publishing statistics")
def pub_stats():
    return pub.get_stats()

@server.tool("pub_calendar", "Get content calendar for a month (YYYY-MM)")
def pub_calendar(month: str = ""):
    return pub.get_calendar(month)

@server.tool("pub_logs", "Get recent publishing logs")
def pub_logs(limit: int = 20):
    return pub.get_logs(limit)

if __name__ == "__main__":
    server.run()
