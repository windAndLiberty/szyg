# szyg API 端点测试 — 子项目 A 设计规格

> 日期：2026-07-08 | 状态：已确认 | 父项目：szyg 后端 QA 质量保证

---

## 目标

为 szyg 后端的核心 API 路由模块建立验收测试覆盖，确保面向用户的关键路径稳定可靠。

## 范围

7 个 P0 路由模块，约 128 个测试用例，全部放在 `server/tests/acceptance/` 下。

## 全局约束

- 节省 API 费用：仅 `image_endpoint` 真实调用火山引擎 API
- 不做压力测试，不做视频生成测试
- 使用项目已有技术栈：pytest + pytest-asyncio + respx + httpx.AsyncClient
- 测试数据与生产数据隔离（使用临时存储或独立 fixture）
- Agency（`agency_routes`）已由用户手动验证，不在本次范围

---

## 一、测试分层策略

### 1.1 模块优先级

| # | 模块 | Mock 策略 | 外部依赖 |
|---|------|-----------|----------|
| 1 | `hermes_chat` | Mock LLM 流式，真实工具分发逻辑 | 无（respx mock） |
| 2 | `conversation_routes` | 全真实 | 无（本地 JSON 存储） |
| 3 | `auth_routes` | 全真实 | 无（本地 SQLite） |
| 4 | `data_routes` | 全真实 | 无（本地 JSON 存储） |
| 5 | `staff_routes` | 全真实 | 无（本地 JSON 配置） |
| 6 | `publisher_routes` | 真实 CRUD，跳过分发到外部平台 | 无（本地 JSON 存储） |
| 7 | `image_endpoint` | **真实调用火山引擎** | 火山引擎 API（需有效 key） |

### 1.2 Mock 技术方案

- **火山引擎 LLM 调用**：`respx.mock` 拦截 `https://ark.cn-beijing.volces.com/api/v3/*`，返回预定义 JSON
- **Ollama**：`respx.mock` 拦截 `http://localhost:11434/*`
- **SSE 流式输出**：直接调用 `hermes_chat.py` 内部函数验证事件生成，不触发真实 LLM 轮次
- **工具执行**：mock `_execute_tool()` 返回预设结果

### 1.3 测试工具

| 工具 | 用途 |
|------|------|
| `pytest` + `pytest-asyncio` | 测试框架（项目已有，`asyncio_mode = "auto"`） |
| `respx` | Mock 外部 HTTP 调用 |
| `httpx.AsyncClient` + `ASGITransport` | 对真实 FastAPI app 发起集成测试请求 |
| `factories` | 测试数据工厂（减少重复构造代码） |

---

## 二、测试结构

```
server/tests/
├── conftest.py                          # 已有：共享 fixtures（扩展）
├── acceptance/
│   ├── conftest.py                      # 已有：FastAPI TestClient fixture
│   ├── test_auth_api.py                 # P0-3：认证 API
│   ├── test_conversation_api.py         # P0-2：对话历史 API
│   ├── test_data_api.py                # P0-4：统一数据 API（已有，扩充）
│   ├── test_staff_api.py               # P0-5：AI 员工 API
│   ├── test_publisher_api.py           # P0-6：内容发布 API
│   ├── test_hermes_chat_api.py         # P0-1：Hermes 聊天 API
│   └── test_image_api.py              # P0-7：图片生成 API
└── fixtures/
    ├── factories.py                     # 测试数据工厂
    └── mock_llm.py                      # 共享 LLM mock 函数
```

---

## 三、各模块测试用例规格

### 3.1 auth_routes（~15 用例）

**端点覆盖：**
- `POST /api/auth/login` — 登录成功、密码错误、用户不存在、空字段
- `GET /api/auth/session` — 有效会话、无效/过期会话
- `GET /api/auth/users` — 列出用户、空列表
- `POST /api/auth/users` — 创建用户、重复用户名、弱密码
- `PUT /api/auth/users/{id}` — 更新用户、不存在的 ID
- `DELETE /api/auth/users/{id}` — 删除用户、不存在的 ID
- `PUT /api/auth/users/{id}/toggle` — 启禁用用户

**数据隔离：** 使用临时 SQLite 数据库或 fixture 清理。

### 3.2 conversation_routes（~20 用例）

**端点覆盖：**
- `GET /api/conversations` — 列表、空列表、分页边界
- `POST /api/conversations` — 创建（带消息）、标题自动截取
- `GET /api/conversations/{id}` — 获取详情、不存在的 ID 404
- `PUT /api/conversations/{id}` — 更新（标题、置顶、消息列表）
- `DELETE /api/conversations/{id}` — 删除、级联清理消息
- 跨用户隔离：用户 A 不能访问用户 B 的对话

### 3.3 data_routes（~30 用例）

**已有基础：** `tests/acceptance/test_data_api.py` — 24 个参数化端点测试。

**扩充方向：**
- 错误路径：无效 resource 名、不存在的 item_id
- 写操作验证：create → list 可见、update 持久化
- DELETE 的幂等性
- `toggle` 类操作的状态翻转
- 覆盖更多 resource 类型（当前覆盖 conversation/team/leads/strategies/chart_data/reply_templates，扩充到 tools/skills/platforms/contents/sops/scheduled_tasks/experiments）

### 3.4 staff_routes（~15 用例）

**端点覆盖：**
- `GET /api/staff/list` — 列出员工、验证返回结构
- `GET /api/staff/{id}` — 单个获取、不存在的 ID
- `GET /api/staff/tasks/list` — 任务列表
- `POST /api/staff/tasks/create` — 创建任务、无效 agent_id
- `PUT /api/staff/tasks/{id}` — 更新任务状态/进度
- `DELETE /api/staff/tasks/{id}` — 删除任务
- `GET /api/staff/configs/list` — 配置列表
- `GET /api/staff/configs/{agent_id}` — 获取配置
- `PUT /api/staff/configs/{agent_id}` — 更新配置
- `POST /api/staff/configs/{agent_id}/reset` — 重置配置

### 3.5 publisher_routes（~20 用例）

**端点覆盖：**
- `GET /api/publisher/contents` — 内容列表
- `POST /api/publisher/contents` — 创建内容、必填字段校验
- `PUT /api/publisher/contents/{id}` — 更新内容
- `DELETE /api/publisher/contents/{id}` — 删除内容
- `POST /api/publisher/contents/{id}/submit` — 提交审核
- `POST /api/publisher/contents/{id}/approve` — 审批通过
- `POST /api/publisher/contents/{id}/reject` — 审批拒绝（需填写原因）
- `POST /api/publisher/contents/{id}/schedule` — 定时发布
- `GET /api/publisher/calendar` — 发布日历
- `GET /api/publisher/stats` — 统计概览
- `GET /api/publisher/materials` — 素材列表
- `POST /api/publisher/materials` — 上传素材
- `DELETE /api/publisher/materials/{id}` — 删除素材

**不测试：** 实际平台发布（`/publish`）、平台登录/会话管理（需要真实账号）。

### 3.6 hermes_chat_api（~20 用例）

**测试策略：** Mock 外部 LLM 调用，测试 SSE 事件生成和工具分发逻辑。

**覆盖内容：**
- 请求验证：空 messages、无效 model、超长 prompt
- `agent_id` 参数加载员工配置（`content`/`acquisition`/`conversion`/`ops`）
- `expert_prompt` 通道：自定义专家 prompt 优先于 agent_id
- SSE 事件格式：`text`、`tool_call`、`tool_result`、`error`、`done` 类型
- 工具分发正确性：指定工具名 → 正确调用对应的内部函数
- 错误处理：LLM 返回非预期格式、工具执行异常
- `case-cards` 端点：`POST /api/hermes/case-cards` 返回推荐案例

**Mock 设置：**
```python
# respx 拦截火山引擎 API，返回预设 tool_calls 或文本响应
respx.post("https://ark.cn-beijing.volces.com/api/v3/chat/completions").mock(
    return_value=httpx.Response(200, json=PREDEFINED_RESPONSE)
)
```

### 3.7 image_endpoint（~8 用例）

**测试策略：** 真实调用火山引擎图片生成 API。

**覆盖内容：**
- 正常生成：有效 prompt → 返回 `{images: [...]}` 含有效 URL
- 空 prompt → 400 错误
- 超长 prompt → 处理截断或报错
- 无效参数（如不支持的尺寸）→ 错误响应
- API key 缺失时的错误处理
- 响应 schema 验证：返回的 image URL 可访问

**注意：** 此模块需要有效的 `VOLCENGINE_API_KEY` 环境变量。CI 中可通过 GitHub Secrets 提供，本地开发从 `.env` 加载。

---

## 四、Fixtures 设计

### factories.py

```python
# 测试数据工厂，避免重复构造数据

def make_user(username="testuser", password="test123", role="admin"):
    return {"username": username, "password": password, "role": role}

def make_conversation(title="测试对话", messages=None):
    return {"title": title, "messages": messages or [], "model": "doubao-seed-2-0-pro-260215"}

def make_staff_task(agent_id="content", title="测试任务"):
    return {"agent_id": agent_id, "title": title, "status": "pending"}

def make_content(title="测试内容", content_type="video", platform="douyin"):
    return {"title": title, "content_type": content_type, "platform": platform}
```

### mock_llm.py

```python
# 共享 LLM mock，所有需要 mock 火山引擎的测试共用

def setup_volcengine_mock():
    """设置 respx mock 拦截火山引擎 API 调用"""
    ...

PREDEFINED_TOOL_CALL_RESPONSE = {...}
PREDEFINED_TEXT_RESPONSE = {...}
```

---

## 五、验收标准

1. 7 个模块的测试文件全部创建，`pytest -m 'not integration'` 全部通过
2. P0-1~6（除 image_endpoint）可在无网络环境下运行（全 mock/本地）
3. P0-7（image_endpoint）在有 `VOLCENGINE_API_KEY` 环境下通过
4. 每个测试文件包含正常路径 + 至少 1 个错误路径
5. 测试数据不与生产数据冲突
6. 测试间相互独立，可任意顺序执行或单独运行

---

## 六、技术约束

- 使用已有依赖：pytest、pytest-asyncio、respx、httpx
- 不引入新的测试框架
- 遵守项目 `pyproject.toml` 中的 pytest 配置（`asyncio_mode = "auto"`、`addopts = "-m 'not integration' --timeout=30"`）
- 每个测试文件使用 `tests/acceptance/conftest.py` 中已有的 `test_app` fixture
