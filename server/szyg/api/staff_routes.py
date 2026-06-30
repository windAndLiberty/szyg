"""AI Staff API — 员工状态、任务管理、配置持久化.

员工状态和任务数据从真实业务子系统动态聚合：
  - 调度器 (scheduler_engine) → 任务计数
  - 发布器 (publisher) → 内容计数
  - 采集引擎 (listen_engine, convert_engine) → 线索/转化计数
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/staff", tags=["ai-staff"])

# ── 数据存储 ──────────────────────────────────────────────────────
_DATA_DIR = Path(os.environ.get("SZYG_DATA_DIR", "data")) / "staff"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_STAFF_FILE = _DATA_DIR / "staff_status.json"
_TASKS_FILE = _DATA_DIR / "tasks.json"
_CONFIGS_FILE = _DATA_DIR / "agent_configs.json"


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Dynamic data aggregation helpers ──────────────────────────────

def _get_scheduler_stats() -> dict:
    """Get real scheduler stats (active/completed/failed job counts)."""
    try:
        from szyg.scheduler_engine import get_scheduler
        scheduler = get_scheduler()
        return scheduler.get_stats()
    except Exception:
        return {"active": 0, "completed": 0, "paused": 0, "failed": 0, "total_jobs": 0}


def _get_publisher_stats() -> dict:
    """Get real publisher stats (drafts/published/pending counts)."""
    try:
        from szyg.publisher import get_publisher
        pub = get_publisher()
        return pub.get_stats()
    except Exception:
        return {"drafts": 0, "published": 0, "pending_review": 0, "total": 0}


def _get_acquisition_stats() -> dict:
    """Get real acquisition stats (leads/customers/conversions)."""
    try:
        from szyg.listen_engine import get_listen_engine
        from szyg.convert_engine import get_convert_engine
        listen = get_listen_engine()
        convert = get_convert_engine()
        leads = getattr(listen, 'leads', [])
        conversions = getattr(convert, '_conversions', [])
        customers = getattr(listen, 'customers', [])
        return {
            "total_leads": len(leads) if leads else 0,
            "total_conversions": len(conversions) if conversions else 0,
            "total_customers": len(customers) if customers else 0,
        }
    except Exception:
        return {"total_leads": 0, "total_conversions": 0, "total_customers": 0}


def _compute_staff_status() -> list[dict]:
    """Compute staff status from real subsystem data."""
    sched = _get_scheduler_stats()
    pub = _get_publisher_stats()
    acq = _get_acquisition_stats()
    now = datetime.now(timezone.utc).isoformat()

    def _pct(done, total):
        return min(100, round((done / total) * 100)) if total > 0 else 0

    return [
        {
            "id": "content",
            "name": "内容专员",
            "emoji": "📝",
            "color": "#00d4ff",
            "status": "running" if pub.get("pending_review", 0) > 0 or pub.get("drafts", 0) > 0 else "idle",
            "tasksToday": pub.get("total", 0),
            "completed": pub.get("published", 0),
            "progress": _pct(pub.get("published", 0), max(pub.get("total", 0), 1)),
            "recent": f"发布: {pub.get('published', 0)}篇, 待审: {pub.get('pending_review', 0)}篇",
            "skills": ["文案生成", "AIGC图像", "视频脚本", "多平台适配"],
            "route": "/content/production",
            "updated_at": now,
        },
        {
            "id": "acquisition",
            "name": "获客专员",
            "emoji": "🎯",
            "color": "#a855f7",
            "status": "running" if acq.get("total_leads", 0) > 0 else "idle",
            "tasksToday": acq.get("total_leads", 0),
            "completed": acq.get("total_conversions", 0),
            "progress": _pct(acq.get("total_conversions", 0), max(acq.get("total_leads", 0), 1)),
            "recent": f"线索: {acq.get('total_leads', 0)}条, 转化: {acq.get('total_conversions', 0)}单",
            "skills": ["搜索截流", "评论生成", "DeAI处理", "线索评分"],
            "route": "/marketing/intercept",
            "updated_at": now,
        },
        {
            "id": "conversion",
            "name": "转化专员",
            "emoji": "💰",
            "color": "#22c55e",
            "status": "running" if acq.get("total_customers", 0) > 0 else "idle",
            "tasksToday": acq.get("total_customers", 0),
            "completed": acq.get("total_conversions", 0),
            "progress": _pct(acq.get("total_conversions", 0), max(acq.get("total_leads", 0), 1)),
            "recent": f"客户: {acq.get('total_customers', 0)}位, 转化: {acq.get('total_conversions', 0)}单",
            "skills": ["线索管理", "SOP执行", "微信桥接", "知识库检索"],
            "route": "/marketing/conversion",
            "updated_at": now,
        },
        {
            "id": "ops",
            "name": "运营专员",
            "emoji": "🚀",
            "color": "#fbbf24",
            "status": "running" if sched.get("active", 0) > 0 else "idle",
            "tasksToday": sched.get("total_jobs", 0),
            "completed": sched.get("completed", 0),
            "progress": _pct(sched.get("completed", 0), max(sched.get("total_jobs", 0), 1)),
            "recent": f"调度: {sched.get('active', 0)}活跃, {sched.get('completed', 0)}完成",
            "skills": ["调度引擎", "A/B测试", "数据报告", "审计日志"],
            "route": "/workflow/scheduler",
            "updated_at": now,
        },
    ]


def _compute_tasks() -> list[dict]:
    """Merge scheduler jobs with manual tasks to produce unified task list."""
    tasks = []

    # 1) Load scheduler jobs as tasks
    try:
        from szyg.scheduler_engine import get_scheduler
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs() if hasattr(scheduler, 'list_jobs') else []
        if not jobs and hasattr(scheduler, '_jobs'):
            jobs = list(scheduler._jobs.values())
        status_map = {"active": "running", "paused": "blocked", "completed": "done", "failed": "blocked"}
        next_id = 1
        for j in jobs:
            jstatus = getattr(j, 'status', 'active')
            if hasattr(jstatus, 'value'):
                jstatus = jstatus.value
            tasks.append({
                "id": next_id,
                "name": getattr(j, 'name', '未命名任务') if hasattr(j, 'name') else str(j),
                "assignee": "运营专员",
                "status": status_map.get(str(jstatus), "ready"),
                "priority": "medium",
                "progress": 50 if str(jstatus) == "active" else (100 if str(jstatus) == "completed" else 0),
                "deadline": getattr(j, 'next_run_at', '') or '',
                "reviewStatus": None,
                "reviewComment": "",
                "reviewTime": "",
                "source": "scheduler",
            })
            next_id += 1
    except Exception:
        pass

    # 2) Merge manual tasks from JSON file (skip ones already covered by scheduler)
    manual_tasks = _load_json(_TASKS_FILE, [])
    existing_names = {t.get("name", "") for t in tasks}
    for mt in manual_tasks:
        if mt.get("name", "") not in existing_names:
            tasks.append(mt)

    return tasks


# ── 默认员工数据 ──────────────────────────────────────────────────
_DEFAULT_STAFF = [
    {
        "id": "content",
        "name": "内容专员",
        "emoji": "📝",
        "color": "#00d4ff",
        "status": "running",
        "tasksToday": 8,
        "completed": 12,
        "progress": 75,
        "recent": "刚完成：小红书文案发布",
        "skills": ["文案生成", "AIGC图像", "视频脚本", "多平台适配"],
        "route": "/content/production",
    },
    {
        "id": "acquisition",
        "name": "获客专员",
        "emoji": "🎯",
        "color": "#a855f7",
        "status": "running",
        "tasksToday": 5,
        "completed": 8,
        "progress": 60,
        "recent": "刚完成：抖音关键词搜索",
        "skills": ["搜索截流", "评论生成", "DeAI处理", "线索评分"],
        "route": "/marketing/intercept",
    },
    {
        "id": "conversion",
        "name": "转化专员",
        "emoji": "💰",
        "color": "#22c55e",
        "status": "idle",
        "tasksToday": 3,
        "completed": 3,
        "progress": 30,
        "recent": "刚完成：客户跟进记录",
        "skills": ["线索管理", "SOP执行", "微信桥接", "知识库检索"],
        "route": "/marketing/conversion",
    },
    {
        "id": "ops",
        "name": "运营专员",
        "emoji": "🚀",
        "color": "#fbbf24",
        "status": "running",
        "tasksToday": 6,
        "completed": 5,
        "progress": 45,
        "recent": "刚完成：定时任务调度",
        "skills": ["调度引擎", "A/B测试", "数据报告", "审计日志"],
        "route": "/workflow/scheduler",
    },
]

_DEFAULT_TASKS = [
    {"id": 1, "name": "制作抖音短视频 #1", "assignee": "内容专员", "status": "ready", "priority": "high", "progress": 0, "deadline": str(datetime.now().strftime("%Y-%m-%d")), "reviewStatus": None, "reviewComment": "", "reviewTime": ""},
    {"id": 2, "name": "撰写小红书文案", "assignee": "内容专员", "status": "ready", "priority": "medium", "progress": 0, "deadline": str(datetime.now().strftime("%Y-%m-%d")), "reviewStatus": None, "reviewComment": "", "reviewTime": ""},
    {"id": 3, "name": "自动回复私信处理", "assignee": "获客专员", "status": "running", "priority": "high", "progress": 65, "deadline": str(datetime.now().strftime("%Y-%m-%d")), "reviewStatus": None, "reviewComment": "", "reviewTime": ""},
    {"id": 4, "name": "朋友圈内容发布", "assignee": "运营专员", "status": "running", "priority": "medium", "progress": 30, "deadline": str(datetime.now().strftime("%Y-%m-%d")), "reviewStatus": None, "reviewComment": "", "reviewTime": ""},
    {"id": 5, "name": "客户跟进电话", "assignee": "转化专员", "status": "blocked", "priority": "high", "progress": 20, "deadline": str(datetime.now().strftime("%Y-%m-%d")), "reviewStatus": None, "reviewComment": "", "reviewTime": ""},
    {"id": 6, "name": "晨间数据报表生成", "assignee": "运营专员", "status": "done", "priority": "low", "progress": 100, "deadline": str(datetime.now().strftime("%Y-%m-%d")), "reviewStatus": None, "reviewComment": "", "reviewTime": ""},
]

_DEFAULT_CONFIGS = {
    "content": {
        "basic": {"name": "内容专员", "description": "负责内容创作、文案撰写、脚本生成", "avatar": "📝", "enabled": True},
        "soul": {"systemPrompt": "你是一位专业的内容创作专员，擅长短视频脚本、社交媒体文案和品牌内容输出。请确保内容符合品牌调性，语言生动有趣。", "behaviorMode": "balanced", "temperature": 0.8},
        "memory": {"shortTermDepth": 10, "longTermEnabled": True, "knowledgeBases": ["product", "brand"]},
        "skills": {"list": [
            {"id": "script", "name": "脚本生成", "description": "自动生成短视频脚本", "enabled": True, "priority": 1},
            {"id": "copy", "name": "文案撰写", "description": "撰写社交媒体文案", "enabled": True, "priority": 2},
            {"id": "adapt", "name": "多平台适配", "description": "适配不同平台内容格式", "enabled": True, "priority": 3},
            {"id": "aigc", "name": "AIGC图像", "description": "生成配图和封面", "enabled": False, "priority": 4},
        ]}
    },
    "acquisition": {
        "basic": {"name": "获客专员", "description": "负责公域拓客、搜索截流、评论互动", "avatar": "🎯", "enabled": True},
        "soul": {"systemPrompt": "你是一位精准的获客专员，擅长通过关键词搜索、评论互动和截流策略获取高意向客户。行为要自然，避免过度营销。", "behaviorMode": "fast", "temperature": 0.9},
        "memory": {"shortTermDepth": 15, "longTermEnabled": True, "knowledgeBases": ["sales", "competitor"]},
        "skills": {"list": [
            {"id": "search", "name": "搜索截流", "description": "关键词搜索与线索截流", "enabled": True, "priority": 1},
            {"id": "comment", "name": "评论生成", "description": "自动生成互动评论", "enabled": True, "priority": 2},
            {"id": "deai", "name": "DeAI处理", "description": "智能线索评分", "enabled": True, "priority": 3},
            {"id": "reply", "name": "自动回复", "description": "私信自动接待", "enabled": False, "priority": 4},
        ]}
    },
    "conversion": {
        "basic": {"name": "转化专员", "description": "负责私域转化、客户跟进、成交推进", "avatar": "💰", "enabled": True},
        "soul": {"systemPrompt": "你是一位专业的销售转化专员，擅长客户跟进、需求挖掘和成交推进。请以客户为中心，提供个性化解决方案。", "behaviorMode": "cautious", "temperature": 0.6},
        "memory": {"shortTermDepth": 20, "longTermEnabled": True, "knowledgeBases": ["sales", "product"]},
        "skills": {"list": [
            {"id": "lead", "name": "线索管理", "description": "管理和跟进销售线索", "enabled": True, "priority": 1},
            {"id": "sop", "name": "SOP执行", "description": "执行标准销售流程", "enabled": True, "priority": 2},
            {"id": "bridge", "name": "微信桥接", "description": "私域客户桥接管理", "enabled": True, "priority": 3},
            {"id": "knowledge", "name": "知识库检索", "description": "检索产品知识库", "enabled": False, "priority": 4},
        ]}
    },
    "ops": {
        "basic": {"name": "运营专员", "description": "负责调度引擎、数据报告、审计日志", "avatar": "🚀", "enabled": True},
        "soul": {"systemPrompt": "你是一位运营调度专员，负责协调各 AI 员工的工作流、生成数据报告并监控系统运行状态。请确保调度高效、数据准确。", "behaviorMode": "balanced", "temperature": 0.7},
        "memory": {"shortTermDepth": 8, "longTermEnabled": False, "knowledgeBases": ["product"]},
        "skills": {"list": [
            {"id": "scheduler", "name": "调度引擎", "description": "任务调度与定时执行", "enabled": True, "priority": 1},
            {"id": "abtest", "name": "A/B测试", "description": "策略对比测试", "enabled": True, "priority": 2},
            {"id": "report", "name": "数据报告", "description": "自动生成运营报告", "enabled": True, "priority": 3},
            {"id": "audit", "name": "审计日志", "description": "操作日志记录与分析", "enabled": False, "priority": 4},
        ]}
    },
}


# ── Pydantic Models ───────────────────────────────────────────────

class TaskCreate(BaseModel):
    name: str
    assignee: str
    priority: str = "medium"
    deadline: str = ""

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    assignee: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    progress: Optional[int] = None
    deadline: Optional[str] = None
    reviewStatus: Optional[str] = None
    reviewComment: Optional[str] = None
    reviewTime: Optional[str] = None

class AgentConfigUpdate(BaseModel):
    basic: Optional[dict] = None
    soul: Optional[dict] = None
    memory: Optional[dict] = None
    skills: Optional[dict] = None


# ── Staff Endpoints ───────────────────────────────────────────────

@router.get("/list")
async def list_staff():
    """获取所有AI员工状态 — 从真实子系统动态聚合."""
    staff = _compute_staff_status()
    return {"staff": staff}


@router.get("/{staff_id}")
async def get_staff(staff_id: str):
    """获取单个员工详情."""
    staff = _compute_staff_status()
    for s in staff:
        if s["id"] == staff_id:
            return s
    raise HTTPException(status_code=404, detail=f"Staff not found: {staff_id}")


# ── Task Endpoints ────────────────────────────────────────────────

@router.get("/tasks/list")
async def list_tasks():
    """获取所有任务 — 合并调度器任务与手动任务."""
    tasks = _compute_tasks()
    return {"tasks": tasks}


@router.post("/tasks/create")
async def create_task(body: TaskCreate):
    """创建新任务（手动任务，追加到 JSON 文件）."""
    tasks = _load_json(_TASKS_FILE, [])
    new_id = max([t["id"] for t in tasks], default=0) + 1
    task = {
        "id": new_id,
        "name": body.name,
        "assignee": body.assignee,
        "status": "ready",
        "priority": body.priority,
        "progress": 0,
        "deadline": body.deadline,
        "reviewStatus": None,
        "reviewComment": "",
        "reviewTime": "",
    }
    tasks.append(task)
    _save_json(_TASKS_FILE, tasks)
    return {"ok": True, "task": task}


@router.put("/tasks/{task_id}")
async def update_task(task_id: int, body: TaskUpdate):
    """更新任务."""
    tasks = _load_json(_TASKS_FILE, [])
    for t in tasks:
        if t["id"] == task_id:
            if body.name is not None:
                t["name"] = body.name
            if body.assignee is not None:
                t["assignee"] = body.assignee
            if body.status is not None:
                t["status"] = body.status
                if body.status == "done":
                    t["progress"] = 100
            if body.priority is not None:
                t["priority"] = body.priority
            if body.progress is not None:
                t["progress"] = body.progress
            if body.deadline is not None:
                t["deadline"] = body.deadline
            if body.reviewStatus is not None:
                t["reviewStatus"] = body.reviewStatus
            if body.reviewComment is not None:
                t["reviewComment"] = body.reviewComment
            if body.reviewTime is not None:
                t["reviewTime"] = body.reviewTime
            _save_json(_TASKS_FILE, tasks)
            return {"ok": True, "task": t}
    raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除任务."""
    tasks = _load_json(_TASKS_FILE, [])
    tasks = [t for t in tasks if t["id"] != task_id]
    _save_json(_TASKS_FILE, tasks)
    return {"ok": True}


# ── Agent Config Endpoints ────────────────────────────────────────

@router.get("/configs/list")
async def list_configs():
    """获取所有员工配置."""
    configs = _load_json(_CONFIGS_FILE, None)
    if configs is None:
        configs = _DEFAULT_CONFIGS
        _save_json(_CONFIGS_FILE, configs)
    return {"configs": configs}


@router.get("/configs/{agent_id}")
async def get_config(agent_id: str):
    """获取单个员工配置."""
    configs = _load_json(_CONFIGS_FILE, _DEFAULT_CONFIGS)
    if agent_id in configs:
        return {"config": configs[agent_id]}
    raise HTTPException(status_code=404, detail=f"Agent config not found: {agent_id}")


@router.put("/configs/{agent_id}")
async def update_config(agent_id: str, body: AgentConfigUpdate):
    """保存员工配置."""
    configs = _load_json(_CONFIGS_FILE, _DEFAULT_CONFIGS)
    if agent_id not in configs:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    if body.basic is not None:
        configs[agent_id]["basic"] = body.basic
    if body.soul is not None:
        configs[agent_id]["soul"] = body.soul
    if body.memory is not None:
        configs[agent_id]["memory"] = body.memory
    if body.skills is not None:
        configs[agent_id]["skills"] = body.skills
    _save_json(_CONFIGS_FILE, configs)
    return {"ok": True}


@router.post("/configs/{agent_id}/reset")
async def reset_config(agent_id: str):
    """重置员工配置为默认值."""
    configs = _load_json(_CONFIGS_FILE, _DEFAULT_CONFIGS)
    if agent_id not in _DEFAULT_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    configs[agent_id] = json.loads(json.dumps(_DEFAULT_CONFIGS[agent_id]))
    _save_json(_CONFIGS_FILE, configs)
    return {"ok": True, "config": configs[agent_id]}
