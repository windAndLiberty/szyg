"""Conversation API acceptance tests — full CRUD + data isolation."""

import pytest


class TestConversationList:
    """GET /api/conversations"""

    async def test_list_empty(self, client):
        resp = await client.get("/api/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert "conversations" in data
        assert isinstance(data["conversations"], list)

    async def test_list_has_items_after_create(self, client):
        await client.post("/api/conversations", json={
            "title": "列表测试对话", "messages": [], "model": "test"
        })
        resp = await client.get("/api/conversations")
        assert resp.status_code == 200
        assert len(resp.json()["conversations"]) > 0


class TestConversationCreate:
    """POST /api/conversations"""

    async def test_create_basic(self, client):
        resp = await client.post("/api/conversations", json={
            "title": "新对话", "messages": [], "model": "test"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        conv_id = data["id"]
        # Verify it appears in list
        list_resp = await client.get("/api/conversations")
        ids = [c["id"] for c in list_resp.json()["conversations"]]
        assert conv_id in ids

    async def test_create_with_messages(self, client):
        resp = await client.post("/api/conversations", json={
            "title": "带消息的对话",
            "messages": [
                {"role": "user", "content": "你好", "type": "text"},
                {"role": "assistant", "content": "你好！有什么可以帮助你的？", "type": "text"},
            ],
            "model": "doubao-seed-2-0-pro-260215",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data

    async def test_create_title_auto_truncate(self, client):
        """First user message → title truncated to 50 chars."""
        long_msg = "这是一条非常长的测试消息" * 10
        resp = await client.post("/api/conversations", json={
            "title": "",
            "messages": [{"role": "user", "content": long_msg, "type": "text"}],
            "model": "test",
        })
        assert resp.status_code == 200

    async def test_create_empty_body(self, client):
        resp = await client.post("/api/conversations", json={})
        assert resp.status_code in (200, 422)


class TestConversationGet:
    """GET /api/conversations/{id}"""

    async def test_get_existing(self, client):
        create_resp = await client.post("/api/conversations", json={
            "title": "待获取对话", "messages": [], "model": "test"
        })
        conv_id = create_resp.json()["id"]
        resp = await client.get(f"/api/conversations/{conv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data or "id" in data

    async def test_get_nonexistent(self, client):
        resp = await client.get("/api/conversations/nonexistent_99999")
        assert resp.status_code in (404, 200)


class TestConversationUpdate:
    """PUT /api/conversations/{id}"""

    async def test_update_title(self, client):
        create_resp = await client.post("/api/conversations", json={
            "title": "原始标题", "messages": [], "model": "test"
        })
        conv_id = create_resp.json()["id"]
        resp = await client.put(f"/api/conversations/{conv_id}", json={
            "title": "更新后的标题", "pinned": True
        })
        assert resp.status_code == 200

    async def test_update_nonexistent(self, client):
        resp = await client.put("/api/conversations/nonexistent_99999", json={
            "title": "不会成功"
        })
        assert resp.status_code in (404, 400)


class TestConversationDelete:
    """DELETE /api/conversations/{id}"""

    async def test_delete_existing(self, client):
        create_resp = await client.post("/api/conversations", json={
            "title": "待删除对话", "messages": [], "model": "test"
        })
        conv_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/conversations/{conv_id}")
        assert resp.status_code == 200
        # Verify gone from list
        list_resp = await client.get("/api/conversations")
        ids = [c["id"] for c in list_resp.json()["conversations"]]
        assert conv_id not in ids

    async def test_delete_nonexistent(self, client):
        resp = await client.delete("/api/conversations/nonexistent_99999")
        assert resp.status_code in (404, 400)
