import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Send } from 'lucide-react'
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
  getCurrentUser,
  type HermesEvent,
} from '@/lib/api'
import ConversationPanel from '@/components/superagent/ConversationPanel'
import WelcomeState from '@/components/superagent/WelcomeState'
import ChatMessageView from '@/components/superagent/ChatMessageView'

const DEFAULT_MODEL = 'doubao-seed-2-0-pro-260215'

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

export default function SuperAgent() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [caseCards, setCaseCards] = useState<CaseCard[]>([])
  const [caseCardsLoading, setCaseCardsLoading] = useState(false)
  const messagesRef = useRef<HTMLDivElement>(null)
  const streamMsgIdRef = useRef<string | null>(null)
  const streamBufRef = useRef<string>('')

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    })
  }, [])

  useEffect(() => {
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
      const data = await apiGet<{ conversations: Conversation[] }>('/api/conversations')
      setConversations(data.conversations || [])
    } catch {
      /* ignore */
    }
  }, [])

  const loadCaseCards = useCallback(async () => {
    setCaseCardsLoading(true)
    try {
      const titles = conversations.slice(0, 10).map((c) => c.title).filter(Boolean)
      const data = await apiPost<{ cards: CaseCard[] }>('/api/hermes/case-cards', {
        recent_titles: titles,
        limit: 6,
      })
      setCaseCards(data.cards || [])
    } catch {
      setCaseCards([])
    } finally {
      setCaseCardsLoading(false)
    }
  }, [conversations])

  useEffect(() => {
    ;(async () => {
      await autoLogin()
      await loadConversations()
    })()
  }, [loadConversations])

  useEffect(() => {
    if (messages.length === 0) loadCaseCards()
  }, [messages.length, loadCaseCards])

  const newConversation = useCallback(() => {
    setActiveConvId(null)
    setMessages([])
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
      const firstUser = messages.find((m) => m.role === 'user' && m.type === 'text')
      const payload = {
        title: firstUser ? firstUser.content.slice(0, 50) : '新对话',
        messages: messages.map((m) => ({
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
      } else if (messages.length > 0) {
        const data = await apiPost<{ id: string }>('/api/conversations', payload)
        if (data?.id) setActiveConvId(data.id)
      }
    } catch {
      /* ignore */
    }
  }, [messages, activeConvId])

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
        case 'tool_result': {
          let res = ev.result || ''
          let status: 'success' | 'error' = 'success'
          try {
            const r = JSON.parse(res)
            if (r && r.error) {
              status = 'error'
              res = r.error
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
        case 'error':
          ensureStreamMsg()
          appendText('\n⚠️ ' + (ev.content || ''))
          break
        case 'status':
          setStatusText(ev.content || '')
          break
        default:
          break
      }
    },
    [addMessage, ensureStreamMsg, appendText],
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

      addMessage({ role: 'user', type: 'text', content: text })
      setInputText('')
      scrollToBottom()
      setStreaming(true)
      setStatusText('')
      streamBufRef.current = ''
      streamMsgIdRef.current = null

      // 生成请求 → 真实 REST 端点；普通对话 → hermes/chat SSE
      const isGen = isGenerationRequest(text)
      try {
        if (isGen) {
          await runGeneration(text)
        } else {
          const apiMessages = [...messages, { role: 'user', content: text } as { role: string; content: string }]
            .filter((m) => m.role === 'user' || m.role === 'assistant')
            .map((m) => ({ role: m.role, content: m.content }))
          await streamHermesChat({
            model: DEFAULT_MODEL,
            messages: apiMessages,
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

  // === RENDER ===
  return (
    <div className="flex h-[calc(100vh-4rem)] bg-[#0B0F1A] overflow-hidden">
      <ConversationPanel
        conversations={conversations}
        activeConvId={activeConvId}
        onSelect={selectConversation}
        onNew={newConversation}
        onPin={handlePin}
        onDelete={handleDelete}
        onRename={handleRename}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {messages.length === 0 ? (
          <WelcomeState
            inputText={inputText}
            setInputText={setInputText}
            onSend={() => sendMessage()}
            onCaseClick={sendCaseCard}
            streaming={streaming}
            caseCards={caseCards}
            caseCardsLoading={caseCardsLoading}
          />
        ) : (
          <>
            {/* Messages */}
            <div ref={messagesRef} className="flex-1 overflow-y-auto">
              <div className="px-8 py-6 space-y-6">
                {messages.map((m, idx) => (
                  <ChatMessageView key={m.id} message={m} statusText={streaming && idx === messages.length - 1 ? statusText : undefined} />
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
    </div>
  )
}


