import pytest
from fastapi import HTTPException

from szyg.api import acquisition_routes
from szyg.comment_engine import CommentItem, _activate_reply_monitor
from szyg.intercept_engine import VideoTarget


@pytest.mark.asyncio
async def test_campaign_plan_generates_a_distinct_comment_per_real_target(monkeypatch):
    async def fake_brief(_objective, _platforms):
        return {"search_query": "门店客流", "audience": "门店老板", "engagement_angle": "给出实用建议", "source": "agent"}

    class FakeEngine:
        async def find_targets(self, *_args, **_kwargs):
            return [
                VideoTarget(platform="douyin", video_id="v1", title="门店没客流怎么办", url="https://example.com/v1", quality_score=80),
                VideoTarget(platform="bilibili", video_id="v2", title="线下生意转线上", url="https://example.com/v2", quality_score=70),
            ]

    async def fake_generate(title, *_args, **_kwargs):
        return [f"关于{title}，可以先从老客户复购开始"]

    monkeypatch.setattr(acquisition_routes, "_campaign_brief", fake_brief)
    monkeypatch.setattr(acquisition_routes, "_get_intercept", lambda: FakeEngine())
    monkeypatch.setattr("szyg.comment_engine.generate_comments_with_llm", fake_generate)
    monkeypatch.setattr("szyg.channel_accounts.get_default_account_for_platform", lambda platform: {
        "id": f"{platform}-account", "platform": platform, "label": f"{platform}经营号",
        "status": "connected", "session": {"valid": True},
    })

    result = await acquisition_routes.plan_comment_campaign(acquisition_routes.CommentCampaignPlanRequest(
        objective="寻找需要线上获客的门店老板", platforms=["douyin", "bilibili"], max_targets=2,
    ))

    assert result["total"] == 2
    assert result["items"][0]["comment_text"] != result["items"][1]["comment_text"]
    assert all(item["account_ready"] for item in result["items"])
    assert {item["video_id"] for item in result["items"]} == {"v1", "v2"}


@pytest.mark.asyncio
async def test_campaign_execute_requires_batch_confirmation():
    with pytest.raises(HTTPException) as exc:
        await acquisition_routes.execute_comment_campaign(acquisition_routes.CommentCampaignExecuteRequest(
            confirmed=False,
            items=[acquisition_routes.CommentCampaignItem(
                platform="douyin", account_id="a1", video_title="测试", video_url="https://example.com/v1", comment_text="这个思路很实用",
            )],
        ))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_campaign_execute_links_account_and_defers_monitoring_until_send(monkeypatch):
    captured = []

    async def fake_enqueue(platform, payload, **kwargs):
        captured.append((platform, payload, kwargs))
        return {"id": "q1", "execution_id": "r1", "status": "pending"}

    monkeypatch.setattr("szyg.channel_accounts.get_account", lambda _account_id: {
        "id": "a1", "platform": "douyin", "label": "门店经营号",
        "status": "connected", "session": {"valid": True},
    })
    monkeypatch.setattr("szyg.comment_engine.enqueue_confirmed_comment", fake_enqueue)

    result = await acquisition_routes.execute_comment_campaign(acquisition_routes.CommentCampaignExecuteRequest(
        confirmed=True, monitor_replies=True,
        items=[acquisition_routes.CommentCampaignItem(
            platform="douyin", account_id="a1", video_id="v1", video_title="门店经营",
            video_url="https://example.com/v1", comment_text="可以先统计老客户常问的问题，再逐个优化",
        )],
    ))

    assert result["monitoring_state"] == "starts_after_verified_send"
    assert captured[0][1]["account_id"] == "a1"
    assert captured[0][1]["monitor_replies"] is True


@pytest.mark.asyncio
async def test_verified_send_activates_exact_reply_thread_monitor(monkeypatch):
    added = []

    class FakeQueue:
        async def update(self, *_args, **_kwargs):
            return None

    class FakeIntercept:
        async def mark_commented(self, platform, video_id):
            assert (platform, video_id) == ("douyin", "v1")

    class FakeListen:
        async def list_targets(self): return []
        async def add_target(self, target): added.append(target)
        async def start(self, _interval): return None

    monkeypatch.setattr("szyg.intercept_engine.get_intercept_engine", lambda: FakeIntercept())
    monkeypatch.setattr("szyg.listen_engine.get_listen_engine", lambda: FakeListen())
    monkeypatch.setattr("szyg.channel_accounts.get_account", lambda _account_id: {
        "platform_user_id": "owner-1", "nickname": "门店经营号",
    })
    monkeypatch.setattr("szyg.comment_engine.get_comment_queue", lambda: FakeQueue())

    result = await _activate_reply_monitor(CommentItem(
        id="q1", platform="douyin", video_id="v1", video_title="门店经营",
        video_url="https://example.com/v1", account_id="a1",
        comment_text="可以先统计老客户常问的问题",
        metadata={"monitor_replies": True}, status="sent",
        platform_result={"comment_id": "comment-1"},
    ))

    assert result == {"status": "active", "comment_id": "comment-1"}
    assert len(added) == 1
    assert added[0].owner == "comment_campaign"
    assert added[0].video_id == "v1"
    assert added[0].monitoring_mode == "reply_thread"
    assert added[0].outbound_comment_id == "comment-1"
    assert added[0].outbound_author_id == "owner-1"
    assert added[0].outbound_author_name == "门店经营号"


@pytest.mark.asyncio
async def test_send_without_comment_id_does_not_monitor_whole_video(monkeypatch):
    added = []
    updates = []

    class FakeQueue:
        async def update(self, item_id, **kwargs):
            updates.append((item_id, kwargs))

    class FakeListen:
        async def list_targets(self): return []
        async def add_target(self, target): added.append(target)
        async def start(self, _interval): return None

    monkeypatch.setattr("szyg.comment_engine.get_comment_queue", lambda: FakeQueue())
    monkeypatch.setattr("szyg.listen_engine.get_listen_engine", lambda: FakeListen())
    monkeypatch.setattr("szyg.intercept_engine.get_intercept_engine", lambda: type("FakeIntercept", (), {
        "mark_commented": lambda self, *_args: _async_none(),
    })())

    result = await _activate_reply_monitor(CommentItem(
        id="q2", platform="xhs", video_id="n1", video_url="https://example.com/n1",
        metadata={"monitor_replies": True}, status="sent",
        platform_result={"evidence": {"type": "visible_confirmation"}},
    ))

    assert result["status"] == "unavailable"
    assert added == []
    assert updates[0][1]["metadata"]["reply_monitoring"]["status"] == "unavailable"


async def _async_none():
    return None
