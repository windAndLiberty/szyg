import { useState, useMemo, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, X, Sparkles, Check, RotateCcw, Loader2, ChevronRight,
  Megaphone, PenTool, GraduationCap, DollarSign, Map, Target, Box,
  ClipboardList, TrendingUp, LifeBuoy, Tag, Send, ArrowLeft, History,
  Trash2, Bot,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { apiGet, apiPost, apiDel, streamHermesChat, getErrorMessage } from '@/lib/api'
import type { LucideIcon } from 'lucide-react'

// ── 类型定义 ──
interface Division {
  id: string
  label: string
  icon: string
  color: string
  count: number
}
interface AgentSummary {
  slug: string
  name: string
  description: string
  emoji: string
  color: string
  vibe: string
  division: string
}
interface MarketInitResponse {
  divisions: Division[]
  agents: AgentSummary[]
  active: ActiveExpert | null
}
interface ActiveExpert {
  slug: string
  name: string
  description: string
  emoji: string
  division: string
  division_label: string
  prompt: string
}
interface AgencyMessage {
  role: string
  content: string
  timestamp: number
}
interface AgencyConversation {
  id: string
  title: string
  expert_slug: string
  expert_name: string
  expert_emoji: string
  expert_division: string
  messages: AgencyMessage[]
  created_at: string
  updated_at: string
}

// ── Division 图标映射 ──
const DIVISION_ICONS: Record<string, LucideIcon> = {
  Megaphone, PenTool, GraduationCap, DollarSign, Map, Target, Box,
  ClipboardList, TrendingUp, LifeBuoy, Sparkles,
}
function getDivisionIcon(name: string): LucideIcon {
  return DIVISION_ICONS[name] || Sparkles
}

// ── 动画 ──
const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.05 } },
}
const cardVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
}

const DEFAULT_MODEL = 'doubao-seed-2-0-pro-260215'

export default function AIMarket() {
  // ── 视图状态 ──
  const [view, setView] = useState<'market' | 'chat'>('market')

  // ── 市场状态 ──
  const [divisions, setDivisions] = useState<Division[]>([])
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [activeExpert, setActiveExpert] = useState<ActiveExpert | null>(null)
  const [selectedDivision, setSelectedDivision] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [activating, setActivating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ── 聊天状态 ──
  const [conversations, setConversations] = useState<AgencyConversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<AgencyMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const initDone = useRef(false)
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    })
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

  // ── 初始加载：一次请求获取 divisions + agents + active ──
  useEffect(() => {
    setLoading(true)
    apiGet<MarketInitResponse>('/api/agency/market-init')
      .then((data) => {
        setDivisions(data.divisions)
        setAgents(data.agents)
        setActiveExpert(data.active)
        initDone.current = true
      })
      .catch((e) => setError(getErrorMessage(e, '加载失败')))
      .finally(() => setLoading(false))
  }, [])

  // ── 加载激活专家（用于 handleSelectExpert 后刷新）──
  const loadActive = useCallback(() => {
    apiGet<ActiveExpert | null>('/api/agency/active')
      .then(setActiveExpert)
      .catch(() => setActiveExpert(null))
  }, [])

  // ── 加载历史对话 ──
  const loadConversations = useCallback(() => {
    apiGet<AgencyConversation[]>('/api/agency/conversations')
      .then(setConversations)
      .catch(() => {})
  }, [])
  useEffect(() => { loadConversations() }, [loadConversations])

  // ── 加载专家列表（250ms 搜索防抖 + 请求取消，防止竞态条件）──
  useEffect(() => {
    if (view !== 'market' || !initDone.current) return
    // 清除上一次定时器
    if (searchTimer.current) clearTimeout(searchTimer.current)
    const abort = new AbortController()

    const doFetch = () => {
      setLoading(true)
      const params = new URLSearchParams()
      if (selectedDivision) params.set('division', selectedDivision)
      if (search.trim()) params.set('search', search.trim())
      const qs = params.toString()
      const url = `/api/agency/agents${qs ? '?' + qs : ''}`
      const headers: Record<string, string> = {}
      const token = localStorage.getItem('token')
      if (token) headers['Authorization'] = `Bearer ${token}`
      fetch(url, { headers, signal: abort.signal })
        .then(async (r) => {
          if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`)
          return r.json()
        })
        .then((data) => { setAgents(data); setError(null) })
        .catch((e) => {
          if ((e as Error).name !== 'AbortError') setError(getErrorMessage(e, '加载专家失败'))
        })
        .finally(() => setLoading(false))
    }

    // 纯分类筛选立即执行；文本搜索 250ms 防抖
    if (search.trim()) {
      searchTimer.current = setTimeout(doFetch, 250)
    } else {
      doFetch()
    }

    return () => {
      abort.abort()
      if (searchTimer.current) clearTimeout(searchTimer.current)
    }
  }, [selectedDivision, search, view])

  // ── 激活专家 → 创建对话 → 进入聊天 ──
  const handleSelectExpert = useCallback(async (slug: string) => {
    setActivating(true)
    setError(null)
    try {
      await apiPost(`/api/agency/activate/${slug}`)
      await loadActive()
      const conv = await apiPost<AgencyConversation>('/api/agency/conversations')
      setActiveConvId(conv.id)
      setMessages([])
      setView('chat')
      setShowHistory(false)
      loadConversations()
    } catch (e) {
      setError(getErrorMessage(e, '激活专家失败'))
    } finally {
      setActivating(false)
    }
  }, [loadActive, loadConversations])

  // ── 加载已有对话 ──
  const handleOpenConversation = useCallback(async (conv: AgencyConversation) => {
    setActivating(true)
    setError(null)
    try {
      // 先激活该对话绑定的专家
      await apiPost(`/api/agency/activate/${conv.expert_slug}`)
      await loadActive()
      setActiveConvId(conv.id)
      setMessages(conv.messages || [])
      setView('chat')
      setShowHistory(false)
    } catch (e) {
      setError(getErrorMessage(e, '加载对话失败'))
    } finally {
      setActivating(false)
    }
  }, [loadActive])

  // ── 发送消息 ──
  const handleSend = useCallback(async () => {
    if (!inputText.trim() || streaming || !activeConvId) return
    const text = inputText.trim()
    setInputText('')

    const userMsg: AgencyMessage = { role: 'user', content: text, timestamp: Date.now() / 1000 }
    setMessages((prev) => [...prev, userMsg])
    await apiPost(`/api/agency/conversations/${activeConvId}/messages`, userMsg).catch(() => {})

    // 构建历史消息列表供 LLM 上下文
    const allMsgs = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }))

    setStreaming(true)
    let fullContent = ''
    // 添加占位 assistant 消息
    setMessages((prev) => [...prev, { role: 'assistant', content: '', timestamp: Date.now() / 1000 }])

    try {
      await streamHermesChat({
        model: DEFAULT_MODEL,
        messages: allMsgs,
        expert_prompt: activeExpert?.prompt || '',
        onEvent: (ev) => {
          if (ev.type === 'chunk' && ev.content) {
            fullContent += ev.content
            setMessages((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              if (last && last.role === 'assistant' && last.content === '') {
                // 更新占位消息
              }
              next[next.length - 1] = { ...next[next.length - 1], content: fullContent }
              return next
            })
          }
        },
      })
    } catch (e) {
      setError(getErrorMessage(e, '对话请求失败'))
      fullContent = fullContent || '抱歉，请求失败了，请重试。'
    } finally {
      setStreaming(false)
    }

    // 保存 assistant 消息到后端
    const assistantMsg: AgencyMessage = { role: 'assistant', content: fullContent, timestamp: Date.now() / 1000 }
    if (fullContent) {
      apiPost(`/api/agency/conversations/${activeConvId}/messages`, assistantMsg).catch(() => {})
    }
  }, [inputText, streaming, activeConvId, messages])

  // ── 删除对话 ──
  const handleDeleteConversation = useCallback(async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    await apiDel(`/api/agency/conversations/${convId}`).catch(() => {})
    loadConversations()
    if (activeConvId === convId) {
      setActiveConvId(null)
      setMessages([])
    }
  }, [activeConvId, loadConversations])

  // ── 返回市场 ──
  const backToMarket = useCallback(() => {
    setView('market')
    setActiveConvId(null)
    setMessages([])
    setShowHistory(false)
    setError(null)
  }, [])

  // ── 恢复默认（停用专家）──
  const deactivateExpert = useCallback(async () => {
    setActivating(true)
    try {
      await apiPost('/api/agency/deactivate')
      await loadActive()
    } catch (e) {
      setError(getErrorMessage(e, '恢复失败'))
    } finally {
      setActivating(false)
    }
  }, [loadActive])

  const totalAgents = useMemo(() => divisions.reduce((s, d) => s + d.count, 0), [divisions])

  // ═══════════════════════════════════════════════════════════════
  // 聊天视图
  // ═══════════════════════════════════════════════════════════════
  if (view === 'chat') {
    const expert = activeExpert
    return (
      <div className="flex flex-1 min-h-0 gap-0">
        {/* ── 历史面板（侧边栏）── */}
        <AnimatePresence>
          {showHistory && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 280, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              className="overflow-hidden border-r border-[#1E293B] shrink-0"
            >
              <div className="w-[280px] h-full flex flex-col bg-[#0D1321]">
                <div className="px-4 py-3 border-b border-[#1E293B] flex items-center justify-between">
                  <span className="text-body-md font-medium text-[#F1F5F9]">历史对话</span>
                  <button onClick={() => setShowHistory(false)} className="p-1 rounded text-[#64748B] hover:text-[#F1F5F9]">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                  {conversations.length === 0 ? (
                    <p className="text-body-sm text-[#64748B] text-center py-8">暂无对话记录</p>
                  ) : (
                    conversations.map((c) => (
                      <button
                        key={c.id}
                        onClick={() => handleOpenConversation(c)}
                        className={cn(
                          'group w-full text-left p-3 rounded-card border transition-colors',
                          activeConvId === c.id
                            ? 'border-[#6366F1] bg-[rgba(99,102,241,0.08)]'
                            : 'border-transparent hover:bg-[#1A2235]',
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-lg shrink-0">{c.expert_emoji}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-body-sm font-medium text-[#F1F5F9] truncate">{c.title}</div>
                            <div className="text-[11px] text-[#64748B] truncate">{c.expert_name}</div>
                          </div>
                          <button
                            onClick={(e) => handleDeleteConversation(c.id, e)}
                            className="p-1 rounded text-[#64748B] hover:text-[#EF4444] opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── 聊天主区域 ── */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* 聊天顶栏：专家信息 + 操作 */}
          <div className="shrink-0 px-4 py-3 border-b border-[#1E293B] flex items-center gap-3">
            <button
              onClick={backToMarket}
              className="flex items-center gap-1 px-2 py-1.5 rounded-button text-[13px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)] transition-colors shrink-0"
            >
              <ArrowLeft className="w-4 h-4" /> 市场
            </button>

            {expert && (
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center text-lg shrink-0"
                  style={{ background: `${divisions.find((d) => d.id === expert.division)?.color || '#6366F1'}22` }}>
                  {expert.emoji}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-body-sm font-semibold text-[#F1F5F9] truncate">{expert.name}</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-[rgba(99,102,241,0.12)] text-[#818CF8] shrink-0">
                      {expert.division_label}
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => setShowHistory((v) => !v)}
                className={cn('p-2 rounded-lg text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)] transition-colors', showHistory && 'text-[#6366F1]')}
                title="历史对话"
              >
                <History className="w-4 h-4" />
              </button>
              {activeExpert && (
                <button
                  onClick={() => { deactivateExpert(); backToMarket() }}
                  disabled={activating}
                  className="flex items-center gap-1 px-2 py-1.5 rounded-button text-[12px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)] transition-colors disabled:opacity-50"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> 换专家
                </button>
              )}
            </div>
          </div>

          {/* 消息列表 */}
          <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center min-h-[40vh] text-[#64748B] gap-3">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-3xl shadow-glow">
                  {expert?.emoji || '🤖'}
                </div>
                <p className="text-body-md font-medium text-[#F1F5F9]">{expert?.name || '专家'}</p>
                <p className="text-body-sm text-[#64748B] text-center max-w-sm">
                  {expert?.description || '开始对话，让专家为你提供专业建议'}
                </p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={cn('flex gap-3', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                  {msg.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center text-base shrink-0 mt-0.5"
                      style={{ background: `${divisions.find((d) => d.id === expert?.division)?.color || '#6366F1'}22` }}>
                      {expert?.emoji || '🤖'}
                    </div>
                  )}
                  <div className={cn(
                    'max-w-[75%] rounded-card-lg px-4 py-3 text-body-sm leading-relaxed',
                    msg.role === 'user'
                      ? 'bg-[#6366F1] text-white'
                      : 'bg-[#1A2235] text-[#F1F5F9] border border-[#1E293B]',
                  )}>
                    <div className="whitespace-pre-wrap break-words">
                      {msg.content || (streaming && idx === messages.length - 1 ? (
                        <span className="flex items-center gap-1 text-[#64748B]">
                          <Loader2 className="w-3.5 h-3.5 animate-spin" /> 思考中…
                        </span>
                      ) : '')}
                    </div>
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-lg bg-[#6366F1] flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="w-4 h-4 text-white" />
                    </div>
                  )}
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 输入栏 */}
          <div className="shrink-0 px-4 py-3 border-t border-[#1E293B]">
            <div className="flex items-center gap-2">
              <input
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                placeholder={expert ? `向${expert.name}提问…` : '输入消息…'}
                disabled={streaming}
                className="flex-1 h-11 px-4 rounded-card bg-[#0D1321] border border-[#1E293B] text-body-md text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155] transition-colors disabled:opacity-50"
              />
              <button
                onClick={handleSend}
                disabled={!inputText.trim() || streaming}
                className="w-11 h-11 rounded-card bg-[#6366F1] text-white flex items-center justify-center hover:bg-[#818CF8] active:scale-95 transition-all disabled:opacity-40 shrink-0"
              >
                {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ═══════════════════════════════════════════════════════════════
  // 市场视图
  // ═══════════════════════════════════════════════════════════════
  return (
    <motion.div variants={containerVariants} initial="hidden" animate="visible" className="space-y-6">
      {/* 页头 */}
      <motion.div variants={cardVariants}>
        <h1 className="text-display-md font-display text-[#F1F5F9] mb-2">AI 人才市场</h1>
        <p className="text-body-lg text-[#94A3B8]">
          发现并启用领域专家，为超级员工切换专业角色 · 共 {totalAgents} 位专家
        </p>
      </motion.div>

      {/* 当前激活专家提示 */}
      {activeExpert && (
        <motion.div
          variants={cardVariants}
          className="rounded-card-lg border border-[rgba(99,102,241,0.3)] p-4 flex items-center gap-4"
          style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(17,24,39,0.6) 100%)' }}
        >
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-2xl shrink-0 shadow-glow">
            {activeExpert.emoji}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-body-md font-medium text-[#F1F5F9]">{activeExpert.name}</span>
              <span className="px-2 py-0.5 rounded text-[11px] bg-[rgba(99,102,241,0.15)] text-[#818CF8]">{activeExpert.division_label}</span>
            </div>
            <p className="text-body-sm text-[#94A3B8] mt-0.5 line-clamp-1">{activeExpert.description}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="flex items-center gap-1 text-[12px] text-[#10B981]"><Check className="w-3.5 h-3.5" /> 已激活</span>
            <button onClick={deactivateExpert} disabled={activating} className="flex items-center gap-1.5 px-3 py-1.5 rounded-button text-[13px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)] transition-colors disabled:opacity-50">
              <RotateCcw className="w-3.5 h-3.5" /> 恢复默认
            </button>
          </div>
        </motion.div>
      )}

      {/* 搜索栏 */}
      <motion.div variants={cardVariants} className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索专家名称、能力或领域…" className="w-full h-12 pl-11 pr-4 rounded-card bg-[#0D1321] border border-[#1E293B] text-body-md text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155] transition-colors" />
      </motion.div>

      {/* 分类标签栏 */}
      <motion.div variants={cardVariants} className="flex items-center gap-2 flex-wrap">
        <button onClick={() => setSelectedDivision(null)} className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-button text-[13px] font-medium transition-all', !selectedDivision ? 'bg-[#6366F1] text-white' : 'bg-[#1A2235] text-[#94A3B8] hover:text-[#F1F5F9] border border-[#1E293B]')}>
          <Tag className="w-3.5 h-3.5" /> 全部 {totalAgents}
        </button>
        {divisions.map((d) => {
          const Icon = getDivisionIcon(d.icon)
          const isActive = selectedDivision === d.id
          return (
            <button key={d.id} onClick={() => setSelectedDivision(isActive ? null : d.id)} className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-button text-[13px] font-medium transition-all border', isActive ? 'text-white' : 'bg-[#1A2235] text-[#94A3B8] hover:text-[#F1F5F9] border-[#1E293B]')} style={isActive ? { background: d.color, borderColor: d.color } : undefined}>
              <Icon className="w-3.5 h-3.5" />{d.label}<span className="text-[11px] opacity-70">{d.count}</span>
            </button>
          )
        })}
      </motion.div>

      {error && <div className="rounded-card border border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.08)] px-4 py-3 text-body-sm text-[#EF4444]">⚠️ {error}</div>}

      {/* 专家网格 */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-[#64748B] gap-2">
          <Loader2 className="w-5 h-5 animate-spin" /><span className="text-body-md">加载专家列表…</span>
        </div>
      ) : agents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-[#64748B] gap-2">
          <Search className="w-8 h-8 opacity-40" /><span className="text-body-md">未找到匹配的专家</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {agents.map((agent) => {
            const div = divisions.find((d) => d.id === agent.division)
            const isActive = activeExpert?.slug === agent.slug
            return (
              <motion.button
                key={agent.slug}
                variants={cardVariants}
                onClick={() => handleSelectExpert(agent.slug)}
                disabled={activating}
                whileHover={{ y: -4 }}
                className="group text-left rounded-card-lg overflow-hidden border border-[#1E293B] hover:border-[#6366F1]/30 transition-all disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)' }}
              >
                <div className="p-5">
                  {/* 顶部：emoji + 名称 + 状态 */}
                  <div className="flex items-start gap-3 mb-3">
                    <div className="w-11 h-11 rounded-xl flex items-center justify-center text-xl shrink-0"
                      style={{ background: `${div?.color || '#6366F1'}22` }}>{agent.emoji}</div>
                    <div className="flex-1 min-w-0 pt-0.5">
                      <div className="flex items-center gap-2">
                        <h3 className="text-body-md font-semibold text-[#F1F5F9] truncate group-hover:text-[#6366F1] transition-colors">{agent.name}</h3>
                        {isActive && <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] bg-[rgba(16,185,129,0.15)] text-[#10B981] shrink-0"><Check className="w-2.5 h-2.5" /> 使用中</span>}
                      </div>
                      {div && (
                        <span className="inline-block mt-1 px-2 py-0.5 rounded text-[11px]"
                          style={{ background: `${div.color}18`, color: div.color }}>{div.label}</span>
                      )}
                    </div>
                  </div>
                  {/* 简介 — 醒目展示 */}
                  <div className="rounded-card bg-[rgba(99,102,241,0.06)] border border-[rgba(99,102,241,0.1)] px-3 py-2.5">
                    <p className="text-body-sm text-[#CBD5E1] leading-relaxed line-clamp-3">
                      {agent.description}
                    </p>
                  </div>
                </div>
                {/* 底部操作提示 */}
                <div className="px-5 py-2.5 border-t border-[#1E293B] flex items-center justify-between bg-[rgba(0,0,0,0.15)]">
                  <span className="text-[12px] text-[#64748B] group-hover:text-[#94A3B8] transition-colors">
                    {activating ? '激活中…' : isActive ? '继续对话' : '点击选择此专家'}
                  </span>
                  <ChevronRight className="w-4 h-4 text-[#64748B] group-hover:text-[#6366F1] transition-colors" />
                </div>
              </motion.button>
            )
          })}
        </div>
      )}
    </motion.div>
  )
}
