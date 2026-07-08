# szyg API 端点测试 — 子项目 A 设计规格

> 日期：2026-07-08 | 状态：已确认 | 父项目：szyg 后端 QA 质量保证

---

## 目标

为 szyg 后端的核心 API 路由模块建立验收测试覆盖，确保面向用户的关键路径稳定可靠。

## 范围

7 个 P0 路由模块，约 128 个测试用例，全部放在 `server/tests/acceptance/` 下。

## 全局约束

- **真实调用，不 mock LLM**：本地 Ollama + 火山引擎 API 均真实调用
- 不做压力测试，不做视频生成测试
- 使用项目已有技术栈：pytest + pytest-asyncio + httpx.AsyncClient
- 测试数据与生产数据隔离（使用临时存储或独立 fixture）
- Agency（`agency_routes`）已由用户手动验证，不在本次范围
- 需要 `VOLCENGINE_API_KEY` 环境变量 + Ollama 本地运行

---

## 一、测试分层策略

### 1.1 模块优先级

| # | 模块 | 调用策略 | 外部依赖 |
|---|------|-----------|----------|
| 1 | `hermes_chat` | **真实 LLM 调用**（火山引擎 + 本地 Ollama 回退）+ 真实工具分发 | 火山引擎 API + 本地 Ollama |
| 2 | `conversation_routes` | 全真实 | 无（本地 JSON 存储） |
| 3 | `auth_routes` | 全真实 | 无（本地 SQLite） |
| 4 | `data_routes` | 全真实 | 无（本地 JSON 存储） |
| 5 | `staff_routes` | 全真实 | 无（本地 JSON 配置） |
| 6 | `publisher_routes` | 真实 CRUD，跳过分发到外部平台 | 无（本地 JSON 存储） |
| 7 | `image_endpoint` | **真实调用火山引擎** | 火山引擎 API |

### 1.2 真实调用策略

- **hermes_chat**：直接 POST `/api/hermes/chat`，接收真实 SSE 流式响应。优先使用火山引擎模型（`doubao-seed-2-0-pro-260215`），Ollama 作为本地回退（`qwen3:0.6B`）
- **工具分发**：真实调用 `_execute_tool()`，验证工具链完整（如知识库搜索、内容 CRUD）
- **image_endpoint**：真实 POST `/api/image/generate`，验证火山引擎返回有效图片 URL
- **本地端点**（auth、conversation、data、staff、publisher）：纯本地操作，无外部依赖，直接验证 CRUD 完整性

### 1.3 测试工具

| 工具 | 用途 |
|------|------|
| `pytest` + `pytest-asyncio` | 测试框架（项目已有，`asyncio_mode = "auto"`） |
| `httpx.AsyncClient` + `ASGITransport` | 对真实 FastAPI app 发起集成测试请求 |
| `factories` | 测试数据工厂（减少重复构造代码） |
| `env_config` | 从环境变量/settings 读取 API key 和 endpoint 配置 |

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
│   ├── test_hermes_chat_api.py         # P0-1：Hermes 聊天 API（真实 LLM）
│   └── test_image_api.py              # P0-7：图片生成 API（真实火山引擎）
└── fixtures/
    ├── factories.py                     # 测试数据工厂
    └── env_config.py                    # API key / endpoint 配置读取
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

### 3.6 hermes_chat_api（~15 用例）

**测试策略：** 真实调用火山引擎 API + 本地 Ollama，接收完整 SSE 流式响应。

**覆盖内容：**
- 请求验证：空 messages → 422、无效 model → 正常回退 Ollama
- 普通对话：发送 "你好，请用中文回复" → 验证 SSE 流式返回 `text` 事件 + `done` 事件
- `agent_id` 参数加载员工配置（`content`/`acquisition`/`conversion`/`ops`）→ 验证不同 agent 身份下的响应风格
- `expert_prompt` 通道：自定义专家 prompt → 验证优先于 agent_id
- SSE 事件完整性：`status` 进度 → `text` 内容 → `done` 收尾，事件顺序正确
- 工具调用：发送 "帮我搜索知识库中关于营销的内容" → 验证 `tool_call` + `tool_result` 事件
- 本地 Ollama 回退：未配置火山引擎时回退到 Ollama 正常工作
- `case-cards` 端点：`POST /api/hermes/case-cards` → 返回推荐案例列表，验证数据结构

**注意：** 此模块会产生 API 费用（火山引擎按 token 计费），但单次对话成本很低（~0.01-0.1 元）。建议测试时使用短 prompt。Ollama 回退测试零费用。

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

### env_config.py

```python
# 从环境变量 / settings 读取 API 配置，供测试使用

import os
from szyg.config import get_settings

def get_volcengine_api_key() -> str:
    """从 VOLCENGINE_API_KEY 环境变量读取，不存在时跳过测试"""
    key = os.environ.get("VOLCENGINE_API_KEY", "")
    if not key:
        pytest.skip("VOLCENGINE_API_KEY not set")
    return key

def get_ollama_base_url() -> str:
    """Ollama 默认地址，可通过环境变量覆盖"""
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

def is_ollama_available() -> bool:
    """检测本地 Ollama 是否可用"""
    import httpx
    try:
        r = httpx.get(f"{get_ollama_base_url()}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False
```

---

## 五、验收标准

1. 7 个模块的测试文件全部创建
2. P0-2~6（auth、conversation、data、staff、publisher）可在无网络环境下运行（纯本地），`pytest tests/acceptance/test_auth_api.py tests/acceptance/test_conversation_api.py tests/acceptance/test_data_api.py tests/acceptance/test_staff_api.py tests/acceptance/test_publisher_api.py` 通过
3. P0-1（hermes_chat）需要火山引擎 API 或本地 Ollama 运行，`pytest tests/acceptance/test_hermes_chat_api.py` 通过
4. P0-7（image_endpoint）需要 `VOLCENGINE_API_KEY`，`pytest tests/acceptance/test_image_api.py` 通过
5. 每个测试文件包含正常路径 + 至少 1 个错误路径
6. 测试数据不与生产数据冲突（使用独立测试账号 + 测试后清理）
7. 测试间相互独立，可任意顺序执行或单独运行
8. hermes_chat 和 image_endpoint 测试自动跳过（pytest.skip）当 API key 不可用时

---

## 六、技术约束

- 使用已有依赖：pytest、pytest-asyncio、httpx
- 不引入新的测试框架
- 遵守项目 `pyproject.toml` 中的 pytest 配置（`asyncio_mode = "auto"`、`addopts = "-m 'not integration' --timeout=30"`）
- 每个测试文件使用 `tests/acceptance/conftest.py` 中已有的 `test_app` fixture
- hermes_chat 和 image_endpoint 需通过 env_config 检测 API 可用性，不可用时自动 skip
