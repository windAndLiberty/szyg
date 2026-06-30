> ⚠️ **本文档已废弃（2026-06-28）**
> 内容已合并至 `szyg前端实施规范.md`（开发者实施规范，路由表/组件命名/页面映射/SuperStaffPanel 技术规格/Phase 细节）。
> 产品级设计见 `szyg产品功能融合设计.md`。
>
> **不再更新本文档。所有新决策请更新上述两份 SSOT 文档。**

---

# szyg 前端重构参考文档

> 本文档是给开发者的架构参考，不是给 AI 的复制粘贴提示词。包含新路由表、页面映射、命名规范、超级员工面板技术要点。配合 `szyg前端重构计划.md` 使用。

---

## 一、新路由表

### 1.1 主导航（顶部4模块）

| 路径 | 页面组件 | 说明 |
|------|----------|------|
| `/dashboard` | `Dashboard.vue` | 今日指挥台：员工状态 + 超级员工输入框 + 任务队列 + 数据速览 |
| `/ai-staff` | `AiStaff.vue`（壳） | AI员工中心，含子路由视图 |
| `/ai-staff/overview` | `StaffOverview.vue` | 4个员工状态卡片网格 + 快捷任务 |
| `/ai-staff/tasks` | `TaskBoard.vue` | 任务看板（Kanban）：待执行/执行中/待验收/已完成 |
| `/ai-staff/content-studio` | `ContentStudio.vue` | 内容专员工作室：生产/发布/素材/排班 4个tab |
| `/ai-staff/acquisition-studio` | `AcquisitionStudio.vue` | 获客专员工作室：搜索/截流/互动/监控 4个tab |
| `/ai-staff/conversion-studio` | `ConversionStudio.vue` | 转化专员工作室：线索/跟进/SOP/知识库 4个tab |
| `/ai-staff/ops-studio` | `OpsStudio.vue` | 运营专员工作室：调度/监控/报告/审计 4个tab |
| `/content-factory` | `ContentFactory.vue` | 内容工厂：素材库、成片库、文案库、发布记录（结果沉淀） |
| `/marketing` | `Marketing.vue` | 营销拓客：线索列表、客户跟进、成交记录（结果沉淀） |
| `/settings` | `Settings.vue`（壳） | 系统设置，含子路由 |
| `/settings/platforms` | `SettingsPlatforms.vue` | 平台账号管理 |
| `/settings/tools` | `SettingsTools.vue` | 工具市场 |
| `/settings/system` | `SettingsSystem.vue` | 系统配置 |
| `/settings/brand` | `SettingsBrand.vue` | 品牌配置（admin only） |
| `/settings/team` | `SettingsTeam.vue` | 团队管理（admin only） |
| `/settings/announcements` | `SettingsAnnouncements.vue` | 公告管理（admin only） |

### 1.2 超级员工面板（非路由，全局组件）

| 组件 | 路径 | 说明 |
|------|------|------|
| `SuperStaffButton.vue` | `web/src/components/SuperStaffButton.vue` | 全局悬浮按钮（所有页面可见） |
| `SuperStaffPanel.vue` | `web/src/components/SuperStaffPanel.vue` | 右侧滑出对话面板 |

### 1.3 旧路由重定向（保留兼容）

```javascript
// 所有旧路由 → 新路由，保留6个月后再移除
{ path: '/agents', redirect: '/ai-staff/overview' },
{ path: '/agents/:id', redirect: to => ({ path: `/ai-staff/overview` }) },
{ path: '/pipeline/:path(.*)', redirect: '/ai-staff/content-studio' },
{ path: '/capture/:path(.*)', redirect: '/ai-staff/acquisition-studio' },
{ path: '/conversion/:path(.*)', redirect: '/ai-staff/conversion-studio' },
{ path: '/chat', redirect: '/ai-staff/overview' },  // 旧Chat入口引导到AI员工
{ path: '/image', redirect: '/ai-staff/content-studio' },
{ path: '/video', redirect: '/ai-staff/content-studio' },
{ path: '/video-edit', redirect: '/ai-staff/content-studio' },
{ path: '/publisher', redirect: '/ai-staff/content-studio' },
{ path: '/publish', redirect: '/ai-staff/content-studio' },
{ path: '/calendar', redirect: '/ai-staff/content-studio' },
{ path: '/scheduler', redirect: '/ai-staff/ops-studio' },
{ path: '/skills', redirect: '/ai-staff/overview' },
{ path: '/hub', redirect: '/ai-staff/overview' },
{ path: '/documents', redirect: '/ai-staff/content-studio' },
{ path: '/search', redirect: '/ai-staff/acquisition-studio' },
{ path: '/intercept', redirect: '/ai-staff/acquisition-studio' },
{ path: '/comments', redirect: '/ai-staff/acquisition-studio' },
{ path: '/monitor', redirect: '/ai-staff/ops-studio' },
{ path: '/auto-reply', redirect: '/ai-staff/acquisition-studio' },
{ path: '/ab-test', redirect: '/ai-staff/ops-studio' },
{ path: '/leads', redirect: '/ai-staff/conversion-studio' },
{ path: '/wechat', redirect: '/ai-staff/conversion-studio' },
{ path: '/dm', redirect: '/ai-staff/conversion-studio' },
{ path: '/knowledge', redirect: '/ai-staff/conversion-studio' },
{ path: '/sop', redirect: '/ai-staff/conversion-studio' },
{ path: '/history', redirect: '/ai-staff/ops-studio' },
{ path: '/strategy', redirect: '/ai-staff/ops-studio' },
{ path: '/ab-results', redirect: '/ai-staff/ops-studio' },
{ path: '/platforms/:platform?', redirect: '/settings/platforms' },
{ path: '/tools/:category?', redirect: '/settings/tools' },
{ path: '/settings-old', redirect: '/settings/system' },
{ path: '/oem', redirect: '/settings/brand' },
{ path: '/admin', redirect: '/settings/team' },
// 中间代路由重定向
{ path: '/security-matrix/:path(.*)', redirect: '/settings/:path(.*)' },
{ path: '/creative-studio/:path(.*)', redirect: '/ai-staff/:path(.*)' },
{ path: '/growth-engine/:path(.*)', redirect: '/ai-staff/acquisition-studio' },
{ path: '/infra/:path(.*)', redirect: '/settings/:path(.*)' },
```

---

## 二、旧页面 → 新页面合并映射

| 旧页面 | 新归属 | 处理方式 |
|--------|--------|----------|
| `Agents.vue` / `AgentDetail.vue` | `AiStaff.vue` → `StaffOverview.vue` | 员工卡片网格，详情用右侧抽屉 |
| `Chat.vue` | **升级为 `SuperStaffPanel.vue`** | 从简单聊天 → 全能力工具调用对话面板 |
| `ImageGen.vue` | `ContentStudio.vue` → Tab 1 | 嵌入「AI生成」子标签 |
| `VideoGen.vue` | `ContentStudio.vue` → Tab 1 | 同上 |
| `VideoEdit.vue` | `ContentStudio.vue` → Tab 1 | 同上 |
| `Pipeline.vue` | `ContentStudio.vue` → Tab 1 | 合并为「内容生产向导」 |
| `Publisher.vue` | `ContentStudio.vue` → Tab 2 | 合并为「发布管理」 |
| `PublishManage.vue` | `ContentStudio.vue` → Tab 2 | 同上 |
| `Calendar.vue` | `ContentStudio.vue` → Tab 4 | 合并为「排班调度」 |
| `Scheduler.vue` | `OpsStudio.vue` → Tab 1 | 合并为「调度引擎」 |
| `Skills.vue` | `AiStaff.vue` → 各员工详情 | 取消独立页面，技能标签嵌入员工卡片 |
| `Hub.vue` | `AiStaff.vue` → 员工概览 | 取消独立页面，导航功能融入 |
| `Documents.vue` | `ContentStudio.vue` → Tab 1 | 作为「办公技能」子项 |
| `VideoSearch.vue` | `AcquisitionStudio.vue` → Tab 1 | 合并为「搜索截流」 |
| `Intercept.vue` | `AcquisitionStudio.vue` → Tab 2 | 合并为「截流任务」 |
| `CommentManager.vue` | `AcquisitionStudio.vue` → Tab 3 | 合并为「互动管理」 |
| `Monitor.vue` | `OpsStudio.vue` → Tab 2 | 合并为「系统监控」 |
| `AutoReply.vue` | `AcquisitionStudio.vue` → Tab 3 | 合并为「自动回复配置」 |
| `ABTest.vue` | `OpsStudio.vue` → Tab 3 | 合并为「数据报告」中的实验模块 |
| `Leads.vue` | `ConversionStudio.vue` → Tab 1 | 合并为「线索管理」 |
| `Wechat.vue` | `ConversionStudio.vue` → Tab 2 | 合并为「客户跟进」 |
| `DM.vue` | `ConversionStudio.vue` → Tab 2 | 同上 |
| `SOP.vue` | `ConversionStudio.vue` → Tab 3 | 合并为「SOP引擎」 |
| `Knowledge.vue` | `ConversionStudio.vue` → Tab 4 | 合并为「知识库」 |
| `History.vue` | `OpsStudio.vue` → Tab 4 | 合并为「审计日志」 |
| `Strategy.vue` | `OpsStudio.vue` → Tab 3 | 合并为「数据报告」中的策略模块 |
| `ABResults.vue` | `OpsStudio.vue` → Tab 3 | 同上 |
| `Platforms.vue` | `Settings.vue` → `/settings/platforms` | 保留内容，嵌入设置页 |
| `Tools.vue` | `Settings.vue` → `/settings/tools` | 同上 |
| `Settings.vue`（旧） | `Settings.vue` → `/settings/system` | 同上 |
| `OEM.vue` | `Settings.vue` → `/settings/brand` | 同上 |
| `Admin.vue` | `Settings.vue` → `/settings/team` | 同上 |

**结果：30+个独立页面 → 8个核心页面 + 全局面板 + 设置子页**

---

## 三、命名规范

### 3.1 路由路径

```
/dashboard              ← 仪表盘
/ai-staff               ← AI员工（壳）
/ai-staff/overview      ← 员工概览
/ai-staff/tasks         ← 任务工作台
/ai-staff/content-studio    ← 内容专员工作室
/ai-staff/acquisition-studio ← 获客专员工作室
/ai-staff/conversion-studio   ← 转化专员工作室
/ai-staff/ops-studio          ← 运营专员工作室
/content-factory        ← 内容工厂
/marketing              ← 营销拓客
/settings               ← 系统设置（壳）
/settings/platforms     ← 平台账号
/settings/tools         ← 工具市场
/settings/system        ← 系统配置
/settings/brand         ← 品牌配置
/settings/team          ← 团队管理
/settings/announcements ← 公告管理
```

### 3.2 组件命名（PascalCase）

| 组件 | 说明 |
|------|------|
| `AiStaff.vue` | AI员工中心壳（含子路由视图） |
| `StaffOverview.vue` | 员工概览 |
| `TaskBoard.vue` | 任务工作台（Kanban） |
| `ContentStudio.vue` | 内容专员工作室 |
| `AcquisitionStudio.vue` | 获客专员工作室 |
| `ConversionStudio.vue` | 转化专员工作室 |
| `OpsStudio.vue` | 运营专员工作室 |
| `ContentFactory.vue` | 内容工厂 |
| `Marketing.vue` | 营销拓客 |
| `Settings.vue` | 系统设置壳 |
| `SuperStaffButton.vue` | 超级员工悬浮按钮（全局） |
| `SuperStaffPanel.vue` | 超级员工对话面板（全局） |
| `StaffCard.vue` | 员工状态卡片（复用） |
| `TaskCard.vue` | 任务卡片（Kanban用） |
| `ToolCallCard.vue` | 工具调用进度卡片（超级员工面板用） |

### 3.3 用户界面文字（不暴露技术术语）

| 界面位置 | 应使用 | 不应使用 |
|----------|--------|----------|
| 顶部导航 | 超级员工 | Hermes |
| 面板标题 | 超级员工 | Hermes |
| 消息署名 | 超级员工 | Hermes |
| 仪表盘卡片 | 超级员工 | Hermes |
| 技术接口 | 保留 `hermes_chat.py`、 `/api/hermes/*` | — |
| 内部代码 | 保留 `hermesStore`、`hermesService` | — |

---

## 四、超级员工对话面板技术要点

### 4.1 组件架构

```
SuperStaffButton.vue        ← 悬浮按钮（所有页面挂载在 AppLayout 中）
  └── 点击 → 展开 SuperStaffPanel.vue

SuperStaffPanel.vue         ← 右侧滑出面板
  ├── PanelHeader.vue       ← 标题栏（头像+名称+状态灯+关闭按钮）
  ├── MessageList.vue       ← 消息列表（滚动容器）
  │   ├── UserMessage.vue   ← 用户消息（右对齐）
  │   ├── StaffMessage.vue  ← 超级员工回复（左对齐，支持多种类型）
  │   │   ├── TextMessage.vue
  │   │   ├── ThinkingMessage.vue   ← "正在分析任务..."
  │   │   ├── ToolCallCard.vue      ← 工具调用进度（核心）
  │   │   └── ResultCard.vue        ← 执行结果展示
  │   └── SystemMessage.vue ← 系统提示（如"连接已恢复"）
  ├── InputArea.vue         ← 输入框 + 发送按钮 + 快捷指令
  └── PanelFooter.vue       ← 底部状态栏（模型信息、网络状态）
```

### 4.2 后端接口

```typescript
// 发送消息（SSE 流式）
POST /api/hermes/chat
Body: { message: string, session_id?: string }
Response: SSE stream

// 获取历史
GET /api/hermes/history?session_id=xxx&limit=50

// 取消当前任务
POST /api/hermes/cancel
Body: { session_id: string }

// SSE 事件类型（参考）
event: thinking      data: { task_breakdown: [...] }
event: tool_call     data: { tool: string, params: {}, progress: 0.5 }
event: tool_result   data: { tool: string, result: {}, status: 'success' }
event: message       data: { content: '...', role: 'assistant' }
event: error         data: { code: string, message: '...' }
event: done          data: {}
```

### 4.3 关键状态管理

```typescript
// Pinia Store（建议）
interface SuperStaffState {
  isOpen: boolean           // 面板是否展开
  isMinimized: boolean      // 是否最小化（收起为底部标签）
  messages: Message[]       // 消息列表
  isThinking: boolean       // 是否正在思考
  currentToolCall: ToolCall | null  // 当前工具调用
  activeTasks: Task[]        // 超级员工正在执行的任务
  sessionId: string         // 当前会话ID
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting'
}
```

### 4.4 消息类型定义

```typescript
interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  type: 'text' | 'thinking' | 'tool_call' | 'tool_result' | 'error' | 'confirm'
  content?: string
  toolCall?: {
    tool: string
    params: Record<string, any>
    progress: number  // 0-1
    status: 'running' | 'completed' | 'failed'
  }
  result?: {
    tool: string
    data: any
    preview?: string  // 预览内容（如视频缩略图URL）
  }
  confirmRequest?: {
    title: string
    description: string
    actions: { label: string, value: string }[]
  }
  timestamp: number
}
```

### 4.5 视觉规范

| 元素 | 规范 |
|------|------|
| 面板宽度 | 420px（桌面），100%（移动端） |
| 面板高度 | 100vh（桌面），从底部滑出（移动端） |
| 面板背景 | 半透明深色 + 毛玻璃效果（backdrop-filter: blur） |
| 边框 | 左侧 1px 青色发光边框（rgba(0, 212, 255, 0.3)） |
| 悬浮按钮 | 56px 圆形，青色渐变背景，脉冲动画 |
| 用户消息 | 右对齐，深色气泡，圆角 12px 12px 2px 12px |
| 超级员工消息 | 左对齐，半透明背景，圆角 12px 12px 12px 2px |
| 工具调用卡片 | 带边框卡片，顶部有进度条，青色主题 |
| 结果卡片 | 绿色边框，含预览图和操作按钮 |
| 错误卡片 | 红色边框，含重试按钮 |
| 快捷指令 | 横向滚动的小标签，点击填充输入框 |

---

## 五、仪表盘设计要点

### 5.1 布局（从上到下）

```
┌────────────────────────────────────────────────────────────┐
│ 今日指挥台                          2024-06-27 周四        │
├────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────┐  ┌────────────────┐  │
│ │  🎤 输入指令，如"帮我发3条..."    │  │ [一键上班]     │  │
│ │  ─────────────────────────────   │  │ [语音] [快捷]  │  │
│ └──────────────────────────────────┘  └────────────────┘  │
├────────────────────────────────────────────────────────────┤
│ 员工状态                                                    │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────┐│
│ │ 超级员工  │ │ 内容专员  │ │ 获客专员  │ │ 转化专员  │ │ 运营││
│ │  🤖      │ │  📝      │ │  🎯      │ │  💬      │ │  📊││
│ │ 运行中    │ │ 空闲      │ │ 运行中    │ │ 空闲      │ │ ...││
│ │ ████░░   │ │ ────      │ │ ██████░░ │ │ ────      │ │ ...││
│ │ 3/5 任务  │ │ 0/3 任务  │ │ 2/4 任务  │ │ 0/2 任务  │ │ ...││
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────┘│
├────────────────────────────────────────────────────────────┤
│ 任务队列                              │ 今日数据             │
│ ┌──────────────────────────────────┐ │ ┌────────────────┐ │
│ │ 任务名称        员工    进度   状态 │ │ │ 今日发布  12   │ │
│ │ ───────────────────────────────── │ │ │ ↑ 20%         │ │
│ │ 生成抖音视频    内容专员 ████░ 运行 │ │ │               │ │
│ │ 搜索竞品评论    获客专员 ██░░░ 运行 │ │ │ 新增线索  45   │ │
│ │ 处理昨日私信    转化专员 ────  待执行│ │ │ ↑ 15%         │ │
│ │ ...                               │ │ │               │ │
│ └──────────────────────────────────┘ │ │ 新增客户  8    │ │
│                                      │ │ ↑ 33%         │ │
│                                      │ │               │ │
│                                      │ │ 转化率   18%  │ │
│                                      │ │ ↑ 2%          │ │
│                                      │ └────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### 5.2 超级员工快捷输入框

- 位置：仪表盘顶部，最显眼的位置
- 样式：大输入框（高度 48px），左侧有 🎤 语音按钮，右侧有 ⚡ 发送按钮
- 占位文字："输入指令，如：帮我发3条抖音视频并处理评论区私信"
- 交互：输入后按 Enter 发送，直接打开超级员工面板并显示执行过程
- 快捷指令：输入框下方有一排小标签（一键上班 / 生成今日内容 / 检查平台状态 / 处理昨日私信）

---

## 六、实施顺序建议

### Phase 1（骨架）
1. 新建 `AiStaff.vue` 壳组件 + 所有子路由空壳
2. 新建 `SuperStaffButton.vue` + `SuperStaffPanel.vue`（空壳，仅可展开/收起）
3. 重写 `router.js` + `AppLayout.vue`（新导航 + 旧路由重定向）
4. 跑通路由，确认所有新页面可访问

### Phase 2（核心页面）
5. 重写 `Dashboard.vue`（新指挥台布局）
6. 实现 `StaffOverview.vue`（员工卡片网格）
7. 实现 `TaskBoard.vue`（Kanban 看板）
8. 实现 `SuperStaffPanel.vue`（超级员工对话面板，对接后端 SSE）

### Phase 3（工作室）
9. 实现 `ContentStudio.vue`（合并 ImageGen/VideoGen/Pipeline/Publisher/Calendar）
10. 实现 `AcquisitionStudio.vue`（合并 VideoSearch/Intercept/CommentManager）
11. 实现 `ConversionStudio.vue`（合并 Leads/Wechat/DM/SOP/Knowledge）
12. 实现 `OpsStudio.vue`（合并 Scheduler/Monitor/History/Strategy）

### Phase 4（沉淀页 + 设置）
13. 实现 `ContentFactory.vue`（内容资产沉淀）
14. 实现 `Marketing.vue`（客户成果沉淀）
15. 重写 `Settings.vue`（合并 Platforms/Tools/Settings/OEM/Admin）

### Phase 5（收尾）
16. 打磨 Onboarding：首次登录引导用户使用超级员工完成第一个任务
17. 旧页面重命名为 `.bak`，保留 1 周后删除
18. 测试所有旧路由重定向是否正常

---

*本文档版本：v1.0*
*配合阅读：`szyg前端重构计划.md`（产品级设计文档）*
