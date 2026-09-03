---
title: 域灵前端架构与路由设计
status: 已更新 v2.0
desc: React 19 + TypeScript + Vite 6 + Tailwind CSS 3
---

# 🏗️ 前端架构与路由设计 (React版)

## 1. 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| TypeScript | 5.7 | 类型系统 |
| Vite | 6 | 构建工具 |
| Tailwind CSS | 3 | 原子化样式 |
| Framer Motion | 12 | 动画引擎 |
| Lucide React | 0.48+ | 图标库 |
| Recharts | 2.15+ | 图表库 |
| Radix UI | 1.x | 无头组件基座 |
| React Router | 7.5 | 路由管理 |
| class-variance-authority | 0.7 | 组件变体管理 |

## 2. 项目结构

```
szyg-frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── postcss.config.js
├── public/
│   └── szyg-logo.svg
└── src/
    ├── main.tsx              # 入口
    ├── App.tsx               # 路由配置
    ├── index.css             # 全局样式 + Design Tokens
    ├── api.ts                # API 通信层 (代理到后端 :8000)
    ├── types/                # TypeScript 类型定义
    ├── lib/                  # 工具函数 (utils, hooks, format)
    ├── components/
    │   ├── Layout.tsx        # 布局壳 (Sidebar + TopBar + Content)
    │   ├── Sidebar.tsx       # 侧边栏导航
    │   ├── TopBar.tsx        # 顶部栏
    │   ├── Footer.tsx        # 页脚
    │   ├── ui/               # 基础组件库
    │   │   ├── button.tsx
    │   │   ├── card.tsx
    │   │   ├── badge.tsx
    │   │   ├── input.tsx
    │   │   ├── avatar.tsx
    │   │   ├── switch.tsx
    │   │   ├── label.tsx
    │   │   ├── separator.tsx
    │   │   └── empty.tsx
    │   └── superagent/       # 超级员工组件
    │       ├── ChatMessageView.tsx
    │       ├── ConversationPanel.tsx
    │       └── WelcomeState.tsx
    └── pages/
        ├── Dashboard.tsx     # 运营仪表盘
        ├── DigitalHuman.tsx  # 数字人管理
        ├── Settings.tsx      # 系统设置
        └── SuperAgent.tsx   # 超级员工对话页面
```

## 3. 应用外壳布局

```
┌────────────────────────────────────────────────────┐
│  Sidebar (260px)  │  TopBar (64px)                 │
│                   ├────────────────────────────────┤
│  Logo             │                                │
│  ─────────        │  Page Content                  │
│  AI员工           │  (pt-8 px-8)                   │
│  内容创作         │                                │
│  营销获客         │                                │
│  发布管理         │                                │
│  工作流           │                                │
│  数据洞察         │                                │
│  知识库           │                                │
│  系统设置         │                                │
│  ─────────        │                                │
│  Collapse ◀       │                                │
└──────────────────┴────────────────────────────────┘
```

- **Sidebar**：260px 展开 / 72px 折叠，`bg-[#111827]`
- **TopBar**：64px 固定高度，`bg-[#111827]`
- **Content**：`flex-1 pt-[64px] pl-[260px]` (折叠时 72px)

## 4. 9大一级模块与路由

```
域灵 (szyg) — 智能矩阵运营系统
│
├── 🤖 AI员工         /ai-staff     ← P0 默认入口
│   ├── 💬 超级员工    /             ← 系统首页
│   ├── 🎬 AI视频      /ai-staff/video
│   ├── 🧠 AI人才市场  /ai-staff/market
│   └── 📋 任务看板    /ai-staff/tasks
│
├── 📦 内容创作       /content
│   ├── ✏️ 内容生产    /content/production
│   ├── 🖼️ 素材管理    /content/assets
│   └── 🧍 数字人      /content/digital-human
│
├── 🎯 营销获客       /marketing
│   ├── 🎣 智能截流    /marketing/intercept
│   ├── 📡 舆情监听    /marketing/listen
│   ├── 💼 客户转化    /marketing/conversion
│   └── 👥 客户资产    /marketing/customers
│
├── 📤 发布管理       /publish
│   ├── 📮 发布中心    /publish/center
│   ├── 🔐 账号管理    /publish/accounts
│   └── 📅 内容日历    /publish/calendar
│
├── ⚙️ 工作流         /workflow
│   ├── 🔄 流水线编排  /workflow/pipeline
│   ├── ⏰ 调度引擎    /workflow/scheduler
│   └── 📋 SOP管理     /workflow/sop
│
├── 📊 数据洞察       /insights
│   ├── 📈 运营仪表盘  /insights/dashboard
│   ├── 📉 内容分析    /insights/content-analytics
│   └── 🎯 获客分析    /insights/acquisition-analytics
│
├── 📚 知识库         /knowledge
│   ├── 📖 知识管理    /knowledge/base
│   ├── 🧠 长期记忆    /knowledge/memory
│   ├── 🛠️ 技能市场    /knowledge/skills
│   └── 🏫 商学院      /knowledge/academy
│
└── ⚙️ 系统设置       /settings
    ├── 🛡️ 风控策略    /settings/risk-control
    ├── 🔧 工具管理    /settings/tools
    ├── ⚙️ 系统配置    /settings/system
    ├── 🎨 品牌配置    /settings/brand
    ├── 👥 团队管理    /settings/team
    └── 💳 计费管理    /settings/billing
```

## 5. 当前已实现页面

| 路由 | 文件 | 状态 | 说明 |
|------|------|------|------|
| `/` | `SuperAgent.tsx` | ✅ 已实现 | 超级员工对话主页面，含SSE流式 |
| `/dashboard` | `Dashboard.tsx` | ✅ 已实现 | KPI卡片+趋势图+实时动态+任务队列 |
| `/digital-human` | `DigitalHuman.tsx` | ✅ 已实现 | 数字人卡片网格+搜索筛选+上传 |
| `/settings` | `Settings.tsx` | ✅ 已实现 | Tab式设置页面(通用/AI模型/Agent/集成/团队) |

## 6. 待实现的页面

按模块树结构，需要逐步创建：

| 优先级 | 路由 | 建议 |
|--------|------|------|
| P0 | `/ai-staff/chat` | 复用SuperAgent.tsx，作为AI员工子路由 |
| P1 | `/ai-staff/video` | 复用DigitalHuman.tsx中视频能力，或新建 |
| P1 | `/ai-staff/market` | 新建AI人才市场页 (Agency集成) |
| P1 | `/content/production` | 新建AI内容生产页 |
| P1 | `/content/assets` | 新建素材管理页 |
| P1 | `/publish/center` | 新建发布中心页 |
| P1 | `/publish/accounts` | 新建平台账号管理页 |
| P1 | `/marketing/intercept` | 新建智能截流配置页 |
| P1 | `/marketing/listen` | 新建舆情监听页 |

## 7. 向后兼容重定向

```typescript
// App.tsx 中需要维护的重定向规则
const redirects = [
  { from: "/chat", to: "/ai-staff/chat" },
  { from: "/agents", to: "/ai-staff/market" },
  { from: "/publisher", to: "/publish/center" },
  { from: "/old-content", to: "/content/production" },
  // ... 共40+条
];
```

