import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ListChecks,
  Clock,
  CheckCircle2,
  XCircle,
  RefreshCw,
  X,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  ClipboardList,
  AlertCircle,
  Hand,
} from 'lucide-react'
import { fetchTasks, getTaskDetail, retryTask, cancelTask } from '@/lib/api'
import type { TaskItem, TaskDetail, TaskListResponse } from '@/lib/api'
import { cn } from '@/lib/utils'
import { PublishedPostLink } from '@/components/publish/PublishedPostLink'
import { translateCurrent, useI18n } from '@/lib/i18n'

// ── Constants ─────────────────────────────────────────────────

const FILTER_TABS = [
  { key: 'all', get label() { return translateCurrent("全部") }, icon: null },
  { key: 'running', get label() { return translateCurrent("⏳ 进行中") }, icon: null },
  { key: 'needs_human', get label() { return translateCurrent("✋ 需人工") }, icon: null },
  { key: 'completed', get label() { return translateCurrent("✅ 已完成") }, icon: null },
  { key: 'failed', get label() { return translateCurrent("❌ 失败") }, icon: null },
] as const

const COLUMNS = [
  { key: 'running', get title() { return translateCurrent("进行中") }, icon: Clock, color: '#10B981', bgColor: 'rgba(16,185,129,0.06)' },
  { key: 'needs_human', get title() { return translateCurrent("需人工") }, icon: Hand, color: '#F59E0B', bgColor: 'rgba(245,158,11,0.06)' },
  { key: 'completed', get title() { return translateCurrent("已完成") }, icon: CheckCircle2, color: '#64748B', bgColor: 'rgba(100,116,139,0.06)' },
  { key: 'failed', get title() { return translateCurrent("失败") }, icon: XCircle, color: '#EF4444', bgColor: 'rgba(239,68,68,0.06)' },
] as const

const POLL_INTERVAL = 10_000 // 10 seconds

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.06 } },
}

const cardVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const },
  },
  highlight: {
    opacity: 1,
    y: 0,
    boxShadow: [
      '0 0 0 0px rgba(99,102,241,0)',
      '0 0 0 3px rgba(99,102,241,0.35)',
      '0 0 0 0px rgba(99,102,241,0)',
    ],
    transition: {
      boxShadow: { duration: 1.2, ease: 'easeInOut' as const },
      duration: 0.35,
    },
  },
  exit: { opacity: 0, scale: 0.95, transition: { duration: 0.2 } },
}

// ── Helpers ────────────────────────────────────────────────────

function truncate(text: string, maxLen: number): string {
  if (!text || text.length <= maxLen) return text || ''
  return text.slice(0, maxLen) + '…'
}

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60_000)
    if (diffMin < 1) return translateCurrent("刚刚")
    if (diffMin < 60) return translateCurrent("{v0} 分钟前", { v0: diffMin })
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return translateCurrent("{v0} 小时前", { v0: diffHr })
    const diffDay = Math.floor(diffHr / 24)
    if (diffDay < 7) return translateCurrent("{v0} 天前", { v0: diffDay })
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  } catch {
    return iso
  }
}

// ── Sub-components ─────────────────────────────────────────────

/** Filter tab bar */
function FilterTabs({
  active,
  counts,
  onChange,
}: {
  active: string
  counts: Record<string, number>
  onChange: (key: string) => void
}) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {FILTER_TABS.map((tab) => {
        const isActive = active === tab.key
        const count = counts[tab.key] ?? 0
        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={cn(
              'inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-200',
              isActive
                ? 'bg-[#6366F1] text-white shadow-sm'
                : 'bg-[#1A2235] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[#1E293B] border border-transparent hover:border-[#334155]',
            )}
          >
            <span>{tab.label}</span>
            {count > 0 && (
              <span
                className={cn(
                  'inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-xs font-semibold',
                  isActive
                    ? 'bg-white/20 text-white'
                    : 'bg-[#0B0F1A] text-[#64748B]',
                )}
              >
                {count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

/** Individual task card */
function TaskCard({
  task,
  onExpand,
  onRetry,
  onCancel,
  isHighlighted,
}: {
  task: TaskItem
  onExpand: (id: string) => void
  onRetry: (id: string) => void
  onCancel: (id: string) => void
  isHighlighted: boolean
}) {
  const { t } = useI18n()
  const borderColor =
    task.status === 'running'
      ? '#10B981'
      : task.status === 'needs_human'
        ? '#F59E0B'
      : task.status === 'completed'
        ? '#64748B'
        : task.status === 'failed'
          ? '#EF4444'
          : '#334155'

  return (
    <motion.div
      variants={cardVariants}
      initial="hidden"
      animate={isHighlighted ? 'highlight' : 'visible'}
      exit="exit"
      whileHover={{ y: -1 }}
      className="relative rounded-xl overflow-hidden cursor-pointer group"
      style={{ background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)' }}
      onClick={() => onExpand(task.id)}
    >
      {/* Left border color indicator */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1"
        style={{ backgroundColor: borderColor }}
      />

      <div className="pl-5 pr-4 py-4">
        {/* Header: icon + type label + platform badge */}
        <div className="flex items-center gap-2 mb-2.5">
          <span className="text-lg leading-none">{task.type_icon}</span>
          <span className="text-[13px] font-medium text-[#F1F5F9] leading-tight truncate flex-1">
            {task.name}
          </span>
          <span className="text-[11px] text-[#64748B] bg-[#0D1321] border border-[#1E293B] rounded-md px-2 py-0.5 shrink-0 whitespace-nowrap">
            {task.platform}
          </span>
        </div>

        {/* Time */}
        <div className="flex items-center gap-1.5 mb-2.5 text-[11px] text-[#64748B]">
          <Clock className="w-3 h-3 shrink-0" />
          <span>
            {task.status === 'running'
              ? t("开始于 {v0}", { v0: formatTime(task.started_at) })
              : task.status === 'completed'
                ? t("完成于 {v0}", { v0: formatTime(task.finished_at) })
                : t("开始于 {v0}", { v0: formatTime(task.started_at) })}
          </span>
        </div>

        {/* Status-specific content */}
        {task.status === 'running' && (
          <div className="mb-3">
            <p className="text-xs text-[#10B981] bg-[rgba(16,185,129,0.08)] rounded-lg px-2.5 py-1.5 leading-relaxed">
              {task.progress || t("执行中...")}
            </p>
          </div>
        )}

        {task.status === 'completed' && (
          <div className="mb-3">
            <p className="text-xs text-[#94A3B8] bg-[rgba(100,116,139,0.08)] rounded-lg px-2.5 py-1.5 leading-relaxed">
              {task.result || t("已完成")}
            </p>
          </div>
        )}

        {task.status === 'needs_human' && (
          <div className="mb-3">
            <div className="flex items-start gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-[#F59E0B] shrink-0 mt-0.5" />
              <p className="text-xs text-[#F59E0B] leading-relaxed">
                {truncate(task.error || task.progress || t("需要人工处理"), 60)}
              </p>
            </div>
          </div>
        )}

        {task.status === 'failed' && (
          <div className="mb-3">
            <div className="flex items-start gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-[#EF4444] shrink-0 mt-0.5" />
              <p className="text-xs text-[#EF4444] leading-relaxed">
                {truncate(task.error, 50)}
              </p>
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2 pt-1 border-t border-[#1E293B]">
          <button
            onClick={(e) => { e.stopPropagation(); onExpand(task.id) }}
            className="text-xs text-[#94A3B8] hover:text-[#F1F5F9] transition-colors flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" />

            {t("查看详情")}
          </button>

          {task.status === 'running' && (
            <button
              onClick={(e) => { e.stopPropagation(); onCancel(task.id) }}
              className="text-xs text-[#F59E0B] hover:text-[#FBBF24] transition-colors ml-auto flex items-center gap-1"
            >
              <XCircle className="w-3 h-3" />

              {t("取消任务")}
            </button>
          )}

          {(task.status === 'failed' || task.status === 'needs_human') && (
            <button
              onClick={(e) => { e.stopPropagation(); onRetry(task.id) }}
              className="text-xs text-[#6366F1] hover:text-[#818CF8] transition-colors ml-auto flex items-center gap-1"
            >
              <RefreshCw className="w-3 h-3" />

              {t("重试")}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

/** Column header */
function ColumnHeader({
  title,
  icon: Icon,
  color,
  count,
}: {
  title: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  count: number
}) {
  return (
    <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#1E293B]">
      <span style={{ color }} className="shrink-0 flex">
        <Icon className="w-4 h-4" />
      </span>
      <h3 className="text-sm font-semibold text-[#F1F5F9]">{title}</h3>
      <span className="text-xs text-[#64748B] bg-[#1A2235] rounded-full px-2 py-0.5 ml-auto">
        {count}
      </span>
    </div>
  )
}

/** Expanded task detail panel / modal */
function TaskDetailModal({
  taskId,
  onClose,
}: {
  taskId: string
  onClose: () => void
}) {
  const { t } = useI18n()
  const [detail, setDetail] = useState<TaskDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getTaskDetail(taskId)
      .then((d) => { if (!cancelled) setDetail(d) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [taskId])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Panel */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-2xl max-h-[85vh] overflow-hidden rounded-card-lg border border-[#1E293B] flex flex-col"
        style={{ background: 'linear-gradient(180deg, rgba(26,34,53,0.95) 0%, rgba(17,24,39,0.98) 100%)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1E293B] shrink-0">
          <div className="flex items-center gap-3">
            {detail && (
              <span className="text-xl">{detail.type_icon}</span>
            )}
            <div>
              <h2 className="text-base font-semibold text-[#F1F5F9]">
                {detail?.name || t("加载中...")}
              </h2>
              <p className="text-xs text-[#64748B] mt-0.5">
                {detail?.platform}  {t("· 优先级")} {detail?.priority}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A2235] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 text-[#6366F1] animate-spin" />
            </div>
          ) : detail ? (
            <div className="space-y-5">
              {/* Task info */}
              <div className="grid grid-cols-2 gap-3">
                <InfoBlock label={t("任务类型")} value={detail.type_label} />
                <InfoBlock label={t("触发方式")} value={detail.trigger_type} />
                <InfoBlock label={t("创建时间")} value={new Date(detail.created_at).toLocaleString('zh-CN')} />
                <InfoBlock label={t("状态")} value={
                  <span className={cn(
                    'text-xs font-medium px-2 py-0.5 rounded-full',
                    detail.status === 'running' && 'bg-[rgba(16,185,129,0.15)] text-[#10B981]',
                    detail.status === 'needs_human' && 'bg-[rgba(245,158,11,0.15)] text-[#F59E0B]',
                    detail.status === 'completed' && 'bg-[rgba(100,116,139,0.15)] text-[#94A3B8]',
                    detail.status === 'failed' && 'bg-[rgba(239,68,68,0.15)] text-[#EF4444]',
                  )}>
                    {detail.status === 'running' ? t("进行中") : detail.status === 'needs_human' ? t("需人工") : detail.status === 'completed' ? t("已完成") : t("失败")}
                  </span>
                } />
              </div>

              {detail.error && (
                <div className="bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.2)] rounded-xl p-4">
                  <p className="text-xs font-medium text-[#EF4444] mb-1">{t("错误原因")}</p>
                  <p className="text-sm text-[#FCA5A5] leading-relaxed">{detail.error}</p>
                </div>
              )}

              {detail.execution_run?.error_code && (
                <div className="bg-[#0D1321] border border-[#1E293B] rounded-xl p-4">
                  <p className="text-xs font-medium text-[#F59E0B] mb-1">{t("错误码")}</p>
                  <p className="text-sm text-[#F1F5F9]">{detail.execution_run.error_code}</p>
                </div>
              )}

              {detail.result && (
                <div className="bg-[rgba(16,185,129,0.06)] border border-[rgba(16,185,129,0.15)] rounded-xl p-4">
                  <p className="text-xs font-medium text-[#10B981] mb-1">{t("执行结果")}</p>
                  <p className="text-sm text-[#94A3B8] leading-relaxed">{detail.result}</p>
                </div>
              )}

              <PublishedPostLink result={detail.execution_run?.result} platform={detail.execution_run?.platform} />

              {detail.steps && detail.steps.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-[#F1F5F9] mb-3">{t("执行步骤")}</h4>
                  <div className="space-y-2">
                    {detail.steps.map((step) => (
                      <div key={step.id} className="rounded-lg bg-[#0D1321] border border-[#1E293B] px-3 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-[#F1F5F9] truncate">{step.name}</p>
                            <p className="mt-1 text-xs text-[#64748B]">{step.executor_type} · {step.step_id}</p>
                          </div>
                          <span className={cn(
                            'shrink-0 text-xs font-medium px-2 py-0.5 rounded-full',
                            step.status === 'success' && 'bg-[rgba(16,185,129,0.15)] text-[#10B981]',
                            step.status === 'running' && 'bg-[rgba(59,130,246,0.15)] text-[#3B82F6]',
                            step.status === 'failed' && 'bg-[rgba(239,68,68,0.15)] text-[#EF4444]',
                            step.status === 'needs_human' && 'bg-[rgba(245,158,11,0.15)] text-[#F59E0B]',
                          )}>
                            {step.status === 'needs_human' ? t("需人工") : step.status}
                          </span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-3 text-xs text-[#64748B]">
                          <span>{step.duration_ms ? `${Math.round(step.duration_ms / 1000)}s` : t("未完成")}</span>
                          {step.error_code && <span className="text-[#F59E0B]">{step.error_code}</span>}
                          {step.error_message && <span className="text-[#FCA5A5]">{truncate(step.error_message, 90)}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Execution logs */}
              {detail.logs.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-[#F1F5F9] mb-3">{t("审计日志")}</h4>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {detail.logs.map((log, i) => (
                      <div
                        key={log.id || i}
                        className="flex items-start gap-3 text-xs py-2 px-3 rounded-lg bg-[#0D1321] border border-[#1E293B]"
                      >
                        <span
                          className={cn(
                            'w-1.5 h-1.5 rounded-full mt-1.5 shrink-0',
                            log.status === 'success' && 'bg-[#10B981]',
                            log.status === 'error' && 'bg-[#EF4444]',
                            log.status === 'info' && 'bg-[#3B82F6]',
                          )}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-[#94A3B8] leading-relaxed break-all">{log.message}</p>
                          <p className="text-[#64748B] mt-1">
                            {new Date(log.timestamp).toLocaleString('zh-CN')}
                            {log.action ? ` · ${log.action}` : ''}
                            {log.error_code ? ` · ${log.error_code}` : ''}
                          </p>
                          {log.artifact_path && (
                            <p className="text-[#38BDF8] mt-1 break-all">{log.artifact_path}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-[#64748B] text-sm">{t("无法加载任务详情")}</div>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

/** Info block inside detail modal */
function InfoBlock({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-[#0D1321] border border-[#1E293B] rounded-lg px-3 py-2.5">
      <p className="text-[11px] text-[#64748B] mb-0.5">{label}</p>
      <div className="text-sm text-[#F1F5F9]">{value}</div>
    </div>
  )
}

/** Empty state */
function EmptyBoard() {
  const { t } = useI18n();

  return (
    <div className="flex flex-col items-center justify-center py-20 px-6">
      <div className="w-16 h-16 rounded-2xl bg-[#1A2235] border border-[#1E293B] flex items-center justify-center mb-5">
        <ClipboardList className="w-8 h-8 text-[#64748B]" />
      </div>
      <h3 className="text-base font-semibold text-[#94A3B8] mb-2">{t("暂无工作记录")}</h3>
      <p className="text-sm text-[#64748B] text-center max-w-sm leading-relaxed">

        {t("通过超级员工、内容发布或营销获客创建任务后，AI 员工的执行过程会在这里留下记录")}
      </p>
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────

export default function TaskBoard() {
  const { t } = useI18n()
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [counts, setCounts] = useState<Record<string, number>>({ all: 0, running: 0, needs_human: 0, completed: 0, failed: 0 })
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set())
  const [retryingIds, setRetryingIds] = useState<Set<string>>(new Set())
  const [cancellingIds, setCancellingIds] = useState<Set<string>>(new Set())

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const prevTaskIdsRef = useRef<Set<string>>(new Set())
  const prevTaskDataRef = useRef<Map<string, TaskItem>>(new Map())

  // ── Data fetching ──────────────────────────────────────────

  const loadTasks = useCallback(async (silent = false) => {
    if (!silent) setError('')
    try {
      const data: TaskListResponse = await fetchTasks()
      setTasks(data.tasks)
      setCounts(data.counts)
      setLoading(false)

      // Detect changes for highlight animation
      const prevIds = prevTaskIdsRef.current
      const prevData = prevTaskDataRef.current
      const newIds = new Set(data.tasks.map((t) => t.id))
      const newData = new Map(data.tasks.map((t) => [t.id, t]))

      // Find: new tasks, or tasks whose status changed
      const changed = new Set<string>()
      for (const t of data.tasks) {
        if (!prevIds.has(t.id)) {
          changed.add(t.id) // new task
        } else {
          const prev = prevData.get(t.id)
          if (prev && prev.status !== t.status) {
            changed.add(t.id) // status changed
          }
        }
      }

      if (changed.size > 0 && !silent) {
        setHighlightedIds(changed)
        setTimeout(() => setHighlightedIds(new Set()), 1500)
      }

      prevTaskIdsRef.current = newIds
      prevTaskDataRef.current = newData
    } catch (err: unknown) {
      if (!silent) {
        setError(err instanceof Error ? err.message : t("加载任务失败"))
      }
    }
  }, [])

  // Initial load + auto-refresh
  useEffect(() => {
    loadTasks()
    intervalRef.current = setInterval(() => loadTasks(true), POLL_INTERVAL)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [loadTasks])

  // ── Actions ────────────────────────────────────────────────

  const handleRetry = useCallback(async (taskId: string) => {
    setRetryingIds((prev) => new Set(prev).add(taskId))
    try {
      await retryTask(taskId)
      await loadTasks()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("重试失败"))
    } finally {
      setRetryingIds((prev) => {
        const next = new Set(prev)
        next.delete(taskId)
        return next
      })
    }
  }, [loadTasks])

  const handleCancel = useCallback(async (taskId: string) => {
    setCancellingIds((prev) => new Set(prev).add(taskId))
    try {
      await cancelTask(taskId)
      await loadTasks()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("取消失败"))
    } finally {
      setCancellingIds((prev) => {
        const next = new Set(prev)
        next.delete(taskId)
        return next
      })
    }
  }, [loadTasks])

  const handleExpand = useCallback((taskId: string) => {
    setExpandedId(taskId)
  }, [])

  // ── Filtered tasks ─────────────────────────────────────────

  const filteredTasks = filter === 'all'
    ? tasks
    : tasks.filter((t) => t.status === filter || (filter === 'running' && (t.status === 'running' || t.status === 'pending')))

  const runningTasks = filteredTasks.filter((t) => t.status === 'running' || t.status === 'pending')
  const needsHumanTasks = filteredTasks.filter((t) => t.status === 'needs_human')
  const completedTasks = filteredTasks.filter((t) => t.status === 'completed')
  const failedTasks = filteredTasks.filter((t) => t.status === 'failed')

  const isEmpty = runningTasks.length === 0 && needsHumanTasks.length === 0 && completedTasks.length === 0 && failedTasks.length === 0
  const tasksForColumn = (key: string) => {
    if (key === 'running') return runningTasks
    if (key === 'needs_human') return needsHumanTasks
    if (key === 'completed') return completedTasks
    return failedTasks
  }

  // ── Render ──────────────────────────────────────────────────

  return (
    <div className="min-h-full px-4 sm:px-6 lg:px-8 py-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <p className="text-sm text-[#94A3B8]">{t("查看 AI 员工完成了什么、卡在哪里、是否需要人工处理")}</p>
        </div>

        {/* Manual refresh */}
        <button
          onClick={() => loadTasks()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-[#1A2235] border border-[#1E293B] text-sm text-[#94A3B8] hover:text-[#F1F5F9] hover:border-[#334155] transition-colors self-start"
        >
          <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />

          {t("刷新")}
        </button>
      </div>

      {/* Error toast */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 flex items-center gap-3 px-4 py-3 rounded-xl bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.25)] text-sm text-[#EF4444]"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError('')} className="shrink-0 text-[#EF4444]/70 hover:text-[#EF4444]">
            <X className="w-4 h-4" />
          </button>
        </motion.div>
      )}

      {/* Filter tabs */}
      <div className="mb-6">
        <FilterTabs active={filter} counts={counts} onChange={setFilter} />
      </div>

      {/* Content: Kanban or Empty */}
      {loading && tasks.length === 0 ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="w-8 h-8 text-[#6366F1] animate-spin" />
        </div>
      ) : isEmpty ? (
        <EmptyBoard />
      ) : (
        <>
          {/* Desktop: 3-column layout */}
          <div className="hidden lg:grid lg:grid-cols-4 gap-4">
            {COLUMNS.map((col) => {
              const colTasks = tasksForColumn(col.key)

              return (
                <div
                  key={col.key}
                  className="rounded-xl border border-[#1E293B] p-4 min-h-[300px]"
                  style={{ backgroundColor: col.bgColor }}
                >
                  <ColumnHeader title={col.title} icon={col.icon} color={col.color} count={colTasks.length} />

                  <div className="space-y-3">
                    <AnimatePresence mode="popLayout">
                      {colTasks.map((task) => (
                        <TaskCard
                          key={task.id}
                          task={task}
                          onExpand={handleExpand}
                          onRetry={handleRetry}
                          onCancel={handleCancel}
                          isHighlighted={highlightedIds.has(task.id)}
                        />
                      ))}
                    </AnimatePresence>

                    {colTasks.length === 0 && (
                      <div className="text-center py-10 text-sm text-[#64748B]">

                        {t("暂无任务")}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Tablet: 2-column layout */}
          <div className="hidden md:grid lg:hidden grid-cols-2 gap-4">
            {COLUMNS.map((col) => {
              const colTasks = tasksForColumn(col.key)

              return (
                <div
                  key={col.key}
                  className="rounded-xl border border-[#1E293B] p-4 min-h-[200px]"
                  style={{ backgroundColor: col.bgColor }}
                >
                  <ColumnHeader title={col.title} icon={col.icon} color={col.color} count={colTasks.length} />
                  <div className="space-y-3">
                    <AnimatePresence mode="popLayout">
                      {colTasks.map((task) => (
                        <TaskCard
                          key={task.id}
                          task={task}
                          onExpand={handleExpand}
                          onRetry={handleRetry}
                          onCancel={handleCancel}
                          isHighlighted={highlightedIds.has(task.id)}
                        />
                      ))}
                    </AnimatePresence>
                    {colTasks.length === 0 && (
                      <div className="text-center py-10 text-sm text-[#64748B]">{t("暂无任务")}</div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Mobile: single column, grouped by status */}
          <div className="md:hidden space-y-6">
            {COLUMNS.map((col) => {
              const colTasks = tasksForColumn(col.key)

              if (colTasks.length === 0) return null

              return (
                <div key={col.key}>
                  <ColumnHeader title={col.title} icon={col.icon} color={col.color} count={colTasks.length} />
                  <div className="space-y-3">
                    <AnimatePresence mode="popLayout">
                      {colTasks.map((task) => (
                        <TaskCard
                          key={task.id}
                          task={task}
                          onExpand={handleExpand}
                          onRetry={handleRetry}
                          onCancel={handleCancel}
                          isHighlighted={highlightedIds.has(task.id)}
                        />
                      ))}
                    </AnimatePresence>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Detail modal */}
      <AnimatePresence>
        {expandedId && (
          <TaskDetailModal taskId={expandedId} onClose={() => setExpandedId(null)} />
        )}
      </AnimatePresence>
    </div>
  )
}
