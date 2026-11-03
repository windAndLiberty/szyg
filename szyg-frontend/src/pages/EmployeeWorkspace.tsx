import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Archive,
  Bot,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileBox,
  Laptop,
  LoaderCircle,
  MessageSquarePlus,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from 'lucide-react'
import SuperAgent from './SuperAgent'
import BrowserWorkView, {
  type BrowserApproval,
  type BrowserWorkEvent,
  type BrowserWorkPhase,
} from '@/components/superagent/BrowserWorkView'
import { translateCurrent, useI18n } from '@/lib/i18n'

type RuntimeStatus = {
  phase?: string
  available?: boolean
  ready?: boolean
  version?: string
  error?: string
  activeRuns?: number
}

type Employee = {
  id: string
  agentId: string
  name: string
  emoji: string
  title: string
  status: string
  archived: boolean
  instructions?: string
}

type Session = {
  key: string
  id?: string
  sessionId?: string
  agentId?: string
  label?: string
  displayName?: string
  updatedAt?: number | string
  hasActiveRun?: boolean
}

type TimelineEvent = {
  id: string
  type: string
  source: string
  timestamp: number
  payload: Record<string, unknown>
}

type Message = {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  timestamp?: number
}

type Routine = Record<string, unknown>

const statusLabels: Record<string, string> = {
  stopped: '未启动',
  unavailable: '未安装',
  starting: '正在启动',
  repairing: '正在修复',
  reconnecting: '正在重连',
  ready: '空闲',
  failed: '需要处理',
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function userFacingError(reason: unknown): string {
  const message = reason instanceof Error ? reason.message : String(reason || '')
  if (/credits?.*(余额不足|insufficient)|余额不足|billing error|auth\/billing failure|balance and usage limits/i.test(message)) {
    return translateCurrent('Credits 余额不足，请充值后重试。')
  }
  if (/too many requests|请求较多|rate.?limit/i.test(message)) {
    return translateCurrent('当前请求较多，请稍后重试。')
  }
  if (/openclaw|gateway|protocol|runtime|econn|timed?\s*out|not ready|not initialized|route-compatible authentication source|authentication source.*openai/i.test(message)) {
    return translateCurrent('小妤的工作环境暂时不可用，请稍后重试。')
  }
  return message || translateCurrent('操作暂时没有完成，请稍后重试。')
}

function textContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content.map((part) => {
    if (typeof part === 'string') return part
    const row = asRecord(part)
    return typeof row.text === 'string' ? row.text : ''
  }).filter(Boolean).join('\n')
}

function normalizeEmployees(result: Record<string, unknown>): Employee[] {
  const rows = Array.isArray(result.agents) ? result.agents : []
  return rows.map((value) => {
    const row = asRecord(value)
    const agentId = String(row.agentId || row.id || '')
    return {
      id: agentId,
      agentId,
      name: String(row.name || row.displayName || '数字员工'),
      emoji: String(row.emoji || '✨'),
      title: String(row.title || '数字员工'),
      status: row.hasActiveRun ? 'working' : 'idle',
      archived: Boolean(row.archived),
      instructions: typeof row.instructions === 'string' ? row.instructions : undefined,
    }
  }).filter((item) => item.id && !item.archived)
}

function normalizeSessions(result: Record<string, unknown>): Session[] {
  const rows = Array.isArray(result.sessions) ? result.sessions : Array.isArray(result.items) ? result.items : []
  return rows.map((value) => {
    const row = asRecord(value)
    const rawLabel = String(row.displayName || row.title || row.label || '新对话')
    return {
      key: String(row.key || row.sessionKey || row.id || ''),
      id: typeof row.id === 'string' ? row.id : undefined,
      sessionId: typeof row.sessionId === 'string' ? row.sessionId : undefined,
      agentId: typeof row.agentId === 'string' ? row.agentId : undefined,
      label: rawLabel.startsWith('xiaoyu-') ? '新对话' : rawLabel,
      displayName: typeof row.displayName === 'string' ? row.displayName : undefined,
      updatedAt: typeof row.updatedAt === 'number' || typeof row.updatedAt === 'string' ? row.updatedAt : undefined,
      hasActiveRun: Boolean(row.hasActiveRun),
    }
  }).filter((item) => item.key && !item.key.includes(':cron:'))
}

function eventError(payload: Record<string, unknown>): string {
  for (const key of ['error', 'errorMessage', 'detail', 'message']) {
    if (typeof payload[key] === 'string' && payload[key]) return String(payload[key])
  }
  const data = asRecord(payload.data)
  for (const key of ['error', 'errorMessage', 'detail', 'message']) {
    if (typeof data[key] === 'string' && data[key]) return String(data[key])
  }
  return ''
}

function normalizeHistory(result: Record<string, unknown>): Message[] {
  const rows = Array.isArray(result.messages) ? result.messages : []
  return rows.map((value, index) => {
    const row = asRecord(value)
    const role: Message['role'] = row.role === 'user' || row.role === 'system' ? row.role : 'assistant'
    const rawText = textContent(row.content) || String(row.text || '')
    const text = role === 'assistant' && (/^Your request couldn't be completed:/i.test(rawText) || /auth\/billing failure|route-compatible authentication source/i.test(rawText))
      ? userFacingError(rawText)
      : rawText
    return {
      id: String(asRecord(row.__openclaw).id || row.id || `${index}`),
      role,
      text,
      timestamp: typeof row.timestamp === 'number' ? row.timestamp : undefined,
    }
  }).filter((item) => item.text)
}

function eventTitle(event: TimelineEvent) {
  if (event.type === 'approval') return translateCurrent('等待确认')
  if (event.type === 'question') return translateCurrent('需要补充信息')
  if (event.type === 'artifact') return translateCurrent('生成了新产物')
  if (event.type === 'routine') return translateCurrent('例程状态变化')
  if (event.type === 'computer') return translateCurrent('工作电脑状态变化')
  if (event.type === 'session') return translateCurrent('会话状态变化')
  if (event.type === 'message') return translateCurrent('员工正在工作')
  if (event.type === 'runtime.status') {
    const status = statusLabels[String(event.payload.phase || '')] || '状态更新'
    return `${translateCurrent('小妤')} ${translateCurrent('状态')}：${translateCurrent(status)}`
  }
  return translateCurrent('工作进度更新')
}

function extractEventText(payload: Record<string, unknown>) {
  for (const key of ['text', 'content', 'message', 'summary', 'description', 'command']) {
    if (typeof payload[key] === 'string' && payload[key]) return String(payload[key])
  }
  const data = asRecord(payload.data)
  for (const key of ['text', 'content', 'message', 'summary']) {
    if (typeof data[key] === 'string' && data[key]) return String(data[key])
  }
  return ''
}

function routineState(routine: Routine) {
  const state = asRecord(routine.state)
  const runningAtMs = Number(state.runningAtMs || routine.runningAtMs || 0)
  const lastRunStatus = String(state.lastRunStatus || routine.lastRunStatus || '')
  return {
    running: runningAtMs > 0,
    runningAtMs,
    nextRunAtMs: Number(state.nextRunAtMs || routine.nextRunAtMs || 0),
    lastRunAtMs: Number(state.lastRunAtMs || routine.lastRunAtMs || 0),
    lastRunStatus,
    lastError: String(state.lastError || routine.lastRunError || ''),
  }
}

function formatRoutineTime(value: number) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).format(new Date(value))
}

function routineScheduleLabel(routine: Routine) {
  const schedule = asRecord(routine.schedule)
  if (schedule.kind === 'cron') return `${String(schedule.expr || '')}${schedule.tz ? ` · ${String(schedule.tz)}` : ''}`
  if (schedule.kind === 'every') {
    const minutes = Math.round(Number(schedule.everyMs || 0) / 60_000)
    return minutes >= 60 && minutes % 60 === 0
      ? translateCurrent('每 {v0} 小时', { v0: minutes / 60 })
      : translateCurrent('每 {v0} 分钟', { v0: Math.max(1, minutes) })
  }
  if (schedule.kind === 'at') return formatRoutineTime(new Date(String(schedule.at || '')).getTime())
  if (schedule.kind === 'on-exit') return translateCurrent('本地事件触发')
  if (schedule.kind === 'stream') return translateCurrent('本地数据流触发')
  return translateCurrent('按配置触发')
}

function RoutineCard({ routine, onPause, onRun }: {
  routine: Routine
  onPause: (routine: Routine) => void
  onRun: (routine: Routine) => void
}) {
  const state = routineState(routine)
  const disabled = routine.enabled === false
  const status = state.running
    ? translateCurrent('正在运行')
    : disabled
      ? translateCurrent('已暂停')
      : state.lastRunStatus === 'error'
        ? translateCurrent('上次运行失败')
        : translateCurrent('等待下次运行')
  return (
    <div className={`rounded-xl border p-3 ${state.running ? 'border-[#4F46E5] bg-[#312E81]/20' : 'border-[#1E293B] bg-[#111827]'}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${state.running ? 'bg-[#4F46E5]/25 text-[#A5B4FC]' : 'bg-[#1E293B] text-[#64748B]'}`}>
          {state.running ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Clock3 className="h-4 w-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-xs font-medium">{String(routine.displayName || routine.name || translateCurrent('未命名后台任务'))}</div>
          <div className={`mt-1 text-[11px] ${state.running ? 'text-[#A5B4FC]' : state.lastRunStatus === 'error' ? 'text-[#FB7185]' : 'text-[#64748B]'}`}>{status}</div>
        </div>
        <button onClick={() => onPause(routine)} className="rounded-lg border border-[#273449] p-2 text-[#94A3B8] hover:border-[#6366F1]" title={translateCurrent(disabled ? '恢复定时任务' : '暂停定时任务')}>
          {disabled ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
        </button>
      </div>
      <div className="mt-3 grid grid-cols-[72px_1fr] gap-x-2 gap-y-1 text-[11px] text-[#64748B]">
        <span>{translateCurrent('触发计划')}</span><span className="truncate text-[#94A3B8]">{routineScheduleLabel(routine)}</span>
        <span>{translateCurrent(state.running ? '开始时间' : '下次运行')}</span><span className="text-[#94A3B8]">{formatRoutineTime(state.running ? state.runningAtMs : state.nextRunAtMs)}</span>
        {state.lastRunAtMs > 0 && <><span>{translateCurrent('上次运行')}</span><span className="text-[#94A3B8]">{formatRoutineTime(state.lastRunAtMs)}</span></>}
      </div>
      {state.lastError && <div className="mt-2 line-clamp-2 rounded-lg bg-[#450A0A]/35 px-2 py-1.5 text-[10px] text-[#FCA5A5]">{state.lastError}</div>}
      <div className="mt-3 flex justify-end">
        <button onClick={() => onRun(routine)} disabled={state.running} className="inline-flex items-center gap-1.5 rounded-lg border border-[#273449] px-2.5 py-1.5 text-[11px] text-[#CBD5E1] hover:border-[#6366F1] disabled:cursor-not-allowed disabled:opacity-40"><Play className="h-3 w-3" />{translateCurrent('立即运行')}</button>
      </div>
    </div>
  )
}

export default function EmployeeWorkspace() {
  const { t } = useI18n()
  const api = window.electronAPI?.openClaw
  const legacyMode = !api
  const [runtime, setRuntime] = useState<RuntimeStatus>({ phase: 'starting' })
  const [employees, setEmployees] = useState<Employee[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeEmployeeId, setActiveEmployeeId] = useState('')
  const [activeSessionKey, setActiveSessionKey] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [creatingEmployee, setCreatingEmployee] = useState(false)
  const [newEmployeeName, setNewEmployeeName] = useState('')
  const [newEmployeeTitle, setNewEmployeeTitle] = useState('')
  const [questionAnswer, setQuestionAnswer] = useState('')
  const [browserOpen, setBrowserOpen] = useState(false)
  const [routinePanelOpen, setRoutinePanelOpen] = useState(false)
  const [sideTab, setSideTab] = useState<'activity' | 'routines' | 'artifacts'>('activity')
  const [routines, setRoutines] = useState<Routine[]>([])
  const [routinesLoading, setRoutinesLoading] = useState(false)
  const [artifacts, setArtifacts] = useState<Record<string, unknown>[]>([])
  const [deepThinking, setDeepThinking] = useState(() => window.localStorage.getItem('xiaoyu.deepThinking') === 'true')
  const [error, setError] = useState('')
  const initializedDefaultRef = useRef(false)
  const historyTimerRef = useRef<number | null>(null)

  const activeEmployee = employees.find((item) => item.id === activeEmployeeId) || employees[0]
  const activeSession = sessions.find((item) => item.key === activeSessionKey)
  const employeeDisplayName = (name?: string) => name === '小妤' || !name ? t('小妤') : name

  const refreshHistory = useCallback(async (sessionKey = activeSessionKey, employeeId = activeEmployeeId) => {
    if (!api || !sessionKey) return
    try {
      const result = await api.sessions.history({ sessionKey, agentId: employeeId, limit: 200, maxChars: 12000 })
      const nextMessages = normalizeHistory(result)
      setMessages(nextMessages)
      return nextMessages
    } catch (reason) {
      setError(userFacingError(reason))
    }
  }, [api, activeSessionKey, activeEmployeeId])

  const waitForAssistant = useCallback(async (
    sessionKey: string,
    employeeId: string,
    baselineAssistantCount: number,
  ) => {
    // chat.send is acknowledged after dispatch, before the model turn has
    // necessarily been committed to history. Gateway events can also arrive
    // slightly before the SQLite transcript becomes visible. Poll the narrow
    // history endpoint until a new visible assistant message is committed so
    // the UI never drops a successful reply.
    const deadline = Date.now() + 90_000
    while (Date.now() < deadline) {
      const nextMessages = await refreshHistory(sessionKey, employeeId)
      if (nextMessages && nextMessages.filter((item) => item.role === 'assistant').length > baselineAssistantCount) {
        return
      }
      await new Promise((resolve) => window.setTimeout(resolve, 750))
    }
    await refreshHistory(sessionKey, employeeId)
  }, [refreshHistory])

  const loadWorkspace = useCallback(async () => {
    if (!api) return
    try {
      // Employees and sessions are the critical workspace data. Routines are
      // loaded by their own side panel and must not make the whole employee
      // workspace look unavailable when OpenClaw's cron authority is recovering.
      const [botResult, sessionResult] = await Promise.all([
        api.bots.list(),
        api.sessions.list({ limit: 100, ownerFirst: true }),
      ])
      let nextEmployees = normalizeEmployees(botResult)
      if (nextEmployees.length === 0 && !initializedDefaultRef.current) {
        initializedDefaultRef.current = true
        await api.bots.create({
          name: '小妤',
          emoji: '✨',
          title: '首席数字员工',
          instructions: '理解目标、调度技能、在关键节点等待确认，并用结构化报告交付结果。',
          toolPolicy: { permissionMode: 'guarded' },
        })
        nextEmployees = normalizeEmployees(await api.bots.list())
      }
      setEmployees(nextEmployees)
      setActiveEmployeeId((current) => current || nextEmployees[0]?.id || '')
      const nextSessions = normalizeSessions(sessionResult)
      setSessions(nextSessions)
      const firstSession = nextSessions.find((item) => !nextEmployees[0]?.id || item.agentId === nextEmployees[0].id) || nextSessions[0]
      setActiveSessionKey((current) => current || firstSession?.key || '')
    } catch (reason) {
      setError(userFacingError(reason))
    }
  }, [api])

  const loadRoutines = useCallback(async () => {
    if (!api) return
    setRoutinesLoading(true)
    try {
      const result = await api.routines.list({ includeDisabled: true, limit: 200 })
      const rows = Array.isArray(result.jobs) ? result.jobs : Array.isArray(result.items) ? result.items : []
      setRoutines(rows.map(asRecord))
    } catch {
      // Routine authority recovers independently. Keep the last good snapshot
      // rather than turning a transient scheduler issue into workspace failure.
    } finally {
      setRoutinesLoading(false)
    }
  }, [api])

  useEffect(() => {
    window.localStorage.setItem('xiaoyu.deepThinking', String(deepThinking))
  }, [deepThinking])

  useEffect(() => {
    if (!api) return
    let disposed = false
    const sync = async () => {
      try {
        const status = await api.runtime.status() as RuntimeStatus
        if (disposed) return
        setRuntime(status)
        if (status.ready) await Promise.all([loadWorkspace(), loadRoutines()])
      } catch (reason) {
        if (!disposed) setError(userFacingError(reason))
      }
    }
    void sync()
    const unsubscribe = api.runs.subscribe((event) => {
      if (disposed) return
      if (event.type === 'runtime.status') {
        setRuntime(event.payload as RuntimeStatus)
        return
      }
      if (event.type === 'message' && event.payload.runStatus === 'failed') {
        setError(userFacingError(eventError(event.payload)))
      }
      setEvents((current) => [event as TimelineEvent, ...current].slice(0, 120))
      if (event.type === 'message' || event.type === 'session') {
        if (historyTimerRef.current) window.clearTimeout(historyTimerRef.current)
        historyTimerRef.current = window.setTimeout(() => void refreshHistory(), 180)
      }
      if (event.type === 'routine') void loadRoutines()
    })
    const poll = window.setInterval(sync, 4000)
    return () => {
      disposed = true
      unsubscribe()
      window.clearInterval(poll)
      if (historyTimerRef.current) window.clearTimeout(historyTimerRef.current)
    }
  }, [api, loadRoutines, loadWorkspace, refreshHistory])

  useEffect(() => {
    if (activeSessionKey) void refreshHistory(activeSessionKey, activeEmployeeId)
    else setMessages([])
  }, [activeSessionKey, activeEmployeeId, refreshHistory])

  useEffect(() => {
    if (api && activeEmployeeId) void api.computer.status({ agentId: activeEmployeeId })
  }, [api, activeEmployeeId])

  const filteredSessions = useMemo(
    () => sessions.filter((item) => !activeEmployeeId || !item.agentId || item.agentId === activeEmployeeId),
    [sessions, activeEmployeeId],
  )

  const createSession = useCallback(async () => {
    if (!api || !activeEmployee) return null
    setError('')
    const result = await api.sessions.create({
      agentId: activeEmployee.agentId,
      label: `xiaoyu-${activeEmployee.agentId}-${Date.now()}`,
      displayName: `${activeEmployee.name}的新任务`,
      permissionMode: 'guarded',
      deepThinking,
    })
    const key = String(result.key || result.sessionKey || result.id || '')
    await loadWorkspace()
    if (key) setActiveSessionKey(key)
    return key
  }, [api, activeEmployee, deepThinking, loadWorkspace])

  const sendMessage = useCallback(async () => {
    const message = input.trim()
    if (!api || !activeEmployee || !message || sending) return
    const baselineAssistantCount = messages.filter((item) => item.role === 'assistant').length
    setInput('')
    setError('')
    setSending(true)
    setMessages((current) => [...current, { id: `local-${Date.now()}`, role: 'user', text: message }])
    try {
      const sessionKey = activeSessionKey || await createSession()
      if (!sessionKey) throw new Error('无法创建员工会话')
      await api.runs.send({ sessionKey, agentId: activeEmployee.agentId, message, deepThinking })
      await waitForAssistant(sessionKey, activeEmployee.agentId, baselineAssistantCount)
    } catch (reason) {
      setError(userFacingError(reason))
    } finally {
      setSending(false)
    }
  }, [api, activeEmployee, activeSessionKey, createSession, deepThinking, input, messages, sending, waitForAssistant])

  const createEmployee = useCallback(async () => {
    if (!api || !newEmployeeName.trim()) return
    try {
      const result = await api.bots.create({
        name: newEmployeeName.trim(),
        title: newEmployeeTitle.trim() || '数字员工',
        emoji: '🤖',
        instructions: `你是${newEmployeeTitle.trim() || '数字员工'}，按工作空间规则完成任务。`,
        toolPolicy: { permissionMode: 'guarded' },
      })
      setNewEmployeeName('')
      setNewEmployeeTitle('')
      setCreatingEmployee(false)
      await loadWorkspace()
      if (result.agentId) setActiveEmployeeId(String(result.agentId))
    } catch (reason) {
      setError(userFacingError(reason))
    }
  }, [api, loadWorkspace, newEmployeeName, newEmployeeTitle])

  const runningRoutines = useMemo(
    () => routines.filter((routine) => routineState(routine).running),
    [routines],
  )

  const pauseRoutine = useCallback(async (routine: Routine) => {
    if (!api || !routine.id) return
    try {
      await api.routines.pause({ id: routine.id, paused: routine.enabled !== false })
      await loadRoutines()
    } catch (reason) {
      setError(userFacingError(reason))
    }
  }, [api, loadRoutines])

  const runRoutine = useCallback(async (routine: Routine) => {
    if (!api || !routine.id) return
    try {
      await api.routines.run({ id: routine.id, mode: 'force' })
      await loadRoutines()
    } catch (reason) {
      setError(userFacingError(reason))
    }
  }, [api, loadRoutines])

  const resolveApproval = useCallback(async (approval: TimelineEvent, decision: 'allow-once' | 'deny') => {
    if (!api) return
    const id = String(approval.payload.id || approval.payload.approvalId || '')
    if (!id) return
    try {
      await api.approvals.resolve({ id, decision })
      setEvents((current) => current.filter((item) => item.id !== approval.id))
    } catch (reason) {
      setError(userFacingError(reason))
    }
  }, [api])

  const approvalEvent = events.find((event) => event.type === 'approval')
  const questionEvent = events.find((event) => event.type === 'question')
  const answerQuestion = useCallback(async () => {
    if (!api || !questionEvent || !questionAnswer.trim()) return
    const id = String(questionEvent.payload.id || questionEvent.payload.questionId || '')
    const questions = Array.isArray(questionEvent.payload.questions) ? questionEvent.payload.questions : []
    const first = asRecord(questions[0])
    const questionId = String(first.questionId || first.id || 'answer')
    if (!id) return
    try {
      await api.questions.answer({ id, answers: { answers: { [questionId]: [questionAnswer.trim()] } }, resolvedBy: 'xiaoyu-desktop' })
      setQuestionAnswer('')
      setEvents((current) => current.filter((item) => item.id !== questionEvent.id))
    } catch (reason) {
      setError(userFacingError(reason))
    }
  }, [api, questionAnswer, questionEvent])
  const workEvents = useMemo<BrowserWorkEvent[]>(() => events.slice(0, 30).map((event) => ({
    id: event.id,
    type: event.type,
    title: eventTitle(event),
    detail: extractEventText(event.payload),
    technicalName: event.source,
    state: event.type === 'approval' || event.type === 'question' ? 'warning' : 'success',
  })), [events])
  const workPhase: BrowserWorkPhase = approvalEvent ? 'waiting' : runtime.activeRuns ? 'running' : runtime.ready ? 'idle' : runtime.phase === 'failed' ? 'failed' : 'paused'
  const browserApproval: BrowserApproval | null = approvalEvent ? {
    id: String(approvalEvent.payload.id || approvalEvent.payload.approvalId || approvalEvent.id),
    title: '员工准备执行外部操作',
    summary: extractEventText(approvalEvent.payload) || '请确认是否允许本次操作。',
  } : null

  useEffect(() => {
    if (!api || sideTab !== 'artifacts' || !runtime.ready) return
    void api.artifacts.list({ agentId: activeEmployeeId, limit: 4 }).then((result) => {
      const rows = Array.isArray(result.artifacts) ? result.artifacts : []
      setArtifacts(rows.map(asRecord))
    }).catch(() => setArtifacts([]))
  }, [api, sideTab, runtime.ready, activeEmployeeId])

  if (legacyMode) return <SuperAgent />

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden bg-[#0B0F1A] text-[#F1F5F9]">
      <aside className="flex w-[250px] shrink-0 flex-col border-r border-[#1E293B] bg-[#0D1320]">
        <div className="border-b border-[#1E293B] px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold"><Users className="h-4 w-4 text-[#818CF8]" />{t("员工名册")}</div>
              <div className="mt-1 text-xs text-[#64748B]">{t("每位员工拥有独立记忆与工作区")}</div>
            </div>
            <button onClick={() => setCreatingEmployee(true)} className="rounded-lg border border-[#273449] p-2 text-[#94A3B8] hover:border-[#6366F1] hover:text-white" title={t("新建员工")}><Plus className="h-4 w-4" /></button>
          </div>
        </div>

        {creatingEmployee && (
          <div className="m-3 space-y-2 rounded-xl border border-[#334155] bg-[#111827] p-3">
            <input value={newEmployeeName} onChange={(event) => setNewEmployeeName(event.target.value)} placeholder={t("员工名称")} className="w-full rounded-lg border border-[#273449] bg-[#0B0F1A] px-3 py-2 text-sm outline-none focus:border-[#6366F1]" />
            <input value={newEmployeeTitle} onChange={(event) => setNewEmployeeTitle(event.target.value)} placeholder={t("职位，如内容负责人")} className="w-full rounded-lg border border-[#273449] bg-[#0B0F1A] px-3 py-2 text-sm outline-none focus:border-[#6366F1]" />
            <div className="flex gap-2">
              <button onClick={() => void createEmployee()} className="flex-1 rounded-lg bg-[#6366F1] px-3 py-2 text-xs font-medium">{t("创建")}</button>
              <button onClick={() => setCreatingEmployee(false)} className="rounded-lg border border-[#273449] px-3 py-2 text-xs text-[#94A3B8]">{t("取消")}</button>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-2">
          {employees.map((employee) => (
            <button
              key={employee.id}
              onClick={() => {
                setActiveEmployeeId(employee.id)
                const first = sessions.find((item) => item.agentId === employee.id)
                setActiveSessionKey(first?.key || '')
              }}
              className={`mb-1 w-full rounded-xl border px-3 py-3 text-left transition ${activeEmployee?.id === employee.id ? 'border-[#4F46E5] bg-[#312E81]/25' : 'border-transparent hover:border-[#273449] hover:bg-[#111827]'}`}
            >
              <div className="flex items-center gap-3">
                <div className="grid h-9 w-9 place-items-center rounded-xl bg-[#1E293B] text-lg">{employee.emoji}</div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{employeeDisplayName(employee.name)}</div>
                  <div className="mt-0.5 truncate text-xs text-[#64748B]">{t(employee.title)}</div>
                </div>
                <span className={`h-2 w-2 rounded-full ${employee.status === 'working' ? 'bg-[#F59E0B]' : 'bg-[#10B981]'}`} />
              </div>
            </button>
          ))}
          {employees.length === 0 && runtime.ready && <div className="px-4 py-8 text-center text-xs text-[#64748B]">{t("正在准备首位数字员工…")}</div>}
        </div>

        <div className="border-t border-[#1E293B] p-3">
          <div className="flex items-center gap-2 rounded-lg bg-[#111827] px-3 py-2 text-xs">
            <span className={`h-2 w-2 rounded-full ${runtime.ready ? 'bg-[#10B981]' : runtime.phase === 'failed' || runtime.phase === 'unavailable' ? 'bg-[#EF4444]' : 'bg-[#F59E0B]'}`} />
            <span className="flex-1 text-[#94A3B8]">{t("小妤工作状态")}</span>
            <span>{runtime.activeRuns ? t('工作中') : statusLabels[runtime.phase || ''] || runtime.phase}</span>
          </div>
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-4 border-b border-[#1E293B] px-5">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] text-xl">{activeEmployee?.emoji || '✨'}</div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2"><h1 className="truncate text-base font-semibold">{employeeDisplayName(activeEmployee?.name)}</h1><span className="rounded-full bg-[#1E293B] px-2 py-0.5 text-[11px] text-[#94A3B8]">{t(activeEmployee?.title || '数字员工')}</span></div>
            <div className="mt-0.5 text-xs text-[#64748B]">{activeSession?.label || '选择或创建一个任务对话'}</div>
          </div>
          <button onClick={() => { setRoutinePanelOpen(true); void loadRoutines() }} disabled={!runtime.ready} className="relative inline-flex items-center gap-2 rounded-lg border border-[#273449] px-3 py-2 text-xs text-[#CBD5E1] hover:border-[#6366F1] disabled:opacity-40">
            {runningRoutines.length ? <LoaderCircle className="h-4 w-4 animate-spin text-[#A5B4FC]" /> : <Clock3 className="h-4 w-4" />}
            {t("后台任务")}
            <span className={`min-w-5 rounded-full px-1.5 py-0.5 text-[10px] ${runningRoutines.length ? 'bg-[#4F46E5] text-white' : 'bg-[#1E293B] text-[#94A3B8]'}`}>{runningRoutines.length}</span>
          </button>
          <button onClick={() => void createSession()} disabled={!runtime.ready} className="inline-flex items-center gap-2 rounded-lg border border-[#273449] px-3 py-2 text-xs text-[#CBD5E1] hover:border-[#6366F1] disabled:opacity-40"><MessageSquarePlus className="h-4 w-4" />{t("新任务")}</button>
          <button onClick={() => setBrowserOpen(true)} className="inline-flex items-center gap-2 rounded-lg border border-[#273449] px-3 py-2 text-xs text-[#CBD5E1] hover:border-[#6366F1]"><Laptop className="h-4 w-4" />{t("工作电脑")}</button>
        </header>

        {!runtime.ready && (
          <div className={`m-4 flex items-start gap-3 rounded-xl border p-4 ${runtime.phase === 'failed' || runtime.phase === 'unavailable' ? 'border-[#7C2D12] bg-[#431407]/35' : 'border-[#1E3A5F] bg-[#0C2A42]/35'}`}>
            {runtime.phase === 'starting' || runtime.phase === 'repairing' || runtime.phase === 'reconnecting' || runtime.phase === 'stopped' ? <LoaderCircle className="mt-0.5 h-5 w-5 animate-spin text-[#60A5FA]" /> : <CircleAlert className="mt-0.5 h-5 w-5 text-[#FB7185]" />}
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{runtime.phase === 'failed' || runtime.phase === 'unavailable' ? t("小妤暂时无法开始工作") : t("小妤正在准备工作环境")}</div>
              <div className={`mt-1 text-xs ${runtime.phase === 'failed' || runtime.phase === 'unavailable' ? 'text-[#FDA4AF]' : 'text-[#93C5FD]'}`}>{runtime.phase === 'failed' || runtime.phase === 'unavailable' ? t("工作环境正在恢复，你也可以立即重试。") : t("正在加载技能和工作区，很快就好。")}</div>
            </div>
            {(runtime.phase === 'failed' || runtime.phase === 'unavailable') && <button onClick={() => void api?.runtime.restart().catch((reason) => setError(userFacingError(reason)))} className="rounded-lg border border-[#7C2D12] p-2" title={t("重试")}><RefreshCw className="h-4 w-4" /></button>}
          </div>
        )}

        {error && <div className="mx-4 mt-3 flex items-center gap-2 rounded-lg border border-[#7F1D1D] bg-[#450A0A]/40 px-3 py-2 text-xs text-[#FCA5A5]"><CircleAlert className="h-4 w-4" /><span className="flex-1">{error}</span><button onClick={() => setError('')}><X className="h-4 w-4" /></button></div>}

        <div className="flex min-h-0 flex-1">
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {messages.length === 0 ? (
                <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center text-center">
                  <div className="mb-5 grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-[#4F46E5]/35 to-[#7C3AED]/20"><Sparkles className="h-8 w-8 text-[#A5B4FC]" /></div>
                  <h2 className="text-xl font-semibold">{t("把一项工作交给{v0}", { v0: employeeDisplayName(activeEmployee?.name) })}</h2>
                  <p className="mt-2 text-sm leading-6 text-[#64748B]">{t("员工会读取所需技能、检查前置条件，并在发布或其他不可逆操作前等待你的确认。")}</p>
                </div>
              ) : (
                <div className="mx-auto max-w-3xl space-y-5">
                  {messages.map((message) => (
                    <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[82%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'rounded-br-md bg-[#4F46E5] text-white' : 'rounded-bl-md border border-[#273449] bg-[#111827] text-[#E2E8F0]'}`}>{message.text}</div>
                    </div>
                  ))}
                  {sending && <div className="flex items-center gap-2 text-xs text-[#818CF8]"><LoaderCircle className="h-4 w-4 animate-spin" />{t("员工正在处理…")}</div>}
                </div>
              )}
            </div>

            {approvalEvent && (
              <div className="mx-5 mb-3 rounded-xl border border-[#92400E] bg-[#451A03]/60 p-4">
                <div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 text-[#FBBF24]" /><div className="flex-1"><div className="text-sm font-medium">{t("需要你的确认")}</div><div className="mt-1 text-xs text-[#FDE68A]">{extractEventText(approvalEvent.payload) || t("员工准备执行会影响真实业务状态的操作。")}</div></div></div>
                <div className="mt-3 flex justify-end gap-2"><button onClick={() => void resolveApproval(approvalEvent, 'deny')} className="rounded-lg border border-[#78350F] px-3 py-2 text-xs">{t("取消")}</button><button onClick={() => void resolveApproval(approvalEvent, 'allow-once')} className="rounded-lg bg-[#D97706] px-3 py-2 text-xs font-medium text-white">{t("仅本次允许")}</button></div>
              </div>
            )}

            {questionEvent && (
              <div className="mx-5 mb-3 rounded-xl border border-[#3730A3] bg-[#1E1B4B]/55 p-4">
                <div className="flex items-start gap-3"><CircleAlert className="mt-0.5 h-5 w-5 text-[#A5B4FC]" /><div className="flex-1"><div className="text-sm font-medium">{t("员工需要补充信息")}</div><div className="mt-1 text-xs text-[#C7D2FE]">{extractEventText(questionEvent.payload) || t("请补充缺少的信息，员工会从暂停处继续。")}</div></div></div>
                <div className="mt-3 flex gap-2"><input value={questionAnswer} onChange={(event) => setQuestionAnswer(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void answerQuestion() }} className="min-w-0 flex-1 rounded-lg border border-[#3730A3] bg-[#0B0F1A] px-3 py-2 text-xs outline-none focus:border-[#6366F1]" placeholder={t("输入回答")} /><button onClick={() => void answerQuestion()} className="rounded-lg bg-[#4F46E5] px-3 py-2 text-xs font-medium">{t("继续")}</button></div>
              </div>
            )}

            <div className="border-t border-[#1E293B] bg-[#0D1320]/90 p-4">
              <div className="mx-auto max-w-3xl rounded-2xl border border-[#273449] bg-[#111827] p-3 focus-within:border-[#6366F1]">
                <div className="flex items-end gap-3">
                  <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendMessage() } }} rows={2} placeholder={t("交代目标、资料和完成标准…")} disabled={!runtime.ready || !activeEmployee} className="max-h-40 min-h-[48px] flex-1 resize-none bg-transparent px-1 py-2 text-sm outline-none placeholder:text-[#475569] disabled:opacity-50" />
                  {sending ? <button onClick={() => void api?.runs.interrupt({ key: activeSessionKey, agentId: activeEmployeeId })} className="grid h-10 w-10 place-items-center rounded-xl bg-[#334155]" title={t("停止")}><Pause className="h-4 w-4" /></button> : <button onClick={() => void sendMessage()} disabled={!input.trim() || !runtime.ready || !activeEmployee} className="grid h-10 w-10 place-items-center rounded-xl bg-[#6366F1] disabled:bg-[#273449]" title={t("发送")}><Send className="h-4 w-4" /></button>}
                </div>
                <div className="mt-2 flex items-center justify-between border-t border-[#1E293B] pt-2">
                  <button
                    type="button"
                    aria-pressed={deepThinking}
                    onClick={() => setDeepThinking((current) => !current)}
                    disabled={sending}
                    className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[11px] transition disabled:opacity-50 ${deepThinking ? 'border-[#6366F1] bg-[#312E81]/45 text-[#C7D2FE]' : 'border-[#273449] text-[#64748B] hover:text-[#CBD5E1]'}`}
                    title={t("开启后会使用推理模型，适合复杂规划和分析，并消耗更多 Credits。")}
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    {t("深度思考")}
                    <span className={`h-1.5 w-1.5 rounded-full ${deepThinking ? 'bg-[#818CF8]' : 'bg-[#475569]'}`} />
                    {deepThinking ? t("已开启") : t("已关闭")}
                  </button>
                  <span className="text-[10px] text-[#475569]">{deepThinking ? t("复杂任务模式 · 消耗更多 Credits") : t("普通模式 · 更快且更节省")}</span>
                </div>
              </div>
            </div>
          </div>

          <aside className="hidden w-[310px] shrink-0 border-l border-[#1E293B] bg-[#0D1320] xl:flex xl:flex-col">
            <div className="flex border-b border-[#1E293B] p-2">
              {([
                ['activity', '动态', Clock3],
                ['routines', '例程', Play],
                ['artifacts', '产物', FileBox],
              ] as const).map(([id, label, Icon]) => <button key={id} onClick={() => setSideTab(id)} className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs ${sideTab === id ? 'bg-[#1E293B] text-white' : 'text-[#64748B]'}`}><Icon className="h-3.5 w-3.5" />{t(label)}{id === 'routines' && runningRoutines.length > 0 && <span className="rounded-full bg-[#4F46E5] px-1.5 text-[9px] text-white">{runningRoutines.length}</span>}</button>)}
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {sideTab === 'activity' && (events.length ? events.slice(0, 50).map((event) => <div key={event.id} className="mb-2 rounded-xl border border-[#1E293B] bg-[#111827] p-3"><div className="flex items-center gap-2 text-xs font-medium"><span className={`h-2 w-2 rounded-full ${event.type === 'approval' || event.type === 'question' ? 'bg-[#F59E0B]' : 'bg-[#6366F1]'}`} />{eventTitle(event)}</div><div className="mt-1 line-clamp-3 text-[11px] leading-5 text-[#64748B]">{extractEventText(event.payload) || event.source}</div></div>) : <EmptySide icon={Clock3} text="暂无工作动态" />)}
              {sideTab === 'routines' && (routines.length ? <div className="space-y-2">{routines.map((routine, index) => <RoutineCard key={String(routine.id || index)} routine={routine} onPause={(item) => void pauseRoutine(item)} onRun={(item) => void runRoutine(item)} />)}</div> : <EmptySide icon={Play} text="暂无后台任务" />)}
              {sideTab === 'artifacts' && (artifacts.length ? artifacts.map((artifact, index) => <div key={String(artifact.id || index)} className="mb-2 rounded-xl border border-[#1E293B] bg-[#111827] p-3"><div className="flex items-center gap-2 text-xs font-medium"><FileBox className="h-3.5 w-3.5 text-[#2DD4A8]" />{String(artifact.title || artifact.name || '工作产物')}</div><div className="mt-1 text-[11px] text-[#64748B]">{String(artifact.mimeType || artifact.type || '文件')}</div></div>) : <EmptySide icon={FileBox} text="暂无产物" />)}
            </div>
            <div className="border-t border-[#1E293B] p-3">
              <div className="mb-2 flex items-center justify-between text-xs text-[#64748B]"><span>{t("最近对话")}</span><button onClick={() => void createSession()}><Plus className="h-4 w-4" /></button></div>
              {filteredSessions.slice(0, 5).map((session) => <button key={session.key} onClick={() => { setError(''); setActiveSessionKey(session.key) }} className={`mb-1 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs ${activeSessionKey === session.key ? 'bg-[#1E293B]' : 'hover:bg-[#111827]'}`}><span className="min-w-0 flex-1 truncate">{session.label}</span>{session.hasActiveRun && <LoaderCircle className="h-3 w-3 animate-spin text-[#818CF8]" />}<ChevronRight className="h-3 w-3 text-[#475569]" /></button>)}
            </div>
          </aside>
        </div>
      </section>

      {routinePanelOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#020617]/75 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) setRoutinePanelOpen(false) }}>
          <section className="flex max-h-[82vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-[#273449] bg-[#0D1320] shadow-2xl shadow-black/50">
            <header className="flex items-center gap-3 border-b border-[#1E293B] px-5 py-4">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#312E81]/45 text-[#A5B4FC]"><Clock3 className="h-5 w-5" /></div>
              <div className="min-w-0 flex-1">
                <h2 className="text-sm font-semibold">{t("后台任务")}</h2>
                <p className="mt-0.5 text-xs text-[#64748B]">{runningRoutines.length ? t("当前有 {v0} 个任务正在运行", { v0: runningRoutines.length }) : t("当前没有正在运行的后台任务")}</p>
              </div>
              <button onClick={() => void loadRoutines()} disabled={routinesLoading} className="rounded-lg border border-[#273449] p-2 text-[#94A3B8] hover:border-[#6366F1] disabled:opacity-40" title={t("刷新")}><RefreshCw className={`h-4 w-4 ${routinesLoading ? 'animate-spin' : ''}`} /></button>
              <button onClick={() => setRoutinePanelOpen(false)} className="rounded-lg border border-[#273449] p-2 text-[#94A3B8] hover:border-[#6366F1]" title={t("关闭")}><X className="h-4 w-4" /></button>
            </header>
            <div className="border-b border-[#1E293B] bg-[#0B0F1A]/55 px-5 py-3 text-[11px] leading-5 text-[#64748B]">
              {t("定时任务只会在小妤运行期间执行。关闭应用期间错过的周期任务不会在下次启动时集中补跑。")}
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {routines.length ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {[...routines].sort((left, right) => Number(routineState(right).running) - Number(routineState(left).running)).map((routine, index) => (
                    <RoutineCard key={String(routine.id || index)} routine={routine} onPause={(item) => void pauseRoutine(item)} onRun={(item) => void runRoutine(item)} />
                  ))}
                </div>
              ) : routinesLoading ? (
                <div className="flex items-center justify-center gap-2 py-16 text-xs text-[#64748B]"><LoaderCircle className="h-4 w-4 animate-spin" />{t("正在读取后台任务…")}</div>
              ) : (
                <EmptySide icon={Clock3} text={t("暂无后台任务")} />
              )}
            </div>
          </section>
        </div>
      )}

      <BrowserWorkView
        open={browserOpen}
        pageActive
        taskTitle={activeSession?.label || '员工工作电脑'}
        result=""
        status={runtime.ready ? '本地工作电脑已连接' : '运行内核尚未就绪'}
        phase={workPhase}
        events={workEvents}
        approval={browserApproval}
        paused={false}
        busy={Boolean(runtime.activeRuns)}
        onClose={() => setBrowserOpen(false)}
        onTakeover={() => void api?.computer.takeover({ agentId: activeEmployeeId })}
        onResume={() => void api?.computer.returnControl({ agentId: activeEmployeeId })}
        onStop={() => void api?.runs.interrupt({ key: activeSessionKey, agentId: activeEmployeeId })}
        onApproval={(decision) => { if (approvalEvent) void resolveApproval(approvalEvent, decision === 'approve_once' ? 'allow-once' : 'deny') }}
      />
    </div>
  )
}

function EmptySide({ icon: Icon, text }: { icon: typeof Archive; text: string }) {
  return <div className="flex flex-col items-center py-12 text-center text-xs text-[#475569]"><Icon className="mb-3 h-7 w-7" /><span>{text}</span></div>
}
