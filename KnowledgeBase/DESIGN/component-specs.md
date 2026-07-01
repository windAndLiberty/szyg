# 🧩 全局组件规范 (Global Component Specifications)

> 本文件定义域灵系统中所有可复用 UI 组件的精确形态。实现时必须通过 Element Plus 二次封装 + CSS 变量覆盖，禁止在业务代码中重写样式。

---

## 1. 按钮 (Button)

### 1.1 按钮类型

| 类型 | 样式 | 用途 |
|------|------|------|
| **Primary** | `var(--accent)` 背景，白色文字 | 页面主要操作（创建、保存、发布） |
| **Secondary** | `var(--bg-hover)` 背景，`var(--text-secondary)` 文字 | 次要操作、取消、关闭 |
| **Ghost** | 透明背景，`var(--text-secondary)` 文字 | 低优先级操作、图标旁辅助 |
| **Danger** | `var(--error-soft)` 背景，`var(--error)` 文字 | 删除、断开、危险操作 |
| **Icon** | 仅图标，无文字 | 工具栏操作 |

### 1.2 尺寸

| 尺寸 | 高度 | 内边距 | 字号 | 圆角 |
|------|------|--------|------|------|
| Large | 40px | 12px 20px | 14px | 8px |
| Default | 36px | 10px 16px | 14px | 8px |
| Small | 32px | 8px 12px | 13px | 6px |

### 1.3 交互状态

| 状态 | 变化 |
|------|------|
| Hover | 背景加深/变浅 8%，`translateY(-0.5px)`，150ms |
| Active / Press | `transform: scale(0.98)`，150ms ease-snappy |
| Focus | `box-shadow: 0 0 0 2px var(--accent-soft)` |
| Disabled | 背景 `var(--bg-hover)`，文字 `var(--text-muted)`，cursor not-allowed，无 hover 效果 |
| Loading | 按钮宽度不变，文字替换为 spinner，spinner 颜色与文字色一致 |

### 1.4 设计细节

- Primary 按钮阴影：`var(--btn-shadow)`（定义在 `design-system.md` 中，值为 `0 2px 8px var(--accent-glow)`）。
- 按钮文字字重：500。
- 图标按钮尺寸：容器 32px，图标 16px，内边距 8px。
- 按钮组间距：12px。
- 禁止在按钮中使用渐变背景（除非规范特别说明）。

---

## 2. 输入框 (Input)

### 2.1 标准输入框

| 属性 | 值 |
|------|-----|
| 高度 | 36px（默认）/ 40px（大）/ 32px（小） |
| 内边距 | 10px 12px |
| 背景 | `var(--input-bg)`（Light: #F5F4F2；Dark: #2C2C2E） |
| 边框 | 1px solid `var(--border-color)` |
| 圆角 | 8px |
| 字号 | 14px |
| 文字颜色 | `var(--text-primary)` |
| 占位符颜色 | `var(--text-placeholder)` |

### 2.2 状态

| 状态 | 样式 |
|------|------|
| Hover | 边框颜色变为 `var(--text-tertiary)` |
| Focus | 边框颜色变为 `var(--accent)`，`box-shadow: 0 0 0 3px var(--accent-soft)` |
| Error | 边框颜色变为 `var(--error)`，背景 `var(--error-soft)` |
| Disabled | 背景 `var(--bg-hover)`，文字 `var(--text-muted)`，边框 `var(--border-light)` |
| Read-only | 背景 `var(--bg-hover)`，无边框焦点效果 |

### 2.3 前缀/后缀图标

- 图标颜色：`var(--text-tertiary)`，focus 时不改变。
- 图标与文字间距：8px。
- 图标尺寸：16px。

### 2.4 文本域 (Textarea)

- 最小高度：80px（默认），内边距 12px。
- 行高：1.6。
- 圆角 8px，边框与输入框一致。
- 右下角可拖动，但建议提供固定高度或最大高度。

---

## 3. 选择器 (Select / Dropdown)

### 3.1 Select 输入框

- 外观与标准 Input 完全一致。
- 下拉箭头图标：16px，`var(--text-tertiary)`，展开时旋转 180°，200ms。

### 3.2 下拉面板

| 属性 | 值 |
|------|-----|
| 背景 | `var(--bg-card)` |
| 边框 | 1px solid `var(--border-light)` |
| 圆角 | `var(--radius-md)` (12px) |
| 阴影 | `var(--shadow-lg)` |
| 内边距 | 6px |
| 最大高度 | 240px |
| 滚动条 | 4px |

### 3.3 选项项

| 属性 | 值 |
|------|-----|
| 高度 | 36px |
| 内边距 | 0 12px |
| 圆角 | 6px |
| 默认颜色 | `var(--text-secondary)` |
| Hover | `var(--bg-hover)`，文字 `var(--text-primary)` |
| Selected | 文字 `var(--accent)`，背景 `var(--accent-soft)`，字重 500 |
| Disabled | 文字 `var(--text-muted)` |

---

## 4. 卡片 (Card)

### 4.1 标准卡片

已在 `layout-framework.md` 中定义，此处补充：

| 属性 | 值 |
|------|-----|
| 背景 | `var(--bg-card)` |
| 边框 | 1px solid `var(--border-light)` |
| 圆角 | 12px |
| 阴影 | `var(--shadow-sm)` |
| 内边距 | 24px |
| Hover | `var(--shadow-md)` + `translateY(-1px)`，250ms |

### 4.2 卡片变体

| 变体 | 说明 |
|------|------|
| **Flat** | 无阴影，仅边框，用于列表项或嵌套面板 |
| **Hoverable** | 默认带阴影，hover 提升（默认卡片） |
| **Glass** | 背景 `var(--glass-bg)` + 模糊，用于浮层/覆盖卡片 |
| **Compact** | 内边距 16px，用于密集列表 |

### 4.3 卡片 Header

- 高度：自动，底部间距 16px。
- 左侧：标题 + 可选副标题。
- 右侧：操作按钮（图标按钮或 small 按钮）。
- 标题：`text-base`（14px），字重 600。
- 副标题：`text-xs`（12px），颜色 `var(--text-tertiary)`，间距 4px。

---

## 5. 表格 (Table)

### 5.1 表格整体

| 属性 | 值 |
|------|-----|
| 背景 | 透明（表格本身无背景） |
| 表头背景 | `var(--table-header-bg)`（Light: #F8F7F5；Dark: rgba(255,255,255,0.03)） |
| 表头文字 | `var(--text-secondary)`，`text-xs`（12px），字重 600，全大写可选 |
| 行高 | 56px（标准）/ 48px（紧凑） |
| 边框 | 仅行底部 1px `var(--border-light)`，无纵向边框 |
| 行 hover | `var(--bg-hover)` |
| 选中行 | `var(--bg-selected)` |

### 5.2 单元格

| 属性 | 值 |
|------|-----|
| 内边距 | 12px 16px |
| 对齐 | 默认左对齐；数字/状态右对齐或居中 |
| 文字颜色 | `var(--text-primary)`（数据）/ `var(--text-secondary)`（次要） |
| 字号 | 14px |

### 5.3 表格操作

- 行内操作：hover 时显示图标按钮（编辑、删除），默认隐藏，避免视觉噪音。
- 操作图标尺寸：16px，颜色 `var(--text-tertiary)`，hover `var(--text-primary)`。
- 批量操作栏：位于表格上方，使用 Secondary 按钮，间距 12px。

### 5.4 空表格

- 表格无数据时显示空状态（见 11 节），不显示表头或分页。

---

## 6. 标签 (Tag)

### 6.1 标准标签

| 属性 | 值 |
|------|-----|
| 高度 | 24px（默认）/ 20px（小） |
| 内边距 | 4px 10px（默认）/ 2px 8px（小） |
| 圆角 | 999px（pill） |
| 字号 | 12px |
| 字重 | 500 |

### 6.2 语义变体

| 变体 | 背景 | 文字 |
|------|------|------|
| Default | `var(--bg-hover)` | `var(--text-secondary)` |
| Primary | `var(--accent-soft)` | `var(--accent)` |
| Success | `var(--success-soft)` | `var(--success)` |
| Warning | `var(--warning-soft)` | `var(--warning)` |
| Error | `var(--error-soft)` | `var(--error)` |
| Info | `var(--info-soft)` | `var(--info)` |

- 所有标签使用 pill 形状，不使用方形标签。
- 可删除标签：右侧带 14px 关闭图标，hover 时图标颜色加深。

---

## 7. 菜单 (Menu / Navigation)

### 7.1 侧边栏导航项

已在 `layout-framework.md` 中定义。补充：

- 导航项高度：40px。
- 圆角：8px。
- 图标 16px，文字 14px，间距 12px。
- active 态：背景 `var(--accent-soft)`，文字 `var(--accent)`，字重 500。
- hover 态：背景 `var(--bg-hover)`，文字 `var(--text-primary)`。

### 7.2 上下文菜单 / 下拉菜单

| 属性 | 值 |
|------|-----|
| 背景 | `var(--bg-card)` |
| 边框 | 1px solid `var(--border-light)` |
| 圆角 | 12px |
| 阴影 | `var(--shadow-lg)` |
| 内边距 | 6px |
| 项高度 | 36px |
| 项内边距 | 0 12px |
| 项圆角 | 6px |
| 项默认颜色 | `var(--text-secondary)` |
| 项 hover | `var(--bg-hover)` + `var(--text-primary)` |
| 项 active | `var(--accent-soft)` + `var(--accent)` |
| 分割线 | 1px solid `var(--border-light)`，上下间距 4px |

---

## 8. 对话框 (Dialog)

### 8.1 标准对话框

| 属性 | 值 |
|------|-----|
| 背景 | `var(--bg-card)` |
| 边框 | 1px solid `var(--border-light)` |
| 圆角 | 16px |
| 阴影 | `var(--shadow-xl)` |
| 最小宽度 | 400px |
| 最大宽度 | 560px（默认）/ 720px（大）/ 360px（小） |
| 内边距 | 24px（body）/ 20px 24px（header）/ 16px 24px（footer） |
| 遮罩 | `var(--bg-overlay)`，带 backdrop-filter blur(2px) |

### 8.2 动画

- 进入：`scaleIn` 0.3s + `fadeIn` 0.2s，使用 `--ease-smooth`。
- 退出：反向，0.2s。
- 遮罩：`fadeIn` 0.2s。

### 8.3 Header / Footer

- Header：标题 `text-lg`（16px），字重 600；关闭按钮 24px 图标，位于右侧。
- Footer：按钮右对齐，间距 12px；主操作在右，次要操作在左。
- 可滚动 body：最大高度 `calc(80vh - 120px)`，滚动条 4px。

---

## 9. 抽屉 (Drawer)

### 9.1 标准抽屉

| 属性 | 值 |
|------|-----|
| 宽度 | 400px（默认）/ 560px（宽）/ 320px（窄） |
| 背景 | `var(--bg-page)` |
| 边框 | 无（左侧/右侧自然分隔） |
| 阴影 | `var(--shadow-xl)` |
| 圆角 | 左侧抽屉：右侧圆角 16px；右侧抽屉：左侧圆角 16px |
| 内边距 | 24px |

### 9.2 动画

- 进入：从对应方向滑入，400ms `--ease-smooth`。
- 退出：滑出，250ms。

### 9.3 Header

- 高度：56px。
- 标题：`text-lg`（16px），字重 600。
- 关闭按钮：顶部右侧，24px 图标。

---

## 10. 标签页 (Tabs)

### 10.1 标准标签页

| 属性 | 值 |
|------|-----|
| 容器 | 无背景，底部 1px `var(--border-light)` |
| 项高度 | 40px |
| 项内边距 | 0 16px |
| 默认颜色 | `var(--text-tertiary)` |
| Hover | `var(--text-secondary)` |
| Active | `var(--text-primary)`，字重 600 |
| 激活指示条 | 2px `var(--accent)`，位于底部，圆角 1px |
| 过渡 | 200ms `--ease-smooth` |

### 10.2 卡片式标签页

- 用于卡片内部切换内容。
- 背景：`var(--bg-hover)`，圆角 8px，padding 4px。
- 项：圆角 6px，active 背景 `var(--bg-card)`，阴影 `var(--shadow-sm)`。

---

## 11. 空状态 (Empty State)

### 11.1 标准空状态

- 容器：flex 居中，`min-height: 320px`。
- 图标：48px 线性图标，颜色 `var(--text-tertiary)`，底部间距 16px。
- 标题：`text-base`（14px），字重 500，颜色 `var(--text-primary)`。
- 描述：`text-sm`（13px），颜色 `var(--text-secondary)`，最大宽度 320px，居中对齐，底部间距 16px。
- 操作：一个 Primary 或 Secondary 按钮。

### 11.2 变体

| 变体 | 图标颜色 | 说明 |
|------|----------|------|
| Default | `var(--text-tertiary)` | 无数据、待创建 |
| Search | `var(--text-tertiary)` | 搜索无结果 |
| Error | `var(--error)` | 加载失败 |
| Success | `var(--success)` | 操作完成（可选） |

---

## 12. 加载状态 (Loading)

### 12.1 全局加载

- 全屏遮罩：背景 `var(--loading-mask-bg)`，带 `backdrop-filter: blur(2px)`。
- Spinner：24px，颜色 `var(--accent)`，动画 rotate 1s linear infinite。
- 可选文字：`text-sm`，颜色 `var(--text-secondary)`，间距 12px。

### 12.2 局部加载

- 按钮加载：按钮内显示 spinner，文字隐藏，按钮宽度不变。
- 卡片加载：骨架屏覆盖卡片内容区域。
- 表格加载：表头保留，行区域显示 5 行骨架屏。

### 12.3 骨架屏 (Skeleton)

| 属性 | 值 |
|------|-----|
| 背景 | `var(--border-light)` |
| shimmer 高亮 | `linear-gradient(90deg, transparent, var(--border-color), transparent)` |
| 圆角 | 继承容器（卡片 12px，文本行 4px，头像 999px） |
| 动画 | `shimmer` 1.5s infinite |
| 行高 | 12px（文本），24px（按钮/标签），40px（输入框） |

---

## 13. 状态指示器 (Status Indicators)

### 13.1 状态点

| 尺寸 | 直径 | 用途 |
|------|------|------|
| sm | 6px | 表格内、标签内 |
| md | 8px | 列表项、卡片 header |
| lg | 10px | 页面级状态 |

- 形状：圆形。
- 颜色：默认 `var(--success)` / `var(--warning)` / `var(--error)` / `var(--text-tertiary)`（离线）。
- 在线/运行中可添加 pulse 动画：

```css
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(34, 160, 107, 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(34, 160, 107, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 160, 107, 0); }
}
```

### 13.2 状态标签

- 使用 Tag 组件，语义变体对应状态。
- 文字 + 状态点组合：状态点 6px，右侧间距 6px。

---

## 14. 开关 (Switch)

| 属性 | 值 |
|------|-----|
| 宽度 | 40px |
| 高度 | 22px |
| 圆角 | 999px |
| 默认轨道 | `var(--border-color)` |
| 选中轨道 | `var(--accent)` |
| 滑块 | `var(--text-inverse)` |
| 滑块尺寸 | 18px |
| 过渡 | 200ms `--ease-smooth` |
| 禁用 | 轨道 `var(--bg-hover)`，滑块 `var(--text-muted)` |

- 开关左侧可放置标签文字，右侧可放置辅助说明。

---

## 15. 复选框与单选框 (Checkbox / Radio)

| 属性 | 值 |
|------|-----|
| 尺寸 | 16px × 16px |
| 边框 | 1px solid `var(--border-color)` |
| 圆角 | 4px（checkbox）/ 999px（radio） |
| 背景 | `var(--bg-card)` |
| 选中背景 | `var(--accent)` |
| 选中图标 | `var(--text-inverse)` |
| 焦点 | `box-shadow: 0 0 0 3px var(--accent-soft)` |
| 标签间距 | 8px |
| 标签颜色 | `var(--text-secondary)`；选中或 hover 时 `var(--text-primary)` |

---

## 16. 提示与反馈 (Alert / Toast)

### 16.1 页面内 Alert

| 属性 | 值 |
|------|-----|
| 背景 | 语义色 soft 变体（如 `var(--success-soft)`） |
| 边框 | 左侧 3px 实线（语义色） |
| 圆角 | 12px |
| 内边距 | 12px 16px |
| 图标 | 16px，语义色 |
| 标题 | `text-sm`，字重 500，语义色 |
| 描述 | `text-sm`，`var(--text-secondary)` |

### 16.2 Toast 通知

| 属性 | 值 |
|------|-----|
| 位置 | 顶部居中，距顶 24px |
| 背景 | `var(--bg-card)` |
| 边框 | 1px solid `var(--border-light)` |
| 圆角 | 12px |
| 阴影 | `var(--shadow-lg)` |
| 内边距 | 12px 16px |
| 最大宽度 | 400px |
| 动画 | 进入 `fadeSlideUp` 300ms；退出 `fadeOut` 200ms |
| 自动关闭 | 3s（默认），5s（错误） |

---

## 17. 分页 (Pagination)

| 属性 | 值 |
|------|-----|
| 按钮尺寸 | 32px × 32px |
| 按钮背景 | `var(--bg-hover)` |
| 按钮边框 | 1px solid `var(--border-light)` |
| 按钮圆角 | 8px |
| 默认颜色 | `var(--text-secondary)` |
| Hover | `var(--bg-active)`，颜色 `var(--text-primary)` |
| Active | 背景 `var(--accent)`，颜色 `var(--text-inverse)`，边框 `var(--accent)` |
| 禁用 | 背景 `var(--bg-hover)`，颜色 `var(--text-muted)` |
| 间距 | 8px |

---

## 18. 面包屑 (Breadcrumb)

| 属性 | 值 |
|------|-----|
| 字号 | `text-sm` (13px) |
| 默认颜色 | `var(--text-secondary)` |
| Hover | `var(--text-primary)` |
| 当前页 | `var(--text-primary)`，字重 500 |
| 分隔符 | `>`，`var(--text-muted)`，间距 8px |

---

## 19. 头像 (Avatar)

| 属性 | 值 |
|------|-----|
| 尺寸 | 28px（默认）/ 24px（小）/ 32px（大）/ 40px（特大） |
| 圆角 | 999px |
| 背景 | `var(--accent-soft)` |
| 文字/图标颜色 | `var(--accent)` |
| 边框 | 无（默认）；在线状态可在右下角加 8px 状态点 |

---

## 20. 工具提示 (Tooltip)

| 属性 | 值 |
|------|-----|
| 背景 | `var(--bg-card)` |
| 边框 | 1px solid `var(--border-light)` |
| 圆角 | 8px |
| 阴影 | `var(--shadow-md)` |
| 内边距 | 6px 10px |
| 字号 | 12px |
| 颜色 | `var(--text-secondary)` |
| 箭头 | 与 tooltip 背景一致，带 1px 边框 |

---

## 21. 实现约束

- 所有组件必须通过 CSS 变量覆盖 Element Plus 默认样式，禁止在业务组件中写死颜色或尺寸。
- 按钮、输入、卡片等高频组件建议封装为 `BaseButton.vue`、`BaseCard.vue` 等原子组件，避免直接依赖 Element Plus 类名。
- 组件 hover/focus 动效必须统一使用 `design-system.md` 中定义的 easing 与 duration token。
- 所有图标尺寸、间距必须遵循本规范，禁止随意放大图标以“更醒目”。
