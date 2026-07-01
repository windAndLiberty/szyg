<template>
  <div class="super-agent">
    <div class="agent-layout">
      <!-- Left: Conversation History Panel -->
      <div class="conv-history-panel">
        <div class="conv-header">
          <span class="conv-title">对话历史</span>
          <el-button text size="small" @click="newConversation" class="new-btn">
            <el-icon><Plus /></el-icon>
          </el-button>
        </div>
        <div class="conv-list" v-if="state.conversations.length > 0">
          <div
            v-for="conv in state.conversations"
            :key="conv.id"
            class="conv-item"
            :class="{ active: conv.id === state.activeConvId }"
            @click="selectConversation(conv.id)"
          >
            <div class="conv-item-title">{{ conv.title }}</div>
            <div class="conv-item-time">{{ formatTime(conv.updated_at) }}</div>
          </div>
        </div>
        <div v-else class="conv-empty">
          <div class="empty-icon">💬</div>
          <div class="empty-text">暂无对话记录</div>
        </div>
      </div>

      <!-- Right: Chat Area -->
      <div class="chat-area">
        <!-- Messages Area -->
        <div class="messages-area" ref="messagesRef">
          <!-- Welcome Empty State -->
          <div v-if="state.messages.length === 0" class="welcome-state">
            <div class="agent-icon">🤖</div>
            <div class="welcome-title">你好，我是超级员工</div>
            <div class="welcome-desc">用一句话指挥我完成任何营销任务</div>
            <div class="quick-cards-grid">
              <div
                v-for="card in quickCards"
                :key="card.title"
                class="quick-card"
                @click="sendQuickCard(card.content)"
              >
                <div class="card-title">{{ card.title }}</div>
                <div class="card-desc">{{ card.desc }}</div>
              </div>
            </div>
          </div>

          <!-- Messages -->
          <div v-for="msg in state.messages" :key="msg.id" class="message" :class="msg.role">
            <div class="msg-avatar">{{ msg.role === 'user' ? getUserInitial() : '🤖' }}</div>
            <div class="msg-content">
              <div class="msg-text" v-html="renderMarkdown(msg.content)"></div>
              <div v-if="msg.toolCall" class="tool-calls">
                <div class="tool-call-item">
                  <el-tag size="small" :type="msg.toolCall.status === 'success' ? 'success' : msg.toolCall.status === 'error' ? 'danger' : 'warning'">
                    {{ msg.toolCall.tool }}
                  </el-tag>
                  <span class="tool-result">{{ msg.content }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-if="state.streaming" class="message assistant">
            <div class="msg-avatar">🤖</div>
            <div class="msg-content">
              <div class="msg-text streaming-text" v-html="renderMarkdown(streamText)"></div><span class="cursor">▊</span>
              <div v-if="streamTools.length" class="tool-calls">
                <div v-for="(tool, idx) in streamTools" :key="idx" class="tool-call-item">
                  <el-tag size="small" :type="tool.status === 'success' ? 'success' : tool.status === 'error' ? 'danger' : 'warning'">
                    {{ tool.name }}
                  </el-tag>
                  <span class="tool-result">{{ tool.result }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Input Area -->
        <div class="input-area">
          <div class="quick-tags">
            <el-tag
              v-for="tag in quickTags"
              :key="tag"
              class="quick-tag"
              effect="plain"
              round
              @click="insertTag(tag)"
            >
              {{ tag }}
            </el-tag>
          </div>
          <div class="input-row">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="2"
              placeholder="输入指令，如：帮我搜索抖音上关于AI培训的视频，生成评论并发送"
              @keydown.enter.exact.prevent="sendMessage"
              :disabled="state.streaming"
            />
            <el-button type="primary" size="large" @click="sendMessage" :loading="state.streaming">
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, reactive } from 'vue'
import { Plus, Promotion } from '@element-plus/icons-vue'
import axios from 'axios'
import { getErrorMessage, autoLogin } from '../api.js'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

const inputText = ref('')
const streamText = ref('')
const streamTools = ref([])
const messagesRef = ref(null)

const state = reactive({
  conversations: [],
  activeConvId: null,
  messages: [],
  streaming: false,
  model: 'doubao-1-5-pro-32k-250115',
  activeStaffId: null,
})

const quickCards = [
  { title: '搜索截流', desc: '搜索抖音 AI 培训视频并截流', content: '搜索抖音AI培训视频并截流' },
  { title: '生成文案', desc: '生成 5 条护肤文案', content: '生成5条护肤文案' },
  { title: '定时发布', desc: '今天 12 点发 3 个视频到抖音', content: '今天12点发3个视频到抖音' },
  { title: '数据查看', desc: '查看今日截流数据', content: '查看今日截流数据' },
  { title: '客户接待', desc: '给新客户发欢迎语', content: '给新客户发欢迎语' },
]

function renderMarkdown(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text))
}

let msgId = 0
function addMessage(msg) {
  state.messages.push({ id: ++msgId, ...msg })
}

function clearMessages() {
  state.messages = []
  state.activeConvId = null
}

async function loadConversations() {
  try {
    const { data } = await axios.get('/api/conversations')
    state.conversations = data.conversations || []
  } catch {}
}

async function loadConversation(id) {
  state.activeConvId = id
  try {
    const { data } = await axios.get(`/api/conversations/${id}`)
    state.messages = (data?.messages || []).map((m, idx) => ({
      ...m,
      id: m.id || `hist-${id}-${idx}`
    }))
  } catch {}
}

async function saveConversation() {
  try {
    const payload = {
      title: state.messages.length > 0 ? state.messages[0].content.slice(0, 50) : '新对话',
      messages: state.messages.map(m => ({
        role: m.role,
        content: m.content,
        type: m.type || 'text',
        timestamp: m.timestamp || Date.now() / 1000
      })),
      agent_id: state.activeStaffId || '',
      model: state.model
    }
    if (state.activeConvId) {
      await axios.put(`/api/conversations/${state.activeConvId}`, payload)
    } else {
      const { data } = await axios.post('/api/conversations', payload)
      if (data?.id) {
        state.activeConvId = data.id
      }
    }
  } catch {}
}

onMounted(() => {
  loadConversations()
})

function newConversation() {
  clearMessages()
}

const quickTags = [
  '搜索抖音AI培训视频并截流',
  '生成5条护肤文案',
  '今天12点发3个视频到抖音',
  '查看今日截流数据',
  '给新客户发欢迎语',
]

function insertTag(tag) {
  inputText.value = tag
}

async function selectConversation(id) {
  await loadConversation(id)
  scrollToBottom()
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || state.streaming) return

  addMessage({ role: 'user', type: 'text', content: text })
  inputText.value = ''
  await scrollToBottom()

  state.streaming = true
  streamText.value = ''
  streamTools.value = []

  const apiMessages = state.messages
    .filter(m => m.type === 'text' && (m.role === 'user' || m.role === 'assistant'))
    .map(m => ({ role: m.role, content: m.content }))

  try {
    const response = await fetch('/api/hermes/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({
        model: state.model,
        messages: apiMessages,
        stream: true,
        agent_id: state.activeStaffId || undefined,
      }),
    })

    if (!response.ok) {
      if (response.status === 401) {
        await autoLogin()
        return
      }
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          switch (event.type) {
            case 'text':
              streamText.value += event.content
              break
            case 'tool_call': {
              const name = event.tool || 'unknown'
              let args = event.args || {}
              if (typeof args === 'string') {
                try { args = JSON.parse(args) } catch {}
              }
              streamTools.value.push({
                id: event.id || '',
                name,
                status: 'running',
                result: typeof args === 'object' ? JSON.stringify(args).slice(0, 200) : String(args).slice(0, 200),
              })
              break
            }
            case 'tool_result': {
              const matching = streamTools.value.find(t => t.id === event.id)
                || (streamTools.value.length ? streamTools.value[streamTools.value.length - 1] : null)
              if (matching && matching.status === 'running') {
                let res = event.result || ''
                try {
                  const r = JSON.parse(res)
                  if (r.error) { matching.status = 'error'; res = r.error }
                } catch {}
                matching.status = matching.status === 'error' ? 'error' : 'success'
                matching.result = typeof res === 'string' ? res.slice(0, 200) : JSON.stringify(res).slice(0, 200)
              }
              break
            }
            case 'error':
              streamText.value += '\n⚠️ ' + event.content
              break
            case 'status':
            case 'done':
              break
          }
        } catch {}
      }
    }

    addMessage({
      role: 'assistant',
      type: 'text',
      content: streamText.value || '（已处理）',
    })
    for (const t of streamTools.value) {
      addMessage({
        role: 'system',
        type: 'tool_result',
        content: t.result || '',
        toolCall: { id: t.id, tool: t.name, status: t.status },
      })
    }
  } catch (e) {
    addMessage({
      role: 'assistant',
      type: 'text',
      content: `⚠️ 请求失败: ${getErrorMessage(e)}`,
    })
  } finally {
    state.streaming = false
    await saveConversation()
    await loadConversations()
    streamText.value = ''
    streamTools.value = []
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

function getUserInitial() {
  const userStr = localStorage.getItem('user')
  if (!userStr) return 'U'
  try {
    const user = JSON.parse(userStr)
    return user.username ? user.username[0].toUpperCase() : 'U'
  } catch {
    return 'U'
  }
}

function formatTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  const now = new Date()
  const diff = now - date
  const hours = Math.floor(diff / (1000 * 60 * 60))
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN')
}

function sendQuickCard(content) {
  inputText.value = content
  sendMessage()
}

onMounted(() => {
  loadConversations()
})
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════
   Super Agent Page — Full-Bleed Layout
   ═══════════════════════════════════════════════════════════════════ */
.super-agent {
  height: calc(100vh - 56px);
  display: flex;
  flex-direction: column;
}

.agent-layout {
  display: flex;
  height: 100%;
  background: var(--border-light);
}

/* ═══════════════════════════════════════════════════════════════════
   Conversation History Panel (280px)
   ═══════════════════════════════════════════════════════════════════ */
.conv-history-panel {
  width: 280px;
  background: var(--bg-page);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  border-right: 1px solid var(--border-light);
}

.conv-header {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-light);
}

.conv-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.new-btn {
  color: var(--text-tertiary);
  font-size: 20px;
}

.new-btn:hover {
  color: var(--text-primary);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conv-list::-webkit-scrollbar {
  width: 4px;
}

.conv-list::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 2px;
}

.conv-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background var(--duration-fast) var(--ease-smooth);
}

.conv-item:hover {
  background: var(--bg-hover);
}

.conv-item.active {
  background: var(--accent-soft);
}

.conv-item.active .conv-item-title {
  color: var(--accent);
}

.conv-item-title {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-item-time {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.conv-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* ═══════════════════════════════════════════════════════════════════
   Chat Area
   ═══════════════════════════════════════════════════════════════════ */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-body);
  min-width: 0;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
}

.messages-area::-webkit-scrollbar {
  width: 4px;
}

.messages-area::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 2px;
}

/* ═══════════════════════════════════════════════════════════════════
   Welcome Empty State
   ═══════════════════════════════════════════════════════════════════ */
.welcome-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.agent-icon {
  width: 64px;
  height: 64px;
  border-radius: 999px;
  background: var(--accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  margin-bottom: 24px;
}

.welcome-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.welcome-desc {
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 400px;
  text-align: center;
  margin-bottom: 32px;
}

.quick-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  max-width: 600px;
}

.quick-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-smooth);
}

.quick-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.card-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.card-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ═══════════════════════════════════════════════════════════════════
   Messages
   ═══════════════════════════════════════════════════════════════════ */
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
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
}

.msg-content {
  flex: 1;
  min-width: 0;
}

.msg-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  word-break: break-word;
}

.message.user .msg-text {
  color: var(--text-primary);
}

.message.assistant .msg-text {
  color: var(--text-secondary);
}

.streaming-text {
  color: var(--accent);
}

.cursor {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.tool-calls {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-call-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.tool-result {
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ═══════════════════════════════════════════════════════════════════
   Input Area
   ═══════════════════════════════════════════════════════════════════ */
.input-area {
  border-top: 1px solid var(--border-light);
  padding: 16px 32px;
  background: var(--bg-body);
}

.quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.quick-tag {
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-smooth);
}

.quick-tag:hover {
  background: var(--bg-active);
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

/* ═══════════════════════════════════════════════════════════════════
   Responsive
   ═══════════════════════════════════════════════════════════════════ */
@media (max-width: 1279px) {
  .conv-history-panel {
    width: 240px;
  }
  .messages-area {
    padding: 24px;
  }
  .input-area {
    padding: 16px 24px;
  }
}

@media (max-width: 1023px) {
  .conv-history-panel {
    display: none;
  }
  .messages-area {
    padding: 24px;
  }
  .quick-cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .messages-area {
    padding: 16px;
  }
  .input-area {
    padding: 16px;
  }
  .quick-cards-grid {
    grid-template-columns: 1fr;
  }
}
</style>
