import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from szyg import conversation_experts
from szyg.api.agency_routes import router


@pytest.fixture()
def experts(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_experts, "DATABASE", tmp_path / "experts.sqlite")
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


BASE = "/api/agency/conversation-experts"
RED = "marketing-xiaohongshu-specialist"
FINANCE = "finance-financial-analyst"


def conversation(agent="main", private=False):
    return {"agent_id": agent, "session_key": f"agent:{agent}:dashboard:{'incognito-' if private else ''}{uuid.uuid4()}"}


def turn(client, ctx, message):
    response = client.post(f"{BASE}/resolve", json={**ctx, "message": message})
    response.raise_for_status()
    return response.json()


def test_automatic_follow_up_switch_and_session_isolation(experts):
    ctx = conversation()
    assert turn(experts, ctx, "你好") == {"active": []}
    assert turn(experts, ctx, "不用小红书") == {"active": []}
    first = turn(experts, ctx, "帮我给小红书写一篇笔记")
    assert [(e["slug"], e["source"]) for e in first["active"]] == [(RED, "auto")]
    assert "Lifestyle Brand Development" in first["workContext"]["selection"]
    assert turn(experts, ctx, "请缩短第二段")["active"] == first["active"]
    assert not turn(experts, ctx, "今晚想吃什么")["active"]
    assert turn(experts, ctx, "做一次现金流分析")["active"][0]["slug"] == FINANCE
    assert turn(experts, ctx, "发布到抖音和小红书")["active"][0]["slug"] == "marketing-multi-platform-publisher"
    assert turn(experts, conversation(), "你好") == {"active": []}
    assert turn(experts, conversation("sales"), "你好") == {"active": []}
    assert experts.get(BASE, params={**ctx, "agent_id": "sales"}).status_code == 422
    assert experts.post(f"{BASE}/attach", json={**ctx, "slug": "../../local"}).status_code == 404


def test_user_removal_persists_and_reloading_pins(experts):
    ctx = conversation()
    assert turn(experts, ctx, "小红书")["active"][0]["slug"] == RED
    assert experts.post(f"{BASE}/detach", json={**ctx, "slug": RED}).json() == {"active": []}
    removed = turn(experts, ctx, "再写小红书笔记")
    assert not removed["active"] and "已卸载" in removed["workContext"]["title"]
    assert "selection" not in removed["workContext"]
    assert experts.get(BASE, params=ctx).json() == {"active": []}
    assert experts.post(f"{BASE}/attach", json={**ctx, "slug": RED}).json()["active"][0]["source"] == "manual"
    assert [x["slug"] for x in turn(experts, ctx, "核算毛利率")["active"]] == [RED]
    assert "小红书" not in conversation_experts.DATABASE.read_bytes().decode(errors="ignore")


def test_manual_limit_catalog_and_private_storage(experts):
    ctx = conversation(private=True)
    catalog = experts.get(f"{BASE}/catalog", params={"locale": "en-US"}).json()
    assert any(a["name"] == "Financial Analyst" for a in catalog)
    assert all(a["slug"] != "specialized-mcp-builder" for a in catalog)
    for slug in [RED, FINANCE, "design-ui-designer"]:
        assert experts.post(f"{BASE}/attach", json={**ctx, "slug": slug}).is_success
    assert experts.post(f"{BASE}/attach", json={**ctx, "slug": "product-manager"}).status_code == 422
    response = turn(experts, ctx, "做一份报告")
    assert len(response["active"]) == len(response["workContext"]["detail"]) == 3
    assert len(response["workContext"]["selection"]) <= 640
    assert experts.get(BASE, params=ctx).json()["active"] == response["active"]
    assert not conversation_experts.DATABASE.exists()


def test_every_automatic_domain_has_a_bundled_commercial_profile(experts):
    catalog = {a["slug"] for a in experts.get(f"{BASE}/catalog").json()}
    assert set(conversation_experts._CUES) <= catalog
