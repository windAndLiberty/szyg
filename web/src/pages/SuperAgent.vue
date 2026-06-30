<template>
  <div class="super-agent">
    <div class="agent-layout">
      <!-- Left: Conversation History -->
      <div class="agent-sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">对话历史</span>
          <el-button text size="small" @click="newConversation">
            <el-icon><Plus /></el-icon>
          </el-button>
        </div>
        <div class="conversation-list">
          <div
            v-for="conv in store.conversations"
            :key="conv.id"
            class="conversation-item"
            :class="{ active: conv.id === store.activeConvId }"
            @click="selectConversation(conv.id)"
          >
            <div class="conv-title">{{ conv.title }}</div>
            <div class="conv-time">{{ conv.time }}</div>
          </div>
        </div>
      </div>

      <!-- Center: Chat Area -->
      <div class="agent-main">
        <div class="messages-area" ref="messagesRef">
          <div v-for="msg in messages" :key="msg.id" class="message" :class="msg.role">
            <div class="msg-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
            <div class="msg-content">
              <div class="msg-text" v-html="renderMarkdown(msg.content)"></div>
              <div v-if="msg.tools && msg.tools.length" class="tool-calls">
                <div v-for="tool in msg.tools" :key="tool.name" class="tool-call-item">
                  <el-tag size="small" :type="tool.status === 'success' ? 'success' : tool.status === 'error' ? 'danger' : 'warning'">
                    {{ tool.name }}
                  </el-tag>
                  <span class="tool-result">{{ tool.result }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-if="store.streaming" class="message assistant">
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
            />
            <el-button type="primary" size="large" @click="sendMessage" :loading="store.streaming">
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { Plus, Promotion } from '@element-plus/icons-vue'
import axios from 'axios'
import { getErrorMessage } from '../api.js'
import { useSuperStaffStore } from '../stores/superStaff'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

const store = useSuperStaffStore()
const inputText = ref('')
const streamText = ref('')
const streamTools = ref([])
const messagesRef = ref(null)

// Use store state for shared conversation
const messages = computed({
  get: () => store.messages,
  set: () => {}, // mutations via store methods
})

function renderMarkdown(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text))
}

onMounted(() => {
  store.loadConversations()
  store.loadModels()
  store.loadStaffList()
})

// ── Local conversation helpers (delegate to store) ──
async function loadConversations() {
  await store.loadConversations()
}
function newConversation() {
  store.clearMessages()
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
  await store.loadConversation(id)
  scrollToBottom()
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || store.streaming) return

  store.addMessage({ role: 'user', type: 'text', content: text })
  inputText.value = ''
  await scrollToBottom()

  store.startStreaming()
  streamText.value = ''
  streamTools.value = []

  // Build message history (same as panel)
  const apiMessages = store.messages
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
        model: store.model,
        messages: apiMessages,
        stream: true,
        agent_id: store.activeStaffId || undefined,
      }),
    })

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

    store.addMessage({
      role: 'assistant',
      type: 'text',
      content: streamText.value || '（已处理）',
    })
    for (const t of streamTools.value) {
      store.addMessage({
        role: 'system',
        type: 'tool_result',
        content: t.result || '',
        toolCall: { id: t.id, tool: t.name, status: t.status },
      })
    }
  } catch (e) {
    store.addMessage({
      role: 'assistant',
      type: 'text',
      content: `⚠️ 请求失败: ${getErrorMessage(e)}`,
    })
  } finally {
    store.stopStreaming()
    store.saveConversation(null).catch(() => {})
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

onMounted(() => {
  if (store.messages.length === 0) {
    store.addMessage({
      role: 'assistant',
      type: 'text',
      content: '你好！我是超级员工，可以用一句话指挥我完成任何营销任务。试试输入"搜索抖音上关于AI培训的视频"吧。',
    })
  }
})
</script>

<style scoped>
.super-agent { height: calc(100vh - 120px); }
.agent-layout { display: flex; height: 100%; gap: 1px; background: var(--border-light); }

.agent-sidebar { width: 240px; background: var(--bg-page); display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-light); }
.sidebar-title { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.conversation-list { flex: 1; overflow-y: auto; padding: 8px; }
.conversation-item { padding: 10px 12px; border-radius: var(--radius-sm); cursor: pointer; margin-bottom: 4px; }
.conversation-item:hover { background: var(--bg-hover); }
.conversation-item.active { background: var(--accent-soft); }
.conv-title { font-size: 13px; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conv-time { font-size: 11px; color: var(--text-tertiary); margin-top: 2px; }

.agent-main { flex: 1; display: flex; flex-direction: column; background: var(--bg-main); min-width: 0; }
.messages-area { flex: 1; overflow-y: auto; padding: 24px; }
.message { display: flex; gap: 12px; margin-bottom: 20px; }
.msg-avatar { font-size: 24px; flex-shrink: 0; }
.msg-content { flex: 1; min-width: 0; }
.msg-text { font-size: 14px; line-height: 1.7; color: var(--text-primary); word-break: break-word; }
.message.user .msg-text { color: var(--text-primary); }
.message.assistant .msg-text { color: var(--text-secondary); }
.streaming-text { color: var(--accent); }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

.tool-calls { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.tool-call-item { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.tool-result { color: var(--text-tertiary); }

.input-area { border-top: 1px solid var(--border-light); padding: 12px 24px; }
.quick-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.quick-tag { cursor: pointer; }
.input-row { display: flex; gap: 8px; align-items: flex-end; }
</style>
