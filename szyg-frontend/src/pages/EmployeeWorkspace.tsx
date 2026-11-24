import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type SetStateAction } from 'react'
import {
  Archive,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileBox,
  LoaderCircle,
  Ellipsis,
  MessageSquare,
  Pause,
  Play,
  Plus,
  RefreshCw,
  PanelRight,
  ShieldCheck,
  X,
} from 'lucide-react'
import EmployeeActionsMenu from '@/components/employees/EmployeeActionsMenu'
import { EmployeeMediaMessage, DirectorRuntimeInfo, type EmployeeAsset } from '@/components/employees/DirectorMedia'
import DirectorRenderStatus, { useDirectorRenders } from '@/components/employees/DirectorRenderStatus'
import { useConversationRuns } from '@/components/employees/useConversationRuns'
import EmployeeComposer from '@/components/employees/EmployeeComposer'
import { useConversationExperts } from '@/lib/useConversationExperts'
import RobotAvatar, { defaultRobotPreset, XIAOYU_AVATAR } from '@/components/ui/RobotAvatar'
import { EmployeeEditor, EmployeeModal, employeeModelUnavailableReason, useEmployeeModels, type AccessMode, type EmployeeProfile } from '@/components/employees/EmployeeEditor'
import SuperAgent from './SuperAgent'
import BrowserWorkView, {
  type BrowserApproval,
  type BrowserWorkEvent,
  type BrowserWorkPhase,
} from '@/components/superagent/BrowserWorkView'
import { translateCurrent, useI18n } from '@/lib/i18n'
import { useKeepAlivePageActive } from '@/lib/hooks'

type RuntimeStatus = {
  phase?: string
  available?: boolean
  ready?: boolean
  version?: string
  error?: string
  activeRuns?: number
}

type Employee = EmployeeProfile & {
  id: string
  agentId: string
  name: string
  primary: boolean
  title: string
  status: string
  archived: boolean
}

const DIRECTOR_ID = 'xiaoyu-director'
const SESSION_PAGE_SIZE = 100
const primaryChatPreference = (id: string) => 'xiaoyu.primary-chat.' + id

function readPrimaryChat(id: string) {
  try { return localStorage.getItem(primaryChatPreference(id)) || '' } catch { return '' }
}

function rememberPrimaryChat(id: string, key: string) {
  try { localStorage.setItem(primaryChatPreference(id), key) } catch { /* Storage can be disabled. */ }
}

function canBePrimaryChat(session: Session, id: string) {
  return session.agentId === id && session.canConfigure === true && !session.archived &&
    /^agent:[a-z0-9_-]+:dashboard:[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(session.key)
}

function canOpenEmployeeDetails(employee: Employee) {
  return !employee.primary && employee.id !== 'main' && employee.id !== DIRECTOR_ID
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
  canConfigure?: boolean
  archived?: boolean
  model?: string
  permissionMode?: AccessMode
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

const emptyMessages: Message[] = []
const terminalRunStates = new Set(['completed', 'failed', 'cancelled'])
type DraftSend = {message: Message; matchingMessages: number}
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
  const message = (reason instanceof Error ? reason.message : String(reason || '')).replace(/^Error invoking remote method '[^']+':\s*(?:Error:\s*)?/, '')
  if (/credits?.*(余额不足|insufficient)|余额不足|billing error|auth\/billing failure|balance and usage limits/i.test(message)) {
    return translateCurrent('Credits 余额不足，请充值后重试。')
  }
  if (/too many requests|请求较多|rate.?limit/i.test(message)) {
    return translateCurrent('当前请求较多，请稍后重试。')
  }
  if (/gateway (?:unavailable|closed|disconnected)|runtime (?:unavailable|stopped)|econn|timed?\s*out|not ready|not initialized|route-compatible authentication source|authentication source.*openai/i.test(message)) {
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

function accessMode(value: unknown): AccessMode | undefined {
  return value === 'full' || value === 'guarded' || value === 'read-only' || value === 'workspace' ? value : undefined
}

function modelChoice(value: unknown): string | undefined {
  const id = typeof value === 'string' ? value.replace(/^xiaoyu-managed\//, '') : ''
  return !id || id.startsWith('text.') ? undefined : id
}

function normalizeEmployees(result: Record<string, unknown>): Employee[] {
  const rows = Array.isArray(result.agents) ? result.agents : []
  return rows.map((value) => {
    const row = asRecord(value)
    const agentId = String(row.agentId || row.id || '')
    const primary = agentId === (result.defaultId || 'main')
    return {
      id: agentId,
      agentId,
      name: String(row.name || row.displayName || (primary ? '小妤' : '数字员工')),
      primary,
      title: String(row.title || ''),
      status: row.hasActiveRun ? 'working' : 'idle',
      archived: Boolean(row.archived),
      instructions: typeof row.instructions === 'string' ? row.instructions : '',
      avatar: typeof row.avatar === 'string' ? row.avatar : '',
      model: modelChoice(row.model) || 'auto',
      permissionMode: accessMode(asRecord(row.toolPolicy).permissionMode) || 'guarded',
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
      agentId: String(row.agentId || String(row.key || row.sessionKey || '').match(/^agent:([^:]+):/)?.[1] || ''),
      model: modelChoice(row.model),
      canConfigure: row.canConfigure !== false,
      archived: row.archived === true || Boolean(row.archivedAt),
      permissionMode: accessMode(row.permissionMode),
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

function eventMatches(event: TimelineEvent, employeeId: string, sessionKey: string) {
  const {payload} = event
  const context = [payload, asRecord(payload.request), asRecord(payload.data), asRecord(payload.context)]
  const key = context.find(row => typeof row.sessionKey === 'string' && row.sessionKey)?.sessionKey
  const owner = context.find(row => typeof row.agentId === 'string' && row.agentId)?.agentId
  if (key) return key === sessionKey && (!owner || owner === employeeId)
  return Boolean(owner && owner === employeeId && (event.type === 'routine' || event.type === 'computer'))
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
    <div className={`rounded-xl border p-3 ${state.running ? 'border-[#4F46E5] bg-accent-soft/20' : 'border-border bg-card'}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${state.running ? 'bg-[#4F46E5]/25 text-accent-ink' : 'bg-muted text-muted-foreground'}`}>
          {state.running ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Clock3 className="h-4 w-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-xs font-medium">{String(routine.displayName || routine.name || translateCurrent('未命名后台任务'))}</div>
          <div className={`mt-1 text-[11px] ${state.running ? 'text-accent-ink' : state.lastRunStatus === 'error' ? 'text-danger-ink' : 'text-muted-foreground'}`}>{status}</div>
        </div>
        <button onClick={() => onPause(routine)} className="rounded-lg border border-border p-2 text-muted-foreground hover:border-[#6366F1]" title={translateCurrent(disabled ? '恢复定时任务' : '暂停定时任务')}>
          {disabled ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
        </button>
      </div>
      <div className="mt-3 grid grid-cols-[72px_1fr] gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
        <span>{translateCurrent('触发计划')}</span><span className="truncate text-muted-foreground">{routineScheduleLabel(routine)}</span>
        <span>{translateCurrent(state.running ? '开始时间' : '下次运行')}</span><span className="text-muted-foreground">{formatRoutineTime(state.running ? state.runningAtMs : state.nextRunAtMs)}</span>
        {state.lastRunAtMs > 0 && <><span>{translateCurrent('上次运行')}</span><span className="text-muted-foreground">{formatRoutineTime(state.lastRunAtMs)}</span></>}
      </div>
      {state.lastError && <div className="mt-2 line-clamp-2 rounded-lg bg-danger-soft/35 px-2 py-1.5 text-[10px] text-danger-ink">{state.lastError}</div>}
      <div className="mt-3 flex justify-end">
        <button onClick={() => onRun(routine)} disabled={state.running} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-[11px] text-foreground hover:border-[#6366F1] disabled:cursor-not-allowed disabled:opacity-40"><Play className="h-3 w-3" />{translateCurrent('立即运行')}</button>
      </div>
    </div>
  )
}

export default function EmployeeWorkspace() {
  const { t } = useI18n()
  const api = window.electronAPI?.openClaw
  const legacyMode = !api
  const pageActive = useKeepAlivePageActive()
  const modelCatalog = useEmployeeModels()
  const [runtime, setRuntime] = useState<RuntimeStatus>({ phase: 'starting' })
  const [employees, setEmployees] = useState<Employee[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeEmployeeId, setActiveEmployeeId] = useState('')
  const [activeSessionKey, setActiveSessionKey] = useState('')
  const [openingEmployeeId, setOpeningEmployeeId] = useState('')
  const [listedSession, setListedSession] = useState<Session>()
  const [historyEmployee, setHistoryEmployee] = useState<Employee>()
  const [historyRows, setHistoryRows] = useState<Session[]>([])
  const [historyNext, setHistoryNext] = useState<number>()
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const historyRequest = useRef(0)
  const [histories, setHistories] = useState<Record<string, Message[]>>({})
  const historyReads = useRef(new Map<string, object>())
  const [outbound, setOutbound] = useState<Record<string, DraftSend>>({})
  const dispatching = useRef(new Set<string>())
  const [chatErrors, setChatErrors] = useState<Record<string, string>>({})
  const [allEvents, setEvents] = useState<TimelineEvent[]>([])
  const [chatDrafts, setChatDrafts] = useState<Record<string, string>>({})
  const [attachmentDrafts, setAttachmentDrafts] = useState<Record<string, EmployeeAsset[]>>({})
  const [openingChats, setOpeningChats] = useState<Set<string>>(() => new Set())
  const openingRef = useRef(new Set<string>())
  const navigationRevision = useRef(0)
  const [creatingEmployee, setCreatingEmployee] = useState(false)
  const [createRequestId, setCreateRequestId] = useState('')
  const [profileId, setProfileId] = useState('')
  const [employeeMenu, setEmployeeMenu] = useState<{ id: string; x: number; y: number; toolbar: boolean } | null>(null)
  const menuTrigger = useRef<HTMLButtonElement | null>(null)
  const [directorEngineOpen, setDirectorEngineOpen] = useState(false)
  const [avatarId, setAvatarId] = useState('')
  const [draftOptions, setDraftOptions] = useState<Record<string, { model?: string; permissionMode?: AccessMode }>>({})
  const [configuring, setConfiguring] = useState(false)
  const configuringRef = useRef(false)
  const initialSelection = useRef(false)
  const selectionRef = useRef({ employeeId: '', sessionKey: '' })
  const loadSequence = useRef(0)
  const [questionAnswer, setQuestionAnswer] = useState('')
  const [browserOpen, setBrowserOpen] = useState(false)
  const [routinePanelOpen, setRoutinePanelOpen] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [sideTab, setSideTab] = useState<'activity' | 'routines' | 'artifacts'>('activity')
  const [routines, setRoutines] = useState<Routine[]>([])
  const [routinesLoading, setRoutinesLoading] = useState(false)
  const [artifacts, setArtifacts] = useState<Record<string, unknown>[]>([])
  const [deepThinking, setDeepThinking] = useState(() => window.localStorage.getItem('xiaoyu.deepThinking') === 'true')
  const [error, setError] = useState('')
  const initializedDefaultRef = useRef(false)
  const historyTimerRef = useRef<number | null>(null)
  const chatScroll = useRef<HTMLDivElement>(null)
  const nearBottom = useRef(true)

  const activeEmployee = employees.find((item) => item.id === activeEmployeeId) || employees[0]
  const isDirector = activeEmployee?.id === DIRECTOR_ID
  const activeSession = sessions.find(item => item.key === activeSessionKey && item.agentId === activeEmployee?.id)
    || (listedSession?.key === activeSessionKey && listedSession.agentId === activeEmployee?.id ? listedSession : undefined)
  const isMainConversation = !activeSessionKey || readPrimaryChat(activeEmployee?.id || '') === activeSessionKey
  const draftKey = isMainConversation ? 'employee:' + (activeEmployee?.id || '') : activeSessionKey
  const input = chatDrafts[draftKey] || ''
  const attachments = attachmentDrafts[draftKey] || []
  const setInput = useCallback((action: SetStateAction<string>) => {
    setChatDrafts(current => ({...current, [draftKey]: typeof action === 'function' ? action(current[draftKey] || '') : action}))
  }, [draftKey])
  const setAttachments = useCallback((action: SetStateAction<EmployeeAsset[]>) => {
    setAttachmentDrafts(current => ({...current, [draftKey]: typeof action === 'function' ? action(current[draftKey] || []) : action}))
  }, [draftKey])
  const editedEmployee = employees.find(item => item.id === profileId && canOpenEmployeeDetails(item))
  const menuEmployee = employees.find(item => item.id === employeeMenu?.id)
  const employeeSelectionBusy = configuring || !!openingEmployeeId
  const avatarEmployee = employees.find(item => item.id === avatarId)
  const readOnlyHistory = Boolean(activeSession && (activeSession.canConfigure === false || activeSession.archived))
  const canConfigure = !activeSessionKey || (activeSession?.canConfigure === true && !readOnlyHistory)
  const events = useMemo(() => allEvents.filter(event => eventMatches(event,activeEmployeeId,activeSessionKey)), [allEvents,activeEmployeeId,activeSessionKey])
  const selectedOptions = activeSessionKey ? activeSession : draftOptions[activeEmployee?.id || '']
  const preferredModel = selectedOptions?.model || activeEmployee?.model || 'auto'
  const usingAutomaticModel = canConfigure && Boolean(employeeModelUnavailableReason(modelCatalog, preferredModel))
  const model = usingAutomaticModel ? 'auto' : preferredModel
  const fixedReasoning = model === 'kimi-k3-1-pro-261024'
  const useReasoning = fixedReasoning || deepThinking
  const permissionMode = selectedOptions?.permissionMode || activeEmployee?.permissionMode || 'guarded'
  selectionRef.current = { employeeId: activeEmployeeId, sessionKey: activeSessionKey }

  function employeeDisplayName(name?: string) {
    if (!name || name === '小妤') return t('小妤')
    return name === '视频导演' ? t('director.name') : name
  }

  const refreshHistory = useCallback(async (sessionKey: string, employeeId: string) => {
    if (!api || !sessionKey) return
    const request = {}
    historyReads.current.set(sessionKey, request)
    try {
      const result = await api.sessions.history({ sessionKey, agentId: employeeId, limit: 200, maxChars: 12000 })
      if (historyReads.current.get(sessionKey) !== request) return
      setHistories(current => ({...current, [sessionKey]: normalizeHistory(result)}))
    } catch (reason) {
      if (historyReads.current.get(sessionKey) === request && selectionRef.current.sessionKey === sessionKey) {
        setError(userFacingError(reason))
      }
    } finally {
      if (historyReads.current.get(sessionKey) === request) historyReads.current.delete(sessionKey)
    }
  }, [api])

  const {runs,admit,onEvent:observeRun,stop} = useConversationRuns(api,Boolean(runtime.ready),activeSessionKey,activeEmployeeId,refreshHistory)
  const currentRun = runs[activeSessionKey]
  const sending = Boolean(outbound[draftKey] || currentRun)
  const opening = openingChats.has(activeEmployeeId)
  const recorded = histories[activeSessionKey] || emptyMessages
  const pending = outbound[draftKey]
  const messages = pending && recorded.filter(row => row.role === 'user' && row.text === pending.message.text).length <= pending.matchingMessages
    ? [...recorded, pending.message] : recorded
  const renderJobs = useDirectorRenders(api,activeSessionKey,activeEmployeeId,isDirector && pageActive && Boolean(runtime.ready),sending)
  const renderCount = renderJobs.length
  const latestRenderState = renderJobs[0]?.status
  const messageCount = messages.length
  const lastMessage = messages.at(-1)?.text
  useLayoutEffect(() => { nearBottom.current = true }, [draftKey])
  useLayoutEffect(() => {
    if (nearBottom.current && chatScroll.current) chatScroll.current.scrollTop = chatScroll.current.scrollHeight
  }, [draftKey,messageCount,lastMessage,renderCount,latestRenderState,sending])
  const scopedError = chatErrors[activeSessionKey || draftKey] || chatErrors[draftKey]

  const stopCurrent = useCallback(async () => {
    try { await stop(activeSessionKey,activeEmployeeId) }
    catch (reason) {
      setChatErrors(current => ({...current,[activeSessionKey || draftKey]:userFacingError(reason)}))
    }
  }, [activeSessionKey,activeEmployeeId,draftKey,stop])

  const resolvePrimaryChat = useCallback(async (employeeId: string, recent: Session[]) => {
    const saved = readPrimaryChat(employeeId)
    const known = recent.filter(row => canBePrimaryChat(row, employeeId))
    let session = known.find(row => row.key === saved) || (!saved ? known[0] : undefined)
    if (!session && api) {
      // The initial cross-employee index is bounded. Search the employee's
      // own pages before considering a saved primary chat missing.
      let fallback = known[0]
      for (let offset = 0; ; offset += SESSION_PAGE_SIZE) {
        const raw = await api.sessions.list({agentId: employeeId, limit: SESSION_PAGE_SIZE, offset, excludeCron: true})
        const rows = normalizeSessions(raw)
        const eligible = rows.filter(row => canBePrimaryChat(row, employeeId))
        fallback ||= eligible[0]
        session = eligible.find(row => row.key === saved)
        const page = Array.isArray(raw.sessions) ? raw.sessions : Array.isArray(raw.items) ? raw.items : []
        if (session || (!saved && fallback) || page.length < SESSION_PAGE_SIZE) break
      }
      session ||= fallback
    }
    if (session) rememberPrimaryChat(employeeId, session.key)
    return session
  }, [api])

  const loadWorkspace = useCallback(async () => {
    if (!api) return
    const sequence = ++loadSequence.current
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
          emoji: '🤖',
          title: '首席数字员工',
          instructions: '理解目标、调度技能、在关键节点等待确认，并用结构化报告交付结果。',
          toolPolicy: { permissionMode: 'guarded' },
        })
        nextEmployees = normalizeEmployees(await api.bots.list())
      }
      if (sequence !== loadSequence.current) return
      setEmployees(nextEmployees)
      const nextSessions = normalizeSessions(sessionResult)
      setSessions(nextSessions)
      if (!initialSelection.current && nextEmployees.length) {
        const first = nextEmployees.find(employee => employee.primary) || nextEmployees[0]
        const session = await resolvePrimaryChat(first.id, nextSessions)
        if (sequence !== loadSequence.current || initialSelection.current) return
        initialSelection.current = true
        setActiveEmployeeId(first.id)
        setListedSession(session)
        setActiveSessionKey(session?.key || '')
      }
    } catch (reason) {
      setError(userFacingError(reason))
    }
  }, [api, resolvePrimaryChat])

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
      const relevantRun = observeRun(event)
      const sessionKey = typeof event.payload.sessionKey === 'string' ? event.payload.sessionKey : ''
      const runId = typeof event.payload.runId === 'string' ? event.payload.runId : ''
      const finished = terminalRunStates.has(String(event.payload.runStatus))
      if (sessionKey && relevantRun && event.payload.runStatus === 'failed') {
        setChatErrors(current => ({...current,[sessionKey]:userFacingError(eventError(event.payload))}))
      }
      setEvents(current => {
        const visible = finished && runId
          ? current.filter(item => !['approval','question'].includes(item.type) || item.payload.runId !== runId)
          : current
        const actionable = visible.filter(item => item.type === 'approval' || item.type === 'question')
        const activity = visible.filter(item => item.type !== 'approval' && item.type !== 'question')
        const other = activity.filter(item => item.payload.sessionKey !== sessionKey)
        const recent = activity.filter(item => item.payload.sessionKey === sessionKey)
        return [event as TimelineEvent, ...actionable, ...[...recent.slice(0,49), ...other].slice(0,450)]
      })
      const selection = selectionRef.current
      if (sessionKey && sessionKey === selection.sessionKey && !finished && (event.type === 'message' || event.type === 'session')) {
        if (historyTimerRef.current) window.clearTimeout(historyTimerRef.current)
        historyTimerRef.current = window.setTimeout(() => void refreshHistory(sessionKey,selection.employeeId), 180)
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
  }, [api, loadRoutines, loadWorkspace, refreshHistory, observeRun])

  useEffect(() => {
    if (activeSessionKey || !activeEmployeeId) return
    const selected = sessions.find(row => row.key === readPrimaryChat(activeEmployeeId) && canBePrimaryChat(row,activeEmployeeId))
    if (selected && selectionRef.current.employeeId === activeEmployeeId) {
      setListedSession(selected)
      setActiveSessionKey(selected.key)
    }
  }, [activeEmployeeId,activeSessionKey,sessions])

  useEffect(() => {
    setQuestionAnswer('')
    if (activeSessionKey) void refreshHistory(activeSessionKey, activeEmployeeId)
  }, [activeSessionKey, activeEmployeeId, refreshHistory])

  useEffect(() => {
    if (api && activeEmployeeId) void api.computer.status({ agentId: activeEmployeeId })
  }, [api, activeEmployeeId])

  const createConversation = useCallback(async (employee: Employee, primary: boolean, useDraftOptions = false) => {
    if (!api || !runtime.ready || openingRef.current.has(employee.id)) return null
    const navigation = navigationRevision.current
    openingRef.current.add(employee.id)
    setOpeningChats(new Set(openingRef.current))
    try {
      setError('')
      const session = await api.sessions.create({
        agentId: employee.agentId,
        label: `xiaoyu-${employee.agentId}-${Date.now()}`,
        displayName: t(primary ? 'employee.mainChat' : 'employee.newChat'),
        permissionMode: useDraftOptions ? permissionMode : employee.permissionMode,
        model: useDraftOptions ? preferredModel : employee.model,
        deepThinking: useDraftOptions ? useReasoning : deepThinking || employee.model === 'kimi-k3-1-pro-261024',
      })
      const key = String(session.key || session.sessionKey || session.id || '')
      if (key) {
        if (primary) rememberPrimaryChat(employee.id, key)
        const row: Session = {key, agentId:employee.id, label:t(primary ? 'employee.mainChat' : 'employee.newChat'),
          canConfigure:true, model:useDraftOptions ? preferredModel : employee.model,
          permissionMode:useDraftOptions ? permissionMode : employee.permissionMode}
        setSessions(current => current.some(item => item.key === key) ? current : [row,...current])
        if (navigationRevision.current === navigation) {
          setActiveEmployeeId(employee.id)
          setListedSession(row)
          setActiveSessionKey(key)
          setProfileId('')
        }
        void loadWorkspace()
      }
      return key
    } finally {
      openingRef.current.delete(employee.id)
      setOpeningChats(new Set(openingRef.current))
    }
  }, [api, runtime.ready, permissionMode, preferredModel, useReasoning, deepThinking, loadWorkspace, t])

  const createSession = useCallback(() => activeEmployee ? createConversation(activeEmployee, true, true) : Promise.resolve(null),
    [activeEmployee, createConversation])

  const experts = useConversationExperts({ agentId: activeEmployee?.id, sessionKey: activeSessionKey, createSession,
    disabled: legacyMode || !runtime.ready || readOnlyHistory })

  function sendMessage(draft: string) {
    const message = draft.trim()
    if (!api || !activeEmployee || activeEmployee.id !== activeEmployeeId || !canConfigure || !message ||
        sending || dispatching.current.has(draftKey) || openingRef.current.has(activeEmployeeId) || configuringRef.current) return false
    dispatching.current.add(draftKey)
    const pending: DraftSend = {
      message:{id:'local-' + crypto.randomUUID(),role:'user',text:message},
      matchingMessages:recorded.filter(item => item.role === 'user' && item.text === message).length,
    }
    setOutbound(current => ({...current,[draftKey]:pending}))
    setChatErrors(current => ({...current,[draftKey]:'',[activeSessionKey]:''}))
    setInput('')
    void (async () => {
      let sessionKey = activeSessionKey
      let admitted = false
      try {
        if (!sessionKey) sessionKey = await createSession() || ''
        if (!sessionKey) throw new Error(t('employee.waitReady'))
        const result = await api.runs.send({sessionKey,agentId:activeEmployee.id,message,deepThinking:useReasoning,usingAutomaticModel,
          attachments:attachments.map(asset => asset.url)})
        admitted = true
        admit(sessionKey,activeEmployee.id,result)
        await refreshHistory(sessionKey,activeEmployee.id)
      } catch (reason) {
        if (!admitted) {
          setInput(current => current || input)
          setAttachments(current => [...current, ...attachments.filter(asset => !current.some(item => item.url === asset.url))])
        }
        setChatErrors(current => ({...current,[sessionKey || draftKey]:userFacingError(reason)}))
      } finally {
        dispatching.current.delete(draftKey)
        setOutbound(current => {
          const next = {...current}
          delete next[draftKey]
          return next
        })
      }
    })()
    return true
  }

  async function saveProfile(draft: EmployeeProfile, employee?: Employee, avatarOnly = false, original?: EmployeeProfile) {
    if (!api) throw new Error(t('employee.waitReady'))
    try {
      if (avatarOnly && employee) {
        await api.bots.update({agentId:employee.id, avatar:draft.avatar})
      } else {
        const payload = {name:draft.name, title:draft.title, instructions:draft.instructions, avatar:draft.avatar,
          model:draft.model, toolPolicy:{permissionMode:draft.permissionMode}}
        if (employee) {
          const changes: Record<string, unknown> = {}
          for (const key of ['name','title','instructions','avatar','model'] as const) {
            if (draft[key] !== original?.[key]) changes[key] = draft[key]
          }
          if (draft.permissionMode !== original?.permissionMode) changes.toolPolicy = {permissionMode:draft.permissionMode}
          if (Object.keys(changes).length) await api.bots.update({...changes,agentId:employee.id})
        } else {
          const result = await api.bots.create({...payload,requestId:createRequestId})
          initialSelection.current = true
          const id = String(result.agentId || result.id || '')
          if (id) {
            setEmployees(current => [...current.filter(item => item.id !== id), {...draft,id,agentId:id,primary:false,status:'idle',archived:false}])
            setActiveEmployeeId(id)
          }
          setProfileId('')
          setActiveSessionKey('')
          setListedSession(undefined)
          navigationRevision.current++
        }
      }
      setError('')
      await loadWorkspace()
    } catch (reason) { throw new Error(userFacingError(reason)) }
  }

  const closeEmployeeMenu = useCallback((restoreFocus = false) => {
    if (restoreFocus) menuTrigger.current?.focus({ preventScroll: true })
    menuTrigger.current = null
    setEmployeeMenu(null)
  }, [])

  useEffect(() => {
    if (!pageActive || employeeSelectionBusy) closeEmployeeMenu()
  }, [pageActive, employeeSelectionBusy, closeEmployeeMenu])

  function openEmployeeMenu(id: string, trigger: HTMLButtonElement, point?: { x: number; y: number }, toolbar = false) {
    if (employeeSelectionBusy && !toolbar) return
    const bounds = trigger.getBoundingClientRect()
    menuTrigger.current = trigger
    const position = point && Number.isFinite(point.x) && Number.isFinite(point.y) && (point.x || point.y)
      ? point : { x: bounds.left, y: bounds.bottom + 4 }
    setEmployeeMenu({ id, ...position, toolbar })
  }

  function showConversation(employee: Employee, session?: Session) {
    navigationRevision.current++
    if (employee.id !== activeEmployeeId || (session?.key || '') !== activeSessionKey) {
      setActiveEmployeeId(employee.id)
      setListedSession(session)
      setActiveSessionKey(session?.key || '')
    }
    setError('')
    setProfileId('')
  }

  async function selectEmployee(employee: Employee) {
    if (employeeSelectionBusy) return
    const navigation = ++navigationRevision.current
    setOpeningEmployeeId(employee.id)
    try {
      const primary = await resolvePrimaryChat(employee.id, sessions)
      if (navigationRevision.current === navigation) showConversation(employee, primary)
    } catch (reason) {
      setError(userFacingError(reason))
    } finally {
      setOpeningEmployeeId('')
    }
  }

  function closeHistory() {
    historyRequest.current++
    setHistoryEmployee(undefined)
    setHistoryLoading(false)
  }

  async function loadHistory(employee: Employee, offset = 0) {
    if (!api) return
    const request = ++historyRequest.current
    setHistoryEmployee(employee)
    setHistoryLoading(true)
    setHistoryError('')
    if (!offset) { setHistoryRows([]); setHistoryNext(undefined) }
    try {
      const result = await api.sessions.list({agentId: employee.id, archived:'all', limit:SESSION_PAGE_SIZE, offset, excludeCron:true})
      if (request !== historyRequest.current) return
      const rows = normalizeSessions(result).filter(row => row.agentId === employee.id)
      const page = Array.isArray(result.sessions) ? result.sessions : Array.isArray(result.items) ? result.items : []
      setHistoryRows(current => offset ? [...current, ...rows.filter(row => !current.some(previous => previous.key === row.key))] : rows)
      setHistoryNext(page.length >= SESSION_PAGE_SIZE ? offset + page.length : undefined)
    } catch (reason) {
      if (request === historyRequest.current) setHistoryError(userFacingError(reason))
    } finally {
      if (request === historyRequest.current) setHistoryLoading(false)
    }
  }

  async function configureConversation(change: { model?: string; permissionMode?: AccessMode }) {
    if (!api || !activeEmployee || !canConfigure || configuringRef.current || openingRef.current.has(activeEmployeeId) || sending) return
    if (!activeSessionKey) {
      setDraftOptions(current => ({...current,[activeEmployee.id]:{...current[activeEmployee.id],...change}}))
      return
    }
    configuringRef.current = true
    setConfiguring(true); setError('')
    try {
      await api.sessions.configure({key:activeSessionKey,agentId:activeEmployee.id,...change})
      setSessions(current => current.map(item => item.key === activeSessionKey ? {...item,...change} : item))
      await loadWorkspace()
    } catch (reason) { setError(userFacingError(reason)) }
    finally { configuringRef.current = false; setConfiguring(false) }
  }

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
  const workPhase: BrowserWorkPhase = approvalEvent ? 'waiting' : sending ? 'running' : runtime.ready ? 'idle' : runtime.phase === 'failed' ? 'failed' : 'paused'
  const browserApproval: BrowserApproval | null = approvalEvent ? {
    id: String(approvalEvent.payload.id || approvalEvent.payload.approvalId || approvalEvent.id),
    title: '员工准备执行外部操作',
    summary: extractEventText(approvalEvent.payload) || '请确认是否允许本次操作。',
  } : null

  useEffect(() => {
    if (!detailsOpen || !api || sideTab !== 'artifacts' || !runtime.ready) return
    let mounted = true
    setArtifacts([])
    void api.artifacts.list({ agentId: activeEmployeeId, limit: 4 }).then((result) => {
      const rows = Array.isArray(result.artifacts) ? result.artifacts : []
      if (mounted) setArtifacts(rows.map(asRecord))
    }).catch(() => { if (mounted) setArtifacts([]) })
    return () => { mounted = false }
  }, [detailsOpen, api, sideTab, runtime.ready, activeEmployeeId])

  if (legacyMode) return <SuperAgent />

  return (
    <div className="employee-desk flex h-[calc(100dvh-4rem)] overflow-hidden bg-background text-foreground">
      <aside className="flex w-[clamp(164px,16vw,220px)] max-[480px]:w-28 shrink-0 flex-col border-r bg-muted/30">
        <div className="border-b border-border px-4 py-4 max-[480px]:px-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">{t("员工名册")}</h2>
            <button disabled={sending || opening || configuring} onClick={() => { setCreateRequestId(crypto.randomUUID()); setCreatingEmployee(true) }} className="rounded-lg border border-border p-2 text-muted-foreground hover:border-[#6366F1] hover:text-foreground" title={t("新建员工")}><Plus className="h-4 w-4" /></button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {employees.map((employee) => (
            <button key={employee.id} type="button" disabled={employeeSelectionBusy}
              aria-pressed={activeEmployee?.id === employee.id} aria-haspopup="menu" aria-keyshortcuts="Shift+F10"
              aria-expanded={employeeMenu?.id === employee.id} onClick={() => void selectEmployee(employee)}
              onContextMenu={event => {
                event.preventDefault()
                openEmployeeMenu(employee.id, event.currentTarget, { x: event.clientX, y: event.clientY })
              }}
              onKeyDown={event => {
                if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) {
                  event.preventDefault()
                  openEmployeeMenu(employee.id, event.currentTarget)
                }
              }}
              className={'mb-1 block w-full truncate rounded-lg px-3 py-2 text-left text-sm font-medium disabled:opacity-60 ' + (activeEmployee?.id === employee.id ? 'bg-muted' : 'hover:bg-card')}>
              {employeeDisplayName(employee.name)}
            </button>
          ))}
          {employees.length === 0 && runtime.ready && <div className="px-4 py-8 text-center text-xs text-muted-foreground">{t("正在准备首位数字员工…")}</div>}
        </div>

      </aside>

      {editedEmployee ? <EmployeeEditor catalog={modelCatalog} key={editedEmployee.id} mode="details" identity={editedEmployee.id} initial={editedEmployee}
        onSave={(draft, original) => saveProfile(draft,editedEmployee,false,original)} onClose={() => setProfileId('')} /> :
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-14 shrink-0 flex-wrap items-center gap-2 border-b px-3 py-2 lg:px-5">
          {activeEmployee && <button type="button" onClick={() => setAvatarId(activeEmployee.id)} aria-label={t('employee.avatarFor',{name:activeEmployee.name})} className="inline-flex rounded-xl hover:ring-2 hover:ring-ring">
            <RobotAvatar identity={activeEmployee.id} avatar={activeEmployee.avatar} primary={activeEmployee.primary} className="h-10 w-10 rounded-xl" /></button>}
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-semibold">{employeeDisplayName(activeEmployee?.name)}</h1>
            {!isMainConversation && <div className="truncate text-xs text-muted-foreground">{activeSession?.label}</div>}
          </div>
          <button type="button" aria-label={t("动态")} title={t("动态")} aria-expanded={detailsOpen} aria-controls="workspace-details"
            onClick={() => setDetailsOpen(!detailsOpen)} className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground">
            <PanelRight className="h-4 w-4" />
          </button>
          {activeEmployee && <button type="button" aria-label={t('employee.chatActions')} title={t('employee.chatActions')}
            aria-haspopup="menu" aria-expanded={employeeMenu?.toolbar === true}
            onClick={event => openEmployeeMenu(activeEmployee.id, event.currentTarget, undefined, true)}
            className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground">
            <Ellipsis className="h-5 w-5"/>
          </button>}
        </header>

        {!runtime.ready && (
          <div className={`m-4 flex items-start gap-3 rounded-xl border p-4 ${runtime.phase === 'failed' || runtime.phase === 'unavailable' ? 'border-danger-ink/35 bg-warning-soft/35' : 'border-info-ink/35 bg-info-soft/35'}`}>
            {runtime.phase === 'starting' || runtime.phase === 'repairing' || runtime.phase === 'reconnecting' || runtime.phase === 'stopped' ? <LoaderCircle className="mt-0.5 h-5 w-5 animate-spin text-info-ink" /> : <CircleAlert className="mt-0.5 h-5 w-5 text-danger-ink" />}
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{runtime.phase === 'failed' || runtime.phase === 'unavailable' ? t("小妤暂时无法开始工作") : t("小妤正在准备工作环境")}</div>
              <div className={`mt-1 text-xs ${runtime.phase === 'failed' || runtime.phase === 'unavailable' ? 'text-danger-ink' : 'text-info-ink'}`}>{runtime.phase === 'failed' || runtime.phase === 'unavailable' ? t("工作环境正在恢复，你也可以立即重试。") : t("正在加载技能和工作区，很快就好。")}</div>
            </div>
            {(runtime.phase === 'failed' || runtime.phase === 'unavailable') && <button onClick={() => void api?.runtime.restart().catch((reason) => setError(userFacingError(reason)))} className="rounded-lg border border-danger-ink/35 p-2" title={t("重试")}><RefreshCw className="h-4 w-4" /></button>}
          </div>
        )}

        {(error || scopedError) && <div role="alert" className="mx-4 mt-3 flex items-center gap-2 rounded-lg border border-danger-ink/35 bg-danger-soft/40 px-3 py-2 text-xs text-danger-ink"><CircleAlert className="h-4 w-4" /><span className="flex-1">{error || scopedError}</span><button aria-label={t('关闭')} onClick={() => {
          setError('')
          setChatErrors(current => ({...current,[draftKey]:'',[activeSessionKey]:''}))
        }}><X className="h-4 w-4" /></button></div>}

        <div className="relative flex min-h-0 flex-1">
          <div className="flex min-w-0 flex-1 flex-col">
            <div ref={chatScroll} onScroll={event => {
              const node = event.currentTarget
              nearBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80
            }} className="flex-1 overflow-y-auto px-4 py-6 lg:px-8">
              {messages.length === 0 && !sending && !renderJobs.length ? (
                <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center text-center">
                  {activeEmployee && <RobotAvatar identity={activeEmployee.id} primary={activeEmployee.primary}
                    avatar={activeEmployee.avatar} className="mb-4 h-14 w-14 rounded-2xl"/>}
                  <h2 className="text-xl font-medium tracking-tight">{t('employee.startConversation', {name: employeeDisplayName(activeEmployee?.name)})}</h2>
                  {isDirector && <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">{t('director.welcome')}</p>}
                </div>
              ) : (
                <div className="mx-auto max-w-3xl space-y-5">
                  {messages.map((message) => (
                    <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      {message.role === 'assistant' && activeEmployee && <button type="button" onClick={() => setAvatarId(activeEmployee.id)} className="mr-2 inline-flex h-7 shrink-0 rounded-lg hover:ring-2 hover:ring-ring" aria-label={t('employee.avatarFor',{name:activeEmployee.name})}>
                        <RobotAvatar identity={activeEmployee.id} primary={activeEmployee.primary} avatar={activeEmployee.avatar} className="h-7 w-7 rounded-lg"/></button>}
                      <div className={`min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere] text-[15px] leading-7 ${message.role === 'user' ? 'max-w-[86%] rounded-2xl bg-muted px-4 py-2' : 'w-full'}`}>
                        <EmployeeMediaMessage text={message.text}/>
                      </div>
                    </div>
                  ))}
                  {isDirector && <DirectorRenderStatus jobs={renderJobs}
                    delivered={url => messages.some(row => row.role === 'assistant' && row.text.includes(url))}/>}
                  {sending && !renderJobs.some(job => job.status === 'running') && <div role="status" className="flex items-center gap-2 text-xs text-accent-ink">
                    <LoaderCircle className="h-4 w-4 animate-spin" />{t(currentRun?.status === 'queued' ? 'employee.turnQueued' : '员工正在处理…')}
                  </div>}
                </div>
              )}
            </div>

            {approvalEvent && (
              <div className="mx-5 mb-3 rounded-xl border border-warning-ink/35 bg-warning-soft/60 p-4">
                <div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 text-warning-ink" /><div className="flex-1"><div className="text-sm font-medium">{t("需要你的确认")}</div><div className="mt-1 text-xs text-warning-ink">{extractEventText(approvalEvent.payload) || t("员工准备执行会影响真实业务状态的操作。")}</div></div></div>
                <div className="mt-3 flex justify-end gap-2"><button onClick={() => void resolveApproval(approvalEvent, 'deny')} className="rounded-lg border border-warning-ink/35 px-3 py-2 text-xs">{t("取消")}</button><button onClick={() => void resolveApproval(approvalEvent, 'allow-once')} className="rounded-lg bg-[#D97706] px-3 py-2 text-xs font-medium text-white">{t("仅本次允许")}</button></div>
              </div>
            )}

            {questionEvent && (
              <div className="mx-5 mb-3 rounded-xl border border-accent-ink/35 bg-accent-soft/55 p-4">
                <div className="flex items-start gap-3"><CircleAlert className="mt-0.5 h-5 w-5 text-accent-ink" /><div className="flex-1"><div className="text-sm font-medium">{t("员工需要补充信息")}</div><div className="mt-1 text-xs text-accent-ink">{extractEventText(questionEvent.payload) || t("请补充缺少的信息，员工会从暂停处继续。")}</div></div></div>
                <div className="mt-3 flex gap-2"><input value={questionAnswer} onChange={(event) => setQuestionAnswer(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void answerQuestion() }} className="min-w-0 flex-1 rounded-lg border border-accent-ink/35 bg-background px-3 py-2 text-xs outline-none focus:border-[#6366F1]" placeholder={t("输入回答")} /><button onClick={() => void answerQuestion()} className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground">{t("继续")}</button></div>
              </div>
            )}

            <EmployeeComposer key={draftKey}
              assets={attachments} onAssetsChange={setAttachments}
              value={input} onChange={setInput} onTranscribed={text => setInput(current => current ? current + ' ' + text : text)}
              director={isDirector} agentId={activeEmployeeId} sessionKey={activeSessionKey} createSession={createSession}
              onSend={sendMessage} onStop={canConfigure && currentRun?.runId ? () => void stopCurrent() : undefined}
              disabled={readOnlyHistory || !runtime.ready || !activeEmployeeId || !!openingEmployeeId}
              settingsDisabled={!canConfigure || configuring || opening || sending || !activeEmployee}
              sending={sending} readOnly={readOnlyHistory} access={permissionMode}
              onAccessChange={permissionMode => void configureConversation({permissionMode})}
              model={model} modelCatalog={modelCatalog}
              onModelChange={model => void configureConversation({model})}
              reasoning={useReasoning} reasoningFixed={fixedReasoning}
              onReasoningChange={() => setDeepThinking(current => !current)} experts={experts}/>
          </div>

          {detailsOpen && <aside id="workspace-details" className="absolute inset-y-0 right-0 z-10 flex w-64 max-w-full flex-col border-l bg-card shadow-lg 2xl:static 2xl:shadow-none">
            <div className="flex border-b border-border p-2">
              {([
                ['activity', '动态', Clock3],
                ['routines', '例程', Play],
                ['artifacts', '产物', FileBox],
              ] as const).map(([id, label, Icon]) => <button key={id} onClick={() => setSideTab(id)} className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs ${sideTab === id ? 'bg-muted text-foreground' : 'text-muted-foreground'}`}><Icon className="h-3.5 w-3.5" />{t(label)}{id === 'routines' && runningRoutines.length > 0 && <span className="rounded-full bg-[#4F46E5] px-1.5 text-[9px] text-white">{runningRoutines.length}</span>}</button>)}
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {sideTab === 'activity' && (events.length ? events.slice(0, 50).map((event) => <div key={event.id} className="mb-2 rounded-xl border border-border bg-card p-3"><div className="flex items-center gap-2 text-xs font-medium"><span className={`h-2 w-2 rounded-full ${event.type === 'approval' || event.type === 'question' ? 'bg-[#F59E0B]' : 'bg-[#6366F1]'}`} />{eventTitle(event)}</div><div className="mt-1 line-clamp-3 text-[11px] leading-5 text-muted-foreground">{extractEventText(event.payload) || event.source}</div></div>) : <EmptySide icon={Clock3} text="暂无工作动态" />)}
              {sideTab === 'routines' && (routines.length ? <div className="space-y-2">{routines.map((routine, index) => <RoutineCard key={String(routine.id || index)} routine={routine} onPause={(item) => void pauseRoutine(item)} onRun={(item) => void runRoutine(item)} />)}</div> : <EmptySide icon={Play} text="暂无后台任务" />)}
              {sideTab === 'artifacts' && (artifacts.length ? artifacts.map((artifact, index) => <div key={String(artifact.id || index)} className="mb-2 rounded-xl border border-border bg-card p-3"><div className="flex items-center gap-2 text-xs font-medium"><FileBox className="h-3.5 w-3.5 text-success-ink" />{String(artifact.title || artifact.name || '工作产物')}</div><div className="mt-1 text-[11px] text-muted-foreground">{String(artifact.mimeType || artifact.type || '文件')}</div></div>) : <EmptySide icon={FileBox} text="暂无产物" />)}
            </div>
          </aside>}
        </div>
      </section>}

      {pageActive && employeeMenu && menuEmployee && <EmployeeActionsMenu name={employeeDisplayName(menuEmployee.name)}
        position={employeeMenu} onClose={closeEmployeeMenu}
        onDetails={!employeeMenu.toolbar && canOpenEmployeeDetails(menuEmployee) ? () => setProfileId(menuEmployee.id) : undefined}
        onAvatar={!employeeMenu.toolbar ? () => setAvatarId(menuEmployee.id) : undefined}
        onHistory={() => void loadHistory(menuEmployee)}
        onRoutines={employeeMenu.toolbar && runtime.ready ? () => {setRoutinePanelOpen(true); void loadRoutines()} : undefined}
        onComputer={employeeMenu.toolbar ? () => setBrowserOpen(true) : undefined}
        onDirectorEngine={!employeeMenu.toolbar && menuEmployee.id === DIRECTOR_ID ? () => setDirectorEngineOpen(true) : undefined}/>}
      {historyEmployee && <EmployeeModal title={t('employee.historyFor', {name: employeeDisplayName(historyEmployee.name)})} onClose={closeHistory}>
        <div className="min-h-0 overflow-auto p-3" aria-busy={historyLoading}>
          {historyRows.map(row => <button type="button" key={row.key} disabled={employeeSelectionBusy}
            onClick={() => { closeHistory(); showConversation(historyEmployee, row) }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm hover:bg-muted disabled:opacity-50">
            <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground"/>
            <span className="min-w-0 flex-1 truncate">{readPrimaryChat(historyEmployee.id) === row.key ? t('employee.mainChat') : t(row.label || '新对话')}</span>
            {(row.canConfigure === false || row.archived) && <span className="text-xs text-muted-foreground">{t('employee.readOnly')}</span>}
            {row.hasActiveRun && <LoaderCircle className="h-3.5 w-3.5 animate-spin text-accent-ink"/>}
          </button>)}
          {historyLoading && <p role="status" className="p-3 text-sm text-muted-foreground">{t('settings.loading')}</p>}
          {historyError && <p role="alert" className="p-3 text-sm text-danger-ink">{historyError}</p>}
          {!historyLoading && !historyError && !historyRows.length && <p className="p-3 text-sm text-muted-foreground">{t('employee.emptyHistory')}</p>}
          {!historyLoading && historyNext !== undefined && <button type="button" onClick={() => void loadHistory(historyEmployee, historyNext)}
            className="rounded-lg px-3 py-2 text-xs text-muted-foreground hover:bg-muted">{t('employee.moreHistory')}</button>}
        </div>
        <footer className="flex justify-end border-t p-3">
          <button type="button" disabled={employeeSelectionBusy || !runtime.ready} onClick={() => {
            const employee = historyEmployee
            closeHistory()
            void createConversation(employee, false).catch(reason => setError(userFacingError(reason)))
          }} className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm hover:bg-muted disabled:opacity-50">
            <Plus size={16}/>{t('employee.newChat')}
          </button>
        </footer>
      </EmployeeModal>}
      {directorEngineOpen && <EmployeeModal title={t('director.engine')} onClose={() => setDirectorEngineOpen(false)}>
        <DirectorRuntimeInfo/>
      </EmployeeModal>}

      {creatingEmployee && <EmployeeEditor catalog={modelCatalog} mode="create" identity={createRequestId}
        initial={{name:'',title:'',instructions:'',avatar:XIAOYU_AVATAR,model:'auto',permissionMode:'guarded'}}
        onSave={draft => saveProfile(draft)} onClose={() => setCreatingEmployee(false)} />}
      {avatarEmployee && <EmployeeEditor catalog={modelCatalog} key={'avatar-' + avatarEmployee.id} mode="avatar" identity={avatarEmployee.id}
        initial={{...avatarEmployee, avatar:avatarEmployee.avatar || defaultRobotPreset(avatarEmployee.id,avatarEmployee.primary)}}
        onSave={draft => saveProfile(draft,avatarEmployee,true)} onClose={() => setAvatarId('')} />}

      {routinePanelOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) setRoutinePanelOpen(false) }}>
          <section className="flex max-h-[82vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl shadow-black/50">
            <header className="flex items-center gap-3 border-b border-border px-5 py-4">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent-soft/45 text-accent-ink"><Clock3 className="h-5 w-5" /></div>
              <div className="min-w-0 flex-1">
                <h2 className="text-sm font-semibold">{t("后台任务")}</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">{runningRoutines.length ? t("当前有 {v0} 个任务正在运行", { v0: runningRoutines.length }) : t("当前没有正在运行的后台任务")}</p>
              </div>
              <button onClick={() => void loadRoutines()} disabled={routinesLoading} className="rounded-lg border border-border p-2 text-muted-foreground hover:border-[#6366F1] disabled:opacity-40" title={t("刷新")}><RefreshCw className={`h-4 w-4 ${routinesLoading ? 'animate-spin' : ''}`} /></button>
              <button onClick={() => setRoutinePanelOpen(false)} className="rounded-lg border border-border p-2 text-muted-foreground hover:border-[#6366F1]" title={t("关闭")}><X className="h-4 w-4" /></button>
            </header>
            <div className="border-b border-border bg-background/55 px-5 py-3 text-[11px] leading-5 text-muted-foreground">
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
                <div className="flex items-center justify-center gap-2 py-16 text-xs text-muted-foreground"><LoaderCircle className="h-4 w-4 animate-spin" />{t("正在读取后台任务…")}</div>
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
        busy={Boolean(canConfigure && currentRun?.runId)}
        onClose={() => setBrowserOpen(false)}
        onTakeover={() => void api?.computer.takeover({ agentId: activeEmployeeId })}
        onResume={() => void api?.computer.returnControl({ agentId: activeEmployeeId })}
        onStop={() => void stopCurrent()}
        onApproval={(decision) => { if (approvalEvent) void resolveApproval(approvalEvent, decision === 'approve_once' ? 'allow-once' : 'deny') }}
      />
    </div>
  )
}

function EmptySide({ icon: Icon, text }: { icon: typeof Archive; text: string }) {
  return <div className="flex flex-col items-center py-12 text-center text-xs text-muted-foreground"><Icon className="mb-3 h-7 w-7" /><span>{text}</span></div>
}
