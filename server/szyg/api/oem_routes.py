"""OEM branding API — logo, copyright, theme, multi-tenant config"""
import json, os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from szyg.api.auth_routes import optional_user, require_admin
from szyg.auth import User

router = APIRouter(prefix="/api/oem", tags=["oem"])

from szyg.data_path import DATA_DIR
OEM_FILE = DATA_DIR / "oem.json"

DEFAULT_CONFIG = {
    "name": "智能矩阵运营系统",
    "logo_url": "",
    "copyright": "© 2024 szyg — 自托管AI工具平台",
    "disclaimer": "本平台仅供学习和研究使用，禁止用于非法用途。",
    "theme": "default",
    "oem_id": "default",
    "support_name": "客服咨询",
    "support_url": "",
    "website_name": "官方网站",
    "website_url": "",
}


class OEMConfig(BaseModel):
    name: str = "szyg"
    logo_url: str = ""
    copyright: str = ""
    disclaimer: str = ""
    theme: str = "default"
    oem_id: str = "default"
    support_name: str = "客服咨询"
    support_url: str = ""
    website_name: str = "官方网站"
    website_url: str = ""


def _read_oem() -> dict:
    if OEM_FILE.exists():
        return json.loads(OEM_FILE.read_text(encoding='utf-8'))
    OEM_FILE.parent.mkdir(parents=True, exist_ok=True)
    OEM_FILE.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(DEFAULT_CONFIG)


@router.get("/config/{oem_id}", response_model=OEMConfig)
async def get_oem_config(oem_id: str = "default"):
    config = _read_oem()
    config["oem_id"] = oem_id
    return OEMConfig(**config)


@router.post("/config")
async def update_oem_config(data: OEMConfig, admin: User = Depends(require_admin)):
    OEM_FILE.parent.mkdir(parents=True, exist_ok=True)
    OEM_FILE.write_text(data.model_dump_json(indent=2), encoding="utf-8")
    return {"ok": True}
