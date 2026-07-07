# SuperAgent 页面视觉升级 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对超级员工页面进行精致专业风视觉升级，重点提升输入框可用性、消息气泡表现力及整体设计品质。

**Architecture:** 三文件改动，互不冲突 — ChatMessageView.tsx（消息气泡+工具卡片+动效）、WelcomeState.tsx（欢迎页输入区+品牌区+案例卡片）、SuperAgent.tsx（输入框系统+布局间距）。基于现有 `framer-motion` + Tailwind CSS，不引入新依赖。

**Tech Stack:** React 18, TypeScript, Tailwind CSS, framer-motion, Lucide icons

## Global Constraints

- 不引入新依赖
- 所有颜色使用 Tailwind 任意值语法 `[...]` 或 CSS 自定义属性
- 保持现有 `React.memo` 性能优化
- 所有现有功能（流式输出、生成请求、工具调用展示）不受影响
- 三文件改动独立，可分别 commit

---

### Task 1: 消息气泡系统升级（ChatMessageView.tsx）

**Files:**
- Modify: `szyg-frontend/src/components/superagent/ChatMessageView.tsx`

- [ ] **Step 1: 用户消息气泡右对齐 + 增强视觉**

找到用户消息的渲染分支（`isUser` 且 `type === 'text'`），将气泡容器改为：

```tsx
// 原代码在 line 96-109，替换气泡 div 的 className
<div
  className={cn(
    'inline-block rounded-card px-4 py-2.5 text-body-md leading-relaxed',
    // 原：无 max-width 和 ml-auto
    isUser
      ? 'ml-auto max-w-[70%] bg-[rgba(99,102,241,0.15)] border border-[rgba(99,102,241,0.25)] text-[#F1F5F9] shadow-[0_0_12px_rgba(99,102,241,0.08)]'
      : 'text-[#94A3B8]',
  )}
>
```

注意：`ml-auto max-w-[70%]` 需要在 isUser 条件下才添加，否则影响 AI 消息。

- [ ] **Step 2: AI 消息添加淡容器背景 + 左侧锚点线**

在同一个 AI 消息分支（`!isUser`）中将纯文本升级为带容器：

```tsx
// AI 消息：添加背景 + 左侧锚点线，同时限制宽度
// 原条件 `message.type === 'text'` 分支中 isUser 为 false 时
// 将 className 中的 :  false 分支改为：
: 'mr-auto max-w-[75%] bg-[rgba(17,24,39,0.5)] border-l-2 border-[rgba(99,102,241,0.2)] rounded-r-card px-4 py-2.5 text-[#94A3B8]',
```

同时将整个文本气泡的 `max-w-full` 移除，改为由 `ml-auto`/`mr-auto` + `max-w-[70%]`/`max-w-[75%]` 控制。

- [ ] **Step 3: 打字光标颜色调整**

找到 `message.isStreaming` 的光标 span（line 106-108），将 `bg-[#6366F1]` 改为 `bg-[#818CF8]`：

```tsx
{message.isStreaming && (
  <span className="inline-block w-[7px] h-[14px] bg-[#818CF8] ml-0.5 align-middle animate-pulse" />
)}
```

- [ ] **Step 4: 消息入场动画时长调整**

找到 `motion.div`（line 85-89），将 `duration: 0.4` 改为 `duration: 0.35`：

```tsx
<motion.div
  className={cn('flex gap-3', isUser ? 'flex-row' : 'flex-row')}
  initial={{ opacity: 0, y: 16 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
>
```

- [ ] **Step 5: 验证**

运行 `npm run dev`，打开超级员工页面，发送几条消息，确认：
- 用户消息右对齐，有发光阴影
- AI 消息左对齐，有左侧紫色锚点线和淡背景
- 打字光标颜色更柔和
- 消息入场动画流畅

- [ ] **Step 6: Commit**

```bash
git add szyg-frontend/src/components/superagent/ChatMessageView.tsx
git commit -m "feat: 升级 SuperAgent 消息气泡系统 — 对齐、背景、锚点线、动效
"
```

---

### Task 2: 欢迎页视觉升级（WelcomeState.tsx）

**Files:**
- Modify: `szyg-frontend/src/components/superagent/WelcomeState.tsx`

- [ ] **Step 1: 品牌区 margin-bottom 增加**

找到品牌 block 的 `motion.div`（line 43），将 `mb-8` 改为 `mb-10`：

```tsx
<motion.div
  className="flex flex-col items-center gap-4 mb-10"
  // ...
>
```

- [ ] **Step 2: 输入框容器升级为毛玻璃效果**

找到输入框外层容器（line 71），替换 `className`：

```tsx
<div className="relative rounded-card-lg border border-[#1E293B] bg-[#111827]/80 backdrop-blur-md focus-within:border-[#334155] focus-within:ring-1 focus-within:ring-[#6366F1]/20 transition-all overflow-hidden">
```

关键变化：`bg-[#0D1321]` → `bg-[#111827]/80 backdrop-blur-md`，新增 `focus-within:ring-1 focus-within:ring-[#6366F1]/20`。

- [ ] **Step 3: 发送按钮尺寸统一为 48px**

找到发送按钮（line 83-96），将 `w-9 h-9` 改为 `w-12 h-12`，图标 `w-4 h-4` 改为 `w-5 h-5`：

```tsx
<button
  onClick={onSend}
  disabled={streaming || !inputText.trim()}
  className={cn(
    'flex items-center justify-center w-12 h-12 rounded-button transition-all',
    inputText.trim() && !streaming
      ? 'bg-[#6366F1] text-white hover:bg-[#818CF8] active:scale-95 shadow-glow'
      : 'bg-[#1A2235] text-[#64748B] cursor-not-allowed',
  )}
  aria-label="发送"
>
  <Send className="w-5 h-5" />
</button>
```

- [ ] **Step 4: 案例卡片间距 + hover 效果增强**

找到卡片网格容器（line 123），将 `gap-4` 改为 `gap-5`：

```tsx
<div className="grid grid-cols-2 md:grid-cols-3 gap-5">
```

找到卡片 button（line 125），在 className 中添加 hover 边框色和阴影：

```tsx
// 原: "group text-left rounded-card overflow-hidden border border-[#1E293B] hover:border-[#334155] ..."
// 改为:
"group text-left rounded-card overflow-hidden border border-[#1E293B] hover:border-[#6366F1]/30 hover:shadow-card-hover transition-all disabled:opacity-50"
```

- [ ] **Step 5: 验证**

运行 `npm run dev`，打开超级员工页面（无消息时显示欢迎页），确认：
- 品牌区与输入框间距增大
- 输入框毛玻璃效果，聚焦时有紫色辉光环
- 发送按钮 48px，带发光阴影
- 案例卡片间距更宽松，hover 有紫色边框和阴影

- [ ] **Step 6: Commit**

```bash
git add szyg-frontend/src/components/superagent/WelcomeState.tsx
git commit -m "feat: 升级欢迎页视觉 — 毛玻璃输入框、48px发送按钮、卡片间距优化
"
```

---

### Task 3: 聊天输入框 + 布局间距升级（SuperAgent.tsx）

**Files:**
- Modify: `szyg-frontend/src/pages/SuperAgent.tsx`

- [ ] **Step 1: 消息区水平 padding 增大**

找到消息列表容器（line 471），将 `px-6` 改为 `px-8`：

```tsx
<div ref={messagesRef} className="flex-1 overflow-y-auto">
  <div className="px-8 py-6 space-y-6">
```

- [ ] **Step 2: 输入区容器升级为毛玻璃效果 + 顶部分割线**

找到输入栏容器（line 480），完整替换：

```tsx
{/* Input bar */}
<div className="shrink-0 border-t border-[#1E293B] bg-[#111827]/80 backdrop-blur-md">
  {/* 微渐变装饰线 */}
  <div className="h-px bg-gradient-to-r from-[rgba(99,102,241,0.2)] via-transparent to-transparent" />
  <div className="flex items-end gap-3 px-5 py-4">
    <textarea
      value={inputText}
      onChange={(e) => setInputText(e.target.value)}
      onKeyDown={handleInputKeyDown}
      disabled={streaming}
      rows={3}
      placeholder="描述你想要生成的视频或图片，或与超级员工对话..."
      className="flex-1 bg-transparent text-body-md text-[#F1F5F9] placeholder-[#64748B] resize-none focus:outline-none max-h-48 py-2"
    />
    <button
      onClick={() => sendMessage()}
      disabled={streaming || !inputText.trim()}
      className="flex items-center justify-center w-12 h-12 rounded-button bg-[#6366F1] text-white shrink-0 disabled:opacity-40 hover:bg-[#818CF8] active:scale-95 shadow-glow transition-all disabled:hover:bg-[#6366F1] disabled:shadow-none"
      aria-label="发送"
    >
      <Send className="w-5 h-5" />
    </button>
  </div>
  {/* 快捷键提示 */}
  <div className="flex justify-end px-5 pb-2">
    <span className="text-[11px] text-[#64748B]">Enter 发送 · Shift+Enter 换行</span>
  </div>
</div>
```

关键变化：
- 容器背景：`bg-[#0D1321]` → `bg-[#111827]/80 backdrop-blur-md`
- 新增顶部微渐变装饰线
- `rows={1}` → `rows={3}`
- `gap-2` → `gap-3`
- `px-4 py-4` → `px-5 py-4`
- 按钮 `w-11 h-11` → `w-12 h-12`，图标 `w-4 h-4` → `w-5 h-5`
- 按钮添加 `hover:bg-[#818CF8] active:scale-95 shadow-glow`
- 禁用态添加 `disabled:hover:bg-[#6366F1] disabled:shadow-none` 防止 hover 变色
- 新增底部快捷键提示

- [ ] **Step 3: 验证**

运行 `npm run dev`，进入有消息的对话，确认：
- 输入框默认 3 行，可自动扩展至约 192px（max-h-48）
- 毛玻璃背景，顶部微渐变线
- 发送按钮 48px，与欢迎页一致的交互效果
- 底部快捷键提示可见
- 消息区水平 padding 更宽敞
- Enter 发送、Shift+Enter 换行正常工作
- 流式模式下输入框禁用正常

- [ ] **Step 4: Commit**

```bash
git add szyg-frontend/src/pages/SuperAgent.tsx
git commit -m "feat: 升级聊天输入框系统 — 3行高度、毛玻璃、48px按钮、布局间距优化
"
```

---

### Task 4: 最终验证与收尾

- [ ] **Step 1: 全流程视觉验证**

运行 `npm run dev`，依次验证：

1. **欢迎页** — 毛玻璃输入框、48px 发送按钮（带发光）、案例卡片间距和 hover 效果
2. **发送消息** — 用户消息右对齐 + 发光阴影、AI 消息左对齐 + 锚点线
3. **输入框交互** — 3 行默认高度、自动扩展、Enter 发送 / Shift+Enter 换行
4. **流式输出** — 打字光标为 `#818CF8`、消息入场 0.35s 动画
5. **工具调用** — 正常展示（不受影响）
6. **图片/视频生成** — 正常展示（不受影响）

- [ ] **Step 2: 如有视觉问题，修复后重新验证**

- [ ] **Step 3: 最终 commit（如有微调）**

```bash
git add -A
git commit -m "chore: 最终视觉微调与收尾"
```
