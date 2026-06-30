# szyg 前端实施规范 v2.0

> **定位**: 开发者实施规范（SSOT 配套文档）。定义"怎么做"——路由表、组件命名、页面映射、SuperStaffPanel 技术规格、Phase 细节。
> **产品设计**: 见 `szyg产品功能融合设计.md`（定义"做什么"和"为什么"）
> **已废弃**: `szyg前端重构参考文档.md`（内容已合并至本文）
> **日期**: 2026-06-28

---

## 一、新路由表（完整）

### 1.1 主导航（5 项）

```
/dashboard                          → Dashboard.vue
/ai-staff                           → AiStaff.vue (壳，含 <router-view>)
  /ai-staff/overview                → StaffOverview.vue
  /ai-staff/tasks                   → TaskBoard.vue
  /ai-staff/content-studio          → ContentStudio.vue
  /ai-staff/acquisition-studio      → AcquisitionStudio.vue
  /ai-staff/conversion-studio       → ConversionStudio.vue
  /ai-staff/ops-studio              → OpsStudio.vue
/assets                             → ContentAssets.vue
/crm                                → CustomerAssets.vue
/settings                           → Settings.vue (壳，含 <router-view>)
  /settings/platforms               → SettingsPlatforms.vue
  /settings/skills                  → SettingsSkills.vue
  /settings/tools                   → SettingsTools.vue
  /settings/system                  → SettingsSystem.vue
  /settings/brand                   → SettingsBrand.vue (admin only)
  /settings/team                    → SettingsTeam.vue (admin only)
```

### 1.2 超级员工面板（非路由，全局组件）

| 组件 | 路径 | 说明 |
|------|------|------|
| `SuperStaffButton.vue` | `web/src/components/SuperStaffButton.vue` | 全局悬浮按钮，所有页面可见 |
| `SuperStaffPanel.vue` | `web/src/components/SuperStaffPanel.vue` | 右侧滑出对话面板，可展开全屏 |

### 1.3 旧路由重定向

```javascript
// ═══════════════════════════════════════════════════════════════
// Gen 1-3 旧路由 → 新路由（保留 6 个月后移除）
// ═══════════════════════════════════════════════════════════════

// ── /chat 特殊处理 ──
// Phase 1: 保持 /chat → ChatPage (原页面正常服务)
// Phase 2: SuperStaffPanel SSE 对接完成后
//          /chat → redirect to /?panel=open (仪表盘 + 自动打开面板)

// ── Pipeline / 内容工厂 ──
{ path: '/pipeline/:path(.*)',       redirect: '/ai-staff/content-studio' },
{ path: '/agents',                   redirect: '/ai-staff/overview' },
{ path: '/agents/:id',               redirect: '/ai-staff/overview' },
{ path: '/chat',                     redirect: '/ai-staff/overview' },    // Phase 2 启用
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

// ── Capture / 公域拓客 ──
{ path: '/capture/:path(.*)',        redirect: '/ai-staff/acquisition-studio' },
{ path: '/search',                   redirect: '/ai-staff/acquisition-studio' },
{ path: '/intercept',                redirect: '/ai-staff/acquisition-studio' },
{ path: '/comments',                 redirect: '/ai-staff/acquisition-studio' },
{ path: '/monitor',                  redirect: '/ai-staff/ops-studio' },
{ path: '/auto-reply',               redirect: '/ai-staff/acquisition-studio' },
{ path: '/ab-test',                  redirect: '/ai-staff/ops-studio' },

// ── Conversion / 私域转化 ──
{ path: '/conversion/:path(.*)',     redirect: '/ai-staff/conversion-studio' },
{ path: '/leads',                    redirect: '/ai-staff/conversion-studio' },
{ path: '/wechat',                   redirect: '/ai-staff/conversion-studio' },
{ path: '/dm',                       redirect: '/ai-staff/conversion-studio' },
{ path: '/knowledge',                redirect: '/ai-staff/conversion-studio' },
{ path: '/sop',                      redirect: '/ai-staff/conversion-studio' },
{ path: '/history',                  redirect: '/ai-staff/ops-studio' },
{ path: '/strategy',                 redirect: '/ai-staff/ops-studio' },
{ path: '/ab-results',               redirect: '/ai-staff/ops-studio' },

// ── Security Matrix / 账号基建 ──
{ path: '/security-matrix/:path(.*)',redirect: '/settings/platforms' },
{ path: '/platforms/:platform?',     redirect: '/settings/platforms' },
{ path: '/tools/:category?',         redirect: '/settings/tools' },
{ path: '/oem',                      redirect: '/settings/brand' },
{ path: '/admin',                    redirect: '/settings/team' },
{ path: '/settings-old',             redirect: '/settings/system' },

// ── 中间代路由 ──
{ path: '/creative-studio/:path(.*)',redirect: '/ai-staff/:path(.*)' },
{ path: '/growth-engine/:path(.*)',  redirect: '/ai-staff/acquisition-studio' },
{ path: '/infra/:path(.*)',          redirect: '/settings/platforms' },
{ path: '/acquisition/:path(.*)',    redirect: '/ai-staff/acquisition-studio' },
```

---

## 二、旧页面 → 新页面合并映射

### 2.1 操作工作台（4 个 Studio 替代 22 个旧页面）

| 旧页面 | 新归属 | 合并方式 |
|--------|--------|---------|
| `Agents.vue` / `AgentDetail.vue` / `Hub.vue` | `StaffOverview.vue` | 员工卡片网格 + 详情右侧抽屉 |
| `ImageGen.vue` / `VideoGen.vue` / `VideoEdit.vue` / `Pipeline.vue` | `ContentStudio.vue` Tab 1 | 内容生产 |
| `Publisher.vue` / `PublishManage.vue` | `ContentStudio.vue` Tab 2 | 发布管理 |
| 素材上传/管理（新功能） | `ContentStudio.vue` Tab 3 | 素材库 |
| `VideoSearch.vue` | `AcquisitionStudio.vue` Tab 1 | 搜索截流 |
| `Intercept.vue` | `AcquisitionStudio.vue` Tab 2 | 截流任务 |
| `CommentManager.vue` / `AutoReply.vue` | `AcquisitionStudio.vue` Tab 3 | 互动管理 |
| `Monitor.vue` | `AcquisitionStudio.vue` Tab 4 | 监听雷达 |
| `Leads.vue` | `ConversionStudio.vue` Tab 1 | 线索管理 |
| `Wechat.vue` / `DM.vue` | `ConversionStudio.vue` Tab 2 | 客户跟进 |
| `SOP.vue` | `ConversionStudio.vue` Tab 3 | SOP 引擎 |
| `Knowledge.vue` | `ConversionStudio.vue` Tab 4 | 知识库 |
| `Scheduler.vue` + `Calendar.vue` | `OpsStudio.vue` Tab 1 | 调度引擎 + 排班日历 |
| `Strategy.vue` + `ABTest.vue` + `ABResults.vue` | `OpsStudio.vue` Tab 2 | 数据报告 |
| `History.vue` | `OpsStudio.vue` Tab 3 | 审计日志 |

**注意**: ContentStudio 只有 3 个 Tab（不含 Calendar）。Calendar 归属 OpsStudio Tab 1。

### 2.2 沉淀页（替代 0 个旧页面，全新）

| 新页面 | 内容 | 说明 |
|--------|------|------|
| `ContentAssets.vue` | 成片库 / 文案库 / 发布记录 / 效果数据 | 只读检索，操作在 ContentStudio 完成 |
| `CustomerAssets.vue` | 线索列表 / 跟进记录 / 成交记录 / 转化漏斗 | 只读检索，操作在 ConversionStudio 完成 |

### 2.3 设置页

| 旧页面 | 新归属 | 说明 |
|--------|--------|------|
| `Platforms.vue` | `SettingsPlatforms.vue` | 平台账号 + 安全评分卡片 |
| `Skills.vue`（旧） | **升级为 `SettingsSkills.vue`** | 技能市场（浏览/搜索/安装/发布） |
| `Tools.vue` | `SettingsTools.vue` | 工具管理 |
| `Settings.vue`（旧） | `SettingsSystem.vue` | 系统配置 |
| `OEM.vue` | `SettingsBrand.vue` | 品牌配置（admin only） |
| `Admin.vue` | `SettingsTeam.vue` | 团队管理（admin only） |

### 2.4 全局面板

| 旧页面 | 新归属 | 说明 |
|--------|--------|------|
| `Chat.vue` | **升级为 `SuperStaffPanel.vue`** | 从内嵌聊天页 → 全局面板；`Documents.vue` 功能嵌入 ContentStudio Tab 1 |

**结果**: 34 个旧页面 → **10 个核心页面**（Dashboard + AiStaff 壳 + 4 Studio + 2 Assets + 2 Settings）+ SuperStaffPanel 全局面板

---

## 三、组件命名规范（PascalCase）

### 3.1 页面组件

| 组件 | 路径 |
|------|------|
| `Dashboard.vue` | `web/src/pages/Dashboard.vue` |
| `AiStaff.vue` | `web/src/pages/AiStaff.vue` |
| `StaffOverview.vue` | `web/src/pages/StaffOverview.vue` |
| `TaskBoard.vue` | `web/src/pages/TaskBoard.vue` |
| `ContentStudio.vue` | `web/src/pages/ContentStudio.vue` |
| `AcquisitionStudio.vue` | `web/src/pages/AcquisitionStudio.vue` |
| `ConversionStudio.vue` | `web/src/pages/ConversionStudio.vue` |
| `OpsStudio.vue` | `web/src/pages/OpsStudio.vue` |
| `ContentAssets.vue` | `web/src/pages/ContentAssets.vue` |
| `CustomerAssets.vue` | `web/src/pages/CustomerAssets.vue` |
| `Settings.vue` | `web/src/pages/Settings.vue` |
| `SettingsPlatforms.vue` | `web/src/pages/SettingsPlatforms.vue` |
| `SettingsSkills.vue` | `web/src/pages/SettingsSkills.vue` |
| `SettingsTools.vue` | `web/src/pages/SettingsTools.vue` |
| `SettingsSystem.vue` | `web/src/pages/SettingsSystem.vue` |
| `SettingsBrand.vue` | `web/src/pages/SettingsBrand.vue` |
| `SettingsTeam.vue` | `web/src/pages/SettingsTeam.vue` |

### 3.2 全局组件

| 组件 | 路径 | 说明 |
|------|------|------|
| `SuperStaffButton.vue` | `web/src/components/SuperStaffButton.vue` | 悬浮 FAB 按钮 |
| `SuperStaffPanel.vue` | `web/src/components/SuperStaffPanel.vue` | 右侧滑出面板 |
| `StaffCard.vue` | `web/src/components/StaffCard.vue` | 员工状态卡片（复用） |
| `TaskCard.vue` | `web/src/components/TaskCard.vue` | 任务卡片（Kanban 用） |
| `ToolCallCard.vue` | `web/src/components/ToolCallCard.vue` | 工具调用进度卡片（SuperStaffPanel 用） |

---

## 四、SuperStaffPanel 技术规格

### 4.1 组件架构

```
SuperStaffButton.vue         ← 悬浮按钮，挂载在 AppLayout 中
  └── 点击 → emit('toggle-panel')

SuperStaffPanel.vue          ← 右侧滑出面板
  ├── PanelHeader.vue        ← 头像 + "超级员工" + 状态灯 + 全屏按钮 + 关闭
  ├── MessageList.vue        ← 消息滚动容器
  │   ├── UserMessage.vue    ← 右对齐气泡
  │   ├── ThinkingMessage.vue ← "正在分析任务…" 任务拆解动画
  │   ├── ToolCallCard.vue   ← 工具调用进度卡片（核心）
  │   ├── ResultCard.vue     ← 执行结果（绿色边框 + 预览 + 操作按钮）
  │   ├── ErrorCard.vue      ← 错误（红色边框 + 重试按钮）
  │   └── ConfirmCard.vue    ← 确认请求（操作按钮）
  ├── InputArea.vue          ← 输入框 + 发送 + 快捷指令标签
  └── PanelFooter.vue        ← 模型信息 + 网络状态
```

### 4.2 视觉规范

| 元素 | 规范 |
|------|------|
| 悬浮按钮 | 56px 圆形，青色渐变背景，脉冲动画，位置: 页面右下角 bottom: 24px, right: 24px |
| 面板宽度 | 420px（桌面默认）/ 全屏（"展开"按钮触发） |
| 面板高度 | 100vh |
| 面板背景 | 半透明深色 + 毛玻璃（`backdrop-filter: blur(12px)`） |
| 边框 | 左侧 1px 青色发光（`rgba(0, 212, 255, 0.3)`），全屏模式无边框 |
| 用户消息 | 右对齐，深色气泡，`border-radius: 12px 12px 2px 12px` |
| 助手消息 | 左对齐，半透明背景，`border-radius: 12px 12px 12px 2px` |
| 工具调用卡片 | 带边框青色卡片，顶部进度条 |
| 结果卡片 | 绿色左边框，含缩略图预览 |
| 错误卡片 | 红色左边框，含重试按钮 |

### 4.3 SSE 事件类型

| event | data | 前端渲染组件 |
|-------|------|------------|
| `thinking` | `{ task_breakdown: [{ title, agent, estimated_time }] }` | `ThinkingMessage.vue` |
| `tool_call` | `{ tool, params, progress: 0.5 }` | `ToolCallCard.vue` |
| `tool_result` | `{ tool, result, status: 'success'\|'failed' }` | `ResultCard.vue` / `ErrorCard.vue` |
| `message` | `{ content, role: 'assistant' }` | 文本气泡 |
| `error` | `{ code, message }` | `ErrorCard.vue` + 重试按钮 |
| `done` | `{}` | 标记本轮完成 |

### 4.4 后端接口

```typescript
// 发送消息（SSE 流式）
POST /api/hermes/chat
Body: { message: string, session_id?: string }
Response: SSE stream (6 种事件类型)

// 获取历史
GET /api/hermes/history?session_id=xxx&limit=50

// 取消当前任务
POST /api/hermes/cancel
Body: { session_id: string }
```

### 4.5 Pinia Store

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
  toolCall?: {
    tool: string
    params: Record<string, any>
    progress: number    // 0-1
    status: 'running' | 'completed' | 'failed'
  }
  result?: {
    tool: string
    data: any
    preview?: string
  }
  confirmRequest?: {
    title: string
    description: string
    actions: { label: string; value: string }[]
  }
  timestamp: number
}
```

### 4.6 `/chat` 迁移策略

```
Phase 1: /chat 路由保持不变，服务原 ChatPage.vue
Phase 2: SuperStaffPanel SSE 对接完成并测试通过后:
  1. 将 /chat 重定向从 ChatPage 改为 { path: '/', query: { panel: 'open' } }
  2. AppLayout 检测 query.panel === 'open' → 自动展开 SuperStaffPanel
  3. 保留 ChatPage.vue 为 .bak 1 周后删除
```

---

## 五、各工作室 Tab 设计

### ContentStudio（3 Tab）

| Tab | 标题 | 功能 | 合并的旧页面 |
|-----|------|------|------------|
| 1 | 内容生产 | AI 生成（文/图/视频）、智能剪辑、脚本编辑器、流水线 DAG 视图、文档工具 | ImageGen / VideoGen / VideoEdit / Pipeline / Documents |
| 2 | 发布管理 | 多平台分发、审核工作流、发布状态追踪 | Publisher / PublishManage |
| 3 | 素材库 | 上传、AI 标注、模板库浏览、品牌风格管理 | 新功能 |

> **不含 Calendar**。Calendar 归属 OpsStudio Tab 1。

### AcquisitionStudio（4 Tab）

| Tab | 标题 | 功能 | 合并的旧页面 |
|-----|------|------|------------|
| 1 | 搜索截流 | 关键词配置、多平台搜索、5 维评分结果列表 | VideoSearch |
| 2 | 截流任务 | 评论队列、批量发送、速率监控 | Intercept |
| 3 | 互动管理 | 自动回复配置、DeAI 去模板化、预检结果 | CommentManager / AutoReply |
| 4 | 监听雷达 | 实时评论区流、情感标签、线索自动发现 | Monitor |

### ConversionStudio（4 Tab）

| Tab | 标题 | 功能 | 合并的旧页面 |
|-----|------|------|------------|
| 1 | 线索管理 | Kanban 漏斗看板、4 维评分、A/B/C/D 分级 | Leads |
| 2 | 客户跟进 | 微信桥接、多平台私信聚合、AI 回复建议 | Wechat / DM |
| 3 | SOP 引擎 | SOP 创建/编辑/版本管理、执行追踪 | SOP |
| 4 | 知识库 | 文档摄入、FTS5 检索、RAG 问答 | Knowledge |

### OpsStudio（3 Tab）

| Tab | 标题 | 功能 | 合并的旧页面 |
|-----|------|------|------------|
| 1 | 调度引擎 | Cron/Interval/Event 触发器、**排班日历**、执行历史 | Scheduler / Calendar |
| 2 | 数据报告 | A/B 实验管理、策略配置、效果对比、统计显著性 | Strategy / ABTest / ABResults |
| 3 | 审计日志 | 操作历史、异常记录、全链路回溯 | History |

---

## 六、设置子页设计

### SettingsPlatforms

- 账号卡片列表（平台图标 + 头像 + 昵称 + 登录状态 + 最后活跃时间）
- **安全评分卡片**（顶部醒目位置）：指纹健康度 / 环境隔离状态 / 各平台账号健康度
- 账号操作：绑定/解绑/扫码登录/Session 刷新

### SettingsSkills

- 卡片式技能浏览器（分类筛选 + 搜索 + 评分 + 下载量 + 兼容性标签）
- 技能详情页（L0/L1/L2 渐进披露）
- 一键安装 → 安装后自动出现在对应工作室的"技能"标签
- 发布技能包（上传 SKILL.md + 引用文件）
- 已安装技能管理

### SettingsTools / SettingsSystem / SettingsBrand / SettingsTeam

- 沿用现有功能，重新组织布局
- SettingsBrand 和 SettingsTeam 标记 `requiresAdmin: true`

---

## 七、实施 Phase 细节

### Phase 1: 骨架路由 + 面板空壳（1-2 周）

| # | 任务 | 产出 | 验收标准 |
|---|------|------|---------|
| 1 | 重写 `router.js` | 新路由表 + 完整旧路由重定向 | 所有新路径可访问（显示空壳），所有旧路径正确重定向 |
| 2 | 重写 `AppLayout.vue` | 5 项顶部导航 + `<router-view>` + SuperStaffButton 挂载 | 导航切换正常，FAB 显示在所有页面 |
| 3 | 新建所有新页面空壳 | 10 个页面 .vue 文件 + 6 个设置子页 | 每个页面显示占位内容 |
| 4 | 新建 `SuperStaffButton.vue` + `SuperStaffPanel.vue` | FAB 按钮（56px 脉冲）+ 右侧面板（420px 毛玻璃，可展开/收起）+ Pinia Store | 点击 FAB → 面板滑出；点击面板外 → 关闭；点击全屏按钮 → 全屏 |
| 5 | **保留 `/chat` 路由** | ChatPage 原样服务 | 现有对话功能不受影响 |
| 6 | 重写 `Dashboard.vue` 布局 | 快捷输入框 + 员工状态卡片行 + Kanban 空壳 + 今日数据卡片 | 布局正确，数据可为 mock |

### Phase 2: 面板 SSE 对接 + 核心页面（2-3 周）

| # | 任务 | 产出 | 验收标准 |
|---|------|------|---------|
| 7 | SuperStaffPanel SSE 对接 | EventSource 连接 `hermes_chat.py`，6 种事件渲染 | 输入"帮我检查平台状态"→ 面板实时展示工具调用过程 |
| 8 | `/chat` 迁移 | `/chat` → 重定向到 `/?panel=open` | 旧 Chat 链接自动打开新面板 |
| 9 | `StaffOverview.vue` | 4 员工卡片 + 快捷任务下拉 | 每个卡片显示状态/今日任务数/进度 |
| 10 | `TaskBoard.vue` | Kanban 4 列（ready/running/blocked/done） | 对接 Hermes Kanban SQLite |
| 11 | `ContentStudio.vue` (3 Tab) | 内容生产 / 发布管理 / 素材库 | 在工作室完成"生成→发布"全流程，不跳页 |
| 12 | `AcquisitionStudio.vue` (4 Tab) | 搜索截流 / 截流任务 / 互动管理 / 监听雷达 | 各 Tab 功能可用 |
| 13 | `ConversionStudio.vue` (4 Tab) | 线索管理 / 客户跟进 / SOP 引擎 / 知识库 | 各 Tab 功能可用 |
| 14 | `OpsStudio.vue` (3 Tab) | 调度引擎+日历 / 数据报告 / 审计日志 | Calendar 在调度 Tab 内可用 |

### Phase 3: 沉淀页 + 设置中心（1-2 周）

| # | 任务 | 产出 | 验收标准 |
|---|------|------|---------|
| 15 | `ContentAssets.vue` | 成片库/文案库/发布记录/效果数据 | 可搜索历史内容，不可编辑（只读） |
| 16 | `CustomerAssets.vue` | 线索列表/跟进记录/成交记录/转化漏斗 | 可搜索历史客户，不可编辑（只读） |
| 17 | `SettingsPlatforms.vue` | 平台账号列表 + **安全评分卡片** | 安全评分卡片醒目展示 |
| 18 | `SettingsSkills.vue` | 技能市场：浏览/搜索/安装/发布 | agentskills.io 兼容 |
| 19 | `SettingsTools.vue` + `SettingsSystem.vue` | 工具管理 + 全局配置 | 功能可用 |
| 20 | `SettingsBrand.vue` + `SettingsTeam.vue` | 品牌配置 + 团队管理 | admin 权限控制正常 |

### Phase 4: 能力深化（2-3 周）

| # | 任务 |
|---|------|
| 21 | 超级员工任务拆解增强（对接 Hermes Delegate Task） |
| 22 | Kanban 人机协同审核节点（comment/unblock） |
| 23 | 代理 Profiles 隔离（4 角色独立 config/SOUL/memory/skills） |
| 24 | 发布效果追踪（跨平台数据回采 + 对比分析面板） |
| 25 | 向量嵌入 Pipeline 配置（embedding_dim: 768 → 混合检索） |

### Phase 5: 收尾（1 周）

| # | 任务 |
|---|------|
| 26 | Onboarding 引导流程 |
| 27 | 旧 `.vue` → `.bak`，保留 1 周后删除 |
| 28 | 全链路回归测试 |

---

## 八、UI 命名规范

| 界面位置 | 应使用 | 不应使用 |
|----------|--------|----------|
| 顶部导航 | 仪表盘 \| AI员工 \| 内容资产 \| 客户资产 \| 系统设置 | 指挥中心 \| 内容工厂 \| 营销拓客 \| 账号基建 |
| FAB / 面板 / 消息 | 超级员工 | Hermes |
| 员工卡片 | 内容专员 / 获客专员 / 转化专员 / 运营专员 | 内容Agent / 获客Agent |
| 工作室标题 | 内容专员工作室 / 获客专员工作室 / 转化专员工作室 / 运营专员工作室 | ContentStudio |
| 代码/接口 | 保留 `hermes_chat.py`、`hermesStore`、`/api/hermes/*` | — |
| 沉淀页 | 内容资产 / 客户资产 | 内容工厂 / 营销拓客 |

---

*本文档为 szyg 前端实施的开发者规范（SSOT 配套文档）v2.0*
*产品设计见 `szyg产品功能融合设计.md`*
