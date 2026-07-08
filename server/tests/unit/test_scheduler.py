"""
Unit tests for szyg.scheduler_engine — smart scheduling engine.

Tests cover:
- Cron expression matching
- Next cron run calculation
- Job CRUD operations
- Job scheduling (cron/interval/once)
- Health check
- History and stats
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from szyg.scheduler_engine import (
    JobAction,
    JobExecution,
    JobStatus,
    ScheduleJob,
    Scheduler,
    TriggerType,
    _cron_matches,
    _next_cron_run,
)


@pytest.fixture
def scheduler(tmp_path: Path):
    """Create Scheduler with isolated temp data files."""
    sched_db = tmp_path / "scheduler_jobs.json"
    sched_hist = tmp_path / "scheduler_history.json"
    sched_db.write_text("[]", encoding="utf-8")
    sched_hist.write_text("[]", encoding="utf-8")

    with patch("szyg.scheduler_engine.SCHEDULER_DB", sched_db), \
         patch("szyg.scheduler_engine.SCHEDULER_HISTORY", sched_hist), \
         patch("szyg.scheduler_engine._resolve", side_effect=lambda p: p):
        yield Scheduler()


class TestCronMatches:
    def test_wildcard_every_minute(self):
        assert _cron_matches("* * * * *", datetime(2024, 6, 15, 10, 30)) is True

    def test_specific_minute(self):
        assert _cron_matches("30 * * * *", datetime(2024, 6, 15, 10, 30)) is True
        assert _cron_matches("30 * * * *", datetime(2024, 6, 15, 10, 31)) is False

    def test_specific_hour(self):
        assert _cron_matches("0 9 * * *", datetime(2024, 6, 15, 9, 0)) is True
        assert _cron_matches("0 9 * * *", datetime(2024, 6, 15, 10, 0)) is False

    def test_specific_day(self):
        assert _cron_matches("0 0 15 * *", datetime(2024, 6, 15, 0, 0)) is True
        assert _cron_matches("0 0 15 * *", datetime(2024, 6, 16, 0, 0)) is False

    def test_specific_month(self):
        assert _cron_matches("0 0 1 6 *", datetime(2024, 6, 1, 0, 0)) is True
        assert _cron_matches("0 0 1 6 *", datetime(2024, 7, 1, 0, 0)) is False

    def test_specific_weekday(self):
        # Monday = 0
        monday = datetime(2024, 6, 10, 9, 0)  # This is a Monday
        assert _cron_matches("0 9 * * 0", monday) is True
        # Tuesday = 1
        tuesday = datetime(2024, 6, 11, 9, 0)
        assert _cron_matches("0 9 * * 0", tuesday) is False

    def test_step_pattern(self):
        assert _cron_matches("*/15 * * * *", datetime(2024, 6, 15, 10, 0)) is True
        assert _cron_matches("*/15 * * * *", datetime(2024, 6, 15, 10, 15)) is True
        assert _cron_matches("*/15 * * * *", datetime(2024, 6, 15, 10, 7)) is False

    def test_list_pattern(self):
        assert _cron_matches("0 9,12,18 * * *", datetime(2024, 6, 15, 9, 0)) is True
        assert _cron_matches("0 9,12,18 * * *", datetime(2024, 6, 15, 10, 0)) is False

    def test_range_pattern(self):
        assert _cron_matches("0 9-17 * * *", datetime(2024, 6, 15, 12, 0)) is True
        assert _cron_matches("0 9-17 * * *", datetime(2024, 6, 15, 8, 0)) is False

    def test_invalid_cron(self):
        assert _cron_matches("invalid", datetime.now()) is False
        assert _cron_matches("* *", datetime.now()) is False


class TestNextCronRun:
    def test_daily_9am(self):
        now = datetime(2024, 6, 15, 8, 0)
        result = _next_cron_run("0 9 * * *", now)
        assert result is not None
        next_dt = datetime.fromisoformat(result)
        assert next_dt.hour == 9
        assert next_dt.minute == 0
        assert next_dt > now

    def test_returns_none_if_no_match_in_24h(self):
        # Invalid cron that never matches
        result = _next_cron_run("61 25 32 13 *", datetime.now())
        assert result is None


class TestScheduleJobModel:
    def test_default_construction(self):
        job = ScheduleJob(name="Test Job")
        assert job.name == "Test Job"
        assert job.trigger_type == TriggerType.MANUAL
        assert job.action == JobAction.CUSTOM
        assert job.priority == 5
        assert job.status == JobStatus.ACTIVE
        assert job.max_retries == 3
        assert len(job.id) == 8

    def test_cron_job(self):
        job = ScheduleJob(
            name="Daily Post",
            trigger_type=TriggerType.CRON,
            trigger_config={"cron": "0 8 * * *"},
            action=JobAction.PUBLISH_CONTENT,
        )
        assert job.trigger_config["cron"] == "0 8 * * *"

    def test_interval_job(self):
        job = ScheduleJob(
            name="Hourly Check",
            trigger_type=TriggerType.INTERVAL,
            trigger_config={"minutes": 60},
        )
        assert job.trigger_config["minutes"] == 60


class TestJobExecutionModel:
    def test_default_construction(self):
        exec_ = JobExecution(job_id="j1")
        assert exec_.job_id == "j1"
        assert exec_.status == "running"
        assert exec_.started_at != ""
        assert exec_.finished_at == ""


class TestSchedulerCRUD:
    def test_create_job(self, scheduler: Scheduler):
        job = scheduler.create_job(name="Test Job", trigger_type=TriggerType.MANUAL)
        assert job.name == "Test Job"
        assert job.id is not None

    def test_list_jobs(self, scheduler: Scheduler):
        scheduler.create_job(name="Job 1")
        scheduler.create_job(name="Job 2")
        jobs = scheduler.list_jobs()
        assert len(jobs) == 2

    def test_get_job(self, scheduler: Scheduler):
        job = scheduler.create_job(name="Find Me")
        found = scheduler.get_job(job.id)
        assert found is not None
        assert found.name == "Find Me"

    def test_get_nonexistent(self, scheduler: Scheduler):
        assert scheduler.get_job("nonexistent") is None

    def test_update_job(self, scheduler: Scheduler):
        job = scheduler.create_job(name="Original")
        updated = scheduler.update_job(job.id, name="Updated")
        assert updated.name == "Updated"

    def test_delete_job(self, scheduler: Scheduler):
        job = scheduler.create_job(name="Delete Me")
        assert scheduler.delete_job(job.id) is True
        assert scheduler.get_job(job.id) is None

    def test_pause_resume(self, scheduler: Scheduler):
        job = scheduler.create_job(name="Pausable")
        paused = scheduler.pause_job(job.id)
        assert paused.status == JobStatus.PAUSED
        resumed = scheduler.resume_job(job.id)
        assert resumed.status == JobStatus.ACTIVE

    def test_filter_by_status(self, scheduler: Scheduler):
        j1 = scheduler.create_job(name="Active")
        j2 = scheduler.create_job(name="Paused")
        scheduler.pause_job(j2.id)
        active = scheduler.list_jobs(status="active")
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_filter_by_tag(self, scheduler: Scheduler):
        scheduler.create_job(name="Tagged", tags=["daily", "social"])
        scheduler.create_job(name="Untagged")
        tagged = scheduler.list_jobs(tag="daily")
        assert len(tagged) == 1

    def test_filter_by_search(self, scheduler: Scheduler):
        scheduler.create_job(name="Morning Post")
        scheduler.create_job(name="Evening Report")
        results = scheduler.list_jobs(search="morning")
        assert len(results) == 1

    def test_limit(self, scheduler: Scheduler):
        for i in range(10):
            scheduler.create_job(name=f"Job {i}")
        results = scheduler.list_jobs(limit=3)
        assert len(results) == 3


class TestJobScheduling:
    def test_cron_next_run(self, scheduler: Scheduler):
        job = scheduler.create_job(
            name="Daily",
            trigger_type=TriggerType.CRON,
            trigger_config={"cron": "0 9 * * *"},
        )
        assert job.next_run_at != ""

    def test_interval_next_run(self, scheduler: Scheduler):
        job = scheduler.create_job(
            name="Hourly",
            trigger_type=TriggerType.INTERVAL,
            trigger_config={"minutes": 60},
        )
        assert job.next_run_at != ""
        next_dt = datetime.fromisoformat(job.next_run_at)
        assert next_dt > datetime.now()

    def test_once_next_run(self, scheduler: Scheduler):
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        job = scheduler.create_job(
            name="One-shot",
            trigger_type=TriggerType.ONCE,
            trigger_config={"at": future},
        )
        assert job.next_run_at == future


class TestSchedulerExecution:
    def test_execute_job(self, scheduler: Scheduler):
        job = scheduler.create_job(
            name="Tool Job",
            action=JobAction.EXECUTE_TOOL,
            action_config={"tool": "test_tool"},
        )
        execution = scheduler.execute_job(job.id)
        assert execution.status == "success"
        assert "test_tool" in execution.result

    def test_execute_workflow(self, scheduler: Scheduler):
        job = scheduler.create_job(
            name="Workflow",
            action=JobAction.RUN_WORKFLOW,
            action_config={"sop_name": "Test SOP", "params": {}},
        )
        execution = scheduler.execute_job(job.id)
        assert execution.status == "success"
        assert "Test SOP" in execution.result

    def test_execute_notification(self, scheduler: Scheduler):
        job = scheduler.create_job(
            name="Notification",
            action=JobAction.SEND_NOTIFICATION,
            action_config={"message": "Hello!"},
        )
        execution = scheduler.execute_job(job.id)
        assert execution.status == "success"
        assert "Hello!" in execution.result

    def test_execute_nonexistent_raises(self, scheduler: Scheduler):
        with pytest.raises(ValueError, match="not found"):
            scheduler.execute_job("nonexistent")


class TestHistory:
    def test_get_history_empty(self, scheduler: Scheduler):
        assert scheduler.get_history() == []

    def test_get_history_after_execution(self, scheduler: Scheduler):
        job = scheduler.create_job(
            name="Executed",
            action=JobAction.SEND_NOTIFICATION,
            action_config={"message": "test"},
        )
        scheduler.execute_job(job.id)
        history = scheduler.get_history()
        assert len(history) == 1
        assert history[0].job_id == job.id

    def test_filter_history_by_job(self, scheduler: Scheduler):
        j1 = scheduler.create_job(
            name="Job 1",
            action=JobAction.SEND_NOTIFICATION,
            action_config={"message": "m1"},
        )
        j2 = scheduler.create_job(
            name="Job 2",
            action=JobAction.SEND_NOTIFICATION,
            action_config={"message": "m2"},
        )
        scheduler.execute_job(j1.id)
        scheduler.execute_job(j2.id)
        history = scheduler.get_history(job_id=j1.id)
        assert len(history) == 1
        assert history[0].job_id == j1.id


class TestStats:
    def test_empty_stats(self, scheduler: Scheduler):
        stats = scheduler.get_stats()
        assert stats["total_jobs"] == 0
        assert stats["total_executions"] == 0

    def test_stats_after_operations(self, scheduler: Scheduler):
        j1 = scheduler.create_job(
            name="Job 1",
            action=JobAction.SEND_NOTIFICATION,
            action_config={"message": "test"},
        )
        j2 = scheduler.create_job(name="Job 2")
        scheduler.execute_job(j1.id)
        scheduler.pause_job(j2.id)

        stats = scheduler.get_stats()
        assert stats["total_jobs"] == 2
        assert stats["active"] == 1
        assert stats["paused"] == 1
        assert stats["total_executions"] == 1


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self, scheduler: Scheduler):
        health = await scheduler.health_check()
        assert "running" in health
        assert "consecutive_tick_failures" in health
        assert "per_job_failures" in health
        assert "active_jobs" in health
        assert "paused_jobs" in health


class TestSeedDemoJobs:
    def test_seeds_5_demos(self, scheduler: Scheduler):
        scheduler.seed_demo_jobs()
        jobs = scheduler.list_jobs()
        assert len(jobs) == 5

    def test_idempotent(self, scheduler: Scheduler):
        scheduler.seed_demo_jobs()
        scheduler.seed_demo_jobs()
        jobs = scheduler.list_jobs()
        assert len(jobs) == 5  # Should not duplicate
