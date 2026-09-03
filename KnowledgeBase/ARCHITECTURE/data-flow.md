# 🔄 核心数据流

## 1. 用户请求流 (标准 CRUD)

```
用户操作 (浏览器/Electron)
  │
  ▼
Vue 组件 (web/src/pages/*.vue)
  │  axios 请求 + JWT header
  ▼
FastAPI 路由 (server/szyg/api/*_routes.py)
  │  TenantMiddleware → 设置租户上下文
  │  认证校验 → JWT 解析 → User 对象
  ▼
业务引擎 (server/szyg/*_engine.py)
  │  逻辑处理 + 数据操作
  ▼
存储层 (SQLite / JSON 文件)
  │
  ▼
JSON / SSE 响应
  │
  ▼
Vue 组件渲染
```

## 2. AI 对话流 (Hermes 超级员工)

```
用户输入消息
  │
  ▼
SuperAgent.vue → POST /api/hermes/chat (SSE)
  │
  ▼
hermes_chat.py
  │  构建系统提示词 + 加载 MCP 工具
  ▼
LLM 后端 (火山引擎 / Ollama)
  │  流式生成 → SSE 事件推送
  ▼
前端实时渲染 (marked + dompurify)
  │
  ▼
对话结束 → conversation_routes.py 持久化
```

## 3. 多平台发布流

```
用户选择内容 + 平台
  │
  ▼
PublishCenter.vue → POST /api/publisher/publish
  │
  ▼
publisher.py (发布引擎)
  │  根据平台选择适配器
  ▼
platforms/registry → 适配器 (抖音/小红书/微信)
  │  Playwright (浏览器自动化) 或 UIA (Windows 桌面)
  ▼
平台操作 (登录 → 上传 → 发布)
  │
  ▼
结果返回 → 前端展示发布状态
```

## 4. 调度任务流

```
用户创建调度任务 (SchedulerEngine.vue)
  │
  ▼
POST /api/scheduler/tasks
  │
  ▼
scheduler_engine.py
  │  注册定时任务 → 后台 asyncio 循环
  ▼
到达触发时间
  │  执行任务 (发布/截流/监听等)
  ▼
结果持久化 → 通知前端
```

## 5. AIGC 流水线流

```
用户配置流水线 (PipelineDesigner.vue)
  │  文本 → 图像 → 视频 → 语音
  ▼
POST /api/pipeline/run
  │
  ▼
pipeline_engine.py
  │  按步骤执行，每步可调用不同模型
  ├─ 文本生成: LLM (火山引擎/Ollama)
  ├─ 图像生成: ComfyUI / 火山引擎 Seedream
  ├─ 视频生成: 火山引擎 Seedance
  └─ 语音合成: edge-tts
  ▼
产物存储 → data/volcengine_output/ 或 data/comfyui_output/
  │
  ▼
前端展示结果
```
