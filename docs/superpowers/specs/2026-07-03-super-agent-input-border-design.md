# 超级员工输入框边框调整设计

## 背景

在「超级员工」页面（`web/src/pages/SuperAgent.vue`）的欢迎态输入框 `.welcome-input-box` 当前存在两层视觉边界：

1. 外层容器有一圈浅色描边（`border: 1px solid var(--border-light)`），在浅色主题下接近白色。
2. 内层 `el-textarea` 仅在聚焦时出现蓝色边框/光晕。

用户希望去掉外层白色描边，仅保留中间的蓝色框。

## 目标

- 去掉 `.welcome-input-box` 外层容器的浅色/白色描边。
- 让内部输入框本身常驻显示蓝色边框，成为视觉上的「中间蓝色框」。

## 方案

采用「方案 A」：

1. 将 `.welcome-input-box` 的 `border` 设为 `none`。
2. 在 `.welcome-input-box :deep(.el-textarea__inner)` 中增加 `border: 1px solid var(--accent)`。
3. 将内层 textarea 的 `border-radius` 从默认 `8px` 调整为 `20px`，使其在 28px 大圆角容器内更协调。
4. 保留 `tech-theme.css` 中定义的聚焦蓝色光晕，聚焦时蓝色边框效果更突出。

## 影响范围

- 仅影响 `web/src/pages/SuperAgent.vue` 中 `.welcome-input-box` 及其内部 `.el-textarea__inner` 的样式。
- 不影响聊天态底部的 `.input-area` 输入框。
- 不影响 Element Plus 全局主题覆盖。

## 验收标准

- [ ] 欢迎页输入框外圈浅色描边消失。
- [ ] 内部输入框在非聚焦状态下可见蓝色边框。
- [ ] 聚焦时输入框仍保持蓝色视觉反馈。
- [ ] 页面无布局错位或样式冲突。
