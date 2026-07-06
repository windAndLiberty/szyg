# 超级员工欢迎页面重设计规范

> 灵感来源：Kimi 极简居中布局 + 黄金比例美学
> 文件范围：`web/src/pages/SuperAgent.vue` 模板 + CSS
> 状态：待 Elite_Coder 执行（v2 - 简化输入框，logo 置顶）

---

## 1. 设计目标

极简美学，黄金比例布局。用户进入页面后视觉焦点自然从 logo → 品牌名 → 输入框 → 案例卡片流动，只有一个行动点（输入框），底部案例卡片降低冷启动焦虑。

---

## 2. 整体布局（黄金比例）

```
┌─────────────────────────────────────────────┐
│                  (留白 ~38%)                 │  ← 顶部留白占 38vh
│                                             │
│              [logo1 圆形图标]                 │  ← 80px 圆形 logo
│               超级员工                        │  ← 品牌标识
│                                             │
│   ┌─────────────────────────────────────┐   │
│   │  输入 "/" 唤起工具和能力          [↑]│   │  ← 纯输入框 + 内嵌发送按钮
│   │                                     │   │
│   └─────────────────────────────────────┘   │
│                                             │
│   智能员工 精选案例              更多 →       │
│   ┌──────┐  ┌──────┐  ┌──────┐              │
│   │ 占位  │  │ 占位  │  │ 占位  │              │
│   │全栈开发│  │营销策划│  │数据分析│              │
│   └──────┘  └──────┘  └──────┘              │
│                  (留白 ~10%)                 │
└─────────────────────────────────────────────┘
```

- **保留左侧导航栏**（`conv-history-panel` 始终显示，不隐藏）
- **保留底部输入框**（`.input-area` 始终显示，不隐藏）
- **禁止滚动**：欢迎页面不可上下滚动，所有内容在一屏内完整展示
- **整体居中**：所有元素（logo、标题、输入框、案例卡片）作为一个整体在可用空间内水平+垂直居中
- **黄金比例垂直分布**：内容整体垂直居中，各元素间距保持视觉平衡
- **水平居中对齐**，最大宽度 720px
- **视觉焦点递进**：logo → 品牌名 → 输入框 → 案例卡片

---

## 3. 区域详细规范

### 3.1 Logo 图标 + 品牌标识

**Logo（logo1.png）**：
| 属性 | 值 |
|------|-----|
| 尺寸 | `104px × 104px` |
| 形状 | 圆形（`border-radius: 999px`） |
| 位置 | 居中，品牌标题正上方 |
| margin-bottom | `20px` |
| 阴影 | `0 4px 20px rgba(0, 0, 0, 0.14)` |
| object-fit | `cover` |
| 溢出 | `overflow: hidden` |

**品牌标题**：
| 属性 | 值 |
|------|-----|
| 文本 | `超级员工` |
| 位置 | logo 下方，居中 |
| 字体 | 无衬线粗体，`font-size: 40px`，`font-weight: 700` |
| 颜色 | `var(--text-primary)` |
| 字母间距 | `letter-spacing: 6px` |
| margin | `0 0 48px` |

### 3.2 核心输入框（极简版）

**移除所有底部工具栏**：不再包含 `+` 按钮、智能体按钮、深度思考选择器。

**容器**：
| 属性 | 值 |
|------|-----|
| 宽度 | `max-width: 640px`，居中 |
| 圆角 | `border-radius: 28px`（大圆角矩形） |
| 边框 | `1px solid var(--border-light)` |
| 阴影 | `0 2px 20px rgba(0, 0, 0, 0.08)` |
| 背景 | `var(--bg-body)` |
| padding | `6px 6px 6px 24px`（左大右小，为发送按钮留空间） |

**输入区**：
- `el-input` `type="textarea"`
- `:rows="3"`
- 占位文字：`输入 "/" 唤起工具和能力`
- 无边框（`border: none`），透明背景
- `resize: none`

**发送按钮（内嵌输入框右下角）**：

发送按钮作为输入框容器内部的绝对定位元素，位于右下角：

| 属性 | 值 |
|------|-----|
| 位置 | `position: absolute; right: 10px; bottom: 10px` |
| 类型 | `el-button` `type="primary"` `circle` |
| 尺寸 | `40px × 40px` |
| 图标 | `Promotion`（向上箭头） |
| 点击 | `sendMessage` |
| loading | `:loading="state.streaming"` |

> 容器需 `position: relative` 以锚定按钮。

### 3.3 底部案例区

**容器**：
| 属性 | 值 |
|------|-----|
| 宽度 | `max-width: 640px`，居中 |
| margin-top | `56px` |

**标题栏**：
- 左侧：`智能员工 精选案例`，`font-size: 15px`，`color: var(--text-secondary)`
- 右侧：`更多 →`，文字链接，`font-size: 13px`，`color: var(--accent)`，`cursor: pointer`
- 布局：`display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px`

**案例卡片（三列等宽）**：

```css
.case-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
```

每个卡片：
| 属性 | 值 |
|------|-----|
| 圆角 | `border-radius: 12px` |
| 边框 | `1px solid var(--border-light)` |
| 溢出 | `overflow: hidden` |
| cursor | `pointer` |
| transition | `transform 0.2s, box-shadow 0.2s` |
| hover | `transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.08)` |

卡片结构：
```html
<div class="case-card" @click="sendQuickCard(card.content)">
  <div class="case-card-image"></div>
  <div class="case-card-title">{{ card.title }}</div>
</div>
```

**案例卡片数据为动态加载**：通过 `POST /api/hermes/case-cards` 从抖音实时搜索，基于用户近期对话历史推断关键词。详见 `KnowledgeBase/API_SPECS/welcome-case-cards-spec.md`。

**卡片样式**：
```css
.case-card-image {
  height: 130px;
  background: var(--accent-soft);
  overflow: hidden;
}

.case-card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.case-card-title {
  padding: 12px 16px;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}
```

**响应式**：
```css
@media (max-width: 768px) {
  .case-cards {
    grid-template-columns: 1fr;
  }
}
```

---

## 4. 数据结构

### 4.1 `caseCards` — 动态 ref

```js
const caseCards = ref([])  // 从 /api/hermes/case-cards 异步加载
const caseCardsLoading = ref(false)
```

> 详细 API 规范见 `KnowledgeBase/API_SPECS/welcome-case-cards-spec.md`

### 4.2 移除 `thinkMode`

不再需要 `thinkMode` ref 和深度思考选择器。

---

## 5. 模板变更

### 5.1 欢迎状态模板

```html
<div v-if="state.messages.length === 0" class="welcome-page">
  <!-- Logo + 品牌标识 -->
  <div class="brand-block">
    <div class="brand-logo"><img :src="logo1Url" alt="logo" /></div>
    <h1 class="brand-title">超级员工</h1>
  </div>

  <!-- 核心输入框（极简，发送按钮内嵌） -->
  <div class="welcome-input-box">
    <el-input
      v-model="inputText"
      type="textarea"
      :rows="3"
      placeholder='输入 "/" 唤起工具和能力'
      @keydown.enter.exact.prevent="sendMessage"
      :disabled="state.streaming"
      resize="none"
    />
    <el-button
      class="welcome-send-btn"
      type="primary"
      circle
      @click="sendMessage"
      :loading="state.streaming"
    >
      <el-icon><Promotion /></el-icon>
    </el-button>
  </div>

  <!-- 精选案例（动态加载） -->
  <div class="case-section">
    <div class="case-header">
      <span class="case-title">智能员工 精选案例</span>
    </div>
    <div class="case-cards" v-loading="caseCardsLoading">
      <div v-for="card in caseCards" :key="card.video_url" class="case-card" @click="sendQuickCard(card.title)">
        <div class="case-card-image">
          <img v-if="card.cover_url" :src="card.cover_url" :alt="card.title" />
        </div>
        <div class="case-card-title">{{ card.title }}</div>
      </div>
    </div>
    <div v-if="!caseCardsLoading && caseCards.length === 0" class="case-empty">暂无推荐案例</div>
  </div>
</div>
```

### 5.2 保留左侧导航栏

**对话历史面板始终保留**，不添加任何 `v-if` 条件。`conv-history-panel` 保持原样，无论是否有消息。

### 5.3 保留底部输入框

**底部输入框始终保留**，不添加任何 `v-if` 条件。`.input-area` 保持原样。

> **重要**：本轮修改仅限欢迎页面（`welcome-page` / `welcome-state`）内部内容，不修改页面整体布局结构（导航栏、输入框区域等）。

---

## 6. CSS 规范

### 6.1 欢迎页容器（黄金比例）

```css
.messages-area.welcome-mode {
  flex: 1 1 auto;            /* ← 关键修复：填满 chat-area 剩余高度 */
  display: flex;             /*   使子元素 .welcome-page 可以垂直居中 */
  flex-direction: column;
  overflow: hidden;
}

.welcome-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;  /* 垂直居中 */
  overflow: hidden;          /* 禁止滚动 */
  padding: 24px 32px;
  max-width: 720px;           /* ← 放大：640 → 720 */
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
  gap: 40px;                 /* ← 放大：32 → 40，各区块统一间距 */
}
```

> **布局说明**：`.messages-area.welcome-mode` 必须使用 `flex: 1 1 auto` + `display: flex` 使其填满 `.chat-area` 的全部剩余高度，这样子元素 `.welcome-page` 的 `justify-content: center` 才能真正实现垂直居中。`overflow: hidden` 禁止滚动。各区块通过 `gap: 32px` 保持统一间距。

### 6.2 Logo + 品牌标识

```css
.brand-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 48px;       /* ← 放大：40 → 48 */
}

.brand-logo {
  width: 104px;              /* ← 放大：80 → 104 */
  height: 104px;
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 20px;       /* ← 放大：16 → 20 */
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.14);
}

.brand-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.brand-title {
  font-size: 40px;           /* ← 放大：32 → 40 */
  font-weight: 700;
  letter-spacing: 6px;       /* ← 放大：4 → 6 */
  color: var(--text-primary);
  margin: 0;
}
```

### 6.3 输入框容器（圆角矩形 + 内嵌发送按钮）

```css
.welcome-input-box {
  position: relative;          /* 锚定发送按钮 */
  width: 100%;
  max-width: 640px;           /* ← 放大：560 → 640 */
  border: 1px solid var(--border-light);
  border-radius: 28px;         /* ← 放大：24 → 28 */
  background: var(--bg-body);
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.08);
  padding: 6px 6px 6px 24px;   /* ← 放大：4px → 6px, 20px → 24px */
  box-sizing: border-box;
}

.welcome-input-box :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  background: transparent;
  resize: none;
  font-size: 16px;            /* ← 放大：默认14 → 16 */
  padding: 12px 56px 12px 4px;/* ← 放大内边距 */
}

.welcome-send-btn {
  position: absolute;
  right: 10px;
  bottom: 10px;
  width: 40px;                /* ← 放大：默认 → 40px */
  height: 40px;
}
```

### 6.4 案例区

```css
.case-section {
  width: 100%;
  max-width: 640px;           /* ← 放大：560 → 640 */
  margin-top: 56px;           /* ← 放大：48 → 56 */
}

.case-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;       /* ← 放大：16 → 20 */
}

.case-title {
  font-size: 15px;            /* ← 放大：13 → 15 */
  color: var(--text-secondary);
}

.case-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;                  /* ← 放大：16 → 20 */
}

.case-card {
  border-radius: 12px;
  border: 1px solid var(--border-light);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.case-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

.case-card-image {
  height: 130px;             /* ← 放大：100 → 130 */
  background: var(--accent-soft);
  overflow: hidden;
}

.case-card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.case-empty {
  text-align: center;
  font-size: 15px;            /* ← 放大：13 → 15 */
  color: var(--text-tertiary);
  padding: 28px 0;           /* ← 放大：24 → 28 */
}

.case-card-title {
  padding: 12px 16px;        /* ← 放大：10px 14px → 12px 16px */
  font-size: 15px;            /* ← 放大：13 → 15 */
  font-weight: 500;
  color: var(--text-primary);
}

@media (max-width: 768px) {
  .case-cards {
    grid-template-columns: 1fr;
  }
}
```

---

## 7. 移除项

| 移除内容 | 原因 |
|---------|------|
| `.welcome-input-toolbar` 整个工具栏 | 极简设计，移除 + 按钮、智能体、深度思考 |
| `thinkMode` ref 及 `el-select` | 不再需要深度思考选择器 |
| `.toolbar-left` / `.toolbar-right` CSS | 工具栏已移除 |
| `logo2Url` 导入 | 欢迎页统一使用 `logo1Url` |
| 硬编码 `caseCards` 常量数组 | 改为动态 ref，从 API 加载 |
| `.case-more` CSS 及模板中的"更多 →" | 移除，不再显示"更多"链接 |
| `conv-history-panel` 上的 `v-if` | **不要添加**，对话历史始终保留 |
| `.input-area` 上的 `v-if` | **不要添加**，底部输入框始终保留 |

---

## 8. 保留项

- `logo1Url` 导入保留（欢迎页 logo + 对话头像共用）
- 对话消息中的 `logo1Url` 头像保持不变
- 流式消息的 `logo1Url` 头像保持不变
- 右键菜单功能保持不变
- 导出对话功能保持不变
- `sendQuickCard` 函数保持不变（点击卡片填入输入框）

---

## 9. 验收标准

1. 欢迎页顶部显示 104px 圆形 logo1 图标，下方紧跟"超级员工"品牌标题（`font-size: 40px`）
2. 输入框为大圆角矩形（`border-radius: 28px`，`max-width: 640px`），仅含 textarea + 右下角内嵌 40px 圆形发送按钮
3. **无** `+` 按钮、智能体按钮、深度思考选择器
4. 输入框下方显示三列案例卡片（动态从抖音搜索加载），有标题栏，**无"更多"链接**
5. **对话历史面板始终保留**（不隐藏）
6. **底部输入框始终保留**（不隐藏）
7. 有对话消息时，恢复原有布局（左侧导航 + 消息流 + 底部输入框）
8. 案例卡片点击后填入视频标题到输入框
9. 欢迎页面**不可上下滚动**（`overflow: hidden`），所有内容在一屏内完整展示
10. 所有元素（logo、标题、输入框、案例卡片）**整体在可用空间内水平+垂直居中**（`.messages-area.welcome-mode` 使用 `flex: 1 1 auto` + `display: flex` 填满高度，`.welcome-page` 使用 `justify-content: center` + `align-items: center`）
11. 响应式：768px 以下案例卡片变为单列
12. 案例卡片从 `/api/hermes/case-cards` 动态加载，显示真实抖音视频封面和标题
13. 无对话历史或搜索失败时，显示"暂无推荐案例"空态
