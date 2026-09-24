import asyncio

import pytest

import szyg.integrations.acquisition_adapters as acquisition_adapters
from szyg.intelligence_collectors import CollectorRegistry, PlatformCollector


class FakeAdapter:
    def __init__(self, responses):
        self.responses = responses

    async def search(self, keyword: str, limit: int = 20):
        value = self.responses[keyword]
        if isinstance(value, Exception):
            raise value
        return value[:limit]


@pytest.mark.asyncio
async def test_platform_collector_reports_partial_results(monkeypatch):
    adapter = FakeAdapter({
        "有效词": [{
            "video_id": "item_1",
            "title": "真实公开内容",
            "url": "https://example.com/item_1",
            "likes": 12,
        }],
        "受限词": RuntimeError("login required"),
    })
    monkeypatch.setattr(acquisition_adapters, "get_acquisition_adapter", lambda _platform: adapter)

    result = await PlatformCollector("xhs").collect(
        ["有效词", "受限词"],
        limit=4,
        timeout_seconds=2,
    )

    assert result.health.status == "partial"
    assert result.health.item_count == 1
    assert result.health.successful_queries == 1
    assert result.records[0]["keyword"] == "有效词"
    assert result.errors[0]["keyword"] == "受限词"


@pytest.mark.asyncio
async def test_platform_collector_distinguishes_login_from_empty(monkeypatch):
    class LoginAdapter(FakeAdapter):
        def search_diagnostics(self):
            return {
                "status": "needs_login",
                "error_code": "login_required",
                "message": "需要登录后才能读取公开内容",
            }

    monkeypatch.setattr(
        acquisition_adapters,
        "get_acquisition_adapter",
        lambda _platform: LoginAdapter({"测试": []}),
    )

    result = await PlatformCollector("weibo").collect(
        ["测试"],
        limit=4,
        timeout_seconds=2,
    )

    assert result.health.status == "needs_login"
    assert result.health.error_code == "login_required"
    assert result.health.item_count == 0


@pytest.mark.asyncio
async def test_platform_collector_reports_timeout(monkeypatch):
    class SlowAdapter:
        async def search(self, _keyword: str, limit: int = 20):
            await asyncio.sleep(2)
            return []

    monkeypatch.setattr(acquisition_adapters, "get_acquisition_adapter", lambda _platform: SlowAdapter())

    result = await PlatformCollector("douyin").collect(
        ["测试"],
        limit=4,
        timeout_seconds=1,
    )

    assert result.health.status == "timeout"
    assert result.health.error_code == "collection_timeout"


@pytest.mark.asyncio
async def test_registry_reports_unknown_source_as_unavailable():
    result = await CollectorRegistry().collect_many(
        ["unknown"],
        ["测试"],
        limit=4,
        timeout_seconds=2,
    )

    assert result[0].health.status == "unavailable"
    assert result[0].health.error_code == "collector_unavailable"
