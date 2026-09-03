"""System announcements & update log API"""
import json, os, uuid
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from szyg.auth import User
from szyg.api.auth_routes import require_admin

router = APIRouter(prefix="/api/announce", tags=["announce"])

from szyg.data_path import DATA_DIR
ANNOUNCE_FILE = DATA_DIR / "announcements.json"


class Announcement(BaseModel):
    id: str
    title: str
    content: str
    level: str = "info"  # info | warning | success | error
    is_pinned: bool = False
    created_at: str = ""
    expires_at: str = ""


def _read() -> list[dict]:
    if ANNOUNCE_FILE.exists():
        return json.loads(ANNOUNCE_FILE.read_text(encoding='utf-8'))
    return []

def _write(data: list[dict]):
    ANNOUNCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ANNOUNCE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/list", response_model=list[Announcement])
async def list_announcements(limit: int = 10):
    """Get active announcements (not expired), newest first"""
    now = datetime.now().isoformat()
    items = _read()
    active = []
    for a in items:
        if a.get("expires_at") and a["expires_at"] < now:
            continue
        active.append(a)
    # Pinned first, then by date
    active.sort(key=lambda x: (not x.get("is_pinned"), x.get("created_at", "")), reverse=False)
    # Actually: pinned first, then newest first
    pinned = [a for a in active if a.get("is_pinned")]
    unpinned = [a for a in active if not a.get("is_pinned")]
    unpinned.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    result = pinned + unpinned
    return [Announcement(**a) for a in result[:limit]]


@router.post("/create", response_model=Announcement)
async def create_announcement(
    title: str, content: str, level: str = "info",
    is_pinned: bool = False, expires_days: int = 30,
    admin: User = Depends(require_admin),
):
    """Admin: create an announcement"""
    items = _read()
    a = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "content": content,
        "level": level,
        "is_pinned": is_pinned,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now().isoformat() if expires_days == 0 else ""),
    }
    if expires_days > 0:
        from datetime import timedelta
        a["expires_at"] = (datetime.now() + timedelta(days=expires_days)).isoformat()
    items.append(a)
    _write(items)
    return Announcement(**a)


@router.delete("/{announce_id}")
async def delete_announcement(announce_id: str, admin: User = Depends(require_admin)):
    items = _read()
    items = [a for a in items if a.get("id") != announce_id]
    _write(items)
    return {"ok": True}
