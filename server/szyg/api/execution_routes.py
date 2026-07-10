"""Execution Kernel API routes."""

from fastapi import APIRouter, HTTPException, Query

from szyg.execution_kernel import get_execution_kernel

router = APIRouter(prefix="/api/executions", tags=["executions"])


@router.get("")
async def list_executions(
    limit: int = Query(100, ge=1, le=500),
    status: str = Query("", description="Optional execution status filter"),
    platform: str = Query("", description="Optional platform filter"),
):
    kernel = get_execution_kernel()
    return {"runs": kernel.list_runs(limit=limit, status=status, platform=platform)}


@router.get("/{run_id}")
async def get_execution(run_id: str):
    kernel = get_execution_kernel()
    run = kernel.get_run(run_id)
    if not run:
        raise HTTPException(404, "Execution not found")
    return {
        **run,
        "steps": kernel.list_steps(run_id),
        "audit": kernel.list_audit(run_id),
        "observations": kernel.list_observations(run_id),
    }


@router.get("/{run_id}/steps")
async def get_execution_steps(run_id: str):
    kernel = get_execution_kernel()
    if not kernel.get_run(run_id):
        raise HTTPException(404, "Execution not found")
    return {"steps": kernel.list_steps(run_id)}


@router.get("/{run_id}/audit")
async def get_execution_audit(run_id: str):
    kernel = get_execution_kernel()
    if not kernel.get_run(run_id):
        raise HTTPException(404, "Execution not found")
    return {
        "audit": kernel.list_audit(run_id),
        "observations": kernel.list_observations(run_id),
    }


@router.post("/{run_id}/pause")
async def pause_execution(run_id: str):
    kernel = get_execution_kernel()
    try:
        run = kernel.pause_run(run_id)
    except KeyError:
        raise HTTPException(404, "Execution not found")
    return {"ok": True, "run": run}


@router.post("/{run_id}/cancel")
async def cancel_execution(run_id: str):
    kernel = get_execution_kernel()
    try:
        run = kernel.cancel_run(run_id)
    except KeyError:
        raise HTTPException(404, "Execution not found")
    return {"ok": True, "run": run}


@router.post("/{run_id}/resume")
async def resume_execution(run_id: str):
    kernel = get_execution_kernel()
    try:
        run = kernel.resume_run(run_id)
    except KeyError:
        raise HTTPException(404, "Execution not found")
    return {"ok": True, "run": run}


@router.post("/{run_id}/retry")
async def retry_execution(run_id: str):
    kernel = get_execution_kernel()
    try:
        run = kernel.retry_run(run_id)
    except KeyError:
        raise HTTPException(404, "Execution not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": run}

