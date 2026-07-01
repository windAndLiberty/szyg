# 🎨 核心视觉语言 (Core Visual Language)

> 本文件定义域灵系统全局视觉系统的原子级规范：色彩、字体、间距、阴影、圆角、动效、图标。所有前端样式变量必须以本文件为唯一来源。
> 设计哲学：Effie Aesthetic —— 退让、温润、克制、专注。

---

## 1. 设计原则

| 原则 | 含义 | 在代码中的体现 |
|------|------|----------------|
| **退让 (Retreat)** | 框架 UI 不抢内容风头 | 侧边栏/顶栏低对比、无边框、半透明毛玻璃 |
| **呼吸 (Breath)** | 用留白组织信息 | 大内边距、宽松行高、极少分隔线 |
| **克制 (Restraint)** | 颜色与动效只做必要表达 | 主 accent 仅用于关键状态；无装饰性渐变 |
| **温润 (Warmth)** | 避免冷硬科技灰 | 背景偏暖；文字使用暖调灰；阴影偏暖黑 |
| **专注 (Focus)** | 减少视觉噪音 | 统一组件形态；空状态安静、引导明确 |
| **和谐 (Harmony)** | 比例系统统一 | 4px 网格 + 黄金比例进阶；排版基于模数尺度 |

---

## 2. 色彩系统

### 2.1 色彩哲学

- 背景使用 **暖米白** (Light) 或 **深炭黑** (Dark)，模拟高级纸张与深夜书写环境。
- 唯一强调色使用 **soft indigo-purple**（柔和靛紫），仅用于：当前导航、主按钮、焦点环、状态高亮。
- 所有文字使用暖调灰阶，不使用纯黑 `#000000` 或纯白 `#FFFFFF`（除图标/反色场景）。
- 语义色（成功、警告、错误）保持低饱和度，不破坏整体宁静氛围。

### 2.2 Light 主题变量

```css
:root,
html[data-theme="light"] {
  /* Backgrounds — warm paper */
  --bg-body:       #F9F8F6;
  --bg-page:       #FFFFFF;
  --bg-card:       #FEFDFB;
  --bg-hover:      rgba(31, 31, 34, 0.04);
  --bg-active:     rgba(31, 31, 34, 0.07);
  --bg-selected:   rgba(110, 123, 255, 0.08);
  --bg-overlay:    rgba(255, 255, 255, 0.92);

  /* Text — warm grays */
  --text-primary:   #1F1F22;
  --text-secondary: #6E6E73;
  --text-tertiary:  #A1A1AA;
  --text-muted:     #C8C8CC;
  --text-inverse:   #FFFFFF;
  --text-placeholder: #A1A1AA;

  /* Accent — soft indigo-purple */
  --accent:            #6E7BFF;
  --accent-hover:      #5A68E5;
  --accent-soft:       rgba(110, 123, 255, 0.12);
  --accent-glow:       rgba(110, 123, 255, 0.22);
  --accent-gradient:   linear-gradient(135deg, #6E7BFF, #8C9AFF);

  /* Borders — barely visible, warm */
  --border-color:  #E8E7E4;
  --border-light:  #F2F1EE;
  --border-subtle: rgba(31, 31, 34, 0.04);
  --border-active: var(--accent);

  /* Semantic — muted, calm */
  --success:       #22A06B;
  --success-soft:  rgba(34, 160, 107, 0.10);
  --warning:       #D97706;
  --warning-soft:  rgba(217, 119, 6, 0.10);
  --error:         #DC2626;
  --error-soft:    rgba(220, 38, 38, 0.10);
  --info:          #6E7BFF;
  --info-soft:     rgba(110, 123, 255, 0.10);

  /* Frosted glass */
  --glass-bg:         rgba(255, 255, 255, 0.72);
  --glass-border:     rgba(31, 31, 34, 0.05);
  --glass-blur:       blur(20px);
  --glass-blur-sm:    blur(12px);

  /* Shadows — warm, soft, layered */
  --shadow-sm:        0 1px 2px rgba(31, 31, 34, 0.04);
  --shadow-md:        0 2px 8px rgba(31, 31, 34, 0.05);
  --shadow-lg:        0 8px 24px rgba(31, 31, 34, 0.08);
  --shadow-xl:        0 16px 48px rgba(31, 31, 34, 0.12);
  --shadow-glow:      0 0 16px var(--accent-glow);
  --shadow-inset:     inset 0 1px 2px rgba(31, 31, 34, 0.04);

  /* Radius */
  --radius-sm:  8px;
  --radius-md:  12px;
  --radius-lg:  16px;
  --radius-xl:  24px;
  --radius-full: 999px;

  /* Motion */
  --ease-smooth:    cubic-bezier(0.22, 1, 0.36, 1);
  --ease-snappy:    cubic-bezier(0.16, 1, 0.3, 1);
  --ease-bounce:    cubic-bezier(0.34, 1.56, 0.64, 1);
  --duration-fast:  150ms;
  --duration-normal: 250ms;
  --duration-slow:  400ms;

  /* Scrollbar */
  --scrollbar-thumb:       rgba(31, 31, 34, 0.12);
  --scrollbar-thumb-hover: rgba(31, 31, 34, 0.20);
  --scrollbar-track:       transparent;
}
```

### 2.3 Dark 主题变量

```css
html[data-theme="dark"] {
  /* Backgrounds — deep charcoal */
  --bg-body:       #1C1C1E;
  --bg-page:       #222225;
  --bg-card:       #2A2A2D;
  --bg-hover:      rgba(255, 255, 255, 0.05);
  --bg-active:     rgba(255, 255, 255, 0.08);
  --bg-selected:   rgba(140, 154, 255, 0.12);
  --bg-overlay:    rgba(28, 28, 30, 0.92);

  /* Text — warm, slightly desaturated */
  --text-primary:   #F5F5F7;
  --text-secondary: #A1A1AA;
  --text-tertiary:  #6E6E73;
  --text-muted:     #4A4A4C;
  --text-inverse:   #1C1C1E;
  --text-placeholder: #6E6E73;

  /* Accent — lighter indigo-purple for dark mode */
  --accent:            #8C9AFF;
  --accent-hover:      #A6B1FF;
  --accent-soft:       rgba(140, 154, 255, 0.15);
  --accent-glow:       rgba(140, 154, 255, 0.25);
  --accent-gradient:   linear-gradient(135deg, #8C9AFF, #A6B1FF);

  /* Borders */
  --border-color:  #3A3A3C;
  --border-light:  #2C2C2E;
  --border-subtle: rgba(255, 255, 255, 0.04);
  --border-active: var(--accent);

  /* Semantic — slightly lighter for dark */
  --success:       #34D399;
  --success-soft:  rgba(52, 211, 153, 0.12);
  --warning:       #FBBF24;
  --warning-soft:  rgba(251, 191, 36, 0.12);
  --error:         #F87171;
  --error-soft:    rgba(248, 113, 113, 0.12);
  --info:          #8C9AFF;
  --info-soft:     rgba(140, 154, 255, 0.12);

  /* Glass */
  --glass-bg:         rgba(42, 42, 45, 0.60);
  --glass-border:     rgba(255, 255, 255, 0.06);
  --glass-blur:       blur(20px);
  --glass-blur-sm:    blur(12px);

  /* Shadows — deeper, warm black */
  --shadow-sm:        0 1px 2px rgba(0, 0, 0, 0.25);
  --shadow-md:        0 2px 8px rgba(0, 0, 0, 0.30);
  --shadow-lg:        0 8px 24px rgba(0, 0, 0, 0.35);
  --shadow-xl:        0 16px 48px rgba(0, 0, 0, 0.45);
  --shadow-glow:      0 0 16px var(--accent-glow);
  --shadow-inset:     inset 0 1px 2px rgba(0, 0, 0, 0.25);

  /* Scrollbar */
  --scrollbar-thumb:       rgba(255, 255, 255, 0.10);
  --scrollbar-thumb-hover: rgba(255, 255, 255, 0.18);
}
```

### 2.4 色彩使用规则

| 变量 | 用途 | 禁止 |
|------|------|------|
| `--bg-body` | 页面底层背景 | 不要用于卡片、弹窗 |
| `--bg-page` | 顶栏、侧边栏、 elevated surfaces | 不要用于主内容区底色（那是 body） |
| `--bg-card` | 卡片、面板、对话框、抽屉 | 不要直接用于 body |
| `--text-primary` | 标题、正文、关键数据 | 不要用于辅助说明 |
| `--text-secondary` | 次要文本、标签、说明 | 不要用于正文主内容 |
| `--text-tertiary` | 占位、禁用、极次要信息 | 不要用于可交互文本 |
| `--accent` | 当前导航、主按钮、焦点环、链接 hover | 不要用于大面积背景或装饰 |
| `--accent-soft` | 当前项背景、hover 背景、tag 背景 | 不要替代 `--accent` 做文字 |
| `--border-color` | 卡片边框、输入框边框 | 不要使用深色或高对比边框 |
| `--shadow-lg` | 浮层、抽屉、对话框 | 不要在静态卡片上滥用 |

### 2.5 主题切换机制

- 根节点 `html` 通过 `data-theme="light" | "dark"` 切换。
- 默认跟随系统 `prefers-color-scheme`；用户手动选择后写入 `localStorage` 键 `szyg_theme`。
- 所有组件样式必须通过 CSS 变量引用，禁止在组件中写死十六进制颜色。
- **Solarized 主题在本次规范中废弃**，不再维护。迁移时移除 `html[data-theme="solarized"]` 相关代码。

---

## 3. 字体系统

### 3.1 字体栈

```css
--font-sans: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', 'Hiragino Sans GB',
             'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'SF Mono', 'Fira Code', 'JetBrains Mono', 'Menlo', 'Consolas', monospace;
```

- 中文优先使用系统字体（PingFang SC / Microsoft YaHei），保证渲染质量。
- 英文/数字回退到 Inter 或系统无衬线字体。
- 数字、表格、金额使用 `font-variant-numeric: tabular-nums` 保证对齐。

### 3.2 字号模数尺度

基于 **4px 网格 + 黄金比例**构建。标题字号按 1.25 倍进阶（接近黄金比例的 UI 简化），行高与字重保证中文可读性。

| Token | 字号 | 行高 | 字重 | 用途 |
|-------|------|------|------|------|
| `text-xs` | 12px | 1.6 (19.2px) | 400 | 标签、时间、辅助提示 |
| `text-sm` | 13px | 1.55 (20.15px) | 400 | 表单标签、菜单项、次要按钮 |
| `text-base` | 14px | 1.6 (22.4px) | 400 | 正文、表格内容 |
| `text-md` | 15px | 1.55 (23.25px) | 500 |  emphasized body, 选中项 |
| `text-lg` | 16px | 1.5 (24px) | 500 | 小标题、卡片标题 |
| `text-xl` | 20px | 1.35 (27px) | 600 | 页面标题、大数字 |
| `text-2xl` | 24px | 1.3 (31.2px) | 600 | 页面大标题 |
| `text-3xl` | 32px | 1.25 (40px) | 700 | 品牌/核心数据 |

### 3.3 字体使用规则

- 标题使用 `--text-primary` + 较高字重；正文使用 `--text-secondary` + 常规字重。
- 中文标题避免使用 `font-weight: 700` 以上，防止笔画过粗。
- 大标题字重 600，超大标题 700。
- 段落行高不低于 1.5，确保中文阅读舒适。
- 标签、时间等使用 `letter-spacing: 0.2px` 增加呼吸感；中文正文不使用字间距调整。

---

## 4. 间距系统

### 4.1 4px 基础网格

所有间距必须是 4px 的整数倍，保证视觉对齐与和谐。

| Token | 值 | 用途 |
|-------|-----|------|
| `space-1` | 4px | 图标与文本间距、最小间隙 |
| `space-2` | 8px | 紧密内联间距 |
| `space-3` | 12px | 按钮内边距、输入框内边距 |
| `space-4` | 16px | 卡片内部小间距、表单项间距 |
| `space-5` | 20px | 表单内边距 |
| `space-6` | 24px | 卡片内边距、内容块间距 |
| `space-8` | 32px | 模块间距 |
| `space-10` | 40px | 页面级间距 |
| `space-12` | 48px | 大模块间距 |
| `space-16` | 64px | 黄金比例进阶间距 |
| `space-20` | 80px | 页面 section 间距 |
| `space-24` | 96px | 超大间距 |

### 4.2 黄金比例应用

大尺度留白遵循 **1.618 比例** 递进：24px → 40px → 64px → 104px（可选）。

- 卡片内部 padding: 24px
- 卡片之间间距: 24px 或 40px
- 页面内容区与侧边栏内边距: 32px 或 40px
- 页面模块之间: 64px

### 4.3 布局间距规则

- **卡片内边距**：`24px`（标准）、`16px`（紧凑列表）。
- **页面内容区内边距**：`32px`（桌面）、`24px`（平板）、`16px`（手机）。
- **表单项间距**：`20px`（label + input 之间 8px）。
- **按钮内边距**：`8px 16px`（默认）；`6px 12px`（小）。
- **表格行高**：`56px`（标准行），`48px`（紧凑行）。

---

## 5. 圆角系统

| Token | 值 | 用途 |
|-------|-----|------|
| `radius-sm` | 8px | 按钮、输入框、小标签、菜单项 |
| `radius-md` | 12px | 卡片、对话框、下拉面板 |
| `radius-lg` | 16px | 大面板、浮层 |
| `radius-xl` | 24px | 营销卡片、特殊模块 |
| `radius-full` | 999px | 头像、标签 pill、开关 |

- 全局使用圆角，避免尖锐直角，营造温润感。
- 侧边栏、顶栏等结构性元素使用 `0` 或 `radius-sm` 的局部圆角（如菜单项），不使用大圆角。
- 浮层（对话框、抽屉）使用 `radius-lg` 或 `radius-md`。

---

## 6. 阴影与 elevation

### 6.1 阴影层级

| Token | 阴影 | 用途 |
|-------|------|------|
| `--shadow-sm` | 0 1px 2px rgba(31,31,34,0.04) | 静态卡片、按钮 resting |
| `--shadow-md` | 0 2px 8px rgba(31,31,34,0.05) | 卡片 hover、小浮层 |
| `--shadow-lg` | 0 8px 24px rgba(31,31,34,0.08) | 对话框、抽屉、下拉菜单 |
| `--shadow-xl` | 0 16px 48px rgba(31,31,34,0.12) | 模态框、全屏浮层 |
| `--shadow-glow` | 0 0 16px var(--accent-glow) | 焦点环、选中态 glow |
| `--shadow-inset` | inset 0 1px 2px rgba(31,31,34,0.04) | 输入框内阴影、凹陷表面 |

### 6.2 Elevation 规则

- Elevation 通过背景色 + 阴影共同表达，不单独依赖阴影。
- `--bg-body` → `--bg-page` → `--bg-card` → 浮层，逐层升高。
- 静态卡片使用 `--shadow-sm`；hover 时过渡到 `--shadow-md`。
- 浮层（dialog/drawer/dropdown）使用 `--shadow-lg` 或 `--shadow-xl`。
- 禁止使用多层阴影或彩色阴影（除 accent glow 外）。

---

## 7. 毛玻璃效果

### 7.1 使用场景

- 侧边栏背景：`--glass-bg` + `backdrop-filter: var(--glass-blur)`。
- 顶栏背景：当顶栏位于滚动内容上方时，使用毛玻璃制造通透感。
- 浮动面板：部分下拉菜单、提示浮层可使用小模糊。

### 7.2 规则

- 毛玻璃必须配合半透明背景，不能单独使用 `backdrop-filter`。
- 在深色模式下毛玻璃更克制（`--glass-bg: rgba(42,42,45,0.60)`），避免过亮。
- 性能考虑：滚动时避免大面积 backdrop-filter，必要时使用 will-change 提示或降级为纯色背景。
- 低功耗/老年模式可禁用毛玻璃，降级为 `--bg-page`。

---

## 8. 动效系统

### 8.1 缓动函数

| Token | 曲线 | 用途 |
|-------|------|------|
| `--ease-smooth` | cubic-bezier(0.22, 1, 0.36, 1) | 大多数过渡、hover、焦点 |
| `--ease-snappy` | cubic-bezier(0.16, 1, 0.3, 1) | 按钮按下、状态切换 |
| `--ease-bounce` | cubic-bezier(0.34, 1.56, 0.64, 1) | 极少数活泼反馈（如成功勾选） |

### 8.2 时长阶梯

| Token | 值 | 用途 |
|-------|-----|------|
| `--duration-fast` | 150ms | 按钮 hover、颜色变化、焦点环 |
| `--duration-normal` | 250ms | 卡片 hover、下拉展开、侧边栏折叠 |
| `--duration-slow` | 400ms | 页面切换、对话框进入、抽屉滑出 |

### 8.3 动效规则

- 所有可交互元素必须有 hover/focus 反馈，但反馈必须柔和。
- 颜色、边框、阴影、transform 过渡必须分开定义，避免统一 `all` 导致性能问题。
- 按钮按下：`transform: scale(0.98)` + 150ms ease-snappy。
- 卡片 hover：`translateY(-1px)` + shadow 提升，250ms。
- 页面/列表入场：`fadeSlideUp` 400ms，错落（stagger）50ms。
- 禁止使用弹性/弹跳动画做导航或布局变化，避免眩晕感。

### 8.4 标准动画关键帧

```css
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: scale(1); }
}

@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
```

- 通用入场类：`.animate-in` = `fadeSlideUp 0.4s var(--ease-smooth) both`。
- 加载骨架屏使用 `shimmer` 动画，宽度 200% 渐变。

---

## 9. 图标系统

### 9.1 图标库

- 使用 `@element-plus/icons-vue` 作为默认图标库。
- 所有图标使用 `outline` 风格或线性图标，保持纤细、安静。
- 禁止使用彩色、填充、3D、阴影图标。

### 9.2 图标尺寸

| Token | 尺寸 | 用途 |
|-------|------|------|
| `icon-xs` | 12px | 标签内小图标 |
| `icon-sm` | 14px | 按钮、菜单项 |
| `icon-md` | 16px | 标准按钮、表单、表格操作 |
| `icon-lg` | 20px | 标题旁图标、空状态图标 |
| `icon-xl` | 24px | 空状态、特性图标 |

### 9.3 图标规则

- 图标颜色默认继承 `--text-secondary`；hover 时过渡为 `--text-primary` 或 `--accent`（仅当图标为操作时）。
- 图标与文字间距：`8px`（默认）。
- 图标按钮必须有 `aria-label` 或 tooltip 说明。

---

## 10. CSS 变量命名约定

- 所有设计 token 以 `--` 开头，使用 kebab-case。
- 语义分类：
  - 背景：`--bg-*`
  - 文字：`--text-*`
  - 边框：`--border-*`
  - 强调：`--accent-*`
  - 阴影：`--shadow-*`
  - 圆角：`--radius-*`
  - 动效：`--ease-*`, `--duration-*`
- 禁止在组件样式中写死颜色、字号、间距。所有值必须引用 token。
- 必要时在组件中定义局部变量，但局部变量必须由全局 token 派生。

---

## 11. 可访问性

- 正文与背景对比度至少 **4.5:1**。
- 大号文本/图标对比度至少 **3:1**。
- 焦点环必须可见：`box-shadow: 0 0 0 2px var(--accent-soft), 0 0 0 4px var(--accent)` 或等效方案。
- 所有交互元素必须支持键盘导航。
- 减少动画偏好（`prefers-reduced-motion: reduce`）下，禁用非必要动画。
