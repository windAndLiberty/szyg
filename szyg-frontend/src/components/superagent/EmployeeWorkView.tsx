import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Clock3,
  Hand,
  Maximize2,
  Minimize2,
  Monitor,
  Pause,
  Play,
  Square,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const DEFAULT_WIDTH = 560
const MIN_WIDTH = 440
const MAX_WIDTH = 760
const WIDTH_STORAGE_KEY = 'szyg.employee-work-view-width'

function availableMaxWidth() {
  if (typeof window === 'undefined') return MAX_WIDTH
  return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Math.round(window.innerWidth * 0.62)))
}

function clampWidth(value: number) {
  return Math.min(availableMaxWidth(), Math.max(MIN_WIDTH, Math.round(value)))
}

function initialWidth() {
  if (typeof window === 'undefined') return DEFAULT_WIDTH
  const stored = Number(window.localStorage.getItem(WIDTH_STORAGE_KEY))
  return clampWidth(Number.isFinite(stored) && stored > 0 ? stored : DEFAULT_WIDTH)
}

export type EmployeeWorkPhase = 'idle' | 'running' | 'waiting' | 'paused' | 'completed' | 'failed' | 'cancelled'

export type EmployeeWorkEvent = {
  id: string
  type: string
  title: string
  detail?: string
  technicalName?: string
  state?: 'running' | 'success' | 'warning' | 'error' | 'idle'
}

export type EmployeeApproval = {
  id: string
  title: string
  summary?: string
}

export type EmployeeFrameMeta = {
  appName?: string
  windowTitle?: string
  sourceWidth?: number
  sourceHeight?: number
}

export type EmployeePointer = {
  id: string
  xPercent: number
  yPercent: number
}

type Props = {
  open: boolean
  taskTitle: string
  result: string
  status: string
  phase: EmployeeWorkPhase
  frameUrl: string
  frameMeta: EmployeeFrameMeta
  pointer: EmployeePointer | null
  live: boolean
  previewBlocked: boolean
  events: EmployeeWorkEvent[]
  approval: EmployeeApproval | null
  paused: boolean
  busy: boolean
  startedAt: number | null
  finishedAt: number | null
  onClose: () => void
  onTakeover: () => void
  onResume: () => void
  onStop: () => void
  onApproval: (decision: 'approve_once' | 'deny') => void
}

const phaseMeta: Record<EmployeeWorkPhase, { label: string; dot: string; text: string }> = {
  idle: { label: '等待任务', dot: 'bg-[#64748B]', text: 'text-[#94A3B8]' },
  running: { label: '正在操作', dot: 'bg-[#747BFF]', text: 'text-[#C7D2FE]' },
  waiting: { label: '等待确认', dot: 'bg-[#F59E0B]', text: 'text-[#FCD34D]' },
  paused: { label: '已暂停', dot: 'bg-[#94A3B8]', text: 'text-[#CBD5E1]' },
  completed: { label: '已完成', dot: 'bg-[#2DD4A8]', text: 'text-[#6EE7C7]' },
  failed: { label: '未完成', dot: 'bg-[#F87171]', text: 'text-[#FCA5A5]' },
  cancelled: { label: '已停止', dot: 'bg-[#64748B]', text: 'text-[#94A3B8]' },
}

function formatDuration(milliseconds: number) {
  const seconds = Math.max(1, Math.round(milliseconds / 1000))
  if (seconds < 60) return `${seconds} 秒`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes} 分 ${rest} 秒` : `${minutes} 分钟`
}

function cleanWindowLabel(value: string) {
  return value.replace(/\.exe$/i, '').replace(/[-_]/g, ' ').trim()
}

export default function EmployeeWorkView({
  open,
  taskTitle,
  result,
  status,
  phase,
  frameUrl,
  frameMeta,
  pointer,
  live,
  previewBlocked,
  events,
  approval,
  paused,
  busy,
  startedAt,
  finishedAt,
  onClose,
  onTakeover,
  onResume,
  onStop,
  onApproval,
}: Props) {
  const [width, setWidth] = useState(initialWidth)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [now, setNow] = useState(Date.now())
  const [visiblePointer, setVisiblePointer] = useState<EmployeePointer | null>(null)
  const draggingRef = useRef(false)
  const previousWidthRef = useRef(DEFAULT_WIDTH)

  useEffect(() => {
    if (!busy || !startedAt) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [busy, startedAt])

  useEffect(() => {
    if (!pointer) return
    setVisiblePointer(pointer)
    const timer = window.setTimeout(() => setVisiblePointer(null), 850)
    return () => window.clearTimeout(timer)
  }, [pointer])

  useEffect(() => {
    if (phase === 'running') setDetailsOpen(false)
    if (phase === 'failed') setDetailsOpen(true)
  }, [phase, taskTitle])

  const finishResize = useCallback(() => {
    draggingRef.current = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }, [])

  const resizeFromPointer = useCallback((event: PointerEvent) => {
    if (!draggingRef.current) return
    const nextWidth = clampWidth(window.innerWidth - event.clientX)
    setWidth(nextWidth)
    setExpanded(nextWidth >= availableMaxWidth() - 4)
  }, [])

  useEffect(() => {
    window.addEventListener('pointermove', resizeFromPointer)
    window.addEventListener('pointerup', finishResize)
    window.addEventListener('pointercancel', finishResize)
    const keepWithinViewport = () => setWidth((current) => clampWidth(current))
    window.addEventListener('resize', keepWithinViewport)
    return () => {
      window.removeEventListener('pointermove', resizeFromPointer)
      window.removeEventListener('pointerup', finishResize)
      window.removeEventListener('pointercancel', finishResize)
      window.removeEventListener('resize', keepWithinViewport)
      finishResize()
    }
  }, [finishResize, resizeFromPointer])

  useEffect(() => {
    window.localStorage.setItem(WIDTH_STORAGE_KEY, String(width))
  }, [width])

  const startResize = (event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    draggingRef.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }

  const resizeWithKeyboard = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      setWidth((current) => clampWidth(current + 24))
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      setWidth((current) => clampWidth(current - 24))
    } else if (event.key === 'Home') {
      event.preventDefault()
      setWidth(MIN_WIDTH)
    } else if (event.key === 'End') {
      event.preventDefault()
      setWidth(availableMaxWidth())
    }
  }

  const toggleExpanded = () => {
    if (expanded) {
      setWidth(clampWidth(previousWidthRef.current))
      setExpanded(false)
      return
    }
    previousWidthRef.current = width
    setWidth(availableMaxWidth())
    setExpanded(true)
  }

  const completedCount = events.filter((event) => event.state === 'success').length
  const activeStep = [...events].reverse().find((event) => event.state === 'running')
  const currentStatus = activeStep?.title || status || phaseMeta[phase].label
  const elapsed = startedAt ? (finishedAt || now) - startedAt : 0
  const appLabel = cleanWindowLabel(frameMeta.windowTitle || frameMeta.appName || '')
  const visibleEvents = useMemo(() => events.slice(-12), [events])

  if (!open) return null

  return (
    <aside
      className="relative flex min-h-0 shrink-0 flex-col border-l border-[#243047] bg-[#0B1020]"
      style={{ width }}
    >
      <div
        role="separator"
        aria-label="调整工作现场宽度"
        aria-orientation="vertical"
        aria-valuemin={MIN_WIDTH}
        aria-valuemax={availableMaxWidth()}
        aria-valuenow={width}
        tabIndex={0}
        title="拖动调整宽度"
        onPointerDown={startResize}
        onKeyDown={resizeWithKeyboard}
        className="group absolute inset-y-0 left-0 z-30 w-3 -translate-x-1/2 cursor-col-resize touch-none focus:outline-none"
      >
        <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-transparent transition-colors group-hover:bg-[#747BFF] group-focus:bg-[#747BFF]" />
      </div>

      <header className="shrink-0 border-b border-[#243047] px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <Monitor className="h-4 w-4 shrink-0 text-[#8B92FF]" />
            <span className="shrink-0 text-sm font-semibold text-[#F4F7FF]">工作现场</span>
            <span className={cn('inline-flex items-center gap-1.5 text-xs', phaseMeta[phase].text)}>
              <span className={cn('h-1.5 w-1.5 rounded-full', phaseMeta[phase].dot, phase === 'running' && 'animate-pulse')} />
              {phaseMeta[phase].label}
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {phase === 'running' && (
              <button
                onClick={onTakeover}
                disabled={!busy}
                title="暂停并接管"
                className="grid h-8 w-8 place-items-center rounded-md text-[#94A3B8] hover:bg-[#182237] hover:text-[#F4F7FF] disabled:opacity-35"
              >
                <Pause className="h-4 w-4" />
              </button>
            )}
            <button
              onClick={toggleExpanded}
              title={expanded ? '恢复宽度' : '展开工作现场'}
              className="grid h-8 w-8 place-items-center rounded-md text-[#94A3B8] hover:bg-[#182237] hover:text-[#F4F7FF]"
            >
              {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </button>
            <button
              onClick={onClose}
              title="收起工作现场"
              className="grid h-8 w-8 place-items-center rounded-md text-[#64748B] hover:bg-[#182237] hover:text-[#F4F7FF]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <p className="mt-2 truncate text-sm text-[#CBD5E1]">{taskTitle || '等待你交代任务'}</p>
      </header>

      <section className="relative min-h-[250px] flex-1 overflow-hidden border-b border-[#243047] bg-[#050812]">
        {frameUrl && !previewBlocked ? (
          <>
            <img src={frameUrl} alt="员工当前操作画面" className="h-full w-full object-contain" />
            {visiblePointer && (
              <span
                key={visiblePointer.id}
                className="pointer-events-none absolute h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[#A5AAFF] bg-[#747BFF]/20 shadow-[0_0_18px_rgba(116,123,255,0.75)] animate-ping"
                style={{ left: `${visiblePointer.xPercent}%`, top: `${visiblePointer.yPercent}%` }}
              />
            )}
            <div className="absolute inset-x-0 top-0 flex items-center justify-between gap-3 bg-gradient-to-b from-black/75 to-transparent px-3 pb-8 pt-3">
              <span className="truncate text-[11px] text-white/75">{appLabel || '当前应用'}</span>
              <span className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-black/45 px-2 py-1 text-[11px] text-white/85 backdrop-blur-sm">
                <span className={cn('h-1.5 w-1.5 rounded-full', live ? 'bg-[#2DD4A8] animate-pulse' : paused ? 'bg-[#F59E0B]' : 'bg-[#64748B]')} />
                {live ? '实时画面' : paused ? '画面已暂停' : '最后画面'}
              </span>
            </div>
            <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/75 to-transparent px-3 pb-3 pt-8">
              <span className="text-[11px] text-white/65">智能聚焦当前窗口</span>
              <Monitor className="h-3.5 w-3.5 text-white/55" />
            </div>
          </>
        ) : (
          <div className="grid h-full place-items-center px-6">
            <div className="text-center text-[#64748B]">
              <Monitor className="mx-auto mb-3 h-7 w-7" />
              <p className="text-sm text-[#94A3B8]">{previewBlocked ? '当前窗口已暂停预览' : '开始电脑操作后显示实时画面'}</p>
              {previewBlocked && <p className="mt-1 text-xs text-[#64748B]">切换到目标应用后会自动继续</p>}
            </div>
          </div>
        )}
      </section>

      {approval && (
        <section className="m-3 rounded-lg border border-[#F59E0B]/35 bg-[#F59E0B]/[0.07] p-3">
          <div className="flex gap-2.5">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-[#FBBF24]" />
            <div className="min-w-0">
              <p className="text-sm text-[#F8FAFC]">{approval.title}</p>
              {approval.summary && <p className="mt-1 text-xs leading-5 text-[#94A3B8]">{approval.summary}</p>}
            </div>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button onClick={() => onApproval('deny')} className="h-8 rounded-md border border-[#334155] px-3 text-xs text-[#CBD5E1] hover:bg-[#1E293B]">取消</button>
            <button onClick={() => onApproval('approve_once')} className="h-8 rounded-md bg-[#747BFF] px-3 text-xs text-white hover:bg-[#8B92FF]">确认继续</button>
          </div>
        </section>
      )}

      <section className="shrink-0 border-b border-[#243047] px-4 py-3">
        {phase === 'completed' ? (
          <div className="rounded-lg border border-[#2DD4A8]/25 bg-[#2DD4A8]/[0.06] p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-[#D9FFF4]">
              <span className="grid h-5 w-5 place-items-center rounded-full bg-[#2DD4A8]/20"><Check className="h-3.5 w-3.5 text-[#2DD4A8]" /></span>
              任务已完成
            </div>
            {result && <p className="mt-2 line-clamp-2 text-sm leading-6 text-[#CBD5E1]">{result}</p>}
            <div className="mt-2 flex items-center gap-3 text-xs text-[#718096]">
              <span className="inline-flex items-center gap-1"><Clock3 className="h-3.5 w-3.5" />{formatDuration(elapsed)}</span>
              <span>完成 {completedCount} 个步骤</span>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-3">
              <p className="truncate text-sm text-[#E2E8F0]">{currentStatus}</p>
              <span className="shrink-0 text-xs text-[#718096]">{completedCount ? `已完成 ${completedCount} 步` : '正在准备'}</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#182237]">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-300',
                  phase === 'failed' ? 'w-full bg-[#F87171]' : phase === 'cancelled' ? 'w-full bg-[#64748B]' : 'w-2/3 bg-[#747BFF] animate-pulse',
                )}
              />
            </div>
          </>
        )}
      </section>

      <section className={cn('min-h-0 shrink-0 border-b border-[#243047]', detailsOpen && 'flex-1 overflow-y-auto')}>
        <button
          onClick={() => setDetailsOpen((value) => !value)}
          className="flex h-11 w-full items-center justify-between px-4 text-xs text-[#94A3B8] hover:bg-[#11192A] hover:text-[#CBD5E1]"
        >
          <span>{detailsOpen ? '执行记录' : `${completedCount ? `已完成 ${completedCount} 个步骤` : '查看执行记录'}`}</span>
          {detailsOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
        {detailsOpen && (
          <div className="px-4 pb-3">
            {visibleEvents.length === 0 ? (
              <p className="py-5 text-center text-xs text-[#64748B]">任务步骤会在这里出现</p>
            ) : (
              <div className="space-y-1">
                {visibleEvents.map((event) => (
                  <div key={event.id} className="flex gap-2.5 border-b border-[#182131] py-2.5 last:border-0">
                    <div className="mt-0.5 shrink-0">
                      {event.state === 'success' ? (
                        <Check className="h-3.5 w-3.5 text-[#2DD4A8]" />
                      ) : event.state === 'error' ? (
                        <CircleAlert className="h-3.5 w-3.5 text-[#F87171]" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-[#8B92FF]" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs text-[#CBD5E1]">{event.title}</p>
                      {event.detail && <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-[#64748B]">{event.detail}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {(phase === 'running' || phase === 'paused' || phase === 'waiting') && (
        <footer className="grid shrink-0 grid-cols-2 gap-2 p-3">
          {paused ? (
            <button onClick={onResume} className="flex h-9 items-center justify-center gap-1.5 rounded-md bg-[#747BFF] text-xs text-white hover:bg-[#8B92FF]">
              <Play className="h-3.5 w-3.5" />继续
            </button>
          ) : (
            <button onClick={onTakeover} disabled={!busy} className="flex h-9 items-center justify-center gap-1.5 rounded-md border border-[#334155] text-xs text-[#CBD5E1] hover:bg-[#182237] disabled:opacity-40">
              <Hand className="h-3.5 w-3.5" />接管
            </button>
          )}
          <button onClick={onStop} disabled={!busy && !paused} className="flex h-9 items-center justify-center gap-1.5 rounded-md border border-[#334155] text-xs text-[#CBD5E1] hover:bg-[#182237] disabled:opacity-40">
            <Square className="h-3.5 w-3.5" />停止
          </button>
        </footer>
      )}
    </aside>
  )
}
