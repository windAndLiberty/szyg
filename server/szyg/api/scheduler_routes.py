"""Smart Scheduler API routes"""
from fastapi import APIRouter, HTTPException, Depends
from szyg.scheduler_engine import (get_scheduler, ScheduleJob, JobExecution,
                                    JobStatus, TriggerType, JobAction)
from szyg.auth import User
from szyg.api.auth_routes import require_admin

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/jobs", response_model=list[ScheduleJob])
async def list_jobs(status: str = "", tag: str = "", search: str = "", limit: int = 50):
    return get_scheduler().list_jobs(status, tag, search, limit)


@router.get("/jobs/{job_id}", response_model=ScheduleJob)
async def get_job(job_id: str):
    j = get_scheduler().get_job(job_id)
    if not j: raise HTTPException(404, "任务不存在")
    return j


@router.post("/jobs", response_model=ScheduleJob)
async def create_job(
    name: str, trigger_type: str = "manual", action: str = "custom",
    description: str = "", priority: int = 5,
    cron: str = "", interval_minutes: int = 60, at_time: str = "",
    action_config_json: str = "{}", tags: str = "",
    admin: User = Depends(require_admin),
):
    import json
    # Build trigger config
    trigger = TriggerType(trigger_type)
    trigger_config = {}
    if trigger == TriggerType.CRON and cron:
        trigger_config["cron"] = cron
    elif trigger == TriggerType.INTERVAL:
        trigger_config["minutes"] = interval_minutes
    elif trigger == TriggerType.ONCE and at_time:
        trigger_config["at"] = at_time

    # Build action config
    try:
        act_config = json.loads(action_config_json) if action_config_json else {}
    except json.JSONDecodeError:
        act_config = {}

    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    return get_scheduler().create_job(
        name=name, description=description,
        trigger_type=trigger, trigger_config=trigger_config,
        action=JobAction(action), action_config=act_config,
        priority=priority, tags=tag_list,
    )


@router.put("/jobs/{job_id}", response_model=ScheduleJob)
async def update_job(job_id: str, name: str = "", priority: int = 0,
                      admin: User = Depends(require_admin)):
    kwargs = {}
    if name: kwargs["name"] = name
    if priority: kwargs["priority"] = priority
    j = get_scheduler().update_job(job_id, **kwargs)
    if not j: raise HTTPException(404, "任务不存在")
    return j


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, admin: User = Depends(require_admin)):
    if get_scheduler().delete_job(job_id):
        return {"ok": True}
    raise HTTPException(404, "任务不存在")


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    j = get_scheduler().pause_job(job_id)
    if not j: raise HTTPException(404, "任务不存在")
    return j


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    j = get_scheduler().resume_job(job_id)
    if not j: raise HTTPException(404, "任务不存在")
    return j


@router.post("/jobs/{job_id}/execute", response_model=JobExecution)
async def execute_job(job_id: str):
    return get_scheduler().execute_job(job_id)


@router.get("/history", response_model=list[JobExecution])
async def history(job_id: str = "", limit: int = 50):
    return get_scheduler().get_history(job_id, limit)


@router.get("/stats")
async def stats():
    return get_scheduler().get_stats()
