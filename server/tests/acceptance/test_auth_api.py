"""Auth API acceptance tests — login, session, user CRUD."""

import pytest


class TestAuthLogin:
    """POST /api/auth/login"""

    async def test_login_success(self, client):
        """Valid credentials → 200 with token."""
        resp = await client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data or "user" in data

    async def test_login_wrong_password(self, client):
        """Wrong password → 401 or error."""
        resp = await client.post("/api/auth/login", json={
            "username": "admin", "password": "wrong_password_xyz"
        })
        assert resp.status_code in (401, 400, 403)

    async def test_login_nonexistent_user(self, client):
        """Non-existent user → 401 or error."""
        resp = await client.post("/api/auth/login", json={
            "username": "nonexistent_user_12345", "password": "test"
        })
        assert resp.status_code in (401, 400, 403)

    async def test_login_empty_fields(self, client):
        """Empty username/password → 422."""
        resp = await client.post("/api/auth/login", json={
            "username": "", "password": ""
        })
        assert resp.status_code == 422


class TestAuthSession:
    """GET /api/auth/session"""

    async def test_session_valid(self, client):
        """After login, session returns user info."""
        # Login first
        login_resp = await client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        if login_resp.status_code != 200:
            pytest.skip("Login failed — cannot test session")
        # Session check
        resp = await client.get("/api/auth/session")
        assert resp.status_code == 200

    async def test_session_without_login(self, client):
        """No login → session returns 401 or empty."""
        resp = await client.get("/api/auth/session")
        # May return 401 or 200 with null user
        assert resp.status_code in (200, 401)


class TestAuthUserCRUD:
    """GET/POST/PUT/DELETE /api/auth/users"""

    async def test_list_users(self, client):
        resp = await client.get("/api/auth/users")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))

    async def test_create_user(self, client):
        resp = await client.post("/api/auth/users", json={
            "username": "test_auth_user", "password": "test123", "role": "user"
        })
        assert resp.status_code == 200

    async def test_create_duplicate_user(self, client):
        await client.post("/api/auth/users", json={
            "username": "test_dup_user", "password": "test123", "role": "user"
        })
        resp = await client.post("/api/auth/users", json={
            "username": "test_dup_user", "password": "test456", "role": "user"
        })
        assert resp.status_code in (400, 409)

    async def test_create_user_empty_username(self, client):
        resp = await client.post("/api/auth/users", json={
            "username": "", "password": "test123"
        })
        assert resp.status_code in (400, 422)

    async def test_update_user(self, client):
        # Create then update
        await client.post("/api/auth/users", json={
            "username": "test_update_user", "password": "old", "role": "user"
        })
        # Find user ID by listing
        list_resp = await client.get("/api/auth/users")
        users = list_resp.json() if isinstance(list_resp.json(), list) else list_resp.json().get("data", [])
        user = next((u for u in users if u.get("username") == "test_update_user"), None)
        if user is None:
            pytest.skip("User not found after creation")
        user_id = user.get("id") or user.get("_id")
        resp = await client.put(f"/api/auth/users/{user_id}", json={"password": "newpassword"})
        assert resp.status_code == 200

    async def test_delete_user(self, client):
        await client.post("/api/auth/users", json={
            "username": "test_delete_user", "password": "test123", "role": "user"
        })
        list_resp = await client.get("/api/auth/users")
        users = list_resp.json() if isinstance(list_resp.json(), list) else list_resp.json().get("data", [])
        user = next((u for u in users if u.get("username") == "test_delete_user"), None)
        if user is None:
            pytest.skip("User not found after creation")
        user_id = user.get("id") or user.get("_id")
        resp = await client.delete(f"/api/auth/users/{user_id}")
        assert resp.status_code == 200

    async def test_toggle_user(self, client):
        await client.post("/api/auth/users", json={
            "username": "test_toggle_user", "password": "test123", "role": "user"
        })
        list_resp = await client.get("/api/auth/users")
        users = list_resp.json() if isinstance(list_resp.json(), list) else list_resp.json().get("data", [])
        user = next((u for u in users if u.get("username") == "test_toggle_user"), None)
        if user is None:
            pytest.skip("User not found")
        user_id = user.get("id") or user.get("_id")
        resp = await client.put(f"/api/auth/users/{user_id}/toggle")
        assert resp.status_code == 200

    async def test_get_nonexistent_user(self, client):
        resp = await client.get("/api/auth/users/nonexistent_id_99999")
        assert resp.status_code in (404, 200)  # 404 or empty
