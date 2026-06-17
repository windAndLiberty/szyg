"""Client-side API — local runtime and status"""
from fastapi import APIRouter
from szyg.client import ClientStatus, get_runtime

router = APIRouter(prefix="/api/client", tags=["client"])


@router.get("/status")
async def client_status():
    """Check client capabilities and runtime status"""
    return ClientStatus.get_all()


@router.get("/runtime")
async def runtime_list():
    """List running local processes"""
    return {"running": get_runtime().list_running()}


@router.post("/runtime/launch")
async def runtime_launch(exe_path: str, cwd: str = ""):
    """Launch a local executable"""
    try:
        proc = get_runtime().launch(exe_path, cwd)
        return {"ok": True, "pid": proc.pid}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/runtime/stop")
async def runtime_stop(exe_path: str):
    """Stop a running local process"""
    get_runtime().stop(exe_path)
    return {"ok": True}
