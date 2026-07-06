# 超级员工对话流 — 视频卡片渲染规范

> 本文件定义超级员工（SuperAgent）对话流中 AI 生成视频的完整渲染链路规范。
> 涉及源码：`server/szyg/api/hermes_chat.py`、`web/src/pages/SuperAgent.vue`
> 执行者：Elite_Coder

---

## 1. 业务背景

AI 视频生成是**两步异步**流程：

1. `ai_video_create(prompt, duration, model)` → 提交任务，返回 `task_id`
2. `ai_video_task_status(task_id)` → 轮询任务状态，完成后下载视频到本地

当前前端无视频卡片，LLM 调用视频工具后结果仅以纯文本 JSON 展示在工具结果卡片中，用户无法直接预览播放。

---

## 2. 交互设计

### 2.1 用户体验流程

```
用户: "帮我生成一个海洋主题的短视频"
  │
  ▼
LLM 调用 ai_video_create
  ├─ 前端：插入进度卡片（spinner + 提示词 + "视频生成中..."）
  └─ 后端：SSE 发送 video_task 事件
  │
  ▼
LLM 调用 ai_video_task_status(task_id) 轮询
  ├─ 前端：进度卡片更新状态文字（"生成中 50%..."）
  └─ 后端：SSE 发送 video_status 事件
  │
  ▼  (可能多轮轮询)
  │
ai_video_task_status 返回 succeeded
  ├─ 前端：进度卡片替换为视频播放器卡片
  │   ├─ <video controls> 内嵌播放（不遮挡对话流）
  │   ├─ 放大按钮 → 弹出 modal overlay（半透明背景 + 居中大播放器）
  │   └─ 全屏按钮 → video.requestFullscreen() 原生全屏
  └─ 后端：SSE 发送 video 事件（含本地可访问 URL）
```

### 2.2 卡片视觉布局

```
┌──────────────────────────────────┐
│  🎬 视频生成中...                 │  ← 进度卡片 (video_pending)
│  ⏳ 海洋主题短视频                │
│  状态: 生成中 50%                 │
└──────────────────────────────────┘

         ↓ 任务完成后替换为 ↓

┌──────────────────────────────────┐
│                                  │
│         <video controls>         │  ← 视频卡片 (video)
│         (内嵌播放器)              │
│                                  │
├──────────────────────────────────┤
│  🎬 海洋主题短视频                │
│  [🔍 放大]  [⛶ 全屏]  [⬇ 下载]   │
└──────────────────────────────────┘
```

### 2.3 Modal Overlay（放大播放）

```
┌─────────────────────────────────────────────┐
│ (半透明黑色背景, 点击关闭)                     │
│                                             │
│        ┌─────────────────────────┐          │
│        │                         │          │
│        │    <video controls>     │          │
│        │    (居中大播放器)        │          │
│        │                         │          │
│        └─────────────────────────┘          │
│                                             │
│                    [⛶ 全屏] [✕ 关闭]        │
└─────────────────────────────────────────────┘
```

---

## 3. SSE 事件类型定义

### 3.1 `video_task` 事件

**触发时机**：`ai_video_create` 工具执行完成，返回 `{"ok":true, "type":"video_task", ...}` 时。

**发送位置**：`hermes_chat.py` 在 `yield _sse(type='tool_result', ...)` 之后，与现有 `image` 事件检测逻辑并列。

```typescript
interface VideoTaskEvent {
  type: "video_task"
  task_id: string    // 视频任务 ID
  prompt: string     // 生成提示词
  status: string     // 初始状态: "queued"
}
```

**后端检测条件**：
```python
if tool_name == "ai_video_create":
    rj = json.loads(result)
    if rj.get("ok") and rj.get("task_id"):
        yield _sse(
            type='video_task',
            task_id=rj["task_id"],
            prompt=rj.get("prompt", ""),
            status=rj.get("status", "queued"),
        )
```

### 3.2 `video_status` 事件

**触发时机**：`ai_video_task_status` 工具执行完成，返回状态非 `succeeded` 时（仍在生成中）。

```typescript
interface VideoStatusEvent {
  type: "video_status"
  task_id: string     // 视频任务 ID
  status: string      // "queued" | "running" | "failed"
  progress: number    // 0-100
}
```

**后端检测条件**：
```python
if tool_name == "ai_video_task_status":
    rj = json.loads(result)
    if rj.get("status") != "succeeded":
        yield _sse(
            type='video_status',
            task_id=rj.get("task_id", ""),
            status=rj.get("status", "unknown"),
            progress=rj.get("progress", 0),
        )
```

### 3.3 `video` 事件

**触发时机**：`ai_video_task_status` 工具执行完成，返回 `status == "succeeded"` 且有 `video_url` 或 `local_path` 时。

```typescript
interface VideoEvent {
  type: "video"
  task_id: string     // 视频任务 ID
  url: string         // 可访问的视频 URL: /api/files/volcengine_output/{filename}.mp4
  prompt: string      // 生成提示词
}
```

**后端检测条件**：
```python
if tool_name == "ai_video_task_status":
    rj = json.loads(result)
    if rj.get("status") == "succeeded":
        # 从 local_path 提取可访问 URL
        local_path = rj.get("local_path", "")
        if local_path:
            fname = Path(local_path).name
            video_url = f"/api/files/volcengine_output/{fname}"
        else:
            video_url = rj.get("video_url", "")
        if video_url:
            yield _sse(
                type='video',
                task_id=rj.get("task_id", ""),
                url=video_url,
                prompt=rj.get("prompt", ""),
            )
```

**注意**：`ai_video_task_status` 的返回值来自 `hermes_chat.py:1119-1128`：
```python
result = await client.get_video_task(task_id=..., model=...)
if result.get("status") == "succeed" and result.get("video_url"):
    path = await client.download_video(result["video_url"])
    result["local_path"] = path
return json.dumps(result, ensure_ascii=False)
```

需注意 VolcEngine 返回的状态值可能是 `"succeed"` 而非 `"succeeded"` — Elite_Coder 需验证实际返回值并兼容两种拼写。

---

## 4. 前端数据结构

### 4.1 流式收集器

```typescript
// 新增 ref，与 streamImages 并列
const streamVideoTasks = ref([])   // 进行中的视频任务
const streamVideos = ref([])       // 已完成的视频
```

### 4.2 消息对象

#### 进度卡片消息 (`video_pending`)

```typescript
interface VideoPendingMessage {
  id: number
  role: "assistant"
  type: "video_pending"
  task_id: string
  prompt: string
  status: string       // "queued" | "running"
  progress: number     // 0-100
}
```

#### 视频卡片消息 (`video`)

```typescript
interface VideoMessage {
  id: number
  role: "assistant"
  type: "video"
  task_id: string
  video_url: string    // /api/files/volcengine_output/xxx.mp4
  prompt: string
}
```

### 4.3 消息渲染分支

`SuperAgent.vue` 模板 `<div v-for="msg in state.messages">` 内新增分支：

| `msg.type` | 条件 | 渲染组件 |
|------------|------|---------|
| `"video_pending"` | `v-if="msg.type === 'video_pending'"` | 进度卡片（spinner + prompt + status） |
| `"video"` | `v-else-if="msg.type === 'video'"` | 视频卡片（`<video controls>` + 操作按钮） |
| `"image"` | `v-if="msg.type === 'image'"` | 图片卡片（已有） |
| `"text"` | `v-else` | markdown 文本（已有） |

---

## 5. SSE 事件处理逻辑

### 5.1 switch 分支新增

在 `SuperAgent.vue` 的 SSE 事件 `switch (event.type)` 中新增：

```javascript
case 'video_task':
  // 插入进度卡片到流式收集器
  streamVideoTasks.value.push({
    task_id: event.task_id,
    prompt: event.prompt,
    status: event.status,
    progress: 0,
  })
  break

case 'video_status':
  // 更新已有进度卡片的状态
  const task = streamVideoTasks.value.find(t => t.task_id === event.task_id)
  if (task) {
    task.status = event.status
    task.progress = event.progress
  }
  break

case 'video':
  // 视频完成，从进度列表移除，加入完成列表
  streamVideoTasks.value = streamVideoTasks.value.filter(
    t => t.task_id !== event.task_id
  )
  streamVideos.value.push({
    task_id: event.task_id,
    url: event.url,
    prompt: event.prompt,
  })
  break
```

### 5.2 流结束后插入消息

在现有 `addMessage({type: 'text', ...})` 和图片插入逻辑之后，新增：

```javascript
// 插入仍在生成中的视频进度卡片
for (const vt of streamVideoTasks.value) {
  addMessage({
    role: 'assistant',
    type: 'video_pending',
    task_id: vt.task_id,
    prompt: vt.prompt,
    status: vt.status,
    progress: vt.progress,
  })
}
// 插入已完成的视频卡片
for (const vid of streamVideos.value) {
  addMessage({
    role: 'assistant',
    type: 'video',
    task_id: vid.task_id,
    video_url: vid.url,
    prompt: vid.prompt,
  })
}
```

### 5.3 finally 块清空

```javascript
finally {
  state.streaming = false
  // ... 已有清空逻辑
  streamVideoTasks.value = []
  streamVideos.value = []
  // ...
}
```

### 5.4 进度卡片实时更新（跨轮次）

视频生成跨多个 LLM 轮次（LLM 会多次调用 `ai_video_task_status` 轮询）。
每轮 SSE 流结束后，`streamVideoTasks` 会被清空并重新插入到 `state.messages`。

**问题**：这会导致进度卡片在每轮之间闪烁（先清空再重新插入）。

**解决方案**：在 `state.messages` 中通过 `task_id` 匹配并**原地更新**已有进度卡片，而非重复插入：

```javascript
// 流结束后，更新或插入进度卡片
for (const vt of streamVideoTasks.value) {
  const existing = state.messages.find(
    m => m.type === 'video_pending' && m.task_id === vt.task_id
  )
  if (existing) {
    // 原地更新
    existing.status = vt.status
    existing.progress = vt.progress
  } else {
    addMessage({
      role: 'assistant',
      type: 'video_pending',
      task_id: vt.task_id,
      prompt: vt.prompt,
      status: vt.status,
      progress: vt.progress,
    })
  }
}

// 视频完成时，替换进度卡片为视频卡片
for (const vid of streamVideos.value) {
  const pendingIdx = state.messages.findIndex(
    m => m.type === 'video_pending' && m.task_id === vid.task_id
  )
  if (pendingIdx >= 0) {
    // 原地替换
    state.messages[pendingIdx] = {
      ...state.messages[pendingIdx],
      type: 'video',
      video_url: vid.url,
    }
  } else {
    addMessage({
      role: 'assistant',
      type: 'video',
      task_id: vid.task_id,
      video_url: vid.url,
      prompt: vid.prompt,
    })
  }
}
```

---

## 6. 视频卡片组件规范

### 6.1 进度卡片 (`video_pending`)

```html
<div v-if="msg.type === 'video_pending'" class="video-card-pending">
  <div class="video-pending-icon">
    <el-icon class="is-loading"><Loading /></el-icon>
  </div>
  <div class="video-pending-info">
    <div class="video-pending-title">🎬 视频生成中...</div>
    <div class="video-pending-prompt">{{ msg.prompt }}</div>
    <div class="video-pending-status">
      状态: {{ msg.status }} {{ msg.progress > 0 ? msg.progress + '%' : '' }}
    </div>
  </div>
</div>
```

### 6.2 视频卡片 (`video`)

```html
<div v-else-if="msg.type === 'video'" class="video-card">
  <video
    :src="msg.video_url"
    controls
    preload="metadata"
    class="video-player"
    :ref="el => videoRefs[msg.id] = el"
  />
  <div class="video-card-footer">
    <span class="video-card-prompt">{{ msg.prompt }}</span>
    <div class="video-card-actions">
      <el-button text size="small" @click="enlargeVideo(msg)">
        <el-icon><ZoomIn /></el-icon> 放大
      </el-button>
      <el-button text size="small" @click="fullscreenVideo(msg)">
        <el-icon><FullScreen /></el-icon> 全屏
      </el-button>
      <el-button text size="small" @click="downloadVideo(msg)">
        <el-icon><Download /></el-icon> 下载
      </el-button>
    </div>
  </div>
</div>
```

### 6.3 Video Modal Overlay

```html
<!-- Video Modal -->
<div v-if="videoModal.show" class="video-modal-overlay" @click.self="closeVideoModal">
  <div class="video-modal-container">
    <video
      v-if="videoModal.url"
      :src="videoModal.url"
      controls
      autoplay
      class="video-modal-player"
      :ref="el => videoModalRef = el"
    />
    <div class="video-modal-actions">
      <el-button text size="small" @click="fullscreenModalVideo">
        <el-icon><FullScreen /></el-icon> 全屏
      </el-button>
      <el-button text size="small" @click="closeVideoModal">
        <el-icon><Close /></el-icon> 关闭
      </el-button>
    </div>
  </div>
</div>
```

### 6.4 函数定义

```javascript
const videoRefs = ref({})       // msg.id → video element
const videoModalRef = ref(null)
const videoModal = reactive({
  show: false,
  url: '',
})

function enlargeVideo(msg) {
  videoModal.url = msg.video_url
  videoModal.show = true
}

function fullscreenVideo(msg) {
  const el = videoRefs.value[msg.id]
  if (el && el.requestFullscreen) {
    el.requestFullscreen()
  }
}

function fullscreenModalVideo() {
  const el = videoModalRef.value
  if (el && el.requestFullscreen) {
    el.requestFullscreen()
  }
}

function closeVideoModal() {
  videoModal.show = false
  videoModal.url = ''
}

function downloadVideo(msg) {
  const a = document.createElement('a')
  a.href = msg.video_url
  a.download = ''
  a.click()
}
```

---

## 7. CSS 样式规范

### 7.1 进度卡片

```css
.video-card-pending {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  max-width: 400px;
}

.video-pending-icon {
  font-size: 24px;
  color: var(--accent);
}

.video-pending-info {
  flex: 1;
  min-width: 0;
}

.video-pending-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.video-pending-prompt {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.video-pending-status {
  font-size: 11px;
  color: var(--text-tertiary);
}
```

### 7.2 视频卡片

```css
.video-card {
  border-radius: 8px;
  overflow: hidden;
  max-width: 400px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
}

.video-player {
  width: 100%;
  height: auto;
  display: block;
  max-height: 300px;
  object-fit: contain;
  background: #000;
}

.video-card-footer {
  padding: 8px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.video-card-prompt {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.video-card-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
```

### 7.3 Video Modal Overlay

```css
.video-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.video-modal-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.video-modal-player {
  max-width: 90vw;
  max-height: 80vh;
  border-radius: 8px;
  background: #000;
}

.video-modal-actions {
  display: flex;
  gap: 8px;
}

.video-modal-actions .el-button {
  color: white;
}
```

---

## 8. 后端改动规范

### 8.1 文件：`server/szyg/api/hermes_chat.py`

**改动位置**：`hermes_chat.py:1774` 现有 `image` 事件检测块之后，在同一 `for tool_name, tool_id, result in all_results:` 循环内。

**新增逻辑**：

```python
# 检测视频生成工具，发送 video_task / video / video_status 事件
if tool_name == "ai_video_create":
    try:
        rj = json.loads(result)
        if rj.get("ok") and rj.get("task_id"):
            yield _sse(
                type='video_task',
                task_id=rj["task_id"],
                prompt=rj.get("prompt", ""),
                status=rj.get("status", "queued"),
            )
    except Exception as e:
        logger.debug(f"Failed to parse video_task result: {e}")

elif tool_name == "ai_video_task_status":
    try:
        rj = json.loads(result)
        status = rj.get("status", "")
        # 兼容 succeed / succeeded 两种拼写
        if status in ("succeed", "succeeded"):
            local_path = rj.get("local_path", "")
            if local_path:
                fname = Path(local_path).name
                video_url = f"/api/files/volcengine_output/{fname}"
            else:
                video_url = rj.get("video_url", "")
            if video_url:
                yield _sse(
                    type='video',
                    task_id=rj.get("task_id", ""),
                    url=video_url,
                    prompt=rj.get("prompt", ""),
                )
        else:
            yield _sse(
                type='video_status',
                task_id=rj.get("task_id", ""),
                status=status,
                progress=rj.get("progress", 0),
            )
    except Exception as e:
        logger.debug(f"Failed to parse video_status result: {e}")
```

**依赖**：`Path` 已在文件顶部导入（`from pathlib import Path`）。

### 8.2 工具结果字段参考

`ai_video_create` 返回（`hermes_chat.py:1109-1117`）：
```json
{
  "ok": true,
  "type": "video_task",
  "task_id": "xxx",
  "status": "queued",
  "model": "doubao-video",
  "prompt": "用户提示词",
  "note": "视频生成是异步任务..."
}
```

`ai_video_task_status` 返回（`hermes_chat.py:1119-1128` + `volcengine_client.py:539-545`）：
```json
{
  "task_id": "xxx",
  "status": "succeed",
  "video_url": "https://volcengine.com/.../video.mp4",
  "progress": 100,
  "local_path": "/data/volcengine_output/volc_video_xxx.mp4"
}
```

---

## 9. 前端改动规范

### 9.1 文件：`web/src/pages/SuperAgent.vue`

#### 9.1.1 Template 改动

在现有 `v-if="msg.type === 'image'"` 分支之前插入 `video_pending` 和 `video` 分支：

```html
<!-- 视频进度卡片 -->
<div v-if="msg.type === 'video_pending'" class="video-card-pending">
  ...
</div>
<!-- 视频播放卡片 -->
<div v-else-if="msg.type === 'video'" class="video-card">
  ...
</div>
<!-- 图片卡片 (已有) -->
<div v-else-if="msg.type === 'image'" class="image-card" ...>
  ...
</div>
<!-- 文本 (已有) -->
<div v-else class="msg-text" ...>
  ...
</div>
```

**注意**：将现有 `v-if="msg.type === 'image'"` 改为 `v-else-if`，确保条件链正确。

在 Lightbox `el-image-viewer` 之后新增 Video Modal。

#### 9.1.2 Script 改动

- 新增 imports：`Loading, ZoomIn, FullScreen, Download, Close` from `@element-plus/icons-vue`
- 新增 refs：`streamVideoTasks`, `streamVideos`, `videoRefs`, `videoModalRef`, `videoModal`
- SSE switch 新增 `video_task` / `video_status` / `video` 三个 case
- 流结束后插入/更新视频消息（使用 task_id 原地更新，避免闪烁）
- `finally` 块清空 `streamVideoTasks` 和 `streamVideos`
- 新增函数：`enlargeVideo`, `fullscreenVideo`, `fullscreenModalVideo`, `closeVideoModal`, `downloadVideo`

#### 9.1.3 Style 改动

新增 `.video-card-pending`、`.video-card`、`.video-player`、`.video-card-footer`、`.video-card-prompt`、`.video-card-actions`、`.video-modal-overlay`、`.video-modal-container`、`.video-modal-player`、`.video-modal-actions` 样式。

#### 9.1.4 对话持久化

`saveConversation` 函数（`SuperAgent.vue:211-235`）中 `messages` 映射需包含视频消息字段：

```javascript
messages: state.messages.map(m => ({
  role: m.role,
  content: m.content,
  type: m.type || 'text',
  timestamp: m.timestamp || Date.now() / 1000,
  image_url: m.image_url,
  prompt: m.prompt,
  // 新增视频字段
  video_url: m.video_url,
  task_id: m.task_id,
  status: m.status,
  progress: m.progress,
})),
```

加载历史对话时（`loadConversation`），`video_pending` 类型的消息若任务已完成会显示为进度卡片（历史数据不刷新）。这是可接受的行为 — 用户重新进入对话时，未完成的历史视频任务不再轮询。

---

## 10. 验收标准

- [ ] 用户发送"生成视频"指令后，对话流中立即出现进度卡片（spinner + 提示词）
- [ ] LLM 轮询任务状态时，进度卡片的状态文字实时更新
- [ ] 视频生成完成后，进度卡片自动替换为视频播放器卡片
- [ ] 视频卡片内嵌 `<video controls>` 可直接播放，不遮挡对话流
- [ ] 点击"放大"按钮弹出 modal overlay，背景半透明，点击背景关闭
- [ ] 点击"全屏"按钮进入浏览器原生全屏，ESC 退出
- [ ] Modal overlay 内"全屏"按钮也可进入原生全屏
- [ ] 点击"下载"按钮可下载视频文件
- [ ] 视频卡片宽度不超过 400px，高度自适应
- [ ] 不影响现有图片卡片和文本消息的渲染
- [ ] 保存/加载历史对话时视频卡片可恢复（已完成的视频可重新播放）
- [ ] 兼容 VolcEngine 返回 `succeed` 和 `succeeded` 两种状态拼写

---

## 11. 注意事项

- 视频生成是异步任务，LLM 会多轮调用 `ai_video_task_status` 轮询，每轮都会触发 SSE 流。进度卡片必须通过 `task_id` 原地更新，不能每轮重新插入，否则会闪烁。
- `ai_video_task_status` 返回的 `local_path` 是服务器本地路径，需转换为 `/api/files/volcengine_output/{filename}` URL 供前端访问。
- VolcEngine API 返回的状态值可能是 `succeed` 而非 `succeeded` — 后端和前端均需兼容。
- `<video>` 标签的 `preload="metadata"` 确保只加载元数据，不自动下载整个视频。
- Modal overlay 的 `z-index: 2000` 需高于现有 Lightbox（`el-image-viewer` 默认 z-index ~2000），确保不被遮挡。
- 视频文件格式为 `.mp4`，浏览器原生支持，无需额外编解码器。
