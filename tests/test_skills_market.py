import pytest

from szyg.api import skills_routes


def test_clawhub_item_hides_technical_market_fields():
    item = skills_routes._clawhub_item(
        {
            "slug": "meeting-notes",
            "displayName": "Meeting Notes",
            "summary": "Turn meetings into summaries and follow-up tasks.",
            "topics": ["meeting", "productivity"],
            "stats": {"downloads": 1200, "installs": 30, "stars": 4},
            "metadata": {"setup": []},
        },
        "office",
    )

    assert item is not None
    assert item["description"] == "帮助安排日程、整理会议内容和后续待办。"
    assert item["category_label"] == "办公提效"
    assert item["downloads"] == 1200
    assert "source" not in item
    assert "trust_level" not in item


def test_clawhub_item_filters_high_risk_irrelevant_skills():
    item = skills_routes._clawhub_item(
        {
            "slug": "crypto-wallet-helper",
            "displayName": "Crypto Wallet Helper",
            "summary": "Manage wallet credentials.",
        },
        "recommended",
    )

    assert item is None


@pytest.mark.asyncio
async def test_market_list_returns_external_business_catalog_only(monkeypatch):
    skills_routes._market_cache.clear()
    result = await skills_routes.market_list(category="marketing", page_size=20)

    assert result["total"] >= 4
    assert {item["identifier"] for item in result["items"]} >= {
        "marketing-analytics",
        "customer-persona-copy-map",
        "ecommerce-aftersales-reply",
        "social-media-content-calendar",
    }
    assert all(item["ready_to_use"] is True for item in result["items"])
    assert {item["id"] for item in result["categories"]} >= {"recommended", "office", "marketing"}


def test_curated_catalog_has_chinese_names_and_no_email_skills():
    assert len(skills_routes._INSTALL_READY_CATALOG) == 19
    for identifier, item in skills_routes._INSTALL_READY_CATALOG.items():
        assert any("\u4e00" <= char <= "\u9fff" for char in item["name"])
        assert "email" not in identifier.lower()


class FakeBundle:
    def __init__(self, skill_md: str, files=None):
        self.files = {"SKILL.md": skill_md, **(files or {})}


def test_install_ready_rejects_api_key_dependency():
    ok, reason = skills_routes._validate_install_ready_bundle(
        "bing-search-cn",
        FakeBundle("Set EVOLINK_API_KEY before use."),
    )
    assert ok is False
    assert "密钥" in reason


def test_install_ready_rejects_extra_setup():
    ok, reason = skills_routes._validate_install_ready_bundle(
        "bing-search-cn",
        FakeBundle("Run pip install duckduckgo-search before use."),
    )
    assert ok is False
    assert "额外安装" in reason


def test_install_ready_accepts_bing_skill_without_api_key():
    ok, reason = skills_routes._validate_install_ready_bundle(
        "bing-search-cn",
        FakeBundle("Use the included bing-search.js file. No API key is required.", {"bing-search.js": ""}),
    )
    assert ok is True
    assert reason == "添加后即可使用"


def test_install_resolver_skips_search_only_source(monkeypatch):
    meta = object()
    bundle = FakeBundle("Use web_fetch directly.")

    class SearchOnlySource:
        def inspect(self, identifier):
            return meta

        def fetch(self, identifier):
            return None

    class DownloadSource:
        def inspect(self, identifier):
            return meta

        def fetch(self, identifier):
            return bundle

    monkeypatch.setattr(
        skills_routes,
        "_get_source_router",
        lambda: [SearchOnlySource(), DownloadSource()],
    )

    resolved_meta, resolved_bundle = skills_routes._resolve_install_bundle("bing-search-cn")
    assert resolved_meta is meta
    assert resolved_bundle is bundle
