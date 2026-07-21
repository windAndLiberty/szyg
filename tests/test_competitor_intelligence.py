import asyncio
import json

import szyg.competitor_intelligence as intel


def _isolate_intelligence(tmp_path, monkeypatch):
    monkeypatch.setattr(intel, "COMPETITOR_FILE", tmp_path / "competitor_accounts.json")
    monkeypatch.setattr(intel, "BUSINESS_PROFILE_FILE", tmp_path / "intelligence_business_profiles.json")
    monkeypatch.setattr(intel, "DISCOVERY_FILE", tmp_path / "intelligence_discoveries.json")
    monkeypatch.setattr(intel, "BRIEF_FILE", tmp_path / "intelligence_content_briefs.json")
    monkeypatch.setattr(intel, "SNAPSHOT_FILE", tmp_path / "intelligence_snapshots.json")
    monkeypatch.setattr(intel, "SOURCE_FILE", tmp_path / "intelligence_sources.json")
    monkeypatch.setattr(intel, "MARKET_NEWS_FILE", tmp_path / "intelligence_market_news.json")


def _fake_bilibili_json(url: str, referer: str = "") -> dict:
    if "web-interface/card" in url:
        return {
            "code": 0,
            "data": {
                "card": {
                    "mid": "281143686",
                    "name": "打工喵i",
                    "face": "https://i0.hdslb.com/bfs/face/avatar.jpg",
                    "fans": 71000,
                    "attention": 1037,
                    "sign": "制作不易",
                }
            },
        }
    if "relation/stat" in url:
        return {"code": 0, "data": {"follower": 71056, "following": 1037}}
    return {"code": -404}


def test_bilibili_competitor_sync_enriches_account(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)
    monkeypatch.setattr(intel, "_fetch_json", _fake_bilibili_json)
    monkeypatch.setattr(
        intel,
        "_bilibili_recent_items_by_author",
        lambda name, mid, limit=5: [
            {
                "id": "recent_BV1",
                "title": "当我试图驯服AI做短剧",
                "url": "https://www.bilibili.com/video/BV1/",
                "plays": 1200,
                "likes": 90,
                "comments_count": 12,
            }
        ],
    )

    row = intel.create_competitor({
        "profile_url": "https://space.bilibili.com/281143686",
        "platform": "bilibili",
        "name": "待同步账号",
    })
    synced = intel.sync_competitor(row["id"])

    assert synced["sync_status"] == "success"
    assert synced["name"] == "打工喵i"
    assert synced["profile_url"] == "https://space.bilibili.com/281143686"
    assert synced["avatar_url"].endswith("avatar.jpg")
    assert synced["followers"] == 71056
    assert synced["following"] == 1037
    assert synced["recent_items"][0]["title"] == "当我试图驯服AI做短剧"
    assert intel.overview()["synced_competitors"] == 1
    snapshots = json.loads((tmp_path / "intelligence_snapshots.json").read_text(encoding="utf-8"))
    assert snapshots[0]["entity_id"] == row["id"]
    assert snapshots[0]["followers"] == 71056


def test_sync_competitors_filters_platform(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)
    monkeypatch.setattr(intel, "_fetch_json", _fake_bilibili_json)
    monkeypatch.setattr(intel, "_bilibili_recent_items_by_author", lambda name, mid, limit=5: [])

    intel.create_competitor({
        "profile_url": "https://space.bilibili.com/281143686",
        "platform": "bilibili",
        "name": "B站账号",
    })
    intel.create_competitor({
        "profile_url": "https://example.com/account",
        "platform": "weibo",
        "name": "微博账号",
    })

    rows = intel.sync_competitors(platform="bilibili", limit=10)

    assert len(rows) == 1
    assert rows[0]["platform"] == "bilibili"
    stored = json.loads((tmp_path / "competitor_accounts.json").read_text(encoding="utf-8"))
    assert len(stored) == 2


def test_accept_bilibili_candidate_syncs_immediately(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)
    monkeypatch.setattr(intel, "_fetch_json", _fake_bilibili_json)
    monkeypatch.setattr(
        intel,
        "_bilibili_recent_items_by_author",
        lambda name, mid, limit=5: [{"id": "recent_BV2", "title": "近期作品", "url": "https://www.bilibili.com/video/BV2/"}],
    )

    discovery = {
        "id": "disc_1",
        "candidates": [
            {
                "id": "candidate_1",
                "platform": "bilibili",
                "name": "打工喵i",
                "profile_url": "https://space.bilibili.com/281143686",
                "tags": ["AI"],
            }
        ],
    }
    intel._save(intel.DISCOVERY_FILE, [discovery])

    row = intel.accept_discovery_candidate("disc_1", "candidate_1")

    assert row["sync_status"] == "success"
    assert row["avatar_url"]
    assert row["followers"] == 71056
    assert len(row["recent_items"]) == 1


def test_content_analysis_extracts_topics_demands_and_opportunities():
    content_items = [
        {
            "id": "content_1",
            "platform": "bilibili",
            "platform_label": "B站",
            "keyword": "AI英语老师",
            "title": "小艺说英语3",
            "source_url": "https://www.bilibili.com/video/BV1/",
            "likes": 80,
            "comments_count": 2,
            "favorites": 12,
            "coins": 3,
            "quality_score": 91,
            "comment_insights": {
                "questions": ["怎么报名小艺老师的课？"],
                "needs": ["想要试听链接"],
                "summary": "评论区出现明确问题",
            },
        }
    ]
    candidates = [
        {
            "name": "小艺英语",
            "platform": "bilibili",
            "platform_label": "B站",
            "profile_url": "https://space.bilibili.com/1",
            "evidence_url": "https://www.bilibili.com/video/BV1/",
            "matched_items": 1,
            "followers": 1000,
            "reason": "高相关内容",
        }
    ]

    analysis = intel._make_content_analysis({"product_name": "海马英语"}, content_items, candidates)

    assert analysis["top_topics"][0]["topic"] == "AI英语老师"
    assert analysis["top_topics"][0]["avg_quality_score"] == 91
    assert analysis["demand_signals"][0]["text"] == "怎么报名小艺老师的课？"
    assert analysis["account_opportunities"][0]["name"] == "小艺英语"
    assert "海马英语" in analysis["content_angles"][0]["description"]


def test_create_content_brief_from_latest_discovery(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)
    discovery = {
        "id": "disc_1",
        "profile": {"product_name": "海马英语", "audience": "宝妈"},
        "platforms": ["bilibili"],
        "analysis": {
            "content_angles": [
                {
                    "title": "AI英语老师 的差异化选题",
                    "description": "参考高互动内容做不同场景",
                    "source_url": "https://www.bilibili.com/video/BV1/",
                }
            ],
            "demand_signals": [
                {"text": "怎么报名课程？", "source_url": "https://www.bilibili.com/video/BV1/"}
            ],
        },
        "top_content": [
            {"title": "小艺说英语3", "keyword": "AI英语老师", "source_url": "https://www.bilibili.com/video/BV1/"}
        ],
    }
    intel._save(intel.DISCOVERY_FILE, [discovery])

    brief = intel.create_content_brief({})

    assert brief["discovery_id"] == "disc_1"
    assert brief["title"] == "AI英语老师 的差异化选题"
    assert brief["platform_suggestion"] == ["B站"]
    assert "海马英语" in brief["objective"]
    assert "怎么报名课程" in brief["outline"][0]
    assert len(intel.list_content_briefs()) == 1


def test_create_content_brief_requires_intelligence_data(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)

    try:
        intel.create_content_brief({})
    except ValueError as exc:
        assert "还没有" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_content_brief_prompt_formats_copy_generation_prompt(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)
    intel._save(intel.BRIEF_FILE, [
        {
            "id": "brief_1",
            "title": "AI英语老师 的差异化选题",
            "objective": "面向宝妈，为海马英语生成内容方向。",
            "platform_suggestion": ["B站", "小红书"],
            "outline": ["开头：怎么报名课程？", "主体：强调每天10分钟"],
            "reference_topic": "AI英语老师",
            "reference_content": "小艺说英语3",
            "demand_signals": [{"text": "想要试听链接"}],
            "source_urls": ["https://www.bilibili.com/video/BV1/"],
            "status": "draft",
            "created_at": "2026-07-18T00:00:00+08:00",
            "updated_at": "2026-07-18T00:00:00+08:00",
        }
    ])

    result = intel.content_brief_prompt("brief_1")

    assert result["copy_type"] == "情报选题文案"
    assert "AI英语老师 的差异化选题" in result["prompt"]
    assert "想要试听链接" in result["prompt"]
    assert "不要照搬竞品标题" in result["prompt"]


def test_latest_report_includes_monitoring_digest_without_discovery(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)
    intel._save(intel.COMPETITOR_FILE, [
        {
            "id": "comp_1",
            "platform": "bilibili",
            "platform_label": "B站",
            "name": "竞品账号A",
            "profile_url": "https://space.bilibili.com/1",
            "followers": 2000,
            "recent_items": [
                {
                    "title": "低互动作品",
                    "url": "https://www.bilibili.com/video/BV1/",
                    "plays": 100,
                    "likes": 10,
                    "comments_count": 1,
                },
                {
                    "title": "高互动作品",
                    "url": "https://www.bilibili.com/video/BV2/",
                    "plays": 200,
                    "likes": 20,
                    "comments_count": 8,
                    "favorites": 5,
                    "coins": 2,
                },
            ],
            "last_sync_at": "2026-07-18T00:00:00+08:00",
            "sync_status": "success",
        }
    ])

    report = intel.latest_report()

    assert report["summary"]["content_count"] == 0
    assert report["monitoring"]["account_count"] == 1
    assert report["monitoring"]["accounts_with_updates"] == 1
    assert report["monitoring"]["recent_item_count"] == 2
    assert report["monitoring"]["top_recent_items"][0]["title"] == "高互动作品"


def test_create_content_brief_from_monitoring_item(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)
    intel._save(intel.COMPETITOR_FILE, [
        {
            "id": "comp_1",
            "platform": "bilibili",
            "platform_label": "B站",
            "name": "竞品账号A",
            "profile_url": "https://space.bilibili.com/1",
            "followers": 2000,
            "recent_items": [
                {
                    "title": "高互动作品",
                    "url": "https://www.bilibili.com/video/BV2/",
                    "plays": 200,
                    "likes": 20,
                    "comments_count": 8,
                    "favorites": 5,
                    "coins": 2,
                },
            ],
            "last_sync_at": "2026-07-18T00:00:00+08:00",
            "sync_status": "success",
        }
    ])

    brief = intel.create_content_brief({
        "source": "monitoring",
        "source_url": "https://www.bilibili.com/video/BV2/",
    })

    assert brief["source"] == "monitoring"
    assert "高互动作品" in brief["title"]
    assert brief["reference_content"] == "高互动作品"
    assert brief["source_urls"] == ["https://www.bilibili.com/video/BV2/"]
    assert len(intel.list_content_briefs()) == 1


def test_breakout_scoring_uses_same_platform_sample():
    items = [
        {"id": "low", "platform": "bilibili", "quality_score": 40, "likes": 10, "comments_count": 1},
        {"id": "mid", "platform": "bilibili", "quality_score": 55, "likes": 20, "comments_count": 2},
        {"id": "high", "platform": "bilibili", "quality_score": 92, "likes": 300, "comments_count": 40, "favorites": 80, "coins": 30},
    ]

    intel._annotate_breakouts(items)

    high = next(item for item in items if item["id"] == "high")
    low = next(item for item in items if item["id"] == "low")
    assert high["is_breakout"] is True
    assert high["hot_score"] > low["hot_score"]
    assert high["comparison_sample_size"] == 3
    assert "同批样本" in high["breakout_reason"]


def test_content_relevance_handles_mixed_chinese_and_english_query():
    assert intel._content_relevance("AI英语学习", "英语老师的AI课堂学习方法") >= 60
    assert intel._content_relevance("AI英语学习", "电商直播挂机项目") == 0


def test_visualization_exposes_real_sources_and_snapshot_growth(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)
    intel._save(intel.DISCOVERY_FILE, [{
        "id": "disc_1",
        "created_at": "2026-07-18T10:00:00+08:00",
        "updated_at": "2026-07-18T10:00:00+08:00",
        "summary": {"platforms": {"bilibili": 2}},
        "analysis": {"top_topics": [{"topic": "AI英语", "engagement": 120, "count": 2, "avg_quality_score": 88}]},
        "candidates": [{"id": "candidate_1"}],
        "content_items": [
            {
                "id": "content_1",
                "platform": "bilibili",
                "source_name": "B站公开数据",
                "collection_method": "public_api",
                "data_quality": "verified",
                "collected_at": "2026-07-18T10:00:00+08:00",
                "hot_score": 90,
                "is_breakout": True,
                "quality_score": 90,
            },
            {
                "id": "content_2",
                "platform": "bilibili",
                "source_name": "B站公开数据",
                "collection_method": "public_api",
                "data_quality": "verified",
                "collected_at": "2026-07-18T10:00:00+08:00",
                "hot_score": 60,
                "quality_score": 60,
            },
        ],
    }])
    intel._save(intel.SNAPSHOT_FILE, [
        {"entity_id": "comp_1", "name": "竞品A", "platform": "bilibili", "followers": 120, "captured_at": "2026-07-18T10:00:00+08:00"},
        {"entity_id": "comp_1", "name": "竞品A", "platform": "bilibili", "followers": 100, "captured_at": "2026-07-17T10:00:00+08:00"},
    ])

    data = intel.visualization_data()

    assert data["sample_size"] == 2
    assert data["platform_distribution"][0]["label"] == "B站"
    assert data["data_sources"][0]["quality"] == "verified"
    assert data["account_growth"][0]["growth"] == 20
    assert data["breakouts"][0]["id"] == "content_1"


def test_knowledge_base_can_be_disabled():
    profile = {"use_knowledge_base": False, "product_name": "海马英语"}

    assert intel._load_knowledge_context(profile) == []


def test_information_source_crud(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)

    source = intel.create_information_source({
        "name": "行业观察",
        "url": "https://example.com/feed.xml",
        "keywords": ["AI教育"],
    })

    assert intel.list_information_sources()[0]["name"] == "行业观察"
    updated = intel.update_information_source(source["id"], {"enabled": False})
    assert updated["enabled"] is False
    assert intel.delete_information_source(source["id"]) is True
    assert intel.list_information_sources() == []


def test_parse_market_feed_preserves_source_and_time():
    content = b"""<?xml version='1.0' encoding='UTF-8'?>
    <rss version='2.0'><channel><item>
      <title>AI education market grows</title>
      <link>https://example.com/news/1</link>
      <description><![CDATA[<p>New classroom products were released.</p>]]></description>
      <pubDate>Fri, 18 Jul 2026 08:00:00 GMT</pubDate>
    </item></channel></rss>"""

    rows = intel._parse_feed(content, {"id": "source_1", "name": "Industry News"})

    assert rows[0]["title"] == "AI education market grows"
    assert rows[0]["summary"] == "New classroom products were released."
    assert rows[0]["source_name"] == "Industry News"
    assert rows[0]["source_url"] == "https://example.com/news/1"
    assert rows[0]["collected_at"]


def test_parse_public_page_supports_user_supplied_website():
    content = """
    <html><body><article>
      <h2><a href="/news/ai-education">AI教育行业发布新的课堂产品</a></h2>
      <p>2026年7月18日，多家企业发布面向英语学习的新能力。</p>
    </article></body></html>
    """.encode("utf-8")

    rows = intel._parse_public_page(content, {
        "id": "source_2",
        "name": "教育行业网",
        "url": "https://example.com/industry/",
    })

    assert rows[0]["source_url"] == "https://example.com/news/ai-education"
    assert rows[0]["source_name"] == "教育行业网"
    assert rows[0]["collection_method"] == "public_page"


def test_collect_market_news_uses_profile_and_deduplicates(tmp_path, monkeypatch):
    _isolate_intelligence(tmp_path, monkeypatch)
    intel.upsert_business_profile({
        "id": "default",
        "product_name": "AI英语老师",
        "industry": "教育科技",
        "seed_keywords": ["AI英语"],
        "use_knowledge_base": False,
    })
    source = intel.create_information_source({
        "name": "教育资讯",
        "url": "https://example.com/feed.xml",
        "keywords": ["AI英语"],
    })

    async def fake_fetch(source_row, limit=30):
        return [
            {
                "id": "news_1",
                "title": "AI英语学习产品发布新功能",
                "summary": "教育科技公司发布口语陪练能力",
                "source_url": "https://example.com/news/1",
                "source_id": source_row.get("id", ""),
                "source_name": source_row.get("name", ""),
                "collection_method": "public_feed",
                "data_quality": "verified_source",
                "published_at": "2026-07-18T08:00:00+08:00",
                "collected_at": "2026-07-18T09:00:00+08:00",
            },
            {
                "id": "news_2",
                "title": "AI英语学习产品发布新功能",
                "summary": "重复消息",
                "source_url": "https://example.com/news/1",
                "source_id": source_row.get("id", ""),
                "source_name": source_row.get("name", ""),
                "collection_method": "public_feed",
                "data_quality": "verified_source",
                "published_at": "2026-07-18T08:00:00+08:00",
                "collected_at": "2026-07-18T09:00:00+08:00",
            },
        ]

    monkeypatch.setattr(intel, "_fetch_market_feed", fake_fetch)
    result = asyncio.run(intel.collect_market_news("default", include_auto_search=False))

    assert result["total"] == 1
    assert result["items"][0]["relevance_score"] >= 20
    assert result["items"][0]["matched_keywords"] == ["AI英语"]
    assert intel.list_market_news()[0]["source_url"] == "https://example.com/news/1"
    refreshed_source = next(row for row in intel.list_information_sources() if row["id"] == source["id"])
    assert refreshed_source["status"] == "success"
    assert refreshed_source["item_count"] == 1
