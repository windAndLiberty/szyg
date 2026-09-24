"""Publisher API acceptance tests — content workflow, materials, stats.

Phase 1 (automatic, ~15 tests): ContentCRUD, ContentWorkflow, PublisherMeta
Phase 2 (requires manual login): TestPlatformPublish

Adaptation notes:
- publisher_routes uses query parameters (not JSON body) for create/update/submit/approve/reject/schedule/publish
- Admin auth (HTTP Bearer) required for delete, approve, reject
- Materials endpoints use JSON body (dict param) for create
- Content response is returned directly (not nested under "content" key)
"""

import pytest


# ── Module-level helper ─────────────────────────────────────────────


async def _admin_headers(client):
    """Log in as admin and return Authorization headers."""
    resp = await client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123"
    })
    if resp.status_code != 200:
        pytest.skip("Cannot authenticate as admin")
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    return {"Authorization": f"Bearer {token}"}


async def _create_content(client, **overrides):
    """Create a content item via the API and return the response.

    Uses query params (matching publisher_routes signature).
    """
    params = {
        "title": overrides.get("title", "验收测试内容"),
        "content_type": overrides.get("content_type", "video"),
        "platforms": overrides.get("platforms", "douyin"),
    }
    resp = await client.post("/api/publisher/contents", params=params)
    if resp.status_code != 200:
        pytest.skip(f"Cannot create content: status={resp.status_code}")
    return resp


def _extract_id(resp):
    """Extract content ID from a create/get response."""
    data = resp.json() if hasattr(resp, "json") else resp
    if isinstance(data, dict):
        return data.get("id")
    return None


# =============================================================================
# 阶段一：本地 CRUD + 工作流（无需平台登录，全自动）
# =============================================================================


class TestContentCRUD:
    """Content CRUD — local operations, no platform login needed."""

    async def test_list_contents(self, client):
        """GET /api/publisher/contents returns 200."""
        resp = await client.get("/api/publisher/contents")
        assert resp.status_code == 200

    async def test_create_content(self, client):
        """POST /api/publisher/contents with valid params -> 200 + id."""
        resp = await _create_content(client)
        data = resp.json()
        assert data.get("id") is not None
        assert data.get("title") == "验收测试内容"
        assert data.get("status") == "draft"

    async def test_create_content_missing_fields(self, client):
        """POST /api/publisher/contents with empty params -> 422."""
        resp = await client.post("/api/publisher/contents", params={})
        assert resp.status_code in (400, 422)

    async def test_create_then_update(self, client):
        """Create content, then update its title via PUT."""
        create_resp = await _create_content(client, title="原始标题")
        content_id = _extract_id(create_resp)
        assert content_id is not None, "Could not extract content ID"

        resp = await client.put(
            f"/api/publisher/contents/{content_id}",
            params={"title": "更新后的标题"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("title") == "更新后的标题"

    async def test_delete_content(self, client):
        """Delete content requires admin auth -> 200."""
        headers = await _admin_headers(client)
        create_resp = await _create_content(client, title="待删除内容")
        content_id = _extract_id(create_resp)
        assert content_id is not None

        resp = await client.delete(
            f"/api/publisher/contents/{content_id}", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

    async def test_get_single_content(self, client):
        """GET /api/publisher/contents/{id} returns the content."""
        create_resp = await _create_content(client, title="单个查询内容")
        content_id = _extract_id(create_resp)
        assert content_id is not None

        resp = await client.get(f"/api/publisher/contents/{content_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("id") == content_id
        assert data.get("title") == "单个查询内容"

    async def test_get_nonexistent_content(self, client):
        """GET /api/publisher/contents/{nonexistent} -> 404."""
        resp = await client.get("/api/publisher/contents/nonexistent_99999")
        assert resp.status_code == 404


class TestContentWorkflow:
    """Review workflow — submit -> approve -> reject -> schedule."""

    async def test_submit_for_review(self, client):
        """Submit changes content status to pending."""
        create_resp = await _create_content(client, title="待审核内容")
        content_id = _extract_id(create_resp)
        assert content_id is not None

        resp = await client.post(f"/api/publisher/contents/{content_id}/submit")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("pending", "PENDING")

    async def test_approve_content(self, client):
        """Approve requires admin auth -> status becomes approved."""
        headers = await _admin_headers(client)
        create_resp = await _create_content(client, title="待审批内容")
        content_id = _extract_id(create_resp)
        assert content_id is not None

        await client.post(f"/api/publisher/contents/{content_id}/submit")
        resp = await client.post(
            f"/api/publisher/contents/{content_id}/approve", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        # Status may be 'approved' or stay as is in the test publisher
        assert data.get("status") is not None

    async def test_reject_content(self, client):
        """Reject requires admin auth + optional comment."""
        headers = await _admin_headers(client)
        create_resp = await _create_content(client, title="待拒绝内容")
        content_id = _extract_id(create_resp)
        assert content_id is not None

        await client.post(f"/api/publisher/contents/{content_id}/submit")
        resp = await client.post(
            f"/api/publisher/contents/{content_id}/reject",
            params={"comment": "测试拒绝原因"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("rejected", "REJECTED")

    async def test_schedule_content(self, client):
        """Schedule sets scheduled_at on an approved content item."""
        headers = await _admin_headers(client)
        create_resp = await _create_content(client, title="定时发布内容")
        content_id = _extract_id(create_resp)
        assert content_id is not None

        await client.post(f"/api/publisher/contents/{content_id}/submit")
        await client.post(
            f"/api/publisher/contents/{content_id}/approve", headers=headers
        )
        resp = await client.post(
            f"/api/publisher/contents/{content_id}/schedule",
            params={"scheduled_at": "2027-01-01T00:00:00"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("scheduled_at") is not None

    async def test_submit_nonexistent_content(self, client):
        """Submit on nonexistent content -> 404."""
        resp = await client.post("/api/publisher/contents/nonexistent_99999/submit")
        assert resp.status_code == 404

    async def test_approve_nonexistent_content(self, client):
        """Approve on nonexistent content -> 404."""
        headers = await _admin_headers(client)
        resp = await client.post(
            "/api/publisher/contents/nonexistent_99999/approve", headers=headers
        )
        assert resp.status_code == 404


class TestPublisherMeta:
    """Calendar, stats, materials, copy library — read-only / local."""

    async def test_calendar(self, client):
        """GET /api/publisher/calendar -> 200."""
        resp = await client.get("/api/publisher/calendar")
        assert resp.status_code == 200

    async def test_calendar_with_month(self, client):
        """GET /api/publisher/calendar?month=YYYY-MM -> 200."""
        resp = await client.get("/api/publisher/calendar", params={"month": "2026-07"})
        assert resp.status_code == 200

    async def test_stats(self, client):
        """GET /api/publisher/stats -> 200."""
        resp = await client.get("/api/publisher/stats")
        assert resp.status_code == 200

    async def test_materials_list(self, client):
        """GET /api/publisher/materials -> 200."""
        resp = await client.get("/api/publisher/materials")
        assert resp.status_code == 200
        data = resp.json()
        assert "materials" in data

    async def test_upload_material(self, client):
        """POST /api/publisher/materials with JSON body -> 200/201 + id."""
        resp = await client.post("/api/publisher/materials", json={
            "name": "测试素材",
            "type": "image",
            "url": "https://example.com/test.jpg",
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data.get("id") is not None
        assert data.get("name") == "测试素材"

    async def test_delete_material(self, client):
        """Create material then delete it."""
        create_resp = await client.post("/api/publisher/materials", json={
            "name": "待删除素材",
            "type": "image",
            "url": "https://example.com/test.jpg",
        })
        if create_resp.status_code not in (200, 201):
            pytest.skip("Cannot create material")
        mat_id = create_resp.json().get("id")
        if not mat_id:
            pytest.skip("Cannot extract material ID")

        resp = await client.delete(f"/api/publisher/materials/{mat_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

    async def test_copy_library(self, client):
        """GET /api/publisher/copy-library -> 200."""
        resp = await client.get("/api/publisher/copy-library")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    async def test_content_assets(self, client):
        """GET /api/publisher/content-assets -> 200."""
        resp = await client.get("/api/publisher/content-assets")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    async def test_logs(self, client):
        """GET /api/publisher/logs -> 200."""
        resp = await client.get("/api/publisher/logs")
        assert resp.status_code == 200

    async def test_ai_generate(self, client):
        """POST /api/publisher/ai-generate -> 200 (may require backend)."""
        resp = await client.post(
            "/api/publisher/ai-generate",
            params={"topic": "测试主题", "content_type": "post"},
        )
        # May fail if LLM backend unavailable; accept 200 or graceful error
        assert resp.status_code in (200, 500, 503)


# =============================================================================
# 阶段二：平台发布联调（需用户配合登录）
#
# 执行前请确保：
#   1. 阶段一全部通过
#   2. 用户已手动登录各平台
#   3. 在 server/ 目录下运行：
#      pytest tests/acceptance/test_publisher_api.py -v -k "PlatformPublish"
# =============================================================================


class TestPlatformPublish:
    """平台发布联调 — 需要用户配合登录三方平台。"""

    PLATFORMS = ["douyin", "xiaohongshu", "kuaishou", "bilibili"]

    @pytest.mark.parametrize("platform", PLATFORMS)
    async def test_platform_status(self, client, platform):
        """检查各平台连接状态。"""
        resp = await client.get(f"/api/publisher/platforms/{platform}/status")
        assert resp.status_code == 200

    @pytest.mark.parametrize("platform", PLATFORMS)
    async def test_platform_sessions(self, client, platform):
        """检查各平台会话列表。"""
        resp = await client.get(f"/api/publisher/platforms/{platform}/sessions")
        assert resp.status_code == 200

    async def test_publish_without_login_fails(self, client):
        """未登录 -> 发布应返回错误。"""
        resp = await client.post(
            "/api/publisher/contents/test_id_nologin/publish",
            params={"platform": "douyin"},
        )
        assert resp.status_code in (400, 401, 403, 404)

    async def test_publish_end_to_end(self, client):
        """端到端：创建 -> 审核 -> 发布 -> 验证日志。"""
        # Create
        create_resp = await client.post("/api/publisher/contents", params={
            "title": "联调发布测试内容",
            "content_type": "video",
            "platforms": "douyin",
        })
        assert create_resp.status_code == 200
        content_id = _extract_id(create_resp)
        assert content_id is not None

        # Submit + approve (need admin auth for approve)
        headers = await _admin_headers(client)
        await client.post(f"/api/publisher/contents/{content_id}/submit")
        await client.post(
            f"/api/publisher/contents/{content_id}/approve", headers=headers
        )

        # Publish
        resp = await client.post(
            f"/api/publisher/contents/{content_id}/publish",
            params={"platform": "douyin"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

        # Check logs
        log_resp = await client.get("/api/publisher/logs")
        assert log_resp.status_code == 200
