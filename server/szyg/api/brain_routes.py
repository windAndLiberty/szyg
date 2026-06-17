"""Brain API — Hermes Agent status and control"""
from fastapi import APIRouter
from szyg.brain_hermes import get_brain

router = APIRouter(prefix="/api/brain", tags=["brain"])

@router.get("/status")
async def brain_status():
    return get_brain().get_status()

@router.get("/prompt")
async def brain_prompt():
    return {"prompt": get_brain().get_system_prompt()}

@router.get("/mcp")
async def brain_mcp():
    return get_brain().get_mcp_servers()
