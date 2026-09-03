# 🎯 域灵系统 — 功能设计方案 v1.0

> 版本：v1.0
> 日期：2026-07-05
> 作者：Architect_Agent
> 基于：所有KnowledgeBase文档深度分析 + 实际代码库状态审计

---

## 1. 设计目标

将域灵从「一句话指挥AI干活」的原子能力工具，升级为面向中小企业的「炼刀AI式超级员工自动化营销平台」——一个拥有多能力聚合和基于Hermes超级员工的智能运营系统。

### 1.1 对标定位

| 维度 | 炼刀AI / 同类产品 | 域灵目标态 |
|------|-------------------|-----------|
| 交互模式 | 自然语言对话驱动 | ✅ 已实现 (SSE流式) |
| AI Agent | 超级员工概念 | ✅ Hermes已实现 |
| 内容生产 | 全模态AIGC | ✅ 文生图/视频/语音/文案 |
| 视频处理 | 剪辑工具链 | ✅ 裁剪/拼接/标题/音频 |
| 多平台发布 | 一键多平台 | ✅ 5平台全覆盖 |
| 获客截流 | 自动搜索+评论 | 🔄 后端就绪，前端待完善 |
| 工作流编排 | 可视化流水线 | ⚠️ 待建设 (Phase 2) |
| 数据分析 | 智能洞察 | ⚠️ 待建设 (Phase 3) |
| 知识库/RAG | 长期记忆 | ⚠️ DB就绪，逻辑待建设 |
| 自托管 | 本地部署 | ✅ Electron桌面端 |

---

## 2. 技术根基：Hermes超级员工架构

### 2.1 Hermes核心能力

```
Hermes (brain_hermes.py)
  ├── LLM推理层 (火山引擎方舟 doubao-seed-2-0-pro)
  │   ├── SYSTEM_PROMPT 注入 (角色/工具/输出规则)
  │   ├── Function Calling (工具自主选择)
  │   └── 多轮对话上下文管理
  │
  ├── 工具层 (30+ MCP工具)
  │   ├── 搜索类: acq_search (多平台)
  │   ├── 生成类: ai_image_generate, ai_video_create, ai_tts
  │   ├── 剪辑类: video_cut, video_concat, video_add_title ...
  │   ├── 发布类: platform_publish_direct, sau_upload_video
  │   ├── 平台类: platform_status, platform_login, platform_logout
  │   └── 数据类: platform_post_status
  │
  ├── 平台适配器层 (Playwright + MediaCrawler)
  │   ├── 抖音 (MediaCrawler优先 → 浏览器降级)
  │   ├── 小红书
  │   ├── 哔哩哔哩
  │   ├── 快手
  │   └── 微信视频号
  │
  └── 引擎层
      ├── video_cut_engine.py (FFmpeg)
      ├── publisher.py (多平台发布)
      ├── intercept_engine.py (智能截流)
      ├── listen_engine.py (舆情监听)
      └── convert_engine.py (客户转化)
```

### 2.2 当前Hermes对话全链路

```
用户输入 → SuperAgent.vue → POST /api/hermes/chat (SSE)
  → hermes_chat.py
    → LLM推理 (火山引擎)
    → 工具选择 + 执行
      → tool_call SSE事件 → 前端实时渲染
      → tool_result SSE事件 → 前端更新状态
    → 文本生成 + 流式输出
      → text SSE事件 → 前端Markdown渲染
    → 多媒体
      → video_task → video_status → video SSE事件
      → image SSE事件
  → 对话自动保存 → conversation_routes.py
    → JSON文件持久化 (data/tenants/{id}/conversations/)
```

---

## 3. 三层能力金字塔

```
           ┌─────────────────────────┐
           │  决策智能层 (Phase 3)    │
           │  数据分析 / 策略推荐     │
           │  A/B测试 / 竞品分析      │
           ├─────────────────────────┤
           │  编排自动化层 (Phase 2)   │
           │  流水线 / 调度 / SOP     │
           │  获客截流完整化           │
           ├─────────────────────────┤
           │  原子能力层 (Phase 1)    │
           │  对话 / 生成 / 剪辑 / 发布 │
           │  ← 当前已完成 ✅          │
           └─────────────────────────┘
```

---

## 4. Phase 1 — 稳定原子能力层 (当前优先)

### 4.1 设计系统落地 (P0)

> 执行 migration-plan.md 的6阶段迁移

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | 统一CSS变量 (style.css → design-system.md对齐) | 🔴 待执行 |
| 2 | Element Plus组件覆盖 (tech-theme.css → component-specs.md) | 🔴 待执行 |
| 3 | AppLayout重构 (220→200px, 48→56px, 毛玻璃) | 🔴 待执行 |
| 4 | 全局工具类建立 (.text-*, .app-grid, .animate-in) | 🟡 待执行 |
| 5 | 43个页面逐个审计 | 🟡 待执行 |
| 6 | 移除Solarized主题残留 | 🟡 待执行 |

### 4.2 对话体验增强 (P1)

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 对话搜索 | 历史对话标题模糊搜索 | 🟡 P1 |
| 消息操作栏 | hover出现：复制/重新生成/反馈 | 🟡 P1 |
| 多Agent切换 | 对话中切换不同Agent角色 | 🟡 P1 |
| 消息反馈 | 点赞/点踩，优化输出质量 | 🟢 P2 |
| 对话标签 | 颜色标签分类管理 | 🟢 P2 |

### 4.3 稳定性增强 (P0-P1)

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 错误码体系 | 统一错误码定义 (CONVENTIONS/error-codes.md) | 🔴 P0 |
| 编码规约 | 填充Python/Vue/API/Naming规约 | 🔴 P0 |
| API契约文档 | 为核心API建立真实契约文档 | 🟡 P1 |
| 数据模型文档 | 填充schema-overview/sqlite-tables | 🟡 P1 |

---

## 5. Phase 2 — 构建编排自动化层 (中期)

### 5.1 智能获客引擎完整化 (P0)

```
获客工作流:
  搜索 → 筛选 → 分析 → 执行 → 沉淀

  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
  │ ① 搜索   │──▶│ ② 筛选   │──▶│ ③ 分析   │──▶│ ④ 执行   │──▶│ ⑤ 沉淀   │
  │ 抖音搜索  │   │ LLM排序  │   │ 评论分析 │   │ 自动评论 │   │ CRM标签  │
  │ 返回Top20 │   │ 筛选Top5 │   │ 客户画像 │   │ 自动私信 │   │ 跟进提醒 │
  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

| 前端页面 | 路由 | 说明 | 后端依赖 |
|----------|------|------|----------|
| 智能截流工作台 | `/marketing/intercept` | 配置策略→预览→执行 | intercept_engine.py ✅ |
| 舆情监听中心 | `/marketing/listen` | 关键词监听→通知 | listen_engine.py ✅ |
| 客户转化 | `/marketing/conversion` | 截流→私信→标签→跟进 | convert_engine.py ✅ |
| 客户资产 | `/marketing/customers` | 客户列表/标签/时间线 | 需新建 |

### 5.2 流水线编排器 (P0 新功能)

可视化拖拽式工作流设计器，将多个原子工具编排为自动化流水线。

**节点类型定义**：

| 节点类型 | 图标 | 功能 | 示例 |
|----------|------|------|------|
| 触发器 | ⏰ | 定时/手动/Webhook触发 | 每天9:00自动执行 |
| 搜索 | 🔍 | 多平台关键词搜索 | 抖音搜索「AI工具」 |
| 生成 | 🎨 | AI内容生成 (图/视频/文案) | 文生视频 |
| 剪辑 | ✂️ | 视频处理 (裁剪/标题/混音) | 加标题+背景音乐 |
| 发布 | 📤 | 多平台内容发布 | 发到抖音+小红书 |
| 条件 | 🔀 | 条件分支判断 | 播放量>1000则继续 |
| 延时 | ⏳ | 等待指定时间 | 等待30分钟 |
| 通知 | 🔔 | 消息通知 | 企业微信/邮件通知 |

**流水线JSON Schema**：

```json
{
  "id": "pipeline_daily_post",
  "name": "每日AI视频自动发布",
  "trigger": { "type": "cron", "value": "0 9 * * *" },
  "nodes": [
    { "id": "n1", "type": "search", "config": { "platform": "douyin", "keyword": "AI教程" } },
    { "id": "n2", "type": "ai_video", "config": { "prompt": "根据{{n1.title}}创作短视频", "duration": 15 } },
    { "id": "n3", "type": "video_cut", "config": { "input": "{{n2.output}}", "start": 0, "duration": 15 } },
    { "id": "n4", "type": "publish", "config": { "platforms": ["douyin", "xhs"], "title": "{{n1.title}}" } }
  ],
  "edges": [["n1","n2"],["n2","n3"],["n3","n4"]]
}
```

### 5.3 调度引擎升级

| 功能 | 说明 |
|------|------|
| 定时任务管理 | 可视化日历视图，Cron + 自然语言（「每天早上9点」） |
| 任务队列 | 待执行/执行中/已完成/失败，支持暂停/恢复 |
| 并发控制 | 多平台发布速率限制 |
| 通知 | 完成/失败时前端Toast + 可选企业微信通知 |

---

## 6. Phase 3 — 决策智能层 (远期)

| 功能模块 | 说明 | 路由 |
|----------|------|------|
| 运营仪表盘 | 发布量/播放量/互动量/转化率趋势 | `/insights/dashboard` |
| 内容分析 | 内容表现排名、最佳发布时间、标签效果 | `/insights/content-analytics` |
| 截流效果分析 | 评论转化率、不同类型评论效果对比 | `/insights/acquisition-analytics` |
| 转化分析 | 客户旅程漏斗、转化归因 | `/insights/conversion-analytics` |
| A/B测试 | 标题/封面/时间A/B实验框架 | `/marketing/ab-test` |
| AI策略建议 | 基于数据的周度运营报告 | 对话内集成 |
| 竞品分析 | 自动追踪竞品账号内容策略 | 需新建 |

---

## 7. 实施路线图

```
Week 1-2: 稳定地基 🔴
├── 设计系统迁移 Phase 1-3
├── AppLayout重构 (200px/64px/56px)
├── 编码规约填充
├── 错误码体系统一
└── API契约文档建立

Week 3-4: 体验增强 🟡
├── 对话搜索
├── 消息操作增强
├── 多Agent切换
├── 数据模型文档完善
└── 设计系统迁移 Phase 4-6

Week 5-8: 编排能力 🟢
├── 获客截流完整化
├── 流水线编排器 MVP
├── 调度引擎 UI
└── 客户资产管理

Week 9-12: 数据智能 🔵
├── 运营仪表盘
├── 内容/截流分析
├── A/B测试框架
└── AI策略建议
```

---

## 8. 质量保障策略

### 8.1 关键验证路径

| 验证项 | 方法 | 优先级 |
|--------|------|--------|
| SSE流式对话全链路 | E2E: 发送消息→流式返回→工具调用→保存 | 🔴 |
| 视频生成+卡片渲染 | E2E: 文生视频→进度→播放器 | 🔴 |
| 抖音搜索-截流闭环 | E2E: 搜索→获取→评论→发布 | 🔴 |
| 多平台发布 | 逐个平台验证 | 🔴 |
| 设计系统迁移后视觉回归 | 截图对比Light/Dark所有页面 | 🟡 |
| 响应式布局 | 1280/1024/768/480断点 | 🟡 |
| 对话导出完整性 | Markdown导出所有消息类型 | 🟡 |

### 8.2 测试金字塔

```
        ┌──────┐
        │ E2E  │  5个核心用户旅程 (Playwright)
        ├──────┤
        │ 集成  │  API契约测试 (FastAPI TestClient + pytest)
        ├──────┤
        │ 单元  │  引擎层单元测试 (pytest + mock)
        └──────┘
```

---

## 9. 文档重组结果

本次清理与重组后的KnowledgeBase目录结构：

```
KnowledgeBase/
├── README.md                              # ✅ 总索引
├── PRD/
│   ├── README.md                          # ✅ 更新：仅列出真实PRD
│   ├── product-requirements.md            # ✅ v3.0 主PRD
│   └── ai-staff-system.md                 # ✅ AI员工系统
├── DESIGN/
│   ├── README.md                          # ✅ 设计系统索引
│   ├── design-system.md                   # ✅ 核心视觉语言
│   ├── layout-framework.md                # ✅ 应用外壳布局
│   ├── component-specs.md                 # ✅ 全局组件规范
│   ├── page-super-agent.md                # ✅ 超级员工页面
│   └── migration-plan.md                  # ✅ 设计系统迁移计划
├── ARCHITECTURE/
│   ├── README.md                          # ✅ 更新：含specs子目录
│   ├── system-overview.md                 # ✅
│   ├── backend-structure.md               # ✅
│   ├── frontend-structure.md              # ✅
│   ├── electron-layer.md                  # 🔄 模板已有
│   ├── data-flow.md                       # 🔄 模板已有
│   ├── security-model.md                  # 🔄 模板已有
│   └── specs/                             # 🆕 专项设计规范
│       ├── welcome-page-redesign.md        # ✅
│       ├── chat-message-ui.md              # ✅
│       ├── chat-context-menu.md            # ✅
│       ├── chat-video-card.md              # ✅
│       ├── douyin-mcp-integration.md       # ✅
│       └── douyin-search-fix.md            # ✅
├── API_SPECS/
│   ├── README.md                          # ✅ 更新
│   └── welcome-case-cards-spec.md         # ✅
├── DATABASE/
│   ├── README.md
│   ├── schema-overview.md                 # 🔄 模板已有
│   ├── sqlite-tables.md                   # 🔄 模板已有
│   └── file-storage.md                    # 🔄 模板已有
├── CONVENTIONS/
│   ├── README.md
│   ├── python-style.md                    # 🔄 模板已有
│   ├── vue-style.md                       # 🔄 模板已有
│   ├── api-design.md                      # 🔄 模板已有
│   ├── error-codes.md                     # 🔄 模板已有
│   ├── naming.md                          # 🔄 模板已有
│   └── llm-output-rules.md                # ✅
└── DECISIONS/
    ├── README.md
    └── ADR-001-volcengine-as-default-llm.md  # ✅
```

> 🗑️ 已删除：17个0字节空占位文件 (API_SPECS 11个 + PRD 6个)
> 📦 已移动：6个ARCHITECTURE专项规范移至 specs/ 子目录

---

## 10. 附录：待删除陈旧的替代建议

| 旧路径 | 处理 |
|--------|------|
| `API_SPECS/acquisition-routes.md` 等11个空文件 | ✅ 已删除 |
| `PRD/acquisition-analytics.md` 等6个空文件 | ✅ 已删除 |
| `ARCHITECTURE/*-spec.md` 散落文件 | ✅ 移至 specs/ |
| `PRD/README.md` 引用已删除文件 | ✅ 已更新 |
| `ARCHITECTURE/README.md` 缺少specs索引 | ✅ 已更新 |
| `API_SPECS/README.md` 引用已删除文件 | ✅ 已更新 |
