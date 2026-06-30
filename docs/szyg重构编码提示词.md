# szyg 系统重构 — 编码 Agent 集群提示词

> **用途**: 交付给 agent 集群，逐步实施 szyg 前端重构。
> **SSOT 文档**: `docs/szyg产品功能融合设计.md`（产品设计）、`docs/szyg前端实施规范.md`（开发者规范）
> **当前状态**: 34 个独立 Vue 页面 + 5 栏导航 → 目标: 10 个核心页面 + SuperStaffPanel 全局面板
> **日期**: 2026-06-28

---

## 一、系统上下文

### 1.1 szyg 是什么

企业级智能数字员工平台。基于 Hermes Agent 内核（Multi-Agent 编排 + Kanban 任务看板 + Skills 技能系统），提供内容生产→多平台发布→公域获客→私域转化全链路 AI 自动化。

### 1.2 技术栈

| 层 | 技术 | 关键文件 |
|-----|------|---------|
| 前端 | Vue 3 + Element Plus + Pinia + Vue Router (createWebHistory) | `web/src/` |
| 后端 | FastAPI + SSE 流式 + Playwright 浏览器自动化 | `server/szyg/` |
| AI 内核 | Hermes Agent v0.15 (Kanban + Delegate Task + MCP 工具) | `hermes.yaml`, `server/szyg/brain_hermes.py` |
| MCP 工具 | 10 个独立 MCP 子进程 (stdio JSON-RPC)，86+ 工具 | `server/szyg/mcp_servers/` |
| 对话接口 | `POST /api/hermes/chat` (SSE 流式，6 种事件类型) | `server/szyg/api/hermes_chat.py` |

### 1.3 当前问题

- **导航过载**: 5 个栏目，内容工厂下塞了 13 个子项
- **功能未闭环**: 一个视频创作流程需跳 5 次页面
- **缺乏主入口**: 没有统一的任务下达和进度监控中心
- **后端能力与前端展示错位**: 后端有 Hermes 超级员工架构，前端完全没体现

---

## 二、目标架构

### 2.1 导航结构（5 项一级导航）

```
/dashboard              → Dashboard.vue          (今日指挥台)
/ai-staff               → AiStaff.vue (壳)        (操作工作台)
  /ai-staff/overview    → StaffOverview.vue       (4个员工状态卡片)
  /ai-staff/tasks       → TaskBoard.vue           (Kanban 任务看板)
  /ai-staff/content-studio      → ContentStudio.vue     (内容专员工作室, 3 Tab)
  /ai-staff/acquisition-studio  → AcquisitionStudio.vue (获客专员工作室, 4 Tab)
  /ai-staff/conversion-studio   → ConversionStudio.vue  (转化专员工作室, 4 Tab)
  /ai-staff/ops-studio          → OpsStudio.vue         (运营专员工作室, 3 Tab)
/assets                 → ContentAssets.vue       (内容沉淀页, 只读)
/crm                    → CustomerAssets.vue      (客户沉淀页, 只读)
/settings               → Settings.vue (壳)        (系统设置)
  /settings/platforms   → SettingsPlatforms.vue   (平台账号 + 安全评分)
  /settings/skills      → SettingsSkills.vue      (技能市场, agentskills.io)
  /settings/tools       → SettingsTools.vue       (工具管理)
  /settings/system      → SettingsSystem.vue       (系统配置)
  /settings/brand       → SettingsBrand.vue       (品牌配置, admin)
  /settings/team        → SettingsTeam.vue        (团队管理, admin)
```

### 2.2 全局组件（非路由）

- `SuperStaffButton.vue` — 56px 圆形青色脉冲 FAB，右下角悬浮，所有页面可见
- `SuperStaffPanel.vue` — 右侧滑出对话面板（420px 毛玻璃），对接 `/api/hermes/chat` SSE

### 2.3 页面类型

| 类型 | 页面 | 特征 |
|------|------|------|
| 操作工作台 | 4 个 Studio | 可编辑、可提交、可执行 |
| 只读沉淀 | ContentAssets / CustomerAssets | 可搜索、可筛选、不可编辑 |
| 指挥台 | Dashboard | 全局概览 + 快捷入口 |
| 配置页 | Settings 子页 | 低频管理操作 |
| 全局面板 | SuperStaffPanel | 随时唤起，不占导航位 |

---

## 三、实施 Phase 与任务

### 🔴 Phase 1: 骨架路由 + 超组员工面板空壳（优先）

**目标**: 新导航可访问，超级员工面板可展开/收起，旧路由全部重定向。**不破坏任何现有功能**。

**并行度**: 任务 1.1 必须最先完成（router + AppLayout），之后 1.2-1.6 可并行。

#### 任务 1.1 — 重写路由和导航（顺序第一）

```
修改文件: web/src/router.js
修改文件: web/src/components/AppLayout.vue
```

**router.js 要求**:
1. 保留现有所有路由（先加新路由，后加重定向）
2. 添加 §2.1 中所有新路由，使用 `() => import(...)` 懒加载
3. 添加完整旧路由重定向（见 §4.2）
4. **关键约束**: `/chat` 路由**暂不修改**，保持指向 `ChatPage`。Phase 2 面板可用后才迁移
5. 路由 meta 格式: `{ requiresAuth: true, section: 'dashboard'|'ai-staff'|'assets'|'crm'|'settings', title: '...' }`

**AppLayout.vue 要求**:
1. 顶部导航改为 5 项:
   - 📊 仪表盘 (`/dashboard`)
   - 👥 AI员工 (`/ai-staff/overview`)
   - 📦 内容资产 (`/assets`)
   - 💼 客户资产 (`/crm`)
   - ⚙️ 系统设置 (`/settings/platforms`)
2. 导航高亮: 根据 `route.meta.section` 匹配
3. 侧边栏逻辑: 当路由 section 为 `ai-staff` 时，显示 AI 员工子导航（overview / tasks / 4 个 studio）；当 section 为 `settings` 时，显示设置子导航
4. 挂载 `<SuperStaffButton />` 组件（所有页面可见）
5. 监听 `route.query.panel === 'open'` → 自动展开 SuperStaffPanel

**验收标准**:
- 浏览器访问 `/dashboard`、`/ai-staff/overview`、`/assets`、`/crm`、`/settings/platforms` 均显示对应空壳组件（可先显示占位文字）
- 访问任意旧路径（如 `/pipeline/chat`、`/agents`）均重定向到新路径
- 访问 `/chat` 仍然打开原 ChatPage（功能不受影响）
- 导航切换高亮正确

#### 任务 1.2 — 新建所有页面空壳

```
新建文件:
  web/src/pages/AiStaff.vue            (含 <router-view> 的壳)
  web/src/pages/StaffOverview.vue      (占位: "员工概览")
  web/src/pages/TaskBoard.vue          (占位: "任务看板")
  web/src/pages/ContentStudio.vue      (占位: 3 个 tab 标签)
  web/src/pages/AcquisitionStudio.vue   (占位: 4 个 tab 标签)
  web/src/pages/ConversionStudio.vue    (占位: 4 个 tab 标签)
  web/src/pages/OpsStudio.vue          (占位: 3 个 tab 标签)
  web/src/pages/ContentAssets.vue      (占位: "内容资产")
  web/src/pages/CustomerAssets.vue     (占位: "客户资产")
  web/src/pages/Settings.vue           (含 <router-view> 的壳)
  web/src/pages/SettingsPlatforms.vue   (占位)
  web/src/pages/SettingsSkills.vue     (占位)
  web/src/pages/SettingsTools.vue      (占位)
  web/src/pages/SettingsSystem.vue      (占位)
  web/src/pages/SettingsBrand.vue      (占位)
  web/src/pages/SettingsTeam.vue       (占位)
```

每个空壳包含: 组件名 + 页面标题 + 占位内容。Studio 空壳需包含 tab 切换结构（仅 UI，不含功能）。

#### 任务 1.3 — 新建 SuperStaff 组件

```
新建文件:
  web/src/components/SuperStaffButton.vue
  web/src/components/SuperStaffPanel.vue
  web/src/stores/superStaff.ts         (或 .js)
```

**SuperStaffButton.vue**:
- 56px × 56px 圆形按钮，固定在页面右下角 (bottom: 24px, right: 24px)
- 青色渐变背景 (`linear-gradient(135deg, #00d4ff, #0099cc)`)
- CSS 脉冲动画 (`@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(0,212,255,0.4) } 70% { box-shadow: 0 0 0 15px rgba(0,212,255,0) } 100% { box-shadow: 0 0 0 0 rgba(0,212,255,0) } }`)
- 图标: 闪电/机器人 SVG icon
- 点击 → toggle SuperStaffPanel

**SuperStaffPanel.vue** (空壳):
- 右侧滑出面板，带 300ms transition (transform: translateX)
- 宽度 420px，背景半透明深色 + `backdrop-filter: blur(12px)`
- 左侧 1px 青色发光边框
- 面板结构: PanelHeader + MessageList (空) + InputArea + PanelFooter
- PanelHeader: "超级员工" 标题 + 状态灯 + 全屏按钮 (预留) + 关闭按钮
- InputArea: textarea + 发送按钮
- PanelFooter: 模型名称 + 连接状态
- 关闭方式: 点击关闭按钮 / 点击面板外遮罩 / 按 Escape

**superStaffStore (Pinia)**:
```typescript
interface SuperStaffState {
  isOpen: boolean
  isFullscreen: boolean
  messages: Message[]
  isThinking: boolean
  currentToolCall: ToolCall | null
  activeTasks: Task[]
  sessionId: string
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting'
}
```
Phase 1 只实现 isOpen 状态切换，其余字段 Phase 2 对接。

**验收标准**:
- 任意页面右下角看到青色脉冲按钮
- 点击 → 右侧滑出面板 (420px 毛玻璃)
- 点击遮罩 / 关闭按钮 / Escape → 面板关闭
- 面板内可看到标题栏 + 空消息区 + 输入框 + 底部状态

#### 任务 1.4 — 重写 Dashboard.vue 布局

```
修改文件: web/src/pages/Dashboard.vue
```

新布局（从上到下）:
1. 顶部快捷输入框: 高度 48px，placeholder "输入指令，如：帮我发3条抖音视频并处理评论区私信"。右侧 [⚡ 发送] 按钮。下方一行快捷标签: [一键上班] [生成今日内容] [检查平台状态] [处理昨日私信]（点击填充输入框）
2. 员工状态卡片行: 水平排列 4 个卡片（内容专员 / 获客专员 / 转化专员 / 运营专员）。每张卡片显示: 头像图标 + 名称 + 状态灯 (运行中/空闲) + 今日任务进度条 + 完成任务数。Phase 1 使用 mock 数据。
3. 左侧 Kanban 区域: 4 列（ready / running / blocked / done），空壳，Phase 2 对接数据
4. 右侧今日数据: 4 个指标卡片（今日发布 / 新增线索 / 新增客户 / 转化率），每卡片显示数值 + 环比变化百分比，Phase 1 使用 mock 数据

**验收标准**: 仪表盘新布局正确渲染，mock 数据显示正常，快捷标签可点击填充输入框

#### 任务 1.5 — 旧路由兼容性验证

```
验证方式: 逐个检查旧路由重定向
```

1. 遍历当前 `router.js` 中所有旧路径
2. 访问每个旧路径 → 确认跳转到正确的新路径
3. 确认不会出现 404 或死循环重定向
4. 尤其验证 `/chat` 仍能正常打开 ChatPage

#### 任务 1.6 — 不破坏现有功能验证

1. 现有 ChatPage (`/chat`) → SSE 对话正常
2. 现有 Agents 页访问 → 重定向到 `/ai-staff/overview`
3. 现有 Platforms 页 → 重定向到 `/settings/platforms`
4. 现有 30+ 页面路由 → 全部有对应的重定向目标
5. 登录/登出流程正常

---

### 🟡 Phase 2: 面板 SSE 对接 + 核心页面实现

**前置条件**: Phase 1 全部完成并验证通过
**并行度**: 任务 2.1 优先，完成后 2.2-2.7 可并行

#### 任务 2.1 — SuperStaffPanel SSE 完整对接

```
修改文件: web/src/components/SuperStaffPanel.vue
修改文件: web/src/stores/superStaff.ts
新增文件: web/src/components/panel/ (子组件目录)
```

**实现要求**:
1. 创建 PanelHeader / MessageList / UserMessage / ThinkingMessage / ToolCallCard / ResultCard / ErrorCard / ConfirmCard / InputArea / PanelFooter 子组件
2. 使用 `EventSource` 或 `fetch` + `ReadableStream` 连接 `POST /api/hermes/chat`
3. 处理 6 种 SSE 事件:
   - `thinking` → ThinkingMessage: 显示任务拆解列表 + 预计耗时
   - `tool_call` → ToolCallCard: 工具名称 + 参数摘要 + 实时进度条
   - `tool_result` → ResultCard (success) / ErrorCard (failed): 结果预览 + 操作按钮
   - `message` → 文本气泡（用户右对齐 / 助手左对齐）
   - `error` → ErrorCard: 错误原因 + 重试按钮
   - `done` → 标记本轮完成
4. 支持断线重连
5. 支持历史消息加载 (`GET /api/hermes/history`)
6. 支持取消当前任务 (`POST /api/hermes/cancel`)
7. 快捷指令: 在 InputArea 上方展示可横向滚动的标签，点击填充输入框
8. 全屏按钮: 点击展开为全屏模式（类似 IDE Zen Mode），标题栏保留最小化和关闭

**消息气泡样式**:
- 用户: 右对齐，`background: var(--brand-dark)`, `border-radius: 12px 12px 2px 12px`
- 助手: 左对齐，`background: rgba(255,255,255,0.05)`, `border-radius: 12px 12px 12px 2px`
- 自动滚动到底部 (新消息到来时)

**验收标准**:
- 在面板输入 "帮我检查各平台账号状态" → 面板实时展示工具调用过程
- 能看到 thinking → tool_call → tool_result → message 完整流程
- 错误场景: 输入不可执行指令 → 显示错误卡片 + 重试按钮
- 断网后恢复 → 自动重连

#### 任务 2.2 — /chat 迁移

```
修改文件: web/src/router.js
```

1. 将 `/chat` 路由从 `ChatPage` 改为重定向到 `/` + `query: { panel: 'open' }`
2. AppLayout 检测到 `panel=open` query → 自动打开 SuperStaffPanel
3. 原 `ChatPage.vue` 重命名为 `ChatPage.vue.bak`

#### 任务 2.3 — StaffOverview.vue

```
修改文件: web/src/pages/StaffOverview.vue
```

- 4 个员工状态卡片网格（2×2 布局）
- 每张卡片: 员工头像 (emoji/icon) + 角色名称 + 状态灯 (绿/灰/红) + 今日任务数 + 进度条 + 最近完成项
- 点击卡片 → 右侧抽屉展示员工详情（能力列表、近期任务、技能标签）
- 详情抽屉含 [前往工作室] 按钮 → 跳转到对应 Studio
- 数据来源: Phase 2 使用后端 `/api/agents/status` (如不存在则 mock)

**验收标准**: 4 个卡片正确展示，点击弹出详情抽屉，"前往工作室"按钮跳转正确

#### 任务 2.4 — TaskBoard.vue (Kanban)

```
修改文件: web/src/pages/TaskBoard.vue
```

- 4 列 Kanban: ready / running / blocked / done
- 每列可拖拽接收任务卡片 (使用 vuedraggable 或原生拖拽)
- 任务卡片显示: 任务名称 + 指派员工 + 进度条 + 操作按钮
- 顶部工具栏: [新建任务] 按钮 + 筛选下拉 (按员工/按状态)
- 数据来源: 对接 Hermes Kanban SQLite (API 端点待确认，Phase 2 可用 mock)

**验收标准**: 4 列展示正常，拖拽移动卡片，筛选功能正常

#### 任务 2.5 — ContentStudio.vue (3 Tab)

```
修改文件: web/src/pages/ContentStudio.vue
```

**Tab 1 — 内容生产**:
- 合并 ImageGen / VideoGen / VideoEdit / Pipeline / Documents 的功能
- 顶部: 模板卡片选择器 (口播/产品展示/知识科普/剧情/图文集)
- 中间: 生产向导 (步骤条: 选题 → 脚本 → 生成 → 预览)
- 右侧: 参数配置面板
- 底部: 生成按钮 + 进度条

**Tab 2 — 发布管理**:
- 合并 Publisher / PublishManage 的功能
- 待发布列表 (表格: 内容标题/平台/状态/排期时间/操作)
- 审核工作流: 草稿→提交→审核→通过/驳回→排期→发布
- 多平台选择器 (抖音/小红书/B站/快手/微信)

**Tab 3 — 素材库**:
- 拖拽上传区域
- 素材卡片网格 (缩略图 + AI 自动标注标签)
- 筛选: 按类型/平台/标签
- 模板库子标签: 预设模板浏览 + 预览

> **不含 Calendar/排班功能** — 排班日历在 OpsStudio Tab 1

**验收标准**: 3 个 Tab 切换正常，可在 Tab1 完成内容生成 → Tab2 提交发布全流程

#### 任务 2.6 — AcquisitionStudio.vue (4 Tab)

```
修改文件: web/src/pages/AcquisitionStudio.vue
```

**Tab 1 — 搜索截流**: 合并 VideoSearch + Intercept 功能。关键词输入 + 平台多选 + 搜索结果列表 (视频缩略图/标题/作者/互动数据/截流评分) + 一键截流按钮
**Tab 2 — 截流任务**: 评论队列列表 (待发送/已发送/失败) + 批量操作 + 速率监控仪表
**Tab 3 — 互动管理**: 合并 CommentManager + AutoReply 功能。自动回复模板管理 + DeAI 预处理预览 + 违禁词检测结果
**Tab 4 — 监听雷达**: 合并 Monitor 功能。实时评论区滚动 + 情感标签 + 线索自动标记

**验收标准**: 4 个 Tab 切换正常，各 Tab 核心功能可用

#### 任务 2.7 — ConversionStudio.vue (4 Tab) + OpsStudio.vue (3 Tab)

**ConversionStudio.vue**:
- Tab 1 线索管理: 合并 Leads。Kanban 漏斗列（新线索/待跟进/沟通中/受阻/已成交/已流失）
- Tab 2 客户跟进: 合并 Wechat + DM。微信桥接面板 + 多平台私信聚合 + AI 回复建议
- Tab 3 SOP 引擎: 合并 SOP。SOP 列表 + 编辑器 + 执行追踪
- Tab 4 知识库: 合并 Knowledge。文档上传 + 检索框 + RAG 问答结果

**OpsStudio.vue**:
- Tab 1 调度引擎: 合并 Scheduler + Calendar。Cron/Interval/Event 触发器列表 + **月/周日历视图** + 执行历史
- Tab 2 数据报告: 合并 Strategy + ABTest + ABResults。A/B 实验管理 + 策略配置 + 效果对比图表
- Tab 3 审计日志: 合并 History。操作日志列表 + 筛选 + 全链路回溯展开

**验收标准**: 各 Tab 切换正常，核心功能可用，Calendar 正确显示在 OpsStudio Tab1

---

### 🟢 Phase 3: 沉淀页 + 设置中心

**并行度**: 3.1-3.7 可全部并行

#### 任务 3.1 — ContentAssets.vue

- 只读内容资产浏览页（成片库/文案库/发布记录/效果数据 4 个子标签）
- 卡片网格展示历史内容（缩略图 + 标题 + 平台标签 + 发布时间 + 数据指标）
- 搜索 + 筛选（按平台/日期范围/内容类型）
- 点击卡片 → 右侧抽屉展示详情（完整数据 + 原内容链接）
- 数据来源: Publisher 历史记录 API

#### 任务 3.2 — CustomerAssets.vue

- 只读客户资产浏览页（线索列表/跟进记录/成交记录/转化漏斗 4 个子标签）
- 线索/客户列表 + 搜索 + 筛选（按等级/来源/日期）
- 转化漏斗可视化图表
- 数据来源: Convert Engine API

#### 任务 3.3 — SettingsPlatforms.vue

- 顶部醒目位置: **安全评分卡片**（指纹健康度 / 环境隔离状态 / 平台账号健康度，绿色/黄色/红色色标）
- 账号卡片列表: 平台图标 + 头像 + 昵称 + 登录状态 + 最后活跃时间
- 操作: 绑定新账号 / 解绑 / 扫码登录 / Session 刷新
- 合并原 Platforms.vue 功能

#### 任务 3.4 — SettingsSkills.vue

- 技能市场: 卡片网格展示可用技能包（名称/描述/评分/下载量/作者/兼容性标签）
- 搜索 + 分类筛选
- 技能详情: 点击展开 L0/L1/L2 渐进披露内容
- 一键安装: 安装后自动出现在对应工作室的"技能"下拉
- 已安装管理: 已安装技能列表 + 卸载 + 更新
- 发布技能: 上传 SKILL.md + 引用文件的表单
- agentskills.io 兼容格式

#### 任务 3.5 — SettingsTools.vue

- 合并原 Tools.vue 功能
- 工具卡片列表（名称/描述/状态/调用次数）

#### 任务 3.6 — SettingsSystem.vue

- 合并原 Settings.vue 功能
- 全局配置项（API 端点/模型选择/默认参数）

#### 任务 3.7 — SettingsBrand.vue + SettingsTeam.vue

- 合并原 OEM.vue (品牌配置: Logo/配色/名称/版权) 和 Admin.vue (团队管理: 成员列表/角色/权限)
- 路由 meta: `requiresAdmin: true`

---

### 🔵 Phase 4: 能力深化

**并行度**: 4.1-4.5 可并行

#### 任务 4.1 — 超级员工任务拆解增强

- 对接 Hermes Delegate Task: 复杂任务自动拆解为 Kanban 子卡片
- 任务拆解树可视化（父任务 → 子任务 → 代理分配 → 执行状态）
- Kanban 中展示子任务关联关系

#### 任务 4.2 — Kanban 人机协同审核节点

- 关键步骤（发布前/高价值线索）插入人工审核标志
- 审核者可在卡片上评论/驳回/放行
- 与 Publisher 审批流整合

#### 任务 4.3 — 代理 Profiles 隔离

- 4 个员工角色独立配置页面: config/SOUL/memory/skills
- 一键部署: 选择角色模板 → 自动生成完整 Profile

#### 任务 4.4 — 发布效果追踪

- 跨平台数据回采面板
- 对比分析: 按平台/内容类型/时间维度的播放/点赞/评论/转化对比

#### 任务 4.5 — 向量嵌入 Pipeline 配置

- 配置 doubao-embedding 端点
- 升级 RAG 为 FTS5 + 向量混合检索

---

### ⚪ Phase 5: 收尾

#### 任务 5.1 — Onboarding 引导

- 首次登录 → 3 步引导: (1) 绑定平台账号 → (2) 用超级员工完成第一个任务 → (3) 查看仪表盘结果
- 使用 driver.js 或类似引导库

#### 任务 5.2 — 旧文件清理

- 所有旧 `.vue` 页面重命名为 `.vue.bak`
- 保留 1 周观察无 bug → 删除

#### 任务 5.3 — 全链路回归测试

- 30+ 旧路由全部重定向正常
- 10 个新页面全部可访问
- SuperStaffPanel 在所有页面可用
- 现有后端 API 调用不受影响

---

## 四、技术参考

### 4.1 完整旧路由重定向表

```javascript
// Phase 1 即添加，确保所有旧链接不 404

// /chat 特殊处理 — Phase 1 保持不变，Phase 2 改为此:
// { path: '/chat', redirect: '/' },  // 配合 query.panel=open

{ path: '/agents',                   redirect: '/ai-staff/overview' },
{ path: '/agents/:id',               redirect: '/ai-staff/overview' },
{ path: '/pipeline/:path(.*)',       redirect: '/ai-staff/content-studio' },
{ path: '/image',                    redirect: '/ai-staff/content-studio' },
{ path: '/video',                    redirect: '/ai-staff/content-studio' },
{ path: '/video-edit',               redirect: '/ai-staff/content-studio' },
{ path: '/publisher',                redirect: '/ai-staff/content-studio' },
{ path: '/publish',                  redirect: '/ai-staff/content-studio' },
{ path: '/calendar',                 redirect: '/ai-staff/ops-studio' },
{ path: '/scheduler',                redirect: '/ai-staff/ops-studio' },
{ path: '/skills',                   redirect: '/ai-staff/overview' },
{ path: '/hub',                      redirect: '/ai-staff/overview' },
{ path: '/documents',                redirect: '/ai-staff/content-studio' },
{ path: '/capture/:path(.*)',        redirect: '/ai-staff/acquisition-studio' },
{ path: '/search',                   redirect: '/ai-staff/acquisition-studio' },
{ path: '/intercept',                redirect: '/ai-staff/acquisition-studio' },
{ path: '/comments',                 redirect: '/ai-staff/acquisition-studio' },
{ path: '/monitor',                  redirect: '/ai-staff/ops-studio' },
{ path: '/auto-reply',               redirect: '/ai-staff/acquisition-studio' },
{ path: '/ab-test',                  redirect: '/ai-staff/ops-studio' },
{ path: '/conversion/:path(.*)',     redirect: '/ai-staff/conversion-studio' },
{ path: '/leads',                    redirect: '/ai-staff/conversion-studio' },
{ path: '/wechat',                   redirect: '/ai-staff/conversion-studio' },
{ path: '/dm',                       redirect: '/ai-staff/conversion-studio' },
{ path: '/knowledge',                redirect: '/ai-staff/conversion-studio' },
{ path: '/sop',                      redirect: '/ai-staff/conversion-studio' },
{ path: '/history',                  redirect: '/ai-staff/ops-studio' },
{ path: '/strategy',                 redirect: '/ai-staff/ops-studio' },
{ path: '/ab-results',               redirect: '/ai-staff/ops-studio' },
{ path: '/security-matrix/:path(.*)',redirect: '/settings/platforms' },
{ path: '/platforms/:platform?',     redirect: '/settings/platforms' },
{ path: '/tools/:category?',         redirect: '/settings/tools' },
{ path: '/oem',                      redirect: '/settings/brand' },
{ path: '/admin',                    redirect: '/settings/team' },
{ path: '/settings-old',             redirect: '/settings/system' },
{ path: '/creative-studio/:path(.*)',redirect: '/ai-staff/:path(.*)' },
{ path: '/growth-engine/:path(.*)',  redirect: '/ai-staff/acquisition-studio' },
{ path: '/infra/:path(.*)',          redirect: '/settings/platforms' },
{ path: '/acquisition/:path(.*)',    redirect: '/ai-staff/acquisition-studio' },
```

### 4.2 关键后端接口（前端需对接）

| 接口 | 用途 | Phase |
|------|------|-------|
| `POST /api/hermes/chat` | SSE 流式对话 | Phase 2 |
| `GET /api/hermes/history` | 对话历史 | Phase 2 |
| `POST /api/hermes/cancel` | 取消任务 | Phase 2 |
| `GET /api/agents/status` | 员工状态 | Phase 2 (可 mock) |
| `GET /api/tasks` | Kanban 任务列表 | Phase 2 (可 mock) |
| `GET /api/publisher/records` | 发布记录 | Phase 3 |
| `GET /api/convert/leads` | 线索列表 | Phase 3 |
| `GET /api/skills/list` | 技能市场列表 | Phase 3 |
| `GET /api/platforms/status` | 平台账号状态 | Phase 3 |

### 4.3 Pinia Store 定义

```typescript
// stores/superStaff.ts
interface SuperStaffState {
  isOpen: boolean
  isFullscreen: boolean
  messages: Message[]
  isThinking: boolean
  currentToolCall: ToolCall | null
  activeTasks: Task[]
  sessionId: string
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting'
}

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  type: 'text' | 'thinking' | 'tool_call' | 'tool_result' | 'error' | 'confirm'
  content?: string
  toolCall?: { tool: string; params: Record<string, any>; progress: number; status: 'running' | 'completed' | 'failed' }
  result?: { tool: string; data: any; preview?: string }
  confirmRequest?: { title: string; description: string; actions: { label: string; value: string }[] }
  timestamp: number
}
```

### 4.4 UI 命名规范

| 界面位置 | 使用 | 禁止 |
|----------|------|------|
| 导航/面板/消息 | 超级员工 | Hermes |
| 员工卡片/工作室 | 内容专员 / 获客专员 / 转化专员 / 运营专员 | Agent / Pipeline |
| 一级导航 | 内容资产 / 客户资产 | 内容工厂 / 营销拓客 |
| 代码变量/API | 保留 hermesStore、hermes_chat.py 等 | — |

### 4.5 视觉 Token

| Token | 值 | 用途 |
|------|-----|------|
| 青色主色 | `#00d4ff` → `#0099cc` | FAB 按钮渐变、面板边框发光 |
| 面板宽度 | 420px | SuperStaffPanel 默认宽度 |
| FAB 尺寸 | 56px | 悬浮按钮 |
| 毛玻璃 | `backdrop-filter: blur(12px)` | 面板背景 |
| 脉冲动画 | `box-shadow 0→15px→0` | FAB 呼吸效果 |
| 面板动画 | `transform 300ms` | 面板滑入滑出 |

---

## 五、并行执行指南

### 5.1 依赖关系

```
Phase 1:
  1.1 (router+AppLayout) ── 必须先完成
    ├── 1.2 (页面空壳) ── 可与 1.3/1.4 并行
    ├── 1.3 (SuperStaff 组件) ── 可与 1.2/1.4 并行
    ├── 1.4 (Dashboard) ── 可与 1.2/1.3 并行
    ├── 1.5 (路由验证) ── 依赖 1.1+1.2 完成
    └── 1.6 (功能验证) ── 依赖 1.1+1.2+1.3 完成

Phase 2:
  2.1 (面板 SSE) ── 优先
    ├── 2.2 (/chat 迁移) ── 依赖 2.1
    ├── 2.3 (StaffOverview) ── 可与 2.4-2.7 并行
    ├── 2.4 (TaskBoard) ── 可与 2.3/2.5-2.7 并行
    ├── 2.5 (ContentStudio) ── 可与 2.3/2.4/2.6/2.7 并行
    ├── 2.6 (AcquisitionStudio) ── 可与 2.3/2.4/2.5/2.7 并行
    └── 2.7 (Conversion+Ops) ── 可与 2.3-2.6 并行

Phase 3: 全部并行（3.1-3.7）
Phase 4: 全部并行（4.1-4.5）
Phase 5: 5.2 需在 5.3 之前
```

### 5.2 每个 Agent 的交付物

每个任务完成后，agent 应输出:
1. 修改/新建的文件列表
2. 自检: 该任务的验收标准逐项确认
3. 已知问题: 任何未解决的 edge case

---

## 六、关键约束与注意事项

### ⚠️ 绝对不能做的事
1. **不要删除任何旧 `.vue` 文件** — Phase 5 之前只能重命名为 `.bak`
2. **不要在 Phase 1 修改 `/chat` 路由** — 保持 ChatPage 正常服务
3. **不要修改后端 API** — 前端重构只改前端，后端接口不变
4. **不要修改 `hermes.yaml` 或 MCP 服务器** — 这些是后端基础设施
5. **不要引入新的 npm 依赖** 除非必要（vuedraggable 可用于 Kanban 拖拽，driver.js 用于 Onboarding）

### ⚠️ 需要特别注意的事
1. **CSS 变量**: szyg 已有 dark/light 主题系统 (`web/src/style.css`, `web/src/tech-theme.css`)，新组件必须兼容两套主题
2. **响应式**: 所有新页面需在 1280px-1920px 正常显示
3. **路由懒加载**: 所有新页面使用 `() => import(...)` 语法
4. **JWT 认证**: 所有新路由添加 `meta: { requiresAuth: true }`
5. **SSE 连接管理**: 页面切换时正确关闭 EventSource，避免连接泄漏

---

*本提示词基于 szyg产品功能融合设计.md v2.0 + szyg前端实施规范.md v2.0 编写*
*日期: 2026-06-28*
