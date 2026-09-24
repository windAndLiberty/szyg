import asyncio
import json


def test_registry_covers_business_domains_without_credits():
    from szyg.hermes_capabilities import get_hermes_capability_registry

    rows = get_hermes_capability_registry().list()
    names = {row["name"] for row in rows}
    domains = {row["domain"] for row in rows}

    assert domains == {"private_domain", "intelligence", "insights", "materials", "publishing", "execution"}
    assert "private_domain.overview" in names
    assert "intelligence.query" in names
    assert "insights.overview" in names
    assert "graphic.plan" in names
    assert "publishing.note" in names
    assert "executions.retry" in names
    assert not any("credit" in name or "billing" in name for name in names)


def test_external_capability_requires_explicit_confirmation():
    from szyg.hermes_capabilities import get_hermes_capability_registry

    result = asyncio.run(get_hermes_capability_registry().execute(
        "publishing.note",
        {"platform": "xhs", "title": "测试", "image_paths": "a.jpg"},
    ))
    payload = json.loads(result)

    assert payload["ok"] is False
    assert payload["status"] == "confirmation_required"


def test_capability_tools_are_exposed_to_hermes():
    from szyg.api.hermes_chat import HERMES_TOOLS

    names = {item["function"]["name"] for item in HERMES_TOOLS}
    assert {"capability_list", "capability_call"} <= names


def test_material_composition_rejects_more_than_five_assets():
    from szyg.hermes_capabilities import get_hermes_capability_registry

    result = asyncio.run(get_hermes_capability_registry().execute(
        "graphic.plan",
        {"assets_json": json.dumps([{"id": str(index)} for index in range(6)])},
    ))
    payload = json.loads(result)

    assert payload["ok"] is False
    assert "最多使用 5 个素材" in payload["error"]


def test_brain_status_distinguishes_registry_from_legacy_mcp_config():
    from szyg.brain_hermes import get_brain

    status = get_brain().get_status()

    assert status["mcp_runtime_attached"] is False
    assert status["business_capabilities"]["count"] >= 27
    assert "private_domain" in status["business_capabilities"]["domains"]
    assert all(server["running"] is False for server in status["server_list"])
