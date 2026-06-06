"""
Smart Scheduling Engine — 智能调度引擎
Cron任务 + 工作流触发 + 优先级队列 + 执行历史 + 重试
"""
import json, os, uuid, asyncio
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable
from pydantic import BaseModel, Field

from szyg.data_path import DATA_DIR
from szyg.tenant import get_tenant_data_file as _tdf
SCHEDULER_DB = DATA_DIR / "scheduler_jobs.json"
SCHEDULER_HISTORY = DATA_DIR / "scheduler_history.json"


class JobStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


class TriggerType(str, Enum):
    CRON = "cron"          # cron表达式
    INTERVAL = "interval"  # 固定间隔
    ONCE = "once"          # 一次性
    EVENT = "event"        # 事件触发
    MANUAL = "manual"      # 手动触发


class JobAction(str, Enum):
    PUBLISH_CONTENT = "publish_content"           # 发布内容
    GENERATE_CONTENT = "generate_content"         # AI生成内容
    RUN_WORKFLOW = "run_workflow"                  # 执行SOP工作流
    SEND_NOTIFICATION = "send_notification"        # 发送通知
    EXECUTE_TOOL = "execute_tool"                  # 执行工具
    PLATFORM_LOGIN_CHECK = "platform_login_check"  # 平台登录状态检查
    PLATFORM_HEALTH_CHECK = "platform_health_check"  # 平台健康巡检
    CUSTOM = "custom"                              # 自定义


class ScheduleJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str = ""
    trigger_type: TriggerType = TriggerType.MANUAL
    trigger_config: dict = Field(default_factory=dict)
    # cron: {"cron": "0 9 * * *"}
    # interval: {"minutes": 30}
    # once: {"at": "2024-06-10T09:00:00"}
    # event: {"event": "content.approved"}
    action: JobAction = JobAction.CUSTOM
    action_config: dict = Field(default_factory=dict)
    # publish_content: {"content_id": "xxx", "platform": "all"}
    # generate_content: {"topic": "...", "agent_id": "copywriter"}
    # run_workflow: {"sop_name": "视频创作SOP", "params": {}}
    priority: int = Field(default=5, ge=1, le=10)
    status: JobStatus = JobStatus.ACTIVE
    max_retries: int = 3
    retry_delay_seconds: int = 60
    tags: list[str] = []
    created_by: str = "admin"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_run_at: str = ""
    next_run_at: str = ""


class JobExecution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    job_id: str
    job_name: str = ""
    status: str = "running"  # running/success/failed/cancelled
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str = ""
    duration_ms: int = 0
    retry_count: int = 0
    result: str = ""
    error: str = ""


def _read(path: Path) -> list[dict]:
    actual = _tdf(path.name) if path.parent == DATA_DIR else path
    if actual.exists():
        return json.loads(actual.read_text(encoding='utf-8'))
    return []

def _write(path: Path, data: list[dict]):
    actual = _tdf(path.name) if path.parent == DATA_DIR else path
    actual.parent.mkdir(parents=True, exist_ok=True)
    actual.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _cron_matches(cron: str, dt: datetime) -> bool:
    """Simple cron matching: minute hour day month weekday"""
    try:
        parts = cron.split()
        if len(parts) != 5:
            return False
        minute, hour, day, month, weekday = parts
        checks = [
            (minute, dt.minute, 0, 59),
            (hour, dt.hour, 0, 23),
            (day, dt.day, 1, 31),
            (month, dt.month, 1, 12),
        ]
        for pattern, value, lo, hi in checks:
            if pattern == "*": continue
            if "/" in pattern:
                step = int(pattern.split("/")[1])
                if value % step != 0: return False
            elif "," in pattern:
                if str(value) not in pattern.split(","): return False
            elif "-" in pattern:
                lo2, hi2 = map(int, pattern.split("-"))
                if not (lo2 <= value <= hi2): return False
            elif int(pattern) != value:
                return False
        if weekday != "*":
            w = dt.weekday()
            if str(w) != weekday: return False
        return True
    except Exception:
        return False


def _next_cron_run(cron: str, from_dt: datetime | None = None) -> str | None:
    """Calculate next cron run time within next 24h"""
    dt = from_dt or datetime.now()
    for i in range(1440):  # Check each minute for next 24h
        check = dt + timedelta(minutes=i + 1)
        if _cron_matches(cron, check):
            return check.isoformat()
    return None


class Scheduler:
    """Smart scheduling engine with background polling loop"""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._running = False
        self._loop_task: asyncio.Task | None = None
        self._tick_interval: int = 60  # 每60秒检查一次到期任务

    # ── Background Loop ──────────────────────────────────

    async def start(self) -> None:
        """启动后台调度循环 (幂等)"""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop())
        import logging
        logging.getLogger(__name__).info(
            f"调度器后台循环已启动 (interval={self._tick_interval}s)"
        )

    async def stop(self) -> None:
        """停止后台调度循环"""
        self._running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        self._loop_task = None
        import logging
        logging.getLogger(__name__).info("调度器后台循环已停止")

    async def _run_loop(self) -> None:
        """后台循环：每隔 tick_interval 检查一次到期任务"""
        import logging
        log = logging.getLogger(__name__)
        while self._running:
            try:
                await asyncio.sleep(self._tick_interval)
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"调度器 tick 异常: {e}")

    async def _tick(self) -> None:
        """执行所有到期的 ACTIVE 任务"""
        import logging
        log = logging.getLogger(__name__)
        now = datetime.now()

        for job in self.list_jobs(status=JobStatus.ACTIVE.value):
            if not job.next_run_at:
                continue
            try:
                next_run = datetime.fromisoformat(job.next_run_at)
                if next_run <= now:
                    log.info(f"触发到期任务: {job.name} ({job.id})")
                    await self._async_dispatch(job)
            except (ValueError, OSError):
                continue

    async def _async_dispatch(self, job: ScheduleJob) -> JobExecution:
        """
        异步分发任务 (替代同步 _dispatch)。

        支持 PUBLISH_CONTENT 异步调用真实平台适配器。
        """
        import logging
        log = logging.getLogger(__name__)

        execution = JobExecution(job_id=job.id, job_name=job.name)
        self.update_job(job_id, status=JobStatus.RUNNING.value,
                        last_run_at=datetime.now().isoformat())

        try:
            action = job.action
            config = job.action_config

            if action == JobAction.PUBLISH_CONTENT:
                from szyg.publisher import get_publisher, Platform
                pub = get_publisher()
                content_id = config.get("content_id", "")
                platform_str = config.get("platform", "")

                if content_id:
                    platform = Platform(platform_str) if platform_str else None
                    await pub.publish_async(content_id, platform)
                    execution.result = f"Published content {content_id}"
                else:
                    execution.result = "No content_id specified"

            elif action == JobAction.GENERATE_CONTENT:
                from szyg.publisher import get_publisher
                pub = get_publisher()
                topic = config.get("topic", "AI生成内容")
                agent_id = config.get("agent_id", "copywriter")
                content_type = config.get("content_type", "post")
                c = pub.ai_generate(topic, agent_id, content_type)
                execution.result = f"Generated content {c.id}: {c.title}"

            elif action == JobAction.RUN_WORKFLOW:
                sop_name = config.get("sop_name", "")
                execution.result = f"Executed SOP: {sop_name}"

            elif action == JobAction.SEND_NOTIFICATION:
                execution.result = f"Notification: {config.get('message', '')[:50]}"

            elif action == JobAction.EXECUTE_TOOL:
                execution.result = f"Executed tool: {config.get('tool', '')}"

            elif action == JobAction.PLATFORM_LOGIN_CHECK:
                from szyg.platforms.registry import get_registry
                from szyg.publisher import Platform
                registry = get_registry()
                plat = config.get("platform", "")
                if plat:
                    p = Platform(plat)
                    adapter = await registry.get(p)
                    status = await adapter.check_login()
                    execution.result = f"{plat}: {'logged in' if status.is_logged_in else 'logged out'}"
                else:
                    results = {}
                    for pinfo in registry.list_platforms():
                        try:
                            p = Platform(pinfo["id"])
                            adapter = await registry.get(p)
                            s = await adapter.check_login()
                            results[pinfo["id"]] = s.is_logged_in
                        except Exception:
                            results[pinfo["id"]] = False
                    execution.result = f"Platform status: {results}"

            elif action == JobAction.PLATFORM_HEALTH_CHECK:
                from szyg.platforms.registry import get_registry
                from szyg.publisher import Platform
                registry = get_registry()
                results = {}
                for pinfo in registry.list_platforms():
                    try:
                        p = Platform(pinfo["id"])
                        adapter = await registry.get(p)
                        is_healthy = await adapter.health_check()
                        results[pinfo["id"]] = "healthy" if is_healthy else "unhealthy"
                    except Exception as e:
                        results[pinfo["id"]] = f"error: {e}"
                execution.result = f"Health check: {results}"

            else:
                execution.result = f"Dispatched {action.value}"

            execution.status = "success"
            self.update_job(job_id, status=JobStatus.ACTIVE.value)

        except Exception as e:
            log.error(f"任务执行失败 [{job.name}]: {e}")
            execution.status = "failed"
            execution.error = str(e)
            self.update_job(job_id, status=JobStatus.FAILED.value)

        execution.finished_at = datetime.now().isoformat()

        # 保存历史
        history = _read(SCHEDULER_HISTORY)
        history.append(execution.model_dump())
        _write(SCHEDULER_HISTORY, history)

        # 更新下次运行时间
        if job.trigger_type == TriggerType.CRON and job.trigger_config.get("cron"):
            next_run = _next_cron_run(job.trigger_config["cron"])
            if next_run:
                self.update_job(job_id, next_run_at=next_run)
        elif job.trigger_type == TriggerType.INTERVAL:
            mins = job.trigger_config.get("minutes", 60)
            self.update_job(job_id,
                            next_run_at=(datetime.now() + timedelta(minutes=mins)).isoformat())
        elif job.trigger_type == TriggerType.ONCE:
            self.update_job(job_id, status=JobStatus.COMPLETED.value)

        return execution

    # --- Job CRUD ---
    def list_jobs(self, status: str = "", tag: str = "", search: str = "", limit: int = 50) -> list[ScheduleJob]:
        jobs = _read(SCHEDULER_DB)
        if status:
            jobs = [j for j in jobs if j.get("status") == status]
        if tag:
            jobs = [j for j in jobs if tag in j.get("tags", [])]
        if search:
            q = search.lower()
            jobs = [j for j in jobs if q in j.get("name","").lower() or q in j.get("description","").lower()]
        jobs.sort(key=lambda x: (x.get("priority", 5), x.get("created_at","")), reverse=True)
        return [ScheduleJob(**j) for j in jobs[:limit]]

    def get_job(self, job_id: str) -> ScheduleJob | None:
        for j in _read(SCHEDULER_DB):
            if j["id"] == job_id:
                return ScheduleJob(**j)
        return None

    def create_job(self, **kwargs) -> ScheduleJob:
        job = ScheduleJob(**kwargs)
        # Calculate next run for cron jobs
        if job.trigger_type == TriggerType.CRON and job.trigger_config.get("cron"):
            job.next_run_at = _next_cron_run(job.trigger_config["cron"]) or ""
        elif job.trigger_type == TriggerType.INTERVAL:
            mins = job.trigger_config.get("minutes", 60)
            job.next_run_at = (datetime.now() + timedelta(minutes=mins)).isoformat()
        elif job.trigger_type == TriggerType.ONCE and job.trigger_config.get("at"):
            job.next_run_at = job.trigger_config["at"]
        items = _read(SCHEDULER_DB)
        items.append(job.model_dump())
        _write(SCHEDULER_DB, items)
        return job

    def update_job(self, job_id: str, **kwargs) -> ScheduleJob | None:
        items = _read(SCHEDULER_DB)
        for i, item in enumerate(items):
            if item["id"] == job_id:
                item.update(kwargs)
                item["updated_at"] = datetime.now().isoformat()
                items[i] = item
                _write(SCHEDULER_DB, items)
                return ScheduleJob(**item)
        return None

    def delete_job(self, job_id: str) -> bool:
        items = _read(SCHEDULER_DB)
        new_items = [j for j in items if j["id"] != job_id]
        _write(SCHEDULER_DB, new_items)
        return len(new_items) != len(items)

    def pause_job(self, job_id: str) -> ScheduleJob | None:
        return self.update_job(job_id, status=JobStatus.PAUSED.value)

    def resume_job(self, job_id: str) -> ScheduleJob | None:
        return self.update_job(job_id, status=JobStatus.ACTIVE.value)

    # --- Execution ---
    def execute_job(self, job_id: str) -> JobExecution:
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        execution = JobExecution(job_id=job_id, job_name=job.name)
        self.update_job(job_id, status=JobStatus.RUNNING.value, last_run_at=datetime.now().isoformat())

        try:
            result = self._dispatch(job)
            execution.status = "success"
            execution.result = str(result)
            self.update_job(job_id, status=JobStatus.ACTIVE.value)
        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            self.update_job(job_id, status=JobStatus.FAILED.value)

        execution.finished_at = datetime.now().isoformat()
        execution.duration_ms = 0  # Simplified

        # Save history
        history = _read(SCHEDULER_HISTORY)
        history.append(execution.model_dump())
        _write(SCHEDULER_HISTORY, history)

        # Update next run time for recurring jobs
        if job.trigger_type == TriggerType.CRON and job.trigger_config.get("cron"):
            next_run = _next_cron_run(job.trigger_config["cron"])
            if next_run:
                self.update_job(job_id, next_run_at=next_run)
        elif job.trigger_type == TriggerType.INTERVAL:
            mins = job.trigger_config.get("minutes", 60)
            self.update_job(job_id, next_run_at=(datetime.now() + timedelta(minutes=mins)).isoformat())
        elif job.trigger_type == TriggerType.ONCE:
            self.update_job(job_id, status=JobStatus.COMPLETED.value)

        return execution

    def _dispatch(self, job: ScheduleJob) -> str:
        """Dispatch job action to appropriate handler"""
        action = job.action
        config = job.action_config

        if action == JobAction.PUBLISH_CONTENT:
            from szyg.publisher import get_publisher
            pub = get_publisher()
            content_id = config.get("content_id", "")
            platform = config.get("platform", "")
            if content_id:
                pub.publish_now(content_id)
                return f"Published content {content_id}"
            return "No content_id specified"

        elif action == JobAction.GENERATE_CONTENT:
            from szyg.publisher import get_publisher
            pub = get_publisher()
            topic = config.get("topic", "AI生成内容")
            agent_id = config.get("agent_id", "copywriter")
            content_type = config.get("content_type", "post")
            c = pub.ai_generate(topic, agent_id, content_type)
            return f"Generated content {c.id}: {c.title}"

        elif action == JobAction.RUN_WORKFLOW:
            sop_name = config.get("sop_name", "")
            params = config.get("params", {})
            return f"Executed SOP workflow: {sop_name} with params {params}"

        elif action == JobAction.SEND_NOTIFICATION:
            return f"Notification sent: {config.get('message', '')[:50]}"

        elif action == JobAction.EXECUTE_TOOL:
            tool = config.get("tool", "")
            return f"Executed tool: {tool}"

        return f"Dispatched {action.value}"

    # --- History ---
    def get_history(self, job_id: str = "", limit: int = 50) -> list[JobExecution]:
        history = _read(SCHEDULER_HISTORY)
        if job_id:
            history = [h for h in history if h.get("job_id") == job_id]
        history.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return [JobExecution(**h) for h in history[:limit]]

    # --- Stats ---
    def get_stats(self) -> dict:
        jobs = _read(SCHEDULER_DB)
        history = _read(SCHEDULER_HISTORY)
        status_counts = {}
        for j in jobs:
            s = j.get("status", "active")
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "total_jobs": len(jobs),
            "active": status_counts.get("active", 0),
            "paused": status_counts.get("paused", 0),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "total_executions": len(history),
            "recent_executions": len([h for h in history if h.get("started_at","") > (datetime.now()-timedelta(hours=24)).isoformat()]),
        }

    # --- Seed demo jobs ---
    def seed_demo_jobs(self):
        existing = _read(SCHEDULER_DB)
        if existing:
            return

        demos = [
            ScheduleJob(
                name="每日早安海报发布",
                description="每天早上8点自动发布早安问候图文",
                trigger_type=TriggerType.CRON,
                trigger_config={"cron": "0 8 * * *"},
                action=JobAction.PUBLISH_CONTENT,
                action_config={"content_id": "", "platform": "all"},
                priority=8,
                tags=["daily", "social"],
            ),
            ScheduleJob(
                name="AI内容批量生成",
                description="每隔2小时自动用AI生成3条营销文案草稿",
                trigger_type=TriggerType.INTERVAL,
                trigger_config={"minutes": 120},
                action=JobAction.GENERATE_CONTENT,
                action_config={"topic": "中小企业数字化转型", "agent_id": "copywriter", "content_type": "post"},
                priority=6,
                tags=["ai", "content"],
            ),
            ScheduleJob(
                name="周报自动生成",
                description="每周五17:00自动生成本周内容发布周报",
                trigger_type=TriggerType.CRON,
                trigger_config={"cron": "0 17 * * 5"},
                action=JobAction.RUN_WORKFLOW,
                action_config={"sop_name": "视频创作SOP", "params": {"topic": "本周热点回顾"}},
                priority=7,
                tags=["weekly", "report"],
            ),
            ScheduleJob(
                name="热点话题紧急发布",
                description="检测到热搜话题时手动触发紧急内容发布",
                trigger_type=TriggerType.MANUAL,
                trigger_config={},
                action=JobAction.PUBLISH_CONTENT,
                action_config={"content_id": "", "platform": "all"},
                priority=10,
                tags=["urgent", "social"],
            ),
            ScheduleJob(
                name="平台数据同步",
                description="每小时同步一次各平台发布数据",
                trigger_type=TriggerType.INTERVAL,
                trigger_config={"minutes": 60},
                action=JobAction.CUSTOM,
                action_config={"command": "sync_platform_stats"},
                priority=3,
                tags=["sync", "data"],
            ),
        ]
        items = [j.model_dump() for j in demos]
        _write(SCHEDULER_DB, items)


# Singleton
_scheduler: Scheduler | None = None
def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
        _scheduler.seed_demo_jobs()
    return _scheduler
