import asyncio

import pytest
from fastapi import FastAPI

from szyg.background_workers import _profile_sync_eligible, configure_background_workers
from szyg.comment_engine import CommentItem, process_due_comments
from szyg.listen_engine import ListenEngine, MonitorTarget


@pytest.mark.asyncio
async def test_due_comment_keeps_selected_account(monkeypatch):
    captured = []

    class FakeQueue:
        async def due(self, _limit):
            return [CommentItem(
                id="q1", platform="douyin", account_id="account-7",
                video_id="v1", video_url="https://example.com/v1",
                comment_text="这条内容很有启发", status="retrying",
            )]

        async def update(self, *_args, **_kwargs):
            return None

    class FakeKernel:
        def create_marketing_comment_run(self, payload):
            captured.append(payload)
            return {"id": "run-1"}

    monkeypatch.setattr("szyg.comment_engine.get_comment_queue", lambda: FakeQueue())
    monkeypatch.setattr("szyg.execution_kernel.get_execution_kernel", lambda: FakeKernel())

    result = await process_due_comments(limit=1)

    assert result["processed"] == 1
    assert captured[0]["account_id"] == "account-7"


@pytest.mark.asyncio
async def test_execution_kernel_passes_selected_account_to_sender(tmp_path, monkeypatch):
    import szyg.execution_kernel as kernel_mod

    for name in ("RUNS_FILE", "STEPS_FILE", "AUDIT_FILE", "OBSERVATIONS_FILE", "ASSERTIONS_FILE"):
        monkeypatch.setattr(kernel_mod, name, tmp_path / f"{name.lower()}.json")
    monkeypatch.setattr(kernel_mod, "_kernel", None)
    captured = []

    async def fake_batch_send(_platform, comments, *_args, **_kwargs):
        captured.extend(comments)
        return [{"status": "sent", "decision": "auto_send"}]

    monkeypatch.setattr("szyg.comment_engine.batch_send", fake_batch_send)
    kernel = kernel_mod.get_execution_kernel()
    run = kernel.create_run("marketing_comment", "douyin", "browser", {
        "platform": "douyin", "account_id": "account-9", "video_id": "v9",
        "video_url": "https://example.com/v9", "text": "这条建议很实用",
        "human_confirmed": True,
    })

    await kernel.run_marketing_comment(run["id"])

    assert captured[0]["account_id"] == "account-9"
    assert kernel.get_run(run["id"])["status"] == "success"


@pytest.mark.asyncio
async def test_business_workers_follow_fastapi_lifecycle():
    app = FastAPI()
    configure_background_workers(app)

    for handler in app.router.on_startup:
        await handler()

    workers = app.state.business_workers
    assert {task.get_name() for task in workers} == {
        "comment-retry-worker",
        "account-profile-sync-worker",
        "geo-audit-worker",
    }
    assert all(not task.done() for task in workers)

    for handler in app.router.on_shutdown:
        await handler()

    assert app.state.business_workers == []
    assert all(task.cancelled() for task in workers)


def test_profile_sync_includes_manual_desktop_channel_but_not_unsupported_account():
    assert _profile_sync_eligible({
        "platform": "tencent", "enabled": True, "status": "connected",
        "session": {"valid": False},
    }) is True
    assert _profile_sync_eligible({
        "platform": "wechat_mp", "enabled": True, "status": "connected",
        "session": {"valid": True},
    }) is False


@pytest.mark.asyncio
async def test_exact_reply_monitor_uses_normal_adapter_path_and_deduplicates(monkeypatch):
    engine = ListenEngine()
    engine._targets = {}
    engine._leads = {}
    monkeypatch.setattr(engine, "_save_targets", lambda: None)
    monkeypatch.setattr(engine, "_save_leads", lambda: None)

    calls = []

    class FakeAdapter:
        async def get_comment_replies(self, video_url, comment_id, limit=30):
            calls.append((video_url, comment_id, limit))
            return [{
                "comment_id": "reply-1",
                "root_comment_id": "outbound-1",
                "author": "潜在客户",
                "author_id": "lead-1",
                "text": "多少钱，怎么联系？",
            }]

        async def get_comments(self, *_args, **_kwargs):
            raise AssertionError("精确监听不应退化为整条视频评论读取")

    monkeypatch.setattr(
        "szyg.integrations.acquisition_adapters.get_acquisition_adapter",
        lambda _platform: FakeAdapter(),
    )
    target = MonitorTarget(
        target_id="target-1", platform="douyin", video_id="v1",
        video_url="https://example.com/v1", owner="comment_campaign",
        outbound_comment_id="outbound-1", outbound_author_id="owner-1",
        monitoring_mode="reply_thread",
    )
    engine._targets[target.target_id] = target

    await engine._poll_target(target)
    await engine._poll_target(target)

    assert calls == [
        ("https://example.com/v1", "outbound-1", 50),
        ("https://example.com/v1", "outbound-1", 50),
    ]
    assert len(engine._leads) == 1
    lead = next(iter(engine._leads.values()))
    assert lead.author_id == "lead-1"
    assert lead.grade == "A"
    assert target.seen_comment_ids == ["reply-1"]
