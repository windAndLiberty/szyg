# szyg 设计系统规范

> 超级数字员工系统 — 视觉设计规范文档

---

## 1. 设计原则

### 1.1 核心理念
- **高端大气**：深色科技主题，传递专业与前沿感
- **清晰易用**：信息层级分明，操作路径直观
- **精致细节**：每个像素都经过考量，微交互自然流畅
- **统一一致**：全系统遵循同一套视觉语言

### 1.2 设计关键词
`科技感` `专业` `深色主题` `玻璃态` `精致` `流畅` `现代 SaaS`

---

## 2. 色彩系统

### 2.1 主色板

| Token | Hex | HSL | 用途 |
|-------|-----|-----|------|
| Accent Primary | `#6366F1` | `239 84% 67%` | 主按钮、链接、高亮、图表主色 |
| Accent Secondary | `#818CF8` | `239 92% 74%` | Hover 状态、次要高亮 |
| Accent Glow | `rgba(99,102,241,0.4)` | — | 发光效果、阴影 |

### 2.2 背景色板

| Token | Hex | 用途 |
|-------|-----|------|
| BG Primary | `#0B0F1A` | 页面主背景 |
| BG Secondary | `#111827` | 侧边栏、顶部栏、卡片底层 |
| BG Tertiary | `#1A2235` | 卡片上层、弹出层、输入框背景 |
| BG Input | `#0D1321` | 输入框、下拉框背景 |

### 2.3 文字色板

| Token | Hex | 用途 |
|-------|-----|------|
| Text Primary | `#F1F5F9` | 标题、重要文字 |
| Text Secondary | `#94A3B8` | 正文、描述 |
| Text Muted | `#64748B` | 占位符、次要信息、时间戳 |

### 2.4 边框色板

| Token | Hex | 用途 |
|-------|-----|------|
| Border Subtle | `#1E293B` | 默认边框、分割线 |
| Border Active | `#334155` | Hover 边框、焦点边框 |

### 2.5 状态色板

| 状态 | 颜色 | 背景透明度 |
|------|------|-----------|
| 成功 Success | `#10B981` | 15% |
| 警告 Warning | `#F59E0B` | 15% |
| 危险 Danger | `#EF4444` | 15% |
| 信息 Info | `#3B82F6` | 15% |

### 2.6 渐变定义

```css
/* 卡片渐变 */
.gradient-card {
  background: linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%);
}

/* Hero 区域渐变 */
.gradient-hero {
  background: linear-gradient(135deg, #0B0F1A 0%, #111827 40%, #1A1B3D 100%);
}

/* 紫色发光 */
.gradient-glow-purple {
  background: radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%);
}

/* 蓝色发光 */
.gradient-glow-blue {
  background: radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%);
}
```

---

## 3. 排版系统

### 3.1 字体族

```css
font-family: {
  display: '"Noto Sans SC", "Inter", system-ui, sans-serif',
  body: '"Inter", "Noto Sans SC", system-ui, sans-serif',
  mono: '"SF Mono", "Fira Code", "JetBrains Mono", monospace',
}
```

### 3.2 字号规范

| 层级 | 类名 | 字号 | 行高 | 字间距 | 字重 | 用途 |
|------|------|------|------|--------|------|------|
| Display XL | `.text-display-xl` | 64px | 1.05 | -0.03em | Bold | 着陆页大标题 |
| Display LG | `.text-display-lg` | 48px | 1.1 | -0.02em | Bold | 营销标题 |
| Display MD | `.text-display-md` | 36px | 1.15 | -0.02em | Semibold | 页面标题 |
| Heading LG | `.text-heading-lg` | 28px | 1.2 | -0.01em | Semibold | 区块标题 |
| Heading MD | `.text-heading-md` | 22px | 1.25 | -0.01em | Semibold | 卡片标题 |
| Heading SM | `.text-heading-sm` | 18px | 1.3 | — | Semibold | 子标题 |
| Body LG | `.text-body-lg` | 16px | 1.6 | — | Normal | 正文 |
| Body MD | `.text-body-md` | 14px | 1.5 | — | Normal | 次要文字 |
| Body SM | `.text-body-sm` | 13px | 1.4 | — | Normal | 辅助文字 |
| Label | `.text-label` | 12px | 1.3 | 0.05em | Medium | 标签/徽章 |
| Mono MD | `.text-mono-md` | 13px | 1.5 | — | Normal | 代码/数据 |

### 3.3 KPI 数字

```css
.kpi-number {
  font-size: 42px;
  font-weight: bold;
  line-height: 1;
  letter-spacing: -0.02em;
  color: #F1F5F9;
}
```

---

## 4. 间距系统

### 4.1 布局间距

| 元素 | 尺寸 | 说明 |
|------|------|------|
| 侧边栏宽度 | 260px (展开) / 72px (收起) | 固定定位 |
| 顶部栏高度 | 64px | 固定定位 |
| 主内容内边距 | 32px (p-8) | 上下左右 |
| 卡片内边距 | 20px (p-5) | 默认 |
| 卡片间距 | 16px (gap-4) | 网格间距 |

### 4.2 圆角规范

| Token | 值 | 用途 |
|-------|-----|------|
| `rounded-card` | 12px | 卡片 |
| `rounded-card-sm` | 10px | 小卡片、列表项 |
| `rounded-card-lg` | 16px | 大卡片、弹窗 |
| `rounded-input` | 10px | 输入框 |
| `rounded-button` | 10px | 按钮 |

---

## 5. 组件规范

### 5.1 卡片 (Card)

```css
.glass-card {
  background: linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%);
  border: 1px solid #1E293B;
  border-radius: 12px;
  /* Hover */
  hover: border-color #334155;
  hover: box-shadow 0 8px 24px rgba(0,0,0,0.3);
}
```

### 5.2 按钮 (Button)

| 变体 | 背景 | 文字 | 边框 | Hover |
|------|------|------|------|-------|
| Default | `#6366F1` | `#FFFFFF` | 无 | `#818CF8` |
| Outline | 透明 | `#94A3B8` | `#1E293B` | bg `rgba(255,255,255,0.03)` |
| Ghost | 透明 | `#94A3B8` | 无 | bg `rgba(255,255,255,0.03)` |
| Destructive | `#EF4444` | `#FFFFFF` | 无 | `#EF4444/90` |

### 5.3 输入框 (Input)

```css
input {
  background: #0D1321;
  border: 1px solid #1E293B;
  border-radius: 10px;
  color: #F1F5F9;
  placeholder-color: #64748B;
  focus: border-color #334155;
  focus: ring 1px rgba(99,102,241,0.2);
}
```

### 5.4 徽章 (Badge)

| 变体 | 背景 | 文字 |
|------|------|------|
| Success | `rgba(16,185,129,0.15)` | `#10B981` |
| Warning | `rgba(245,158,11,0.15)` | `#F59E0B` |
| Error | `rgba(239,68,68,0.15)` | `#EF4444` |
| Info | `rgba(59,130,246,0.15)` | `#3B82F6` |

### 5.5 侧边栏导航项

```css
/* 默认 */
color: #94A3B8;
hover: bg rgba(255,255,255,0.03);
hover: color #F1F5F9;

/* 激活 */
bg: rgba(99,102,241,0.08);
color: #6366F1;
border-left: 3px solid #6366F1;
```

---

## 6. 动画规范

### 6.1 缓动函数

| 名称 | 值 | 用途 |
|------|-----|------|
| Ease Out Expo | `cubic-bezier(0.16, 1, 0.3, 1)` | 页面入场、卡片动画 |
| Ease Out Quart | `cubic-bezier(0.25, 1, 0.5, 1)` | 一般过渡 |
| Ease Spring | `cubic-bezier(0.34, 1.56, 0.64, 1)` | 弹性效果 |

### 6.2 时长规范

| 类型 | 时长 | 用途 |
|------|------|------|
| 即时 | 100ms | Hover 颜色变化 |
| 快速 | 200ms | Hover 位移、边框变化 |
| 标准 | 300ms | 展开/收起、Tab 切换 |
| 缓慢 | 400-600ms | 页面入场、卡片动画 |

### 6.3 入场动画

```typescript
// 容器
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
}

// 子元素
const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1, y: 0,
    transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] },
  },
}
```

---

## 7. 阴影系统

| Token | 值 | 用途 |
|-------|-----|------|
| `shadow-card-hover` | `0 8px 24px rgba(0,0,0,0.3)` | 卡片 Hover |
| `shadow-card-lift` | `0 12px 32px rgba(0,0,0,0.2)` | 卡片抬升 |
| Dropdown | `0 4px 16px rgba(0,0,0,0.4)` | 下拉菜单 |
| Modal | `0 16px 48px rgba(0,0,0,0.5)` | 弹窗/抽屉 |

---

## 8. 图标规范

- **图标库**: Lucide React
- **默认尺寸**: 16px (w-4 h-4)
- **导航图标**: 20px (w-5 h-5)
- **状态图标**: 14-16px
- **描边宽度**: 默认 (1.5px)

---

## 9. 响应式断点

| 断点 | 宽度 | 布局调整 |
|------|------|----------|
| SM | 640px | 单列 → 双列 |
| MD | 768px | 双列 → 三列 |
| LG | 1024px | 侧边栏展开 |
| XL | 1280px | 最大内容宽度 |

---

## 10. 无障碍规范

- 所有交互元素支持键盘导航
- 焦点状态可见（ring 高亮）
- 色彩对比度满足 WCAG 2.1 AA 标准
- 语义化 HTML 标签
- 图标按钮包含 aria-label

---

*本设计系统严格参考 frontend_refer 项目视觉风格，确保整体界面效果高度一致且精致。*
