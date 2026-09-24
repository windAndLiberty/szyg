import json

import pytest

import szyg.competitor_intelligence as legacy
import szyg.intelligence_pipeline as pipeline


def test_intelligence_config_is_loaded_from_top_level():
    config = pipeline._config()

    assert config["analysis_model"] == "doubao-seed-2-0-lite-260428"
    assert config["query_all_enabled_platforms"] is True
    assert config["collectors"]["douyin"] == "browser_session"
    assert config["collectors"]["public_web"] == "public_feed"


@pytest.mark.parametrize(("raw", "expected"), [
    ("AI英语学习工具解决哑巴英语用户", "开口练习"),
    ("利用AI作为专属外教练习英语口语", "AI口语陪练"),
    ("2026英语口语学习APP推荐", "真实测评"),
    ("伪AI英语学习产品避坑风险提示", "选购避坑"),
    ("宝妈圈热门AI少儿口语产品实测", "真实测评"),
    ("AI学习机硬件选购", "AI英语学习机"),
    ("游戏化属性的英语学习", "游戏化学习"),
    ("B站英语学习工具高互动", "学习工具推荐"),
    ("AI教育类学习产品内容", "AI教育内容"),
    ("AI英文教育模型助力", "AI教育内容"),
])
def test_normalize_topic_produces_stable_semantic_labels(raw, expected):
    assert pipeline._normalize_topic(raw) == expected


def test_sanitize_summary_normalizes_model_confidence():
    rows = pipeline._sanitize_summary([{
        "title": "样本仍有限",
        "confidence": "样本不足，结论代表性有限",
    }], "low")

    assert rows[0]["confidence"] == "low"


def test_load_published_context_keeps_only_success_and_cleans_technical_data(tmp_path, monkeypatch):
    runs_file = tmp_path / "execution_runs.json"
    archive_file = tmp_path / "execution_runs_archive.json"
    monkeypatch.setattr(pipeline, "RUNS_FILE", runs_file)
    monkeypatch.setattr(pipeline, "ARCHIVED_RUNS_FILE", archive_file)
    runs_file.write_text(json.dumps([
        {
            "id": "exec_success",
            "task_type": "publish_note",
            "platform": "xhs",
            "status": "success",
            "input": {
                "title": "英语启蒙怎么选",
                "note": "真实内容 C:\\Users\\Demo\\secret.png exec_abcd SZYG AI生成",
                "tags": ["英语启蒙"],
            },
            "finished_at": "2026-07-18T10:00:00+08:00",
        },
        {
            "id": "exec_failed",
            "task_type": "publish_note",
            "platform": "douyin",
            "status": "failed",
            "input": {"title": "不应读取", "note": "失败任务"},
        },
    ], ensure_ascii=False), encoding="utf-8")
    archive_file.write_text("[]", encoding="utf-8")

    rows = pipeline.load_published_context()

    assert len(rows) == 1
    assert rows[0]["title"] == "英语启蒙怎么选"
    assert "secret.png" not in rows[0]["content"]
    assert "exec_abcd" not in rows[0]["content"]
    assert "AI生成" not in rows[0]["content"]


@pytest.mark.asyncio
async def test_semantic_filter_rejects_keyword_overlap(monkeypatch):
    async def fake_model(*_args, **_kwargs):
        return {
            "items": [
                {"id": "good", "relevant": True, "relation_type": "customer_need", "marketing_value": 88, "topic": "陪练效果"},
                {"id": "bad", "relevant": False, "relation_type": "market_change", "marketing_value": 0, "topic": "教师婚恋"},
            ]
        }

    monkeypatch.setattr(pipeline, "_model_json", fake_model)
    samples = [
        {"id": "good", "title": "家长如何判断AI英语陪练效果", "text": "", "kind": "platform_content"},
        {"id": "bad", "title": "和英语老师结婚是什么体验", "text": "", "kind": "platform_content"},
    ]

    result, model_used = await pipeline.semantic_filter(
        "家长选择AI英语陪练时关心什么",
        {"focus": "AI英语陪练", "exclude_topics": ["教师婚恋"]},
        samples,
        {"product_name": "AI英语学习产品", "audience": "家长"},
    )

    decisions = {item["id"]: item for item in result["items"]}
    assert model_used is True
    assert decisions["good"]["relevant"] is True
    assert decisions["bad"]["relevant"] is False


@pytest.mark.asyncio
async def test_market_context_excludes_cached_auto_searches_from_other_topics(monkeypatch):
    current = {
        "id": "current",
        "source_url": "https://example.com/current",
        "source_id": "auto_AI英语学习机",
    }

    async def fake_collect(*_args, **_kwargs):
        return {"items": [current], "sources": [{"status": "success"}]}

    monkeypatch.setattr(legacy, "collect_market_news", fake_collect)
    monkeypatch.setattr(legacy, "list_market_news", lambda limit=80: [
        current,
        {
            "id": "unrelated",
            "source_url": "https://example.com/unrelated",
            "source_id": "auto_咖啡店营销",
        },
        {
            "id": "manual",
            "source_url": "https://example.com/manual",
            "source_id": "source_industry_news",
        },
    ])

    result = await pipeline._collect_market_context({
        "id": "default",
        "seed_keywords": ["AI英语学习机"],
    })

    assert [item["id"] for item in result["items"]] == ["current", "manual"]


@pytest.mark.asyncio
async def test_query_report_uses_relevant_samples_and_does_not_persist_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "REPORT_FILE", tmp_path / "intelligence_reports.json")
    monkeypatch.setattr(pipeline, "RUNS_FILE", tmp_path / "execution_runs.json")
    monkeypatch.setattr(pipeline, "ARCHIVED_RUNS_FILE", tmp_path / "execution_runs_archive.json")

    monkeypatch.setattr(legacy, "list_business_profiles", lambda: [{
        "id": "default",
        "product_name": "海马英语",
        "industry": "AI英语学习",
        "audience": "家长",
        "seed_keywords": ["英语启蒙"],
        "platforms": ["bilibili"],
    }])
    monkeypatch.setattr(legacy, "_load_knowledge_context", lambda *_args, **_kwargs: [])

    captured = {}

    async def fake_discover(payload, persist_profile=True, persist_discovery=True):
        captured["persist_profile"] = persist_profile
        captured["persist_discovery"] = persist_discovery
        return {
            "content_items": [
                {"id": "good", "title": "家长关心开口效果", "description": "每天练习反馈", "platform": "bilibili", "platform_label": "B站", "keyword": "AI英语陪练", "likes": 20, "comments_count": 5, "source_url": "https://example.com/good"},
                {"id": "bad", "title": "和英语老师结婚", "description": "婚恋话题", "platform": "bilibili", "platform_label": "B站", "keyword": "英语老师", "likes": 999, "comments_count": 99, "source_url": "https://example.com/bad"},
            ],
            "source_health": [{
                "source": "bilibili",
                "label": "B站",
                "source_type": "platform",
                "method": "public_page",
                "status": "success",
                "item_count": 2,
                "attempted_queries": 1,
                "successful_queries": 1,
                "duration_ms": 10,
                "error_code": "",
                "message": "已读取 2 条公开内容",
            }],
        }

    async def fake_news(*_args, **kwargs):
        captured["profile_override"] = kwargs.get("profile_override")
        return {"items": []}

    async def fake_plan(*_args, **_kwargs):
        return {"intent": "market_research", "focus": "AI英语陪练", "search_keywords": ["AI英语陪练"], "exclude_topics": ["教师婚恋"], "platforms": ["bilibili"], "time_range": "近30天"}

    async def fake_filter(*_args, **_kwargs):
        return {"items": [
            {"id": "good", "relevant": True, "relation_type": "customer_need", "marketing_value": 90, "topic": "开口效果", "reason": "家长真实需求", "customer_need": "看得见的学习效果", "sentiment": "question"},
            {"id": "bad", "relevant": False, "relation_type": "market_change", "marketing_value": 0, "topic": "婚恋", "reason": "业务无关", "customer_need": "", "sentiment": "neutral"},
        ]}, True

    async def fake_narrative(*_args, **_kwargs):
        return {
            "executive_summary": [{"title": "效果反馈最重要", "finding": "家长关注开口效果", "why_it_matters": "应展示过程证据", "confidence": "low"}],
            "customer_voice": [],
            "content_patterns": [],
            "industry_moves": [],
            "actions": [],
            "topic_recommendations": {},
        }, True

    async def fake_market_context(profile):
        result = await fake_news(profile_override=profile)
        result["source_health"] = {
            "source": "public_web",
            "label": "公开资讯",
            "source_type": "public_web",
            "method": "public_feed",
            "status": "no_data",
            "item_count": 0,
            "attempted_queries": 0,
            "successful_queries": 0,
            "duration_ms": 0,
            "error_code": "",
            "message": "本轮未发现匹配的公开资讯",
        }
        return result

    monkeypatch.setattr(pipeline, "_collect_platform_content", lambda payload, _plan: fake_discover(payload, False, False))
    monkeypatch.setattr(pipeline, "_collect_market_context", fake_market_context)
    monkeypatch.setattr(pipeline, "plan_intelligence_query", fake_plan)
    monkeypatch.setattr(pipeline, "semantic_filter", fake_filter)
    monkeypatch.setattr(pipeline, "_narrative_report", fake_narrative)

    report = await pipeline.run_intelligence_query("家长选择AI英语陪练时最关心什么")

    assert captured["persist_profile"] is False
    assert captured["persist_discovery"] is False
    assert captured["profile_override"]["seed_keywords"][0] == "AI英语陪练"
    assert report["data_scope"]["raw_samples"] == 2
    assert report["data_scope"]["relevant_samples"] == 1
    assert report["data_scope"]["filtered_samples"] == 1
    assert [item["source"] for item in report["data_scope"]["source_health"]] == ["bilibili", "public_web"]
    assert [item["id"] for item in report["evidence"]] == ["good"]
    assert "结婚" not in json.dumps(report, ensure_ascii=False)
    assert pipeline.list_intelligence_reports()[0]["id"] == report["id"]


@pytest.mark.asyncio
async def test_narrative_fallback_still_produces_actionable_sections(monkeypatch):
    async def unavailable_model(*_args, **_kwargs):
        return None

    monkeypatch.setattr(pipeline, "_model_json", unavailable_model)
    report, model_used = await pipeline._narrative_report(
        "家长关心什么",
        {"focus": "AI英语陪练"},
        [{"topic": "AI口语陪练", "count": 4, "score": 82, "engagement": 120}],
        [{
            "topic": "开口练习",
            "customer_need": "家长希望孩子敢开口，并看到持续的学习反馈",
            "sentiment": "question",
            "relation_type": "customer_need",
            "reason": "公开内容出现真实选购疑问",
        }],
        [],
        4,
    )

    assert model_used is False
    assert report["customer_voice"]
    assert report["content_patterns"]
    assert report["actions"]


@pytest.mark.asyncio
async def test_narrative_model_enhances_summary_without_removing_stable_sections(monkeypatch):
    async def available_model(*_args, **_kwargs):
        return {
            "executive_summary": [{
                "title": "用户优先关心开口效果",
                "finding": "真实测评与口语陪练互动更集中",
                "why_it_matters": "应优先展示练习过程与反馈",
                "confidence": "medium",
            }],
            "actions": [{"title": "制作实测内容", "description": "展示练习前后差异", "priority": 1}],
            "topic_recommendations": {"AI口语陪练": "优先验证"},
        }

    monkeypatch.setattr(pipeline, "_model_json", available_model)
    report, model_used = await pipeline._narrative_report(
        "家长关心什么",
        {"focus": "AI口语陪练"},
        [{"topic": "AI口语陪练", "count": 4, "score": 82, "engagement": 120}],
        [{
            "topic": "开口练习",
            "customer_need": "家长希望孩子敢开口",
            "sentiment": "question",
            "relation_type": "customer_need",
            "reason": "公开内容出现真实选购疑问",
        }],
        [],
        4,
    )

    assert model_used is True
    assert report["executive_summary"][0]["title"] == "用户优先关心开口效果"
    assert report["customer_voice"]
    assert report["content_patterns"]
