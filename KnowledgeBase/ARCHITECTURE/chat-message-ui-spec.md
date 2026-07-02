# 对话消息 UI 优化规范

> 文件范围：`web/src/pages/SuperAgent.vue` 模板 + CSS
> 状态：待 Elite_Coder 执行

---

## 1. 需求

1. **用户消息添加对话气泡**：用户消息文本用圆角气泡包裹，视觉上区分于 agent 消息
2. **Agent 消息不加气泡**：保持现有纯文本样式，无背景色包裹
3. **头像与内容水平对齐**：头像（28px）与消息内容第一行文字在同一水平线上，间距统一

---

## 2. 当前问题分析

### 2.1 头像与内容未对齐

当前 `.message` 使用 `display: flex; gap: 12px`，但 `.msg-avatar` 没有设置 `align-self`，而 `.msg-content` 中的 `.msg-text` 有 `line-height: 1.7`，导致头像顶部与文字第一行基线不在同一水平线。

**修复**：`.msg-avatar` 添加 `align-self: flex-start`，确保头像与内容顶部对齐。同时 `margin-top` 微调使头像中心与第一行文字视觉对齐。

### 2.2 用户消息无气泡

当前 `.message.user .msg-text` 仅改变文字颜色，无背景、圆角、内边距，视觉上与 agent 消息几乎无区分。

---

## 3. 模板修改

### 3.1 用户消息气泡

在 `.msg-text` 外层包裹一个气泡容器，**仅对 user 消息生效**。

**修改前**（`SuperAgent.vue` 约 line 93-95）：
```html
<div v-for="msg in state.messages" :key="msg.id" class="message" :class="msg.role">
  <div class="msg-avatar">{{ msg.role === 'user' ? getUserInitial() : '' }}<img v-if="msg.role !== 'user'" :src="logo1Url" alt="AI" class="avatar-logo" /></div>
  <div class="msg-content">
    <!-- ... -->
    <div v-else class="msg-text" v-html="renderMarkdown(msg.content)" @click="handleMsgClick"></div>
```

**修改后**：
```html
<div v-for="msg in state.messages" :key="msg.id" class="message" :class="msg.role">
  <div class="msg-avatar">{{ msg.role === 'user' ? getUserInitial() : '' }}<img v-if="msg.role !== 'user'" :src="logo1Url" alt="AI" class="avatar-logo" /></div>
  <div class="msg-content">
    <!-- ... -->
    <div v-else class="msg-bubble" :class="{ 'user-bubble': msg.role === 'user' }">
      <div class="msg-text" v-html="renderMarkdown(msg.content)" @click="handleMsgClick"></div>
    </div>
```

> **注意**：仅对 `v-else`（纯文本消息）添加 `.msg-bubble` 包裹。视频卡片、图片卡片、工具调用等特殊消息类型不加气泡。

### 3.2 流式消息

流式 agent 消息（`state.streaming` 块，约 line 152-165）**不加气泡**，保持原样。

---

## 4. CSS 规范

### 4.1 消息行对齐

```css
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: flex-start;    /* 头像与内容顶部对齐 */
}

.msg-avatar {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: var(--accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  color: var(--accent);
  overflow: hidden;
  margin-top: 2px;            /* 微调：使头像与第一行文字视觉居中对齐 */
}
```

### 4.2 用户消息气泡

```css
.msg-bubble {
  /* 默认无样式 — agent 消息不显示气泡 */
}

.msg-bubble.user-bubble {
  background: var(--accent-soft);
  border-radius: 12px 12px 12px 4px;   /* 左下角小圆角，模拟"来自左侧"的指向 */
  padding: 10px 14px;
  display: inline-block;
  max-width: 100%;
}

.msg-bubble.user-bubble .msg-text {
  color: var(--text-primary);
}
```

### 4.3 Agent 消息样式（不变）

```css
.message.assistant .msg-text {
  color: var(--text-secondary);
}
```

Agent 消息保持纯文本，无背景、无圆角、无内边距。

### 4.4 气泡内 Markdown 渲染

气泡内的 `.msg-text` 需确保 Markdown 元素（代码块、列表等）不被气泡 `overflow` 截断：

```css
.msg-bubble.user-bubble .msg-text {
  word-break: break-word;
}

.msg-bubble.user-bubble .msg-text :deep(pre) {
  background: rgba(0, 0, 0, 0.06);
  border-radius: 6px;
  padding: 8px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
```

---

## 5. 不修改项

- `.msg-avatar` 尺寸保持 28px × 28px
- `.avatar-logo` 样式不变
- 视频卡片（`.video-card`）、图片卡片（`.image-card`）、工具调用（`.tool-calls`）不加气泡
- 流式消息（`state.streaming`）不加气泡
- 消息间距 `margin-bottom: 20px` 不变
- `gap: 12px`（头像与内容间距）不变

---

## 6. 验收标准

1. 用户消息文本被圆角气泡包裹（`background: var(--accent-soft)`，`border-radius: 12px 12px 12px 4px`）
2. Agent 消息无气泡，保持纯文本样式
3. 头像（28px）与消息内容第一行文字在同一水平线上（`align-items: flex-start` + `margin-top: 2px` 微调）
4. 气泡内 Markdown 正常渲染（代码块、列表、链接不被截断）
5. 视频卡片、图片卡片、工具调用不受气泡影响
6. 流式消息无气泡
7. 暗色主题下气泡颜色正常显示（`--accent-soft` 已有暗色模式值）
