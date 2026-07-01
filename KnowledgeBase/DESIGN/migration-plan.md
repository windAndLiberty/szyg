# 🔄 迁移计划：从现有主题到全局设计系统

> 本文件说明如何将现有 `@d:\szyg\web\src\style.css` 与 `@d:\szyg\web\src\tech-theme.css` 逐步迁移到本设计系统定义的目标态。
> 迁移按阶段进行，每阶段完成后应进行视觉回归检查，避免一次性大面积改动导致不可控。

---

## 1. 迁移原则

1. **先 token，后组件**：先统一 CSS 变量，再调整组件覆盖。
2. **先框架，后页面**：先完成 AppLayout、全局样式，再逐个页面审计。
3. **禁止双轨运行**：迁移完成后删除旧变量和旧覆盖，避免旧 token 与新 token 同时存在。
4. **渐进式**：允许中间态存在，但每个中间态必须向下兼容主题切换。

---

## 2. 阶段划分

### 阶段 1：重构 `style.css` 变量系统

**目标**：将 `style.css` 中的变量与 `design-system.md` 对齐。

#### 2.1 替换核心色彩变量

| 旧变量（或当前值） | 新变量 / 目标值 | 说明 |
|---------------------|------------------|------|
| `--bg-body: #f8f7f5` | `#F9F8F6` | 更暖的米白 |
| `--text-primary: #2c2c2c` | `#1F1F22` | 更暖的近黑 |
| `--text-secondary: #666666` | `#6E6E73` | 更中性的暖灰 |
| `--text-tertiary: #999999` | `#A1A1AA` | 更柔和的灰 |
| `--accent: #6b7280` | `#6E7BFF` | 改为 soft indigo-purple |
| `--accent-hover: #4b5563` | `#5A68E5` | 对应深一点的 indigo |
| `--accent-soft: rgba(107,114,128,0.08)` | `rgba(110,123,255,0.12)` | 新 accent 的柔和版 |
| `--border-color: #ececea` | `#E8E7E4` | 更暖的边框 |
| `--shadow-card` 等 | 使用新 `--shadow-md/lg` | 统一命名 |

#### 2.2 移除 Solarized 主题

- 删除 `html[data-theme="solarized"]` 整个代码块。
- 删除主题切换器中 Solarized 选项。
- 更新 `AppLayout.vue` 中 `themeLabels` 对象。

#### 2.3 更新 Dark 主题

- 将 dark 模式 accent 从 `#9ca3af` 改为 `#8C9AFF`。
- 调整背景色从 `#1c1c1e` / `#242426` / `#2c2c2e` 到 `#1C1C1E` / `#222225` / `#2A2A2D`。
- 统一文字变量为 `#F5F5F7` / `#A1A1AA` / `#6E6E73`。

#### 2.4 清理旧别名

- 保留必要的向后兼容别名（如 `--bg-canvas` → `--bg-body`），但新增变量命名统一后应逐步弃用。
- 在 `style.css` 底部添加注释标记 deprecated aliases，提醒后续删除。

#### 2.5 新增设计系统变量

- 添加 `--accent-glow`、`--shadow-glow`、`--shadow-inset` 等新变量。
- 添加排版 token（如 `--font-sans`）和间距 token（如 `--space-6`）到 `:root`。
- 建议最终拆分为 `tokens.css` 独立文件，由 `style.css` 导入。

---

### 阶段 2：重构 `tech-theme.css` 组件覆盖

**目标**：使 Element Plus 组件形态与 `component-specs.md` 完全一致。

#### 2.1 按钮覆盖

- 更新 `.el-button--primary` 背景为 `var(--accent)`，文字为 `var(--text-inverse)`。
- 调整 `.el-button--default` 背景为 `var(--bg-hover)`，文字为 `var(--text-secondary)`。
- 统一按钮圆角为 8px，字重 500。
- 添加 active 态 `scale(0.98)`。

#### 2.2 输入框覆盖

- 统一输入框高度 36px，内边距 10px 12px。
- 调整 focus 环为 `0 0 0 3px var(--accent-soft)`（当前是 2px）。
- 确保 `.el-input__wrapper` 无边框阴影，只保留 border。

#### 2.3 表格覆盖

- 移除纵向边框，只保留行底边框。
- 表头文字改为 `text-xs` + `var(--text-secondary)` + 字重 600。
- 行高改为 56px（标准）。

#### 2.4 卡片覆盖

- 统一卡片内边距 24px，圆角 12px。
- 添加 hover 动效：`translateY(-1px)` + `var(--shadow-md)`，250ms。

#### 2.5 菜单 / 标签 / 对话框覆盖

- 调整导航项高度为 40px，active 背景为 `var(--accent-soft)`。
- 标签统一为 pill（圆角 999px）。
- 对话框圆角改为 16px，阴影 `var(--shadow-xl)`。

---

### 阶段 3：重构 `AppLayout.vue`

**目标**：使应用外壳符合 `layout-framework.md` 规范。

#### 3.1 侧边栏调整

- 宽度从 220px 改为 **200px**；折叠状态从 56px 改为 **64px**。
- 背景改为 `var(--glass-bg)` + `backdrop-filter: blur(20px)`。
- 品牌区高度改为 56px，与顶栏对齐。
- 导航项高度改为 40px，内边距 10px 12px，圆角 8px。
- 移除或简化分组箭头（保留分组标题但不显示折叠图标，或改为更 subtle 的指示）。
- 底部折叠按钮移到 sidebar-footer，高度 48px。

#### 3.2 顶栏调整

- 高度从 48px 改为 **56px**。
- 内边距改为 0 24px。
- 背景默认 `var(--bg-page)`，滚动后切换为毛玻璃 + 阴影。
- 右侧工具区统一间距 16px。
- 添加响应式：手机端显示汉堡菜单按钮。

#### 3.3 内容区调整

- 内边距改为 32px（桌面）/ 24px（平板）/ 16px（手机）。
- 使用 CSS 变量响应式或 Vue 监听窗口宽度切换 class。

---

### 阶段 4：建立全局工具类

**目标**：提供常用布局与排版工具类，减少重复样式。

建议在 `style.css` 中新增：

```css
/* Typography */
.text-xs { font-size: 12px; line-height: 1.6; }
.text-sm { font-size: 13px; line-height: 1.55; }
.text-base { font-size: 14px; line-height: 1.6; }
.text-md { font-size: 15px; line-height: 1.55; font-weight: 500; }
.text-lg { font-size: 16px; line-height: 1.5; font-weight: 600; }
.text-xl { font-size: 20px; line-height: 1.35; font-weight: 600; }
.text-2xl { font-size: 24px; line-height: 1.3; font-weight: 600; }
.text-3xl { font-size: 32px; line-height: 1.25; font-weight: 700; }

/* Spacing */
.p-4  { padding: 16px; }
.p-6  { padding: 24px; }
.p-8  { padding: 32px; }
.m-6  { margin: 24px; }
.m-8  { margin: 32px; }
.m-10 { margin: 40px; }

/* Grid */
.app-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 24px;
}

/* Animation helpers */
.animate-in { animation: fadeSlideUp 0.4s var(--ease-smooth) both; }
.animate-in-scale { animation: scaleIn 0.4s var(--ease-smooth) both; }

/* Tabular numbers */
.tabular-nums { font-variant-numeric: tabular-nums; font-feature-settings: 'tnum'; }
```

- 也可选择引入 Tailwind-like 工具类，但优先使用 CSS 变量 + 少量语义化类名，避免类名爆炸。

---

### 阶段 5：页面逐个审计

**目标**：确保所有业务页面符合设计系统。

#### 5.1 审计清单

对每个 `.vue` 页面（位于 `web/pages/`）执行：

- [ ] 是否使用 `AppLayout` 作为外壳？
- [ ] 是否使用 CSS 变量而非硬编码颜色？
- [ ] 卡片是否使用标准卡片样式（内边距 24px、圆角 12px）？
- [ ] 按钮是否使用 Primary / Secondary / Danger 规范？
- [ ] 表格是否使用标准表格样式（行高 56px、无纵向边框）？
- [ ] 空状态是否使用标准空状态组件？
- [ ] 页面标题、模块间距是否符合 32px/40px 节奏？
- [ ] 是否使用了统一的字体层级（`text-xs/sm/base/lg/xl`）？
- [ ] 动效是否使用 `--ease-smooth` / `--duration-*`？

#### 5.2 页面优先级

建议按以下顺序迁移：

1. `SuperAgent.vue`（当前首页，用户高频使用）
2. `Dashboard.vue`（若后续启用）
3. 其他业务页面（Agents、Chat、Hub、Publisher 等）

---

### 阶段 6：移除旧主题与 Solarized

**目标**：清理历史代码，保证规范唯一性。

- 删除 `html[data-theme="solarized"]` 样式块。
- 从 `AppLayout.vue` 主题切换器中移除 Solarized。
- 删除 `style.css` 中已废弃的 legacy alias 注释（确认无组件引用后）。
- 检查 `localStorage` 中已保存的 `solarized` 主题，启动时自动回退为 `light` 或 `dark`（跟随系统）。

---

## 3. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `@d:\szyg\web\src\style.css` | 大幅修改 | 替换变量、更新主题、新增工具类 |
| `@d:\szyg\web\src\tech-theme.css` | 大幅修改 | 调整组件覆盖以匹配规范 |
| `@d:\szyg\web\src\components\AppLayout.vue` | 大幅修改 | 调整外壳尺寸、布局、响应式 |
| `web/pages/*.vue` | 逐个审计 | 按阶段 5 清单调整 |
| `web/src/main.js` | 可能新增 | 如需拆分 `tokens.css` 则调整导入顺序 |

---

## 4. 风险与回退策略

| 风险 | 回退策略 |
|------|----------|
| 变量替换导致部分页面颜色异常 | 保留旧 alias 作为 fallback，直到页面审计完成 |
| Element Plus 升级导致覆盖失效 | 将覆盖集中到 `tech-theme.css`，升级后集中修复 |
| 用户不习惯新主题 | 保留主题切换入口，提供 Light / Dark 两套 |
| 性能问题（毛玻璃） | 提供 `prefers-reduced-transparency` 降级，关闭 blur |

---

## 5. 验收标准

- [ ] 所有页面在 Light / Dark 模式下视觉一致，无突兀色差。
- [ ] 侧边栏 200px / 64px 折叠、顶栏 56px、内容区 32px padding 正确。
- [ ] 按钮、输入、卡片、表格、标签、菜单、对话框形态与 `component-specs.md` 一致。
- [ ] 无 Solarized 主题残留。
- [ ] 无硬编码颜色/字号（除 CSS 变量定义外）。
- [ ] 动效柔和、无抖动、无过度弹跳。
- [ ] 在 1280px / 1024px / 768px / 480px 断点下布局正常。

---

## 6. 建议的下一步

1. 由 Elite_Coder 创建功能分支 `feat/effie-design-system`。
2. 按阶段 1 开始修改 `style.css`。
3. 每完成一个阶段，运行 `npm run dev` 并在浏览器中截图对比。
4. 阶段 3 完成后通知 QA_Guardian 进行视觉回归检查。
5. 所有阶段完成后合并到主分支，并更新本迁移计划为“已完成”。
