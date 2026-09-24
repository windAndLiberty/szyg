import json

import pytest

import szyg.competitor_intelligence as competitor
import szyg.geo_service as geo
import szyg.geo_analysis as geo_analysis
from szyg.hermes_capabilities import HermesCapabilityRegistry
from szyg.geo_repository import GeoRepository


@pytest.fixture()
def isolated_geo(tmp_path, monkeypatch):
    monkeypatch.setattr(competitor, "BUSINESS_PROFILE_FILE", tmp_path / "profiles.json")
    monkeypatch.setattr(geo, "AUDITS_FILE", tmp_path / "audits.json")
    monkeypatch.setattr(geo, "OBSERVATIONS_FILE", tmp_path / "observations.json")
    monkeypatch.setattr(geo, "RECOMMENDATIONS_FILE", tmp_path / "recommendations.json")
    monkeypatch.setattr(geo, "GEO_DB_FILE", tmp_path / "geo.db")
    geo._SERVICE = None
    service = geo.get_geo_service()

    async def analyze(profile, answer, citations, facts, *, allow_remote=True):
        del facts
        del allow_remote
        mentioned = profile["product_name"] in answer
        recommended = mentioned and "推荐" in answer
        return {
            "mentioned": mentioned, "recommended": recommended,
            "recommendation_strength": "explicit" if recommended else ("mentioned" if mentioned else "none"),
            "recommendation_evidence": answer if recommended else "", "position": 1 if recommended else 0,
            "sentiment": "positive" if recommended else "neutral", "competitor_mentions": [],
            "factual_issues": [], "citations": citations, "analysis_status": "completed",
        }

    monkeypatch.setattr(geo, "analyze_answer", analyze)
    yield service
    geo._SERVICE = None


def test_geo_profile_reuses_intelligence_business_profile(isolated_geo):
    profile = isolated_geo.update_profile({
        "product_name": "领鹿", "website": "https://example.com", "brand_aliases": ["SZYG"],
        "products": ["数字员工"], "competitors": ["竞品A"], "languages": ["zh-CN"],
        "geo_providers": ["doubao"],
    })
    questions = isolated_geo.update_questions(["适合传统企业的数字员工有哪些？", "适合传统企业的数字员工有哪些？"])
    assert profile["website"] == "https://example.com"
    assert isolated_geo.get_profile()["brand_aliases"] == ["SZYG"]
    assert questions == ["适合传统企业的数字员工有哪些？"]
    assert competitor.list_business_profiles()[0]["target_questions"] == questions
    assert {item["predicate"] for item in isolated_geo.get_facts()} >= {"品牌名称", "官方网站", "主要产品"}


@pytest.mark.asyncio
async def test_geo_audit_keeps_success_when_another_provider_fails(isolated_geo, monkeypatch):
    isolated_geo.update_profile({"product_name": "领鹿", "website": "https://example.com", "brand_aliases": ["SZYG"], "competitors": ["竞品A"], "geo_providers": ["doubao", "openai"]})
    isolated_geo.update_questions(["推荐几款数字员工"])

    async def status():
        return [
            {"id": "doubao", "label": "豆包", "mode": "consumer_surface", "configured": True},
            {"id": "openai", "label": "ChatGPT", "mode": "consumer_surface", "configured": True},
        ]

    async def query(provider_id, *_args):
        if provider_id == "openai":
            raise RuntimeError("provider unavailable")
        return {
            "answer": "推荐领鹿数字员工。", "provider_model": "consumer-test", "fidelity": "consumer_surface",
            "capture_method": "sidebar_browser",
            "request_id": "req-1", "search_queries": ["数字员工"],
            "citations": [{"url": "https://example.com/a"}, {"url": "https://example.com/a"}],
        }

    monkeypatch.setattr(isolated_geo, "refresh_provider_status", status)
    monkeypatch.setattr(isolated_geo, "_query_provider", query)
    audit = isolated_geo.create_audit(sample_count=1)
    finished = await isolated_geo.run_audit(audit["id"])
    observations = isolated_geo.list_observations(audit_id=audit["id"])
    overview = isolated_geo.overview(30)

    assert finished["status"] == "partial"
    assert finished["completed"] == 1
    assert finished["failed"] == 1
    success = next(item for item in observations if item["status"] == "completed")
    assert success["mentioned"] is True
    assert success["recommended"] is True
    assert len(success["citations"]) == 1
    assert success["citations"][0]["is_owned_domain"] is True
    assert overview["mention_rate"] == 100.0
    assert overview["recommendation_rate"] == 100.0
    assert overview["owned_citation_rate"] == 100.0


@pytest.mark.asyncio
async def test_geo_audit_fails_truthfully_without_configured_provider(isolated_geo, monkeypatch):
    isolated_geo.update_profile({"product_name": "领鹿", "geo_providers": ["doubao"]})
    isolated_geo.update_questions(["推荐几款数字员工"])

    async def status():
        return [{"id": "doubao", "label": "豆包", "mode": "consumer_surface", "configured": False}]

    monkeypatch.setattr(isolated_geo, "refresh_provider_status", status)
    audit = isolated_geo.create_audit(provider_ids=["doubao"], sample_count=1)
    finished = await isolated_geo.run_audit(audit["id"])
    assert finished["status"] == "failed"
    assert "侧边栏浏览器" in finished["error"]
    assert isolated_geo.list_observations(audit_id=audit["id"]) == []


def test_queued_browser_audit_can_be_cancelled(isolated_geo):
    isolated_geo.update_profile({"product_name": "领鹿", "geo_providers": ["deepseek"]})
    isolated_geo.update_questions(["推荐几款数字员工"])
    audit = isolated_geo.create_audit(provider_ids=["deepseek"], sample_count=1)

    cancelled = isolated_geo.cancel_audit(audit["id"])

    assert cancelled["status"] == "failed"
    assert cancelled["error"] == "你已停止本次浏览器检测"
    assert isolated_geo.repository.list_queued_audits() == []


@pytest.mark.asyncio
async def test_scheduled_audit_waits_for_visible_geo_workbench(isolated_geo, monkeypatch):
    import szyg.geo_browser as geo_browser

    isolated_geo.update_profile({"product_name": "领鹿", "geo_providers": ["deepseek"]})
    isolated_geo.update_questions(["推荐几款数字员工"])

    async def status():
        return [{"id": "deepseek", "label": "DeepSeek", "mode": "consumer_surface", "configured": True}]

    class HiddenBrowser:
        async def visible(self):
            return False

    monkeypatch.setattr(isolated_geo, "refresh_provider_status", status)
    monkeypatch.setattr(geo_browser, "get_geo_sidebar_browser", lambda: HiddenBrowser())
    audit = isolated_geo.create_audit(provider_ids=["deepseek"], sample_count=1, mode="scheduled")

    waiting = await isolated_geo.run_audit(audit["id"])

    assert waiting["status"] == "queued"
    assert "打开GEO品牌体检" in waiting["error"]
    assert isolated_geo.list_observations(audit_id=audit["id"]) == []


@pytest.mark.asyncio
async def test_only_automatic_sidebar_samples_count_in_core_metrics(isolated_geo):
    isolated_geo.update_profile({"product_name": "领鹿", "website": "https://example.com"})
    isolated_geo.update_questions(["领鹿数字员工可靠吗？"])
    question_id = isolated_geo.list_question_details()[0]["id"]
    audit = isolated_geo.create_audit(provider_ids=["deepseek"], question_ids=[question_id], sample_count=1, mode="spot_check")
    isolated_geo.repository.update_audit(audit["id"], status="needs_human")
    first = await isolated_geo.capture_spot_check(audit["id"], question_id, "推荐领鹿数字员工。", ["https://example.com/case"])
    repeated = await isolated_geo.capture_spot_check(audit["id"], question_id, "重复提交不应新增记录。", [])
    isolated_geo.repository.insert_observation({
        "id": "automatic-sidebar", "audit_id": audit["id"], "question_id": question_id,
        "provider_id": "openai", "provider_label": "ChatGPT", "fidelity": "consumer_surface",
        "capture_method": "sidebar_browser", "sample_index": 1, "answer": "推荐领鹿数字员工。",
        "status": "completed", "analysis_status": "deterministic", "mentioned": True,
        "recommended": True, "position": 1, "citations": [], "competitor_mentions": [], "factual_issues": [],
    })
    isolated_geo.repository.insert_observation({
        "id": "historical-official", "audit_id": audit["id"], "question_id": question_id,
        "provider_id": "doubao", "provider_label": "豆包", "fidelity": "official_search_api",
        "capture_method": "api", "sample_index": 1, "answer": "历史接口回答",
        "status": "completed", "analysis_status": "completed", "mentioned": False,
        "recommended": False, "citations": [], "competitor_mentions": [], "factual_issues": [],
    })
    overview = isolated_geo.overview(30)
    assert overview["valid_sample_count"] == 1
    assert overview["recommendation_rate"] == 100.0
    assert repeated["id"] == first["id"]
    assert overview["consumer_sample_count"] == 1
    assert overview["official_sample_count"] == 1
    assert overview["fact_checked_sample_count"] == 0


@pytest.mark.asyncio
async def test_verification_records_scoped_before_metrics(isolated_geo):
    isolated_geo.update_profile({"product_name": "领鹿", "website": "https://example.com", "geo_providers": ["doubao"]})
    isolated_geo.update_questions(["推荐几款数字员工"])
    question_id = isolated_geo.list_question_details()[0]["id"]
    audit = isolated_geo.create_audit(provider_ids=["doubao"], question_ids=[question_id], sample_count=1)
    observation = isolated_geo.repository.insert_observation({
        "id": "verification-baseline", "audit_id": audit["id"], "question_id": question_id,
        "provider_id": "doubao", "provider_label": "豆包", "fidelity": "consumer_surface",
        "capture_method": "sidebar_browser", "sample_index": 1, "answer": "领鹿是一款数字员工。",
        "status": "completed", "analysis_status": "completed", "mentioned": True, "recommended": False,
        "citations": [], "competitor_mentions": [], "factual_issues": [],
    })
    recommendation = isolated_geo.repository.replace_recommendations(audit["id"], [{
        "category": "not_recommended", "title": "说明为什么客户应该选择你",
        "evidence_ids": [observation["id"]], "question_ids": [question_id], "provider_ids": ["doubao"],
    }])[0]

    verification = isolated_geo.verify_recommendation(recommendation["id"])
    updated = isolated_geo.get_recommendation(recommendation["id"])

    assert verification["sample_count"] == 3
    assert updated["verification_result"]["before"]["valid_samples"] == 1
    assert updated["verification_result"]["before"]["mention_rate"] == 100.0


@pytest.mark.asyncio
async def test_question_suggestions_use_saved_business_context_without_remote_ai(isolated_geo):
    isolated_geo.update_profile({
        "product_name": "领鹿", "products": ["数字员工"], "audience": "传统企业主",
        "competitors": ["竞品A"],
    })
    items = await isolated_geo.suggest_questions(3)

    assert items[0]["text"] == "适合传统企业主的数字员工有哪些？"
    assert items[0]["source"] == "ai_suggestion"
    assert any("数字员工" in item["text"] for item in items)


@pytest.mark.asyncio
async def test_structured_analysis_works_with_cloud_client_without_close(monkeypatch):
    import szyg.integrations.volcengine_client as volcengine

    class FakeCloudClient:
        def __init__(self, **_kwargs):
            pass

        async def chat(self, *_args, **_kwargs):
            return {"message": {"content": json.dumps({
                "mentioned": True, "recommended": True, "recommendation_strength": "explicit",
                "recommendation_evidence": "推荐领鹿", "position": 1, "sentiment": "positive",
                "competitor_mentions": [], "factual_issues": [],
            }, ensure_ascii=False)}}

    monkeypatch.setattr(volcengine, "VolcEngineClient", FakeCloudClient)
    result = await geo_analysis.analyze_answer(
        {"product_name": "领鹿", "brand_aliases": [], "competitors": []},
        "我们推荐领鹿用于企业自动化。", [], [],
    )

    assert result["analysis_status"] == "completed"
    assert result["recommended"] is True


def test_super_agent_can_discover_geo_capabilities():
    names = {item["name"] for item in HermesCapabilityRegistry().list(domain="geo")}
    assert {
        "geo.audit", "geo.observations", "geo.overview", "geo.profile", "geo.recommendations",
        "geo.questions.suggest", "geo.sources.analyze", "geo.recommendation.get",
        "geo.recommendation.verify", "geo.site.review",
    } <= names


def test_legacy_json_migration_is_idempotent_and_excluded_from_core_metrics(tmp_path):
    audit_file = tmp_path / "geo_audits.json"
    observation_file = tmp_path / "geo_observations.json"
    recommendation_file = tmp_path / "geo_recommendations.json"
    audit_file.write_text(json.dumps([{
        "id": "legacy-audit", "status": "completed", "questions": ["推荐数字员工"],
        "provider_ids": ["doubao"], "total": 1, "completed": 1,
    }], ensure_ascii=False), encoding="utf-8")
    observation_file.write_text(json.dumps([{
        "id": "legacy-observation", "audit_id": "legacy-audit", "question": "推荐数字员工",
        "provider_id": "doubao", "answer": "推荐领鹿。", "mentioned": True, "recommended": True,
    }], ensure_ascii=False), encoding="utf-8")
    recommendation_file.write_text("[]", encoding="utf-8")

    repository = GeoRepository(tmp_path / "geo.db")
    args = {
        "audits_path": audit_file,
        "observations_path": observation_file,
        "recommendations_path": recommendation_file,
        "questions": ["推荐数字员工"],
    }
    repository.migrate_legacy(**args)
    repository.migrate_legacy(**args)

    observations = repository.list_observations(limit=20)
    assert len(observations) == 1
    assert observations[0]["fidelity"] == "plain_model"
    assert audit_file.exists() and observation_file.exists()
