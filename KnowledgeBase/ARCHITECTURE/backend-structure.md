# 🏗️ 后端目录结构与模块职责

## 1. 顶层结构

```
server/szyg/
├── main.py                 # 应用入口 (get_app → create_app → uvicorn)
├── app.py                  # 精简版 create_app (无 TenantMiddleware，备用)
├── version.py              # VERSION = "1.0.0"
├── auth.py                 # JWT 认证 + SQLite 用户管理
├── tenant.py               # 多租户隔离 (ContextVar + Middleware)
├── data_path.py            # 数据目录路径定义
├── atomic_file.py          # 原子文件写入工具
├── tool_runtime.py         # 工具运行时
├── vision_grounding.py     # 视觉定位引擎
├── publisher.py            # 多平台发布引擎
├── scheduler_engine.py     # 调度引擎 (后台循环)
├── pipeline_engine.py      # 多模型 AIGC 流水线
├── comment_engine.py       # 评论引擎 (截流/自动回复)
├── intercept_engine.py     # 智能截流引擎
├── listen_engine.py        # 舆情监听引擎
├── convert_engine.py       # 客户转化引擎
├── video_cut_engine.py     # 视频剪辑引擎
├── brain.py                # AI Brain (基础)
├── brain_hermes.py         # AI Brain (Hermes 超级员工)
├── client.py               # 客户端运行时
├── mcp_server.py           # MCP Server (工具协议)
├── models/                 # Pydantic 数据模型
├── config/                 # 配置加载 (loader.py + settings.py)
├── api/                    # FastAPI 路由层 (20+ 路由模块)
├── platforms/              # 平台适配器 (抖音/小红书/微信/B站)
├── integrations/           # 第三方集成
├── skills/                 # 技能模块 (Hermes Skills Hub)
├── mcp_servers/            # MCP Server 实现
├── pipelines/              # 流水线定义
├── infrastructure/         # 基础设施 (沙箱/浏览器节点)
├── agent_core/             # 智能体核心
├── core/                   # 核心工具
├── mcp/                    # MCP 协议
├── memory/                 # 记忆存储
├── storage/                # 文件存储
├── fonts/                  # 字体资源
├── video_templates/        # 视频模板
└── wechaty/                # Wechaty 集成
```

## 2. API 路由层 (`server/szyg/api/`)

### 2.1 始终加载的路由

| 文件 | 路由前缀 | 职责 |
|------|----------|------|
| `auth_routes.py` | `/api/auth` | 登录/注册/JWT 校验 |
| `tools_routes.py` | `/api/tools` | 工具列表/调用 |
| `oem_routes.py` | `/api/oem` | OEM/白标配置 |

### 2.2 核心业务路由

| 文件 | 路由前缀 | 职责 |
|------|----------|------|
| `agent_routes.py` | `/api/agents` | 智能体市场 CRUD |
| `hub_routes.py` | `/api/hub` | AI 工具 Hub |
| `announce_routes.py` | `/api/announcements` | 公告系统 |
| `publisher_routes.py` | `/api/publisher` | 多平台发布 |
| `scheduler_routes.py` | `/api/scheduler` | 调度任务管理 |
| `platform_routes.py` | `/api/platforms` | 平台账号/操作 |
| `brain_routes.py` | `/api/brain` | AI Brain (nanobot) |
| `chat.py` | `/api/chat` | 原始 Ollama 对话 |
| `hermes_chat.py` | `/api/hermes` | 超级员工对话 (Ollama + MCP tools) |
| `client_routes.py` | `/api/client` | 客户端运行时 |

### 2.3 可选路由 (try_include)

| 文件 | 路由前缀 | 职责 | 依赖 |
|------|----------|------|------|
| `routes.py` | `/v1` | 聚合路由 (chat + models) | - |
| `frontend_routes.py` | `/api/frontend` | 前端数据供给 | - |
| `image_endpoint.py` | `/api/image` | 图像生成 | openai/ComfyUI |
| `models_endpoint.py` | `/api/models` | 模型列表 | - |
| `pipeline_endpoint.py` | `/api/pipeline` | 多模型流水线 | - |
| `video_endpoint.py` | `/api/video` | 视频生成/处理 | - |
| `acquisition_routes.py` | `/api/acquisition` | 获客/截流/转化 | - |
| `skills_routes.py` | `/api/skills` | 技能市场 | - |
| `infra_routes.py` | `/api/infra` | 基础设施/沙箱 | - |
| `memory_routes.py` | `/api/memory` | 长期记忆 CRUD | - |
| `risk_control_routes.py` | `/api/risk` | 风控策略 | - |
| `sau_routes.py` | `/api/sau` | social-auto-upload | - |
| `staff_routes.py` | `/api/staff` | 员工状态/任务/配置 | - |
| `conversation_routes.py` | `/api/conversations` | 对话历史持久化 | - |
| `data_routes.py` | `/api/data` | 统一前端数据 API | - |

### 2.4 健康检查端点

| 路径 | 方法 | 用途 |
|------|------|------|
| `/api/health` | GET | 健康检查 (返回 status + version) |
| `/api/config` | GET | 返回 debug + log_level |
| `/` | GET | 根路径 (返回 name + version + docs) |
| `/docs` | GET | Swagger UI (FastAPI 内置) |

## 3. 核心引擎层

| 引擎 | 文件 | 职责 |
|------|------|------|
| 发布引擎 | `publisher.py` | 多平台内容发布 (图文/视频) |
| 调度引擎 | `scheduler_engine.py` | 定时任务后台循环 |
| 流水线引擎 | `pipeline_engine.py` | 多模型 AIGC 编排 (文本→图像→视频→语音) |
| 截流引擎 | `intercept_engine.py` | 评论区智能截流 |
| 监听引擎 | `listen_engine.py` | 舆情/关键词监听 |
| 转化引擎 | `convert_engine.py` | 客户转化/自动回复 |
| 评论引擎 | `comment_engine.py` | 评论生成与管理 |
| 视频剪辑 | `video_cut_engine.py` | FFmpeg 视频剪辑 |
| 视觉定位 | `vision_grounding.py` | 图像视觉定位 |
| AI Brain | `brain.py` / `brain_hermes.py` | AI 推理核心 |

## 4. 平台适配器 (`server/szyg/platforms/`)

- **注册表模式**: `registry.py` → `get_registry()` 统一管理
- **适配器**: 抖音 / 小红书 / 微信 / B站
- **自动化**: Playwright (浏览器) / UIA (Windows 桌面)
- **生命周期**: 启动时注册 → 运行时调用 → 关闭时 `close_all()`

## 5. 数据存储

| 存储 | 路径 | 用途 |
|------|------|------|
| auth.db | `data/auth.db` | 用户表 (users) |
| knowledge.db | `data/knowledge.db` | 知识库 (文档分块 + FTS) |
| memory.db | `data/memory.db` | 长期记忆 (向量 + FTS) |
| sop.db | `data/sop.db` | SOP 工作流 |
| JSON 文件 | `data/frontend/*.json` | 前端页面持久化数据 |
| 文件存储 | `data/volcengine_output/` | AIGC 生成产物 |
| 文件存储 | `data/comfyui_output/` | ComfyUI 图像输出 |
| 租户隔离 | `data/tenants/{tenant_id}/` | 多租户数据目录 |
