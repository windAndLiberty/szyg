import json
from datetime import datetime, timedelta

import pytest

import szyg.comment_engine as comment_engine
from szyg.integrations.acquisition_adapters import BilibiliAcquisitionAdapter, _reply_count

from szyg.comment_engine import (
    CommentItem,
    CommentQueue,
    CommentRateLimiter,
    MarketingAutomationPolicy,
    preflight_check,
    repair_comment,
)


def test_bilibili_channel_session_maps_to_api_credential_fields():
    values = BilibiliAcquisitionAdapter._credential_values_from_storage_state({
        "cookies": [
            {"name": "SESSDATA", "value": "session-value"},
            {"name": "bili_jct", "value": "csrf-value"},
            {"name": "buvid3", "value": "device-value"},
            {"name": "DedeUserID", "value": "user-value"},
            {"name": "unrelated", "value": "ignored"},
        ]
    })

    assert values == {
        "sessdata": "session-value",
        "bili_jct": "csrf-value",
        "buvid3": "device-value",
        "dedeuserid": "user-value",
    }


def test_bilibili_comment_reply_count_accepts_null_replies():
    assert _reply_count(None) == 0
    assert _reply_count([]) == 0
    assert _reply_count([{}, {}]) == 2
    assert _reply_count(3) == 3


def test_low_risk_comment_can_auto_send():
    result = preflight_check("这个角度挺有意思，收藏了")

    assert result["pass"] is True
    assert result["decision"] == "auto_send"
    assert result["risk_codes"] == []


def test_repairable_comment_does_not_need_human():
    text = "总的来说这个内容非常非常有价值，欢迎点赞关注！！！" * 8
    result = preflight_check(text)

    assert result["decision"] == "auto_repair_then_send"
    assert "needs_human" != result["status"]

    repaired = repair_comment(text, "douyin")
    assert len(repaired["repaired"]) <= 200
    assert repaired["preflight"]["decision"] in {"auto_send", "auto_repair_then_send"}


def test_contact_and_sensitive_action_require_human():
    result = preflight_check("感兴趣可以加微信 13800138000 详细聊")

    assert result["decision"] == "needs_human"
    assert result["status"] == "needs_human"
    assert "contains_contact" in result["risk_codes"]


def test_transient_platform_error_is_retry_not_human():
    result = MarketingAutomationPolicy.classify_send_error("未找到评论发送按钮")

    assert result["decision"] == "delay_retry"
    assert result["status"] == "retrying"


@pytest.mark.asyncio
async def test_queue_stats_keep_needs_human_separate(tmp_path):
    queue = CommentQueue(str(tmp_path / "comment_queue.json"))
    await queue.add(CommentItem(id="1", platform="douyin", status="failed"))
    await queue.add(CommentItem(id="2", platform="douyin", status="skipped"))
    await queue.add(CommentItem(id="3", platform="douyin", status="needs_human"))
    await queue.add(CommentItem(id="4", platform="douyin", status="sent", decision="auto_repair_then_send"))

    stats = await queue.stats()

    assert stats.total_failed == 1
    assert stats.total_skipped == 1
    assert stats.total_needs_human == 1
    assert stats.total_auto_repaired == 1


@pytest.mark.asyncio
async def test_rate_limiter_persists_across_instances(tmp_path):
    path = str(tmp_path / "comment_rate_limits.json")
    limiter = CommentRateLimiter(path)
    limiter._hourly_limits["douyin"] = 1
    limiter._daily_limits["douyin"] = 10

    assert await limiter.can_send("douyin") is True
    await limiter.record("douyin")

    reloaded = CommentRateLimiter(path)
    assert await reloaded.can_send("douyin") is False


@pytest.mark.asyncio
async def test_queue_lists_due_retry_items(tmp_path):
    queue = CommentQueue(str(tmp_path / "comment_queue.json"))
    await queue.add(CommentItem(
        id="due",
        platform="douyin",
        status="retrying",
        next_run_at="2000-01-01T00:00:00",
        human_confirmed=True,
    ))
    await queue.add(CommentItem(
        id="future",
        platform="douyin",
        status="delayed",
        next_run_at="2999-01-01T00:00:00",
        human_confirmed=True,
    ))

    due = await queue.due()

    assert [item.id for item in due] == ["due"]


@pytest.mark.asyncio
async def test_queue_does_not_retry_unconfirmed_items(tmp_path):
    queue = CommentQueue(str(tmp_path / "comment_queue.json"))
    await queue.add(CommentItem(
        id="unconfirmed",
        platform="douyin",
        status="retrying",
        next_run_at="2000-01-01T00:00:00",
        human_confirmed=False,
    ))

    assert await queue.due() == []


@pytest.mark.asyncio
async def test_batch_send_requires_confirmation_and_persists_status(tmp_path, monkeypatch):
    queue = CommentQueue(str(tmp_path / "comment_queue.json"))
    limiter = CommentRateLimiter(str(tmp_path / "comment_rate_limits.json"))
    monkeypatch.setattr(comment_engine, "_COMMENT_QUEUE", queue)
    monkeypatch.setattr(comment_engine, "_COMMENT_RATE_LIMITER", limiter)

    class FakeRegistry:
        def is_registered(self, _platform):
            return True

        async def get(self, _platform):
            return object()

    class FakeAcquisitionAdapter:
        def __init__(self):
            self.calls = 0

        async def send_comment(self, **_kwargs):
            self.calls += 1
            return {"success": True, "comment_id": "remote-1"}

    fake_adapter = FakeAcquisitionAdapter()
    monkeypatch.setattr("szyg.platforms.registry.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("szyg.integrations.acquisition_adapters.get_acquisition_adapter", lambda _platform: fake_adapter)
    monkeypatch.setattr(comment_engine.random, "uniform", lambda *_args: 0)

    unconfirmed = await comment_engine.batch_send(
        "douyin",
        [{"text": "这个角度很有意思", "video_url": "https://example.com/video"}],
        deai=False,
        create_execution=False,
    )
    assert unconfirmed[0]["status"] == "needs_human"
    assert fake_adapter.calls == 0

    confirmed = await comment_engine.batch_send(
        "douyin",
        [{
            "text": "这个角度很有意思",
            "video_url": "https://example.com/video",
            "human_confirmed": True,
        }],
        deai=False,
        create_execution=False,
    )
    assert confirmed[0]["status"] == "sent"
    assert fake_adapter.calls == 1
    stored = await queue.get(confirmed[0]["id"])
    assert stored is not None
    assert stored.status == "sent"
    assert stored.human_confirmed is True


@pytest.mark.asyncio
async def test_enqueue_confirmed_comment_persists_before_kernel_handoff(tmp_path, monkeypatch):
    queue = CommentQueue(str(tmp_path / "comment_queue.json"))
    monkeypatch.setattr(comment_engine, "_COMMENT_QUEUE", queue)

    captured = {}

    class FakeKernel:
        def create_marketing_comment_run(self, payload):
            captured.update(payload)
            return {"id": "exec-test"}

    monkeypatch.setattr("szyg.execution_kernel.get_execution_kernel", lambda: FakeKernel())

    result = await comment_engine.enqueue_confirmed_comment(
        "bilibili",
        {
            "video_id": "BV-test",
            "video_title": "英语学习工具体验",
            "video_url": "https://example.com/video",
            "text": "这几款工具分别适合哪个学习阶段？",
        },
        deai=False,
    )

    stored = await queue.get(result["id"])
    assert stored is not None
    assert stored.status == "pending"
    assert stored.human_confirmed is True
    assert stored.metadata["execution_id"] == "exec-test"
    assert captured["queue_item_id"] == stored.id
    assert captured["human_confirmed"] is True


@pytest.mark.asyncio
async def test_delayed_batch_comment_waits_for_worker(tmp_path, monkeypatch):
    queue = CommentQueue(str(tmp_path / "comment_queue.json"))
    monkeypatch.setattr(comment_engine, "_COMMENT_QUEUE", queue)

    class FailingKernel:
        def create_marketing_comment_run(self, _payload):
            raise AssertionError("delayed comments must not start immediately")

    monkeypatch.setattr("szyg.execution_kernel.get_execution_kernel", lambda: FailingKernel())

    result = await comment_engine.enqueue_confirmed_comment(
        "bilibili",
        {
            "video_id": "BV-delayed",
            "video_title": "延后目标",
            "video_url": "https://example.com/video",
            "text": "这个功能适合哪些学习阶段？",
            "batch_id": "batch-test",
        },
        delay_seconds=45,
    )

    stored = await queue.get(result["id"])
    assert stored is not None
    assert stored.status == "delayed"
    assert stored.next_run_at
    assert stored.metadata["batch_id"] == "batch-test"
    assert result["execution_id"] == ""


@pytest.mark.asyncio
async def test_batch_send_preserves_existing_batch_metadata(tmp_path, monkeypatch):
    queue = CommentQueue(str(tmp_path / "comment_queue.json"))
    limiter = CommentRateLimiter(str(tmp_path / "comment_rate_limits.json"))
    monkeypatch.setattr(comment_engine, "_COMMENT_QUEUE", queue)
    monkeypatch.setattr(comment_engine, "_COMMENT_RATE_LIMITER", limiter)

    await queue.add(CommentItem(
        id="batch-item",
        platform="bilibili",
        video_id="BV-batch",
        video_title="获客方法",
        video_url="https://example.com/video",
        comment_text="这个方法适合中小团队吗？",
        original_text="这个方法适合中小团队吗？",
        status="pending",
        human_confirmed=True,
        metadata={"batch_id": "comment_batch_test", "execution_id": "exec-test"},
    ))

    class FakeRegistry:
        def is_registered(self, _platform):
            return True

        async def get(self, _platform):
            return object()

    class FakeAcquisitionAdapter:
        async def send_comment(self, **_kwargs):
            return {"success": True, "comment_id": "remote-batch"}

    monkeypatch.setattr("szyg.platforms.registry.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr(
        "szyg.integrations.acquisition_adapters.get_acquisition_adapter",
        lambda _platform: FakeAcquisitionAdapter(),
    )
    monkeypatch.setattr(comment_engine.random, "uniform", lambda *_args: 0)

    result = await comment_engine.batch_send(
        "bilibili",
        [{
            "queue_item_id": "batch-item",
            "video_id": "BV-batch",
            "video_title": "获客方法",
            "video_url": "https://example.com/video",
            "text": "这个方法适合中小团队吗？",
            "human_confirmed": True,
        }],
        deai=False,
        create_execution=False,
    )

    stored = await queue.get("batch-item")
    assert result[0]["status"] == "sent"
    assert stored is not None
    assert stored.metadata["batch_id"] == "comment_batch_test"
    assert stored.metadata["execution_id"] == "exec-test"


@pytest.mark.asyncio
async def test_comment_queue_archives_old_terminal_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(CommentQueue, "MAX_ACTIVE_BATCHES", 2)
    monkeypatch.setattr(CommentQueue, "MAX_ARCHIVED_BATCHES", 3)
    queue = CommentQueue(
        str(tmp_path / "comment_queue.json"),
        str(tmp_path / "comment_queue_archive.json"),
    )

    for index in range(4):
        await queue.add(CommentItem(
            id=f"sent-{index}",
            platform="bilibili",
            video_id=f"BV-{index}",
            status="sent",
            sent_at=(datetime.now() + timedelta(seconds=index)).isoformat(),
            metadata={"batch_id": f"batch-{index}"},
        ))

    active = await queue.list(limit=10)
    archived = await queue.list_archived(limit=10)

    assert {item.id for item in active} == {"sent-2", "sent-3"}
    assert {item["id"] for item in archived} == {"sent-0", "sent-1"}
    assert queue.archive_stats()["total_batches"] == 2


@pytest.mark.asyncio
async def test_comment_queue_never_archives_unfinished_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(CommentQueue, "MAX_ACTIVE_BATCHES", 1)
    queue = CommentQueue(
        str(tmp_path / "comment_queue.json"),
        str(tmp_path / "comment_queue_archive.json"),
    )
    await queue.add(CommentItem(
        id="pending",
        platform="bilibili",
        status="delayed",
        metadata={"batch_id": "active-batch"},
    ))
    await queue.add(CommentItem(
        id="sent",
        platform="bilibili",
        status="sent",
        metadata={"batch_id": "terminal-batch"},
    ))

    assert await queue.get("pending") is not None
    assert await queue.get("sent") is None
    assert {item["id"] for item in await queue.list_archived()} == {"sent"}


def test_comment_queue_prunes_archive_after_retention_window(tmp_path, monkeypatch):
    monkeypatch.setattr(CommentQueue, "ARCHIVE_RETENTION_DAYS", 180)
    archive_path = tmp_path / "comment_queue_archive.json"
    archive_path.write_text(json.dumps({
        "items": [
            {
                "id": "expired",
                "platform": "bilibili",
                "status": "sent",
                "created_at": (datetime.now() - timedelta(days=181)).isoformat(),
                "metadata": {"batch_id": "expired-batch"},
            },
            {
                "id": "retained",
                "platform": "bilibili",
                "status": "sent",
                "created_at": (datetime.now() - timedelta(days=30)).isoformat(),
                "metadata": {"batch_id": "retained-batch"},
            },
        ]
    }), encoding="utf-8")

    queue = CommentQueue(str(tmp_path / "comment_queue.json"), str(archive_path))

    assert queue.archive_stats()["total_items"] == 1
    assert json.loads(archive_path.read_text(encoding="utf-8"))["items"][0]["id"] == "retained"
