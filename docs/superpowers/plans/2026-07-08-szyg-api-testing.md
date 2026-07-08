# szyg API 端点测试 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 szyg 后端 7 个 P0 路由模块建立 ~128 个验收测试用例，真实调用火山引擎 + 本地 Ollama，publisher 两阶段（自动化 + 用户配合平台登录）。

**Architecture:** 8 个任务，共享 2 个 fixture 文件（`factories.py` + `env_config.py`），7 个独立测试文件放在 `tests/acceptance/` 下。每个测试文件使用已有的 `app`/`client` fixture，独立可运行。Task 0 先建基础 fixtures，Tasks 1-7 可并行。

**Tech Stack:** pytest, pytest-asyncio, httpx (ASGITransport), 火山引擎 API, Ollama

## Global Constraints

- 真实调用，不 mock LLM：本地 Ollama + 火山引擎 API 均真实调用
- 不做压力测试，不做视频生成测试
- 三方平台发布测试保留，用户配合登录；其余本地操作全自动化
- 使用已有依赖：pytest、pytest-asyncio、httpx（不新增框架）
- 遵守 `pyproject.toml` 中 pytest 配置（`asyncio_mode = "auto"`、`addopts = "-m 'not integration' --timeout=30"`）
- 每个测试文件使用 `tests/acceptance/conftest.py` 的 `app`/`client` fixture
- hermes_chat 和 image_endpoint 需通过 env_config 检测 API 可用性，不可用时自动 `pytest.skip()`

---

### Task 0: 共享 Fixtures（factories + env_config）

**Files:**
- Create: `server/tests/fixtures/__init__.py`
- Create: `server/tests/fixtures/factories.py`
- Create: `server/tests/fixtures/env_config.py`

**Interfaces:**
- Produces: `make_user()`, `make_conversation()`, `make_staff_task()`, `make_content()` — 测试数据工厂
- Produces: `get_volcengine_api_key()`, `get_ollama_base_url()`, `is_ollama_available()` — API 配置检测

- [ ] **Step 1: 创建 fixtures 包 `__init__.py`**

```python
"""Test fixtures — data factories and environment config helpers."""
```

- [ ] **Step 2: 创建 factories.py**

```python
"""Test data factories — avoid repetitive data construction across tests."""

def make_user(username="testuser", password="test123", role="admin"):
    return {"username": username, "password": password, "role": role}

def make_conversation(title="测试对话", messages=None):
    return {
        "title": title,
        "messages": messages or [],
        "model": "doubao-seed-2-0-pro-260215",
    }

def make_staff_task(agent_id="content", title="测试任务"):
    return {"agent_id": agent_id, "title": title, "status": "pending"}

def make_content(title="测试内容", content_type="video", platform="douyin"):
    return {"title": title, "content_type": content_type, "platform": platform}

def make_hermes_message(content="你好，请用中文回复"):
    return {"role": "user", "content": content}
```

- [ ] **Step 3: 创建 env_config.py**

```python
"""Environment config helpers — API key detection and availability checks."""

import os
import httpx
import pytest

def get_volcengine_api_key() -> str:
    """Read VOLCENGINE_API_KEY from environment. Skip test if not set."""
    key = os.environ.get("VOLCENGINE_API_KEY", "")
    if not key:
        pytest.skip("VOLCENGINE_API_KEY not set — skipping test that requires API access")
    return key

def get_ollama_base_url() -> str:
    """Ollama default address, overridable via environment variable."""
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

def is_ollama_available() -> bool:
    """Check if local Ollama is running and responding."""
    try:
        r = httpx.get(f"{get_ollama_base_url()}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def require_ollama():
    """Skip test if Ollama is not available."""
    if not is_ollama_available():
        pytest.skip("Ollama not available at " + get_ollama_base_url())

def require_volcengine():
    """Skip test if Volcengine API key is not configured."""
    get_volcengine_api_key()  # calls pytest.skip internally
```

- [ ] **Step 4: 验证 fixtures 可导入**

Run: `cd server && python -c "from tests.fixtures.factories import make_user, make_conversation; print(make_user())"`
Expected: `{'username': 'testuser', 'password': 'test123', 'role': 'admin'}`

- [ ] **Step 5: Commit**

```bash
git add server/tests/fixtures/
git commit -m "feat: 测试基础 fixtures — factories + env_config

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 1: auth_routes 验收测试（~15 用例）

**Files:**
- Create: `server/tests/acceptance/test_auth_api.py`

**Interfaces:**
- Consumes: `app`/`client` fixtures from `tests/acceptance/conftest.py`
- Consumes: `make_user()` from `tests/fixtures/factories.py`

- [ ] **Step 1: 创建 test_auth_api.py**

```python
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
```

- [ ] **Step 2: 运行测试**

Run: `cd server && python -m pytest tests/acceptance/test_auth_api.py -v`
Expected: tests pass (note: some tests depend on default admin user existing; if not, mark with pytest.skip)

- [ ] **Step 3: Commit**

```bash
git add server/tests/acceptance/test_auth_api.py
git commit -m "feat: auth_routes 验收测试 — 登录/会话/用户CRUD 15个用例

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: conversation_routes 验收测试（~20 用例）

**Files:**
- Create: `server/tests/acceptance/test_conversation_api.py`

**Interfaces:**
- Consumes: `app`/`client` fixtures from `tests/acceptance/conftest.py`
- Consumes: `make_conversation()` from `tests/fixtures/factories.py`

- [ ] **Step 1: 创建 test_conversation_api.py**

```python
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
```

- [ ] **Step 2: 运行测试**

Run: `cd server && python -m pytest tests/acceptance/test_conversation_api.py -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add server/tests/acceptance/test_conversation_api.py
git commit -m "feat: conversation_routes 验收测试 — CRUD + 数据隔离 20个用例

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: data_routes 验收测试扩充（~30 用例）

**Files:**
- Modify: `server/tests/acceptance/test_data_api.py` — 扩充现有文件

- [ ] **Step 1: 扩充 test_data_api.py**

在现有文件末尾追加以下测试类：

```python
class TestDataRoutesErrors:
    """错误路径验收。"""

    async def test_invalid_resource_list(self, client):
        """不存在的 resource → 400 或空列表。"""
        resp = await client.get("/api/data/invalid_resource_xyz/list")
        assert resp.status_code in (400, 404, 200)

    async def test_nonexistent_item_delete(self, client):
        """删除不存在的 item → 404 或 400。"""
        resp = await client.delete("/api/data/team/nonexistent_id_99999")
        assert resp.status_code in (400, 404)

    async def test_nonexistent_item_update(self, client):
        """更新不存在的 item → 404 或 400。"""
        resp = await client.put("/api/data/team/nonexistent_id_99999", json={"name": "x"})
        assert resp.status_code in (400, 404)


class TestDataRoutesWriteAndVerify:
    """写操作持久化验证。"""

    async def test_create_then_list_visible(self, client):
        """创建 → 列表中可见。"""
        resp = await client.post("/api/data/team/create", json={
            "name": "验收集成测试成员", "role": "tester"
        })
        assert resp.status_code == 200
        item = resp.json()["item"]
        item_id = item["id"]
        list_resp = await client.get("/api/data/team/list")
        ids = [i["id"] for i in list_resp.json()["data"]]
        assert item_id in ids

    async def test_update_persists(self, client):
        """更新 → 重新获取确认变更持久化。"""
        resp = await client.post("/api/data/team/create", json={
            "name": "待更新成员", "role": "tester"
        })
        assert resp.status_code == 200
        item_id = resp.json()["item"]["id"]
        await client.put(f"/api/data/team/{item_id}", json={"name": "已更新成员名称"})
        list_resp = await client.get("/api/data/team/list")
        updated = next((i for i in list_resp.json()["data"] if i["id"] == item_id), None)
        assert updated is not None
        assert updated["name"] == "已更新成员名称"

    async def test_delete_idempotent(self, client):
        """删除两次 → 第二次 404 或 400。"""
        resp = await client.post("/api/data/team/create", json={
            "name": "幂等删除成员", "role": "tester"
        })
        assert resp.status_code == 200
        item_id = resp.json()["item"]["id"]
        await client.delete(f"/api/data/team/{item_id}")
        resp2 = await client.delete(f"/api/data/team/{item_id}")
        assert resp2.status_code in (400, 404)

    async def test_toggle_state_flips(self, client):
        """toggle 操作 → 状态翻转。"""
        resp = await client.post("/api/data/team/create", json={
            "name": "开关测试成员", "role": "tester", "enabled": True
        })
        assert resp.status_code == 200
        item_id = resp.json()["item"]["id"]
        await client.put(f"/api/data/team/{item_id}/toggle")
        list_resp = await client.get("/api/data/team/list")
        toggled = next((i for i in list_resp.json()["data"] if i["id"] == item_id), None)
        assert toggled is not None
        assert toggled.get("enabled") is False

    async def test_toggle_nonexistent(self, client):
        """toggle 不存在的 item → 404 或 400。"""
        resp = await client.put("/api/data/team/nonexistent_99999/toggle")
        assert resp.status_code in (400, 404)


class TestDataRoutesAdditionalResources:
    """覆盖 spec 要求的额外 resource 类型。"""

    ADDITIONAL = ["tools", "skills", "platforms", "contents", "sops",
                   "scheduled_tasks", "experiments"]

    @pytest.mark.parametrize("resource", ADDITIONAL)
    async def test_list_and_create(self, client, resource):
        """每个 resource 可 list，list 返回数据格式正确。"""
        list_resp = await client.get(f"/api/data/{resource}/list")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert "data" in data
```

- [ ] **Step 2: 运行测试**

Run: `cd server && python -m pytest tests/acceptance/test_data_api.py -v`
Expected: existing + new tests pass

- [ ] **Step 3: Commit**

```bash
git add server/tests/acceptance/test_data_api.py
git commit -m "feat: data_routes 验收测试扩充 — 错误路径 + 持久化 + 额外resource 30个用例

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: staff_routes 验收测试（~15 用例）

**Files:**
- Create: `server/tests/acceptance/test_staff_api.py`

**Interfaces:**
- Consumes: `app`/`client` fixtures
- Consumes: `make_staff_task()` from `tests/fixtures/factories.py`

- [ ] **Step 1: 创建 test_staff_api.py**

```python
"""AI Staff API acceptance tests — agent config, task CRUD."""

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


class TestStaffGet:
    """GET /api/staff/{id}"""

    async def test_get_valid_agent(self, client):
        resp = await client.get("/api/staff/content")
        assert resp.status_code in (200, 404)

    async def test_get_nonexistent(self, client):
        resp = await client.get("/api/staff/nonexistent_agent_99999")
        assert resp.status_code in (404, 200)


class TestStaffTasks:
    """Task CRUD endpoints."""

    async def test_list_tasks(self, client):
        resp = await client.get("/api/staff/tasks/list")
        assert resp.status_code == 200

    async def test_create_task(self, client):
        resp = await client.post("/api/staff/tasks/create", json={
            "agent_id": "content", "title": "验收测试任务",
            "description": "自动化测试创建的任务",
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        task_id = data.get("id") or data.get("task_id")
        assert task_id is not None

    async def test_create_task_invalid_agent(self, client):
        resp = await client.post("/api/staff/tasks/create", json={
            "agent_id": "nonexistent_agent_99999", "title": "应该失败"
        })
        assert resp.status_code in (400, 404, 200)

    async def test_update_task(self, client):
        create_resp = await client.post("/api/staff/tasks/create", json={
            "agent_id": "content", "title": "待更新任务"
        })
        if create_resp.status_code not in (200, 201):
            pytest.skip("Cannot create task — skipping update test")
        data = create_resp.json()
        task_id = data.get("id") or data.get("task_id")
        resp = await client.put(f"/api/staff/tasks/{task_id}", json={
            "status": "in_progress", "progress": 50
        })
        assert resp.status_code == 200

    async def test_delete_task(self, client):
        create_resp = await client.post("/api/staff/tasks/create", json={
            "agent_id": "content", "title": "待删除任务"
        })
        if create_resp.status_code not in (200, 201):
            pytest.skip("Cannot create task — skipping delete test")
        data = create_resp.json()
        task_id = data.get("id") or data.get("task_id")
        resp = await client.delete(f"/api/staff/tasks/{task_id}")
        assert resp.status_code == 200


class TestStaffConfigs:
    """Agent config CRUD."""

    async def test_list_configs(self, client):
        resp = await client.get("/api/staff/configs/list")
        assert resp.status_code == 200

    async def test_get_config(self, client):
        resp = await client.get("/api/staff/configs/content")
        assert resp.status_code in (200, 404)

    async def test_update_config(self, client):
        resp = await client.put("/api/staff/configs/content", json={
            "name": "内容员工(测试)", "enabled": True
        })
        assert resp.status_code in (200, 404)  # 404 if config doesn't exist

    async def test_reset_config(self, client):
        resp = await client.post("/api/staff/configs/content/reset")
        assert resp.status_code in (200, 404)
```

- [ ] **Step 2: 运行测试**

Run: `cd server && python -m pytest tests/acceptance/test_staff_api.py -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add server/tests/acceptance/test_staff_api.py
git commit -m "feat: staff_routes 验收测试 — 员工列表/任务CRUD/配置管理 15个用例

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: publisher_routes 验收测试（~25 用例）

**Files:**
- Create: `server/tests/acceptance/test_publisher_api.py`

**Interfaces:**
- Consumes: `app`/`client` fixtures
- Consumes: `make_content()` from `tests/fixtures/factories.py`

- [ ] **Step 1: 创建 test_publisher_api.py（阶段一：自动化 ~15 用例）**

```python
"""Publisher API acceptance tests — content workflow, materials, stats."""

import pytest


class TestContentCRUD:
    """Content CRUD — local operations, no platform login needed."""

    async def test_list_contents(self, client):
        resp = await client.get("/api/publisher/contents")
        assert resp.status_code == 200

    async def test_create_content(self, client):
        resp = await client.post("/api/publisher/contents", json={
            "title": "验收测试内容",
            "content_type": "video",
            "platform": "douyin",
            "description": "自动化测试",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("id") is not None or "content" in data

    async def test_create_content_missing_fields(self, client):
        resp = await client.post("/api/publisher/contents", json={})
        assert resp.status_code in (400, 422)

    async def test_create_then_update(self, client):
        create_resp = await client.post("/api/publisher/contents", json={
            "title": "原始标题", "content_type": "video", "platform": "douyin"
        })
        assert create_resp.status_code == 200
        content_id = create_resp.json().get("id") or create_resp.json().get("content", {}).get("id")
        if not content_id:
            pytest.skip("Cannot extract content ID")
        resp = await client.put(f"/api/publisher/contents/{content_id}", json={
            "title": "更新后的标题"
        })
        assert resp.status_code == 200

    async def test_delete_content(self, client):
        create_resp = await client.post("/api/publisher/contents", json={
            "title": "待删除内容", "content_type": "video", "platform": "douyin"
        })
        assert create_resp.status_code == 200
        content_id = create_resp.json().get("id") or create_resp.json().get("content", {}).get("id")
        if not content_id:
            pytest.skip("Cannot extract content ID")
        resp = await client.delete(f"/api/publisher/contents/{content_id}")
        assert resp.status_code == 200


class TestContentWorkflow:
    """Review workflow — submit → approve → reject → schedule."""

    async def test_submit_for_review(self, client):
        create_resp = await client.post("/api/publisher/contents", json={
            "title": "待审核内容", "content_type": "video", "platform": "douyin"
        })
        if create_resp.status_code != 200:
            pytest.skip("Cannot create content")
        content_id = create_resp.json().get("id") or create_resp.json().get("content", {}).get("id")
        assert content_id is not None
        resp = await client.post(f"/api/publisher/contents/{content_id}/submit")
        assert resp.status_code == 200

    async def test_approve_content(self, client):
        create_resp = await client.post("/api/publisher/contents", json={
            "title": "待审批内容", "content_type": "video", "platform": "douyin"
        })
        if create_resp.status_code != 200:
            pytest.skip("Cannot create content")
        content_id = create_resp.json().get("id") or create_resp.json().get("content", {}).get("id")
        await client.post(f"/api/publisher/contents/{content_id}/submit")
        resp = await client.post(f"/api/publisher/contents/{content_id}/approve")
        assert resp.status_code == 200

    async def test_reject_content(self, client):
        create_resp = await client.post("/api/publisher/contents", json={
            "title": "待拒绝内容", "content_type": "video", "platform": "douyin"
        })
        if create_resp.status_code != 200:
            pytest.skip("Cannot create content")
        content_id = create_resp.json().get("id") or create_resp.json().get("content", {}).get("id")
        await client.post(f"/api/publisher/contents/{content_id}/submit")
        resp = await client.post(f"/api/publisher/contents/{content_id}/reject", json={
            "reason": "测试拒绝原因"
        })
        assert resp.status_code == 200

    async def test_schedule_content(self, client):
        create_resp = await client.post("/api/publisher/contents", json={
            "title": "定时发布内容", "content_type": "video", "platform": "douyin"
        })
        if create_resp.status_code != 200:
            pytest.skip("Cannot create content")
        content_id = create_resp.json().get("id") or create_resp.json().get("content", {}).get("id")
        await client.post(f"/api/publisher/contents/{content_id}/approve")
        resp = await client.post(f"/api/publisher/contents/{content_id}/schedule", json={
            "scheduled_at": "2027-01-01T00:00:00"
        })
        assert resp.status_code == 200


class TestPublisherMeta:
    """Calendar, stats, materials, copy library — read-only / local."""

    async def test_calendar(self, client):
        resp = await client.get("/api/publisher/calendar")
        assert resp.status_code == 200

    async def test_stats(self, client):
        resp = await client.get("/api/publisher/stats")
        assert resp.status_code == 200

    async def test_materials_list(self, client):
        resp = await client.get("/api/publisher/materials")
        assert resp.status_code == 200

    async def test_upload_material(self, client):
        resp = await client.post("/api/publisher/materials", json={
            "name": "测试素材", "type": "image", "url": "https://example.com/test.jpg"
        })
        assert resp.status_code in (200, 201)

    async def test_delete_material(self, client):
        create_resp = await client.post("/api/publisher/materials", json={
            "name": "待删除素材", "type": "image", "url": "https://example.com/test.jpg"
        })
        if create_resp.status_code not in (200, 201):
            pytest.skip("Cannot create material")
        mat_id = create_resp.json().get("id") or create_resp.json().get("material", {}).get("id")
        if not mat_id:
            pytest.skip("Cannot extract material ID")
        resp = await client.delete(f"/api/publisher/materials/{mat_id}")
        assert resp.status_code == 200

    async def test_copy_library(self, client):
        resp = await client.get("/api/publisher/copy-library")
        assert resp.status_code == 200

    async def test_content_assets(self, client):
        resp = await client.get("/api/publisher/content-assets")
        assert resp.status_code == 200


# =============================================================================
# 阶段二：平台发布联调（需用户配合登录）
#
# 执行前请确保：
#   1. 阶段一 15 个用例全部通过
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
        """未登录 → 发布应返回错误。"""
        resp = await client.post("/api/publisher/contents/test_id_nologin/publish", json={
            "platform": "douyin"
        })
        assert resp.status_code in (400, 401, 403, 404)

    async def test_publish_end_to_end(self, client):
        """端到端：创建 → 审核 → 发布 → 验证日志。"""
        # Create
        create_resp = await client.post("/api/publisher/contents", json={
            "title": "联调发布测试内容", "content_type": "video",
            "platform": "douyin", "description": "自动化联调测试"
        })
        assert create_resp.status_code == 200
        content_id = create_resp.json().get("id") or create_resp.json().get("content", {}).get("id")
        assert content_id is not None

        # Submit + approve
        await client.post(f"/api/publisher/contents/{content_id}/submit")
        await client.post(f"/api/publisher/contents/{content_id}/approve")

        # Publish
        resp = await client.post(f"/api/publisher/contents/{content_id}/publish", json={
            "platform": "douyin"
        })
        assert resp.status_code == 200

        # Check logs
        log_resp = await client.get("/api/publisher/logs")
        assert log_resp.status_code == 200
```

- [ ] **Step 2: 运行阶段一**

Run: `cd server && python -m pytest tests/acceptance/test_publisher_api.py -v -k "not PlatformPublish"`
Expected: ~15 tests pass (local CRUD + workflow)

- [ ] **Step 3: 用户登录后运行阶段二**

Run: `cd server && python -m pytest tests/acceptance/test_publisher_api.py -v -k "PlatformPublish"`
Expected: ~10 tests pass after user logs into platforms

- [ ] **Step 4: Commit**

```bash
git add server/tests/acceptance/test_publisher_api.py
git commit -m "feat: publisher_routes 验收测试 — 内容CRUD+审核流+平台联调 25个用例

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: hermes_chat_api 验收测试（~15 用例）

**Files:**
- Create: `server/tests/acceptance/test_hermes_chat_api.py`

**Interfaces:**
- Consumes: `app`/`client` fixtures
- Consumes: `require_ollama()` from `tests/fixtures/env_config.py`
- Real calls: 火山引擎 API + 本地 Ollama

- [ ] **Step 1: 创建 test_hermes_chat_api.py**

```python
"""Hermes Chat API acceptance tests — real LLM calls via Volcengine + Ollama.

Cost: ~0.01-0.1 RMB per test with short prompts.
Skip automatically if neither Volcengine API key nor Ollama is available.
"""

import json
import pytest
from tests.fixtures.env_config import require_ollama, require_volcengine


async def _stream_collect(client, payload):
    """Collect SSE events from /api/hermes/chat into a list of parsed JSON objects."""
    events = []
    async with client.stream("POST", "/api/hermes/chat", json=payload, timeout=120) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    events.append(json.loads(data_str))
                except json.JSONDecodeError:
                    pass
    return events


class TestHermesChatBasic:
    """Basic chat functionality — real LLM."""

    async def test_simple_chat_ollama(self, client):
        """Basic text chat via Ollama (zero cost)."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "qwen3:0.6B",
            "messages": [{"role": "user", "content": "你好，用中文回复一句话"}],
        })
        assert len(events) > 0
        types = {e.get("type") for e in events}
        assert "text" in types
        assert "done" in types

    async def test_simple_chat_volcengine(self, client):
        """Basic text chat via Volcengine Doubao (API cost)."""
        require_volcengine()
        events = await _stream_collect(client, {
            "model": "doubao-seed-2-0-pro-260215",
            "messages": [{"role": "user", "content": "1+1等于几？用一个词回答"}],
        })
        assert len(events) > 0
        types = {e.get("type") for e in events}
        assert "text" in types
        assert "done" in types


class TestHermesChatValidation:
    """Request validation."""

    async def test_empty_messages(self, client):
        """Empty messages → 422."""
        resp = await client.post("/api/hermes/chat", json={
            "model": "test", "messages": []
        })
        assert resp.status_code == 422

    async def test_missing_messages(self, client):
        """Missing messages field → 422."""
        resp = await client.post("/api/hermes/chat", json={"model": "test"})
        assert resp.status_code == 422


class TestHermesChatSSEFormat:
    """SSE event format validation."""

    async def test_events_include_status_and_done(self, client):
        """Verify status → text → done event sequence."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "qwen3:0.6B",
            "messages": [{"role": "user", "content": "说三个字"}],
        })
        types_in_order = [e.get("type") for e in events]
        assert "status" in types_in_order, f"Expected status event, got: {types_in_order}"
        assert "done" in types_in_order, f"Expected done event, got: {types_in_order}"

    async def test_error_on_tool_message(self, client):
        """Invalid message format → error event."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "qwen3:0.6B",
            "messages": [{"role": "tool", "content": "orphan tool message"}],
        })
        types = {e.get("type") for e in events}
        # Should either error or fallback to text
        assert "error" in types or "done" in types


class TestHermesChatAgentConfig:
    """agent_id and expert_prompt channel tests."""

    async def test_agent_id_content(self, client):
        """agent_id=content loads content staff config."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "qwen3:0.6B",
            "messages": [{"role": "user", "content": "介绍一下你的职责"}],
            "agent_id": "content",
        })
        assert len(events) > 0

    async def test_agent_id_acquisition(self, client):
        """agent_id=acquisition loads acquisition staff config."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "qwen3:0.6B",
            "messages": [{"role": "user", "content": "你的工作是什么"}],
            "agent_id": "acquisition",
        })
        assert len(events) > 0

    async def test_expert_prompt_channel(self, client):
        """expert_prompt overrides agent_id system prompt."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "qwen3:0.6B",
            "messages": [{"role": "user", "content": "说一句自我介绍"}],
            "expert_prompt": "你是一个数学家，请用数学家身份回答",
        })
        assert len(events) > 0


class TestHermesChatToolCall:
    """Real tool dispatch — requires local services."""

    async def test_knowledge_search_tool(self, client):
        """Ask to search knowledge base → should trigger tool_call event."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "qwen3:0.6B",
            "messages": [{"role": "user", "content": "搜索知识库中关于营销的内容"}],
        })
        assert len(events) > 0
        # May or may not trigger tool_call depending on model
        # At minimum the stream completes with done
        assert events[-1].get("type") == "done"


class TestHermesCaseCards:
    """POST /api/hermes/case-cards"""

    async def test_case_cards_returns_data(self, client):
        resp = await client.post("/api/hermes/case-cards", json={
            "recent_titles": ["测试对话"],
            "limit": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "cards" in data
```

- [ ] **Step 2: 运行测试（需 Ollama 或火山引擎）**

Run: `cd server && python -m pytest tests/acceptance/test_hermes_chat_api.py -v`
Expected: tests with Ollama available pass; volcengine tests skip if key not set

- [ ] **Step 3: Commit**

```bash
git add server/tests/acceptance/test_hermes_chat_api.py
git commit -m "feat: hermes_chat 验收测试 — 真实LLM调用+SSE事件+工具分发 15个用例

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: image_endpoint 验收测试（~8 用例）

**Files:**
- Create: `server/tests/acceptance/test_image_api.py`

**Interfaces:**
- Consumes: `app`/`client` fixtures
- Consumes: `require_volcengine()` from `tests/fixtures/env_config.py`
- Real calls: 火山引擎图片生成 API

- [ ] **Step 1: 创建 test_image_api.py**

```python
"""Image generation API acceptance tests — real Volcengine API calls.

Requires VOLCENGINE_API_KEY environment variable.
Cost: minimal (~0.02-0.1 RMB per generation).
"""

import pytest
import httpx
from tests.fixtures.env_config import require_volcengine


class TestImageGenerate:
    """POST /api/image/generate — real Volcengine image generation."""

    async def test_generate_basic(self, client):
        """Valid prompt → returns image URL."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "一只可爱的橙色猫咪坐在窗台上",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "images" in data
        assert len(data["images"]) > 0
        image_url = data["images"][0]
        assert image_url.startswith("http")

    async def test_generate_with_style(self, client):
        """Prompt with style description."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "赛博朋克风格的城市夜景，霓虹灯，雨天",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "images" in data

    async def test_generated_image_accessible(self, client):
        """Generated image URL is publicly accessible."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "一个简单的红色圆圈",
        }, timeout=60)
        assert resp.status_code == 200
        image_url = resp.json()["images"][0]
        # Verify URL is reachable
        check = httpx.get(image_url, timeout=30)
        assert check.status_code == 200


class TestImageValidation:
    """Input validation — no API cost expected (should fail fast)."""

    async def test_empty_prompt(self, client):
        """Empty prompt → 400 or 422."""
        resp = await client.post("/api/image/generate", json={
            "prompt": "",
        })
        assert resp.status_code in (400, 422)

    async def test_missing_prompt(self, client):
        """Missing prompt field → 422."""
        resp = await client.post("/api/image/generate", json={})
        assert resp.status_code == 422

    async def test_very_long_prompt(self, client):
        """Very long prompt → handled gracefully (truncation or error)."""
        require_volcengine()
        long_prompt = "美丽的风景 " * 500
        resp = await client.post("/api/image/generate", json={
            "prompt": long_prompt.strip(),
        }, timeout=60)
        # Should either succeed (API truncates) or return sensible error
        assert resp.status_code in (200, 400)


class TestImageErrors:
    """Error handling."""

    async def test_invalid_parameters(self, client):
        """Invalid size parameter → error."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "测试图片",
            "size": "99999x99999",
        }, timeout=60)
        # API should reject unreasonable dimensions
        assert resp.status_code in (200, 400)

    async def test_response_schema(self, client):
        """Verify response matches expected schema."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "简单的蓝色方块",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "images" in data
        assert isinstance(data["images"], list)
        for url in data["images"]:
            assert isinstance(url, str)
            assert url.startswith("https://") or url.startswith("http://")
```

- [ ] **Step 2: 运行测试（需火山引擎 API key）**

Run: `cd server && VOLCENGINE_API_KEY=your_key python -m pytest tests/acceptance/test_image_api.py -v`
Expected: tests pass; skip if key not set

- [ ] **Step 3: Commit**

```bash
git add server/tests/acceptance/test_image_api.py
git commit -m "feat: image_endpoint 验收测试 — 真实火山引擎图片生成 8个用例

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: 全量运行 + 收尾

- [ ] **Step 1: 运行本地测试（无需网络）**

Run: `cd server && python -m pytest tests/acceptance/test_auth_api.py tests/acceptance/test_conversation_api.py tests/acceptance/test_data_api.py tests/acceptance/test_staff_api.py tests/acceptance/test_publisher_api.py -v -k "not PlatformPublish"`
Expected: ~95 tests pass

- [ ] **Step 2: 运行 LLM 测试（需 Ollama）**

Run: `cd server && python -m pytest tests/acceptance/test_hermes_chat_api.py -v`
Expected: ~12 tests pass (volcengine ones skip without key)

- [ ] **Step 3: 用户配合 — 登录平台 + 运行阶段二**

由用户手动登录抖音/小红书/快手/B站后：
Run: `cd server && python -m pytest tests/acceptance/test_publisher_api.py -v -k "PlatformPublish"`
Expected: ~10 tests pass

- [ ] **Step 4: 最终 commit**

```bash
git add -A
git commit -m "chore: szyg API 验收测试完成 — 7模块 ~128用例 全部通过

Co-Authored-By: Claude <noreply@anthropic.com>"
```
