# szyg 后端功能实现技术文档

> 版本: 1.0.0 | 更新日期: 2026-06-28

## 架构概览

后端基于 **FastAPI + Pydantic + Playwright** 构建，通过 **Hermes Agent** 作为 AI 核心驱动，采用 **MCP (Model Context Protocol) Server** 架构将各功能模块解耦为独立工具服务。数据层使用 JSON 文件持久化 + SQLite (FTS5) 全文检索，无外部数据库依赖。

```
szyg/
├── api/              FastAPI 路由层 (24个路由文件)
├── agent_core/       AI 核心 (记忆/知识/SOP/规划/技能/模型路由)
├── integrations/     外部服务集成 (火山引擎/Ollama/ComfyUI/FFmpeg/采集适配器)
├── mcp_servers/      MCP Server 工具服务 (13个)
├── platforms/        平台适配器 (抖音/小红书/B站/快手/微信)
├── infrastructure/   基础设施 (数据库/HTTP客户端/日志)
├── models/           Pydantic 数据模型
├── skills/           技能库 (214个技能文件)
├── brain_hermes.py   Hermes Agent 集成层
├── hermes_chat.py    LLM 工具调用编排 (118KB, 核心调度)
├── publisher.py      内容发布管道
├── scheduler_engine.py  智能调度引擎
├── pipeline_engine.py   多模型AIGC流水线
├── intercept_engine.py  智能截流引擎
├── comment_engine.py    评论管理引擎
├── listen_engine.py     舆情监听引擎
├── convert_engine.py    客户转化引擎
├── video_cut_engine.py  视频剪辑引擎
├── vision_grounding.py  视觉定位模块
├── auth.py             JWT 认证
├── tenant.py           多租户隔离
└── tool_runtime.py     插件运行时
```

---

## 1. AI 核心 (Agent Core)

### 1.1 Hermes Agent 集成

- **文件**: `brain_hermes.py`, `hermes_chat.py`
- **实现**: 深度集成 Hermes Agent v0.15 作为 AI 核心引擎，通过 `hermes.yaml` 配置 MCP Server 列表
- **工具调用**: `hermes_chat.py` 中的 `_execute_tool()` 函数实现了 **80+ 工具** 的分发路由，包含 allowlist 安全检查、参数消毒、路径白名单保护
- **LLM 后端**: 支持火山引擎方舟 (VolcEngine ARK) 和 Ollama 本地模型，通过模型名自动路由
- **SSE 流式**: `/api/hermes/chat` 端点实现 Server-Sent Events 流式响应，支持工具调用 → 执行 → 回传结果的完整循环

### 1.2 长期记忆

- **文件**: `agent_core/memory.py`
- **实现**: 基于 SQLite FTS5 全文检索 + 向量存储
- **功能**: 记忆条目的存储、检索、搜索、更新、删除，支持语义相似度匹配

### 1.3 知识库 (RAG)

- **文件**: `agent_core/knowledge.py`
- **实现**: 在 Memory 基础上扩展文档摄入能力
- **功能**: 支持 txt/md/json 文件摄入，按段落/语义分块，RAG 检索相关片段作为 LLM 上下文，来源文件追踪

### 1.4 SOP 管理器

- **文件**: `agent_core/sop_manager.py`
- **实现**: 用户自定义标准操作流程模板
- **功能**: 每个 SOP 包含有序步骤列表，每步引用一个技能，与 Planner + SkillRegistry 协作执行

### 1.5 技能注册表

- **文件**: `agent_core/skill_registry.py`, `skills/` (214个技能文件)
- **实现**: 技能注册、列表、执行、参数校验、注销
- **技能库**: 包含创意设计、文档处理、数据分析、视频制作等多个类别

### 1.6 模型路由

- **文件**: `agent_core/model_router.py`
- **实现**: 根据模型名自动路由到对应的 LLM 后端 (火山引擎/Ollama/OpenRouter/LiteLLM)

### 1.7 规划器

- **文件**: `agent_core/planner.py`
- **实现**: 任务分解与步骤规划，匹配 SOP 模板并按步骤执行

---

## 2. MCP Server 工具服务

### 2.1 MCP 协议实现

- **文件**: `mcp_server.py`
- **协议**: JSON-RPC 2.0 over stdio，支持 `initialize` / `tools/list` / `tools/call` 方法
- **特性**: 装饰器注册工具 (`@server.tool`)，自动推断参数类型生成 inputSchema，支持同步和异步工具处理器

### 2.2 已注册的 MCP Server (13个)

| MCP Server | 文件 | 功能 |
|------------|------|------|
| publisher | `publisher_mcp.py` | 内容 CRUD、审核流程、发布管理 |
| scheduler | `scheduler_mcp.py` | 定时任务管理 (创建/暂停/恢复/删除/历史) |
| tools | `tools_mcp.py` | 工具市场 (浏览/搜索/安装/卸载) |
| knowledge | `knowledge_mcp.py` | 知识库搜索/摄入/统计 |
| agents | `agents_mcp.py` | 智能体列表/详情/分类 |
| oem | `oem_mcp.py` | OEM 品牌定制配置 |
| platforms | `platforms_mcp.py` | 平台列表/状态/登录/发布/会话管理 |
| skills | `skills_mcp.py` | 技能列表 (75KB, 最大MCP Server) |
| video | `video_mcp.py` | 视频剪辑 (裁剪/拼接/变速/标题/音频) |
| web_tools | `web_tools_mcp.py` | 网页抓取/截图/搜索 (33KB) |
| pipeline | `pipeline_mcp.py` | 多模型流水线编排 |
| **acquisition** | `acquisition_mcp.py` | **平台采集 (搜索/评论/私信)** |
| (brain) | `brain_hermes.py` | 内核诊断/MCP列表/系统配置 |

### 2.3 Acquisition MCP Server (新增)

- **文件**: `mcp_servers/acquisition_mcp.py`
- **工具数**: 6个
- **工具列表**:
  - `acq_platforms` — 列出采集平台状态
  - `acq_search` — 跨平台视频搜索 (bilibili/douyin/xhs/kuaishou)
  - `acq_get_comments` — 获取视频评论列表
  - `acq_send_comment` — 发送评论到视频
  - `acq_batch_send_comments` — 批量发送评论
  - `acq_send_dm` — 发送私信 (B站)

---

## 3. 平台适配层

### 3.1 平台适配器架构

- **文件**: `platforms/base.py`, `platforms/registry.py`
- **基类**: `BasePlatformAdapter` — 定义 `initialize` / `check_login` / `login` / `publish` / `get_status` / `safe_publish` / `health_check` 抽象接口
- **注册表**: `PlatformRegistry` 单例模式，延迟初始化，支持工厂模式注册
- **发布流程**: `safe_publish()` 封装了重试机制、审计截图、`pre_publish` / `post_publish` 钩子

### 3.2 已注册的平台适配器

| 平台 | 文件 | 技术方案 | 功能 |
|------|------|----------|------|
| 抖音 | `douyin.py` (47KB) | Playwright 浏览器自动化 | 登录/发布/搜索/评论/评论获取 |
| 小红书 | `xiaohongshu.py` (14KB) | Playwright 浏览器自动化 | 登录/发布 |
| B站 | `bilibili.py` (8KB) | Playwright 浏览器自动化 | 登录/发布 |
| 快手 | `kuaishou.py` (7KB) | Playwright 浏览器自动化 | 登录/发布 |
| 微信公众号 | `wechat_desktop.py` (21KB) | Windows UI Automation | 登录/发布 |

### 3.3 浏览器基础设施

- **BrowserPool** (`browser_pool.py`): 单例共享 Playwright 浏览器实例，防止进程泄漏，支持上下文复用和空闲清理
- **SessionManager** (`session_manager.py`): 持久化 Playwright `storage_state` (cookies + localStorage) 到 `data/sessions/` 目录
- **反检测** (`anti_detect.py`, `stealth.min.js`): 注入 stealth 脚本，包含 WebDriver 隐藏、Navigator 伪装、Canvas 指纹干扰等反爬措施

### 3.4 采集适配层 (新增)

- **文件**: `integrations/acquisition_adapters.py`
- **设计**: 统一 `search` / `send_comment` / `get_comments` / `send_dm` 接口，各平台独立实现
- **实现**:

| 平台 | 适配器类 | 技术方案 | 依赖 |
|------|----------|----------|------|
| B站 | `BilibiliAcquisitionAdapter` | bilibili-api-python 纯 API 调用 | `bilibili-api-python` (pip) |
| 抖音 | `PlaywrightAcquisitionAdapter` | Playwright 浏览器自动化 | 复用现有 BrowserPool |
| 小红书 | `PlaywrightAcquisitionAdapter` | Playwright 浏览器自动化 | 复用现有 BrowserPool |
| 快手 | `PlaywrightAcquisitionAdapter` | Playwright 浏览器自动化 | 复用现有 BrowserPool |

- **B站凭证**: 从 `data/sessions/bilibili_credential.json` 加载 `sessdata` + `bili_jct`，支持评论发送和私信
- **数据标准化**: `_normalize_search_result()` 和 `_normalize_comment()` 将各平台返回数据统一为标准格式

---

## 4. 流量引擎 (4个引擎)

### 4.1 智能截流引擎

- **文件**: `intercept_engine.py` (20KB)
- **功能**: 多平台视频搜索聚合 → 五维质量评分 → 去重 → 一键截流流水线
- **质量评分**: engagement(30%) + plays(25%) + freshness(20%) + author(15%) + bonus(10%)
- **A/B 测试**: 支持两种评论策略对比测试
- **桥接**: 优先调用 `AcquisitionAdapter.search()`，fallback 到平台适配器 `adapter.search()`

### 4.2 评论管理引擎

- **文件**: `comment_engine.py` (23KB)
- **功能**: 评论队列持久化、频率控制 (小时+日双上限)、DeAI 去AI味处理、批量发送
- **DeAI 处理器**: LLM 后处理，去除 AI 模板句式、替换敏感营销词、添加真人语气
- **发前检查**: 屏蔽词检测、长度校验、中文占比检查、垃圾模式识别
- **桥接**: 优先调用 `AcquisitionAdapter.send_comment()`，fallback 到平台适配器

### 4.3 舆情监听引擎

- **文件**: `listen_engine.py` (17KB)
- **功能**: 后台异步轮询目标视频新评论、关键词情感分析 (positive/negative/question/lead)、客户线索自动识别
- **回调机制**: 新评论通知和线索通知
- **桥接**: 优先调用 `AcquisitionAdapter.get_comments()`，fallback 到平台适配器

### 4.4 客户转化引擎

- **文件**: `convert_engine.py` (19KB)
- **功能**: 四维线索评分 (intent 40 + engagement 25 + urgency 20 + value 15)、A/B/C/D 等级分档、自动回复生成、转化漏斗追踪
- **转化漏斗**: discovered → replied → dm_sent → responded → qualified → converted
- **回复上下文**: per-user 会话历史记忆
- **桥接**: 优先调用 `AcquisitionAdapter.send_comment()`，fallback 到平台适配器

---

## 5. 内容发布系统

### 5.1 发布管道

- **文件**: `publisher.py` (18KB)
- **流程**: AI 生成 → 人工审核 → 定时发布 → 发布历史
- **内容类型**: post (短帖) / article (长文) / video (视频脚本) / image (图文)
- **多平台发布**: `publish_async()` 并发发布到多个平台，调用 `PlatformRegistry` 获取适配器执行 `safe_publish`
- **原子操作**: 使用 `atomic_file.py` 实现线程安全的文件读写

### 5.2 智能调度引擎

- **文件**: `scheduler_engine.py` (27KB)
- **触发类型**: Cron 表达式 / 固定间隔 / 定时执行
- **任务动作**: `PUBLISH_CONTENT` / `GENERATE_CONTENT` / `RUN_WORKFLOW` / `PLATFORM_LOGIN_CHECK` / `PLATFORM_HEALTH_CHECK`
- **健康追踪**: 连续 tick 失败计数、per-job 失败计数、自动暂停问题任务
- **后台轮询**: `_run_loop()` 异步轮询，`_tick()` 执行到期任务

---

## 6. AIGC 多模型流水线

### 6.1 流水线引擎

- **文件**: `pipeline_engine.py` (28KB)
- **架构**: DAG (有向无环图) 流水线定义，支持节点依赖、拓扑排序、分层并行执行
- **节点类型**: text (LLM 文本) / image (AI 图像) / video (AI 视频) / audio (TTS) / skill (技能调用)
- **执行器**: `PipelineExecutor` 支持超时控制、重试逻辑、可选节点、模板参数渲染
- **集成**: 深度集成火山引擎方舟多模型 API

### 6.2 火山引擎集成

- **文件**: `integrations/volcengine_client.py` (32KB)
- **能力**: 文本对话 (OpenAI 兼容 API)、图像生成、视频生成 (异步轮询)、语音合成 (TTS)、语音克隆、Embedding 向量
- **模型**: 豆包 Pro 系列文本模型、豆包图像模型、豆包视频模型、豆包 TTS 模型

### 6.3 本地 AI 引擎

| 引擎 | 文件 | 功能 |
|------|------|------|
| Ollama | `integrations/ollama_client.py` | 本地 LLM 对话/生成/流式 |
| ComfyUI | `integrations/comfyui_client.py` | 本地 Stable Diffusion 图像生成 |
| Whisper | `integrations/whisper_client.py` | 语音转文字 |
| FFmpeg | `integrations/ffmpeg_client.py` | 音视频处理 |
| LiteLLM | `integrations/litellm_client.py` | 多 LLM 后端统一接口 |
| OpenRouter | `integrations/openrouter_client.py` | OpenRouter API 代理 |

---

## 7. 视频处理

### 7.1 视频剪辑引擎

- **文件**: `video_cut_engine.py` (11KB)
- **功能**: 视频裁剪、拼接、变速、标题文字叠加 (多字体)、音频替换、音频混音、封面提取
- **依赖**: FFmpeg (支持多路径查找)
- **模板**: `video_templates/` 目录包含 12 个视频模板

### 7.2 视觉定位模块

- **文件**: `vision_grounding.py` (33KB)
- **三层架构**:
  - Tier 1: OmniParser v2 (YOLO-based UI 元素检测，需 GPU)
  - Tier 2: Hermes 辅助视觉模型 (文本分析)
  - Tier 3: CSS selector fallback
- **用途**: 为平台适配器提供视觉元素定位能力，替代脆弱的 CSS 选择器

---

## 8. API 路由层

### 8.1 路由模块 (24个)

| 路由文件 | 功能 |
|----------|------|
| `hermes_chat.py` (118KB) | LLM 对话 + 工具调用编排 (核心) |
| `acquisition_routes.py` (26KB) | 截流/评论/监听/转化 API |
| `platform_routes.py` (13KB) | 平台管理 API |
| `infra_routes.py` (9KB) | 基础设施管理 API |
| `publisher_routes.py` (7KB) | 内容发布 API |
| `pipeline_endpoint.py` (7KB) | 流水线 API |
| `client.py` (8KB) | 客户端管理 API |
| `video_endpoint.py` (3KB) | 视频剪辑 API |
| `scheduler_routes.py` (3KB) | 调度任务 API |
| `tools_routes.py` (4KB) | 工具市场 API |
| `agent_routes.py` (3KB) | 智能体 API |
| `announce_routes.py` (3KB) | 公告管理 API |
| `oem_routes.py` (2KB) | OEM 品牌 API |
| `hub_routes.py` (2KB) | Hub 路由 |
| `auth_routes.py` (2KB) | 认证 API |
| `frontend_routes.py` (3KB) | 前端路由 |
| `image_endpoint.py` (3KB) | 图像生成 API |
| `models_endpoint.py` (2KB) | 模型列表 API |
| `brain_routes.py` | 内核诊断 API |
| `chat.py` | 聊天补全 API (OpenAI 兼容) |

### 8.2 安全机制

- **JWT 认证** (`auth.py`): PBKDF2-SHA256 密码哈希，7天有效期 token
- **工具白名单**: `_execute_tool()` 中的 `ALLOWED` 集合限制可执行工具
- **路径白名单**: `_PATH_ALLOWLIST` 限制文件操作范围，防止路径遍历
- **参数消毒**: `_sanitize_args()` 解析和验证工具参数
- **破坏性工具**: `DESTRUCTIVE_TOOLS` 集合标记需要管理员权限的工具
- **多租户隔离** (`tenant.py`): 基于 `contextvars` 的请求级租户上下文

---

## 9. 数据持久化

### 9.1 文件存储

- **位置**: `data/` 目录
- **原子读写**: `atomic_file.py` 实现线程安全的 JSON 文件读写
- **多租户**: 通过 `get_tenant_data_file()` 按租户隔离数据文件

### 9.2 SQLite 数据库

- **认证**: `data/auth.db` — 用户认证数据
- **记忆**: SQLite FTS5 — 长期记忆全文检索

### 9.3 会话存储

- **位置**: `data/sessions/`
- **内容**: 各平台 Playwright `storage_state` (cookies + localStorage)
- **B站凭证**: `bilibili_credential.json` — API 凭证 (sessdata + bili_jct)

---

## 10. 测试覆盖

### 10.1 测试文件

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_mcp.py` | MCP Server 框架 |
| `test_platforms.py` | 平台适配器/调度器/MCP工具/路由 |
| `test_api.py` | API 路由/认证/模型兼容性 |
| `test_integrations.py` | Whisper/ComfyUI/FFmpeg/Ollama/LiteLLM |
| `test_config.py` | 配置加载 |
| `test_e2e.py` | 端到端流程 |
| `test_skill_registry.py` | 技能注册 |
| `test_wechaty.py` | 微信桥接 |
| `test_memory.py` | 记忆系统 |
| `test_model_router.py` | 模型路由 |

### 10.2 测试结果

- **回归测试**: 138 项全部通过 (10秒)
- **采集集成测试**: 13 项全部通过 (含 B站真实 API 搜索验证)

---

## 11. 依赖管理

- **工具**: uv + pyproject.toml
- **Python**: >=3.12
- **核心依赖**: FastAPI, Pydantic, Playwright, httpx, PyYAML, structlog
- **平台采集**: bilibili-api-python, douyin-tiktok-scraper
- **可选依赖**: openai (LLM), openpyxl/python-docx/python-pptx (文档), PyPDF2/pdfplumber (PDF), beautifulsoup4 (HTML解析)

---

## 12. 当前实现状态总结

| 模块 | 状态 | 说明 |
|------|------|------|
| AI 核心 (Hermes) | ✅ 已实现 | 80+ 工具调用，SSE 流式响应 |
| 长期记忆 | ✅ 已实现 | SQLite FTS5 全文检索 |
| 知识库 (RAG) | ✅ 已实现 | 文档摄入 + 上下文检索 |
| SOP 管理器 | ✅ 已实现 | 自定义工作流模板 |
| MCP Server 框架 | ✅ 已实现 | JSON-RPC 2.0, 13个 MCP Server |
| 平台适配器 (5平台) | ✅ 已实现 | 抖音/小红书/B站/快手/微信 |
| 采集适配器 (4平台) | ✅ 已实现 | B站API + 3平台Playwright |
| 智能截流引擎 | ✅ 已实现 | 搜索→评分→生成→发送 |
| 评论管理引擎 | ✅ 已实现 | 队列/频率/DeAI/批量发送 |
| 舆情监听引擎 | ✅ 已实现 | 异步轮询/情感分析/线索发现 |
| 客户转化引擎 | ✅ 已实现 | 线索评分/自动回复/漏斗追踪 |
| 内容发布管道 | ✅ 已实现 | AI生成→审核→定时→多平台发布 |
| 智能调度引擎 | ✅ 已实现 | Cron/间隔/定时 + 重试 + 健康追踪 |
| AIGC 流水线 | ✅ 已实现 | DAG编排 + 多模型 + 并行执行 |
| 火山引擎集成 | ✅ 已实现 | 文本/图像/视频/TTS/克隆/Embedding |
| 视频剪辑引擎 | ✅ 已实现 | FFmpeg 裁剪/拼接/变速/标题/音频 |
| 视觉定位 | ✅ 已实现 | 三层架构 (OmniParser/视觉模型/CSS) |
| JWT 认证 | ✅ 已实现 | PBKDF2-SHA256 + 7天token |
| 多租户隔离 | ✅ 已实现 | contextvars 请求级隔离 |
| 工具运行时 | ✅ 已实现 | 插件安装/卸载/启动/停止 |
| OEM 品牌定制 | ✅ 已实现 | 名称/主题/版权配置 |
| 回归测试 | ✅ 138项通过 | 覆盖核心模块 |
