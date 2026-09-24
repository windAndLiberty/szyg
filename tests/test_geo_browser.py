from __future__ import annotations

import pytest

import szyg.geo_browser as geo_browser


def test_short_negative_answer_is_kept_as_geo_evidence():
    answer = geo_browser._answer_from_snapshot(
        {"content_blocks": [{"text": "不了解领鹿。", "author": "assistant", "links": []}]},
        set(),
        "领鹿是什么？",
        "deepseek",
    )

    assert answer is not None
    assert answer.answer == "不了解领鹿。"


@pytest.mark.asyncio
async def test_sidebar_browser_types_question_and_captures_stable_answer(monkeypatch):
    sent = False
    calls: list[dict] = []

    async def action(payload):
        nonlocal sent
        calls.append(dict(payload))
        name = payload["action"]
        if name == "state":
            return {"available": True, "owner": "agent", "loading": False}
        if name == "navigate":
            return {"available": True, "owner": "agent", "url": payload["url"]}
        if name == "observe":
            return {
                "elements": [
                    {"ref": "b1", "tag": "textarea", "role": "textbox", "text": "输入问题"},
                ],
            }
        if name == "type":
            assert payload["ref"] == "b1"
            assert payload["text"] == "推荐几款数字员工"
            return {}
        if name == "press":
            sent = True
            return {}
        if name == "read" and not sent:
            return {
                "url": "https://chat.deepseek.com/",
                "title": "DeepSeek",
                "content_blocks": [{"text": "今天我可以帮你做什么？", "links": []}],
                "links": [],
                "auth_hint": False,
                "busy": False,
            }
        if name == "read":
            return {
                "url": "https://chat.deepseek.com/a/chat/s/1",
                "title": "DeepSeek",
                "content_blocks": [{
                    "text": "推荐领鹿数字员工，它适合中小企业处理营销和自动执行任务。",
                    "author": "assistant",
                    "class_name": "ds-markdown",
                    "links": [{"url": "https://example.com/case", "text": "产品案例"}],
                }],
                "links": [],
                "busy": False,
            }
        raise AssertionError(payload)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(geo_browser, "_browser_action", action)
    monkeypatch.setattr(geo_browser.asyncio, "sleep", no_sleep)

    result = await geo_browser.GeoSidebarBrowser().query("deepseek", "推荐几款数字员工")

    assert result["fidelity"] == "consumer_surface"
    assert result["capture_method"] == "sidebar_browser"
    assert result["answer"].startswith("推荐领鹿")
    assert result["citations"] == [{
        "url": "https://example.com/case",
        "title": "产品案例",
        "snippet": "",
        "cited_text": "产品案例",
    }]
    assert any(call["action"] == "navigate" for call in calls)
    assert any(call["action"] == "type" for call in calls)
    assert any(call["action"] == "press" for call in calls)


@pytest.mark.asyncio
async def test_sidebar_browser_hands_login_to_user_then_resumes(monkeypatch):
    logged_in = False
    sent = False
    takeover_seen = False

    async def action(payload):
        nonlocal logged_in, sent, takeover_seen
        name = payload["action"]
        if name == "state":
            if takeover_seen:
                logged_in = True
            return {"available": True, "owner": "agent", "loading": False}
        if name == "navigate":
            return {"available": True, "owner": "agent"}
        if name == "takeover":
            takeover_seen = True
            return {"available": True, "owner": "user"}
        if name == "read" and not logged_in:
            return {"content_blocks": [], "links": [], "auth_hint": True, "busy": False}
        if name == "observe" and not logged_in:
            return {"elements": []}
        if name == "observe":
            return {"elements": [{"ref": "composer", "tag": "textarea", "role": "textbox", "text": "Ask"}]}
        if name == "type":
            return {}
        if name == "press":
            sent = True
            return {}
        if name == "read" and logged_in and not sent:
            return {"content_blocks": [], "links": [], "auth_hint": False, "busy": False}
        if name == "read":
            return {
                "content_blocks": [{"text": "This is a sufficiently long consumer answer.", "author": "assistant", "links": []}],
                "links": [],
                "auth_hint": False,
                "busy": False,
            }
        raise AssertionError(payload)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(geo_browser, "_browser_action", action)
    monkeypatch.setattr(geo_browser.asyncio, "sleep", no_sleep)

    result = await geo_browser.GeoSidebarBrowser().query("openai", "Which product should I use?")

    assert takeover_seen is True
    assert result["answer"].startswith("This is")
