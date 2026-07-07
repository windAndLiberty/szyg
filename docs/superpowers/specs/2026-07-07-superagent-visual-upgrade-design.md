# SuperAgent 页面视觉升级 — 设计规格

> 日期：2026-07-07 | 风格：精致专业风 | 状态：已确认

---

## 目标

对超级员工页面进行整体视觉升级，解决输入框高度不足问题，提升整体设计品质。

## 范围

三文件改动：
- `szyg-frontend/src/pages/SuperAgent.tsx` — 输入框系统、间距系统
- `szyg-frontend/src/components/superagent/WelcomeState.tsx` — 欢迎页输入区、品牌区、案例卡片
- `szyg-frontend/src/components/superagent/ChatMessageView.tsx` — 消息气泡、工具卡片、入场动效

---

## 一、输入框系统

### 1.1 聊天模式输入区（SuperAgent.tsx）

**容器：**
- 背景：`bg-[#111827]/80` + `backdrop-blur-md`（毛玻璃效果，与消息区视觉分层）
- 顶部分割：使用微渐变线替代纯 `border-t border-[#1E293B]`：
  `border-t border-transparent` + 伪元素或 `bg-gradient-to-r from-[rgba(99,102,241,0.15)] via-transparent to-transparent` 置于顶部 1px
- 内边距：`px-5 py-4`（原 `px-4 py-4`，左右更宽松）

**输入框：**
- `rows={3}`（默认3行 ≈ 72px），`max-h-48`（自适应扩展至 ≈ 192px）
- 不需要显式 resize handle，自动增长靠 textarea 的 `rows` + `max-h` + overflow
- 字体：`text-body-md`（14px / 1.5 行高）
- 占位符文本保持现有

**发送按钮：**
- 尺寸从 44px → 48px（`w-12 h-12`）
- 启用态：`bg-[#6366F1] text-white hover:bg-[#818CF8] active:scale-95 shadow-glow`
- 禁用态：`bg-[#1A2235] text-[#64748B] cursor-not-allowed`
- 图标 `Send` 从 `w-4 h-4` 增大为 `w-5 h-5`

**快捷键提示：**
- 添加底部文字：`Enter 发送 · Shift+Enter 换行`
- 样式：`text-[11px] text-[#64748B]`，置于输入区右下方
- 与欢迎页保持一致

### 1.2 欢迎页输入区（WelcomeState.tsx）

**容器：**
- 保持 `w-full max-w-2xl mb-10`（mb 从原值保持不变）
- 风格升级为毛玻璃：`border border-[#1E293B] bg-[#111827]/80 backdrop-blur-md`

**输入框：**
- 保持 `rows={3}`，内边距 `px-4 py-3.5`
- 占位符文本保持

**发送按钮：**
- 与聊天模式统一：48px 尺寸、hover 动画、`shadow-glow`
- 快捷键提示保持

---

## 二、消息气泡系统（ChatMessageView.tsx）

### 2.1 用户消息

- 对齐：`ml-auto max-w-[70%]`（右对齐，限制宽度）
- 背景：`bg-[rgba(99,102,241,0.15)]`（原 0.1 → 0.15，提高对比度）
- 边框：`border border-[rgba(99,102,241,0.25)]`（原 0.2 → 0.25）
- 阴影：`shadow-[0_0_12px_rgba(99,102,241,0.08)]`（新增微弱发光，增强"已发送"感知）
- 圆角：保持 `rounded-card`（12px）

### 2.2 AI 消息

- 对齐：`mr-auto max-w-[75%]`
- 背景：`bg-[rgba(17,24,39,0.5)]`（新增淡容器，替代纯透明）
- 左侧锚点线：`border-l-2 border-[rgba(99,102,241,0.2)]`（视觉锚点，区分 AI 内容块）
- 内边距：`px-4 py-2.5`
- 保留富文本渲染（bold、code、换行）

### 2.3 打字光标

- 颜色：`bg-[#818CF8]`（原 `#6366F1`，更柔和）
- 动画：保持 `animate-pulse`

### 2.4 工具调用卡片

- 保持现有样式，微调间距更紧凑
- 状态图标动画：
  - 成功：`<CheckCircle2>` 添加 scale-in 弹跳（可后续用 CSS class）
  - 失败：`<AlertCircle>` 添加短暂闪烁
  - 运行中：保持旋转动画

### 2.5 系统消息（状态提示 / 错误）

- 居中显示：`mx-auto`
- 背景：`bg-[rgba(17,24,39,0.4)]`
- 字体：`text-[12px] text-[#94A3B8]`
- 作为温和的不干扰提示

---

## 三、布局与动效

### 3.1 消息区间距（SuperAgent.tsx）

- 水平 padding：`px-8`（原 `px-6`，对话更居中）
- 垂直 padding：`py-6`（保持）
- 消息间距：`space-y-6`（保持）
- 滚动条：保持 6px 细滚动条

### 3.2 欢迎页（WelcomeState.tsx）

- 品牌区 margin-bottom：`mb-10`（原 `mb-8`，给输入框更多呼吸空间）
- 案例卡片网格间距：`gap-5`（原 `gap-4`）
- 卡片 hover：`hover:border-[#6366F1]/30 hover:shadow-card-hover`
- 卡片 `whileHover: y=-4` 保持

### 3.3 动效

- 消息入场：`opacity + y: 16 → 0`，duration 从 0.4s 调整为 0.35s（更敏捷）
- 发送按钮：`active:scale-95` 过渡
- 输入框聚焦：添加 `ring-1 ring-[#6366F1]/20` 辉光环（或使用 `focus-within:ring-1` 在容器上）
- 毛玻璃过渡：输入区背景从纯色到毛玻璃的自然过渡

### 3.4 布局状态切换

- 无消息 → 欢迎页（居中，Logo + 输入框 + 案例卡片）
- 有消息 → 顶部消息列表 + 底部固定输入栏
- 暂无布局变化需求

---

## 技术约束

- 不引入新依赖，使用现有的 `framer-motion` + Tailwind CSS
- 所有颜色值使用 CSS 自定义属性或 Tailwind 的任意值语法 `[...]`
- 三文件改动，互不冲突
- 保持 `React.memo` 性能优化模式

## 验收标准

1. 聊天输入框默认 3 行高度，可自动扩展至约 192px
2. 用户消息气泡右对齐，AI 消息左对齐带左侧锚点线
3. 输入区背景呈现毛玻璃效果
4. 动效流畅，无不自然的卡顿或跳跃
5. 欢迎页和聊天模式视觉风格统一
6. 所有现有功能（流式输出、生成请求、工具调用展示）不受影响
