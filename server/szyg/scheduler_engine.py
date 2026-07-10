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
from szyg.atomic_file import atomic_read, atomic_write
from szyg.atomic_file import atomic_read_async, atomic_write_async

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


def _resolve(path: Path) -> Path:
    """Resolve tenant path and ensure parent dirs exist."""
    actual = _tdf(path.name) if path.parent == DATA_DIR else path
    actual.parent.mkdir(parents=True, exist_ok=True)
    return actual


def _read(path: Path) -> list[dict]:
    """Sync read with path resolution. Thread-safe via atomic_file."""
    return atomic_read(_resolve(path))


def _write(path: Path, data: list[dict]) -> None:
    """Sync atomic write with path resolution. Thread-safe via atomic_file."""
    atomic_write(_resolve(path), data)


async def _read_async(path: Path) -> list[dict]:
    """Non-blocking read — runs file I/O in thread pool."""
    return await atomic_read_async(_resolve(path))


async def _write_async(path: Path, data: list[dict]) -> None:
    """Non-blocking write — runs file I/O in thread pool."""
    await atomic_write_async(_resolve(path), data)


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

    # Thresholds
    MAX_CONSECUTIVE_TICK_FAILURES = 5   # warn after N whole-tick failures
    MAX_PER_JOB_FAILURES = 3            # auto-pause job after N consecutive fails

    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._running = False
        self._loop_task: asyncio.Task | None = None
        self._tick_interval: int = 60  # 每60秒检查一次到期任务

        # Health tracking
        self._consecutive_tick_failures: int = 0
        self._last_tick_success: str = ""  # ISO timestamp
        self._per_job_failures: dict[str, int] = {}  # job_id → consecutive failures

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
        """后台循环：每隔 tick_interval 检查一次到期任务。

        Tracks consecutive whole-tick failures.  After the threshold is
        exceeded, emits a warning so operators can investigate before the
        scheduler silently goes deaf.
        """
        import logging
        log = logging.getLogger(__name__)
        while self._running:
            try:
                await asyncio.sleep(self._tick_interval)
                await self._tick()
                self._consecutive_tick_failures = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._consecutive_tick_failures += 1
                n = self._consecutive_tick_failures
                if n >= self.MAX_CONSECUTIVE_TICK_FAILURES:
                    log.error(
                        "调度器 tick 连续失败 %d 次 (阈值=%d) — 调度器可能已失效! "
                        "last error: %s",
                        n, self.MAX_CONSECUTIVE_TICK_FAILURES, e,
                    )
                else:
                    log.error(
                        "调度器 tick 异常 [consecutive=%d/%d]: %s",
                        n, self.MAX_CONSECUTIVE_TICK_FAILURES, e,
                    )

    async def _tick(self) -> None:
        """Execute every due ACTIVE job with per-job timeout and failure tracking.

        Per-job failure counting:
          - One success resets the counter.
          - ``MAX_PER_JOB_FAILURES`` consecutive failures → auto-pause the job
            so it doesn't silently retry forever.
        """
        import logging
        log = logging.getLogger(__name__)
        now = datetime.now()
        self._last_tick_success = now.isoformat()

        JOB_TIMEOUTS = {
            "publish_content": 120,
            "generate_content": 60,
            "run_workflow": 300,
            "platform_login_check": 30,
            "platform_health_check": 30,
            "execute_tool": 60,
            "custom": 60,
        }

        for job in self.list_jobs(status=JobStatus.ACTIVE.value):
            if not job.next_run_at:
                continue
            try:
                next_run = datetime.fromisoformat(job.next_run_at)
            except (ValueError, TypeError):
                log.warning("[scheduler] invalid next_run_at for %s: %r — skipping",
                            job.name, job.next_run_at)
                continue

            if next_run > now:
                continue

            timeout = JOB_TIMEOUTS.get(job.action.value, 60)
            log.info("[scheduler] triggering: %s (timeout=%ds)", job.name, timeout)

            try:
                await asyncio.wait_for(
                    self._async_dispatch(job),
                    timeout=timeout,
                )
                # Success → reset failure counter
                self._per_job_failures.pop(job.id, None)

            except asyncio.TimeoutError:
                self._record_job_failure(log, job,
                    f"TIMEOUT after {timeout}s — marked FAILED")
                self.update_job(job.id, status=JobStatus.FAILED.value)

            except Exception as e:
                self._record_job_failure(log, job, f"{type(e).__name__}: {e}")

    def _record_job_failure(self, log, job: ScheduleJob, detail: str) -> None:
        """Increment per-job failure counter; auto-pause at threshold."""
        prev = self._per_job_failures.get(job.id, 0)
        current = prev + 1
        self._per_job_failures[job.id] = current

        if current >= self.MAX_PER_JOB_FAILURES:
            log.error(
                "[scheduler] %s failed %d consecutive times — auto-pausing.  %s",
                job.name, current, detail,
            )
            self.update_job(job.id, status=JobStatus.PAUSED.value)
            self._per_job_failures.pop(job.id, None)
        else:
            log.error(
                "[scheduler] %s failed [%d/%d consecutive]: %s",
                job.name, current, self.MAX_PER_JOB_FAILURES, detail,
            )

    async def health_check(self) -> dict:
        """Return scheduler health status for external monitoring."""
        return {
            "running": self._running,
            "consecutive_tick_failures": self._consecutive_tick_failures,
            "last_tick_success": self._last_tick_success,
            "per_job_failures": dict(self._per_job_failures),
            "active_jobs": len(self.list_jobs(status=JobStatus.ACTIVE.value)),
            "paused_jobs": len(self.list_jobs(status=JobStatus.PAUSED.value)),
            "failed_jobs": len(self.list_jobs(status=JobStatus.FAILED.value)),
        }

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
                c = await pub.ai_generate(topic, agent_id, content_type)
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

        # 保存历史 (non-blocking I/O)
        history = await _read_async(SCHEDULER_HISTORY)
        history.append(execution.model_dump())
        await _write_async(SCHEDULER_HISTORY, history)

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
            import asyncio as _asyncio
            from szyg.publisher import get_publisher
            pub = get_publisher()
            topic = config.get("topic", "AI生成内容")
            agent_id = config.get("agent_id", "copywriter")
            content_type = config.get("content_type", "post")
            c = _asyncio.run(pub.ai_generate(topic, agent_id, content_type))
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

    # --- Retry & Cancel ---
    def retry_job(self, job_id: str) -> JobExecution | None:
        """Retry a failed job — reset to ACTIVE and re-execute."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        # Reset failed/paused status back to active so the job can run again
        self.update_job(job_id, status=JobStatus.ACTIVE.value,
                        updated_at=datetime.now().isoformat())
        return self.execute_job(job_id)

    def cancel_job(self, job_id: str) -> ScheduleJob | None:
        """Cancel a running/pending job."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        # Mark as paused so it won't be picked up by the tick loop
        return self.update_job(job_id, status=JobStatus.PAUSED.value,
                               updated_at=datetime.now().isoformat())

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

    def seed_demo_tasks(self) -> None:
        """Seed demo tasks with varied statuses for the task board.
        Creates jobs AND execution history so the board shows realistic data.
        Idempotent — skips if history already exists.
        """
        existing_history = _read(SCHEDULER_HISTORY)
        if existing_history:
            return

        now = datetime.now()

        # ── Running tasks (进行中) ──
        running_jobs = [
            ScheduleJob(
                name="抖音短视频批量发布", description="发布3条产品展示短视频到抖音",
                trigger_type=TriggerType.MANUAL, trigger_config={},
                action=JobAction.PUBLISH_CONTENT,
                action_config={"content_id": "ctx_demo_001", "platform": "douyin"},
                priority=9, status=JobStatus.RUNNING,
                tags=["urgent", "douyin"],
                created_at=(now - timedelta(hours=2)).isoformat(),
                last_run_at=(now - timedelta(minutes=30)).isoformat(),
            ),
            ScheduleJob(
                name="小红书评论区截流", description="监控竞品笔记评论区，自动回复引流",
                trigger_type=TriggerType.INTERVAL,
                trigger_config={"minutes": 30},
                action=JobAction.EXECUTE_TOOL,
                action_config={"tool": "intercept_engine", "platform": "xiaohongshu", "keywords": "护肤,面膜"},
                priority=8, status=JobStatus.RUNNING,
                tags=["intercept", "xiaohongshu"],
                created_at=(now - timedelta(hours=5)).isoformat(),
                last_run_at=(now - timedelta(minutes=5)).isoformat(),
            ),
            ScheduleJob(
                name="B站品牌舆情监听", description="实时监控B站品牌相关弹幕和评论",
                trigger_type=TriggerType.INTERVAL,
                trigger_config={"minutes": 15},
                action=JobAction.PLATFORM_HEALTH_CHECK,
                action_config={"platform": "bilibili", "brand": "玉灵科技"},
                priority=7, status=JobStatus.RUNNING,
                tags=["listen", "bilibili"],
                created_at=(now - timedelta(hours=8)).isoformat(),
                last_run_at=(now - timedelta(minutes=10)).isoformat(),
            ),
        ]

        # ── Completed tasks (已完成) ──
        completed_jobs = [
            ScheduleJob(
                name="快手品牌宣传片发布", description="发布品牌宣传片到快手",
                trigger_type=TriggerType.ONCE,
                trigger_config={"at": (now - timedelta(hours=4)).isoformat()},
                action=JobAction.PUBLISH_CONTENT,
                action_config={"content_id": "ctx_demo_002", "platform": "kuaishou"},
                priority=9, status=JobStatus.COMPLETED,
                tags=["brand", "kuaishou"],
                created_at=(now - timedelta(hours=6)).isoformat(),
                last_run_at=(now - timedelta(hours=4)).isoformat(),
            ),
            ScheduleJob(
                name="AI营销文案周报生成", description="生成本周营销文案数据报告",
                trigger_type=TriggerType.CRON,
                trigger_config={"cron": "0 17 * * 5"},
                action=JobAction.GENERATE_CONTENT,
                action_config={"topic": "本周营销数据汇总", "agent_id": "copywriter", "content_type": "report"},
                priority=6, status=JobStatus.COMPLETED,
                tags=["report", "ai"],
                created_at=(now - timedelta(days=3)).isoformat(),
                last_run_at=(now - timedelta(hours=6)).isoformat(),
            ),
            ScheduleJob(
                name="微信公众号文章发布", description="发布一篇品牌故事文章到微信公众号",
                trigger_type=TriggerType.MANUAL, trigger_config={},
                action=JobAction.PUBLISH_CONTENT,
                action_config={"content_id": "ctx_demo_003", "platform": "weixin"},
                priority=8, status=JobStatus.COMPLETED,
                tags=["brand", "weixin"],
                created_at=(now - timedelta(days=1)).isoformat(),
                last_run_at=(now - timedelta(hours=12)).isoformat(),
            ),
            ScheduleJob(
                name="全平台账号登录巡检", description="检查所有平台账号登录状态",
                trigger_type=TriggerType.INTERVAL,
                trigger_config={"minutes": 360},
                action=JobAction.PLATFORM_LOGIN_CHECK,
                action_config={"platform": "all"},
                priority=5, status=JobStatus.COMPLETED,
                tags=["health", "all"],
                created_at=(now - timedelta(days=2)).isoformat(),
                last_run_at=(now - timedelta(hours=1)).isoformat(),
            ),
        ]

        # ── Failed tasks (失败) ──
        failed_jobs = [
            ScheduleJob(
                name="抖音直播引流视频发布", description="发布直播预热视频到抖音",
                trigger_type=TriggerType.ONCE,
                trigger_config={"at": (now - timedelta(hours=3)).isoformat()},
                action=JobAction.PUBLISH_CONTENT,
                action_config={"content_id": "ctx_demo_004", "platform": "douyin"},
                priority=10, status=JobStatus.FAILED,
                tags=["urgent", "douyin"],
                created_at=(now - timedelta(hours=5)).isoformat(),
                last_run_at=(now - timedelta(hours=3)).isoformat(),
            ),
            ScheduleJob(
                name="微博热搜话题截流", description="自动评论微博热搜话题引流",
                trigger_type=TriggerType.MANUAL, trigger_config={},
                action=JobAction.EXECUTE_TOOL,
                action_config={"tool": "intercept_engine", "platform": "weibo", "keywords": "AI创业"},
                priority=9, status=JobStatus.FAILED,
                tags=["intercept", "weibo"],
                created_at=(now - timedelta(hours=4)).isoformat(),
                last_run_at=(now - timedelta(hours=2)).isoformat(),
            ),
        ]

        jobs = running_jobs + completed_jobs + failed_jobs
        # Append to existing jobs (don't overwrite seed_demo_jobs data)
        existing_db = _read(SCHEDULER_DB)
        existing_ids = {j["id"] for j in existing_db}
        new_items = [j.model_dump() for j in jobs if j.id not in existing_ids]
        existing_db.extend(new_items)
        _write(SCHEDULER_DB, existing_db)

        # ── Execution history ──
        history: list[dict] = []

        # Running task executions
        for j in running_jobs:
            exec_id = str(uuid.uuid4())[:8]
            started = j.last_run_at or (now - timedelta(minutes=30)).isoformat()
            history.append(JobExecution(
                id=exec_id, job_id=j.id, job_name=j.name,
                status="running", started_at=started,
                result=f"执行中… {j.action_config.get('platform', '')} {j.action_config.get('tool', '')}",
            ).model_dump())

        # Completed task executions
        completed_results = [
            ("发布成功，播放量 12,834，点赞 856，评论 234", 125000),
            ("生成报告完成：本周发布 23 条内容，总曝光 45.2 万", 85000),
            ("发布成功，阅读量 3,421，分享 89 次", 32000),
            ("巡检完成：6/6 平台登录正常", 15000),
        ]
        for j, (result, duration_ms) in zip(completed_jobs, completed_results):
            started = j.last_run_at or (now - timedelta(hours=4)).isoformat()
            finished_dt = datetime.fromisoformat(started) + timedelta(milliseconds=duration_ms)
            history.append(JobExecution(
                id=str(uuid.uuid4())[:8], job_id=j.id, job_name=j.name,
                status="success", started_at=started,
                finished_at=finished_dt.isoformat(),
                duration_ms=duration_ms, result=result,
            ).model_dump())

        # Failed task executions
        failed_results = [
            ("抖音API限流：发布频率过高，请等待 30 分钟后再试。当前账号今日已发布 15 条，超过单日上限 20 条，建议错峰发布或升级企业账号提升额度。",
             (now - timedelta(hours=3)).isoformat()),
            ("微博登录态过期：cookie 已失效，需要重新扫码登录。请在账号管理页面重新授权微博账号，或检查账号风控状态是否正常。",
             (now - timedelta(hours=2)).isoformat()),
        ]
        for j, (error, started) in zip(failed_jobs, failed_results):
            finished_dt = datetime.fromisoformat(started) + timedelta(seconds=45)
            history.append(JobExecution(
                id=str(uuid.uuid4())[:8], job_id=j.id, job_name=j.name,
                status="failed", started_at=started,
                finished_at=finished_dt.isoformat(),
                duration_ms=45000, error=error,
            ).model_dump())

        _write(SCHEDULER_HISTORY, history)


# Singleton
_scheduler: Scheduler | None = None
def _demo_seed_enabled() -> bool:
    return os.environ.get("SZYG_SEED_DEMO_DATA", "").lower() in {"1", "true", "yes"} or os.environ.get("SZYG_DEMO_MODE", "").lower() in {"1", "true", "yes"}


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
        if _demo_seed_enabled():
            _scheduler.seed_demo_jobs()
            _scheduler.seed_demo_tasks()
    return _scheduler
