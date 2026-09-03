# 🤖 超级员工页面设计规范 (Super Agent Page Spec)

> 本文件定义 `/super-agent` 路由对应的超级员工界面的页面级布局与交互规范。
> 遵循 `design-system.md` 全局视觉语言与 `layout-framework.md` 应用外壳框架。

---

## 1. 页面定位

超级员工是域灵系统的核心工作台，用户通过自然语言对话指挥 AI 员工完成营销任务。页面采用 **全出血 (full-bleed)** 布局，突破 `AppLayout` 内容区的 32px padding，使对话历史面板紧贴应用外壳边界。

---

## 2. 整体布局

```text
┌───────────────────────────────────────────────────────┐
│ Sidebar  │ Topbar (56px)                               │
│ (200px)  ├──────────────┬──────────────────────────────┤
│          │ Conv History  │  Chat Area                   │
│          │ (280px)       │                              │
│          │               │  ┌──────────────────────┐    │
│          │               │  │  Welcome / Messages  │    │
│          │               │  │                      │    │
│          │               │  └──────────────────────┘    │
│          │               │  ┌──────────────────────┐    │
│          │               │  │  Input Area          │    │
│          │               │  └──────────────────────┘    │
└──────────┴───────────────┴──────────────────────────────┘
```

### 2.1 Full-Bleed 机制

- SuperAgent 页面通过 CSS 突破 `AppLayout` 的 `.app-content` padding。
- 实现方式：`.app-content` 添加 `.full-bleed` 类，设置 `padding: 0`。
- 页面自身管理内部间距，不依赖全局内容区 padding。

### 2.2 三栏结构

| 区域 | 宽度 | 背景 | 说明 |
|------|------|------|------|
| App Sidebar | 200px / 64px | `var(--glass-bg)` | 全局导航，由 AppLayout 管理 |
| Conv History | 280px | `var(--bg-page)` | 对话历史列表，紧贴 App Sidebar 右侧 |
| Chat Area | `flex: 1` | `var(--bg-body)` | 消息区 + 输入区 |

- Conv History 与 Chat Area 之间使用 `1px solid var(--border-light)` 分隔线。
- 三栏总高度：`calc(100vh - 56px)`（减去顶栏高度）。
- 三栏均独立滚动，互不影响。

---

## 3. 对话历史面板 (Conv History Panel)

### 3.1 容器

| 属性 | 值 |
|------|-----|
| 宽度 | 280px（固定，不可缩放） |
| 高度 | 100%（填满 top 到 bottom） |
| 背景 | `var(--bg-page)` |
| 右边框 | 1px solid `var(--border-light)` |
| 布局 | `flex; flex-direction: column` |

### 3.2 Header

| 属性 | 值 |
|------|-----|
| 高度 | 48px |
| 内边距 | 0 16px |
| 底边框 | 1px solid `var(--border-light)` |
| 左侧 | 标题 "对话历史"，`text-sm`（13px），字重 600，`var(--text-primary)` |
| 右侧 | 新建对话按钮，图标按钮 24px，`var(--text-tertiary)`，hover `var(--text-primary)` |

### 3.3 对话列表

| 属性 | 值 |
|------|-----|
| 容器 | `flex: 1; overflow-y: auto` |
| 内边距 | 8px |
| 滚动条 | 4px，`var(--scrollbar-thumb)` |

#### 对话项

| 属性 | 值 |
|------|-----|
| 内边距 | 10px 12px |
| 圆角 | 8px |
| 间距 | 4px（项之间） |
| cursor | pointer |
| hover | `var(--bg-hover)` |
| active | `var(--accent-soft)` 背景 |
| 标题 | 13px，`var(--text-primary)`，单行省略 |
| 时间 | 11px，`var(--text-tertiary)`，间距 2px |
| active 标题颜色 | `var(--accent)` |

### 3.4 空列表状态

- 当无对话历史时，显示居中文字 "暂无对话记录"，`text-sm`，`var(--text-tertiary)`。
- 上方可放置 32px 线性图标，颜色 `var(--text-tertiary)`。

---

## 4. 对话区域 (Chat Area)

### 4.1 容器

| 属性 | 值 |
|------|-----|
| 布局 | `flex; flex-direction: column` |
| 背景 | `var(--bg-body)` |
| 高度 | 100% |

### 4.2 消息区 (Messages Area)

| 属性 | 值 |
|------|-----|
| 容器 | `flex: 1; overflow-y: auto` |
| 内边距 | 32px（桌面）/ 24px（平板）/ 16px（手机） |
| 滚动条 | 4px |

#### 消息项

| 属性 | 值 |
|------|-----|
| 布局 | `flex; gap: 12px` |
| 间距 | 20px（消息之间） |
| 头像 | 28px，圆角 999px，背景 `var(--accent-soft)`，文字 `var(--accent)` |
| 用户头像 | 显示用户名首字 |
| AI 头像 | 显示 Agent 图标或 "AI" |
| 消息内容 | `flex: 1; min-width: 0` |
| 消息文字 | 14px，行高 1.7，`var(--text-primary)` |
| AI 消息文字 | 14px，行高 1.7，`var(--text-secondary)` |
| Markdown | 支持 GFM，代码块圆角 8px，背景 `var(--bg-hover)` |

#### 工具调用展示

| 属性 | 值 |
|------|-----|
| 容器 | margin-top 8px，纵向 flex，gap 4px |
| 项布局 | `flex; align-items: center; gap: 8px` |
| 标签 | 使用 Tag 组件，12px，pill |
| 结果文字 | 12px，`var(--text-tertiary)`，单行省略 |

### 4.3 欢迎引导空状态 (Welcome Empty State)

**触发条件**：无消息或新对话时显示。

```text
┌──────────────────────────────────────┐
│                                      │
│         [Agent 图标 64px]             │
│                                      │
│         你好，我是超级员工             │
│    用一句话指挥我完成任何营销任务       │
│                                      │
│    ┌──────┐ ┌──────┐ ┌──────┐        │
│    │ 快捷1 │ │ 快捷2 │ │ 快捷3 │        │
│    └──────┘ └──────┘ └──────┘        │
│    ┌──────┐ ┌──────┐                 │
│    │ 快捷4 │ │ 快捷5 │                 │
│    └──────┘ └──────┘                 │
│                                      │
└──────────────────────────────────────┘
```

#### 结构定义

| 元素 | 规格 |
|------|------|
| 容器 | `flex: 1; flex-direction: column; align-items: center; justify-content: center; padding: 32px` |
| Agent 图标 | 64px，圆角 999px，背景 `var(--accent-soft)`，内含 Agent emoji 或图标，颜色 `var(--accent)` |
| 图标间距 | 底部 24px |
| 欢迎标题 | `text-xl`（20px），字重 600，`var(--text-primary)`，间距 8px |
| 欢迎描述 | `text-base`（14px），`var(--text-secondary)`，最大宽度 400px，居中对齐，间距 32px |
| 快捷卡片网格 | `display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; max-width: 600px` |
| 快捷卡片 | 见下表 |

#### 快捷卡片

| 属性 | 值 |
|------|-----|
| 背景 | `var(--bg-card)` |
| 边框 | 1px solid `var(--border-light)` |
| 圆角 | 12px |
| 内边距 | 16px |
| cursor | pointer |
| hover | `var(--shadow-md)` + `translateY(-1px)`，250ms |
| 标题 | 13px，字重 500，`var(--text-primary)` |
| 描述 | 12px，`var(--text-tertiary)`，间距 4px，2 行省略 |
| 点击行为 | 将快捷指令填入输入框并自动发送 |

#### 快捷指令内容

| 标题 | 描述 | 发送内容 |
|------|------|----------|
| 搜索截流 | 搜索抖音 AI 培训视频并截流 | `搜索抖音AI培训视频并截流` |
| 生成文案 | 生成 5 条护肤文案 | `生成5条护肤文案` |
| 定时发布 | 今天 12 点发 3 个视频到抖音 | `今天12点发3个视频到抖音` |
| 数据查看 | 查看今日截流数据 | `查看今日截流数据` |
| 客户接待 | 给新客户发欢迎语 | `给新客户发欢迎语` |

- 快捷指令列表应从后端 API 动态获取（如有），否则使用默认值。
- 后续可扩展为 Agent 能力自动生成快捷卡片。

### 4.4 输入区 (Input Area)

| 属性 | 值 |
|------|-----|
| 容器 | 顶部边框 1px `var(--border-light)`，内边距 16px 32px |
| 背景 | `var(--bg-body)` |

#### 快捷标签栏

| 属性 | 值 |
|------|-----|
| 布局 | `flex; flex-wrap: wrap; gap: 6px` |
| 底部间距 | 8px |
| 标签 | 使用 Tag 组件 Default 变体，pill，12px，cursor pointer |
| hover | `var(--bg-active)` |
| 点击 | 填入输入框（不自动发送） |

#### 输入行

| 属性 | 值 |
|------|-----|
| 布局 | `flex; gap: 8px; align-items: flex-end` |
| 输入框 | Textarea，rows=2，圆角 8px，`var(--input-bg)` |
| 占位符 | "输入指令，如：帮我搜索抖音上关于AI培训的视频，生成评论并发送" |
| 发送按钮 | Primary，Large（40px），图标 20px |
| Enter 键 | 发送（Shift+Enter 换行） |
| Loading 态 | 按钮显示 spinner，禁用输入 |

---

## 5. 响应式行为

| 断点 | Conv History | Chat Area | 快捷卡片网格 |
|------|-------------|-----------|-------------|
| ≥1280px | 280px 固定 | flex: 1 | 3 列 |
| 1024–1279px | 240px 固定 | flex: 1 | 3 列 |
| 768–1023px | 隐藏，改为顶部下拉 | flex: 1 | 2 列 |
| <768px | 隐藏，改为顶部下拉 | flex: 1 | 1 列 |

- Conv History 在 `md` 以下隐藏，通过 Chat Area 左上角的按钮触发抽屉式展开。
- 抽屉宽度 280px，背景 `var(--bg-page)`，阴影 `var(--shadow-xl)`。

---

## 6. 交互规范

### 6.1 对话流程

1. 用户进入页面 → 加载对话历史列表。
2. 无历史或点击"新建" → 显示欢迎空状态。
3. 用户点击快捷卡片 → 填入输入框并自动发送。
4. 用户手动输入 → 按 Enter 发送。
5. 消息发送 → 消息区显示用户消息 → 滚动到底部。
6. AI 回复流式输出 → 消息区实时渲染 → 完成后保存对话。
7. 用户点击历史项 → 加载对应对话消息 → 滚动到底部。

### 6.2 流式输出

- AI 回复使用 SSE (Server-Sent Events) 流式输出。
- 流式文字颜色：`var(--accent)`；完成后恢复 `var(--text-secondary)`。
- 光标闪烁动画：`blink 1s infinite`。
- 工具调用实时显示：标签从 warning（running）→ success/error。

### 6.3 滚动行为

- 新消息到达时自动滚动到底部。
- 用户手动上滚时不强制回到底部（检测 `scrollHeight - scrollTop - clientHeight > 100`）。
- 提供"回到底部"浮动按钮（可选，当用户上滚且有新消息时显示）。

---

## 7. 数据接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/hermes/conversations` | GET | 获取对话历史列表 |
| `/api/hermes/conversations/{id}` | GET | 获取指定对话的消息 |
| `/api/hermes/conversations` | POST | 保存对话 |
| `/api/hermes/chat` | POST (SSE) | 发送消息并流式接收回复 |

- 请求/响应格式详见 `KnowledgeBase/API_SPECS/`。

---

## 8. 实现约束

- 页面必须通过 `.full-bleed` 类突破 AppLayout 内容区 padding。
- 对话历史面板紧贴 App Sidebar 右侧，从顶栏底部延伸到视口底部。
- 欢迎空状态在 `state.messages.length === 0` 时显示，有消息后隐藏。
- 快捷卡片点击后自动发送（区别于快捷标签仅填入输入框）。
- 所有颜色、间距、圆角必须引用 `design-system.md` 中定义的 CSS 变量。
- 消息渲染使用 `marked` + `DOMPurify`，禁止直接 `v-html` 未净化的内容。
