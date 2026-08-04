"""Computer-use API routes for controlled Windows desktop automation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from szyg.execution_kernel import get_execution_kernel
from szyg.integrations.computer_use_adapter import get_computer_use_adapter

router = APIRouter(prefix="/api/computer-use", tags=["computer-use"])


class ComputerUseTaskRequest(BaseModel):
    instruction: str = Field(..., min_length=1)
    target_app: str = "windows"
    url: str = ""
    mode: str = "assisted"
    expected_result: str = ""
    target_selector: str = ""
    files: list[str] = Field(default_factory=list)
    steps: list[dict] = Field(default_factory=list)
    max_steps: int = Field(8, ge=1, le=20)
    require_confirmation: bool = True
    allowed_actions: list[str] = Field(default_factory=lambda: ["observe", "open_url", "launch", "click", "type", "hotkey", "upload_file", "wait_for", "verify"])
    sensitive_policy: str = "handoff"
    text: str = ""


class ComputerUseObserveRequest(BaseModel):
    process: str = ""
    title: str = ""
    include_ocr: bool = True
    include_browser_dom: bool = True


class ComputerUseClickIndexRequest(BaseModel):
    index: int = Field(..., ge=1)
    process: str = ""
    vision_type: str = "UiTree"
    x_percentage: int = Field(50, ge=0, le=100)
    y_percentage: int = Field(50, ge=0, le=100)


class ComputerUseClickBoundsRequest(BaseModel):
    bounds: dict
    process: str = ""


class ComputerUseVerifyRequest(BaseModel):
    selector: str = Field(..., min_length=1)
    scope_selector: str = ""
    timeout_ms: int = Field(3000, ge=100, le=30000)


class ComputerUseVisionParseRequest(BaseModel):
    screenshot_path: str = ""
    current_screen: bool = False


class ComputerUseBrowserOpenRequest(BaseModel):
    url: str = Field(..., min_length=1)


@router.get("/status")
async def status():
    adapter = get_computer_use_adapter()
    health, active, windows = await adapter.health(), await adapter.active_window(), await adapter.list_windows()
    return {
        "ok": True,
        "health": health,
        "active_window": active,
        "windows": windows,
        "providers": health.get("providers", {}),
        "backend_version": health.get("backend", "desktop"),
        "vision_fallback_enabled": health.get("available", False),
    }


@router.post("/observe")
async def observe():
    adapter = get_computer_use_adapter()
    return await adapter.observe()


@router.post("/browser/open")
async def browser_open(body: ComputerUseBrowserOpenRequest):
    adapter = get_computer_use_adapter()
    return await adapter.browser_open(body.url)


@router.post("/tree")
async def tree(body: ComputerUseObserveRequest):
    adapter = get_computer_use_adapter()
    return await adapter.window_tree(**(body.model_dump() if hasattr(body, "model_dump") else body.dict()))


@router.post("/clustered-tree")
async def clustered_tree(body: ComputerUseObserveRequest):
    adapter = get_computer_use_adapter()
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    return await adapter.clustered_tree(
        process=payload.get("process", ""),
    )


@router.post("/ocr")
async def ocr(body: ComputerUseObserveRequest):
    adapter = get_computer_use_adapter()
    return await adapter.ocr_process(body.process)


@router.post("/click-index")
async def click_index(body: ComputerUseClickIndexRequest):
    adapter = get_computer_use_adapter()
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    return await adapter.click_index(**payload)


@router.post("/click-bounds")
async def click_bounds(body: ComputerUseClickBoundsRequest):
    adapter = get_computer_use_adapter()
    return await adapter.click_bounds(body.bounds, body.process)


@router.post("/verify")
async def verify(body: ComputerUseVerifyRequest):
    adapter = get_computer_use_adapter()
    return await adapter.verify_exists(body.selector, body.timeout_ms, body.scope_selector)


@router.post("/vision/start")
async def start_vision():
    health = await get_computer_use_adapter().health()
    return {"ok": bool(health.get("available")), "message": health.get("message", "")}


@router.post("/vision/parse")
async def parse_vision(body: ComputerUseVisionParseRequest):
    adapter = get_computer_use_adapter()
    if body.screenshot_path and not body.current_screen:
        return {"ok": False, "error": "请直接观察当前桌面", "elements": []}
    observation = await adapter.observe()
    return {
        "ok": observation.get("ok", False),
        "elements": observation.get("elements", []),
        "screenshot": observation.get("screenshot", {}),
        "summary": observation.get("summary", ""),
    }


@router.post("/tasks")
async def create_task(body: ComputerUseTaskRequest):
    kernel = get_execution_kernel()
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    run = kernel.create_computer_use_run(payload)
    return {"ok": True, "task_id": run["id"], "execution_id": run["id"], "run": run}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    kernel = get_execution_kernel()
    run = kernel.get_run(task_id)
    if not run or run.get("task_type") != "computer_use":
        raise HTTPException(404, "Computer-use task not found")
    return {
        **run,
        "steps": kernel.list_steps(task_id),
        "audit": kernel.list_audit(task_id),
        "observations": kernel.list_observations(task_id),
        "debug_screenshot": next(
            (
                item.get("artifact_path", "")
                for item in reversed(kernel.list_audit(task_id))
                if item.get("artifact_path")
            ),
            "",
        ),
    }
