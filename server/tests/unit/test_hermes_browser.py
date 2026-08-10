from __future__ import annotations

import pytest

from szyg import hermes_browser


@pytest.mark.asyncio
async def test_browser_click_without_sensitive_meaning_runs_without_approval(monkeypatch):
    async def fake_action(payload):
        assert payload == {"action": "observe"}
        return {"elements": [{"ref": "b1", "text": "查看详情", "role": "link"}]}

    monkeypatch.setattr(hermes_browser, "_browser_action", fake_action)
    called = False

    def approval(*_args):
        nonlocal called
        called = True
        return "deny"

    allowed = await hermes_browser._approval_for_target(
        {"action": "click", "ref": "b1"}, approval
    )

    assert allowed is True
    assert called is False


@pytest.mark.asyncio
async def test_browser_publish_action_requires_user_approval(monkeypatch):
    async def fake_action(_payload):
        return {"elements": [{"ref": "b9", "text": "确认发布", "role": "button"}]}

    monkeypatch.setattr(hermes_browser, "_browser_action", fake_action)
    requests = []

    def approval(action, payload, summary):
        requests.append((action, payload, summary))
        return "approve_once"

    allowed = await hermes_browser._approval_for_target(
        {"action": "click", "ref": "b9"}, approval
    )

    assert allowed is True
    assert requests == [
        ("browser.click", {"action": "click", "ref": "b9"}, "确认网页操作")
    ]


@pytest.mark.asyncio
async def test_browser_sensitive_action_is_denied_without_approval_channel(monkeypatch):
    async def fake_action(_payload):
        return {"elements": [{"ref": "b2", "text": "删除账号", "role": "button"}]}

    monkeypatch.setattr(hermes_browser, "_browser_action", fake_action)

    assert await hermes_browser._approval_for_target(
        {"action": "click", "ref": "b2"}, None
    ) is False
