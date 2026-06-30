"""Risk control configuration API — exposes anti-detect settings to the frontend."""

import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

router = APIRouter(prefix="/api/risk-control", tags=["risk-control"])

_CONFIG_PATH = Path(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "data",
        "risk_control_config.json",
    )
)

_DEFAULT_CONFIG = {
    "behavior": {
        "clickInterval": 3,
        "mouseRandomness": 60,
        "browseStay": 15,
        "intervalJitter": 30,
    },
    "limits": {
        "dailyPublish": 10,
        "dailyComment": 50,
        "dailyDM": 30,
        "dailyAddFriend": 20,
        "smartStagger": True,
    },
    "nurture": {
        "timeRange": None,
        "likeProbability": 50,
        "commentProbability": 20,
        "browseCount": 200,
    },
    "content": {
        "complianceCheck": True,
        "sensitiveFilter": True,
        "sensitiveWords": "",
        "hardAdDetect": True,
    },
}


def _load_config() -> dict:
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return _DEFAULT_CONFIG.copy()


def _save_config(cfg: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class RiskControlConfig(BaseModel):
    behavior: Optional[dict] = None
    limits: Optional[dict] = None
    nurture: Optional[dict] = None
    content: Optional[dict] = None


@router.get("/config")
async def get_risk_control_config():
    """Get current risk control configuration."""
    return _load_config()


@router.put("/config")
async def update_risk_control_config(body: RiskControlConfig):
    """Update risk control configuration."""
    current = _load_config()
    if body.behavior is not None:
        current["behavior"] = {**current.get("behavior", {}), **body.behavior}
    if body.limits is not None:
        current["limits"] = {**current.get("limits", {}), **body.limits}
    if body.nurture is not None:
        current["nurture"] = {**current.get("nurture", {}), **body.nurture}
    if body.content is not None:
        current["content"] = {**current.get("content", {}), **body.content}
    _save_config(current)
    return {"ok": True, "config": current}
