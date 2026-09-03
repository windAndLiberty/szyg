"""Tool marketplace API — catalog, install, search, launch"""
import json, os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from szyg.auth import User
from szyg.api.auth_routes import optional_user
from szyg.tool_runtime import get_runtime

router = APIRouter(prefix="/api/tools", tags=["tools"])

from szyg.data_path import DATA_DIR
TOOLS_FILE = DATA_DIR / "tools.json"
INSTALL_FILE = DATA_DIR / "install.json"


class ToolInfo(BaseModel):
    id: str
    soft_code: str
    title: str
    desc: str = ""
    icon: str = ""
    version: str = "1.0"
    category: str = "general"
    is_yun: bool = False
    dw_url: str | None = None
    soft_jc: str | None = None  # tutorial URL
    isfree: bool = True
    windows_canshu: str | None = None  # cloud tool window params


class InstallInfo(BaseModel):
    soft_id: str
    soft_code: str
    version: str
    file_path: str


def _read_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return default

def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


@router.get("/catalog", response_model=list[ToolInfo])
async def catalog(category: str | None = None, search: str | None = None):
    tools = _read_json(TOOLS_FILE, [])
    if category:
        tools = [t for t in tools if t.get("category") == category]
    if search:
        q = search.lower()
        tools = [t for t in tools if q in t.get("title", "").lower() or q in t.get("desc", "").lower()]
    return [ToolInfo(**t) for t in tools]


@router.get("/installed", response_model=list[InstallInfo])
async def installed():
    return [InstallInfo(**i) for i in _read_json(INSTALL_FILE, [])]


@router.post("/install")
async def install_tool(soft_id: str, soft_code: str, version: str, file_path: str):
    """Record a tool as installed"""
    installed = _read_json(INSTALL_FILE, [])
    installed = [i for i in installed if i.get("soft_id") != soft_id]
    installed.append({"soft_id": soft_id, "soft_code": soft_code, "version": version, "file_path": file_path})
    _write_json(INSTALL_FILE, installed)
    return {"ok": True}


@router.delete("/uninstall/{soft_id}")
async def uninstall_tool(soft_id: str):
    installed = _read_json(INSTALL_FILE, [])
    installed = [i for i in installed if i.get("soft_id") != soft_id]
    _write_json(INSTALL_FILE, installed)
    return {"ok": True}


@router.get("/categories")
async def categories():
    tools = _read_json(TOOLS_FILE, [])
    return list(set(t.get("category", "general") for t in tools))


@router.post("/launch/{soft_id}")
async def launch_tool(soft_id: str):
    """Launch an installed tool by soft_id"""
    runtime = get_runtime()
    try:
        proc = runtime.launch(soft_id)
        if proc is None:
            raise HTTPException(404, "工具未安装")
        return {"ok": True, "pid": proc.pid}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/stop/{soft_id}")
async def stop_tool(soft_id: str):
    runtime = get_runtime()
    if runtime.stop(soft_id):
        return {"ok": True}
    raise HTTPException(404, "工具未运行")


@router.get("/stats")
async def tool_stats():
    runtime = get_runtime()
    tools = _read_json(TOOLS_FILE, [])
    installed = _read_json(INSTALL_FILE, [])
    return {
        "tools_total": len(tools),
        "tools_installed": len(installed),
        "tools_running": len(runtime._processes),
    }
