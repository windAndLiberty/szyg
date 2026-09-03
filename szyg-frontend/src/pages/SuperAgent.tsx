import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { Globe2 } from 'lucide-react'
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
import SuperAgentComposer, {
  type ComposerAttachment,
  type ComposerSkill,
} from '@/components/superagent/SuperAgentComposer'
import BrowserWorkView, {
  type BrowserApproval,
  type BrowserWorkEvent,
  type BrowserWorkPhase,
} from '@/components/superagent/BrowserWorkView'
import { notifyWorkDone } from '@/lib/workNotifications'
import { uploadKnowledgeDocument } from '@/pages/knowledge/knowledgeApi'

const DEFAULT_MODEL = 'doubao-seed-2-0-pro-260215'

// 会话现场恢复:刷新/重启后自动回到上次打开的对话
const RESTORE_KEY = 'szyg.superagent.active-conversation'
// 工作现场任务完成后,侧边栏「超级员工」导航显示绿点
const WORK_NAV_PATH = '/'

type HermesRuntimeStatus = {
  memory?: { enabled?: boolean }
  skills?: { count?: number }
}

type InstalledSkill = {
  name: string
  skill_name?: string
  identifier: string
  description: string
}

const COMMON_SKILLS: ComposerSkill[] = [
  {
    id: 'content-planning',
    name: '内容策划',
    emoji: '✍️',
    description: '策划营销选题、文案和多平台内容方案。',
    guidance: '优先使用内容策划、知识库和内容生成能力，给出可直接执行的营销内容方案。',
  },
  {
    id: 'lead-discovery',
    name: '客户发现',
    emoji: '🎯',
    description: '发现高相关潜在客户并规划安全触达方式。',
    guidance: '优先使用公域搜索、客户线索和企业知识能力，寻找高相关潜在客户机会。',
  },
  {
    id: 'sales-followup',
    name: '转化跟进',
    emoji: '🤝',
    description: '判断客户意向并准备个性化跟进建议。',
    guidance: '优先使用客户、线索和转化分析能力，形成个性化跟进建议与下一步行动。',
  },
  {
    id: 'operations-review',
    name: '运营复盘',
    emoji: '📊',
    description: '汇总经营数据，识别问题并给出优化动作。',
    guidance: '优先使用数据洞察、内容表现和经营分析能力，完成运营复盘并提出优化动作。',
  },
]

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

function workToolPresentation(tool: string, rawArgs: unknown): Omit<BrowserWorkEvent, 'id' | 'state'> | null {
  if (HIDDEN_WORK_TOOLS.has(tool)) return null
  const args = objectValue(rawArgs)
  if (tool === 'szyg_browser') {
    const action = String(args.action || '').toLowerCase()
    const mapping: Record<string, string> = {
      open: '打开网页',
      navigate: '打开网页',
      observe: '理解当前页面',
      read: '读取网页结果',
      click: '操作页面内容',
      type: '填写网页内容',
      press: '提交网页内容',
      scroll: '浏览页面',
      back: '返回上一页',
      forward: '前往下一页',
      refresh: '刷新网页',
    }
    return { type: 'browser', title: mapping[action] || '操作网页', technicalName: `${tool}:${action || 'action'}` }
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
  const navigate = useNavigate()
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
  const [composerAttachments, setComposerAttachments] = useState<ComposerAttachment[]>([])
  const [composerSkills, setComposerSkills] = useState<ComposerSkill[]>(COMMON_SKILLS)
  const [selectedSkill, setSelectedSkill] = useState<ComposerSkill | null>(null)
  // 本组件所属 keep-alive 槽位的路径（App.tsx 按 slot 分别渲染，useLocation 返回本 slot 的路径）
  const myLocation = useLocation()
  const myPath = myLocation.pathname + myLocation.search

  const [currentUserName, setCurrentUserName] = useState(() => getCurrentUser()?.username || '')
  const [workViewOpen, setWorkViewOpen] = useState(false)
  // 当前页面是否处于可见的 keep-alive 槽位(切走时为 false,工作台让出原生窗口)
  const [pageActive, setPageActive] = useState(true)
  const [workTaskTitle, setWorkTaskTitle] = useState('')
  const [workResult, setWorkResult] = useState('')
  const [workStatus, setWorkStatus] = useState('')
  const [workPhase, setWorkPhase] = useState<BrowserWorkPhase>('idle')
  const [workEvents, setWorkEvents] = useState<BrowserWorkEvent[]>([])
  const [workApproval, setWorkApproval] = useState<BrowserApproval | null>(null)
  const [workPaused, setWorkPaused] = useState(false)
  const messagesRef = useRef<HTMLDivElement>(null)
  const messagesStateRef = useRef<ChatMessage[]>([])
  const streamMsgIdRef = useRef<string | null>(null)
  const streamBufRef = useRef<string>('')
  const pendingSessionIdRef = useRef(`szyg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`)
  const activeRuntimeSessionRef = useRef(pendingSessionIdRef.current)
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
      const restored = sessionStorage.getItem(RESTORE_KEY)
      if (restored && restored !== activeConvId) {
        selectConversation(restored)
      }
      const prefill = sessionStorage.getItem('szyg:super-agent-prefill')
      if (prefill) {
        sessionStorage.removeItem('szyg:super-agent-prefill')
        setInputText(prefill)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadConversations])

useEffect(() => {
    if (activeConvId) sessionStorage.setItem(RESTORE_KEY, activeConvId)
    else sessionStorage.removeItem(RESTORE_KEY)
  }, [activeConvId])

  useEffect(() => {
    let active = true
    apiGet<HermesRuntimeStatus>('/api/skills/runtime')
      .then((status) => { if (active) setHermesRuntime(status) })
      .catch(() => { if (active) setHermesRuntime(null) })
    return () => { active = false }
  }, [])

  const loadComposerSkills = useCallback(async () => {
    try {
      const { items } = await apiGet<{ items: InstalledSkill[] }>('/api/skills/installed')
      const installed = (items || []).map((item) => ({
          id: `installed:${item.skill_name || item.identifier || item.name}`,
          name: item.name,
          emoji: '🧩',
          description: item.description || '已添加到超级员工，可在合适的工作中使用。',
          guidance: `本轮优先加载并使用已安装技能“${item.name}”。`,
          installed: true,
      }))
      setComposerSkills([...COMMON_SKILLS, ...installed])
    } catch {
      setComposerSkills(COMMON_SKILLS)
    }
  }, [])

  useEffect(() => {
    loadComposerSkills()
    window.addEventListener('szyg:skills-changed', loadComposerSkills)
    return () => window.removeEventListener('szyg:skills-changed', loadComposerSkills)
  }, [loadComposerSkills])

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

  useEffect(() => {
    const handler = (event: Event) => {
      const path = (event as CustomEvent<{ path?: string }>).detail?.path
      // 与「本 slot 自己的路径」比较，而不是全局 window.location——
      // keep-alive 下切换页面后 window.location 已变为新页面地址，
      // 用全局地址比较会让 pageActive 错误保持 true，导致浏览器区域不隐藏。
      setPageActive(path === myPath)
    }
    window.addEventListener('szyg:keep-alive-active-changed', handler)
    return () => window.removeEventListener('szyg:keep-alive-active-changed', handler)
  }, [myPath])

  const newConversation = useCallback(() => {
    setActiveConvId(null)
    pendingSessionIdRef.current = `szyg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    setMessages([])
    setWorkTaskTitle('')
    setWorkResult('')
    setWorkStatus('')
    setWorkPhase('idle')
    setWorkEvents([])
    setWorkApproval(null)
    setWorkPaused(false)
    setComposerAttachments([])
    setSelectedSkill(null)
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

const saveConversation = useCallback(async (messagesSnapshot?: ChatMessage[]) => {
    try {
      // 仅在最新一次提交后保存,避免保存到"流式占位空消息"
      const currentMessages = (messagesSnapshot ?? messagesStateRef.current).filter((m) => !m.isStreaming)
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
          attachments: m.attachments,
          skill_name: m.skill_name,
          skill_icon: m.skill_icon,
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

  // 保存队列:发送流程结束后置 1,待最新状态提交后自动保存(消除竞态)
  const [saveTick, setSaveTick] = useState(0)

  useEffect(() => {
    if (saveTick === 0) return
    ;(async () => {
      const snapshot = [...messagesStateRef.current]
      await Promise.all([saveConversation(snapshot), loadConversations()])
    })()
  }, [saveTick, saveConversation])

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

  const upsertWorkEvent = useCallback((event: Omit<BrowserWorkEvent, 'id'> & { id?: string }) => {
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
          if (name === 'szyg_browser') {
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
        case 'browser.action':
        case 'browser.state': {
          setHistoryCollapsed(true)
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
          setWorkStatus('正在理解任务')
          break
        case 'run.paused':
          setWorkPaused(true)
          setWorkPhase('paused')
          setWorkStatus(String(ev.content || '已暂停'))
          break
case 'run.completed':
          ensureStreamMsg()
          if (!streamBufRef.current && ev.content) appendText(String(ev.content))
          setWorkEvents((current) => current.map((item) => item.state === 'running' ? { ...item, state: 'success', detail: undefined } : item))
          setWorkPaused(false)
          setWorkPhase('completed')
          setWorkResult(compactWorkResult(ev.content || streamBufRef.current))
          setWorkStatus('任务已完成')
          notifyWorkDone(WORK_NAV_PATH)
          break
case 'run.failed':
          ensureStreamMsg()
          // 设备绑定策略:仅真正"请先登录"(从未登录/已退出)才要求重登;
          // 401/过期/换 IP/超时等均不触发登录页
          if (/(?:^|：|:)\s*(请先登录)\s*$/i.test(String(ev.content || '').trim())) {
            window.dispatchEvent(new Event('szyg:cloud-session-expired'))
          }
          replaceStreamText(toUserFacingMessage(ev.content, '当前操作未完成'))
          setWorkEvents((current) => current.map((item) => item.state === 'running' ? { ...item, state: 'error', detail: '任务在这一步停止' } : item))
          setWorkPhase(String(ev.code || '') === 'cancelled' ? 'cancelled' : 'failed')
          setWorkStatus(toUserFacingMessage(ev.content, '当前操作未完成'))
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

  const handleFilesSelected = useCallback(async (files: File[]) => {
    const availableSlots = Math.max(0, 5 - composerAttachments.length)
    const selected = files.slice(0, availableSlots)
    if (selected.length === 0) return

    const pending = selected.map((file) => ({
      file,
      attachment: {
        id: nextId('attachment'),
        name: file.name,
        size: file.size,
        status: file.size > 80 * 1024 * 1024 ? 'error' as const : 'uploading' as const,
        error: file.size > 80 * 1024 * 1024 ? '文件超过 80 MB' : undefined,
      },
    }))
    setComposerAttachments((current) => [...current, ...pending.map((item) => item.attachment)])

    await Promise.allSettled(pending.map(async ({ file, attachment }) => {
      if (attachment.status === 'error') return
      try {
        const document = await uploadKnowledgeDocument(file, '超级员工附件')
        setComposerAttachments((current) => current.map((item) => item.id === attachment.id
          ? { ...item, status: 'ready', documentId: document.id, error: undefined }
          : item))
      } catch (error) {
        setComposerAttachments((current) => current.map((item) => item.id === attachment.id
          ? { ...item, status: 'error', error: getErrorMessage(error, '上传失败') }
          : item))
      }
    }))
  }, [composerAttachments.length])

  const removeComposerAttachment = useCallback((id: string) => {
    setComposerAttachments((current) => current.filter((item) => item.id !== id))
  }, [])

  // === SENDMESSAGE ===
  const sendMessage = useCallback(
    async (overrideText?: string) => {
      const readyAttachments = composerAttachments.filter((item) => item.status === 'ready')
      const text = (overrideText ?? inputText).trim() || (readyAttachments.length > 0 ? '请阅读并分析我上传的附件。' : '')
      if (!text || streaming) return
      // 带附件或显式技能时交给超级员工编排，避免绕过资料检索/技能加载。
      const isGen = isGenerationRequest(text) && readyAttachments.length === 0 && !selectedSkill
      const skillForTurn = selectedSkill
      const attachmentsForTurn = readyAttachments.map((item) => ({
        id: item.id,
        name: item.name,
        size: item.size,
        documentId: item.documentId,
      }))

      addMessage({
        role: 'user',
        type: 'text',
        content: text,
        attachments: attachmentsForTurn,
        skill_name: skillForTurn?.name,
        skill_icon: skillForTurn?.emoji,
      })
      setInputText('')
      setComposerAttachments([])
      setSelectedSkill(null)
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
        setWorkApproval(null)
        setWorkPaused(false)
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
            expert_prompt: [
              skillForTurn?.guidance || '',
              attachmentsForTurn.length > 0
                ? `用户本轮上传了以下资料到知识库：${attachmentsForTurn.map((item) => `${item.name}（文档ID：${item.documentId}）`).join('、')}。请先检查这些文档的解析状态；如仍在处理请稍候并重新检查，随后检索和阅读资料，再回答或执行任务。`
                : '',
            ].filter(Boolean).join('\n'),
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
        setSaveTick((t) => t + 1)
        streamMsgIdRef.current = null
        streamBufRef.current = ''
        scrollToBottom()
      }
    },
    [addMessage, inputText, streaming, messages, handleEvent, ensureStreamMsg, appendText, saveConversation, loadConversations, scrollToBottom, composerAttachments, selectedSkill],
  )

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
        {!workViewOpen && (workEvents.length > 0 || workPhase !== 'idle') && (
          <button
            onClick={() => setWorkViewOpen(true)}
            className="absolute right-4 top-3 z-10 inline-flex h-9 items-center gap-2 rounded-lg border border-[#273449] bg-[#111827]/90 px-3 text-xs text-[#94A3B8] hover:text-[#E2E8F0] hover:border-[#475569]"
            aria-label="查看工作现场"
            title="查看超级员工正在处理的网页"
          >
            <Globe2 className="w-4 h-4" />
            <span>工作现场</span>
          </button>
        )}
        {messages.length === 0 ? (
          <WelcomeState
            inputText={inputText}
            setInputText={setInputText}
            composer={(
              <SuperAgentComposer
                value={inputText}
                onChange={setInputText}
                onSend={() => sendMessage()}
                streaming={streaming}
                attachments={composerAttachments}
                onFilesSelected={handleFilesSelected}
                onRemoveAttachment={removeComposerAttachment}
                skills={composerSkills}
                selectedSkill={selectedSkill}
                onSelectSkill={setSelectedSkill}
                onDiscoverSkills={() => navigate('/knowledge/skills')}
              />
            )}
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
              <div className="mx-auto max-w-4xl px-5 py-4">
                <SuperAgentComposer
                  value={inputText}
                  onChange={setInputText}
                  onSend={() => sendMessage()}
                  streaming={streaming}
                  compact
                  attachments={composerAttachments}
                  onFilesSelected={handleFilesSelected}
                  onRemoveAttachment={removeComposerAttachment}
                  skills={composerSkills}
                  selectedSkill={selectedSkill}
                  onSelectSkill={setSelectedSkill}
                  onDiscoverSkills={() => navigate('/knowledge/skills')}
                />
              </div>
            </div>
          </>
        )}
      </div>

<BrowserWorkView
        open={workViewOpen}
        pageActive={pageActive}
        taskTitle={workTaskTitle}
        result={workResult}
        status={workStatus}
        phase={workPhase}
        events={workEvents}
        approval={workApproval}
        paused={workPaused}
        busy={streaming}
        onClose={() => setWorkViewOpen(false)}
        onTakeover={() => controlRuntime('takeover')}
        onResume={() => controlRuntime('resume')}
        onStop={() => controlRuntime('stop')}
        onApproval={decideApproval}
      />
    </div>
  )
}
