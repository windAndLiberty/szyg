"""
Unit tests for szyg.publisher — content publishing pipeline.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from szyg.publisher import (
    Content,
    ContentStatus,
    ContentType,
    Platform,
    PublishRecord,
    Publisher,
)


@pytest.fixture
def publisher(tmp_path: Path):
    """Create a Publisher with isolated temp data files."""
    pub_db = tmp_path / "publisher.json"
    pub_queue = tmp_path / "publish_queue.json"
    pub_log = tmp_path / "publish_log.json"
    pub_db.write_text("[]", encoding="utf-8")
    pub_queue.write_text("[]", encoding="utf-8")
    pub_log.write_text("[]", encoding="utf-8")

    with patch("szyg.publisher.PUBLISH_DB", pub_db), \
         patch("szyg.publisher.PUBLISH_QUEUE", pub_queue), \
         patch("szyg.publisher.PUBLISH_LOG", pub_log), \
         patch("szyg.publisher._resolve", side_effect=lambda p: p):
        yield Publisher()


class TestContentModel:
    def test_default_construction(self):
        c = Content(title="Test Post")
        assert c.title == "Test Post"
        assert c.content_type == ContentType.POST
        assert c.status == ContentStatus.DRAFT
        assert c.body == ""
        assert c.media_urls == []
        assert c.platforms == [Platform.ALL]
        assert c.tags == []
        assert c.ai_generated is False
        assert len(c.id) == 8

    def test_custom_fields(self):
        c = Content(
            title="Video Script",
            content_type=ContentType.VIDEO_SCRIPT,
            body="Script content here",
            platforms=[Platform.DOUYIN, Platform.XHS],
            tags=["ai", "video"],
            ai_generated=True,
            ai_agent_id="copywriter",
        )
        assert c.content_type == ContentType.VIDEO_SCRIPT
        assert Platform.DOUYIN in c.platforms
        assert "ai" in c.tags
        assert c.ai_generated is True


class TestPublishRecordModel:
    def test_construction(self):
        r = PublishRecord(id="r1", content_id="c1", platform=Platform.DOUYIN)
        assert r.id == "r1"
        assert r.content_id == "c1"
        assert r.platform == Platform.DOUYIN
        assert r.status == "pending"
        assert r.error_msg == ""


class TestContentTypeEnum:
    def test_values(self):
        assert ContentType.POST == "post"
        assert ContentType.ARTICLE == "article"
        assert ContentType.VIDEO_SCRIPT == "video"
        assert ContentType.IMAGE_POST == "image"


class TestContentStatusEnum:
    def test_values(self):
        assert ContentStatus.DRAFT == "draft"
        assert ContentStatus.PENDING == "pending"
        assert ContentStatus.APPROVED == "approved"
        assert ContentStatus.PUBLISHED == "published"
        assert ContentStatus.REJECTED == "rejected"
        assert ContentStatus.ARCHIVED == "archived"


class TestPlatformEnum:
    def test_values(self):
        assert Platform.WECHAT_MP == "wechat_mp"
        assert Platform.DOUYIN == "douyin"
        assert Platform.XHS == "xhs"
        assert Platform.BILIBILI == "bilibili"
        assert Platform.ALL == "all"


class TestPublisherCreate:
    def test_create_content(self, publisher: Publisher):
        c = publisher.create(title="New Post", body="Hello world")
        assert c.title == "New Post"
        assert c.body == "Hello world"
        assert c.status == ContentStatus.DRAFT

    def test_create_multiple(self, publisher: Publisher):
        publisher.create(title="Post 1")
        publisher.create(title="Post 2")
        items = publisher.list_contents()
        assert len(items) == 2


class TestPublisherListContents:
    def test_empty_list(self, publisher: Publisher):
        assert publisher.list_contents() == []

    def test_filter_by_status(self, publisher: Publisher):
        publisher.create(title="Draft", status=ContentStatus.DRAFT)
        publisher.create(title="Published", status=ContentStatus.PUBLISHED)
        drafts = publisher.list_contents(status="draft")
        assert len(drafts) == 1
        assert drafts[0].title == "Draft"

    def test_filter_by_content_type(self, publisher: Publisher):
        publisher.create(title="Post", content_type=ContentType.POST)
        publisher.create(title="Video", content_type=ContentType.VIDEO_SCRIPT)
        videos = publisher.list_contents(content_type="video")
        assert len(videos) == 1
        assert videos[0].title == "Video"

    def test_search_by_title(self, publisher: Publisher):
        publisher.create(title="AI Marketing", body="content")
        publisher.create(title="Manual Work", body="other")
        results = publisher.list_contents(search="ai")
        assert len(results) == 1
        assert results[0].title == "AI Marketing"

    def test_search_by_body(self, publisher: Publisher):
        publisher.create(title="Title", body="machine learning is great")
        publisher.create(title="Other", body="cooking recipe")
        results = publisher.list_contents(search="machine")
        assert len(results) == 1

    def test_limit(self, publisher: Publisher):
        for i in range(10):
            publisher.create(title=f"Post {i}")
        results = publisher.list_contents(limit=3)
        assert len(results) == 3


class TestPublisherGetContent:
    def test_get_existing(self, publisher: Publisher):
        c = publisher.create(title="Find Me")
        found = publisher.get_content(c.id)
        assert found is not None
        assert found.title == "Find Me"

    def test_get_nonexistent(self, publisher: Publisher):
        assert publisher.get_content("nonexistent_id") is None


class TestPublisherUpdate:
    def test_update_title(self, publisher: Publisher):
        c = publisher.create(title="Original")
        updated = publisher.update(c.id, title="Updated")
        assert updated is not None
        assert updated.title == "Updated"

    def test_update_nonexistent(self, publisher: Publisher):
        result = publisher.update("no_such_id", title="X")
        assert result is None

    def test_update_sets_updated_at(self, publisher: Publisher):
        c = publisher.create(title="Track Time")
        original_time = c.updated_at
        updated = publisher.update(c.id, body="new body")
        assert updated.updated_at >= original_time


class TestPublisherDelete:
    def test_delete_existing(self, publisher: Publisher):
        c = publisher.create(title="Delete Me")
        assert publisher.delete(c.id) is True
        assert publisher.get_content(c.id) is None

    def test_delete_nonexistent(self, publisher: Publisher):
        assert publisher.delete("nope") is False


class TestPublisherReviewPipeline:
    def test_submit_review(self, publisher: Publisher):
        c = publisher.create(title="Review Me")
        result = publisher.submit_review(c.id)
        assert result.status == ContentStatus.PENDING

    def test_approve(self, publisher: Publisher):
        c = publisher.create(title="Approve Me")
        publisher.submit_review(c.id)
        result = publisher.approve(c.id, comment="Looks good!")
        assert result.status == ContentStatus.APPROVED
        assert result.review_comment == "Looks good!"

    def test_reject(self, publisher: Publisher):
        c = publisher.create(title="Reject Me")
        publisher.submit_review(c.id)
        result = publisher.reject(c.id, comment="Needs work")
        assert result.status == ContentStatus.REJECTED
        assert result.review_comment == "Needs work"


class TestPublisherSchedule:
    def test_schedule_content(self, publisher: Publisher):
        c = publisher.create(title="Scheduled Post")
        result = publisher.schedule(c.id, "2024-12-31T10:00:00")
        assert result.scheduled_at == "2024-12-31T10:00:00"
        assert result.status == ContentStatus.APPROVED
