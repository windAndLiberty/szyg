# 🏗️ 系统全局架构 — 域灵 (szyg) 智能矩阵运营系统

## 1. 系统定位

域灵是一个**自托管 AI 工具平台**，面向多平台内容营销自动化。核心能力：

- AI 数字员工（智能体）驱动的内容生产与发布
- 多平台自动发布（抖音 / 小红书 / 微信）
- 流量获客（智能截流 / 舆情监听 / 客户转化）
- 工作流编排（流水线 / 调度引擎 / SOP）
- 知识库与长期记忆

## 2. 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | FastAPI | >=0.115 |
| ASGI 服务器 | uvicorn[standard] | >=0.32 |
| Python | 3.12+ | |
| 包管理 | uv + pyproject.toml | |
| 前端框架 | Vue 3 | >=3.5 |
| 前端 UI | Element Plus | >=2.14 |
| 前端路由 | Vue Router | >=4.6 |
| 状态管理 | Pinia | >=3.0 |
| 构建工具 | Vite | >=8.0 |
| 桌面端 | Electron | >=33.4 |
| 打包 | electron-builder | >=25.0 |
| 数据库 | SQLite | 内置 |
| LLM 后端 | 火山引擎方舟 (默认) / Ollama (降级) | |
| 图像生成 | ComfyUI (默认) / 火山引擎 Seedream (降级) | |
| 浏览器自动化 | Playwright | >=1.60 |
| 认证 | JWT (python-jose) + PBKDF2-SHA256 | |

## 3. 三层架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    Electron 桌面端壳                      │
│  electron/main.js → 启动后端 uvicorn → 加载前端 SPA       │
├─────────────────────────────────────────────────────────┤
│                    前端 SPA (Vue 3)                      │
│  web/src/ → Vite 构建 → web/dist/                        │
│  路由: 7 大版块 (AI员工/内容工厂/营销拓客/工作流/          │
│        数据洞察/知识库/系统设置)                           │
│  认证: JWT localStorage + Vue Router beforeEach 守卫     │
├─────────────────────────────────────────────────────────┤
│                    后端 API (FastAPI)                     │
│  server/szyg/api/app.py → create_app()                  │
│  中间件: TenantMiddleware → CORSMiddleware               │
│  路由: 20+ APIRouter 模块化挂载                          │
│  数据: SQLite (auth.db / knowledge.db / memory.db /     │
│        sop.db) + JSON 文件存储 (data/)                    │
│  调度: scheduler_engine 后台循环                          │
│  平台: platforms/registry 适配器注册表                    │
└─────────────────────────────────────────────────────────┘
```

## 4. 后端入口链

```
server/szyg/main.py
  └─ get_app() → create_app() [server/szyg/api/app.py]
       ├─ TenantMiddleware (多租户隔离)
       ├─ CORSMiddleware (跨域)
       ├─ auth_router (认证, 始终加载)
       ├─ tools_router (工具, 始终加载)
       ├─ oem_router (OEM, 始终加载)
       ├─ agent_router (智能体市场)
       ├─ hub_router (工具Hub)
       ├─ announce_router (公告)
       ├─ publisher_router (发布)
       ├─ scheduler_router (调度)
       ├─ platform_router (平台操作)
       ├─ brain_router (AI Brain)
       ├─ chat_api_router (原始Ollama对话)
       ├─ hermes_chat_router (超级员工对话)
       ├─ client_router (客户端运行时)
       ├─ pipeline_router (多模型流水线) [try]
       ├─ video_router (视频端点) [try]
       ├─ acquisition_router (获客) [try]
       ├─ skills_router (技能市场) [try]
       ├─ infra_router (基础设施) [try]
       ├─ memory_router (长期记忆) [try]
       ├─ risk_control_router (风控) [try]
       ├─ sau_router (social-auto-upload) [try]
       ├─ staff_router (员工管理) [try]
       ├─ conversation_router (对话持久化) [try]
       ├─ data_router (统一前端数据API) [try]
       ├─ frontend_routes (前端数据供给) [try]
       ├─ image_endpoint (图像生成) [try]
       ├─ models_endpoint (模型列表) [try]
       ├─ /api/health (健康检查)
       ├─ /api/config (配置)
       └─ StaticFiles (web/dist/ SPA + volcengine_output/)
```

## 5. 数据流

```
用户操作 (浏览器/Electron)
  → Vue 组件 → axios → FastAPI 路由
  → 业务引擎 (publisher/scheduler/acquisition/pipeline)
  → 平台适配器 (Playwright/UIA) 或 LLM 后端 (火山/Ollama)
  → SQLite / JSON 文件持久化
  → SSE/JSON 响应 → Vue 组件渲染
```

## 6. 配置体系

- **主配置**: `config.yaml` (LLM / 图像 / 语音 / 视频 / 平台 / API / 数据库)
- **密钥配置**: `secrets.yaml` (API keys, 通过 `${VAR}` 引用)
- **环境变量**: 优先级 > config.yaml > 代码默认值
- **加载入口**: `server/szyg/config/loader.py` → `load_config()`
- **设置对象**: `server/szyg/config/settings.py` → `get_settings()`

## 7. 多租户模型

- **中间件**: `TenantMiddleware` (ASGI) → 从 `X-OEM-ID` header 解析租户
- **上下文**: `contextvars.ContextVar` 线程/异步安全
- **数据隔离**: `get_tenant_data_dir()` → `data/tenants/{tenant_id}/`
- **用户绑定**: `users.oem_id` 字段关联租户
- **默认租户**: `"default"` (不创建子目录)
