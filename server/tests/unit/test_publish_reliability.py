import asyncio
from unittest.mock import AsyncMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from szyg import execution_kernel as execution
from szyg.integrations import social_auto_upload_adapter as sau
from szyg.integrations.social_auto_upload.utils.publish_submission import (
    PublishVerificationError,
    submit_once,
)


@pytest.mark.parametrize("has_confirmation", [False, True])
async def test_lost_receipt_does_not_replay_submit(has_confirmation):
    page = AsyncMock()
    button = AsyncMock()
    confirmation = AsyncMock() if has_confirmation else None
    page.wait_for_url.side_effect = PlaywrightTimeoutError("receipt lost")

    with pytest.raises(PublishVerificationError):
        await submit_once(page, button, "**/works", confirmation=confirmation)

    button.click.assert_awaited_once()
    if confirmation is not None:
        confirmation.click.assert_awaited_once()


@pytest.fixture
def kernel(monkeypatch, tmp_path):
    for name in ("RUNS", "STEPS", "AUDIT", "OBSERVATIONS", "ASSERTIONS"):
        monkeypatch.setattr(execution, f"{name}_FILE", tmp_path / f"{name}.json")
    return execution.ExecutionKernel()


@pytest.mark.parametrize("platform", ["douyin", "kuaishou", "tencent", "xhs"])
async def test_timeout_cannot_replay_publish(monkeypatch, tmp_path, kernel, platform):
    video = tmp_path / "test.mp4"
    video.touch()
    attempted = asyncio.Event()

    async def timeout_after_submit(**_kwargs):
        attempted.set()
        raise TimeoutError("receipt timed out after submit")

    adapter = AsyncMock()
    adapter.check_login.return_value = {"logged_in": True}
    adapter.upload_video.side_effect = timeout_after_submit
    adapter._publish_timeout_seconds = lambda: 2
    monkeypatch.setattr(sau, "get_sau_adapter", lambda: adapter)
    request = {"platform": platform, "file_path": str(video), "title": "test", "account_id": "owner"}

    run = await kernel.publish_sau(request, is_note=False)
    assert attempted.is_set()
    assert (run["status"], run["error_code"]) == ("needs_human", "verification_uncertain")

    for action in (kernel.resume_run, kernel.retry_run):
        with pytest.raises(ValueError, match="避免重复发布"):
            action(run["id"])
    duplicate = await kernel.publish_sau({**request, "batch_id": "repeated-request"}, is_note=False)
    assert duplicate["id"] == run["id"]
    adapter.upload_video.assert_awaited_once()


@pytest.mark.parametrize(
    ("receipt", "state"),
    [({}, "needs_human"), ({"publish_status": "pending_review", "platform_post_id": "123"}, "needs_human"),
     ({"publish_status": "published", "platform_post_id": "123"}, "success")],
)
async def test_executor_success_needs_platform_evidence(monkeypatch, tmp_path, kernel, receipt, state):
    image = tmp_path / "test.png"
    image.touch()
    adapter = AsyncMock()
    adapter.check_login.return_value = {"logged_in": True}
    adapter.upload_note.return_value = {"success": True, **receipt}
    adapter._publish_timeout_seconds = lambda: 2
    monkeypatch.setattr(sau, "get_sau_adapter", lambda: adapter)

    run = await kernel.publish_sau(
        {"platform": "douyin", "image_paths": [str(image)], "title": "test"}, is_note=True,
    )
    assert run["status"] == state
    assert run["result"]["publish_status"] == receipt.get("publish_status", "submitted")
