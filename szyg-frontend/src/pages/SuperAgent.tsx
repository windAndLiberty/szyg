import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Monitor, Send } from 'lucide-react'
import type { ChatMessage, Conversation, CaseCard } from '@/types'
import {
  autoLogin,
  apiGet,
  apiPost,
  apiPut,
  apiDel,
  streamHermesChat,
  generateImage,
  createVideo,
  pollVideoTask,
  getErrorMessage,
  toUserFacingMessage,
  getCurrentUser,
  fetchCloudSession,
  type HermesEvent,
} from '@/lib/api'
import ConversationPanel from '@/components/superagent/ConversationPanel'
import WelcomeState from '@/components/superagent/WelcomeState'
import ChatMessageView from '@/components/superagent/ChatMessageView'
import EmployeeWorkView, {
  type EmployeeApproval,
  type EmployeeFrameMeta,
  type EmployeePointer,
  type EmployeeWorkEvent,
  type EmployeeWorkPhase,
} from '@/components/superagent/EmployeeWorkView'

const DEFAULT_MODEL = 'doubao-seed-2-0-pro-260215'

type HermesRuntimeStatus = {
  memory?: { enabled?: boolean }
  skills?: { count?: number }
}

// 生成意图识别：后端 hermes/chat 不产出 image/video 事件，
// 生成走独立 REST 端点 (/api/image/generate、/api/video/create + 轮询)。
const GEN_KEYWORDS = ['生成', '画', '视频', '图片', '制作', '创建', '渲染', '动画', '海报', 'image', 'video', 'create', 'generate', 'render']
const VIDEO_KEYWORDS = ['视频', 'video', '动画', '运镜', '动态']
const IMAGE_KEYWORDS = ['图片', 'image', '画', '海报', '插图', '插画', '图']

function isGenerationRequest(text: string): boolean {
  const t = text.toLowerCase()
  return GEN_KEYWORDS.some((k) => t.includes(k.toLowerCase()))
}
function deriveGenKind(text: string): 'video' | 'image' {
  const t = text.toLowerCase()
  if (VIDEO_KEYWORDS.some((k) => t.includes(k.toLowerCase()))) return 'video'
  if (IMAGE_KEYWORDS.some((k) => t.includes(k.toLowerCase()))) return 'image'
  return 'video'
}
function extractPrompt(text: string): string {
  return text.replace(/^(帮我|请|麻烦)?(生成|画|制作|创建|渲染|做)(一段|一个|一张|个|张)?/i, '').trim() || text
}

let msgSeq = 0
const nextId = (prefix: string) => `${prefix}-${Date.now()}-${msgSeq++}`

const HIDDEN_WORK_TOOLS = new Set(['tool_search', 'tool_describe', 'wait'])

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {}
}

function desktopAppLabel(value: unknown) {
  const raw = String(value || '').trim()
  const aliases: Record<string, string> = {
    calculator: '计算器',
    calc: '计算器',
    notepad: '记事本',
    edge: '浏览器',
    chrome: '浏览器',
    browser: '浏览器',
  }
  return aliases[raw.toLowerCase()] || raw.replace(/\.exe$/i, '') || '应用'
}

function workToolPresentation(tool: string, rawArgs: unknown): Omit<EmployeeWorkEvent, 'id' | 'state'> | null {
  if (HIDDEN_WORK_TOOLS.has(tool)) return null
  const args = objectValue(rawArgs)
  if (tool === 'szyg_open_desktop_app') {
    const app = desktopAppLabel(args.app || args.name || args.application)
    return { type: 'application', title: `打开${app}`, detail: '正在启动并确认窗口', technicalName: tool }
  }
  if (tool === 'computer_use') {
    const action = String(args.action || '').toLowerCase()
    const app = desktopAppLabel(args.app || args.application)
    const mapping: Record<string, string> = {
      capture: '确认当前画面',
      click: '操作当前页面',
      double_click: '操作当前页面',
      type: '填写内容',
      type_text: '填写内容',
      set_value: '填写内容',
      key: '使用键盘完成操作',
      scroll: '浏览当前页面',
      drag: '调整页面内容',
      focus_app: `切换到${app}`,
      open: `打开${app}`,
    }
    if (action === 'list_apps' || action === 'list_windows') return null
    return { type: 'computer', title: mapping[action] || '操作当前应用', technicalName: `${tool}:${action || 'action'}` }
  }
  if (tool === 'terminal') return { type: 'system', title: '准备运行环境', technicalName: tool }
  if (/publish|upload/i.test(tool)) return { type: 'business', title: '提交发布任务', technicalName: tool }
  if (/search|intelligence|browser/i.test(tool)) return { type: 'business', title: '查找相关信息', technicalName: tool }
  if (/knowledge|memory|document|file/i.test(tool)) return { type: 'business', title: '整理所需资料', technicalName: tool }
  if (/workflow|scheduler|task/i.test(tool)) return { type: 'business', title: '执行工作流程', technicalName: tool }
  if (/lead|customer|comment|acquisition/i.test(tool)) return { type: 'business', title: '处理客户任务', technicalName: tool }
  if (/image|video|audio|tts|content|copy/i.test(tool)) return { type: 'business', title: '生成内容', technicalName: tool }
  return { type: 'business', title: '执行任务步骤', technicalName: tool }
}

function compactWorkResult(value: unknown) {
  return String(value || '')
    .replace(/^已完成(?:任务|操作)?[：:]?\s*/u, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export default function SuperAgent() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [caseCards, setCaseCards] = useState<CaseCard[]>([])
  const [caseCardsLoading, setCaseCardsLoading] = useState(false)
  const [historyCollapsed, setHistoryCollapsed] = useState(false)
  const [hermesRuntime, setHermesRuntime] = useState<HermesRuntimeStatus | null>(null)
  const [currentUserName, setCurrentUserName] = useState(() => getCurrentUser()?.username || '')
  const [workViewOpen, setWorkViewOpen] = useState(false)
  const [workTaskTitle, setWorkTaskTitle] = useState('')
  const [workResult, setWorkResult] = useState('')
  const [workStatus, setWorkStatus] = useState('')
  const [workPhase, setWorkPhase] = useState<EmployeeWorkPhase>('idle')
  const [workFrame, setWorkFrame] = useState('')
  const [workFrameMeta, setWorkFrameMeta] = useState<EmployeeFrameMeta>({})
  const [workPointer, setWorkPointer] = useState<EmployeePointer | null>(null)
  const [workLive, setWorkLive] = useState(false)
  const [workPreviewBlocked, setWorkPreviewBlocked] = useState(false)
  const [workEvents, setWorkEvents] = useState<EmployeeWorkEvent[]>([])
  const [workApproval, setWorkApproval] = useState<EmployeeApproval | null>(null)
  const [workPaused, setWorkPaused] = useState(false)
  const [workStartedAt, setWorkStartedAt] = useState<number | null>(null)
  const [workFinishedAt, setWorkFinishedAt] = useState<number | null>(null)
  const messagesRef = useRef<HTMLDivElement>(null)
  const messagesStateRef = useRef<ChatMessage[]>([])
  const streamMsgIdRef = useRef<string | null>(null)
  const streamBufRef = useRef<string>('')
  const pendingSessionIdRef = useRef(`szyg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`)
  const activeRuntimeSessionRef = useRef(pendingSessionIdRef.current)
  const workFrameMetaRef = useRef<EmployeeFrameMeta>({})

  useEffect(() => {
    workFrameMetaRef.current = workFrameMeta
  }, [workFrameMeta])

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    })
  }, [])

  useEffect(() => {
    messagesStateRef.current = messages
    scrollToBottom()
  }, [messages, scrollToBottom])

  const addMessage = useCallback((msg: Omit<ChatMessage, 'id' | 'timestamp'> & { id?: string }) => {
    setMessages((prev) => [
      ...prev,
      { id: msg.id ?? nextId('msg'), timestamp: Date.now() / 1000, ...msg },
    ])
  }, [])

  const loadConversations = useCallback(async () => {
    try {
      const data = await apiGet<{ conversations: Conversation[] }>('/api/conversations?limit=50')
      setConversations(data.conversations || [])
    } catch {
      /* ignore */
    }
  }, [])

  const loadCaseCards = useCallback(async () => {
    setCaseCardsLoading(true)
    try {
      const data = await apiPost<{ cards: CaseCard[] }>('/api/hermes/case-cards', {
        limit: 3,
      })
      setCaseCards((data.cards || []).slice(0, 3))
    } catch {
      setCaseCards([])
    } finally {
      setCaseCardsLoading(false)
    }
  }, [])

  useEffect(() => {
    ;(async () => {
      await autoLogin()
      try {
        const session = await fetchCloudSession()
        if (session.authenticated && session.user?.display_name?.trim()) {
          setCurrentUserName(session.user.display_name.trim())
        }
      } catch {
        /* Use the local account name when the cloud session is unavailable. */
      }
      await loadConversations()
    })()
  }, [loadConversations])

  useEffect(() => {
    let active = true
    apiGet<HermesRuntimeStatus>('/api/skills/runtime')
      .then((status) => { if (active) setHermesRuntime(status) })
      .catch(() => { if (active) setHermesRuntime(null) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (messages.length === 0) loadCaseCards()
  }, [messages.length, loadCaseCards])

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ collapsed?: boolean }>).detail
      setHistoryCollapsed((current) => detail?.collapsed ?? !current)
    }
    window.addEventListener('szyg:toggle-super-agent-history', handler)
    return () => window.removeEventListener('szyg:toggle-super-agent-history', handler)
  }, [])

  const newConversation = useCallback(() => {
    setActiveConvId(null)
    pendingSessionIdRef.current = `szyg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    setMessages([])
    setWorkTaskTitle('')
    setWorkResult('')
    setWorkStatus('')
    setWorkPhase('idle')
    setWorkEvents([])
    setWorkFrame('')
    setWorkFrameMeta({})
    setWorkPointer(null)
    setWorkLive(false)
    setWorkPreviewBlocked(false)
    setWorkApproval(null)
    setWorkPaused(false)
    setWorkStartedAt(null)
    setWorkFinishedAt(null)
    loadCaseCards()
  }, [loadCaseCards])

  const selectConversation = useCallback(
    async (id: string) => {
      setActiveConvId(id)
      try {
        const data = await apiGet<{ messages: ChatMessage[] } & { id: string }>(`/api/conversations/${id}`)
        setMessages(
          (data.messages || []).map((m, idx) => ({
            ...m,
            id: m.id || `hist-${id}-${idx}`,
            timestamp: m.timestamp || Date.now() / 1000,
          })),
        )
        scrollToBottom()
      } catch {
        /* ignore */
      }
    },
    [scrollToBottom],
  )

  const saveConversation = useCallback(async () => {
    try {
      const currentMessages = messagesStateRef.current
      const firstUser = currentMessages.find((m) => m.role === 'user' && m.type === 'text')
      const payload = {
        title: firstUser ? firstUser.content.slice(0, 50) : '新对话',
        messages: currentMessages.map((m) => ({
          role: m.role,
          content: m.content,
          type: m.type,
          timestamp: m.timestamp,
          image_url: m.image_url,
          prompt: m.prompt,
          video_url: m.video_url,
          task_id: m.task_id,
          status: m.status,
          progress: m.progress,
        })),
        model: DEFAULT_MODEL,
      }
      if (activeConvId) {
        await apiPut(`/api/conversations/${activeConvId}`, payload)
      } else if (currentMessages.length > 0) {
        const data = await apiPost<{ id: string }>('/api/conversations', payload)
        if (data?.id) setActiveConvId(data.id)
      }
    } catch {
      /* ignore */
    }
  }, [activeConvId])

  const handlePin = useCallback(
    async (conv: Conversation) => {
      const newPinned = !conv.pinned
      setConversations((prev) => prev.map((c) => (c.id === conv.id ? { ...c, pinned: newPinned } : c)))
      try {
        await apiPut(`/api/conversations/${conv.id}`, { pinned: newPinned })
        await loadConversations()
      } catch {
        /* ignore */
      }
    },
    [loadConversations],
  )

  const handleDelete = useCallback(
    async (conv: Conversation) => {
      setConversations((prev) => prev.filter((c) => c.id !== conv.id))
      if (activeConvId === conv.id) {
        setActiveConvId(null)
        setMessages([])
      }
      try {
        await apiDel(`/api/conversations/${conv.id}`)
        await loadConversations()
      } catch {
        /* ignore */
      }
    },
    [activeConvId, loadConversations],
  )

  const handleArchive = useCallback(
    async (conv: Conversation) => {
      setConversations((prev) => prev.filter((item) => item.id !== conv.id))
      if (activeConvId === conv.id) {
        setActiveConvId(null)
        setMessages([])
      }
      try {
        await apiPut(`/api/conversations/${conv.id}`, { archived: true, pinned: false })
        await loadConversations()
      } catch {
        await loadConversations()
      }
    },
    [activeConvId, loadConversations],
  )

  const handleRename = useCallback(
    async (conv: Conversation, title: string) => {
      setConversations((prev) => prev.map((c) => (c.id === conv.id ? { ...c, title } : c)))
      try {
        await apiPut(`/api/conversations/${conv.id}`, { title })
        await loadConversations()
      } catch {
        /* ignore */
      }
    },
    [loadConversations],
  )

  // === SEND MESSAGE + SSE HANDLING ===
  const sendCaseCard = useCallback(
    (card: CaseCard) => {
      setInputText(card.title)
      sendMessage(card.title)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [messages, activeConvId],
  )

  const ensureStreamMsg = useCallback(() => {
    let id = streamMsgIdRef.current
    if (!id) {
      id = nextId('msg')
      streamMsgIdRef.current = id
      setMessages((prev) => [
        ...prev,
        { id: id!, role: 'assistant', type: 'text', content: '', timestamp: Date.now() / 1000, isStreaming: true },
      ])
    }
    return id
  }, [])

  const appendText = useCallback((delta: string) => {
    streamBufRef.current += delta
    const id = streamMsgIdRef.current
    if (!id) return
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content: streamBufRef.current } : m)))
  }, [])

  const replaceStreamText = useCallback((content: string) => {
    streamBufRef.current = content
    const id = streamMsgIdRef.current
    if (!id) return
    setMessages((prev) => prev.map((message) => message.id === id ? { ...message, content } : message))
  }, [])

  const upsertWorkEvent = useCallback((event: Omit<EmployeeWorkEvent, 'id'> & { id?: string }) => {
    setWorkEvents((current) => {
      const eventId = event.id || nextId('work')
      let index = current.findIndex((item) => item.id === eventId)
      if (index < 0) {
        index = current.findIndex((item) => item.type === event.type && item.title === event.title)
      }
      if (index >= 0) {
        const updated = [...current]
        updated[index] = { ...updated[index], ...event, id: updated[index].id }
        return updated.slice(-16)
      }
      return [...current, { ...event, id: eventId }].slice(-16)
    })
  }, [])

  const handleEvent = useCallback(
    (ev: HermesEvent) => {
      switch (ev.type) {
        case 'text':
          ensureStreamMsg()
          appendText(ev.content || '')
          break
        case 'tool_call': {
          const name = ev.tool || 'unknown'
          let argsSummary = ''
          try {
            argsSummary = typeof ev.args === 'string' ? ev.args : JSON.stringify(ev.args || {})
          } catch {
            argsSummary = String(ev.args ?? '')
          }
          addMessage({
            role: 'system',
            type: 'tool_result',
            content: argsSummary.slice(0, 200),
            toolCall: { id: ev.id || nextId('tool'), tool: name, status: 'running' },
          })
          break
        }
        case 'tool.started': {
          const name = String(ev.tool || '正在执行')
          const presentation = workToolPresentation(name, ev.args)
          if (!presentation) break
          upsertWorkEvent({ id: String(ev.id || nextId('work')), ...presentation, state: 'running' })
          setWorkStatus(presentation.title)
          if (name === 'computer_use' || name === 'szyg_open_desktop_app') {
            setHistoryCollapsed(true)
            setWorkViewOpen(true)
          }
          break
        }
        case 'tool_result': {
          let res = ev.result || ''
          let status: 'success' | 'error' = 'success'
          try {
            const r = JSON.parse(res)
            if (r && r.error) {
              status = 'error'
              res = toUserFacingMessage(r.error)
            }
          } catch {
            /* keep raw */
          }
          setMessages((prev) => {
            const idx = [...prev].reverse().findIndex((m) => m.type === 'tool_result' && m.toolCall?.status === 'running')
            if (idx === -1) return prev
            const realIdx = prev.length - 1 - idx
            const upd = [...prev]
            upd[realIdx] = {
              ...upd[realIdx],
              content: (typeof res === 'string' ? res : JSON.stringify(res)).slice(0, 200),
              toolCall: { ...upd[realIdx].toolCall!, status },
            }
            return upd
          })
          break
        }
        case 'tool.completed': {
          const name = String(ev.tool || '操作')
          const presentation = workToolPresentation(name, ev.args)
          if (!presentation) break
          const rawResult = String(ev.result || '')
          const failed = /(?:"error"\s*:|traceback|exception|failed)/i.test(rawResult)
          upsertWorkEvent({
            id: String(ev.id || nextId('work')),
            ...presentation,
            detail: failed ? toUserFacingMessage(rawResult, '这一步未能完成') : undefined,
            state: failed ? 'error' : 'success',
          })
          if (failed) setWorkStatus('这一步需要处理')
          break
        }
        case 'tool.progress': {
          const progress = String(ev.content || '').trim()
          if (progress && progress.length <= 60 && !/(tool|mcp|runtime|schema|callback)/i.test(progress)) {
            setWorkStatus(toUserFacingMessage(progress, '正在继续任务'))
          }
          break
        }
        case 'computer.frame':
          if (typeof ev.image_url === 'string' && ev.image_url) setWorkFrame(ev.image_url)
          setWorkFrameMeta({
            appName: String(ev.app_name || ''),
            windowTitle: String(ev.window_title || ev.content || ''),
            sourceWidth: Number(ev.source_width || 0) || undefined,
            sourceHeight: Number(ev.source_height || 0) || undefined,
          })
          setWorkPreviewBlocked(false)
          setWorkViewOpen(true)
          break
        case 'computer.stream.started':
          setWorkLive(true)
          setWorkPreviewBlocked(false)
          setHistoryCollapsed(true)
          setWorkViewOpen(true)
          break
        case 'computer.stream.blocked':
          setWorkLive(false)
          setWorkPreviewBlocked(true)
          setWorkViewOpen(true)
          break
        case 'computer.stream.stopped':
          setWorkLive(false)
          break
        case 'computer.action': {
          const args = objectValue(ev.args)
          const x = Number(args.x)
          const y = Number(args.y)
          const frameMeta = workFrameMetaRef.current
          if (Number.isFinite(x) && Number.isFinite(y) && frameMeta.sourceWidth && frameMeta.sourceHeight) {
            setWorkPointer({
              id: String(ev.id || nextId('pointer')),
              xPercent: Math.max(0, Math.min(100, x / frameMeta.sourceWidth * 100)),
              yPercent: Math.max(0, Math.min(100, y / frameMeta.sourceHeight * 100)),
            })
          }
          setWorkViewOpen(true)
          break
        }
        case 'approval.required':
          setWorkApproval({
            id: String(ev.approval_id || ''),
            title: String(ev.content || '需要你的确认'),
            summary: String(ev.summary || ''),
          })
          setWorkViewOpen(true)
          setWorkPhase('waiting')
          setWorkStatus('等待你的确认')
          break
        case 'run.started':
          ensureStreamMsg()
          setStatusText('正在理解任务')
          setWorkPaused(false)
          setWorkPhase('running')
          setWorkStartedAt((value) => value || Date.now())
          setWorkFinishedAt(null)
          setWorkStatus('正在理解任务')
          break
        case 'run.paused':
          setWorkLive(false)
          setWorkPaused(true)
          setWorkPhase('paused')
          setWorkStatus(String(ev.content || '已暂停'))
          break
        case 'run.completed':
          ensureStreamMsg()
          if (!streamBufRef.current && ev.content) appendText(String(ev.content))
          setWorkEvents((current) => current.map((item) => item.state === 'running' ? { ...item, state: 'success', detail: undefined } : item))
          setWorkPaused(false)
          setWorkLive(false)
          setWorkPhase('completed')
          setWorkResult(compactWorkResult(ev.content || streamBufRef.current))
          setWorkFinishedAt(Date.now())
          setWorkStatus('任务已完成')
          break
        case 'run.failed':
          ensureStreamMsg()
          replaceStreamText(toUserFacingMessage(ev.content, '当前操作未完成'))
          setWorkEvents((current) => current.map((item) => item.state === 'running' ? { ...item, state: 'error', detail: '任务在这一步停止' } : item))
          setWorkPhase(String(ev.code || '') === 'cancelled' ? 'cancelled' : 'failed')
          setWorkFinishedAt(Date.now())
          setWorkStatus(toUserFacingMessage(ev.content, '当前操作未完成'))
          setWorkLive(false)
          break
        case 'error':
          ensureStreamMsg()
          appendText('\n⚠️ ' + toUserFacingMessage(ev.content, '当前操作未完成，请稍后重试'))
          break
        case 'status':
          setStatusText(toUserFacingMessage(ev.content, '正在处理'))
          break
        case 'status.changed':
          setStatusText(toUserFacingMessage(ev.content, '正在处理'))
          if (!/(tool|mcp|runtime|schema|callback)/i.test(String(ev.content || ''))) {
            setWorkStatus(toUserFacingMessage(ev.content, '正在处理'))
          }
          break
        default:
          break
      }
    },
    [addMessage, upsertWorkEvent, ensureStreamMsg, appendText, replaceStreamText],
  )

  // === 真实图片/视频生成 (REST) ===
  const runGeneration = useCallback(
    async (text: string) => {
      const kind = deriveGenKind(text)
      const prompt = extractPrompt(text)
      if (kind === 'image') {
        ensureStreamMsg()
        appendText(`正在生成图片：${prompt}`)
        try {
          const res = await generateImage(prompt)
          if (res.images && res.images.length > 0) {
            addMessage({ role: 'assistant', type: 'image', content: '', image_url: res.images[0], prompt })
          } else {
            appendText('\n⚠️ 图片生成未返回结果')
          }
        } catch (e) {
          appendText(`\n⚠️ 图片生成失败: ${getErrorMessage(e)}`)
        }
      } else {
        ensureStreamMsg()
        appendText(`正在提交视频生成任务：${prompt}`)
        let taskId = ''
        try {
          const res = await createVideo(prompt)
          taskId = res.task_id
          addMessage({
            role: 'assistant',
            type: 'video_pending',
            content: '',
            task_id: taskId,
            prompt,
            status: res.status || 'queued',
            progress: 0,
          })
        } catch (e) {
          appendText(`\n⚠️ 视频任务提交失败: ${getErrorMessage(e)}`)
          return
        }
        for (let i = 0; i < 120; i++) {
          await new Promise((r) => setTimeout(r, 4000))
          try {
            const t = await pollVideoTask(taskId)
            setMessages((prev) =>
              prev.map((m) =>
                m.type === 'video_pending' && m.task_id === taskId
                  ? { ...m, status: t.status, progress: t.progress ?? m.progress }
                  : m,
              ),
            )
            if (t.status === 'succeeded' || t.status === 'succeed') {
              if (t.video_url) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.type === 'video_pending' && m.task_id === taskId
                      ? { ...m, type: 'video', video_url: t.video_url }
                      : m,
                  ),
                )
              }
              break
            }
            if (t.status === 'failed' || t.error) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.type === 'video_pending' && m.task_id === taskId
                    ? { ...m, status: 'failed' }
                    : m,
                ),
              )
              appendText(`\n⚠️ 视频生成失败: ${t.error || t.status}`)
              break
            }
          } catch {
            /* single poll failure does not abort */
          }
        }
      }
    },
    [ensureStreamMsg, appendText, addMessage],
  )

  // === SENDMESSAGE ===
  const sendMessage = useCallback(
    async (overrideText?: string) => {
      const text = (overrideText ?? inputText).trim()
      if (!text || streaming) return
      const isGen = isGenerationRequest(text)

      addMessage({ role: 'user', type: 'text', content: text })
      setInputText('')
      scrollToBottom()
      setStreaming(true)
      setStatusText('')
      streamBufRef.current = ''
      streamMsgIdRef.current = null

      if (!isGen) {
        setWorkTaskTitle(text)
        setWorkResult('')
        setWorkStatus('正在理解任务')
        setWorkPhase('running')
        setWorkEvents([])
        setWorkFrame('')
        setWorkFrameMeta({})
        setWorkPointer(null)
        setWorkLive(false)
        setWorkPreviewBlocked(false)
        setWorkApproval(null)
        setWorkPaused(false)
        setWorkStartedAt(Date.now())
        setWorkFinishedAt(null)
      }

      // 生成请求 → 真实 REST 端点；普通对话 → hermes/chat SSE
      try {
        if (isGen) {
          await runGeneration(text)
        } else {
          const apiMessages = [...messages, { role: 'user', content: text } as { role: string; content: string }]
            .filter((m) => m.role === 'user' || m.role === 'assistant')
            .map((m) => ({ role: m.role, content: m.content }))
          const runtimeSessionId = activeConvId || pendingSessionIdRef.current
          activeRuntimeSessionRef.current = runtimeSessionId
          await streamHermesChat({
            model: DEFAULT_MODEL,
            messages: apiMessages,
            session_id: runtimeSessionId,
            onEvent: handleEvent,
          })
        }
      } catch (e) {
        ensureStreamMsg()
        appendText(`\n⚠️ 请求失败: ${getErrorMessage(e)}`)
      } finally {
        const id = streamMsgIdRef.current
        if (id) setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, isStreaming: false } : m)))
        if (streamBufRef.current === '') {
          setMessages((prev) => prev.filter((m) => m.id !== id))
        }
        setStatusText('')
        setStreaming(false)
        await saveConversation()
        await loadConversations()
        streamMsgIdRef.current = null
        streamBufRef.current = ''
        scrollToBottom()
      }
    },
    [addMessage, inputText, streaming, messages, handleEvent, ensureStreamMsg, appendText, saveConversation, loadConversations, scrollToBottom],
  )

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const controlRuntime = useCallback(async (action: 'takeover' | 'resume' | 'stop') => {
    const sessionId = activeRuntimeSessionRef.current
    try {
      await apiPost(`/api/hermes/sessions/${encodeURIComponent(sessionId)}/${action}`)
      if (action === 'takeover') {
        setWorkPaused(true)
        setWorkPhase('paused')
        setWorkStatus('已暂停，当前窗口交由你操作')
      } else if (action === 'resume') {
        setWorkPaused(false)
        setWorkPhase('running')
        setWorkStatus('可以继续交代任务')
      } else {
        setWorkPaused(false)
        setWorkPhase('cancelled')
        setWorkFinishedAt(Date.now())
        setWorkStatus('任务已停止')
      }
    } catch (error) {
      setWorkStatus(getErrorMessage(error))
    }
  }, [])

  const decideApproval = useCallback(async (decision: 'approve_once' | 'deny') => {
    if (!workApproval?.id) return
    try {
      await apiPost(`/api/hermes/approvals/${encodeURIComponent(workApproval.id)}`, { decision })
      upsertWorkEvent({
        type: 'approval',
        title: decision === 'approve_once' ? '已确认继续' : '已取消这一步',
        state: decision === 'approve_once' ? 'success' : 'warning',
      })
      setWorkApproval(null)
      setWorkPhase(decision === 'approve_once' ? 'running' : 'cancelled')
      setWorkStatus(decision === 'approve_once' ? '继续执行' : '已取消操作')
    } catch (error) {
      setWorkStatus(getErrorMessage(error))
    }
  }, [upsertWorkEvent, workApproval])

  // === RENDER ===
  return (
    <div className="flex h-[calc(100vh-4rem)] bg-[#0B0F1A] overflow-hidden">
      {!historyCollapsed && (
        <ConversationPanel
          conversations={conversations}
          activeConvId={activeConvId}
          onSelect={selectConversation}
          onNew={newConversation}
          onPin={handlePin}
          onArchive={handleArchive}
          onDelete={handleDelete}
          onRename={handleRename}
        />
      )}

      <div className="relative flex-1 flex flex-col min-w-0">
        {!workViewOpen && (
          <button
            onClick={() => setWorkViewOpen(true)}
            className="absolute right-4 top-3 z-10 w-9 h-9 grid place-items-center border border-[#273449] bg-[#111827]/90 text-[#94A3B8] hover:text-[#E2E8F0] hover:border-[#475569]"
            aria-label="打开工作现场"
            title="工作现场"
          >
            <Monitor className="w-4 h-4" />
          </button>
        )}
        {messages.length === 0 ? (
          <WelcomeState
            inputText={inputText}
            setInputText={setInputText}
            onSend={() => sendMessage()}
            onCaseClick={sendCaseCard}
            streaming={streaming}
            caseCards={caseCards}
            caseCardsLoading={caseCardsLoading}
            skillCount={hermesRuntime?.skills?.count ?? 0}
            memoryEnabled={Boolean(hermesRuntime?.memory?.enabled)}
          />
        ) : (
          <>
            {/* Messages */}
            <div ref={messagesRef} className="flex-1 overflow-y-auto">
              <div className="px-8 py-6 space-y-6">
                {messages.map((m, idx) => (
                  <ChatMessageView
                    key={m.id}
                    message={m}
                    statusText={streaming && idx === messages.length - 1 ? statusText : undefined}
                    userName={currentUserName}
                  />
                ))}
              </div>
            </div>

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
          </>
        )}
      </div>

      <EmployeeWorkView
        open={workViewOpen}
        taskTitle={workTaskTitle}
        result={workResult}
        status={workStatus}
        phase={workPhase}
        frameUrl={workFrame}
        frameMeta={workFrameMeta}
        pointer={workPointer}
        live={workLive}
        previewBlocked={workPreviewBlocked}
        events={workEvents}
        approval={workApproval}
        paused={workPaused}
        busy={streaming}
        startedAt={workStartedAt}
        finishedAt={workFinishedAt}
        onClose={() => setWorkViewOpen(false)}
        onTakeover={() => controlRuntime('takeover')}
        onResume={() => controlRuntime('resume')}
        onStop={() => controlRuntime('stop')}
        onApproval={decideApproval}
      />
    </div>
  )
}


