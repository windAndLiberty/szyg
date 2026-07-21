import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CalendarClock, CheckCircle2, ChevronLeft, ChevronRight, Clock3, History, Loader2, Pause, Play, RefreshCw, RotateCcw, Search, XCircle } from 'lucide-react'
import { confirmWorkflowRun, controlWorkflowRun, runWorkflowInstance, updateWorkflowInstance, workflowInstances, workflowRuns, type WorkflowInstance, type WorkflowRun } from './workflowApi'
import { Empty, Metric, Section, WorkflowPage, WorkflowStatus, formatWorkflowTime, iconButton, inputClass, scheduleLabel } from './WorkflowShared'

const PAGE_SIZE = 10

export default function Scheduler() {
  const [instances, setInstances] = useState<WorkflowInstance[]>([])
  const [runs, setRuns] = useState<WorkflowRun[]>([])
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)

  const load = async () => {
    setLoading(true); setError('')
    try {
      const [instanceData, runData] = await Promise.all([workflowInstances(), workflowRuns(100)])
      setInstances(instanceData.items || [])
      setRuns(runData.items || [])
    } catch (e) { setError(e instanceof Error ? e.message : '运行计划加载失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const filteredRuns = useMemo(() => runs.filter((item) => {
    const q = search.trim().toLowerCase()
    return (status === 'all' || item.status === status) && (!q || `${item.instance_name}${item.error_message || ''}`.toLowerCase().includes(q))
  }), [runs, search, status])
  const pages = Math.max(1, Math.ceil(filteredRuns.length / PAGE_SIZE))
  const visibleRuns = filteredRuns.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  useEffect(() => { setPage(1) }, [search, status])

  const toggle = async (item: WorkflowInstance) => {
    setWorking(item.id)
    try { await updateWorkflowInstance(item.id, { status: item.status === 'active' ? 'paused' : 'active' }); await load() }
    catch (e) { setError(e instanceof Error ? e.message : '计划状态更新失败') }
    finally { setWorking('') }
  }
  const runNow = async (item: WorkflowInstance) => {
    setWorking(`run:${item.id}`)
    try { await runWorkflowInstance(item.id); await load() }
    catch (e) { setError(e instanceof Error ? e.message : '立即运行失败') }
    finally { setWorking('') }
  }
  const runAction = async (item: WorkflowRun, action: 'pause' | 'resume' | 'retry' | 'cancel') => {
    setWorking(`${action}:${item.id}`)
    try { await controlWorkflowRun(item.id, action); await load() }
    catch (e) { setError(e instanceof Error ? e.message : '任务操作失败') }
    finally { setWorking('') }
  }
  const confirmRun = async (item: WorkflowRun) => {
    setWorking(`confirm:${item.id}`)
    try { await confirmWorkflowRun(item.id); await load() }
    catch (e) { setError(e instanceof Error ? e.message : '确认任务失败') }
    finally { setWorking('') }
  }

  const running = runs.filter((item) => ['queued', 'running'].includes(item.status)).length
  const needsHuman = runs.filter((item) => item.status === 'needs_human').length
  const completed = runs.filter((item) => item.status === 'success').length

  return (
    <WorkflowPage subtitle="集中管理运行时间、任务队列和执行结果，业务内容仍在工作流方案中配置。">
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric label="运行计划" value={instances.length} icon={CalendarClock} />
        <Metric label="执行中" value={running} icon={Clock3} tone="blue" />
        <Metric label="今日完成" value={completed} icon={CheckCircle2} tone="green" />
        <Metric label="需要处理" value={needsHuman} icon={AlertTriangle} tone="amber" />
      </div>

      <Section title="运行计划" description="暂停计划不会删除配置，恢复后会从下一次计划时间继续。" action={<button onClick={load} className={iconButton} title="刷新"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></button>}>
        {loading ? <div className="flex h-40 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-[#64748B]" /></div> : instances.length === 0 ? <Empty title="暂无运行计划" description="先在工作流方案页面启用一项岗位任务。" /> : (
          <div className="grid gap-3 lg:grid-cols-2">
            {instances.map((item) => (
              <div key={item.id} className="rounded-lg border border-[#273449] bg-[#0B0F1A] p-4">
                <div className="flex items-start justify-between gap-3"><div><p className="font-medium text-[#F1F5F9]">{item.name}</p><p className="mt-1 text-xs text-[#64748B]">{item.template_name}</p></div><WorkflowStatus status={item.status} /></div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-xs"><div className="rounded-lg bg-[#111827] p-3"><p className="text-[#64748B]">执行频率</p><p className="mt-1 text-[#CBD5E1]">{scheduleLabel(item.schedule)}</p></div><div className="rounded-lg bg-[#111827] p-3"><p className="text-[#64748B]">下次运行</p><p className="mt-1 text-[#CBD5E1]">{formatWorkflowTime(item.next_run_at)}</p></div></div>
                <div className="mt-4 flex justify-end gap-2"><button onClick={() => runNow(item)} className={iconButton} title="立即运行">{working === `run:${item.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}</button><button onClick={() => toggle(item)} className={iconButton} title={item.status === 'active' ? '暂停计划' : '继续计划'}>{working === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : item.status === 'active' ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}</button></div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="执行记录" description="每次触发都会留下真实状态、耗时和可解释的失败原因。">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2">{[['all', '全部'], ['running', '执行中'], ['success', '已完成'], ['failed', '失败'], ['needs_human', '需处理']].map(([value, label]) => <button key={value} onClick={() => setStatus(value)} className={`rounded-lg border px-3 py-2 text-xs ${status === value ? 'border-[#6366F1] bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#273449] text-[#94A3B8]'}`}>{label}</button>)}</div>
          <div className="relative w-full md:w-64"><Search className="absolute left-3 top-2.5 h-4 w-4 text-[#475569]" /><input value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputClass} pl-9`} placeholder="查找任务记录" /></div>
        </div>
        {visibleRuns.length === 0 ? <Empty title="暂无执行记录" description="启用方案并运行后，执行结果会出现在这里。" /> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="text-xs text-[#64748B]"><tr className="border-b border-[#1E293B]"><th className="pb-3 font-medium">任务</th><th className="pb-3 font-medium">状态</th><th className="pb-3 font-medium">开始时间</th><th className="pb-3 font-medium">耗时</th><th className="pb-3 font-medium">结果说明</th><th className="pb-3 text-right font-medium">操作</th></tr></thead><tbody className="divide-y divide-[#1E293B]">{visibleRuns.map((item) => <tr key={item.id}><td className="py-4"><p className="font-medium text-[#F1F5F9]">{item.instance_name}</p><p className="mt-1 text-xs text-[#64748B]">{item.current_step_id ? `当前：${item.current_step_id}` : '标准流程执行'}</p></td><td className="py-4"><WorkflowStatus status={item.status} /></td><td className="py-4 text-[#94A3B8]">{formatWorkflowTime(item.started_at || item.created_at)}</td><td className="py-4 text-[#CBD5E1]">{item.duration_ms ? `${Math.max(1, Math.round(item.duration_ms / 1000))} 秒` : '—'}</td><td className="max-w-xs py-4 text-[#94A3B8]"><span className="line-clamp-2">{item.error_message || (item.status === 'success' ? '任务已按标准流程完成' : '等待执行结果')}</span></td><td className="py-4"><div className="flex justify-end gap-2">{item.status === 'needs_human' && Boolean(item.result?.pending_step) && <button onClick={() => confirmRun(item)} className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-[#6366F1] px-3 text-xs text-white hover:bg-[#4F46E5]">{working === `confirm:${item.id}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}确认继续</button>}{['failed', 'paused'].includes(item.status) && <button onClick={() => runAction(item, 'retry')} className={iconButton} title="重试">{working === `retry:${item.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}</button>}{['queued', 'running'].includes(item.status) && <button onClick={() => runAction(item, 'cancel')} className={iconButton} title="取消"><XCircle className="h-4 w-4" /></button>}</div></td></tr>)}</tbody></table></div>
        )}
        {filteredRuns.length > PAGE_SIZE && <div className="mt-5 flex items-center justify-between border-t border-[#1E293B] pt-4 text-xs text-[#64748B]"><span>共 {filteredRuns.length} 条记录</span><div className="flex items-center gap-2"><button onClick={() => setPage((v) => Math.max(1, v - 1))} disabled={page === 1} className={iconButton}><ChevronLeft className="h-4 w-4" /></button><span>{page} / {pages}</span><button onClick={() => setPage((v) => Math.min(pages, v + 1))} disabled={page === pages} className={iconButton}><ChevronRight className="h-4 w-4" /></button></div></div>}
      </Section>
    </WorkflowPage>
  )
}
