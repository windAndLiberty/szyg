"""AI Staff API acceptance tests — agent list, task CRUD, config management."""

import pytest


class TestStaffList:
    """GET /api/staff/list"""

    async def test_list_returns_staff(self, client):
        resp = await client.get("/api/staff/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "staff" in data or "agents" in data or isinstance(data, list)

    async def test_list_response_structure(self, client):
        """Verify each staff entry has required fields."""
        resp = await client.get("/api/staff/list")
        assert resp.status_code == 200
        data = resp.json()
        items = data if isinstance(data, list) else data.get("staff", data.get("agents", []))
        if items:
            first = items[0]
            assert "id" in first or "agent_id" in first or "name" in first

    async def test_list_contains_known_agents(self, client):
        """Verify default agents are present in the list."""
        resp = await client.get("/api/staff/list")
        data = resp.json()
        items = data if isinstance(data, list) else data.get("staff", data.get("agents", []))
        agent_ids = {s.get("id") for s in items}
        assert "content" in agent_ids
        assert "acquisition" in agent_ids or "acquisition" in agent_ids


class TestStaffGet:
    """GET /api/staff/{id}"""

    async def test_get_valid_agent(self, client):
        resp = await client.get("/api/staff/content")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("id") == "content"

    async def test_get_nonexistent(self, client):
        resp = await client.get("/api/staff/nonexistent_agent_99999")
        assert resp.status_code == 404


class TestStaffTasks:
    """Task CRUD endpoints — /api/staff/tasks/*"""

    async def test_list_tasks(self, client):
        resp = await client.get("/api/staff/tasks/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert isinstance(data["tasks"], list)

    async def test_create_task(self, client):
        resp = await client.post("/api/staff/tasks/create", json={
            "name": "验收测试任务",
            "assignee": "内容专员",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        task = data.get("task")
        assert task is not None
        assert task.get("id") is not None
        assert task.get("name") == "验收测试任务"

    async def test_create_task_with_all_fields(self, client):
        resp = await client.post("/api/staff/tasks/create", json={
            "name": "完整字段任务",
            "assignee": "运营专员",
            "priority": "high",
            "deadline": "2026-12-31",
        })
        assert resp.status_code == 200
        data = resp.json()
        task = data.get("task", {})
        assert task.get("priority") == "high"
        assert task.get("deadline") == "2026-12-31"
        assert task.get("status") == "ready"

    async def test_update_task(self, client):
        create_resp = await client.post("/api/staff/tasks/create", json={
            "name": "待更新任务",
            "assignee": "内容专员",
        })
        assert create_resp.status_code == 200
        task = create_resp.json().get("task", {})
        task_id = task.get("id")
        assert task_id is not None

        resp = await client.put(f"/api/staff/tasks/{task_id}", json={
            "status": "running",
            "progress": 50,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        updated = data.get("task", {})
        assert updated.get("status") == "running"
        assert updated.get("progress") == 50

    async def test_update_nonexistent_task(self, client):
        resp = await client.put("/api/staff/tasks/999999", json={
            "status": "done",
            "progress": 100,
        })
        assert resp.status_code == 404

    async def test_delete_task(self, client):
        create_resp = await client.post("/api/staff/tasks/create", json={
            "name": "待删除任务",
            "assignee": "内容专员",
        })
        assert create_resp.status_code == 200
        task_id = create_resp.json().get("task", {}).get("id")
        assert task_id is not None

        resp = await client.delete(f"/api/staff/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

    async def test_delete_nonexistent_task(self, client):
        """DELETE on nonexistent task returns 200 (idempotent)."""
        resp = await client.delete("/api/staff/tasks/999999")
        assert resp.status_code == 200


class TestStaffConfigs:
    """Agent config CRUD — /api/staff/configs/*"""

    async def test_list_configs(self, client):
        resp = await client.get("/api/staff/configs/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "configs" in data
        assert isinstance(data["configs"], dict)

    async def test_get_config_valid(self, client):
        resp = await client.get("/api/staff/configs/content")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        config = data["config"]
        assert "basic" in config
        assert config["basic"].get("name") == "内容专员"

    async def test_get_config_nonexistent(self, client):
        resp = await client.get("/api/staff/configs/nonexistent_agent_99999")
        assert resp.status_code == 404

    async def test_update_config(self, client):
        resp = await client.put("/api/staff/configs/content", json={
            "basic": {"name": "内容员工(测试)", "enabled": True},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

    async def test_update_config_nonexistent(self, client):
        resp = await client.put("/api/staff/configs/nonexistent_agent_99999", json={
            "basic": {"name": "不存在的员工"},
        })
        assert resp.status_code == 404

    async def test_reset_config(self, client):
        resp = await client.post("/api/staff/configs/content/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert "config" in data

    async def test_reset_config_nonexistent(self, client):
        resp = await client.post("/api/staff/configs/nonexistent_agent_99999/reset")
        assert resp.status_code == 404
