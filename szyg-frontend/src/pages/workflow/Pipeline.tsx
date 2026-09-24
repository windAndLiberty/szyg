import { useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, CheckCircle2, ChevronRight, ClipboardCheck, Clock3,
  FileBarChart, Loader2, Pause, Play, Plus, RefreshCw, Search, Send, ShieldCheck,
  SlidersHorizontal, Sparkles, Trash2, Users, X,
} from 'lucide-react'
import {
  createWorkflowInstance, deleteWorkflowInstance, runWorkflowInstance, updateWorkflowInstance,
  workflowCapabilities, workflowInstances, workflowOverview, workflowTemplates,
  type WorkflowCapability, type WorkflowInstance, type WorkflowOverview, type WorkflowSchedule, type WorkflowTemplate,
} from './workflowApi'
import {
  Empty, Metric, Section, WorkflowPage, WorkflowStatus, formatWorkflowTime, iconButton,
  inputClass, panelClass, primaryButton, scheduleLabel, secondaryButton,
} from './WorkflowShared'
import WorkflowDesigner from './WorkflowDesigner'
import { translateCurrent, useI18n } from '@/lib/i18n'

const categoryLabels: Record<string, string> = {
  get all() { return translateCurrent("全部方案") }, get content_operations() { return translateCurrent("内容运营") }, get channel_operations() { return translateCurrent("渠道运营") },
  get customer_operations() { return translateCurrent("客户运营") }, get data_operations() { return translateCurrent("数据整理") },
}

const templateIcons = {
  send: Send, shield: ShieldCheck, users: Users, report: FileBarChart,
}

const defaultOverview: WorkflowOverview = { templates: 0, active_instances: 0, running: 0, needs_human: 0, success_today: 0 }

export default function Pipeline() {
  const { t } = useI18n()
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [instances, setInstances] = useState<WorkflowInstance[]>([])
  const [overview, setOverview] = useState(defaultOverview)
  const [capabilities, setCapabilities] = useState<WorkflowCapability[]>([])
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<WorkflowTemplate | null>(null)
  const [name, setName] = useState('')
  const [scheduleType, setScheduleType] = useState<WorkflowSchedule['type']>('daily')
  const [time, setTime] = useState('09:00')
  const [humanPolicy, setHumanPolicy] = useState<WorkflowInstance['human_policy']>('pause_on_risk')
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [designer, setDesigner] = useState<'ai' | 'manual' | null>(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [templateData, instanceData, overviewData, capabilityData] = await Promise.all([
        workflowTemplates(), workflowInstances(), workflowOverview(), workflowCapabilities(),
      ])
      setTemplates(templateData.items || [])
      setInstances(instanceData.items || [])
      setOverview(overviewData || defaultOverview)
      setCapabilities(capabilityData.items || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : t("工作流方案加载失败"))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = useMemo(() => templates.filter((item) => {
    const categoryMatch = category === 'all' || item.category === category
    const keyword = search.trim().toLowerCase()
    return categoryMatch && (!keyword || `${item.name}${item.description}${item.outcome}`.toLowerCase().includes(keyword))
  }), [templates, category, search])

  const openConfigure = (template: WorkflowTemplate) => {
    setSelected(template)
    setName(template.name)
    setScheduleType('daily')
    setTime('09:00')
    setHumanPolicy('pause_on_risk')
  }

  const create = async () => {
    if (!selected || !name.trim()) return
    setWorking('create')
    setError('')
    try {
      await createWorkflowInstance({
        template_id: selected.id,
        name: name.trim(),
        schedule: scheduleType === 'manual' ? { type: 'manual' } : { type: scheduleType, time },
        config: {},
        human_policy: humanPolicy,
      })
      setSelected(null)
      setToast(t("工作流方案已启用"))
      window.setTimeout(() => setToast(''), 2600)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("启用方案失败"))
    } finally {
      setWorking('')
    }
  }

  const changeStatus = async (instance: WorkflowInstance) => {
    const next = instance.status === 'active' ? 'paused' : 'active'
    setWorking(instance.id)
    try {
      await updateWorkflowInstance(instance.id, { status: next })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("状态更新失败"))
    } finally { setWorking('') }
  }

  const runNow = async (instance: WorkflowInstance) => {
    setWorking(`run:${instance.id}`)
    try {
      await runWorkflowInstance(instance.id)
      setToast(t("任务已进入运行队列"))
      window.setTimeout(() => setToast(''), 2600)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("运行任务失败"))
    } finally { setWorking('') }
  }

  const remove = async (instance: WorkflowInstance) => {
    if (!window.confirm(t("移除“{v0}”？历史运行记录仍会保留。", { v0: instance.name }))) return
    setWorking(`delete:${instance.id}`)
    try { await deleteWorkflowInstance(instance.id); await load() }
    catch (e) { setError(e instanceof Error ? e.message : t("移除方案失败")) }
    finally { setWorking('') }
  }

  return (
    <WorkflowPage subtitle={t("选择一项岗位任务，补齐少量设置，系统会按计划持续执行并反馈结果。")}>
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
      {toast && <div className="fixed bottom-6 right-6 z-50 rounded-lg border border-[#10B981]/30 bg-[#10231E] px-4 py-3 text-sm text-[#A7F3D0] shadow-xl">{toast}</div>}

      <div className="flex flex-col gap-4 border-b border-[#1E293B] pb-6 sm:flex-row sm:items-center sm:justify-between">
        <div><p className="text-sm font-medium text-[#E2E8F0]">{t("把重复工作交给系统持续完成")}</p><p className="mt-1 text-xs leading-5 text-[#64748B]">{t("描述你的目标，或自行组合已有能力；启用前可以检查和调整每一步。")}</p></div>
        <div className="flex gap-2"><button onClick={() => setDesigner('manual')} className={secondaryButton}><SlidersHorizontal className="h-4 w-4" />{t("手动创建")}</button><button onClick={() => setDesigner('ai')} className={primaryButton}><Sparkles className="h-4 w-4" />{t("AI 帮我设计")}</button></div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric label={t("可用方案")} value={overview.templates} icon={ClipboardCheck} />
        <Metric label={t("已启用")} value={overview.active_instances} icon={CheckCircle2} tone="green" />
        <Metric label={t("正在执行")} value={overview.running} icon={Activity} tone="blue" />
        <Metric label={t("需要处理")} value={overview.needs_human} icon={AlertTriangle} tone="amber" />
      </div>

      <Section
        title={t("工作流方案")}
        description={t("按岗位场景选择，不需要搭建节点或理解技术配置。")}
        action={<button onClick={load} className={iconButton} title={t("刷新")}><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></button>}
      >
        <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">
            {Object.entries(categoryLabels).map(([value, label]) => (
              <button key={value} onClick={() => setCategory(value)} className={`rounded-lg border px-3 py-2 text-xs transition-colors ${category === value ? 'border-[#6366F1] bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#273449] text-[#94A3B8] hover:border-[#475569]'}`}>{label}</button>
            ))}
          </div>
          <div className="relative w-full lg:w-72"><Search className="absolute left-3 top-2.5 h-4 w-4 text-[#475569]" /><input value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputClass} pl-9`} placeholder={t("搜索工作流方案")} /></div>
        </div>

        {loading ? <div className="flex h-48 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-[#64748B]" /></div> : filtered.length === 0 ? (
          <Empty title={t("没有匹配的方案")} description={t("调整分类或关键词后再试。")} />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {filtered.map((template) => {
              const Icon = templateIcons[template.icon as keyof typeof templateIcons] || ClipboardCheck
              return (
                <button key={template.id} disabled={!template.available} onClick={() => template.available && openConfigure(template)} className={`${panelClass} group flex min-h-64 flex-col p-5 text-left transition-all ${template.available ? 'hover:-translate-y-0.5 hover:border-[#4F46E5] hover:bg-[#151D2E]' : 'cursor-not-allowed opacity-65'}`}>
                  <div className="flex items-start justify-between"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#6366F1]/12 text-[#818CF8]"><Icon className="h-5 w-5" /></div><div className="flex items-center gap-2"><span className="text-xs text-[#64748B]">{template.category_label}</span>{!template.available && <span className="rounded-full border border-[#475569] px-2 py-0.5 text-[11px] text-[#94A3B8]">{t("接入中")}</span>}</div></div>
                  <h3 className="mt-5 text-base font-semibold text-[#F1F5F9]">{template.name}</h3>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-[#94A3B8]">{template.description}</p>
                  <div className="mt-auto pt-5"><p className="text-xs text-[#64748B]">{t("完成后得到")}</p><p className="mt-1 text-sm text-[#CBD5E1]">{template.outcome}</p><div className="mt-4 flex items-center justify-between text-xs text-[#818CF8]"><span>{template.steps.length}  {t("个标准步骤")}</span>{template.available && <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />}</div></div>
                </button>
              )
            })}
          </div>
        )}
      </Section>

      <Section title={t("我的工作流")} description={t("已启用的方案会按照计划运行，也可以随时暂停或立即执行。")}>
        {instances.length === 0 ? <Empty title={t("还没有启用方案")} description={t("从上方选择一个岗位任务，完成简单设置后即可开始。")} /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead className="text-xs text-[#64748B]"><tr className="border-b border-[#1E293B]"><th className="pb-3 font-medium">{t("方案")}</th><th className="pb-3 font-medium">{t("运行计划")}</th><th className="pb-3 font-medium">{t("下次运行")}</th><th className="pb-3 font-medium">{t("最近结果")}</th><th className="pb-3 font-medium">{t("状态")}</th><th className="pb-3 text-right font-medium">{t("操作")}</th></tr></thead>
              <tbody className="divide-y divide-[#1E293B]">
                {instances.map((item) => (
                  <tr key={item.id}>
                    <td className="py-4"><p className="font-medium text-[#F1F5F9]">{item.name}</p><p className="mt-1 text-xs text-[#64748B]">{item.template_name}</p></td>
                    <td className="py-4 text-[#CBD5E1]">{scheduleLabel(item.schedule)}</td>
                    <td className="py-4 text-[#94A3B8]">{formatWorkflowTime(item.next_run_at)}</td>
                    <td className="py-4">{item.last_run ? <WorkflowStatus status={item.last_run.status} /> : <span className="text-xs text-[#64748B]">{t("尚未运行")}</span>}</td>
                    <td className="py-4"><WorkflowStatus status={item.status} /></td>
                    <td className="py-4"><div className="flex justify-end gap-2"><button onClick={() => runNow(item)} disabled={working === `run:${item.id}`} className={iconButton} title={t("立即运行")}>{working === `run:${item.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}</button><button onClick={() => changeStatus(item)} disabled={working === item.id} className={iconButton} title={item.status === 'active' ? t("暂停") : t("继续")}>{item.status === 'active' ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}</button><button onClick={() => remove(item)} className={iconButton} title={t("移除")}><Trash2 className="h-4 w-4" /></button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/55" onMouseDown={(e) => { if (e.currentTarget === e.target) setSelected(null) }}>
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-[#273449] bg-[#0F1624] shadow-2xl">
            <div className="sticky top-0 z-10 flex items-start justify-between border-b border-[#273449] bg-[#0F1624] px-6 py-5"><div><p className="text-xs text-[#818CF8]">{selected.category_label}</p><h2 className="mt-1 text-lg font-semibold text-[#F1F5F9]">{t("启用")} {selected.name}</h2><p className="mt-2 text-sm leading-6 text-[#94A3B8]">{selected.description}</p></div><button onClick={() => setSelected(null)} className={iconButton}><X className="h-4 w-4" /></button></div>
            <div className="space-y-6 p-6">
              <div><label className="mb-2 block text-xs text-[#94A3B8]">{t("方案名称")}</label><input value={name} onChange={(e) => setName(e.target.value)} className={inputClass} /></div>
              <div><label className="mb-2 block text-xs text-[#94A3B8]">{t("运行频率")}</label><div className="grid grid-cols-3 gap-2">{(['manual', 'daily', 'weekly'] as WorkflowSchedule['type'][]).map((value) => <button key={value} onClick={() => setScheduleType(value)} className={`rounded-lg border px-3 py-2.5 text-sm ${scheduleType === value ? 'border-[#6366F1] bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#334155] text-[#94A3B8]'}`}>{value === 'manual' ? t("手动运行") : value === 'daily' ? t("每天") : t("每周")}</button>)}</div>{scheduleType !== 'manual' && <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className={`${inputClass} mt-3`} />}</div>
              <div><label className="mb-2 block text-xs text-[#94A3B8]">{t("出现异常时")}</label><select value={humanPolicy} onChange={(e) => setHumanPolicy(e.target.value as WorkflowInstance['human_policy'])} className={inputClass}><option value="pause_on_risk">{t("暂停并通知我处理")}</option><option value="always_confirm_external">{t("外部动作每次确认")}</option><option value="notify_only">{t("记录问题并通知")}</option></select></div>
              <div><p className="mb-3 text-xs font-medium text-[#94A3B8]">{t("标准步骤")}</p><div className="space-y-2">{selected.steps.map((step, index) => <div key={step.id} className="flex gap-3 rounded-lg border border-[#273449] bg-[#0B0F1A] p-3"><div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#6366F1]/15 text-xs text-[#A5B4FC]">{index + 1}</div><div><p className="text-sm text-[#E2E8F0]">{step.name}</p><p className="mt-1 text-xs leading-5 text-[#64748B]">{step.description}</p>{step.requires_confirmation && <p className="mt-2 inline-flex items-center gap-1 text-xs text-[#FBBF24]"><AlertTriangle className="h-3 w-3" />{t("执行前需要确认")}</p>}</div></div>)}</div></div>
              <div className="flex gap-3 border-t border-[#273449] pt-5"><button onClick={() => setSelected(null)} className={`${secondaryButton} flex-1`}>{t("取消")}</button><button onClick={create} disabled={!name.trim() || working === 'create'} className={`${primaryButton} flex-1`}>{working === 'create' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}{t("启用方案")}</button></div>
            </div>
          </aside>
        </div>
      )}
      {designer && <WorkflowDesigner mode={designer} capabilities={capabilities} onClose={() => setDesigner(null)} onActivated={async () => { setDesigner(null); setToast(t("工作流方案已启用")); window.setTimeout(() => setToast(''), 2600); await load() }} />}
    </WorkflowPage>
  )
}
