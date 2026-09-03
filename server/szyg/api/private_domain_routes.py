"""Private-domain sales workspace routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from szyg.data_path import DATA_DIR
from szyg.wechat_desktop_calibration import calibration_summary, validate_calibration
from szyg.integrations.weixin4_bridge import get_weixin4_bridge

router = APIRouter(prefix="/api/private-domain", tags=["private-domain"])

_FOLLOWUPS_FILE = DATA_DIR / "private_domain_followups.json"
_MESSAGES_FILE = DATA_DIR / "messages.json"


class FollowupRequest(BaseModel):
    lead_id: str = ""
    customer_id: str = ""
    customer_name: str = ""
    platform: str = ""
    action: str = "followed"
    reply_text: str = ""
    next_reminder_at: str = ""
    notes: str = ""


class WechatDraftRequest(BaseModel):
    lead_id: str = ""
    customer_id: str = ""
    customer_name: str = ""
    message: str = Field(default="", min_length=1)
    source: str = "private_domain"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


async def _load_leads(limit: int = 50) -> list[dict]:
    from szyg.listen_engine import get_listen_engine

    leads = await get_listen_engine().list_leads(limit=limit)
    if leads:
        return leads

    conversions = _load_json(DATA_DIR / "conversions.json", [])
    return [
        {
            "lead_id": item.get("lead_id") or item.get("id"),
            "id": item.get("lead_id") or item.get("id"),
            "platform": item.get("platform", ""),
            "user_name": item.get("user_name", ""),
            "comment_text": item.get("comment_text", ""),
            "status": item.get("stage", "pending"),
            "grade": item.get("grade", ""),
            "updated_at": item.get("stage_updated_at") or item.get("created_at"),
        }
        for item in conversions[:limit]
    ]


def _wechat_status() -> dict:
    bridge = get_weixin4_bridge()
    window = bridge.status()
    calibration = calibration_summary()
    validation = validate_calibration()
    connected = bool(window.get("found"))
    calibrated = bool(validation.get("ok"))
    if calibrated:
        state = "calibrated"
    elif connected:
        state = "connected"
    else:
        state = "not_connected"
    return {
        "state": state,
        "connected": connected,
        "calibrated": calibrated,
        "label": {
            "calibrated": "输入区已识别",
            "connected": "微信已打开",
            "not_connected": "未连接",
        }[state],
        "window": window,
        "calibration": calibration,
        "validation": validation,
    }


def _lead_id(item: dict) -> str:
    return str(item.get("lead_id") or item.get("id") or "")


@router.get("/overview")
async def private_domain_overview():
    leads = await _load_leads(limit=200)
    followups = _load_json(_FOLLOWUPS_FILE, [])
    today = datetime.now(timezone.utc).astimezone().date()
    followed_today = [
        item for item in followups
        if str(item.get("created_at", ""))[:10] == today.isoformat()
    ]
    followed_leads = {str(item.get("lead_id")) for item in followups if item.get("lead_id")}
    pending = [item for item in leads if _lead_id(item) not in followed_leads and str(item.get("status", "")).lower() not in {"converted", "invalid", "done"}]
    high_intent = [
        item for item in pending
        if str(item.get("grade", "")).lower() in {"a", "s", "高", "high"} or int(item.get("lead_score") or item.get("score") or 0) >= 70
    ]
    return {
        "ok": True,
        "metrics": {
            "pending": len(pending),
            "high_intent": len(high_intent),
            "followed_today": len(followed_today),
            "overdue": 0,
        },
        "wechat": _wechat_status(),
    }


@router.get("/queue")
async def private_domain_queue(limit: int = 50):
    leads = await _load_leads(limit=limit)
    followups = _load_json(_FOLLOWUPS_FILE, [])
    followed_leads = {str(item.get("lead_id")) for item in followups if item.get("lead_id")}
    items = []
    for item in leads:
        enriched = dict(item)
        enriched["private_status"] = "followed" if _lead_id(item) in followed_leads else "pending"
        enriched["recommended_action"] = "优先微信跟进" if str(item.get("grade", "")).lower() in {"a", "s", "高", "high"} else "确认需求后跟进"
        items.append(enriched)
    return {"ok": True, "items": items, "total": len(items)}


@router.post("/followups")
async def create_private_domain_followup(req: FollowupRequest):
    item = {
        "id": uuid.uuid4().hex[:10],
        "lead_id": req.lead_id,
        "customer_id": req.customer_id,
        "customer_name": req.customer_name,
        "platform": req.platform,
        "action": req.action,
        "reply_text": req.reply_text,
        "next_reminder_at": req.next_reminder_at,
        "notes": req.notes,
        "created_at": _now(),
    }
    followups = _load_json(_FOLLOWUPS_FILE, [])
    followups.insert(0, item)
    _save_json(_FOLLOWUPS_FILE, followups[:1000])

    if req.lead_id:
        try:
            from szyg.listen_engine import get_listen_engine
            await get_listen_engine().update_lead(req.lead_id, status="followed", notes=req.notes or req.reply_text)
        except Exception:
            pass
        try:
            from szyg.convert_engine import get_convert_engine
            await get_convert_engine().track_stage(
                req.lead_id,
                req.platform or "wechat",
                "replied",
                user_name=req.customer_name,
                reply_text=req.reply_text,
            )
        except Exception:
            pass

    return {"ok": True, "followup": item}


@router.post("/wechat/draft")
async def create_wechat_draft(req: WechatDraftRequest):
    status = _wechat_status()
    if not status["calibrated"]:
        raise HTTPException(status_code=400, detail="请先识别微信输入区")

    messages = _load_json(_MESSAGES_FILE, [])
    item = {
        "id": uuid.uuid4().hex[:10],
        "customer_id": req.customer_id or req.lead_id or "private_domain",
        "lead_id": req.lead_id,
        "sender": "assistant",
        "text": req.message,
        "status": "draft_ready",
        "source": req.source,
        "time": datetime.now().strftime("%H:%M"),
        "created_at": _now(),
    }
    messages.insert(0, item)
    _save_json(_MESSAGES_FILE, messages[:2000])
    return {
        "ok": True,
        "draft": item,
        "wechat": status,
        "message": "已生成微信草稿记录，请人工确认后发送",
    }
