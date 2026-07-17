import pytest

from szyg.comment_engine import (
    CommentItem,
    CommentQueue,
    CommentRateLimiter,
    MarketingAutomationPolicy,
    preflight_check,
    repair_comment,
)


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
    ))
    await queue.add(CommentItem(
        id="future",
        platform="douyin",
        status="delayed",
        next_run_at="2999-01-01T00:00:00",
    ))

    due = await queue.due()

    assert [item.id for item in due] == ["due"]
