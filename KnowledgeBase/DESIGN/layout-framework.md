# 🏗️ 应用外壳与布局框架 (App Shell & Layout Framework)

> 本文件定义域灵 Dashboard 的整体布局结构：侧边栏、顶栏、主内容区、网格系统、响应式规则。
> 所有页面必须基于本框架实现，禁止自定义全局布局结构。

---

## 1. 整体结构

```text
┌─────────────────────────────────────────────────────┐
│  Sidebar (200px)  │  Topbar (56px)                    │
│                   ├───────────────────────────────────┤
│                   │                                   │
│                   │  Main Content Area                │
│                   │  padding: 32px                    │
│                   │                                   │
│                   │                                   │
└───────────────────┴───────────────────────────────────┘
```

### 1.1 App Shell 层级

| 区域 | 组件 | 定位 | 行为 |
|------|------|------|------|
| `App Shell` | `AppLayout.vue` | `flex` 横向 | 始终占满视口 |
| `Sidebar` | 左侧边栏 | 固定宽度 200px / 折叠 64px | 可折叠，overflow 内部滚动 |
| `Main Area` | 右侧主区域 | `flex: 1` 填充剩余 | 纵向 flex 布局 |
| `Topbar` | 顶部栏 | 高度 56px | 固定在主区域顶部，可滚动时变为毛玻璃 |
| `Content` | 主内容区 | `flex: 1` 填充 | 独立滚动容器 |

### 1.2 颜色与材质

- `App Shell` 背景：`var(--bg-body)`。
- `Sidebar`：背景使用 `var(--glass-bg)` + `backdrop-filter: var(--glass-blur)`；叠加右侧 `1px` 边框 `var(--border-light)`。
- `Topbar`：背景默认 `var(--bg-page)`；滚动时切换为 `var(--glass-bg)` + 模糊 + `var(--shadow-sm)`。
- `Content`：背景 `var(--bg-body)`，无额外边框。

---

## 2. 侧边栏 (Sidebar)

### 2.1 尺寸与结构

| 状态 | 宽度 | 说明 |
|------|------|------|
| 展开 | 200px | 默认状态 |
| 折叠 | 64px | 仅显示图标，隐藏文字与分组标题 |

```vue
<!-- AppLayout.vue 结构示意 -->
<aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
  <div class="sidebar-brand">...</div>
  <nav class="sidebar-nav">...</nav>
  <div class="sidebar-footer">...</div>
</aside>
```

### 2.2 品牌区 (Brand)

- 高度：56px（与顶栏对齐）。
- 内边距：`0 20px`。
- 内容：Logo 图标 + 品牌名（折叠时隐藏文字，只显示图标）。
- 品牌名：`text-lg`（16px），字重 600，颜色 `var(--text-primary)`。
- 点击品牌区跳转首页（`/super-agent` 或 `/`）。

### 2.3 导航区 (Nav)

- 导航区域 `flex: 1`，允许纵向滚动（滚动条极细，4px）。
- 内边距：`16px 12px`（上下 16，左右 12）。
- 导航分组（可选）：分组标题使用 `text-xs`，全大写，颜色 `var(--text-tertiary)`，上下间距 `16px`。
- 分组标题不显示折叠箭头；整个侧边栏保持安静，不喧宾夺主。

#### 导航项 (Nav Item)

| 属性 | 值 |
|------|-----|
| 高度 | 40px |
| 内边距 | `10px 12px` |
| 圆角 | `var(--radius-sm)` (8px) |
| 图标尺寸 | 16px |
| 图标与文字间距 | 12px |
| 默认颜色 | `var(--text-secondary)` |
| hover 颜色 | `var(--text-primary)` + `var(--bg-hover)` |
| active 颜色 | `var(--accent)` + `var(--accent-soft)` 背景 |
| 字重 | 默认 400，active 500 |

- 所有导航项必须带图标 + 文字（折叠状态仅图标）。
- active 态使用 `var(--accent-soft)` 背景 + `var(--accent)` 文字，不使用左侧边框或背景色块。
- 当父级分组收起时，子项整体隐藏（高度动画 200ms）。

### 2.4 侧边栏底部 (Footer)

- 高度：48px。
- 包含：折叠/展开切换按钮（居中）。
- 折叠按钮：`24px` 图标，颜色 `var(--text-tertiary)`，hover 变 `var(--text-primary)`。
- 不显示用户信息或设置入口（这些放在顶栏右侧）。

### 2.5 侧边栏滚动

- 滚动条宽度：4px。
- 滚动条 thumb 颜色：`var(--scrollbar-thumb)`，hover 加深。
- 滚动条 track 透明。
- 滚动时侧边栏背景保持毛玻璃效果。

---

## 3. 顶栏 (Topbar)

### 3.1 尺寸与结构

- 高度：56px。
- 内边距：`0 24px`（与内容区 32px 保持对齐，减去内容区内部 padding 后统一）。
- 横向 flex：`space-between`。
- 左侧：当前页面标题 + 可选面包屑。
- 右侧：全局操作（搜索、主题切换、通知、用户头像）。

### 3.2 页面标题

- 字体：`text-lg`（16px），字重 600，颜色 `var(--text-primary)`。
- 不使用大标题或图标装饰，保持安静。
- 面包屑（如有）：使用 `text-sm`，颜色 `var(--text-secondary)`，分隔符 `>` 颜色 `var(--text-muted)`，当前页颜色 `var(--text-primary)`。

### 3.3 右侧工具区

- 元素间距：16px。
- 所有图标按钮：20px 容器，24px 点击区域，颜色 `var(--text-secondary)`，hover `var(--text-primary)` + `var(--bg-hover)` 背景，圆角 `var(--radius-sm)`。
- 用户头像：28px，圆角 `var(--radius-full)`，点击展开下拉菜单。
- 用户名：`text-sm`，颜色 `var(--text-secondary)`，最大宽度 120px，超出省略。

### 3.4 滚动后的顶栏

- 默认：`var(--bg-page)`，无边框。
- 当 `Content` 滚动超过 8px 时：切换为 `var(--glass-bg)` + `backdrop-filter: var(--glass-blur)` + `var(--shadow-sm)`，底部边框 `var(--border-light)` 1px。
- 过渡：`--duration-normal` + `--ease-smooth`。

---

## 4. 主内容区 (Main Content Area)

### 4.1 基础规则

- 背景：`var(--bg-body)`。
- 内边距：
  - 桌面（≥1280px）：32px
  - 平板（768px–1279px）：24px
  - 手机（<768px）：16px
- 可独立滚动：`overflow-y: auto`。
- 最大宽度：默认无限制，内容区跟随容器拉伸；**纯文本内容页面**可使用 `max-width: 720px` 居中。

### 4.2 页面标题区（可选）

- 与顶栏标题不重复。仅在页面需要额外说明时使用。
- 结构：标题 + 简短描述 + 操作按钮（右对齐）。
- 标题：`text-xl`（20px），字重 600。
- 描述：`text-sm`，颜色 `var(--text-secondary)`，位于标题下方，间距 4px。
- 与下方内容间距：32px。

### 4.3 页面间距节奏

```text
Topbar (56px)
  ↓ 0px（内容区从顶栏下方开始）
Content padding (32px)
  ↓
Page Header（可选）
  ↓ 32px
Section 1
  ↓ 40px（黄金比例间距）
Section 2
  ↓ 40px
...
```

- 同一页面内模块间距：32px 或 40px。
- 模块内部元素间距：16px 或 24px。
- 表单块之间：24px。

---

## 5. 网格系统

### 5.1 12 列网格

```css
.app-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 24px;
}
```

- 列间距：24px（桌面），16px（平板），12px（手机）。
- 所有 Dashboard 卡片、统计面板、图表容器必须放入网格。
- 禁止在页面中随意使用 `float` 或百分比宽度堆砌卡片。

### 5.2 常用列宽

| 类名 | 占用列数 | 用途 |
|------|----------|------|
| `.col-12` | 12 | 全宽卡片、表格、图表 |
| `.col-8` | 8 | 主内容区 |
| `.col-6` | 6 | 双列等宽卡片 |
| `.col-4` | 4 | 三列统计卡 |
| `.col-3` | 3 | 四列小指标 |

### 5.3 响应式网格

- 桌面（≥1280px）：完整 12 列。
- 平板（768px–1279px）：`.col-3` → 6 列；`.col-4` → 6 列；`.col-6` → 12 列；`.col-8` → 12 列。
- 手机（<768px）：所有列变为 12 列，垂直堆叠。

---

## 6. 卡片布局规范

### 6.1 标准卡片

| 属性 | 值 |
|------|-----|
| 背景 | `var(--bg-card)` |
| 边框 | 1px solid `var(--border-light)` |
| 圆角 | `var(--radius-md)` (12px) |
| 阴影 | `var(--shadow-sm)` |
| 内边距 | 24px |
| hover 阴影 | `var(--shadow-md)` + `translateY(-1px)` |
| 过渡 | 250ms `--ease-smooth` |

### 6.2 卡片内部结构

```text
┌─────────────────────────────┐
│  Header (24px bottom margin)│
│  标题 + 可选操作             │
├─────────────────────────────┤
│  Body                       │
│  内容 / 图表 / 表格         │
├─────────────────────────────┤
│  Footer (可选，20px top)     │
│  辅助说明 / 链接             │
└─────────────────────────────┘
```

- 卡片标题：`text-base`（14px），字重 600，颜色 `var(--text-primary)`。
- 卡片副标题：`text-xs`（12px），颜色 `var(--text-tertiary)`，间距 4px。
- 卡片标题与内容间距：16px。
- 卡片操作按钮放在 header 右侧，使用图标按钮或 small 按钮。

---

## 7. 响应式断点

| 断点 | 宽度 | 行为 |
|------|------|------|
| `xl` | ≥1280px | 完整布局，侧边栏展开 200px，内容区 32px padding |
| `lg` | 1024px–1279px | 侧边栏展开，网格列数减少，内容区 24px padding |
| `md` | 768px–1023px | 侧边栏折叠为 64px icon rail，内容区 24px padding |
| `sm` | 480px–767px | 侧边栏隐藏，使用汉堡菜单 + 抽屉式导航 |
| `xs` | <480px | 手机布局，单列，内容区 16px padding |

### 7.1 响应式行为细节

- **侧边栏折叠**：在 `md` 断点自动折叠为 64px，保留导航图标；hover 时不展开，用户必须点击展开按钮。
- **侧边栏隐藏**：在 `sm` 以下，侧边栏完全隐藏，通过顶栏左侧汉堡按钮触发抽屉式导航。
- 抽屉式导航：宽度 280px，覆盖在内容区上方，背景 `var(--bg-page)`，带 `var(--shadow-xl)`。
- 内容区：在 `md` 以下，使用更紧凑的卡片内边距（16px）。

---

## 8. 空状态与异常状态布局

### 8.1 空状态 (Empty State)

- 居中显示：flex 容器，`justify-content: center; align-items: center; min-height: 320px`。
- 图标：48px 线性图标，颜色 `var(--text-tertiary)`。
- 标题：`text-base`（14px），字重 500，颜色 `var(--text-primary)`，间距 12px。
- 描述：`text-sm`（13px），颜色 `var(--text-secondary)`，最大宽度 320px，居中对齐。
- 操作按钮：位于描述下方，间距 16px。

### 8.2 错误状态

- 与空状态类似，但图标使用语义色 `var(--error)`，标题使用 `var(--text-primary)`。
- 提供重试按钮或返回入口。

### 8.3 加载状态

- 页面级加载：使用全屏 mask，背景 `var(--loading-mask-bg)`，中央 spinner 24px，颜色 `var(--accent)`。
- 卡片级加载：骨架屏，圆角继承卡片，使用 `shimmer` 动画。
- 骨架屏颜色：`var(--border-light)` 基底 + `var(--border-color)`  shimmer。

---

## 9. 页面路由与布局映射

| 路由 | 布局 | 说明 |
|------|------|------|
| `/` | AppLayout | 重定向到 `/super-agent` |
| `/super-agent` | AppLayout + 标准内容区 | 主工作台 |
| `/settings/*` | AppLayout + 标准内容区 | 设置页 |
| 其他业务页 | AppLayout + 网格/卡片 | 后续新增页面遵循本框架 |

- 所有业务页面统一使用 `AppLayout.vue` 作为外壳。
- 登录页已移除，应用启动时自动认证并直接进入功能页面。

---

## 10. 实现约束

- 全局布局必须使用 `AppLayout.vue` 中的 `app-layout`、`app-sidebar`、`app-topbar`、`app-content` 类结构。
- 禁止使用 Element Plus `el-container` / `el-aside` / `el-header` 等布局组件直接控制全局结构（样式覆盖除外）。
- 所有布局尺寸必须使用 CSS 变量，禁止硬编码像素值。
- 响应式逻辑优先使用 CSS media query，必要时配合 Vue 响应式状态。
