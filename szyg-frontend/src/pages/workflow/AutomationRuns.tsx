import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import {
  AlertTriangle, CalendarClock, CheckCircle2, ChevronLeft, ChevronRight, Clock3,
  Eye, Loader2, Pause, Play, RotateCcw, Search, Settings2, X, XCircle,
} from 'lucide-react'
import {
  confirmWorkflowRun, controlWorkflowRun, runWorkflowInstance, updateWorkflowInstance,
  updateWorkflowSchedule, workflowInstances, workflowRunDetail, workflowRuns,
  type WorkflowInstance, type WorkflowRun, type WorkflowSchedule,
} from './workflowApi'
import {
  Empty, Metric, Section, WorkflowPage, WorkflowStatus, formatWorkflowTime, iconButton,
  inputClass, primaryButton, scheduleLabel, secondaryButton, workflowRunName,
} from './WorkflowShared'
import { ScheduleEditor } from './AutomationPlans'
import { useI18n } from '@/lib/i18n'

const PAGE_SIZE = 10

export default function AutomationRuns() {
  const { t } = useI18n()
  const [params] = useSearchParams()
  const focusedInstance = params.get('instance') || ''
  const [instances, setInstances] = useState<WorkflowInstance[]>([])
  const [runs, setRuns] = useState<WorkflowRun[]>([])
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<WorkflowInstance | null>(null)
  const [schedule, setSchedule] = useState<WorkflowSchedule>({ type: 'manual' })
  const [detail, setDetail] = useState<Awaited<ReturnType<typeof workflowRunDetail>> | null>(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [instanceData, runData] = await Promise.all([workflowInstances(), workflowRuns(200)])
      setInstances(instanceData.items || [])
      setRuns(runData.items || [])
    } catch (e) { setError(e instanceof Error ? e.message : t("运行计划加载失败")) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const filteredRuns = useMemo(() => runs.filter((item) => {
    const q = search.trim().toLowerCase()
    return (!focusedInstance || item.instance_id === focusedInstance)
      && (status === 'all' || item.status === status)
      && (!q || `${item.instance_name} ${workflowRunName(item)} ${item.error_message || ''}`.toLowerCase().includes(q))
  }), [runs, search, status, focusedInstance])
  const pages = Math.max(1, Math.ceil(filteredRuns.length / PAGE_SIZE))
  const visibleRuns = filteredRuns.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  useEffect(() => { setPage(1) }, [search, status, focusedInstance])

  const toggle = async (item: WorkflowInstance) => {
    setWorking(`toggle:${item.id}`)
    try { await updateWorkflowInstance(item.id, { status: item.status === 'active' ? 'paused' : 'active' }); await load() }
    catch (e) { setError(e instanceof Error ? e.message : t("计划状态更新失败")) }
    finally { setWorking('') }
  }
  const runNow = async (item: WorkflowInstance) => {
    setWorking(`run:${item.id}`)
    try { await runWorkflowInstance(item.id); await load() }
    catch (e) { setError(e instanceof Error ? e.message : t("立即运行失败")) }
    finally { setWorking('') }
  }
  const saveSchedule = async () => {
    if (!editing) return
    setWorking(`schedule:${editing.id}`)
    try { await updateWorkflowSchedule(editing.id, schedule); setEditing(null); await load() }
    catch (e) { setError(e instanceof Error ? e.message : t("运行时间更新失败")) }
    finally { setWorking('') }
  }
  const runAction = async (item: WorkflowRun, action: 'pause' | 'resume' | 'retry' | 'cancel') => {
    setWorking(`${action}:${item.id}`)
    try { await controlWorkflowRun(item.id, action); await load(); if (detail?.run.id === item.id) await openDetail(item) }
    catch (e) { setError(e instanceof Error ? e.message : t("任务操作失败")) }
    finally { setWorking('') }
  }
  const confirmRun = async (item: WorkflowRun) => {
    setWorking(`confirm:${item.id}`)
    try { await confirmWorkflowRun(item.id); await load(); setDetail(null) }
    catch (e) { setError(e instanceof Error ? e.message : t("确认任务失败")) }
    finally { setWorking('') }
  }
  const openDetail = async (item: WorkflowRun) => {
    setWorking(`detail:${item.id}`)
    try { setDetail(await workflowRunDetail(item.id)) }
    catch (e) { setError(e instanceof Error ? e.message : t("执行详情加载失败")) }
    finally { setWorking('') }
  }

  const running = runs.filter((item) => ['queued', 'running'].includes(item.status)).length
  const needsHuman = runs.filter((item) => item.status === 'needs_human').length
  const today = new Date().toLocaleDateString('en-CA')
  const completed = runs.filter((item) => item.status === 'success' && String(item.finished_at || '').slice(0, 10) === today).length

  return <WorkflowPage subtitle={t("安排工作流运行时间，查看每次执行进度，并及时处理需要确认的事项。")}>
    {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><Metric label={t("运行计划")} value={instances.length} icon={CalendarClock} /><Metric label={t("执行中")} value={running} icon={Clock3} tone="blue" /><Metric label={t("今日完成")} value={completed} icon={CheckCircle2} tone="green" /><Metric label={t("需要处理")} value={needsHuman} icon={AlertTriangle} tone="amber" /></div>

    <Section title={t("运行计划")} description={t("在这里统一调整运行时间；暂停不会删除方案配置。")}>
      {loading ? <Loading /> : instances.length === 0 ? <Empty title={t("暂无运行计划")} description={t("先在工作流方案页面启用一项岗位任务。")} /> : <div className="grid gap-3 lg:grid-cols-2">{instances.map((item) => <div key={item.id} className={`rounded-lg border bg-[#0B0F1A] p-4 ${focusedInstance === item.id ? 'border-[#6366F1]' : 'border-[#273449]'}`}><div className="flex items-start justify-between gap-3"><div><p className="font-medium text-[#F1F5F9]">{item.name}</p><p className="mt-1 text-xs text-[#64748B]">{item.template_name}</p></div><WorkflowStatus status={item.status} /></div><div className="mt-4 grid grid-cols-2 gap-3 text-xs"><div className="rounded-lg bg-[#111827] p-3"><p className="text-[#64748B]">{t("执行频率")}</p><p className="mt-1 text-[#CBD5E1]">{scheduleLabel(item.schedule)}</p></div><div className="rounded-lg bg-[#111827] p-3"><p className="text-[#64748B]">{t("下次运行")}</p><p className="mt-1 text-[#CBD5E1]">{formatWorkflowTime(item.next_run_at)}</p></div></div><div className="mt-4 flex justify-end gap-2"><button onClick={() => { setEditing(item); setSchedule(item.schedule) }} className={iconButton} title={t("调整运行时间")}><Settings2 className="h-4 w-4" /></button><button onClick={() => runNow(item)} className={iconButton} title={t("立即运行")}>{working === `run:${item.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}</button><button onClick={() => toggle(item)} className={iconButton} title={item.status === 'active' ? t("暂停计划") : t("继续计划")}>{working === `toggle:${item.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : item.status === 'active' ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}</button></div></div>)}</div>}
    </Section>

    <Section title={t("执行记录")} description={t("每次运行都保留步骤状态、耗时和可解释的失败原因。")}>
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><div className="flex flex-wrap gap-2">{[['all', t("全部")], ['running', t("执行中")], ['success', t("已完成")], ['failed', t("失败")], ['needs_human', t("需处理")]].map(([value, label]) => <button key={value} onClick={() => setStatus(value)} className={`rounded-lg border px-3 py-2 text-xs ${status === value ? 'border-[#6366F1] bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#273449] text-[#94A3B8]'}`}>{label}</button>)}</div><div className="relative w-full md:w-64"><Search className="absolute left-3 top-2.5 h-4 w-4 text-[#475569]" /><input value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputClass} pl-9`} placeholder={t("查找任务记录")} /></div></div>
      {visibleRuns.length === 0 ? <Empty title={t("暂无执行记录")} description={t("启用方案并运行后，执行结果会出现在这里。")} /> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="text-xs text-[#64748B]"><tr className="border-b border-[#1E293B]"><th className="pb-3">{t("任务")}</th><th className="pb-3">{t("状态")}</th><th className="pb-3">{t("开始时间")}</th><th className="pb-3">{t("耗时")}</th><th className="pb-3">{t("结果说明")}</th><th className="pb-3 text-right">{t("操作")}</th></tr></thead><tbody className="divide-y divide-[#1E293B]">{visibleRuns.map((item) => <tr key={item.id} className="cursor-pointer hover:bg-[#0B0F1A]/60" onClick={() => openDetail(item)}><td className="py-4"><p className="font-medium text-[#F1F5F9]">{workflowRunName(item)}</p><p className="mt-1 text-xs text-[#64748B]">{item.current_step_id ? t("当前：{v0}", { v0: item.current_step_id }) : t("标准流程执行")}</p></td><td className="py-4"><WorkflowStatus status={item.status} /></td><td className="py-4 text-[#94A3B8]">{formatWorkflowTime(item.started_at || item.created_at)}</td><td className="py-4 text-[#CBD5E1]">{item.duration_ms ? t("{v0} 秒", { v0: Math.max(1, Math.round(item.duration_ms / 1000)) }) : '—'}</td><td className="max-w-xs py-4 text-[#94A3B8]"><span className="line-clamp-2">{item.error_message || (item.status === 'success' ? t("任务已按标准流程完成") : t("等待执行结果"))}</span></td><td className="py-4"><div className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}><button onClick={() => openDetail(item)} className={iconButton} title={t("查看详情")}>{working === `detail:${item.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}</button>{item.status === 'needs_human' && Boolean(item.result?.pending_step) && <button onClick={() => confirmRun(item)} className={primaryButton}>{t("确认继续")}</button>}{['failed', 'paused'].includes(item.status) && <button onClick={() => runAction(item, 'retry')} className={iconButton} title={t("重试")}><RotateCcw className="h-4 w-4" /></button>}{['queued', 'running'].includes(item.status) && <button onClick={() => runAction(item, 'cancel')} className={iconButton} title={t("取消")}><XCircle className="h-4 w-4" /></button>}</div></td></tr>)}</tbody></table></div>}
      {filteredRuns.length > PAGE_SIZE && <div className="mt-5 flex items-center justify-between border-t border-[#1E293B] pt-4 text-xs text-[#64748B]"><span>{t("共")} {filteredRuns.length}  {t("条记录")}</span><div className="flex items-center gap-2"><button onClick={() => setPage((v) => Math.max(1, v - 1))} disabled={page === 1} className={iconButton}><ChevronLeft className="h-4 w-4" /></button><span>{page} / {pages}</span><button onClick={() => setPage((v) => Math.min(pages, v + 1))} disabled={page === pages} className={iconButton}><ChevronRight className="h-4 w-4" /></button></div></div>}
    </Section>

    {editing && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4" onMouseDown={(e) => { if (e.currentTarget === e.target) setEditing(null) }}><div className="w-full max-w-lg rounded-lg border border-[#273449] bg-[#0F1624] p-6 shadow-2xl"><div className="flex items-start justify-between"><div><p className="text-xs text-[#818CF8]">{t("调整运行时间")}</p><h2 className="mt-1 text-lg font-semibold text-[#F1F5F9]">{editing.name}</h2></div><button onClick={() => setEditing(null)} className={iconButton}><X className="h-4 w-4" /></button></div><div className="mt-6"><ScheduleEditor value={schedule} onChange={setSchedule} /></div><div className="mt-6 flex gap-3"><button onClick={() => setEditing(null)} className={`${secondaryButton} flex-1`}>{t("取消")}</button><button onClick={saveSchedule} className={`${primaryButton} flex-1`}>{working === `schedule:${editing.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}{t("保存计划")}</button></div></div></div>}
    {detail && <RunDetail detail={detail} onClose={() => setDetail(null)} onConfirm={() => confirmRun(detail.run)} />}
  </WorkflowPage>
}

function Loading() { return <div className="flex h-40 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-[#64748B]" /></div> }

function RunDetail({ detail, onClose, onConfirm }: { detail: Awaited<ReturnType<typeof workflowRunDetail>>; onClose: () => void; onConfirm: () => void }) {
  const { t } = useI18n();

  return <div className="fixed inset-0 z-50 flex justify-end bg-black/55" onMouseDown={(e) => { if (e.currentTarget === e.target) onClose() }}><aside className="h-full w-full max-w-xl overflow-y-auto border-l border-[#273449] bg-[#0F1624] shadow-2xl"><div className="sticky top-0 z-10 flex items-start justify-between border-b border-[#273449] bg-[#0F1624] px-6 py-5"><div><p className="text-xs text-[#818CF8]">{t("执行详情")}</p><h2 className="mt-1 text-lg font-semibold text-[#F1F5F9]">{workflowRunName(detail.run)}</h2><div className="mt-2"><WorkflowStatus status={detail.run.status} /></div></div><button onClick={onClose} className={iconButton}><X className="h-4 w-4" /></button></div><div className="space-y-6 p-6"><div className="grid grid-cols-2 gap-3 text-xs"><div className="rounded-lg bg-[#0B0F1A] p-3"><p className="text-[#64748B]">{t("开始时间")}</p><p className="mt-1 text-[#CBD5E1]">{formatWorkflowTime(detail.run.started_at || detail.run.created_at)}</p></div><div className="rounded-lg bg-[#0B0F1A] p-3"><p className="text-[#64748B]">{t("耗时")}</p><p className="mt-1 text-[#CBD5E1]">{detail.run.duration_ms ? t("{v0} 秒", { v0: Math.max(1, Math.round(detail.run.duration_ms / 1000)) }) : '—'}</p></div></div><div><h3 className="mb-3 text-sm font-medium text-[#E2E8F0]">{t("步骤时间线")}</h3><div className="space-y-3">{detail.steps.length === 0 ? <p className="text-xs text-[#64748B]">{t("尚未产生执行步骤")}</p> : detail.steps.map((step, index) => <div key={String(step.id || index)} className="flex gap-3 rounded-lg border border-[#273449] bg-[#0B0F1A] p-4"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#6366F1]/15 text-xs text-[#C7D2FE]">{index + 1}</span><div><p className="text-sm text-[#E2E8F0]">{String(step.name || step.step_id || t("执行步骤"))}</p><p className="mt-1 text-xs text-[#64748B]">{String(step.error_message || step.status || '')}</p></div></div>)}</div></div>{detail.run.error_message && <div className="rounded-lg border border-[#EF4444]/25 bg-[#EF4444]/8 p-4 text-sm text-[#FCA5A5]">{detail.run.error_message}</div>}{detail.run.status === 'needs_human' && Boolean(detail.run.result?.pending_step) && <button onClick={onConfirm} className={`${primaryButton} w-full`}>{t("确认并继续")}</button>}</div></aside></div>
}
