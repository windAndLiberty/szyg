<template>
  <div class="super-agent" @click="closeContextMenu">
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
        </div>
        <div v-else class="conv-empty">
          <div class="empty-icon">💬</div>
          <div class="empty-text">暂无对话记录</div>
        </div>
      </div>

      <!-- Right: Chat Area -->
      <div class="chat-area">
        <!-- Messages Area -->
        <div class="messages-area" ref="messagesRef" :class="{ 'welcome-mode': state.messages.length === 0 }">
          <!-- Welcome Empty State -->
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

            <!-- 精选案例 -->
            <div class="case-section">
              <div class="case-header">
                <span class="case-title">智能员工 精选案例</span>
              </div>
              <div class="case-cards" v-loading="caseCardsLoading">
                <div
                  v-for="card in caseCards"
                  :key="card.video_url"
                  class="case-card"
                  @click="sendQuickCard(card.title)"
                >
                  <div class="case-card-image">
                    <img v-if="card.cover_url" :src="card.cover_url" :alt="card.title" />
                  </div>
                  <div class="case-card-title">{{ card.title }}</div>
                </div>
              </div>
              <div v-if="!caseCardsLoading && caseCards.length === 0" class="case-empty">
                暂无推荐案例
              </div>
            </div>
          </div>

          <!-- Messages -->
          <div v-for="msg in state.messages" :key="msg.id" class="message" :class="msg.role">
            <div class="msg-avatar">{{ msg.role === 'user' ? getUserInitial() : '' }}<img v-if="msg.role !== 'user'" :src="logo1Url" alt="AI" class="avatar-logo" /></div>
            <div class="msg-content">
              <!-- 视频进度卡片 -->
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
              <!-- 视频播放卡片 -->
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
              <!-- 图片卡片 -->
              <div v-else-if="msg.type === 'image'" class="image-card" @click="openLightbox(msg.image_url)">
                <img :src="msg.image_url" :alt="msg.prompt" loading="lazy" />
                <div class="image-card-overlay">
                  <span>{{ msg.prompt }}</span>
                </div>
              </div>
              <!-- 文本 -->
              <div v-else class="msg-text" v-html="renderMarkdown(msg.content)" @click="handleMsgClick"></div>
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
            <div class="msg-avatar"><img :src="logo1Url" alt="AI" class="avatar-logo" /></div>
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
        <div class="input-area" v-if="state.messages.length > 0">
          <div class="input-row">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="3"
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

    <!-- Lightbox -->
    <el-image-viewer
      v-if="lightbox.show"
      :url-list="[lightbox.url]"
      @close="lightbox.show = false"
    />

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
        <el-icon><Top v-if="!ctxMenu.conv?.pinned" /><Bottom v-else /></el-icon>
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
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, reactive } from 'vue'
import { Plus, Promotion, Loading, ZoomIn, FullScreen, Download, Close, Edit, Top, Bottom, Delete } from '@element-plus/icons-vue'
import logo1Url from '../assets/logo1.png'
import { ElMessageBox } from 'element-plus'
import axios from 'axios'
import { getErrorMessage, autoLogin } from '../api.js'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

const inputText = ref('')
const streamText = ref('')
const streamTools = ref([])
const streamImages = ref([])
const streamVideoTasks = ref([])
const streamVideos = ref([])
const messagesRef = ref(null)
const videoRefs = ref({})
const videoModalRef = ref(null)
const caseCards = ref([])
const caseCardsLoading = ref(false)

const lightbox = reactive({
  show: false,
  url: '',
})

const videoModal = reactive({
  show: false,
  url: '',
})

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
  nextTick(() => {
    const menuEl = document.querySelector('.ctx-menu')
    const menuW = menuEl?.offsetWidth || 140
    const menuH = menuEl?.offsetHeight || 160
    ctxMenu.x = Math.min(event.clientX, window.innerWidth - menuW - 8)
    ctxMenu.y = Math.min(event.clientY, window.innerHeight - menuH - 8)
  })
}

function closeContextMenu() {
  ctxMenu.show = false
}

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
    await loadConversations()
  } catch {}
}

async function togglePin(conv) {
  closeContextMenu()
  const newPinned = !conv.pinned
  await axios.put(`/api/conversations/${conv.id}`, { pinned: newPinned })
  conv.pinned = newPinned
  await loadConversations()
}

function exportConversation(conv) {
  closeContextMenu()
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
      const role = m.role === 'user' ? '用户' : m.role === 'assistant' ? '助手' : '系统'
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
  }).catch(e => {
    console.error('导出对话失败:', e)
  })
}

async function deleteConversation(conv) {
  closeContextMenu()
  try {
    await ElMessageBox.confirm(
      `确定删除对话「${conv.title}」吗？此操作不可撤销。`,
      '删除对话',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await axios.delete(`/api/conversations/${conv.id}`)
    if (state.activeConvId === conv.id) {
      clearMessages()
    }
    await loadConversations()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除对话失败:', e)
    }
  }
}

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

function openLightbox(url) {
  lightbox.url = url
  lightbox.show = true
}

function handleMsgClick(e) {
  if (e.target.tagName === 'IMG') {
    openLightbox(e.target.src)
  }
}

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

async function loadCaseCards() {
  if (state.messages.length > 0) return  // 仅欢迎页面加载
  caseCardsLoading.value = true
  try {
    // 获取近期对话标题
    const titles = state.conversations
      .slice(0, 10)
      .map(c => c.title)
      .filter(Boolean)

    const { data } = await axios.post('/api/hermes/case-cards', {
      recent_titles: titles,
      limit: 3,
    })
    caseCards.value = data.cards || []
  } catch (e) {
    console.error('加载精选案例失败:', e)
    caseCards.value = []
  } finally {
    caseCardsLoading.value = false
  }
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
        timestamp: m.timestamp || Date.now() / 1000,
        image_url: m.image_url,
        prompt: m.prompt,
        video_url: m.video_url,
        task_id: m.task_id,
        status: m.status,
        progress: m.progress,
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

onMounted(async () => {
  await loadConversations()
  await loadCaseCards()
})

function newConversation() {
  clearMessages()
  loadCaseCards()
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
            case 'image':
              streamImages.value.push({ url: event.url, prompt: event.prompt })
              break
            case 'video_task':
              streamVideoTasks.value.push({
                task_id: event.task_id,
                prompt: event.prompt,
                status: event.status,
                progress: 0,
              })
              break
            case 'video_status':
              const task = streamVideoTasks.value.find(t => t.task_id === event.task_id)
              if (task) {
                task.status = event.status
                task.progress = event.progress
              }
              break
            case 'video':
              streamVideoTasks.value = streamVideoTasks.value.filter(
                t => t.task_id !== event.task_id
              )
              streamVideos.value.push({
                task_id: event.task_id,
                url: event.url,
                prompt: event.prompt,
              })
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
    // 将图片作为独立消息插入对话流
    for (const img of streamImages.value) {
      addMessage({
        role: 'assistant',
        type: 'image',
        image_url: img.url,
        prompt: img.prompt,
      })
    }
    // 插入或更新视频进度卡片
    for (const vt of streamVideoTasks.value) {
      const existing = state.messages.find(
        m => m.type === 'video_pending' && m.task_id === vt.task_id
      )
      if (existing) {
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
    streamImages.value = []
    streamVideoTasks.value = []
    streamVideos.value = []
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

.messages-area.welcome-mode {
  flex: 0 1 auto;
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
.welcome-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 24px 32px;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
  gap: 40px;
}

.brand-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 48px;
}

.brand-logo {
  width: 104px;
  height: 104px;
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.14);
}

.brand-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.brand-title {
  font-size: 40px;
  font-weight: 700;
  letter-spacing: 6px;
  color: var(--text-primary);
  margin: 0;
}

.welcome-input-box {
  position: relative;
  width: 100%;
  max-width: 640px;
  border: 1px solid var(--border-light);
  border-radius: 28px;
  background: var(--bg-body);
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.08);
  padding: 6px 6px 6px 24px;
  box-sizing: border-box;
}

.welcome-input-box :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  background: transparent;
  resize: none;
  font-size: 16px;
  padding: 12px 56px 12px 4px;
}

.welcome-send-btn {
  position: absolute;
  right: 10px;
  bottom: 10px;
  width: 40px;
  height: 40px;
}

.case-section {
  width: 100%;
  max-width: 640px;
  margin-top: 56px;
}

.case-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.case-title {
  font-size: 15px;
  color: var(--text-secondary);
}

.case-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
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

@media (max-width: 768px) {
  .case-cards {
    grid-template-columns: 1fr;
  }
}

.case-empty {
  text-align: center;
  font-size: 15px;
  color: var(--text-tertiary);
  padding: 28px 0;
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
  overflow: hidden;
}

.agent-icon-large {
  width: 160px;
  height: 160px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 20px;
  margin-bottom: 16px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
}

.agent-icon-large img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.agent-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
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
  overflow: hidden;
}

.avatar-logo {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 999px;
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

.image-card {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  max-width: 300px;
}

.image-card img {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 8px;
}

.image-card-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.7));
  padding: 8px 12px;
  color: white;
  font-size: 12px;
  opacity: 0;
  transition: opacity 0.2s;
}

.image-card:hover .image-card-overlay {
  opacity: 1;
}

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

.conv-item.pinned {
  background: var(--fill-light, #f5f7fa);
}

.conv-item.pinned .pin-icon {
  font-size: 12px;
  margin-right: 4px;
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
