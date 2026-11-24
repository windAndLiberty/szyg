import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, CheckCircle2, Clock3, Loader2, PauseCircle, XCircle } from 'lucide-react'
import type { WorkflowInstanceStatus, WorkflowRunStatus } from './workflowApi'
import { translateCurrent } from '@/lib/i18n'

export const panelClass = 'rounded-lg border border-border bg-card/80'
export const inputClass = 'w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-[#6366F1]'
export const primaryButton = 'inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:brightness-90 disabled:cursor-not-allowed disabled:opacity-45'
export const secondaryButton = 'inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-medium text-foreground transition-colors hover:border-[#6366F1] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-45'
export const iconButton = 'inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground transition-colors hover:border-[#6366F1] hover:text-foreground disabled:opacity-40'

const workflowTemplateNames: Record<string, string> = {
  content_scheduled_publish: '内容定时发布',
  account_health_check: '渠道账号巡检',
  customer_followup_reminder: '客户跟进提醒',
  lead_daily_digest: '线索整理日报',
  geo_weekly_audit: '每周检查AI是否推荐我的企业',
}

const historicalRunNames: Record<string, string> = {
  '人工确认流程验收': '人工确认流程验收',
  '每日渠道账号巡检验收': '每日渠道账号巡检验收',
}

/** Localize built-in workflow labels while leaving custom task names untouched. */
export function workflowRunName(item: { template_id?: string; instance_name?: string }) {
  const source = workflowTemplateNames[item.template_id || ''] || historicalRunNames[item.instance_name || '']
  return source ? translateCurrent(source) : (item.instance_name || translateCurrent('工作流任务'))
}

export function WorkflowPage({ subtitle, children }: { subtitle: string; children: ReactNode }) {
  return (
    <div className="flex h-full flex-col overflow-auto bg-background">
      <div className="border-b border-border px-6 py-5 text-sm text-muted-foreground">{subtitle}</div>
      <div className="space-y-5 p-6">{children}</div>
    </div>
  )
}

export function Metric({ label, value, icon: Icon, tone = 'indigo', hint }: { label: string; value: number | string; icon: LucideIcon; tone?: 'indigo' | 'green' | 'amber' | 'blue'; hint?: string }) {
  const colors = {
    indigo: 'bg-[#6366F1]/12 text-accent-ink',
    green: 'bg-[#10B981]/12 text-success-ink',
    amber: 'bg-[#F59E0B]/12 text-warning-ink',
    blue: 'bg-[#38BDF8]/12 text-info-ink',
  }
  return (
    <div className={`${panelClass} p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold text-foreground">{value}</p></div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${colors[tone]}`}><Icon className="h-4 w-4" /></div>
      </div>
      {hint && <p className="mt-3 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

const statusMap: Record<string, { label: string; className: string; icon: LucideIcon }> = {
  draft: { get label() { return translateCurrent("待启用") }, className: 'border-border bg-muted/15 text-muted-foreground', icon: Clock3 },
  active: { get label() { return translateCurrent("已启用") }, className: 'border-[#10B981]/25 bg-[#10B981]/10 text-success-ink', icon: CheckCircle2 },
  queued: { get label() { return translateCurrent("排队中") }, className: 'border-[#6366F1]/25 bg-[#6366F1]/10 text-accent-ink', icon: Clock3 },
  running: { get label() { return translateCurrent("执行中") }, className: 'border-[#38BDF8]/25 bg-[#38BDF8]/10 text-info-ink', icon: Loader2 },
  success: { get label() { return translateCurrent("已完成") }, className: 'border-[#10B981]/25 bg-[#10B981]/10 text-success-ink', icon: CheckCircle2 },
  paused: { get label() { return translateCurrent("已暂停") }, className: 'border-[#F59E0B]/25 bg-[#F59E0B]/10 text-warning-ink', icon: PauseCircle },
  needs_human: { get label() { return translateCurrent("需处理") }, className: 'border-[#F59E0B]/25 bg-[#F59E0B]/10 text-warning-ink', icon: AlertTriangle },
  failed: { get label() { return translateCurrent("失败") }, className: 'border-[#EF4444]/25 bg-[#EF4444]/10 text-danger-ink', icon: XCircle },
  cancelled: { get label() { return translateCurrent("已取消") }, className: 'border-border bg-muted/15 text-muted-foreground', icon: XCircle },
  disabled: { get label() { return translateCurrent("已停用") }, className: 'border-border bg-muted/15 text-muted-foreground', icon: XCircle },
}

export function WorkflowStatus({ status }: { status: WorkflowInstanceStatus | WorkflowRunStatus | string }) {
  const config = statusMap[status] || statusMap.draft
  const Icon = config.icon
  return <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs ${config.className}`}><Icon className={`h-3 w-3 ${status === 'running' ? 'animate-spin' : ''}`} />{config.label}</span>
}

export function Empty({ title, description }: { title: string; description: string }) {
  return <div className="flex min-h-40 flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background/50 px-6 py-10 text-center"><p className="text-sm font-medium text-foreground">{title}</p><p className="mt-2 max-w-md text-xs leading-5 text-muted-foreground">{description}</p></div>
}

export function Section({ title, description, action, children }: { title: string; description?: string; action?: ReactNode; children: ReactNode }) {
  return <section className={panelClass}><div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4"><div><h2 className="text-sm font-semibold text-foreground">{title}</h2>{description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}</div>{action}</div><div className="p-5">{children}</div></section>
}

export function formatWorkflowTime(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function scheduleLabel(schedule?: { type?: string; time?: string; weekdays?: number[]; interval_minutes?: number; at?: string; label?: string }) {
  if (!schedule) return translateCurrent("手动运行")
  if (schedule.label) return schedule.label
  if (schedule.type === 'daily') return translateCurrent("每天 {v0}", { v0: schedule.time || '09:00' })
  if (schedule.type === 'weekly') return translateCurrent("每周 {v0}", { v0: schedule.time || '09:00' })
  if (schedule.type === 'interval') return translateCurrent("每 {v0} 分钟", { v0: schedule.interval_minutes || 60 })
  if (schedule.type === 'once') return schedule.at ? translateCurrent("一次 · {v0}", { v0: formatWorkflowTime(schedule.at) }) : translateCurrent("指定时间")
  return translateCurrent("手动运行")
}
