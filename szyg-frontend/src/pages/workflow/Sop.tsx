import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, ChevronRight, ClipboardList, Copy, History, Loader2, Save, Search, ShieldCheck, X } from 'lucide-react'
import { cloneWorkflowSop, updateWorkflowSop, workflowSops, type WorkflowSop, type WorkflowStep } from './workflowApi'
import { Empty, Metric, Section, WorkflowPage, WorkflowStatus, formatWorkflowTime, iconButton, inputClass, panelClass, primaryButton } from './WorkflowShared'
import { translateCurrent, useI18n } from '@/lib/i18n'

const categories: Record<string, string> = { get all() { return translateCurrent("全部流程") }, get content_operations() { return translateCurrent("内容运营") }, get channel_operations() { return translateCurrent("渠道运营") }, get customer_operations() { return translateCurrent("客户运营") }, get data_operations() { return translateCurrent("数据整理") } }

export default function Sop() {
  const { t } = useI18n()
  const [items, setItems] = useState<WorkflowSop[]>([])
  const [selected, setSelected] = useState<WorkflowSop | null>(null)
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editSteps, setEditSteps] = useState<WorkflowStep[]>([])

  const load = async () => {
    setLoading(true); setError('')
    try { const data = await workflowSops(); setItems(data.items || []) }
    catch (e) { setError(e instanceof Error ? e.message : t("标准流程加载失败")) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const filtered = useMemo(() => items.filter((item) => {
    const q = search.trim().toLowerCase()
    return (category === 'all' || item.category === category) && (!q || `${item.name}${item.description}`.toLowerCase().includes(q))
  }), [items, category, search])

  const clone = async (item: WorkflowSop) => {
    setWorking(item.id)
    try { const created = await cloneWorkflowSop(item.id); await load(); openDetail(created) }
    catch (e) { setError(e instanceof Error ? e.message : t("复制流程失败")) }
    finally { setWorking('') }
  }

  const openDetail = (item: WorkflowSop) => {
    setSelected(item)
    setEditName(item.name)
    setEditDescription(item.description)
    setEditSteps(item.steps.map((step) => ({ ...step })))
  }

  const save = async () => {
    if (!selected || selected.source !== 'custom' || !editName.trim()) return
    setWorking(`save:${selected.id}`)
    try {
      const updated = await updateWorkflowSop(selected.id, { name: editName.trim(), description: editDescription.trim(), steps: editSteps })
      setSelected(updated)
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : t("保存流程失败")) }
    finally { setWorking('') }
  }

  const custom = items.filter((item) => item.source === 'custom').length
  const confirmations = items.reduce((sum, item) => sum + item.steps.filter((step) => step.requires_confirmation).length, 0)
  const executions = items.reduce((sum, item) => sum + Number(item.execution_count || 0), 0)

  return (
    <WorkflowPage subtitle={t("用清晰的标准步骤约束自动执行，关键外部动作保留人工确认。")}>
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric label={t("标准流程")} value={items.length} icon={ClipboardList} />
        <Metric label={t("我的流程")} value={custom} icon={Copy} tone="blue" />
        <Metric label={t("人工确认点")} value={confirmations} icon={ShieldCheck} tone="amber" />
        <Metric label={t("累计执行")} value={executions} icon={CheckCircle2} tone="green" />
      </div>
      <Section title={t("流程模板库")} description={t("内置模板保持稳定，只需复制后调整适合自己团队的步骤。")}>
        <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><div className="flex flex-wrap gap-2">{Object.entries(categories).map(([value, label]) => <button key={value} onClick={() => setCategory(value)} className={`rounded-lg border px-3 py-2 text-xs ${category === value ? 'border-[#6366F1] bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#273449] text-[#94A3B8]'}`}>{label}</button>)}</div><div className="relative w-full lg:w-72"><Search className="absolute left-3 top-2.5 h-4 w-4 text-[#475569]" /><input value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputClass} pl-9`} placeholder={t("搜索标准流程")} /></div></div>
        {loading ? <div className="flex h-48 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-[#64748B]" /></div> : filtered.length === 0 ? <Empty title={t("暂无标准流程")} description={t("调整筛选条件，或从工作流方案创建一个流程。")} /> : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{filtered.map((item) => <button key={item.id} onClick={() => openDetail(item)} className={`${panelClass} group p-5 text-left transition-all hover:-translate-y-0.5 hover:border-[#4F46E5]`}><div className="flex items-start justify-between"><span className={`rounded-full border px-2 py-1 text-xs ${item.source === 'builtin' ? 'border-[#6366F1]/25 bg-[#6366F1]/10 text-[#A5B4FC]' : 'border-[#38BDF8]/25 bg-[#38BDF8]/10 text-[#7DD3FC]'}`}>{item.source === 'builtin' ? t("系统模板") : t("我的流程")}</span><span className="text-xs text-[#64748B]">{item.category_label}</span></div><h3 className="mt-4 font-semibold text-[#F1F5F9]">{item.name}</h3><p className="mt-2 line-clamp-2 min-h-10 text-sm leading-5 text-[#94A3B8]">{item.description}</p><div className="mt-5 flex items-center justify-between border-t border-[#273449] pt-4 text-xs"><span className="text-[#64748B]">{item.steps.length}  {t("个步骤 · 执行")} {item.execution_count || 0}  {t("次")}</span><ChevronRight className="h-4 w-4 text-[#818CF8] transition-transform group-hover:translate-x-0.5" /></div></button>)}</div>
        )}
      </Section>
      {selected && <div className="fixed inset-0 z-50 flex justify-end bg-black/55" onMouseDown={(e) => { if (e.currentTarget === e.target) setSelected(null) }}><aside className="h-full w-full max-w-xl overflow-y-auto border-l border-[#273449] bg-[#0F1624] shadow-2xl"><div className="sticky top-0 z-10 flex items-start justify-between border-b border-[#273449] bg-[#0F1624] px-6 py-5"><div className="min-w-0 flex-1 pr-4"><p className="text-xs text-[#818CF8]">{selected.category_label} · {selected.source === 'builtin' ? t("系统模板") : t("我的流程")}</p>{selected.source === 'custom' ? <><input value={editName} onChange={(e) => setEditName(e.target.value)} className={`${inputClass} mt-3 font-semibold`} /><textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} rows={2} className={`${inputClass} mt-2 resize-none`} /></> : <><h2 className="mt-1 text-lg font-semibold text-[#F1F5F9]">{selected.name}</h2><p className="mt-2 text-sm leading-6 text-[#94A3B8]">{selected.description}</p></>}</div><button onClick={() => setSelected(null)} className={iconButton}><X className="h-4 w-4" /></button></div><div className="space-y-6 p-6"><div className="space-y-3">{(selected.source === 'custom' ? editSteps : selected.steps).map((step, index) => <div key={step.id} className="flex gap-3 rounded-lg border border-[#273449] bg-[#0B0F1A] p-4"><div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#6366F1]/15 text-xs text-[#C7D2FE]">{index + 1}</div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-medium text-[#E2E8F0]">{step.name}</p>{step.requires_confirmation && <span className="inline-flex items-center gap-1 rounded-full border border-[#F59E0B]/25 bg-[#F59E0B]/10 px-2 py-0.5 text-[11px] text-[#FBBF24]"><AlertTriangle className="h-3 w-3" />{t("人工确认")}</span>}</div>{selected.source === 'custom' ? <textarea value={step.description} onChange={(e) => setEditSteps((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, description: e.target.value } : row))} rows={2} className={`${inputClass} mt-2 resize-none text-xs`} /> : <p className="mt-1 text-xs leading-5 text-[#64748B]">{step.description}</p>}<p className="mt-2 text-[11px] text-[#475569]">{t("失败处理：")}{step.on_failure === 'retry' ? t("自动重试") : step.on_failure === 'skip' ? t("跳过继续") : step.on_failure === 'needs_human' ? t("暂停并人工处理") : t("停止流程")}</p></div></div>)}</div>{selected.recent_runs && selected.recent_runs.length > 0 && <div><div className="mb-3 flex items-center gap-2 text-sm font-medium text-[#E2E8F0]"><History className="h-4 w-4 text-[#818CF8]" />{t("最近执行")}</div><div className="space-y-2">{selected.recent_runs.map((run) => <div key={run.id} className="flex items-center justify-between rounded-lg border border-[#273449] bg-[#0B0F1A] px-3 py-3"><div><p className="text-xs text-[#CBD5E1]">{formatWorkflowTime(run.started_at || run.created_at)}</p><p className="mt-1 text-[11px] text-[#64748B]">{run.error_message || t("标准流程执行记录")}</p></div><WorkflowStatus status={run.status} /></div>)}</div></div>}{selected.source === 'builtin' ? <button onClick={() => clone(selected)} disabled={working === selected.id} className={`${primaryButton} w-full`}>{working === selected.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}{t("复制为我的流程")}</button> : <button onClick={save} disabled={working === `save:${selected.id}` || !editName.trim()} className={`${primaryButton} w-full`}>{working === `save:${selected.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t("保存流程")}</button>}</div></aside></div>}
    </WorkflowPage>
  )
}
