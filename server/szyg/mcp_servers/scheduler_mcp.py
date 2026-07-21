#!/usr/bin/env python3
"""MCP compatibility server backed by WorkflowService and ExecutionKernel."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from szyg.mcp_server import MCPServer
from szyg.workflow_service import get_workflow_service


server = MCPServer("szyg-automation", "Automation plans, schedules, and observable runs")
service = get_workflow_service()


@server.tool("sched_list", "List automation plans")
def sched_list(status: str = "", tag: str = "", search: str = ""):
    del tag
    items = service.list_instances()
    if status:
        items = [item for item in items if item.get("status") == status]
    if search:
        query = search.lower()
        items = [item for item in items if query in item.get("name", "").lower() or query in item.get("description", "").lower()]
    return items


@server.tool("sched_get", "Get an automation plan by ID")
def sched_get(job_id: str):
    return service.get_instance(job_id) or {"error": "Automation plan not found"}


@server.tool("sched_create", "Create an automation plan from a standard process")
def sched_create(
    name: str,
    template_id: str,
    trigger_type: str = "manual",
    interval_minutes: int = 60,
    at_time: str = "",
):
    schedule = {"type": trigger_type}
    if trigger_type == "interval":
        schedule["interval_minutes"] = interval_minutes
    elif trigger_type == "once":
        schedule["at"] = at_time
    elif trigger_type in {"daily", "weekly"}:
        schedule["time"] = at_time or "09:00"
    return service.create_instance({"name": name, "template_id": template_id, "schedule": schedule})


@server.tool("sched_execute", "Run an automation plan immediately")
def sched_execute(job_id: str):
    async def execute():
        run = await service.run_instance(job_id)
        return await service.execute_run(run["id"])

    return asyncio.run(execute())


@server.tool("sched_pause", "Pause an automation plan")
def sched_pause(job_id: str):
    try:
        return service.update_instance(job_id, {"status": "paused"})
    except KeyError:
        return {"error": "Automation plan not found"}


@server.tool("sched_resume", "Resume an automation plan")
def sched_resume(job_id: str):
    try:
        return service.update_instance(job_id, {"status": "active"})
    except KeyError:
        return {"error": "Automation plan not found"}


@server.tool("sched_delete", "Delete an automation plan")
def sched_delete(job_id: str):
    return {"ok": service.delete_instance(job_id)}


@server.tool("sched_history", "Get automation run history")
def sched_history(job_id: str = "", limit: int = 20):
    items = service.list_runs(limit=limit)
    return [item for item in items if not job_id or item.get("instance_id") == job_id]


@server.tool("sched_stats", "Get automation statistics")
def sched_stats():
    return service.overview()


if __name__ == "__main__":
    server.run()
