import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Clock3, Loader2, Search } from 'lucide-react'
import { workflowRuns, type WorkflowRun } from './workflowApi'
import { Empty, Metric, Section, WorkflowPage, WorkflowStatus, formatWorkflowTime, inputClass, workflowRunName } from './WorkflowShared'
import { translateCurrent, useI18n } from '@/lib/i18n'

export default function AutomationHistory() {
  const { t } = useI18n()
  const [runs, setRuns] = useState<WorkflowRun[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => { workflowRuns(200).then((data) => setRuns(data.items || [])).catch((cause) => setError(cause instanceof Error ? cause.message : t("执行记录加载失败"))).finally(() => setLoading(false)) }, [])
  const visible = useMemo(() => runs.filter((item) => !search || `${item.instance_name} ${workflowRunName(item)}`.toLowerCase().includes(search.toLowerCase())), [runs, search])
  const successful = runs.filter((item) => item.status === 'success').length
  return <WorkflowPage subtitle={t("用业务结果说明数字员工完成了什么、发现了什么，以及是否需要处理。")}>
    {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
    <div className="grid gap-4 md:grid-cols-3"><Metric label={t("已完成")} value={successful} icon={CheckCircle2} tone="green" /><Metric label={t("执行中")} value={runs.filter((item) => ['queued', 'running'].includes(item.status)).length} icon={Clock3} tone="blue" /><Metric label={t("需要处理")} value={runs.filter((item) => ['needs_human', 'failed'].includes(item.status)).length} icon={AlertTriangle} tone="amber" /></div>
    <Section title={t("最近执行结果")} description={t("内部步骤和技术日志仍会保留在审计数据中，默认只展示业务结果。")} action={<div className="relative"><Search className="absolute left-3 top-2.5 h-4 w-4 text-[#64748B]" /><input value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputClass} h-9 w-56 pl-9`} placeholder={t("搜索任务")} /></div>}>
      {loading ? <div className="flex h-40 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-[#818CF8]" /></div> : visible.length === 0 ? <Empty title={t("暂无执行记录")} description={t("自动任务运行后，完成结果会出现在这里。")} /> : <div className="space-y-3">{visible.map((item) => <article key={item.id} className="flex flex-col gap-3 rounded-lg border border-[#273449] bg-[#0B0F1A] p-4 lg:flex-row lg:items-center"><div className="min-w-0 flex-1"><p className="font-medium text-[#F1F5F9]">{workflowRunName(item)}</p><p className="mt-1 text-sm text-[#94A3B8]">{businessResult(item)}</p><p className="mt-2 text-xs text-[#64748B]">{formatWorkflowTime(item.started_at || item.created_at)}{item.duration_ms ? t("· 用时 {v0} 秒", { v0: Math.max(1, Math.round(item.duration_ms / 1000)) }) : ''}</p></div><WorkflowStatus status={item.status} /></article>)}</div>}
    </Section>
  </WorkflowPage>
}

function businessResult(item: WorkflowRun) {
  if (item.error_message) return item.error_message
  if (item.status === 'success') {
    if (item.template_id === 'geo_weekly_audit') return translateCurrent("已完成AI品牌推荐检查，结果已进入GEO工作台。")
    if (item.template_id === 'customer_followup_reminder') return translateCurrent("已整理需要继续推进的客户。")
    if (item.template_id === 'lead_daily_digest') return translateCurrent("已整理新增线索和意向情况。")
    return translateCurrent("数字员工已完成本次任务。")
  }
  if (item.status === 'needs_human') return translateCurrent("数字员工已完成准备工作，正在等待你的确认。")
  if (['queued', 'running'].includes(item.status)) return translateCurrent("数字员工正在处理，请稍后查看结果。")
  return translateCurrent("本次任务尚未形成可用结果。")
}
