import pytest

from szyg.comment_engine import MarketingAutomationPolicy
from szyg.integrations.acquisition_adapters import (
    BilibiliAcquisitionAdapter,
    PlaywrightAcquisitionAdapter,
)
from szyg.intercept_engine import InterceptEngine


def test_douyin_api_comments_are_normalized():
    rows = PlaywrightAcquisitionAdapter._normalize_douyin_api_comments([{
        "cid": "comment-1",
        "text": "这个功能适合零基础吗？",
        "user": {"nickname": "学习者", "uid": "user-1"},
        "digg_count": 12,
        "reply_comment_total": 3,
        "create_time": 123,
    }])

    assert rows == [{
        "comment_id": "comment-1",
        "platform": "douyin",
        "author": "学习者",
        "author_id": "user-1",
        "text": "这个功能适合零基础吗？",
        "likes": 12,
        "reply_count": 3,
        "replies": 0,
        "ip_location": "",
        "created_at": 123,
    }]


def test_kuaishou_search_response_is_normalized():
    rows = PlaywrightAcquisitionAdapter._normalize_kuaishou_search_payload({
        "data": {
            "visionSearchPhoto": {
                "result": 1,
                "feeds": [{
                    "photo": {
                        "id": "photo-1",
                        "caption": "AI 英语学习体验",
                        "coverUrl": "https://example.com/cover.jpg",
                        "viewCount": 88,
                        "realLikeCount": 9,
                        "commentCount": 4,
                    },
                    "author": {"name": "英语老师"},
                }],
            }
        }
    })

    assert rows[0]["video_id"] == "photo-1"
    assert rows[0]["author"] == "英语老师"
    assert rows[0]["url"] == "https://www.kuaishou.com/short-video/photo-1"
    assert rows[0]["comments_count"] == 4


def test_kuaishou_comments_response_is_normalized():
    rows = PlaywrightAcquisitionAdapter._normalize_kuaishou_api_comments({
        "rootCommentsV2": [{
            "comment_id": 123,
            "author_name": "用户甲",
            "author_id": "u1",
            "content": "每天练习多久比较合适？",
            "like_count": 5,
            "commentCount": 2,
            "timestamp": 456,
        }]
    })

    assert rows[0]["comment_id"] == "123"
    assert rows[0]["text"] == "每天练习多久比较合适？"
    assert rows[0]["reply_count"] == 2


def test_bilibili_credential_can_be_invalidated():
    adapter = BilibiliAcquisitionAdapter()
    adapter._credential = object()
    adapter._cred_ready = True

    adapter._invalidate_credential()

    assert adapter._credential is None
    assert adapter._cred_ready is False


def test_unverified_send_is_retryable():
    result = MarketingAutomationPolicy.classify_send_error("发送结果未确认，任务未标记为成功")

    assert result == {
        "decision": "delay_retry",
        "status": "retrying",
        "code": "send_unverified",
    }


class _FakeLocator:
    @property
    def first(self):
        return self

    async def count(self):
        return 0

    async def is_visible(self):
        return False


class _FakeInput:
    async def fill(self, _text):
        return None


class _FakeResponse:
    url = "https://example.com/comment/publish"

    async def json(self):
        return {"status_code": 0}


class _FakeButton:
    def __init__(self, page, emit_success):
        self.page = page
        self.emit_success = emit_success

    async def click(self):
        if self.emit_success:
            for handler in list(self.page.handlers):
                await handler(_FakeResponse())


class _FakePage:
    url = "https://example.com/video/1"

    def __init__(self, emit_success=False):
        self.handlers = []
        self.emit_success = emit_success

    def on(self, _event, handler):
        self.handlers.append(handler)

    def remove_listener(self, _event, handler):
        if handler in self.handlers:
            self.handlers.remove(handler)

    async def wait_for_selector(self, _selector, timeout=0):
        return _FakeInput()

    async def query_selector(self, _selector):
        return _FakeButton(self, self.emit_success)

    async def wait_for_timeout(self, _timeout):
        return None

    def get_by_text(self, _text, exact=False):
        return _FakeLocator()


@pytest.mark.asyncio
async def test_browser_send_requires_positive_evidence():
    adapter = PlaywrightAcquisitionAdapter("douyin")

    result = await adapter._submit_comment_with_evidence(
        _FakePage(emit_success=False),
        "这个角度很有意思",
        "textarea",
        "button",
    )

    assert result["success"] is False
    assert result["error_code"] == "send_unverified"


@pytest.mark.asyncio
async def test_browser_send_accepts_platform_response_evidence():
    adapter = PlaywrightAcquisitionAdapter("kuaishou")

    result = await adapter._submit_comment_with_evidence(
        _FakePage(emit_success=True),
        "这个角度很有意思",
        "textarea",
        "button",
    )

    assert result["success"] is True
    assert result["evidence"]["type"] == "platform_response"


@pytest.mark.asyncio
async def test_intercept_search_excludes_results_without_video_id(monkeypatch):
    engine = InterceptEngine()

    async def fake_search(_platform, _keyword, _limit):
        return [
            {"video_id": "", "title": "不可评论的聚合页", "url": "https://example.com/course"},
            {"video_id": "video-1", "title": "可评论视频", "url": "https://example.com/video/1"},
        ]

    monkeypatch.setattr(engine, "_search_platform", fake_search)

    results = await engine.search("AI 英语", ["bilibili"], limit=5, strict_dedup=False)

    assert [item.video_id for item in results[0].videos] == ["video-1"]
