import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import {
  AlertTriangle, ArrowDown, ArrowUp, Check, CheckCircle2, ChevronLeft, ChevronRight,
  ClipboardCheck, Copy, FileBarChart, GitBranch, Loader2, Plus, Save, Search,
  Send, ShieldCheck, Sparkles, Trash2, Users, X,
} from 'lucide-react'
import {
  cloneWorkflowSop, createWorkflowInstance, deleteWorkflowInstance, deleteWorkflowSop, updateWorkflowInstance,
  updateWorkflowSop, upgradeWorkflowInstance, workflowCapabilities, workflowInstances,
  workflowOverview, workflowSops, workflowTemplates,
  type WorkflowCapability, type WorkflowInstance, type WorkflowOverview, type WorkflowSchedule,
  type WorkflowSop, type WorkflowStep, type WorkflowTemplate,
} from './workflowApi'
import {
  Empty, Metric, Section, WorkflowPage, WorkflowStatus, formatWorkflowTime, iconButton,
  inputClass, panelClass, primaryButton, scheduleLabel, secondaryButton,
} from './WorkflowShared'
import WorkflowDesigner from './WorkflowDesigner'
import { translateCurrent, useI18n } from '@/lib/i18n'

type View = 'library' | 'mine' | 'standards'
type Source = {
  id: string
  templateId?: string
  definitionId?: string
  name: string
  description: string
  outcome?: string
  categoryLabel: string
  available: boolean
  steps: WorkflowStep[]
}

const categoryLabels: Record<string, string> = {
  get all() { return translateCurrent("全部方案") }, get content_operations() { return translateCurrent("内容运营") }, get channel_operations() { return translateCurrent("渠道运营") },
  get customer_operations() { return translateCurrent("客户运营") }, get data_operations() { return translateCurrent("数据整理") },
}
const templateIcons = { send: Send, shield: ShieldCheck, users: Users, report: FileBarChart }
const defaultOverview: WorkflowOverview = { templates: 0, active_instances: 0, running: 0, needs_human: 0, success_today: 0 }
const views: Array<{ id: View; label: string }> = [
  { id: 'library', get label() { return translateCurrent("方案库") } }, { id: 'mine', get label() { return translateCurrent("我的工作流") } }, { id: 'standards', get label() { return translateCurrent("标准流程") } },
]
const contextOptions = [
  ['knowledge', '企业资料'], ['accounts', '渠道账号'], ['leads', '客户线索'],
  ['materials', '素材内容'], ['publish_records', '发布记录'],
] as const

export default function AutomationPlans() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const initialView = params.get('view') === 'standards' ? 'standards' : params.get('view') === 'mine' ? 'mine' : 'library'
  const [view, setView] = useState<View>(initialView)
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [instances, setInstances] = useState<WorkflowInstance[]>([])
  const [standards, setStandards] = useState<WorkflowSop[]>([])
  const [capabilities, setCapabilities] = useState<WorkflowCapability[]>([])
  const [overview, setOverview] = useState(defaultOverview)
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [designer, setDesigner] = useState<'ai' | 'manual' | null>(null)
  const [source, setSource] = useState<Source | null>(null)
  const [stage, setStage] = useState(1)
  const [name, setName] = useState('')
  const [context, setContext] = useState<Record<string, boolean>>({ knowledge: true })
  const [schedule, setSchedule] = useState<WorkflowSchedule>({ type: 'daily', time: '09:00' })
  const [humanPolicy, setHumanPolicy] = useState<WorkflowInstance['human_policy']>('pause_on_risk')
  const [selectedStandard, setSelectedStandard] = useState<WorkflowSop | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editSteps, setEditSteps] = useState<WorkflowStep[]>([])
  const [newAction, setNewAction] = useState('')

  const showToast = (message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 2600)
  }

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [templateData, instanceData, overviewData, capabilityData, sopData] = await Promise.all([
        workflowTemplates(), workflowInstances(), workflowOverview(), workflowCapabilities(), workflowSops(),
      ])
      setTemplates(templateData.items || [])
      setInstances(instanceData.items || [])
      setOverview(overviewData || defaultOverview)
      setCapabilities(capabilityData.items || [])
      setStandards(sopData.items || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : t("工作流方案加载失败"))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const switchView = (next: View) => {
    setView(next)
    setParams(next === 'library' ? {} : { view: next }, { replace: true })
  }

  const filteredTemplates = useMemo(() => templates.filter((item) => {
    const keyword = search.trim().toLowerCase()
    return (category === 'all' || item.category === category)
      && (!keyword || `${item.name}${item.description}${item.outcome}`.toLowerCase().includes(keyword))
  }), [templates, category, search])

  const filteredStandards = useMemo(() => standards.filter((item) => {
    const keyword = search.trim().toLowerCase()
    return !keyword || `${item.name}${item.description}${item.category_label}`.toLowerCase().includes(keyword)
  }), [standards, search])

  const openSource = (item: WorkflowTemplate | WorkflowSop, kind: 'template' | 'definition') => {
    const next: Source = {
      id: item.id,
      templateId: kind === 'template' ? item.id : (item as WorkflowSop).template_id,
      definitionId: kind === 'definition' ? item.id : undefined,
      name: item.name,
      description: item.description,
      outcome: item.outcome,
      categoryLabel: item.category_label,
      available: 'available' in item ? item.available !== false : item.enabled,
      steps: item.steps,
    }
    setSource(next)
    setName(item.name.replace(/标准流程$/, ''))
    setContext({ knowledge: true })
    setSchedule({ type: 'daily', time: '09:00' })
    setHumanPolicy('pause_on_risk')
    setStage(1)
  }

  const create = async () => {
    if (!source || !name.trim()) return
    setWorking('create')
    setError('')
    try {
      await createWorkflowInstance({
        template_id: source.templateId,
        definition_id: source.definitionId,
        name: name.trim(),
        description: source.description,
        schedule,
        config: { context },
        human_policy: humanPolicy,
      })
      setSource(null)
      showToast(t("工作流方案已启用，可在运行计划中管理时间"))
      switchView('mine')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("启用方案失败"))
    } finally {
      setWorking('')
    }
  }

  const remove = async (instance: WorkflowInstance) => {
    if (!window.confirm(t("移除“{v0}”？历史运行记录仍会保留。", { v0: instance.name }))) return
    setWorking(`delete:${instance.id}`)
    try { await deleteWorkflowInstance(instance.id); await load() }
    catch (e) { setError(e instanceof Error ? e.message : t("移除方案失败")) }
    finally { setWorking('') }
  }

  const disable = async (instance: WorkflowInstance) => {
    setWorking(`disable:${instance.id}`)
    try { await updateWorkflowInstance(instance.id, { status: 'disabled' }); await load() }
    catch (e) { setError(e instanceof Error ? e.message : t("停用方案失败")) }
    finally { setWorking('') }
  }

  const upgrade = async (instance: WorkflowInstance) => {
    setWorking(`upgrade:${instance.id}`)
    try { await upgradeWorkflowInstance(instance.id); showToast(t("方案已更新到最新标准流程")); await load() }
    catch (e) { setError(e instanceof Error ? e.message : t("更新方案失败")) }
    finally { setWorking('') }
  }

  const openStandard = (item: WorkflowSop) => {
    setSelectedStandard(item)
    setEditName(item.name)
    setEditDescription(item.description)
    setEditSteps(item.steps.map((step) => ({ ...step })))
    setNewAction('')
  }

  const clone = async (item: WorkflowSop) => {
    setWorking(`clone:${item.id}`)
    try { const cloned = await cloneWorkflowSop(item.id); await load(); openStandard(cloned); showToast(t("已复制为企业标准流程")) }
    catch (e) { setError(e instanceof Error ? e.message : t("复制标准流程失败")) }
    finally { setWorking('') }
  }

  const saveStandard = async () => {
    if (!selectedStandard || selectedStandard.source !== 'custom') return
    setWorking(`save:${selectedStandard.id}`)
    try {
      const saved = await updateWorkflowSop(selectedStandard.id, { name: editName.trim(), description: editDescription, steps: editSteps })
      setSelectedStandard(saved)
      showToast(t("标准流程已保存，新版本不会自动影响运行中的方案"))
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : t("保存标准流程失败")) }
    finally { setWorking('') }
  }

  const removeStandard = async () => {
    if (!selectedStandard || selectedStandard.source !== 'custom') return
    if (!window.confirm(t("移除企业标准流程“{v0}”？", { v0: selectedStandard.name }))) return
    setWorking(`delete-sop:${selectedStandard.id}`)
    try {
      await deleteWorkflowSop(selectedStandard.id)
      setSelectedStandard(null)
      showToast(t("企业标准流程已移除"))
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : t("移除标准流程失败")) }
    finally { setWorking('') }
  }

  const addStep = () => {
    const capability = capabilities.find((item) => item.action_id === newAction)
    if (!capability) return
    setEditSteps((rows) => [...rows, {
      id: `step_${Date.now()}`,
      name: capability.name,
      description: capability.description,
      action_id: capability.action_id,
      skill_name: capability.skill_name,
      params: {},
      risk_level: capability.risk_level,
      requires_confirmation: capability.risk_level === 'high',
      confirmation_policy: capability.risk_level === 'high' ? 'every_run' : 'automatic',
      on_failure: capability.risk_level === 'high' ? 'needs_human' : 'stop',
    }])
    setNewAction('')
  }

  const moveStep = (index: number, direction: -1 | 1) => {
    const target = index + direction
    if (target < 0 || target >= editSteps.length) return
    setEditSteps((rows) => {
      const next = [...rows]
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  return (
    <WorkflowPage subtitle={t("选择标准流程，绑定企业资料和运行计划，让重复工作持续完成。")}>
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
      {toast && <div className="fixed bottom-6 right-6 z-50 rounded-lg border border-[#10B981]/30 bg-[#10231E] px-4 py-3 text-sm text-[#A7F3D0] shadow-xl">{toast}</div>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric label={t("可用方案")} value={overview.templates} icon={ClipboardCheck} />
        <Metric label={t("已启用")} value={overview.active_instances} icon={CheckCircle2} tone="green" />
        <Metric label={t("正在执行")} value={overview.running} icon={GitBranch} tone="blue" />
        <Metric label={t("需要处理")} value={overview.needs_human} icon={AlertTriangle} tone="amber" />
      </div>

      <div className="flex flex-col gap-4 border-b border-[#1E293B] pb-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="inline-flex w-fit rounded-lg border border-[#273449] bg-[#0B0F1A] p-1">
          {views.map((item) => <button key={item.id} onClick={() => switchView(item.id)} className={`rounded-md px-4 py-2 text-sm ${view === item.id ? 'bg-[#6366F1] text-white' : 'text-[#94A3B8] hover:text-[#E2E8F0]'}`}>{item.label}</button>)}
        </div>
        <div className="flex gap-2"><button onClick={() => setDesigner('manual')} className={secondaryButton}><GitBranch className="h-4 w-4" />{t("手动创建")}</button><button onClick={() => setDesigner('ai')} className={primaryButton}><Sparkles className="h-4 w-4" />{t("AI 帮我设计")}</button></div>
      </div>

      {view === 'library' && <Section title={t("方案库")} description={t("按岗位场景选择，启用前可以检查标准步骤和人工确认点。")}>
        <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">{Object.entries(categoryLabels).map(([value, label]) => <button key={value} onClick={() => setCategory(value)} className={`rounded-lg border px-3 py-2 text-xs ${category === value ? 'border-[#6366F1] bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#273449] text-[#94A3B8]'}`}>{label}</button>)}</div>
          <SearchBox value={search} onChange={setSearch} placeholder={t("搜索工作流方案")} />
        </div>
        {loading ? <Loading /> : filteredTemplates.length === 0 ? <Empty title={t("没有匹配的方案")} description={t("调整分类或关键词后再试。")} /> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{filteredTemplates.map((item) => {
          const Icon = templateIcons[item.icon as keyof typeof templateIcons] || ClipboardCheck
          return <button key={item.id} disabled={!item.available} onClick={() => item.available && openSource(item, 'template')} className={`${panelClass} group flex min-h-64 flex-col p-5 text-left transition-all ${item.available ? 'hover:-translate-y-0.5 hover:border-[#4F46E5]' : 'cursor-not-allowed opacity-60'}`}><div className="flex items-start justify-between"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#6366F1]/12 text-[#818CF8]"><Icon className="h-5 w-5" /></span><span className="text-xs text-[#64748B]">{item.category_label}</span></div><h3 className="mt-5 font-semibold text-[#F1F5F9]">{item.name}</h3><p className="mt-2 line-clamp-3 text-sm leading-6 text-[#94A3B8]">{item.description}</p><div className="mt-auto pt-5 text-xs"><p className="text-[#64748B]">{t("完成后得到")}</p><p className="mt-1 text-sm text-[#CBD5E1]">{item.outcome}</p><div className="mt-4 flex items-center justify-between text-[#818CF8]"><span>{item.steps.length}  {t("个标准步骤")}</span>{item.available ? <ChevronRight className="h-4 w-4" /> : <span>{t("接入中")}</span>}</div></div></button>
        })}</div>}
      </Section>}

      {view === 'mine' && <Section title={t("我的工作流")} description={t("业务内容在这里管理，运行时间和执行结果统一前往运行计划查看。")}>
        {loading ? <Loading /> : instances.length === 0 ? <Empty title={t("还没有工作流方案")} description={t("从方案库或标准流程创建一项工作流。")} /> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="text-xs text-[#64748B]"><tr className="border-b border-[#1E293B]"><th className="pb-3">{t("方案")}</th><th className="pb-3">{t("标准流程版本")}</th><th className="pb-3">{t("运行摘要")}</th><th className="pb-3">{t("最近结果")}</th><th className="pb-3">{t("状态")}</th><th className="pb-3 text-right">{t("操作")}</th></tr></thead><tbody className="divide-y divide-[#1E293B]">{instances.map((item) => <tr key={item.id}><td className="py-4"><p className="font-medium text-[#F1F5F9]">{item.name}</p><p className="mt-1 text-xs text-[#64748B]">{item.template_name}</p></td><td className="py-4"><span className="text-[#CBD5E1]">v{item.definition_version || 1}</span>{item.upgrade_available && <button onClick={() => upgrade(item)} className="ml-2 rounded-full border border-[#F59E0B]/30 px-2 py-1 text-[11px] text-[#FBBF24]">{t("可更新")}</button>}</td><td className="py-4"><p className="text-[#CBD5E1]">{scheduleLabel(item.schedule)}</p><p className="mt-1 text-xs text-[#64748B]">{formatWorkflowTime(item.next_run_at)}</p></td><td className="py-4">{item.last_run ? <WorkflowStatus status={item.last_run.status} /> : <span className="text-xs text-[#64748B]">{t("尚未运行")}</span>}</td><td className="py-4"><WorkflowStatus status={item.status} /></td><td className="py-4"><div className="flex justify-end gap-2"><button onClick={() => navigate(`/automation/runs?instance=${item.id}`)} className={secondaryButton}>{t("查看运行")}</button>{item.status !== 'disabled' && <button onClick={() => disable(item)} className={iconButton} title={t("停用")}><X className="h-4 w-4" /></button>}<button onClick={() => remove(item)} className={iconButton} title={t("移除")}><Trash2 className="h-4 w-4" /></button></div></td></tr>)}</tbody></table></div>}
      </Section>}

      {view === 'standards' && <Section title={t("标准流程")} description={t("标准流程只定义怎么做；创建工作流方案后才能安排运行。")}>
        <div className="mb-5 flex justify-end"><SearchBox value={search} onChange={setSearch} placeholder={t("搜索标准流程")} /></div>
        {loading ? <Loading /> : filteredStandards.length === 0 ? <Empty title={t("暂无标准流程")} description={t("可以从系统方案复制，或使用 AI 设计新的流程。")} /> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{filteredStandards.map((item) => <button key={item.id} onClick={() => openStandard(item)} className={`${panelClass} group p-5 text-left transition-all hover:-translate-y-0.5 hover:border-[#4F46E5] ${item.available === false ? 'opacity-70' : ''}`}><div className="flex items-center justify-between"><span className={`rounded-full border px-2 py-1 text-xs ${item.source === 'builtin' ? 'border-[#6366F1]/25 text-[#A5B4FC]' : 'border-[#38BDF8]/25 text-[#7DD3FC]'}`}>{item.source === 'builtin' ? t("系统标准") : t("企业标准")}</span><span className="text-xs text-[#64748B]">{item.available === false ? t("接入中") : `v${item.version || 1}`}</span></div><h3 className="mt-4 font-semibold text-[#F1F5F9]">{item.name}</h3><p className="mt-2 line-clamp-2 min-h-10 text-sm leading-5 text-[#94A3B8]">{item.description}</p><div className="mt-5 flex items-center justify-between border-t border-[#273449] pt-4 text-xs text-[#64748B]"><span>{item.steps.length}  {t("个步骤")}</span><ChevronRight className="h-4 w-4 text-[#818CF8]" /></div></button>)}</div>}
      </Section>}

      {source && <ConfigureDrawer source={source} stage={stage} setStage={setStage} name={name} setName={setName} context={context} setContext={setContext} schedule={schedule} setSchedule={setSchedule} humanPolicy={humanPolicy} setHumanPolicy={setHumanPolicy} working={working} onClose={() => setSource(null)} onCreate={create} />}
      {selectedStandard && <StandardDrawer item={selectedStandard} capabilities={capabilities} editName={editName} setEditName={setEditName} editDescription={editDescription} setEditDescription={setEditDescription} editSteps={editSteps} setEditSteps={setEditSteps} newAction={newAction} setNewAction={setNewAction} addStep={addStep} moveStep={moveStep} working={working} onClose={() => setSelectedStandard(null)} onClone={() => clone(selectedStandard)} onSave={saveStandard} onDelete={removeStandard} onCreate={() => { setSelectedStandard(null); openSource(selectedStandard, 'definition') }} />}
      {designer && <WorkflowDesigner mode={designer} capabilities={capabilities} onClose={() => setDesigner(null)} onActivated={async () => { setDesigner(null); showToast(t('工作流方案已启用')); switchView('mine'); await load() }} />}
    </WorkflowPage>
  )
}

function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) {
  return <div className="relative w-full lg:w-72"><Search className="absolute left-3 top-2.5 h-4 w-4 text-[#475569]" /><input value={value} onChange={(e) => onChange(e.target.value)} className={`${inputClass} pl-9`} placeholder={placeholder} /></div>
}

function Loading() { return <div className="flex h-44 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-[#64748B]" /></div> }

function ConfigureDrawer(props: {
  source: Source; stage: number; setStage: (value: number) => void; name: string; setName: (value: string) => void;
  context: Record<string, boolean>; setContext: (value: Record<string, boolean>) => void;
  schedule: WorkflowSchedule; setSchedule: (value: WorkflowSchedule) => void;
  humanPolicy: WorkflowInstance['human_policy']; setHumanPolicy: (value: WorkflowInstance['human_policy']) => void;
  working: string; onClose: () => void; onCreate: () => void;
}) {
  const { t } = useI18n()
  const { source, stage, setStage, name, setName, context, setContext, schedule, setSchedule, humanPolicy, setHumanPolicy, working, onClose, onCreate } = props
  return <div className="fixed inset-0 z-50 flex justify-end bg-black/55" onMouseDown={(e) => { if (e.currentTarget === e.target) onClose() }}><aside className="h-full w-full max-w-xl overflow-y-auto border-l border-[#273449] bg-[#0F1624] shadow-2xl"><div className="sticky top-0 z-10 border-b border-[#273449] bg-[#0F1624] px-6 py-5"><div className="flex items-start justify-between"><div><p className="text-xs text-[#818CF8]">{source.categoryLabel}</p><h2 className="mt-1 text-lg font-semibold text-[#F1F5F9]">{t("启用")} {source.name}</h2></div><button onClick={onClose} className={iconButton}><X className="h-4 w-4" /></button></div><div className="mt-5 grid grid-cols-4 gap-2">{[t("选择流程"), t("绑定资料"), t("运行计划"), t("检查启用")].map((label, index) => <div key={label}><div className={`h-1 rounded-full ${stage >= index + 1 ? 'bg-[#6366F1]' : 'bg-[#273449]'}`} /><p className={`mt-2 text-[11px] ${stage === index + 1 ? 'text-[#C7D2FE]' : 'text-[#64748B]'}`}>{label}</p></div>)}</div></div><div className="space-y-5 p-6">
    {stage === 1 && <><p className="text-sm leading-6 text-[#94A3B8]">{source.description}</p><div className="space-y-2">{source.steps.map((step, index) => <div key={step.id} className="flex gap-3 rounded-lg border border-[#273449] bg-[#0B0F1A] p-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#6366F1]/15 text-xs text-[#A5B4FC]">{index + 1}</span><div><p className="text-sm text-[#E2E8F0]">{step.name}</p><p className="mt-1 text-xs leading-5 text-[#64748B]">{step.description}</p>{step.requires_confirmation && <p className="mt-2 text-xs text-[#FBBF24]">{t("执行前需要确认")}</p>}</div></div>)}</div></>}
    {stage === 2 && <><div><label className="mb-2 block text-xs text-[#94A3B8]">{t("方案名称")}</label><input value={name} onChange={(e) => setName(e.target.value)} className={inputClass} /></div><div><p className="mb-3 text-xs text-[#94A3B8]">{t("允许方案使用的企业资料")}</p><div className="grid grid-cols-2 gap-2">{contextOptions.map(([key, label]) => <label key={key} className={`flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-sm ${context[key] ? 'border-[#6366F1] bg-[#6366F1]/10 text-[#C7D2FE]' : 'border-[#273449] text-[#94A3B8]'}`}><input type="checkbox" checked={Boolean(context[key])} onChange={(e) => setContext({ ...context, [key]: e.target.checked })} className="accent-[#6366F1]" />{t(label)}</label>)}</div></div></>}
    {stage === 3 && <><ScheduleEditor value={schedule} onChange={setSchedule} /><div><label className="mb-2 block text-xs text-[#94A3B8]">{t("出现异常时")}</label><select value={humanPolicy} onChange={(e) => setHumanPolicy(e.target.value as WorkflowInstance['human_policy'])} className={inputClass}><option value="pause_on_risk">{t("暂停并通知我处理")}</option><option value="always_confirm_external">{t("外部动作每次确认")}</option><option value="notify_only">{t("记录问题并通知")}</option></select></div></>}
    {stage === 4 && <><div className="rounded-lg border border-[#10B981]/25 bg-[#10B981]/8 p-4"><div className="flex items-center gap-2 text-sm font-medium text-[#A7F3D0]"><Check className="h-4 w-4" />{t("方案可以启用")}</div><p className="mt-2 text-xs leading-5 text-[#6EE7B7]/80">{t("外部发布、发送和高风险动作仍会按规则等待确认。")}</p></div><div className="rounded-lg border border-[#273449] bg-[#0B0F1A] p-4 text-sm"><p className="font-medium text-[#F1F5F9]">{name}</p><div className="mt-3 space-y-2 text-xs text-[#94A3B8]"><p>{t("标准流程：")}{source.name} · {source.steps.length}  {t("个步骤")}</p><p>{t("运行计划：")}{scheduleLabel(schedule)}</p><p>{t("已关联：")}{contextOptions.filter(([key]) => context[key]).map(([, label]) => t(label)).join('、') || t("不使用额外资料")}</p></div></div></>}
    <div className="flex gap-3 border-t border-[#273449] pt-5">{stage > 1 && <button onClick={() => setStage(stage - 1)} className={`${secondaryButton} flex-1`}><ChevronLeft className="h-4 w-4" />{t("上一步")}</button>}{stage < 4 ? <button onClick={() => setStage(stage + 1)} disabled={stage === 2 && !name.trim()} className={`${primaryButton} flex-1`}>{t("下一步")}<ChevronRight className="h-4 w-4" /></button> : <button onClick={onCreate} disabled={working === 'create'} className={`${primaryButton} flex-1`}>{working === 'create' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}{t("确认并启用")}</button>}</div>
  </div></aside></div>
}

export function ScheduleEditor({ value, onChange }: { value: WorkflowSchedule; onChange: (value: WorkflowSchedule) => void }) {
  const { t } = useI18n()
  const types: Array<[WorkflowSchedule['type'], string]> = [['manual', '手动'], ['daily', '每天'], ['weekly', '每周'], ['interval', '间隔'], ['once', '单次']]
  return <div><label className="mb-2 block text-xs text-[#94A3B8]">{t("运行频率")}</label><div className="grid grid-cols-5 gap-2">{types.map(([type, label]) => <button key={type} onClick={() => onChange(type === 'interval' ? { type, interval_minutes: 60 } : type === 'once' ? { type, at: '' } : type === 'manual' ? { type } : { type, time: '09:00', ...(type === 'weekly' ? { weekdays: [1] } : {}) })} className={`rounded-lg border px-2 py-2 text-xs ${value.type === type ? 'border-[#6366F1] bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#334155] text-[#94A3B8]'}`}>{t(label)}</button>)}</div>{['daily', 'weekly'].includes(value.type) && <input type="time" value={value.time || '09:00'} onChange={(e) => onChange({ ...value, time: e.target.value })} className={`${inputClass} mt-3`} />}{value.type === 'interval' && <div className="mt-3 flex items-center gap-2"><input type="number" min={5} value={value.interval_minutes || 60} onChange={(e) => onChange({ type: 'interval', interval_minutes: Math.max(5, Number(e.target.value) || 5) })} className={inputClass} /><span className="text-sm text-[#94A3B8]">{t("分钟")}</span></div>}{value.type === 'once' && <input type="datetime-local" value={value.at || ''} onChange={(e) => onChange({ type: 'once', at: e.target.value })} className={`${inputClass} mt-3`} />}</div>
}

function StandardDrawer(props: {
  item: WorkflowSop; capabilities: WorkflowCapability[]; editName: string; setEditName: (value: string) => void;
  editDescription: string; setEditDescription: (value: string) => void; editSteps: WorkflowStep[]; setEditSteps: (value: WorkflowStep[]) => void;
  newAction: string; setNewAction: (value: string) => void; addStep: () => void; moveStep: (index: number, direction: -1 | 1) => void;
  working: string; onClose: () => void; onClone: () => void; onSave: () => void; onDelete: () => void; onCreate: () => void;
}) {
  const { t } = useI18n()
  const p = props
  const custom = p.item.source === 'custom'
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/55" onMouseDown={(e) => { if (e.currentTarget === e.target) p.onClose() }}>
      <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-[#273449] bg-[#0F1624] shadow-2xl">
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-[#273449] bg-[#0F1624] px-6 py-5">
          <div className="min-w-0 flex-1 pr-4">
            <p className="text-xs text-[#818CF8]">{custom ? t("企业标准流程") : t("系统标准流程")} · v{p.item.version || 1}</p>
            {custom ? <>
              <input value={p.editName} onChange={(e) => p.setEditName(e.target.value)} className={`${inputClass} mt-3 font-semibold`} />
              <textarea value={p.editDescription} onChange={(e) => p.setEditDescription(e.target.value)} rows={2} className={`${inputClass} mt-2 resize-none`} />
            </> : <>
              <h2 className="mt-1 text-lg font-semibold text-[#F1F5F9]">{p.item.name}</h2>
              <p className="mt-2 text-sm leading-6 text-[#94A3B8]">{p.item.description}</p>
            </>}
          </div>
          <button onClick={p.onClose} className={iconButton}><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-5 p-6">
          {custom && <div className="rounded-lg border border-[#273449] bg-[#0B0F1A] px-4 py-3 text-xs text-[#94A3B8]">

            {t("当前版本 v")}{p.item.version || 1}  {t("· 已保留")} {p.item.versions?.length || 0}  {t("个历史版本")}
            {p.item.updated_at ? t("· 最近保存 {v0}", { v0: formatWorkflowTime(p.item.updated_at) }) : ''}
          </div>}
          <div className="space-y-3">{p.editSteps.map((step, index) => (
            <div key={step.id} className="rounded-lg border border-[#273449] bg-[#0B0F1A] p-4">
              <div className="flex items-start gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#6366F1]/15 text-xs text-[#C7D2FE]">{index + 1}</span>
                <div className="min-w-0 flex-1">{custom ? <>
                  <input value={step.name} onChange={(e) => p.setEditSteps(p.editSteps.map((row, i) => i === index ? { ...row, name: e.target.value } : row))} className={`${inputClass} h-9`} />
                  <textarea value={step.description} onChange={(e) => p.setEditSteps(p.editSteps.map((row, i) => i === index ? { ...row, description: e.target.value } : row))} rows={2} className={`${inputClass} mt-2 resize-none text-xs`} />
                  <select value={step.on_failure} onChange={(e) => p.setEditSteps(p.editSteps.map((row, i) => i === index ? { ...row, on_failure: e.target.value as WorkflowStep['on_failure'] } : row))} className={`${inputClass} mt-2 h-9 text-xs`}>
                    <option value="stop">{t("失败时停止")}</option><option value="retry">{t("自动重试")}</option>
                    <option value="skip">{t("跳过继续")}</option><option value="needs_human">{t("暂停并人工处理")}</option>
                  </select>
                </> : <>
                  <p className="text-sm font-medium text-[#E2E8F0]">{step.name}</p>
                  <p className="mt-1 text-xs leading-5 text-[#64748B]">{step.description}</p>
                </>}</div>
                {custom && <div className="flex gap-1">
                  <button onClick={() => p.moveStep(index, -1)} disabled={index === 0} className={iconButton}><ArrowUp className="h-3.5 w-3.5" /></button>
                  <button onClick={() => p.moveStep(index, 1)} disabled={index === p.editSteps.length - 1} className={iconButton}><ArrowDown className="h-3.5 w-3.5" /></button>
                  <button onClick={() => p.setEditSteps(p.editSteps.filter((_, i) => i !== index))} className={iconButton}><Trash2 className="h-3.5 w-3.5" /></button>
                </div>}
              </div>
            </div>
          ))}</div>
          {custom && <div className="flex gap-2">
            <select value={p.newAction} onChange={(e) => p.setNewAction(e.target.value)} className={inputClass}>
              <option value="">{t("选择要增加的能力")}</option>
              {p.capabilities.map((item) => <option key={item.action_id} value={item.action_id}>{item.name}</option>)}
            </select>
            <button onClick={p.addStep} disabled={!p.newAction} className={secondaryButton}><Plus className="h-4 w-4" />{t("增加")}</button>
          </div>}
          <div className={`grid gap-2 border-t border-[#273449] pt-5 ${custom ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
            {custom ? <>
              <button onClick={p.onDelete} className={secondaryButton}><Trash2 className="h-4 w-4" />{t("移除流程")}</button>
              <button onClick={p.onSave} disabled={!p.editName.trim() || !p.editSteps.length || p.working.startsWith('save:')} className={primaryButton}>
                {p.working.startsWith('save:') ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t("保存新版本")}
              </button>
            </> : <button onClick={p.onClone} disabled={p.working.startsWith('clone:')} className={secondaryButton}><Copy className="h-4 w-4" />{t("复制并调整")}</button>}
            <button onClick={p.onCreate} disabled={p.item.available === false} title={p.item.available === false ? t("该流程正在接入真实业务能力") : t("基于此创建方案")} className={primaryButton}>
              <CheckCircle2 className="h-4 w-4" />{p.item.available === false ? t("能力接入中") : t("基于此创建方案")}
            </button>
          </div>
        </div>
      </aside>
    </div>
  )
}
