import { useEffect, useState } from 'react'
import { CheckCircle2, Loader2, ShieldCheck } from 'lucide-react'
import { confirmWorkflowRun, workflowRunDetail, workflowRuns, type WorkflowRun } from './workflowApi'
import { Empty, Section, WorkflowPage, WorkflowStatus, formatWorkflowTime, primaryButton } from './WorkflowShared'

export default function AutomationApprovals() {
  const [items, setItems] = useState<WorkflowRun[]>([])
  const [details, setDetails] = useState<Record<string, Awaited<ReturnType<typeof workflowRunDetail>>>>({})
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const load = async () => {
    try {
      const data = await workflowRuns(200)
      const pending = (data.items || []).filter((item) => item.status === 'needs_human')
      setItems(pending)
      const rows = await Promise.all(pending.map(async (item) => [item.id, await workflowRunDetail(item.id)] as const))
      setDetails(Object.fromEntries(rows))
    } catch (cause) { setError(cause instanceof Error ? cause.message : '待确认事项加载失败') }
  }
  useEffect(() => { load() }, [])
  const confirm = async (item: WorkflowRun) => {
    setWorking(item.id); setError('')
    try { await confirmWorkflowRun(item.id); await load() }
    catch (cause) { setError(cause instanceof Error ? cause.message : '确认失败') }
    finally { setWorking('') }
  }
  return <WorkflowPage subtitle="数字员工准备执行发送、发布或其他外部操作时，会在这里说明影响并等待确认。">
    {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
    <Section title="待我确认" description="确认前不会执行对应的外部操作。">
      {items.length === 0 ? <Empty title="当前没有待确认事项" description="数字员工可以继续完成低风险工作；需要你决定时会出现在这里。" /> : <div className="space-y-3">{items.map((item) => { const detail = details[item.id]; const pending = (item.result?.pending_step || {}) as Record<string, unknown>; return <article key={item.id} className="rounded-lg border border-[#F59E0B]/25 bg-[#F59E0B]/5 p-5"><div className="flex items-start gap-4"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#F59E0B]/12 text-[#FBBF24]"><ShieldCheck className="h-5 w-5" /></div><div className="flex-1"><div className="flex flex-wrap items-center gap-2"><p className="font-medium text-[#F1F5F9]">{item.instance_name}</p><WorkflowStatus status={item.status} /></div><p className="mt-2 text-sm leading-6 text-[#CBD5E1]">{String(pending.message || pending.name || item.error_message || '数字员工已准备好下一步，需要你确认后继续。')}</p><p className="mt-2 text-xs text-[#64748B]">发起时间 {formatWorkflowTime(item.created_at)} · 已完成 {detail?.steps.filter((step) => step.status === 'success').length || 0} 个前置步骤</p></div><button onClick={() => confirm(item)} disabled={Boolean(working)} className={primaryButton}>{working === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}确认并继续</button></div></article> })}</div>}
    </Section>
  </WorkflowPage>
}
