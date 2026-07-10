import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, CheckCircle2, Clock, Loader2 } from 'lucide-react'

export const PLATFORM_LABELS: Record<string, string> = {
  douyin: '抖音',
  xhs: '小红书',
  kuaishou: '快手',
  bilibili: 'B站',
  wechat: '微信',
  wechat_mp: '公众号',
}

export const PLATFORM_OPTIONS = [
  { value: 'douyin', label: '抖音' },
  { value: 'xhs', label: '小红书' },
  { value: 'kuaishou', label: '快手' },
  { value: 'bilibili', label: 'B站' },
]

export const STRATEGY_OPTIONS = [
  { value: 'balanced', label: '均衡' },
  { value: 'friendly', label: '亲和' },
  { value: 'professional', label: '专业' },
  { value: 'cautious', label: '谨慎' },
]

export const FUNNEL_STAGE_LABELS: Record<string, string> = {
  discovered: '发现线索',
  replied: '已回复',
  dm_sent: '已私信',
  responded: '已回应',
  qualified: '已确认',
  converted: '已转化',
}

export interface QueueMetrics {
  pending: number
  sent: number
  failed: number
  skipped: number
  needsHuman: number
}

export interface FunnelStage {
  stage: string
  label: string
  count: number
}

export function normalizeQueueMetrics(stats: Record<string, unknown> | undefined): QueueMetrics {
  const queue = (stats?.queue || {}) as Record<string, unknown>
  const value = (...keys: string[]) => {
    for (const key of keys) {
      const raw = queue[key] ?? stats?.[key]
      const num = Number(raw)
      if (Number.isFinite(num)) return num
    }
    return 0
  }
  const failed = value('total_failed', 'failed')
  const skipped = value('total_skipped', 'skipped')
  return {
    pending: value('total_pending', 'queued', 'pending'),
    sent: value('total_sent', 'sent'),
    failed,
    skipped,
    needsHuman: value('needs_human', 'needsHuman') || failed + skipped,
  }
}

export function parseFunnelStages(data: Record<string, unknown> | undefined): FunnelStage[] {
  const raw = data?.funnel
  if (!Array.isArray(raw)) return []
  return raw
    .map((item) => {
      const row = item as Record<string, unknown>
      const stage = String(row.stage || '')
      return {
        stage,
        label: FUNNEL_STAGE_LABELS[stage] || stage || '未知阶段',
        count: Number(row.count || 0),
      }
    })
    .filter((item) => item.stage)
}

export function formatNumber(value: unknown): string {
  const n = Number(value || 0)
  if (!Number.isFinite(n) || n <= 0) return '0'
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(Math.round(n))
}

export function formatDateTime(value: unknown): string {
  if (!value) return '-'
  try {
    return new Date(String(value)).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '-'
  }
}

export function platformLabel(platform?: string): string {
  if (!platform) return '未知平台'
  return PLATFORM_LABELS[platform] || platform
}

export function scoreTone(score?: number): string {
  const value = Number(score || 0)
  if (value >= 80) return 'text-[#10B981] bg-[#10B981]/10 border-[#10B981]/25'
  if (value >= 60) return 'text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/25'
  return 'text-[#94A3B8] bg-[#64748B]/10 border-[#64748B]/25'
}

export function statusTone(status?: string): { label: string; className: string; icon: LucideIcon } {
  const normalized = String(status || '').toLowerCase()
  if (['success', 'sent', 'completed', 'active', 'ok'].includes(normalized)) {
    return { label: '成功', className: 'text-[#10B981] bg-[#10B981]/10 border-[#10B981]/25', icon: CheckCircle2 }
  }
  if (['failed', 'error', 'blocked', 'risk'].includes(normalized)) {
    return { label: '失败', className: 'text-[#EF4444] bg-[#EF4444]/10 border-[#EF4444]/25', icon: AlertTriangle }
  }
  if (['running', 'sending', 'processing'].includes(normalized)) {
    return { label: '执行中', className: 'text-[#3B82F6] bg-[#3B82F6]/10 border-[#3B82F6]/25', icon: Loader2 }
  }
  if (['needs_human', 'review', 'pending_review'].includes(normalized)) {
    return { label: '需人工', className: 'text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/25', icon: AlertTriangle }
  }
  if (['queued', 'pending', 'waiting'].includes(normalized)) {
    return { label: '排队中', className: 'text-[#A78BFA] bg-[#A78BFA]/10 border-[#A78BFA]/25', icon: Clock }
  }
  return { label: status ? String(status) : '未开始', className: 'text-[#94A3B8] bg-[#64748B]/10 border-[#64748B]/25', icon: Clock }
}

export function PageShell({
  title,
  subtitle,
  icon: Icon,
  children,
}: {
  title: string
  subtitle: string
  icon: LucideIcon
  children: ReactNode
}) {
  return (
    <div className="flex h-full flex-col overflow-auto bg-[#0B0F1A]">
      <div className="border-b border-[#1E293B] px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#6366F1]/15 text-[#818CF8]">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-[#F1F5F9]">{title}</h1>
            <p className="mt-1 text-sm text-[#64748B]">{subtitle}</p>
          </div>
        </div>
      </div>
      <div className="space-y-5 p-6">{children}</div>
    </div>
  )
}

export function MetricCard({
  label,
  value,
  icon: Icon,
  hint,
  tone = 'indigo',
}: {
  label: string
  value: string | number
  icon: LucideIcon
  hint?: string
  tone?: 'indigo' | 'green' | 'amber' | 'blue' | 'red'
}) {
  const tones = {
    indigo: 'text-[#818CF8] bg-[#6366F1]/12',
    green: 'text-[#10B981] bg-[#10B981]/12',
    amber: 'text-[#F59E0B] bg-[#F59E0B]/12',
    blue: 'text-[#38BDF8] bg-[#38BDF8]/12',
    red: 'text-[#EF4444] bg-[#EF4444]/12',
  }
  return (
    <div className="rounded-lg border border-[#1E293B] bg-[#111827]/80 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-[#64748B]">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-[#F1F5F9]">{value}</p>
        </div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${tones[tone]}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      {hint && <p className="mt-3 text-xs text-[#64748B]">{hint}</p>}
    </div>
  )
}

export function Panel({
  title,
  description,
  action,
  children,
}: {
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="rounded-lg border border-[#1E293B] bg-[#111827]/80">
      <div className="flex items-start justify-between gap-4 border-b border-[#1E293B] px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-[#F1F5F9]">{title}</h2>
          {description && <p className="mt-1 text-xs text-[#64748B]">{description}</p>}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

export function StatusPill({ status }: { status?: string }) {
  const config = statusTone(status)
  const Icon = config.icon
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs ${config.className}`}>
      <Icon className={`h-3 w-3 ${Icon === Loader2 ? 'animate-spin' : ''}`} />
      {config.label}
    </span>
  )
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center rounded-lg border border-dashed border-[#334155] bg-[#0B0F1A]/60 px-6 py-10 text-center">
      <p className="text-sm font-medium text-[#CBD5E1]">{title}</p>
      <p className="mt-2 max-w-md text-xs leading-5 text-[#64748B]">{description}</p>
    </div>
  )
}

export function FieldLabel({ children }: { children: ReactNode }) {
  return <label className="mb-2 block text-xs font-medium text-[#94A3B8]">{children}</label>
}

export const inputClass = 'w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-sm text-[#F1F5F9] outline-none transition-colors placeholder:text-[#475569] focus:border-[#6366F1]'

export const buttonPrimary = 'inline-flex items-center justify-center gap-2 rounded-lg bg-[#6366F1] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#5558E6] disabled:cursor-not-allowed disabled:opacity-50'

export const buttonSecondary = 'inline-flex items-center justify-center gap-2 rounded-lg border border-[#334155] bg-[#0B0F1A] px-3 py-2 text-sm font-medium text-[#CBD5E1] transition-colors hover:border-[#6366F1] hover:text-white disabled:cursor-not-allowed disabled:opacity-50'
