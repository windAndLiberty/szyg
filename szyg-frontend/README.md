# szyg - 超级数字员工系统

> 智能矩阵运营系统 — 高端现代 SaaS 前端设计系统

## 项目概述

本项目为 **"szyg - 超级数字员工系统"** 的完整前端设计系统实现，严格参考 `frontend_refer` 项目的视觉风格与组件设计，打造高端、现代、统一的 SaaS 产品界面。

### 核心特性

- **深色科技主题**：极深蓝黑背景 + 靛蓝紫主色，营造高端科技感
- **精致玻璃态卡片**：渐变背景 + 柔和边框 + hover 光影效果
- **流畅微交互动画**：Framer Motion 驱动的页面过渡与元素动画
- **完整组件库**：Button、Card、Badge、Input、Avatar、Switch、Empty 等
- **响应式布局**：适配桌面端多种屏幕尺寸
- **数据可视化**：Recharts 驱动的面积图、饼图等图表组件

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| TypeScript | 5.7 | 类型系统 |
| Vite | 6 | 构建工具 |
| Tailwind CSS | 3 | 原子化样式 |
| Framer Motion | 12 | 动画引擎 |
| Lucide React | 0.48 | 图标库 |
| Recharts | 2.15 | 图表库 |
| Radix UI | 1.x | 无头组件基座 |

## 设计规范

### 配色系统

```
背景主色:   #0B0F1A  (极深蓝黑)
背景次色:   #111827  (暗灰蓝)
背景第三层: #1A2235  (稍浅暗蓝)
输入框背景: #0D1321

主强调色:   #6366F1  (靛蓝紫)
次强调色:   #818CF8  (浅靛蓝)

文字主色:   #F1F5F9  (近白)
文字次色:   #94A3B8  (浅灰蓝)
文字弱化:   #64748B

边框色:     #1E293B  (暗边框)
Hover边框:  #334155

成功绿:     #10B981
警告橙:     #F59E0B
危险红:     #EF4444
信息蓝:     #3B82F6
```

### 排版层次

| 级别 | 类名 | 字号 | 字重 | 用途 |
|------|------|------|------|------|
| Display XL | `.text-display-xl` | 64px | bold | 着陆页大标题 |
| Display MD | `.text-display-md` | 36px | semibold | 页面标题 |
| Heading LG | `.text-heading-lg` | 28px | semibold | 区块标题 |
| Heading MD | `.text-heading-md` | 22px | semibold | 卡片标题 |
| Body LG | `.text-body-lg` | 16px | normal | 正文 |
| Body MD | `.text-body-md` | 14px | normal | 次要文字 |
| Label | `.text-label` | 12px | medium | 标签/徽章 |

### 布局结构

```
┌──────────────────────────────────────┐
│  Sidebar (260px)  │   TopBar (64px)   │
│                   ├───────────────────┤
│  Logo             │                   │
│  ─────────────    │   Page Content    │
│  Dashboard        │                   │
│  数字人管理       │   (p-8)           │
│  系统设置         │                   │
│  ─────────────    │                   │
│  Collapse         │                   │
├───────────────────┴───────────────────┤
│              Footer                   │
└──────────────────────────────────────┘
```

### 动画规范

- **缓动函数**: `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out-expo)
- **页面入场**: staggerChildren 0.08~0.1s
- **Hover 过渡**: 0.2s
- **Tab 切换**: layoutId 共享元素动画

## 项目结构

```
szyg-frontend/
├── public/
│   └── szyg-logo.svg
├── src/
│   ├── components/
│   │   ├── Layout.tsx          # 布局壳
│   │   ├── Sidebar.tsx         # 侧边栏导航
│   │   ├── TopBar.tsx          # 顶部栏
│   │   ├── Footer.tsx          # 页脚
│   │   └── ui/                 # 基础组件库
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── badge.tsx
│   │       ├── input.tsx
│   │       ├── empty.tsx
│   │       ├── avatar.tsx
│   │       ├── switch.tsx
│   │       ├── separator.tsx
│   │       └── label.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx       # 运营仪表盘
│   │   ├── DigitalHuman.tsx    # 数字人管理
│   │   └── Settings.tsx        # 系统设置
│   ├── data/
│   │   └── mockData.ts         # 模拟数据
│   ├── types/
│   │   └── index.ts            # TypeScript 类型
│   ├── lib/
│   │   └── utils.ts            # 工具函数 (cn)
│   ├── App.tsx                 # 路由配置
│   ├── main.tsx                # 入口文件
│   └── index.css               # 全局样式 + Design Tokens
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
└── postcss.config.js
```

## 页面说明

### 1. 运营仪表盘 (Dashboard)

- **KPI 卡片**：数字员工总数、今日交互、平均成功率、任务队列
- **交互趋势图**：recharts AreaChart，支持 7D/30D/90D 切换
- **实时动态流**：系统事件时间线
- **数字员工分布**：环形图展示类型分布
- **任务队列**：进度条 + 状态标签

### 2. 数字人管理 (DigitalHuman)

- **搜索与筛选**：按名称搜索、按类型/状态筛选
- **卡片网格**：展示数字员工头像、名称、状态、描述、统计数据
- **状态指示**：运行中(绿)、训练中(橙)、待机(灰)、异常(红)
- **上传区域**：可折叠的配置文件拖拽上传区
- **空状态**：浮动动画 + 引导创建

### 3. 系统设置 (Settings)

- **5 个 Tab**：通用设置 / AI 模型 / 数字员工 / 集成配置 / 账户管理
- **主题切换**：Light / Dark / System
- **AI 参数**：模型选择、Temperature、Max Tokens
- **Agent 开关**：8 类数字员工 Agent 的启用控制
- **团队管理**：成员列表、添加/删除

## 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

## 设计系统亮点

1. **高度统一的视觉语言**：所有页面严格遵循同一套配色、圆角、阴影、间距规范
2. **精致的玻璃态效果**：卡片使用 `linear-gradient` + `backdrop-blur` 营造层次感
3. **流畅的微交互**：每个交互元素都有精心设计的 hover/active/focus 状态
4. **专业的数据可视化**：图表配色与整体主题完美融合
5. **中文字体优化**：使用 Noto Sans SC + Inter 组合，中文显示优雅清晰
6. **无障碍设计**：合理的色彩对比度、焦点状态、语义化标签

---

© 2026 szyg - 超级数字员工系统
