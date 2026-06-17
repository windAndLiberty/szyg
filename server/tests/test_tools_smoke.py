"""
Smoke test to execute all 24 registered szyg business tools.
Ensures that none of the tool handler functions raise exceptions or import-time errors.
"""
import pytest
import json
from tools.registry import registry
from szyg.agent_core.szyg_toolset import register_szyg_toolset


@pytest.fixture(autouse=True)
def setup_tools():
    # Make sure they are registered
    register_szyg_toolset()


def test_publisher_tools_smoke():
    # 1. pub_list
    h_list = registry.get_entry("pub_list").handler
    res = json.loads(h_list({"limit": 5}))
    assert isinstance(res, list)

    # 2. pub_create
    h_create = registry.get_entry("pub_create").handler
    res_create = json.loads(h_create({"title": "Smoke Test Content", "body": "Hello World"}))
    assert "id" in res_create
    content_id = res_create["id"]

    # 3. pub_submit
    h_submit = registry.get_entry("pub_submit").handler
    res_submit = json.loads(h_submit({"content_id": content_id}))
    assert "id" in res_submit or "error" in res_submit

    # 4. pub_approve
    h_approve = registry.get_entry("pub_approve").handler
    res_approve = json.loads(h_approve({"content_id": content_id}))
    assert "id" in res_approve or "error" in res_approve

    # 5. pub_publish
    h_publish = registry.get_entry("pub_publish").handler
    res_publish = json.loads(h_publish({"content_id": content_id}))
    assert "published" in res_publish or "error" in res_publish


def test_scheduler_tools_smoke():
    # 1. sched_list
    h_list = registry.get_entry("sched_list").handler
    res = json.loads(h_list({"limit": 5}))
    assert isinstance(res, list)

    # 2. sched_stats
    h_stats = registry.get_entry("sched_stats").handler
    res_stats = json.loads(h_stats({}))
    assert "total_jobs" in res_stats

    # 3. sched_create
    h_create = registry.get_entry("sched_create").handler
    res_create = json.loads(h_create({"name": "Smoke Job", "cron": "0 10 * * *", "description": "daily"}))
    assert "id" in res_create
    job_id = res_create["id"]

    # 4. sched_execute (bad ID is handled gracefully)
    h_exec = registry.get_entry("sched_execute").handler
    res_exec = json.loads(h_exec({"job_id": "nonexistent_job"}))
    assert "error" in res_exec

    # Cleanup created job
    from szyg.scheduler_engine import get_scheduler
    get_scheduler().delete_job(job_id)


def test_marketplace_tools_smoke():
    # 1. tools_catalog
    h_catalog = registry.get_entry("tools_catalog").handler
    res = json.loads(h_catalog({"limit": 5}))
    assert isinstance(res, list)

    # 2. tools_categories
    h_cats = registry.get_entry("tools_categories").handler
    res_cats = json.loads(h_cats({}))
    assert isinstance(res_cats, list)

    # 3. tools_stats
    h_stats = registry.get_entry("tools_stats").handler
    res_stats = json.loads(h_stats({}))
    assert "total" in res_stats


def test_knowledge_tools_smoke():
    # 1. kb_search
    h_search = registry.get_entry("kb_search").handler
    res = json.loads(h_search({"query": "测试", "limit": 2}))
    assert isinstance(res, list)

    # 2. kb_stats
    h_stats = registry.get_entry("kb_stats").handler
    res_stats = json.loads(h_stats({}))
    assert "total" in res_stats or "error" in res_stats


def test_agents_tools_smoke():
    # 1. agents_list
    h_list = registry.get_entry("agents_list").handler
    res = json.loads(h_list({}))
    assert isinstance(res, list)

    # 2. agents_tiers
    h_tiers = registry.get_entry("agents_tiers").handler
    res_tiers = json.loads(h_tiers({}))
    assert isinstance(res_tiers, list)


def test_leads_tools_smoke():
    # 1. lead_search
    h_search = registry.get_entry("lead_search").handler
    res = json.loads(h_search({"limit": 5}))
    assert isinstance(res, list)

    # 2. lead_score
    h_score = registry.get_entry("lead_score").handler
    res_score = json.loads(h_score({"platform": "douyin", "content": "怎么购买？"}))
    assert "score" in res_score or "error" in res_score

    # 3. lead_create
    h_create = registry.get_entry("lead_create").handler
    res_create = json.loads(h_create({"platform": "douyin", "account": "user_smoke", "name": "烟雾测试", "content": "测试"}))
    assert "id" in res_create
    lead_id = res_create["id"]

    # 4. lead_update
    h_update = registry.get_entry("lead_update").handler
    res_update = json.loads(h_update({"lead_id": lead_id, "stage": "engaged", "notes": "Smoke tested"}))
    assert "id" in res_update or "error" in res_update

    # 5. lead_stats
    h_stats = registry.get_entry("lead_stats").handler
    res_stats = json.loads(h_stats({}))
    assert "total" in res_stats


def test_scripts_tools_smoke():
    # 1. script_list
    h_list = registry.get_entry("script_list").handler
    res = json.loads(h_list({"limit": 5}))
    assert isinstance(res, list)

    # 2. script_generate
    h_gen = registry.get_entry("script_generate").handler
    res_gen = json.loads(h_gen({"industry": "retail", "scenario": "price_inquiry"}))
    assert "title" in res_gen or "error" in res_gen


def test_oem_tools_smoke():
    # 1. oem_config
    h_oem = registry.get_entry("oem_config").handler
    res = json.loads(h_oem({}))
    assert isinstance(res, dict)
