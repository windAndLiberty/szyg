import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Globe2,
  Hand,
  LoaderCircle,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  RefreshCw,
  Square,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { translateCurrent, useI18n } from '@/lib/i18n'

const DEFAULT_WIDTH = 580
const MIN_WIDTH = 460
const MAX_WIDTH = 820
const WIDTH_STORAGE_KEY = 'szyg.browser-work-view-width'

function availableMaxWidth() {
  if (typeof window === 'undefined') return MAX_WIDTH
  return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Math.round(window.innerWidth * 0.68)))
}

function clampWidth(value: number) {
  return Math.min(availableMaxWidth(), Math.max(MIN_WIDTH, Math.round(value)))
}

function initialWidth() {
  if (typeof window === 'undefined') return DEFAULT_WIDTH
  const stored = Number(window.localStorage.getItem(WIDTH_STORAGE_KEY))
  return clampWidth(Number.isFinite(stored) && stored > 0 ? stored : DEFAULT_WIDTH)
}

export type BrowserWorkPhase = 'idle' | 'running' | 'waiting' | 'paused' | 'completed' | 'failed' | 'cancelled'

export type BrowserWorkEvent = {
  id: string
  type: string
  title: string
  detail?: string
  technicalName?: string
  state?: 'running' | 'success' | 'warning' | 'error' | 'idle'
}

export type BrowserApproval = {
  id: string
  title: string
  summary?: string
}

type BrowserState = {
  available?: boolean
  visible?: boolean
  owner?: 'none' | 'agent' | 'user'
  url?: string
  title?: string
  loading?: boolean
  canGoBack?: boolean
  canGoForward?: boolean
  lastAction?: string
  error?: string
}

type Props = {
  open: boolean
  /** 页面是否处于当前可见的 keep-alive 槽位;切到其他页面时为 false */
  pageActive?: boolean
  taskTitle: string
  result: string
  status: string
  phase: BrowserWorkPhase
  events: BrowserWorkEvent[]
  approval: BrowserApproval | null
  paused: boolean
  busy: boolean
  onClose: () => void
  onTakeover: () => void
  onResume: () => void
  onStop: () => void
  onApproval: (decision: 'approve_once' | 'deny') => void
}

const phaseMeta: Record<BrowserWorkPhase, { label: string; dot: string; text: string }> = {
  idle: { get label() { return translateCurrent("等待任务") }, dot: 'bg-[#64748B]', text: 'text-[#94A3B8]' },
  running: { get label() { return translateCurrent("正在操作") }, dot: 'bg-[#747BFF]', text: 'text-[#C7D2FE]' },
  waiting: { get label() { return translateCurrent("等待确认") }, dot: 'bg-[#F59E0B]', text: 'text-[#FCD34D]' },
  paused: { get label() { return translateCurrent("已暂停") }, dot: 'bg-[#94A3B8]', text: 'text-[#CBD5E1]' },
  completed: { get label() { return translateCurrent("已完成") }, dot: 'bg-[#2DD4A8]', text: 'text-[#6EE7C7]' },
  failed: { get label() { return translateCurrent("未完成") }, dot: 'bg-[#F87171]', text: 'text-[#FCA5A5]' },
  cancelled: { get label() { return translateCurrent("已停止") }, dot: 'bg-[#64748B]', text: 'text-[#94A3B8]' },
}

function hostname(value?: string) {
  if (!value) return ''
  try {
    return new URL(value).hostname.replace(/^www\./, '')
  } catch {
    return value
  }
}

export default function BrowserWorkView({
  open,
  pageActive = true,
  taskTitle,
  result,
  status,
  phase,
  events,
  approval,
  paused,
  busy,
  onClose,
  onTakeover,
  onResume,
  onStop,
  onApproval,
}: Props) {
  const { t } = useI18n()
  const [width, setWidth] = useState(initialWidth)
  const [expanded, setExpanded] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [browserState, setBrowserState] = useState<BrowserState>({})
  const viewportRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)
  const previousWidthRef = useRef(DEFAULT_WIDTH)
  const electron = window.electronAPI

  const syncBounds = useCallback(() => {
    if (!electron?.browserSetBounds || !viewportRef.current || !open) return
    const rect = viewportRef.current.getBoundingClientRect()
    void electron.browserSetBounds({ x: rect.left, y: rect.top, width: rect.width, height: rect.height })
  }, [electron, open])

  useEffect(() => {
    if (!electron?.browserSetVisible) return
    // 页面切走(keep-alive 隐藏)时必须让出原生浏览器窗口,避免遮挡/黑屏
    void electron.browserSetVisible(open && pageActive)
    if (!open || !pageActive) return
    void electron.browserGetState?.().then((state) => setBrowserState(state as BrowserState))
    const dispose = electron.onBrowserState?.((state) => setBrowserState(state as BrowserState))
    const frame = window.requestAnimationFrame(syncBounds)
    return () => {
      window.cancelAnimationFrame(frame)
      dispose?.()
      void electron.browserSetVisible?.(false)
    }
  }, [electron, open, syncBounds, pageActive])

  useEffect(() => {
    if (!open || !viewportRef.current) return
    const observer = new ResizeObserver(syncBounds)
    observer.observe(viewportRef.current)
    window.addEventListener('resize', syncBounds)
    const timer = window.setTimeout(syncBounds, 80)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', syncBounds)
      window.clearTimeout(timer)
    }
  }, [open, syncBounds, width])

  useEffect(() => {
    window.localStorage.setItem(WIDTH_STORAGE_KEY, String(width))
  }, [width])

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
    return () => {
      window.removeEventListener('pointermove', resizeFromPointer)
      window.removeEventListener('pointerup', finishResize)
      window.removeEventListener('pointercancel', finishResize)
      finishResize()
    }
  }, [finishResize, resizeFromPointer])

  const startResize = (event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    draggingRef.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
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

  const browserAction = async (action: string) => {
    if (!electron?.browserAction) return
    const next = await electron.browserAction({ action })
    setBrowserState(next as BrowserState)
  }

  const handleTakeover = () => {
    void browserAction('takeover')
    onTakeover()
  }

  const handleResume = () => {
    void browserAction('resume')
    onResume()
  }

  const handleStop = () => {
    void browserAction('stop')
    onStop()
  }

  const visibleEvents = useMemo(() => events.slice(-10), [events])
  const activeStatus = browserState.lastAction || status || phaseMeta[phase].label
  const hasDesktopBrowser = Boolean(electron?.browserSetVisible)

  if (!open) return null

  return (
    <aside className="relative flex min-h-0 shrink-0 flex-col border-l border-[#243047] bg-[#0B1020]" style={{ width }}>
      <div
        role="separator"
        aria-label={t("调整工作现场宽度")}
        tabIndex={0}
        title={t("拖动调整宽度")}
        onPointerDown={startResize}
        className="group absolute inset-y-0 left-0 z-30 w-3 -translate-x-1/2 cursor-col-resize touch-none focus:outline-none"
      >
        <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-transparent transition-colors group-hover:bg-[#747BFF] group-focus:bg-[#747BFF]" />
      </div>

      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-[#243047] px-4">
        <div className="grid h-8 w-8 place-items-center rounded-md bg-[#747BFF]/12 text-[#A5B4FC]">
          <Globe2 className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={cn('h-2 w-2 rounded-full', phaseMeta[phase].dot, phase === 'running' && 'animate-pulse')} />
            <span className={cn('text-xs font-medium', phaseMeta[phase].text)}>{phaseMeta[phase].label}</span>
          </div>
          <p className="truncate text-sm font-medium text-[#F4F7FF]">{taskTitle || t("工作现场")}</p>
        </div>
        {paused || browserState.owner === 'user' ? (
          <button onClick={handleResume} className="inline-flex h-8 items-center gap-1.5 px-2.5 text-xs text-[#C7D2FE] hover:bg-[#1E293B]" title={t("继续")}>
            <Play className="h-3.5 w-3.5" />{t("继续")}
          </button>
        ) : (
          <button onClick={handleTakeover} className="inline-flex h-8 items-center gap-1.5 px-2.5 text-xs text-[#CBD5E1] hover:bg-[#1E293B]" title={t("暂时由我操作")}>
            <Hand className="h-3.5 w-3.5" />{t("由我操作")}
          </button>
        )}
        {(busy || phase === 'running' || phase === 'paused') && (
          <button onClick={handleStop} className="grid h-8 w-8 place-items-center text-[#94A3B8] hover:bg-[#1E293B] hover:text-[#FCA5A5]" title={t("停止")}>
            <Square className="h-3.5 w-3.5" />
          </button>
        )}
        <button onClick={toggleExpanded} className="grid h-8 w-8 place-items-center text-[#94A3B8] hover:bg-[#1E293B] hover:text-white" title={expanded ? t("恢复宽度") : t("展开")}>
          {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
        <button onClick={onClose} className="grid h-8 w-8 place-items-center text-[#94A3B8] hover:bg-[#1E293B] hover:text-white" title={t("关闭")}>
          <X className="h-4 w-4" />
        </button>
      </header>

      <div className="flex h-11 shrink-0 items-center gap-1 border-b border-[#243047] bg-[#0E1525] px-2">
        <button disabled={!browserState.canGoBack} onClick={() => void browserAction('back')} className="grid h-8 w-8 place-items-center text-[#94A3B8] hover:bg-[#1E293B] disabled:opacity-30" title={t("后退")}>
          <ArrowLeft className="h-4 w-4" />
        </button>
        <button disabled={!browserState.canGoForward} onClick={() => void browserAction('forward')} className="grid h-8 w-8 place-items-center text-[#94A3B8] hover:bg-[#1E293B] disabled:opacity-30" title={t("前进")}>
          <ArrowRight className="h-4 w-4" />
        </button>
        <button onClick={() => void browserAction('refresh')} className="grid h-8 w-8 place-items-center text-[#94A3B8] hover:bg-[#1E293B]" title={t("刷新")}>
          <RefreshCw className={cn('h-3.5 w-3.5', browserState.loading && 'animate-spin')} />
        </button>
        <div className="mx-1 flex min-w-0 flex-1 items-center gap-2 rounded-md border border-[#26334A] bg-[#111827] px-3 py-1.5">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#2DD4A8]" />
          <span className="truncate text-xs text-[#CBD5E1]">{hostname(browserState.url) || t("等待打开网页")}</span>
        </div>
        {browserState.owner === 'user' && <span className="px-2 text-[11px] text-[#FCD34D]">{t("你正在操作")}</span>}
      </div>

      <div ref={viewportRef} className="relative min-h-0 flex-1 overflow-hidden bg-[#080C14]">
        {!hasDesktopBrowser && (
          <div className="absolute inset-0 grid place-items-center px-10 text-center">
            <div>
              <Globe2 className="mx-auto mb-3 h-7 w-7 text-[#64748B]" />
              <p className="text-sm text-[#CBD5E1]">{t("网页处理画面将在桌面版中实时显示")}</p>
              <p className="mt-1 text-xs text-[#64748B]">{t("当前开发网页仅显示任务进度与确认信息")}</p>
            </div>
          </div>
        )}
      </div>

      {approval && (
        <section className="shrink-0 border-t border-[#6B4F16] bg-[#181407] px-4 py-3">
          <div className="flex items-start gap-2">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-[#F59E0B]" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[#FEF3C7]">{approval.title}</p>
              {approval.summary && <p className="mt-1 text-xs leading-5 text-[#D6C48A]">{approval.summary}</p>}
              <div className="mt-3 flex gap-2">
                <button onClick={() => onApproval('approve_once')} className="h-8 bg-[#F4F7FF] px-3 text-xs font-medium text-[#111827] hover:bg-white">{t("确认继续")}</button>
                <button onClick={() => onApproval('deny')} className="h-8 border border-[#5B4A24] px-3 text-xs text-[#D6C48A] hover:bg-[#2A220E]">{t("取消")}</button>
              </div>
            </div>
          </div>
        </section>
      )}

      <footer className="shrink-0 border-t border-[#243047] bg-[#0E1525]">
        <div className="flex min-h-12 items-center gap-2 px-4">
          {browserState.loading || phase === 'running' ? <LoaderCircle className="h-4 w-4 shrink-0 animate-spin text-[#747BFF]" /> : phase === 'completed' ? <Check className="h-4 w-4 shrink-0 text-[#2DD4A8]" /> : phase === 'paused' ? <Pause className="h-4 w-4 shrink-0 text-[#94A3B8]" /> : <Globe2 className="h-4 w-4 shrink-0 text-[#64748B]" />}
          <span className="min-w-0 flex-1 truncate text-xs text-[#CBD5E1]">{phase === 'completed' && result ? result : activeStatus}</span>
          {visibleEvents.length > 0 && (
            <button onClick={() => setDetailsOpen((value) => !value)} className="inline-flex items-center gap-1 text-xs text-[#94A3B8] hover:text-white">
              {detailsOpen ? t("收起记录") : t("查看记录 {v0}", { v0: visibleEvents.length })}
              {detailsOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </button>
          )}
        </div>
        {detailsOpen && (
          <div className="max-h-44 overflow-y-auto border-t border-[#243047] px-4 py-2">
            {visibleEvents.map((event) => (
              <div key={event.id} className="flex min-h-8 items-start gap-2 py-1.5 text-xs">
                {event.state === 'success' ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#2DD4A8]" /> : event.state === 'error' ? <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#F87171]" /> : <span className="mt-1 h-2 w-2 shrink-0 animate-pulse rounded-full bg-[#747BFF]" />}
                <div className="min-w-0">
                  <p className="text-[#CBD5E1]">{event.title}</p>
                  {event.detail && <p className="mt-0.5 text-[#64748B]">{event.detail}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </footer>
    </aside>
  )
}
