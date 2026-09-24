"""User-facing workflow API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from szyg.execution_kernel import get_execution_kernel
from szyg.workflow_service import get_workflow_service


router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class InstanceCreateRequest(BaseModel):
    template_id: str = ""
    definition_id: str = ""
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    schedule: dict[str, Any] = Field(default_factory=lambda: {"type": "manual"})
    config: dict[str, Any] = Field(default_factory=dict)
    human_policy: str = "pause_on_risk"


class InstanceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    status: str | None = None
    schedule: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    human_policy: str | None = None


class SopUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    enabled: bool | None = None
    steps: list[dict[str, Any]] | None = None


class DraftCreateRequest(BaseModel):
    goal: str = Field(min_length=2, max_length=2000)
    context: dict[str, bool] = Field(default_factory=lambda: {"knowledge": True})
    schedule: dict[str, Any] = Field(default_factory=lambda: {"type": "manual"})
    notification: str = "in_app"


class DraftUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    outcome: str | None = Field(default=None, max_length=300)
    context: dict[str, bool] | None = None
    schedule: dict[str, Any] | None = None
    notification: str | None = None
    steps: list[dict[str, Any]] | None = None


class DraftReviseRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=1000)


def _not_found(message: str = "记录不存在") -> HTTPException:
    return HTTPException(status_code=404, detail=message)


@router.on_event("startup")
async def start_workflow_scheduler() -> None:
    service = get_workflow_service()
    service.archive_legacy_scheduler_data()
    service.start_scheduler()


@router.on_event("shutdown")
async def stop_workflow_scheduler() -> None:
    await get_workflow_service().stop_scheduler()


@router.get("/overview")
async def overview():
    return get_workflow_service().overview()


@router.get("/templates")
async def templates():
    items = get_workflow_service().list_templates()
    return {"items": items, "total": len(items)}


@router.get("/capabilities")
async def capabilities():
    items = get_workflow_service().list_capabilities()
    return {"items": items, "total": len(items)}


@router.post("/drafts")
async def create_draft(req: DraftCreateRequest):
    try:
        return get_workflow_service().create_draft(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, req: DraftUpdateRequest):
    try:
        return get_workflow_service().update_draft(draft_id, req.model_dump(exclude_none=True))
    except KeyError:
        raise _not_found("方案草稿不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/drafts/{draft_id}/design")
async def design_draft(draft_id: str):
    try:
        return await get_workflow_service().design_draft(draft_id)
    except KeyError:
        raise _not_found("方案草稿不存在")
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/drafts/{draft_id}/revise")
async def revise_draft(draft_id: str, req: DraftReviseRequest):
    try:
        return await get_workflow_service().revise_draft(draft_id, req.instruction)
    except KeyError:
        raise _not_found("方案草稿不存在")
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/drafts/{draft_id}/validate")
async def validate_draft(draft_id: str):
    try:
        return get_workflow_service().validate_draft(draft_id)
    except KeyError:
        raise _not_found("方案草稿不存在")


@router.post("/drafts/{draft_id}/activate")
async def activate_draft(draft_id: str):
    try:
        return get_workflow_service().activate_draft(draft_id)
    except KeyError:
        raise _not_found("方案草稿不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/templates/{template_id}")
async def template_detail(template_id: str):
    item = get_workflow_service().get_template(template_id)
    if not item:
        raise _not_found("工作流方案不存在")
    return item


@router.get("/instances")
async def instances():
    items = get_workflow_service().list_instances()
    return {"items": items, "total": len(items)}


@router.post("/instances")
async def create_instance(req: InstanceCreateRequest):
    try:
        return get_workflow_service().create_instance(req.model_dump())
    except KeyError:
        raise _not_found("工作流方案不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/instances/{instance_id}")
async def instance_detail(instance_id: str):
    item = get_workflow_service().get_instance(instance_id)
    if not item:
        raise _not_found("已启用方案不存在")
    return item


@router.put("/instances/{instance_id}")
async def update_instance(instance_id: str, req: InstanceUpdateRequest):
    try:
        return get_workflow_service().update_instance(instance_id, req.model_dump(exclude_none=True))
    except KeyError:
        raise _not_found("已启用方案不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/instances/{instance_id}/schedule")
async def update_instance_schedule(instance_id: str, schedule: dict[str, Any]):
    try:
        return get_workflow_service().update_instance(instance_id, {"schedule": schedule})
    except KeyError:
        raise _not_found("已启用方案不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/instances/{instance_id}/upgrade")
async def upgrade_instance(instance_id: str):
    try:
        return get_workflow_service().upgrade_instance(instance_id)
    except KeyError:
        raise _not_found("已启用方案不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str):
    if not get_workflow_service().delete_instance(instance_id):
        raise _not_found("已启用方案不存在")
    return {"ok": True}


@router.post("/instances/{instance_id}/run")
async def run_instance(instance_id: str):
    try:
        return await get_workflow_service().run_instance(instance_id)
    except KeyError:
        raise _not_found("已启用方案不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/runs")
async def runs(
    limit: int = Query(default=50, ge=1, le=500),
    instance_id: str = Query(default=""),
):
    items = get_workflow_service().list_runs(limit=limit)
    if instance_id:
        items = [item for item in items if item.get("instance_id") == instance_id]
    return {"items": items, "total": len(items)}


@router.get("/runs/{run_id}")
async def run_detail(run_id: str):
    kernel = get_execution_kernel()
    run = kernel.get_run(run_id)
    if not run or run.get("task_type") != "workflow":
        raise _not_found("运行记录不存在")
    return {
        "run": get_workflow_service()._map_run(run),
        "steps": kernel.list_steps(run_id),
        "audit": kernel.list_audit(run_id),
        "observations": kernel.list_observations(run_id),
    }


@router.post("/runs/{run_id}/{action}")
async def control_run(run_id: str, action: str):
    service = get_workflow_service()
    kernel = get_execution_kernel()
    run = kernel.get_run(run_id)
    if not run or run.get("task_type") != "workflow":
        raise _not_found("运行记录不存在")
    try:
        if action == "retry":
            return service._map_run(kernel.retry_run(run_id))
        if action == "confirm":
            return service.confirm_run(run_id)
        if action == "pause":
            return service._map_run(kernel.pause_run(run_id))
        if action == "resume":
            return service._map_run(kernel.resume_run(run_id))
        if action == "cancel":
            return service._map_run(kernel.cancel_run(run_id))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    raise HTTPException(status_code=400, detail="不支持的任务操作")


@router.get("/sops")
async def sops():
    items = get_workflow_service().list_sops()
    return {"items": items, "total": len(items)}


@router.post("/sops/{sop_id}/clone")
async def clone_sop(sop_id: str):
    try:
        return get_workflow_service().clone_sop(sop_id)
    except KeyError:
        raise _not_found("标准流程不存在")


@router.put("/sops/{sop_id}")
async def update_sop(sop_id: str, req: SopUpdateRequest):
    try:
        return get_workflow_service().update_sop(sop_id, req.model_dump(exclude_none=True))
    except KeyError:
        raise _not_found("标准流程不存在")


@router.delete("/sops/{sop_id}")
async def delete_sop(sop_id: str):
    try:
        if not get_workflow_service().delete_sop(sop_id):
            raise _not_found("标准流程不存在")
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
