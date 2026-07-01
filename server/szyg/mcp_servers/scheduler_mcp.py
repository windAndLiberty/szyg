#!/usr/bin/env python3
"""MCP Server: Smart Scheduler"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer
from szyg.scheduler_engine import get_scheduler, TriggerType, JobAction

server = MCPServer("szyg-scheduler", "Smart scheduling engine with cron/interval/event triggers")
sched = get_scheduler()

@server.tool("sched_list", "List all scheduled jobs")
def sched_list(status: str = "", tag: str = "", search: str = ""):
    jobs = sched.list_jobs(status, tag, search)
    return [{"id": j.id, "name": j.name, "trigger": j.trigger_type.value, "action": j.action.value,
             "status": j.status.value, "priority": j.priority, "next_run": j.next_run_at[:19] if j.next_run_at else ""} for j in jobs]

@server.tool("sched_get", "Get a job by ID")
def sched_get(job_id: str):
    j = sched.get_job(job_id)
    if not j: return {"error": "Job not found"}
    return {"id": j.id, "name": j.name, "description": j.description, "trigger": j.trigger_type.value,
            "trigger_config": j.trigger_config, "action": j.action.value, "action_config": j.action_config,
            "status": j.status.value, "priority": j.priority, "next_run": j.next_run_at[:19] if j.next_run_at else ""}

@server.tool("sched_create", "Create a new scheduled job")
def sched_create(name: str, trigger_type: str = "manual", action: str = "custom",
                 cron: str = "", interval_minutes: int = 0, at_time: str = "",
                 action_config_json: str = "{}", priority: int = 5, tags: str = ""):
    import json as _json
    trigger = TriggerType(trigger_type)
    tconf = {}
    if trigger == TriggerType.CRON and cron: tconf["cron"] = cron
    elif trigger == TriggerType.INTERVAL and interval_minutes: tconf["minutes"] = interval_minutes
    elif trigger == TriggerType.ONCE and at_time: tconf["at"] = at_time
    try: aconf = _json.loads(action_config_json) if action_config_json else {}
    except (ValueError, TypeError): aconf = {}
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    j = sched.create_job(name=name, trigger_type=trigger, trigger_config=tconf,
                         action=JobAction(action), action_config=aconf, priority=priority, tags=tag_list)
    return {"id": j.id, "name": j.name, "status": j.status.value}

@server.tool("sched_execute", "Execute a job immediately")
def sched_execute(job_id: str):
    ex = sched.execute_job(job_id)
    return {"job_id": ex.job_id, "job_name": ex.job_name, "status": ex.status, "result": ex.result, "error": ex.error}

@server.tool("sched_pause", "Pause a running job")
def sched_pause(job_id: str):
    j = sched.pause_job(job_id)
    return {"id": j.id, "status": j.status.value} if j else {"error": "Not found"}

@server.tool("sched_resume", "Resume a paused job")
def sched_resume(job_id: str):
    j = sched.resume_job(job_id)
    return {"id": j.id, "status": j.status.value} if j else {"error": "Not found"}

@server.tool("sched_delete", "Delete a job")
def sched_delete(job_id: str):
    return {"ok": sched.delete_job(job_id)}

@server.tool("sched_history", "Get execution history")
def sched_history(job_id: str = "", limit: int = 20):
    items = sched.get_history(job_id, limit)
    return [{"id": h.id, "job_name": h.job_name, "status": h.status, "started": h.started_at[:19],
             "result": h.result, "error": h.error} for h in items]

@server.tool("sched_stats", "Get scheduler statistics")
def sched_stats():
    return sched.get_stats()

if __name__ == "__main__":
    server.run()
