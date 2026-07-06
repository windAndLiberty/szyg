# 超级员工对话历史 — 右键菜单功能规范

> 本文件定义超级员工（SuperAgent）对话历史面板的右键上下文菜单规范。
> 涉及源码：`web/src/pages/SuperAgent.vue`、`server/szyg/api/conversation_routes.py`
> 执行者：Elite_Coder

---

## 1. 功能概览

对话历史面板中每个对话项（`conv-item`）支持右键点击弹出上下文菜单，提供以下操作：

| 菜单项 | 图标 | 说明 |
|--------|------|------|
| 重命名 | `Edit` | 修改对话标题 |
| 置顶/取消置顶 | `Top` / `Bottom` | 固定到列表顶部 / 取消固定 |
| 导出 | `Download` | 导出为 Markdown 文件下载 |
| 删除 | `Delete` | 删除对话（二次确认） |

---

## 2. 后端改动

### 2.1 文件：`server/szyg/api/conversation_routes.py`

#### 2.1.1 `ConversationUpdate` 模型新增字段

```python
class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    messages: Optional[list[ConversationMessage]] = None
    pinned: Optional[bool] = None      # 新增
```

#### 2.1.2 `update_conversation` 接口新增 `pinned` 处理

在现有 `PUT /{conv_id}` 接口中新增：

```python
if body.pinned is not None:
    conv["pinned"] = body.pinned
```

#### 2.1.3 `_list_convs` 返回 `pinned` 字段

```python
convs.append({
    "id": f.stem,
    "title": data.get("title", ""),
    "message_count": len(data.get("messages", [])),
    "agent_id": data.get("agent_id", ""),
    "model": data.get("model", ""),
    "created_at": data.get("created_at", ""),
    "updated_at": data.get("updated_at", ""),
    "pinned": data.get("pinned", False),   # 新增
})
```

#### 2.1.4 `list_conversations` 排序逻辑

置顶对话排在最前，其余按 `updated_at` 降序：

```python
@router.get("")
async def list_conversations(limit: int = 50):
    convs = _list_convs()
    convs.sort(
        key=lambda c: (
            c.get("pinned", False),
            c.get("updated_at", ""),
        ),
        reverse=True,
    )
    return {"conversations": convs[:limit]}
```

**注意**：`reverse=True` 会对 tuple 整体反转。`pinned=True` (1) > `pinned=False` (0)，`updated_at` 字符串按字典序降序排列（ISO 格式可正确排序）。这实现了置顶在前、其余按时间倒序。

#### 2.1.5 `create_conversation` 新增 `pinned` 默认值

```python
data = {
    "id": conv_id,
    "title": body.title or "新对话",
    "messages": [m.model_dump() for m in body.messages],
    "agent_id": body.agent_id,
    "model": body.model,
    "pinned": False,    # 新增
    "created_at": now,
    "updated_at": now,
}
```

---

## 3. 前端改动

### 3.1 文件：`web/src/pages/SuperAgent.vue`

#### 3.1.1 Template — 对话项添加右键事件

```html
<div
  v-for="conv in state.conversations"
  :key="conv.id"
  class="conv-item"
  :class="{ active: conv.id === state.activeConvId, pinned: conv.pinned }"
  @click="selectConversation(conv.id)"
  @contextmenu.prevent="openContextMenu($event, conv)"
>
  <div class="conv-item-title">
    <span v-if="conv.pinned" class="pin-icon">📌</span>
    {{ conv.title }}
  </div>
  <div class="conv-item-time">{{ formatTime(conv.updated_at) }}</div>
</div>
```

#### 3.1.2 Template — 右键菜单组件

使用 `el-dropdown` 配合 `@contextmenu` 实现，或自建浮动菜单。推荐自建轻量菜单：

```html
<!-- 右键菜单 -->
<div
  v-if="ctxMenu.show"
  class="ctx-menu"
  :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
  @click.stop
>
  <div class="ctx-menu-item" @click="renameConversation(ctxMenu.conv)">
    <el-icon><Edit /></el-icon>
    <span>重命名</span>
  </div>
  <div class="ctx-menu-item" @click="togglePin(ctxMenu.conv)">
    <el-icon><Top v-if="!ctxMenu.conv?.pinned" /><CancelTop v-else /></el-icon>
    <span>{{ ctxMenu.conv?.pinned ? '取消置顶' : '置顶' }}</span>
  </div>
  <div class="ctx-menu-item" @click="exportConversation(ctxMenu.conv)">
    <el-icon><Download /></el-icon>
    <span>导出</span>
  </div>
  <div class="ctx-menu-divider"></div>
  <div class="ctx-menu-item danger" @click="deleteConversation(ctxMenu.conv)">
    <el-icon><Delete /></el-icon>
    <span>删除</span>
  </div>
</div>
```

**点击空白关闭菜单**：在 `super-agent` 根 div 上添加 `@click="closeContextMenu"`。

#### 3.1.3 Script — 新增状态和函数

```javascript
import { Edit, Top, CancelTop, Download, Delete } from '@element-plus/icons-vue'

// 右键菜单状态
const ctxMenu = reactive({
  show: false,
  x: 0,
  y: 0,
  conv: null,
})

function openContextMenu(event, conv) {
  ctxMenu.show = true
  ctxMenu.x = event.clientX
  ctxMenu.y = event.clientY
  ctxMenu.conv = conv
}

function closeContextMenu() {
  ctxMenu.show = false
}
```

#### 3.1.4 重命名函数

```javascript
async function renameConversation(conv) {
  closeContextMenu()
  try {
    const { value } = await ElMessageBox.prompt('请输入新的对话标题', '重命名', {
      inputValue: conv.title,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /.+/,
      inputErrorMessage: '标题不能为空',
    })
    await axios.put(`/api/conversations/${conv.id}`, { title: value })
    conv.title = value
  } catch {}
}
```

#### 3.1.5 置顶/取消置顶函数

```javascript
async function togglePin(conv) {
  closeContextMenu()
  const newPinned = !conv.pinned
  await axios.put(`/api/conversations/${conv.id}`, { pinned: newPinned })
  conv.pinned = newPinned
  await loadConversations()
}
```

#### 3.1.6 导出函数

```javascript
function exportConversation(conv) {
  closeContextMenu()
  // 加载完整对话内容
  axios.get(`/api/conversations/${conv.id}`).then(({ data }) => {
    const messages = data.messages || []
    const lines = [
      `# ${data.title || conv.title}`,
      '',
      `> 导出时间: ${new Date().toLocaleString('zh-CN')}`,
      `> 消息数: ${messages.length}`,
      '',
      '---',
      '',
    ]
    for (const m of messages) {
      const role = m.role === 'user' ? '👤 用户' : m.role === 'assistant' ? '🤖 助手' : '🔧 系统'
      lines.push(`### ${role}`)
      lines.push('')
      lines.push(m.content || '(空)')
      lines.push('')
      lines.push('---')
      lines.push('')
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${data.title || conv.title || '对话'}.md`
    a.click()
    URL.revokeObjectURL(url)
  })
}
```

#### 3.1.7 删除函数

```javascript
async function deleteConversation(conv) {
  closeContextMenu()
  try {
    await ElMessageBox.confirm(
      `确定删除对话「${conv.title}」吗？此操作不可撤销。`,
      '删除对话',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await axios.delete(`/api/conversations/${conv.id}`)
    // 如果删除的是当前激活对话，清空消息
    if (state.activeConvId === conv.id) {
      clearMessages()
    }
    await loadConversations()
  } catch {}
}
```

#### 3.1.8 ElMessageBox 引入

确认 `ElMessageBox` 已从 `element-plus` 导入。如果未导入，在 script setup 顶部添加：

```javascript
import { ElMessageBox } from 'element-plus'
```

---

## 4. CSS 样式规范

### 4.1 右键菜单

```css
.ctx-menu {
  position: fixed;
  z-index: 3000;
  min-width: 140px;
  background: var(--bg-card, #fff);
  border: 1px solid var(--border-light, #e4e7ed);
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  padding: 4px 0;
}

.ctx-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
  color: var(--text-primary, #303133);
  cursor: pointer;
  transition: background 0.15s;
}

.ctx-menu-item:hover {
  background: var(--fill-light, #f5f7fa);
}

.ctx-menu-item.danger {
  color: var(--color-danger, #f56c6c);
}

.ctx-menu-item.danger:hover {
  background: var(--color-danger-light-9, #fef0f0);
}

.ctx-menu-divider {
  height: 1px;
  background: var(--border-light, #e4e7ed);
  margin: 4px 0;
}
```

### 4.2 置顶对话项样式

```css
.conv-item.pinned {
  background: var(--fill-light, #f5f7fa);
}

.conv-item.pinned .pin-icon {
  font-size: 12px;
  margin-right: 4px;
}
```

### 4.3 菜单边界处理

右键菜单可能超出窗口边界。在 `openContextMenu` 中需做边界检测：

```javascript
function openContextMenu(event, conv) {
  ctxMenu.show = true
  ctxMenu.conv = conv
  // 延迟一帧获取菜单实际尺寸后做边界检测
  nextTick(() => {
    const menuEl = document.querySelector('.ctx-menu')
    const menuW = menuEl?.offsetWidth || 140
    const menuH = menuEl?.offsetHeight || 160
    ctxMenu.x = Math.min(event.clientX, window.innerWidth - menuW - 8)
    ctxMenu.y = Math.min(event.clientY, window.innerHeight - menuH - 8)
  })
}
```

---

## 5. 数据流

### 5.1 重命名

```
右键 → 重命名 → ElMessageBox.prompt 输入新标题
  → PUT /api/conversations/{id} { title: "新标题" }
  → 后端更新 title + updated_at
  → 前端 conv.title = 新标题
```

### 5.2 置顶

```
右键 → 置顶 → PUT /api/conversations/{id} { pinned: true }
  → 后端更新 pinned + updated_at
  → 前端 loadConversations() 重新加载列表（后端排序：pinned 在前）
```

### 5.3 导出

```
右键 → 导出 → GET /api/conversations/{id} 获取完整消息
  → 前端拼接 Markdown 字符串
  → Blob + URL.createObjectURL + <a download> 下载
```

### 5.4 删除

```
右键 → 删除 → ElMessageBox.confirm 二次确认
  → DELETE /api/conversations/{id}
  → 后端删除 JSON 文件
  → 前端：若删除的是当前激活对话 → clearMessages()
  → loadConversations() 重新加载列表
```

---

## 6. 验收标准

- [ ] 右键点击对话项弹出上下文菜单，菜单位置在鼠标点击处，不超出窗口边界
- [ ] 点击空白处或菜单项后菜单自动关闭
- [ ] 重命名：弹出输入框预填当前标题，确认后标题立即更新
- [ ] 置顶：置顶后对话移到列表顶部，显示📌图标，背景高亮
- [ ] 取消置顶：恢复原排序，移除📌图标
- [ ] 导出：下载 `.md` 文件，内容包含标题、时间、所有消息（按角色区分）
- [ ] 删除：弹出确认框，确认后对话从列表消失；若删除的是当前对话则清空聊天区
- [ ] 删除菜单项文字为红色，与其他菜单项视觉区分
- [ ] 菜单项有 hover 高亮效果
- [ ] 不影响现有左键切换对话和"+"新建对话功能

---

## 7. 注意事项

- `ElMessageBox` 需确认已从 `element-plus` 导入，否则 prompt/confirm 无法弹出。
- 后端 `PUT` 接口已支持 `title` 更新，只需新增 `pinned` 字段处理，无需新建 `PATCH` 接口。
- `_list_convs` 当前按 `st_mtime` 排序，改为返回 `pinned` 字段后由 `list_conversations` 端点重新排序。
- 导出功能纯前端实现，不需要后端新增接口。
- 右键菜单使用 `position: fixed` + `clientX/clientY` 定位，需做窗口边界检测避免菜单溢出。
- 对话存储为 JSON 文件，`pinned` 字段对旧数据默认为 `False`（`data.get("pinned", False)`），无需迁移。
