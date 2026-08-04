"""Client-side API — local AI engines and runtime"""
from fastapi import APIRouter
from szyg.client import LocalAI, ClientStatus, get_runtime

router = APIRouter(prefix="/api/client", tags=["client"])


@router.get("/status")
async def client_status():
    """Check local AI engines and capabilities"""
    return ClientStatus.get_all()


@router.get("/ollama/models")
async def ollama_models():
    """List local Ollama models"""
    if not LocalAI.is_ollama_running():
        return {"error": "Ollama not running", "models": []}
    models = await LocalAI.ollama_models()
    return {"models": models}


@router.post("/ollama/chat")
async def ollama_chat(prompt: str, model: str = "qwen3", system: str = ""):
    """Chat with local Ollama model"""
    if not LocalAI.is_ollama_running():
        return {"error": "Ollama not running"}
    result = await LocalAI.ollama_chat(prompt, model, system)
    return {"response": result}


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
