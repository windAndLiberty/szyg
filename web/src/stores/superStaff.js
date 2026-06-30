import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useSuperStaffStore = defineStore('superStaff', () => {
  // Phase 1 已有
  const isOpen = ref(false)
  const isFullscreen = ref(false)

  // SSE 状态
  const messages = ref([])
  const isThinking = ref(false)
  const currentToolCall = ref(null)
  const activeTasks = ref([])
  const sessionId = ref('')
  const connectionStatus = ref('disconnected') // 'connected' | 'disconnected' | 'reconnecting'
  const model = ref('doubao-seed-2-0-pro-260215')
  const streaming = ref(false)
  const abortController = ref(null)
  const activeStaffId = ref('')  // 当前选择的员工ID，空=通用模式
  const staffList = ref([])       // 从 /api/staff/list 加载的员工列表
  const conversations = ref([])  // 会话历史列表
  const activeConvId = ref('')   // 当前会话ID

  // 方法
  function toggle() { isOpen.value = !isOpen.value }
  function open() { isOpen.value = true }
  function close() { isOpen.value = false }
  function setFullscreen(v) { isFullscreen.value = v }

  function addMessage(msg) {
    const id = msg.id || Date.now() + Math.random().toString(36).slice(2, 8)
    messages.value.push({ id, timestamp: Date.now(), ...msg })
    return id
  }

  function updateMessage(id, updates) {
    const idx = messages.value.findIndex(m => m.id === id)
    if (idx !== -1) {
      messages.value[idx] = { ...messages.value[idx], ...updates }
    }
  }

  function clearMessages() {
    messages.value = []
    activeTasks.value = []
    sessionId.value = ''
  }

  function startStreaming() {
    streaming.value = true
    isThinking.value = true
    connectionStatus.value = 'connected'
    if (!sessionId.value) {
      sessionId.value = 'sess_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
    }
  }

  function stopStreaming() {
    streaming.value = false
    isThinking.value = false
    currentToolCall.value = null
    abortController.value = null
    connectionStatus.value = 'disconnected'
    activeTasks.value = activeTasks.value.filter(t => t.status === 'running')
  }

  function setAbortController(controller) {
    abortController.value = controller
  }

  function cancel() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    streaming.value = false
    isThinking.value = false
    connectionStatus.value = 'disconnected'
  }

  // ── Connection heartbeat ──
  let _heartbeatTimer = null
  let _heartbeatFails = 0

  function startHeartbeat() {
    stopHeartbeat()
    _heartbeatFails = 0
    _heartbeatTimer = setInterval(async () => {
      try {
        await axios.get('/api/health', { timeout: 5000 })
        _heartbeatFails = 0
        if (connectionStatus.value === 'disconnected' && !streaming.value) {
          connectionStatus.value = 'connected'
        }
      } catch {
        _heartbeatFails++
        if (_heartbeatFails >= 3) {
          connectionStatus.value = 'disconnected'
        } else if (_heartbeatFails >= 1) {
          connectionStatus.value = 'reconnecting'
        }
      }
    }, 30000)
  }

  function stopHeartbeat() {
    if (_heartbeatTimer) {
      clearInterval(_heartbeatTimer)
      _heartbeatTimer = null
    }
  }

  // ── activeTasks management (called by SSE event handlers) ──
  function addActiveTask(task) {
    activeTasks.value.push({ id: task.id, name: task.tool || task.name, status: 'running', startTime: Date.now(), ...task })
  }
  function updateActiveTask(id, updates) {
    const idx = activeTasks.value.findIndex(t => t.id === id)
    if (idx !== -1) Object.assign(activeTasks.value[idx], updates)
  }
  function setConnectionStatus(status) {
    connectionStatus.value = status
  }

  // External prompt submission (from Dashboard quick-input, etc.)
  const pendingPrompt = ref('')
  function submitPrompt(text) {
    pendingPrompt.value = text
    isOpen.value = true
  }
  function consumePendingPrompt() {
    const p = pendingPrompt.value
    pendingPrompt.value = ''
    return p
  }

  // 模型列表（从 API 加载，失败时使用默认列表）
  const DEFAULT_MODELS = [
    'doubao-seed-2-0-pro-260215',
    'doubao-seed-2-0-lite-260428',
    'doubao-seed-2-0-mini-260428',
    'doubao-1-5-pro-32k-250115',
    'deepseek-v4-flash-260425',
  ]
  const models = ref([...DEFAULT_MODELS])
  const modelsLoaded = ref(false)

  async function loadModels() {
    if (modelsLoaded.value) return
    try {
      const { data } = await axios.get('/api/models')
      const list = Array.isArray(data) ? data : (data?.models || data?.data || [])
      if (list.length > 0) {
        models.value = list.map(m => typeof m === 'string' ? m : (m.id || m.name || m.model))
        // 自动选择第一个可用模型
        if (!models.value.includes(model.value)) {
          model.value = models.value[0]
        }
      }
    } catch {
      // 保持默认列表
    }
    modelsLoaded.value = true
  }

  // 员工列表（从 /api/staff/list 加载）
  const staffLoaded = ref(false)
  async function loadStaffList() {
    if (staffLoaded.value) return
    try {
      const { data } = await axios.get('/api/staff/list')
      staffList.value = data?.staff || []
    } catch {
      staffList.value = []
    }
    staffLoaded.value = true
  }

  // ── 会话持久化 ──
  async function loadConversations() {
    try {
      const { data } = await axios.get('/api/conversations')
      conversations.value = data?.conversations || []
    } catch {
      conversations.value = []
    }
  }

  async function saveConversation(title) {
    // Build message list from current conversation
    const msgList = messages.value
      .filter(m => m.role !== 'system' || m.type === 'thinking')
      .map(m => ({ role: m.role, content: m.content, type: m.type || 'text', timestamp: m.timestamp }))

    const titleText = title || (msgList.find(m => m.role === 'user')?.content?.slice(0, 40) || '新对话')

    if (activeConvId.value) {
      // Update existing
      try {
        await axios.put(`/api/conversations/${activeConvId.value}`, {
          title: titleText,
          messages: msgList,
        })
      } catch {
        // If update fails (e.g. deleted), create new
        activeConvId.value = ''
      }
    }

    if (!activeConvId.value) {
      // Create new
      try {
        const { data } = await axios.post('/api/conversations', {
          title: titleText,
          messages: msgList,
          agent_id: activeStaffId.value,
          model: model.value,
        })
        activeConvId.value = data.id
      } catch {
        // Non-critical — conversation just won't persist
      }
    }

    // Reload list
    await loadConversations()
  }

  async function loadConversation(convId) {
    try {
      const { data } = await axios.get(`/api/conversations/${convId}`)
      messages.value = (data.messages || []).map(m => ({
        id: Date.now() + Math.random().toString(36).slice(2, 8),
        role: m.role,
        type: m.type || 'text',
        content: m.content,
        timestamp: m.timestamp || Date.now(),
      }))
      activeConvId.value = convId
      return true
    } catch {
      return false
    }
  }

  async function deleteConversation(convId) {
    try {
      await axios.delete(`/api/conversations/${convId}`)
      if (activeConvId.value === convId) {
        activeConvId.value = ''
        messages.value = []
      }
      await loadConversations()
    } catch {
      // ignore
    }
  }

  // 快捷指令
  const quickPrompts = ref([
    '帮我检查各平台账号状态',
    '生成今日小红书+抖音内容并发布',
    '查看最近截流获取的线索',
    '创建一个定时发布任务',
  ])

  return {
    isOpen, isFullscreen, messages, isThinking, currentToolCall,
    activeTasks, sessionId, connectionStatus, model, streaming,
    abortController, models, quickPrompts, pendingPrompt,
    activeStaffId, staffList, conversations, activeConvId,
    toggle, open, close, setFullscreen, addMessage, updateMessage, clearMessages,
    startStreaming, stopStreaming, setAbortController, cancel,
    submitPrompt, consumePendingPrompt, loadModels, loadStaffList,
    addActiveTask, updateActiveTask, setConnectionStatus,
    startHeartbeat, stopHeartbeat,
    loadConversations, saveConversation, loadConversation, deleteConversation,
  }
})
