"""
前端数据 API 验收测试

目标：验证 data_routes.py 提供的所有前端数据接口真实可用，
数据变更能够持久化到 data/frontend/*.json。

注意：本测试使用真实的 FastAPI app 和 ASGITransport，不 mock 数据层。
"""

import pytest


class TestDataRoutesList:
    """通用列表查询端点验收。"""

    RESOURCES = [
        "team", "tools", "skills", "installed_skills", "platforms", "contents",
        "materials", "content_assets", "copy_library", "publish_records", "leads",
        "customers", "sops", "sop_executions", "knowledge_docs", "scheduled_tasks",
        "execution_history", "experiments", "strategies", "logs", "messages_map",
        "agents", "reply_templates", "conversations", "chart_data",
    ]

    @pytest.mark.parametrize("resource", RESOURCES)
    async def test_list_returns_data(self, client, resource):
        """每个资源 /api/data/{resource}/list 应返回 200 且 data 存在。"""
        response = await client.get(f"/api/data/{resource}/list")
        assert response.status_code == 200, f"{resource} list failed: {response.text}"
        data = response.json()
        assert "data" in data
        # messages_map 是 dict，其它是 list
        if resource == "messages_map":
            assert isinstance(data["data"], dict)
        else:
            assert isinstance(data["data"], list)


class TestDataRoutesCrud:
    """通用 CRUD 端点验收。"""

    async def test_create_update_delete_reply_template(self, client):
        """回复模板：创建 -> 更新 -> 删除 -> 确认已删除。"""
        # create
        create_resp = await client.post(
            "/api/data/reply_templates/create",
            json={"name": "验收测试模板", "keywords": ["测试"], "content": "测试内容", "enabled": True},
        )
        assert create_resp.status_code == 200
        created = create_resp.json()["item"]
        assert created["id"] is not None
        item_id = created["id"]

        # list contains it
        list_resp = await client.get("/api/data/reply_templates/list")
        items = [i["id"] for i in list_resp.json()["data"]]
        assert item_id in items

        # update
        update_resp = await client.put(
            f"/api/data/reply_templates/{item_id}",
            json={"name": "已更新模板"},
        )
        assert update_resp.status_code == 200
        list_resp = await client.get("/api/data/reply_templates/list")
        updated = next(i for i in list_resp.json()["data"] if i["id"] == item_id)
        assert updated["name"] == "已更新模板"

        # delete
        delete_resp = await client.delete(f"/api/data/reply_templates/{item_id}")
        assert delete_resp.status_code == 200
        list_resp = await client.get("/api/data/reply_templates/list")
        items = [i["id"] for i in list_resp.json()["data"]]
        assert item_id not in items

    async def test_create_conversation(self, client):
        """会话：创建后列表中可见。"""
        create_resp = await client.post(
            "/api/data/conversations/create",
            json={"title": "验收会话", "time": "刚刚"},
        )
        assert create_resp.status_code == 200
        created = create_resp.json()["item"]
        list_resp = await client.get("/api/data/conversations/list")
        items = [i["id"] for i in list_resp.json()["data"]]
        assert created["id"] in items

    async def test_create_chart_data(self, client):
        """图表数据：创建后列表中可见。"""
        create_resp = await client.post(
            "/api/data/chart_data/create",
            json={"label": "验收策略", "ctr": 1.0, "reply": 2.0, "conv": 3.0, "color": "#000"},
        )
        assert create_resp.status_code == 200
        created = create_resp.json()["item"]
        list_resp = await client.get("/api/data/chart_data/list")
        items_with_id = [i for i in list_resp.json()["data"] if "id" in i]
        assert created["id"] in [i["id"] for i in items_with_id]


class TestBusinessActions:
    """业务动作端点验收。"""

    async def test_team_member_toggle(self, client):
        """团队成员：启用/禁用切换。"""
        # 找到第一个成员
        list_resp = await client.get("/api/data/team/list")
        members = list_resp.json()["data"]
        if not members:
            pytest.skip("无团队成员数据，跳过")
        member_id = members[0]["id"]
        original_status = members[0]["status"]

        toggle_resp = await client.put(f"/api/data/team/{member_id}/toggle")
        assert toggle_resp.status_code == 200
        new_status = toggle_resp.json()["status"]
        assert new_status != original_status

        # 切回
        toggle_resp2 = await client.put(f"/api/data/team/{member_id}/toggle")
        assert toggle_resp2.json()["status"] == original_status

    async def test_lead_follow(self, client):
        """线索跟进：followCount 增加。"""
        list_resp = await client.get("/api/data/leads/list")
        leads = list_resp.json()["data"]
        if not leads:
            pytest.skip("无线索数据，跳过")
        lead_id = leads[0]["id"]
        original_count = leads[0].get("followCount", 0)

        follow_resp = await client.post(f"/api/data/leads/{lead_id}/follow")
        assert follow_resp.status_code == 200

        list_resp2 = await client.get("/api/data/leads/list")
        lead2 = next(l for l in list_resp2.json()["data"] if l["id"] == lead_id)
        assert lead2["followCount"] == original_count + 1

    async def test_strategy_update(self, client):
        """策略更新：可修改 enabled。"""
        list_resp = await client.get("/api/data/strategies/list")
        strategies = list_resp.json()["data"]
        if not strategies:
            pytest.skip("无策略数据，跳过")
        key = strategies[0]["key"]
        original_enabled = strategies[0]["enabled"]

        update_resp = await client.put(
            f"/api/data/strategies/{key}",
            json={"enabled": not original_enabled},
        )
        assert update_resp.status_code == 200

        list_resp2 = await client.get("/api/data/strategies/list")
        strategy2 = next(s for s in list_resp2.json()["data"] if s["key"] == key)
        assert strategy2["enabled"] is not original_enabled

        # 还原
        await client.put(f"/api/data/strategies/{key}", json={"enabled": original_enabled})


class TestRiskControlConfig:
    """风控配置端点验收。"""

    async def test_get_and_put_risk_config(self, client):
        """风控配置：GET 后 PUT 再 GET 验证持久化。"""
        get_resp = await client.get("/api/risk-control/config")
        assert get_resp.status_code == 200
        original = get_resp.json()
        assert "behavior" in original

        new_limits = {
            "dailyPublish": 999,
            "dailyComment": 999,
            "dailyDM": 999,
            "dailyAddFriend": 999,
            "smartStagger": True,
        }
        put_resp = await client.put(
            "/api/risk-control/config",
            json={"limits": new_limits},
        )
        assert put_resp.status_code == 200

        get_resp2 = await client.get("/api/risk-control/config")
        updated = get_resp2.json()
        assert updated["limits"]["dailyPublish"] == 999

        # 还原
        await client.put("/api/risk-control/config", json={"limits": original["limits"]})


class TestUnknownResources:
    """异常路径验收。"""

    async def test_unknown_resource_returns_400(self, client):
        """未知资源应返回 400。"""
        resp = await client.get("/api/data/unknown_xyz/list")
        assert resp.status_code == 400
