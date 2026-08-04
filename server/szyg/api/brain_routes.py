"""Compatibility status endpoints for the isolated intelligent runtime."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from szyg.hermes_capabilities import get_hermes_capability_registry
from szyg.hermes_process_manager import hermes_process_manager


router = APIRouter(prefix="/api/brain", tags=["brain"])


@router.get("/status")
async def brain_status():
    try:
        await asyncio.to_thread(hermes_process_manager.ensure_started)
        healthy = True
    except Exception:
        healthy = False
    capabilities = get_hermes_capability_registry().list()
    return {
        "engine": "super-agent",
        "version": "1.1.0",
        "available": healthy,
        "business_capabilities": {
            "count": len(capabilities),
            "domains": sorted({item.get("domain", "") for item in capabilities if item.get("domain")}),
        },
    }


@router.get("/prompt")
async def brain_prompt():
    return {"prompt": "领鹿员工会结合已授权能力理解目标、执行任务并给出可核验结果。"}


@router.get("/mcp")
async def brain_mcp():
    return {"configured": True, "runtime": "isolated", "servers": []}
