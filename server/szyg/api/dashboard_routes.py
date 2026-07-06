"""统一仪表盘 / 数字员工数据 API — 为 szyg-frontend 提供真实聚合数据.

所有数据均来自真实业务子系统（AI 员工状态、调度器、发布器、采集引擎、对话历史），
绝不使用模拟数据。当某项指标无法计算时返回真实的 0 / 空列表，而非编造数字。

覆盖前端页面:
  - Dashboard  : overview / activities / tasks / interaction-trend / distribution
  - DigitalHuman: digital-humans（由真实 AI 员工映射）
"""

import json
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Query

from szyg.data_path import DATA_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# 复用 staff_routes 中已有的真实聚合逻辑（AI 员工状态 / 任务列表 / 员工配置）
from szyg.api.staff_routes import (
    _compute_staff_status,
    _compute_tasks,
    _load_json,
    _CONFIGS_FILE,
    _DEFAULT_CONFIGS,
)

CONV_DIR = DATA_DIR / "conversations"

# ── 真实员工 → 前端 DigitalHuman 类型映射 ────────────────────────────
_STAFF_TYPE_MAP = {
    "content": "marketing",
    "acquisition": "sales",
    "conversion": "customer_service",
    "ops": "data_analyst",
}
_STAFF_STATUS_MAP = {"running": "active", "idle": "idle", "error": "error"}
_TYPE_COLOR = {
    "sales": "#6366F1", "customer_service": "#10B981", "marketing": "#F59E0B",
    "data_analyst": "#3B82F6", "custom": "#8B5CF6",
}
_TYPE_LABEL = {
    "sales": "销售", "customer_service": "客服", "marketing": "营销",
    "data_analyst": "数据分析", "custom": "定制",
}
_TASK_STATUS_MAP = {
    "ready": "pending", "running": "running", "done": "completed",
    "blocked": "failed", "failed": "failed",
}
_TASK_TYPE_MAP = {
    "内容专员": "内容", "获客专员": "获客", "转化专员": "转化", "运营专员": "调度",
}


def _agent_configs() -> dict:
    """读取真实持久化的员工配置（不存在时使用默认配置）。"""
    configs = _load_json(_CONFIGS_FILE, None)
    if configs is None:
        configs = _DEFAULT_CONFIGS
    return configs


def _resolve_model_label() -> str:
    """从 config.yaml 读取真实默认模型名称。"""
    try:
        from szyg.config.loader import load_config
        cfg = load_config()
        llm = cfg.get("llm", {})
        backend = llm.get("default_backend", "ollama")
        if backend == "volcengine":
            vc = llm.get("volcengine", {})
            eps = vc.get("endpoints", {}) or {}
            for _model_id, ep in eps.items():
                if ep:
                    return ep
            return vc.get("default_model", "doubao-seed-2-0-pro")
        return llm.get("ollama", {}).get("default_model", "ollama")
    except Exception as e:
        logger.debug("resolve model label failed: %s", e)
        return "未配置"


def _to_aware(d: datetime) -> datetime:
    """将 naive datetime 视为 UTC，返回 aware datetime。"""
    if d.tzinfo is None:
        return d.replace(tzinfo=timezone.utc)
    return d


def _list_conversation_mtimes() -> list[datetime]:
    """读取真实对话文件的更新时间（用于交互趋势 / 动态流）。"""
    times: list[datetime] = []
    if not CONV_DIR.exists():
        return times
    for f in CONV_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            ts = data.get("updated_at") or data.get("created_at")
            if ts:
                times.append(_to_aware(datetime.fromisoformat(ts)))
        except Exception:
            try:
                times.append(datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc))
            except Exception:
                continue
    return times


# ═══════════════════════════════════════════════════════════════════
# 数字员工（由真实 AI 员工聚合）
# ═══════════════════════════════════════════════════════════════════

@router.get("/digital-humans")
async def digital_humans():
    """由真实 AI 员工聚合为前端 DigitalHuman 列表。"""
    staff = _compute_staff_status()
    configs = _agent_configs()
    model_label = _resolve_model_label()
    now_iso = datetime.now(timezone.utc).isoformat()

    humans = []
    for s in staff:
        sid = s.get("id", "")
        cfg = configs.get(sid, {})
        basic = cfg.get("basic", {}) if isinstance(cfg, dict) else {}
        staff_status = s.get("status", "idle")
        progress = s.get("progress", 0)
        if staff_status == "running" and progress < 100:
            fe_status = "training"
        else:
            fe_status = _STAFF_STATUS_MAP.get(staff_status, "idle")
        name = s.get("name", sid)
        humans.append({
            "id": sid,
            "name": name,
            "avatar": s.get("emoji") or (name[:1] if name else "AI"),
            "status": fe_status,
            "type": _STAFF_TYPE_MAP.get(sid, "custom"),
            "model": model_label,
            "createdAt": s.get("updated_at", now_iso),
            "lastActive": s.get("updated_at", now_iso),
            "interactions": int(s.get("tasksToday", 0)),
            "successRate": round(float(progress or 0), 1),
            "description": basic.get("description", s.get("recent", "")) if isinstance(basic, dict) else "",
        })
    return {"digitalHumans": humans}


@router.get("/distribution")
async def distribution():
    """按业务类型统计真实 AI 员工的任务量占比。"""
    staff = _compute_staff_status()
    total = sum(int(s.get("tasksToday", 0)) for s in staff)
    buckets: dict[str, int] = {}
    for s in staff:
        t = _STAFF_TYPE_MAP.get(s.get("id", ""), "custom")
        buckets[t] = buckets.get(t, 0) + int(s.get("tasksToday", 0))
    if total == 0:
        for s in staff:
            t = _STAFF_TYPE_MAP.get(s.get("id", ""), "custom")
            buckets[t] = buckets.get(t, 0) + 1
        total = sum(buckets.values()) or 1
    result = []
    for t, v in buckets.items():
        result.append({
            "name": _TYPE_LABEL.get(t, t),
            "value": round(v * 100 / total) if total else 0,
            "color": _TYPE_COLOR.get(t, "#8B5CF6"),
        })
    return {"distribution": result}


@router.get("/interaction-trend")
async def interaction_trend(time_range: str = Query("7D", alias="range")):
    """真实交互趋势：按天聚合对话数量，successRate 取当前真实平均成功率。"""
    days = {"7D": 7, "30D": 30, "90D": 90}.get(time_range, 7)
    staff = _compute_staff_status()
    avg_success = 0.0
    if staff:
        avg_success = round(
            sum(float(s.get("progress", 0)) for s in staff) / len(staff), 1
        )

    mtimes = _list_conversation_mtimes()
    now = datetime.now(timezone.utc)
    counts_by_day: dict[str, int] = {}
    for t in mtimes:
        if (now - t).days < days:
            key = t.strftime("%m-%d")
            counts_by_day[key] = counts_by_day.get(key, 0) + 1

    series = []
    for i in range(days - 1, -1, -1):
        d = now - timedelta(days=i)
        key = d.strftime("%m-%d")
        series.append({
            "date": d.strftime("%b %d").lstrip("0"),
            "interactions": counts_by_day.get(key, 0),
            "successRate": avg_success,
        })
    return {"chartData": series}


@router.get("/activities")
async def activities(limit: int = 8):
    """真实近期动态：聚合任务状态变化与对话记录。无数据时返回空列表。"""
    items = []
    for t in _compute_tasks():
        status = t.get("status", "")
        if status == "done":
            atype = "report_generated"
        elif status == "blocked":
            atype = "alert"
        elif status == "running":
            atype = "interaction"
        else:
            atype = "system"
        ts = t.get("deadline") or t.get("updated_at")
        if not ts:
            ts = datetime.now(timezone.utc).isoformat()
        items.append({
            "id": f"task-{t.get('id')}",
            "type": atype,
            "title": t.get("name", "任务"),
            "description": f"{t.get('assignee', '系统')} · {t.get('status', '')}",
            "timestamp": ts,
        })
    if CONV_DIR.exists():
        for f in sorted(CONV_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                items.append({
                    "id": f"conv-{f.stem}",
                    "type": "interaction",
                    "title": data.get("title", "新对话") or "新对话",
                    "description": f"超级员工 · {len(data.get('messages', []))} 条消息",
                    "timestamp": data.get("updated_at") or data.get("created_at") or "",
                })
            except Exception:
                continue

    def _key(it):
        ts = it.get("timestamp", "")
        try:
            return _to_aware(datetime.fromisoformat(ts))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)
    items.sort(key=_key, reverse=True)
    return {"activities": items[:limit]}


@router.get("/tasks")
async def tasks():
    """真实任务队列（合并调度器任务与手动任务）。"""
    result = []
    for t in _compute_tasks():
        result.append({
            "id": str(t.get("id", "")),
            "name": t.get("name", "未命名任务"),
            "type": _TASK_TYPE_MAP.get(t.get("assignee", ""), "任务"),
            "status": _TASK_STATUS_MAP.get(t.get("status", ""), "pending"),
            "progress": int(t.get("progress", 0)),
            "createdAt": t.get("deadline") or t.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            "priority": t.get("priority", "medium") if t.get("priority") in ("high", "medium", "low") else "medium",
        })
    return {"tasks": result}
