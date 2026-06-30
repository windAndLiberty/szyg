<template>
  <teleport to="body">
    <div class="super-staff-overlay" :class="{ open: store.isOpen }" @click="onOverlayClick">
      <div class="super-staff-panel" :class="{ open: store.isOpen, fullscreen: store.isFullscreen }" @click.stop>
        <!-- Panel Header -->
        <div class="panel-header">
          <div class="header-left">
            <span class="status-light" :class="store.connectionStatus"></span>
            <span class="panel-title">超级员工</span>
          </div>
          <div class="header-right">
            <button class="header-btn" title="新建对话" @click="newConversation">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M12 5v14M5 12h14"/>
              </svg>
            </button>
            <el-dropdown v-if="store.conversations.length" trigger="click" @command="switchConversation">
              <button class="header-btn" title="历史对话">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
                </svg>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="c in store.conversations.slice(0, 10)" :key="c.id" :command="c.id">
                    <span style="font-size:12px">{{ c.title?.slice(0, 30) || '新对话' }}</span>
                    <span style="color:var(--text-tertiary);font-size:10px;margin-left:8px">{{ c.message_count }}条</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <button class="header-btn" :title="store.isFullscreen ? '退出全屏' : '全屏'" @click="toggleFullscreen">
              <svg v-if="!store.isFullscreen" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>
              </svg>
            </button>
            <button class="header-btn" title="关闭" @click="store.close">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Quick Prompts -->
        <div class="quick-prompts-bar">
          <button v-for="p in store.quickPrompts" :key="p" @click="fillPrompt(p)" class="prompt-chip">
            {{ p }}
          </button>
        </div>

        <!-- Message List -->
        <div class="message-list" ref="msgListRef">
          <!-- Empty state -->
          <div v-if="store.messages.length === 0 && !store.isThinking" class="placeholder-text">
            <p>👋 我是你的超级员工</p>
            <p>可以帮你执行各种 AI 任务，比如内容创作、数据分析、客户跟进等。</p>
          </div>

          <!-- Messages -->
          <div v-for="msg in store.messages" :key="msg.id" class="msg-wrapper">
            <!-- User text -->
            <div v-if="msg.type === 'text' && msg.role === 'user'" class="msg-row user">
              <div class="msg-bubble user">{{ msg.content }}</div>
            </div>

            <!-- Assistant text -->
            <div v-else-if="msg.type === 'text' && msg.role === 'assistant'" class="msg-row assistant">
              <div class="msg-bubble assistant markdown-body" v-html="renderMarkdown(msg.content)"></div>
            </div>

            <!-- Thinking -->
            <div v-else-if="msg.type === 'thinking'" class="msg-row thinking">
              <div class="thinking-box">
                <span class="thinking-icon">⏳</span>
                <span class="thinking-text">{{ msg.content }}</span>
                <span class="thinking-pulse"></span>
              </div>
            </div>

            <!-- Tool Call -->
            <div v-else-if="msg.type === 'tool_call'" class="msg-row tool">
              <div class="tool-card">
                <div class="tool-header">
                  <span class="tool-icon">🔧</span>
                  <span class="tool-name">{{ msg.toolCall?.tool || '工具调用' }}</span>
                  <span class="tool-status" :class="msg.toolCall?.status">{{ statusText(msg.toolCall?.status) }}</span>
                </div>
                <div class="tool-params" v-if="msg.toolCall?.params && Object.keys(msg.toolCall.params).length">
                  <code>{{ formatParams(msg.toolCall.params) }}</code>
                </div>
                <div class="tool-progress-bar" v-if="msg.toolCall?.status === 'running'">
                  <div class="tool-progress-fill"></div>
                </div>
              </div>
            </div>

            <!-- Tool Result -->
            <div v-else-if="msg.type === 'tool_result'" class="msg-row result">
              <div class="result-card">
                <div class="result-header">
                  <span class="result-icon">✅</span>
                  <span class="result-title">{{ msg.result?.tool || '执行完成' }}</span>
                </div>
                <div class="result-preview" :class="{ expanded: expandedResults[msg.id] }">
                  <pre><code>{{ formatResultPreview(msg.result?.data) }}</code></pre>
                </div>
                <button v-if="isResultLong(msg.result?.data)" class="expand-btn" @click="toggleExpand(msg.id)">
                  {{ expandedResults[msg.id] ? '收起' : '展开' }}
                </button>
              </div>
            </div>

            <!-- Error -->
            <div v-else-if="msg.type === 'error'" class="msg-row error">
              <div class="error-card">
                <div class="error-header">
                  <span class="error-icon">❌</span>
                  <span class="error-text">{{ msg.content }}</span>
                </div>
                <button class="retry-btn" @click="retryFromError">重试</button>
              </div>
            </div>
          </div>

          <!-- Streaming assistant text (real-time, not yet saved) -->
          <div v-if="store.streaming && streamText" class="msg-wrapper">
            <div class="msg-row assistant">
              <div class="msg-bubble assistant streaming markdown-body" v-html="renderMarkdown(streamText)"></div>
            </div>
          </div>
        </div>

        <!-- Input Area -->
        <div class="input-area">
          <textarea
            v-model="inputText"
            class="chat-input"
            placeholder="输入任务指令... (Enter 发送, Shift+Enter 换行)"
            rows="3"
            @keydown.enter.exact.prevent="sendMessage"
            :disabled="store.streaming"
          />
          <button v-if="!store.streaming" class="send-btn" :disabled="!inputText.trim()" @click="sendMessage">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
            </svg>
          </button>
          <button v-else class="send-btn stop-btn" @click="stopStream">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <rect x="6" y="6" width="12" height="12" rx="2"/>
            </svg>
          </button>
        </div>

        <!-- Panel Footer -->
        <div class="panel-footer">
          <el-select v-model="store.activeStaffId" size="small" class="staff-picker" placeholder="通用" clearable @clear="store.activeStaffId = ''">
            <el-option label="🐙 通用员工" value="" />
            <el-option v-for="s in store.staffList" :key="s.id" :label="s.emoji + ' ' + s.name" :value="s.id" />
          </el-select>
          <el-select v-model="store.model" size="small" class="model-picker" placeholder="选择模型">
            <el-option v-for="m in store.models" :key="m" :label="m" :value="m" />
          </el-select>
          <span class="connection-status" :class="store.connectionStatus">
            {{ statusLabel }}
          </span>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useSuperStaffStore } from '../stores/superStaff'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

const store = useSuperStaffStore()
const inputText = ref('')
const msgListRef = ref(null)
const streamText = ref('')
const expandedResults = ref({})

const statusLabel = computed(() => {
  const map = { connected: '已连接', disconnected: '未连接', reconnecting: '重连中...' }
  return map[store.connectionStatus] || '未知'
})

function renderMarkdown(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text))
}

function onOverlayClick() {
  store.close()
}

function toggleFullscreen() {
  store.setFullscreen(!store.isFullscreen)
}

function fillPrompt(p) {
  inputText.value = p
}

function statusText(status) {
  const map = { running: '执行中', completed: '已完成', failed: '失败' }
  return map[status] || status
}

function formatParams(params) {
  try {
    const p = typeof params === 'string' ? JSON.parse(params) : params
    return JSON.stringify(p, null, 2)
  } catch {
    return String(params)
  }
}

function formatResultPreview(data) {
  try {
    const d = typeof data === 'string' ? JSON.parse(data) : data
    return JSON.stringify(d, null, 2)
  } catch {
    return String(data)
  }
}

function isResultLong(data) {
  const str = formatResultPreview(data)
  return str.split('\n').length > 3 || str.length > 200
}

function toggleExpand(id) {
  expandedResults.value[id] = !expandedResults.value[id]
}

async function scrollToBottom() {
  await nextTick()
  if (msgListRef.value) {
    msgListRef.value.scrollTop = msgListRef.value.scrollHeight
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || store.streaming) return

  // 1. Add user message
  store.addMessage({ role: 'user', type: 'text', content: text })
  inputText.value = ''
  streamText.value = ''
  store.startStreaming()

  await scrollToBottom()

  // 2. Build message history for API (only text messages from user/assistant)
  const apiMessages = store.messages
    .filter(m => m.type === 'text' && (m.role === 'user' || m.role === 'assistant'))
    .map(m => ({ role: m.role, content: m.content }))

  // 3. Create AbortController
  const controller = new AbortController()
  store.setAbortController(controller)

  try {
    const resp = await fetch('/api/hermes/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({
        model: store.model,
        messages: apiMessages,
        stream: true,
        agent_id: store.activeStaffId || undefined,
      }),
      signal: controller.signal,
    })

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          await handleSSEEvent(event)
        } catch (_) {
          // ignore malformed JSON
        }
      }
      await scrollToBottom()
    }

    // Flush remaining buffer
    if (buffer.trim()) {
      const line = buffer.trim()
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6))
          await handleSSEEvent(event)
        } catch (_) {}
      }
    }

  } catch (e) {
    if (e.name === 'AbortError') {
      // User cancelled — save partial content
      if (streamText.value) {
        store.addMessage({ role: 'assistant', type: 'text', content: streamText.value + '\n\n⚠️ _用户已终止_' })
      }
    } else {
      store.addMessage({ role: 'system', type: 'error', content: '连接出错: ' + e.message })
    }
  }

  // Save any remaining stream text as assistant message
  if (streamText.value) {
    store.addMessage({ role: 'assistant', type: 'text', content: streamText.value })
  }

  streamText.value = ''
  store.stopStreaming()
  // Auto-save conversation after each exchange
  store.saveConversation(null).catch(() => {})
  await scrollToBottom()
}

async function handleSSEEvent(event) {
  switch (event.type) {
    case 'text':
      streamText.value += event.content
      break

    case 'status': {
      // Find existing thinking message or create one
      const lastThinking = [...store.messages].reverse().find(m => m.type === 'thinking')
      if (lastThinking && store.streaming) {
        store.updateMessage(lastThinking.id, { content: event.content })
      } else {
        store.addMessage({ role: 'system', type: 'thinking', content: event.content })
      }
      break
    }

    case 'tool_call': {
      let params = event.args || {}
      if (typeof params === 'string') {
        try { params = JSON.parse(params) } catch (_) {}
      }
      const toolId = event.id || ''
      store.addMessage({
        role: 'system',
        type: 'tool_call',
        toolCall: {
          id: toolId,
          tool: event.tool || 'unknown',
          params,
          progress: 0,
          status: 'running',
        },
      })
      store.currentToolCall = event.tool || 'unknown'
      store.addActiveTask({ id: toolId, name: event.tool || 'unknown', status: 'running' })
      break
    }

    case 'tool_result': {
      const matching = [...store.messages].reverse().find(
        m => m.type === 'tool_call' && m.toolCall?.id === event.id
      ) || [...store.messages].reverse().find(m => m.type === 'tool_call')
      if (matching) {
        // Try to detect error in result
        let isError = false
        let resultData = event.result
        try {
          const parsed = JSON.parse(event.result)
          if (parsed.error || parsed.success === false) isError = true
          resultData = parsed
        } catch (_) {}

        if (isError) {
          store.updateMessage(matching.id, {
            type: 'error',
            content: typeof resultData === 'object' ? (resultData.error || '执行失败') : '执行失败',
          })
        } else {
          store.updateMessage(matching.id, {
            type: 'tool_result',
            result: {
              tool: matching.toolCall?.tool || event.tool || 'unknown',
              data: resultData,
            },
          })
        }
      }
      store.currentToolCall = null
      store.updateActiveTask(event.id, { status: 'success' })
      break
    }

    case 'error':
      store.addMessage({ role: 'system', type: 'error', content: event.content || '未知错误' })
      store.setConnectionStatus('disconnected')
      break

    case 'done':
      // Mark round complete — nothing to display
      break
  }
  await scrollToBottom()
}

function stopStream() {
  store.cancel()
  if (streamText.value) {
    store.addMessage({ role: 'assistant', type: 'text', content: streamText.value + '\n\n⚠️ _用户已终止_' })
    streamText.value = ''
  }
}

function retryFromError() {
  // Retry last user message
  const lastUser = [...store.messages].reverse().find(m => m.role === 'user')
  if (lastUser) {
    inputText.value = lastUser.content
    sendMessage()
  }
}

function onKeydown(e) {
  if (e.key === 'Escape' && store.isOpen) {
    store.close()
  }
}

function newConversation() {
  store.clearMessages()
  store.activeConvId = ''
}

async function switchConversation(convId) {
  await store.loadConversation(convId)
  scrollToBottom()
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  store.loadModels()
  store.loadStaffList()
  store.loadConversations()
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  store.stopHeartbeat()
  // Clean up any active stream
  if (store.abortController) {
    store.abortController.abort()
  }
})

// Watch for external prompt submission (from Dashboard quick-input, etc.)
watch(() => store.isOpen, (open) => {
  if (open) {
    store.startHeartbeat()
    const pending = store.consumePendingPrompt()
    if (pending) {
      inputText.value = pending
      nextTick(() => sendMessage())
    }
  } else {
    store.stopHeartbeat()
  }
})
</script>

<style scoped>
.super-staff-overlay {
  position: fixed;
  inset: 0;
  z-index: 1999;
  background: rgba(0, 0, 0, 0.3);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}
.super-staff-overlay.open {
  opacity: 1;
  pointer-events: auto;
}

.super-staff-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 420px;
  background: var(--bg-overlay, rgba(255, 255, 255, 0.95));
  backdrop-filter: blur(12px);
  border-left: 1px solid var(--border-light, #e8e6e3);
  z-index: 2000;
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.3s ease, width 0.3s ease;
}
.super-staff-panel.open {
  transform: translateX(0);
}
.super-staff-panel.fullscreen {
  width: 100vw;
}

/* Panel Header */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-light, #e8e6e3);
  flex-shrink: 0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.status-light {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #5a6e88;
}
.status-light.connected { background: #22c55e; }
.status-light.disconnected { background: #5a6e88; }
.status-light.reconnecting { background: #fbbf24; animation: blink 1s infinite; }
.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
}
.header-right {
  display: flex;
  gap: 8px;
}
.header-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid var(--border-light, #e8e6e3);
  background: transparent;
  color: var(--text-secondary, #5c5c5c);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.header-btn:hover {
  border-color: var(--border-active, rgba(79, 70, 229, 0.3));
  color: var(--accent, #4f46e5);
  background: var(--accent-soft, rgba(79, 70, 229, 0.08));
}

/* Quick Prompts */
.quick-prompts-bar {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-light, #e8e6e3);
  overflow-x: auto;
  flex-shrink: 0;
  scrollbar-width: none;
}
.quick-prompts-bar::-webkit-scrollbar { display: none; }
.prompt-chip {
  padding: 6px 14px;
  border-radius: 16px;
  border: 1px solid var(--border-color, #e8e6e3);
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  color: var(--text-secondary, #5c5c5c);
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
  transition: all 0.2s;
}
.prompt-chip:hover {
  border-color: var(--border-active, rgba(79, 70, 229, 0.3));
  color: var(--accent, #4f46e5);
  background: var(--accent-soft, rgba(79, 70, 229, 0.08));
}

/* Message List */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  scroll-behavior: smooth;
}
.placeholder-text {
  text-align: center;
  color: var(--text-tertiary, #999999);
  padding: 40px 20px;
}
.placeholder-text p {
  margin: 8px 0;
  font-size: 13px;
  line-height: 1.6;
}

/* Message Rows */
.msg-wrapper {
  margin-bottom: 12px;
}
.msg-row {
  display: flex;
  margin: 8px 0;
}
.msg-row.user {
  justify-content: flex-end;
}
.msg-row.assistant {
  justify-content: flex-start;
}
.msg-row.thinking,
.msg-row.tool,
.msg-row.result,
.msg-row.error {
  justify-content: flex-start;
}

/* Bubbles */
.msg-bubble {
  max-width: 80%;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}
.msg-bubble.user {
  background: var(--accent, #4f46e5);
  color: var(--text-inverse, #fff);
  border-radius: 12px 12px 2px 12px;
}
.msg-bubble.assistant {
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  color: var(--text-primary, #1a1a1a);
  border-radius: 12px 12px 12px 2px;
  border: 1px solid var(--border-light, #e8e6e3);
}
.msg-bubble.assistant.streaming {
  border-color: var(--border-active, rgba(79, 70, 229, 0.3));
}

/* Thinking */
.thinking-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 10px;
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  color: var(--text-tertiary, #999999);
  font-size: 12px;
}
.thinking-icon {
  font-size: 14px;
  animation: pulse-rotate 2s ease-in-out infinite;
}
.thinking-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent, #4f46e5);
  animation: pulse-dot 1.5s ease-in-out infinite;
}
@keyframes pulse-rotate {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(180deg); }
}
@keyframes pulse-dot {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

/* Tool Call Card */
.tool-card {
  max-width: 90%;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border-color, #e8e6e3);
  background: var(--bg-card, #ffffff);
  font-size: 12px;
}
.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.tool-icon {
  font-size: 14px;
}
.tool-name {
  font-weight: 600;
  color: var(--accent, #4f46e5);
}
.tool-status {
  margin-left: auto;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--accent-soft, rgba(79, 70, 229, 0.08));
  color: var(--accent, #4f46e5);
}
.tool-status.completed {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}
.tool-status.failed {
  background: rgba(244, 63, 94, 0.1);
  color: #f43f5e;
}
.tool-params {
  margin-top: 6px;
  padding: 8px;
  border-radius: 6px;
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  overflow-x: auto;
}
.tool-params code {
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 11px;
  color: var(--text-secondary, #5c5c5c);
  white-space: pre-wrap;
  word-break: break-word;
}
.tool-progress-bar {
  margin-top: 8px;
  height: 4px;
  border-radius: 2px;
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  overflow: hidden;
  position: relative;
}
.tool-progress-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--accent, #4f46e5);
  width: 60%;
  animation: progress-shimmer 1.5s ease-in-out infinite;
}
@keyframes progress-shimmer {
  0% { transform: translateX(-120%); }
  100% { transform: translateX(200%); }
}

/* Result Card */
.result-card {
  max-width: 90%;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(34, 197, 94, 0.2);
  background: var(--bg-card, #ffffff);
  font-size: 12px;
}
.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.result-icon {
  font-size: 14px;
}
.result-title {
  font-weight: 600;
  color: #22c55e;
}
.result-preview {
  max-height: 4.5em;
  overflow: hidden;
  transition: max-height 0.3s ease;
}
.result-preview.expanded {
  max-height: 500px;
  overflow: auto;
}
.result-preview pre {
  margin: 0;
  padding: 8px;
  border-radius: 6px;
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  overflow-x: auto;
}
.result-preview code {
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 11px;
  color: var(--text-secondary, #5c5c5c);
  white-space: pre-wrap;
  word-break: break-word;
}
.expand-btn {
  margin-top: 8px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #e8e6e3);
  background: transparent;
  color: var(--text-secondary, #5c5c5c);
  cursor: pointer;
  font-size: 11px;
  transition: all 0.2s;
}
.expand-btn:hover {
  border-color: var(--border-active, rgba(79, 70, 229, 0.3));
  color: var(--accent, #4f46e5);
}

/* Error Card */
.error-card {
  max-width: 90%;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(244, 63, 94, 0.3);
  background: var(--rose-500-10, rgba(244, 63, 94, 0.1));
  font-size: 12px;
}
.error-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.error-icon {
  font-size: 14px;
}
.error-text {
  color: var(--rose-400, #fb7185);
  flex: 1;
  word-break: break-word;
}
.retry-btn {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid rgba(244, 63, 94, 0.3);
  background: transparent;
  color: var(--rose-400, #fb7185);
  cursor: pointer;
  font-size: 11px;
  transition: all 0.2s;
}
.retry-btn:hover {
  background: rgba(244, 63, 94, 0.15);
}

/* Input Area */
.input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--border-light, #e8e6e3);
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}
.chat-input {
  flex: 1;
  background: var(--input-bg, #f5f5f5);
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 10px 14px;
  color: var(--text-primary, #1a1a1a);
  font-size: 13px;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
  font-family: inherit;
}
.chat-input::placeholder {
  color: var(--text-muted, #b0b0b0);
}
.chat-input:focus {
  border-color: var(--accent, #4f46e5);
  background: var(--bg-page, #ffffff);
}
.chat-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: none;
  background: var(--accent, #4f46e5);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.2s;
}
.send-btn:hover { opacity: 0.9; }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.stop-btn {
  background: var(--rose-500, #f43f5e);
  animation: pulse-btn 1.5s ease-in-out infinite;
}
@keyframes pulse-btn {
  0%, 100% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(244, 63, 94, 0); }
}

/* Panel Footer */
.panel-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-top: 1px solid var(--border-light, #e8e6e3);
  font-size: 11px;
  flex-shrink: 0;
}
.model-picker {
  width: 220px;
}
.connection-status {
  color: var(--text-tertiary, #999999);
}
.connection-status.connected { color: #22c55e; }
.connection-status.reconnecting { color: #fbbf24; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* Markdown Body */
.markdown-body :deep(h1) { font-size: 1.4em; font-weight: 700; margin: 0.5em 0 0.3em; }
.markdown-body :deep(h2) { font-size: 1.2em; font-weight: 600; margin: 0.5em 0 0.2em; }
.markdown-body :deep(h3) { font-size: 1.1em; font-weight: 600; margin: 0.4em 0 0.2em; }
.markdown-body :deep(p) { margin: 0.3em 0; }
.markdown-body :deep(p:first-child) { margin-top: 0; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { margin: 0.3em 0; padding-left: 1.5em; }
.markdown-body :deep(li) { margin: 0.15em 0; }
.markdown-body :deep(blockquote) {
  margin: 0.4em 0; padding: 6px 14px;
  border-left: 3px solid var(--accent, #4f46e5);
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  border-radius: 0 6px 6px 0;
  color: var(--text-secondary, #5c5c5c);
}
.markdown-body :deep(pre) {
  margin: 0.5em 0; padding: 10px 12px;
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
  border: 1px solid var(--border-light, #e8e6e3);
}
.markdown-body :deep(pre code) {
  background: transparent; padding: 0;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
}
.markdown-body :deep(code) {
  padding: 2px 5px; border-radius: 4px;
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  color: var(--accent, #4f46e5);
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 0.9em;
}
.markdown-body :deep(table) {
  width: 100%; border-collapse: collapse; margin: 0.5em 0; font-size: 12px;
}
.markdown-body :deep(th) {
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  font-weight: 600; text-align: left;
  padding: 6px 10px; border: 1px solid var(--border-color, #e8e6e3);
}
.markdown-body :deep(td) { padding: 5px 10px; border: 1px solid var(--border-color, #e8e6e3); }
.markdown-body :deep(tr:nth-child(even)) { background: var(--bg-hover, rgba(0, 0, 0, 0.03)); }
.markdown-body :deep(a) { color: var(--accent, #4f46e5); text-decoration: underline; }
.markdown-body :deep(strong) { font-weight: 700; color: var(--text-primary, #1a1a1a); }
.markdown-body :deep(img) { max-width: 100%; border-radius: 6px; margin: 0.3em 0; }
</style>
