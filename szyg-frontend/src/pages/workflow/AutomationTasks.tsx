import { useEffect, useState } from 'react'
import { Bot, Clock3, Loader2, Pause, Play, Plus, Sparkles } from 'lucide-react'
import {
  activateWorkflowDraft,
  createWorkflowDraft,
  createWorkflowInstance,
  designWorkflowDraft,
  runWorkflowInstance,
  updateWorkflowInstance,
  workflowInstances,
  workflowTemplates,
  type WorkflowInstance,
  type WorkflowTemplate,
} from './workflowApi'
import { Empty, Section, WorkflowPage, WorkflowStatus, formatWorkflowTime, primaryButton, scheduleLabel, secondaryButton } from './WorkflowShared'
import { useI18n } from '@/lib/i18n'

export default function AutomationTasks() {
  const { t } = useI18n()
  const [instances, setInstances] = useState<WorkflowInstance[]>([])
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [goal, setGoal] = useState('')
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = async () => {
    try {
      const [instanceData, templateData] = await Promise.all([workflowInstances(), workflowTemplates()])
      setInstances(instanceData.items || [])
      setTemplates((templateData.items || []).filter((item) => item.available))
    } catch (cause) { setError(cause instanceof Error ? cause.message : t("自动任务加载失败")) }
  }
  useEffect(() => { load() }, [])

  const createFromGoal = async () => {
    if (goal.trim().length < 2) { setError(t("请用一句话说明希望自动完成的工作")); return }
    setWorking('goal'); setError(''); setNotice('')
    try {
      const draft = await createWorkflowDraft({
        goal: goal.trim(),
        context: { knowledge: true, accounts: true, leads: true, materials: true, publish_records: true },
        schedule: { type: 'manual' },
        notification: 'in_app',
      })
      const designed = await designWorkflowDraft(draft.id)
      await activateWorkflowDraft(designed.id)
      setGoal(''); setNotice(t("AI已整理为自动任务。你可以先手动运行，再决定是否设置固定时间。")); await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : t("自动任务创建失败")) }
    finally { setWorking('') }
  }

  const useTemplate = async (template: WorkflowTemplate) => {
    setWorking(template.id); setError(''); setNotice('')
    try {
      await createWorkflowInstance({ template_id: template.id, name: template.name, schedule: template.id === 'geo_weekly_audit' ? { type: 'weekly', time: '09:00' } : { type: 'manual' }, config: {}, human_policy: 'pause_on_risk' })
      setNotice(t("已启用“{v0}”", { v0: template.name })); await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : t("启用任务失败")) }
    finally { setWorking('') }
  }

  const toggle = async (item: WorkflowInstance) => {
    setWorking(item.id)
    try { await updateWorkflowInstance(item.id, { status: item.status === 'active' ? 'paused' : 'active' }); await load() }
    catch (cause) { setError(cause instanceof Error ? cause.message : t("任务状态更新失败")) }
    finally { setWorking('') }
  }

  const runNow = async (item: WorkflowInstance) => {
    setWorking(`run:${item.id}`); setError('')
    try { await runWorkflowInstance(item.id); setNotice(t("“{v0}”已进入执行队列", { v0: item.name })); await load() }
    catch (cause) { setError(cause instanceof Error ? cause.message : t("任务启动失败")) }
    finally { setWorking('') }
  }

  return <WorkflowPage subtitle={t("告诉AI要自动完成什么；已启用任务只展示时间、确认要求和最近结果。")}>
    {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
    {notice && <div className="rounded-lg border border-[#10B981]/30 bg-[#10B981]/10 px-4 py-3 text-sm text-[#A7F3D0]">{notice}</div>}
    <section className="rounded-xl border border-[#6366F1]/25 bg-gradient-to-br from-[#171B34] to-[#111827] p-6">
      <div className="flex items-center gap-2 text-xs font-medium text-[#A5B4FC]"><Bot className="h-4 w-4" />{t("用一句话创建自动任务")}</div>
      <div className="mt-4 flex flex-col gap-3 lg:flex-row"><textarea value={goal} onChange={(e) => setGoal(e.target.value.slice(0, 2000))} className="min-h-24 flex-1 resize-none rounded-lg border border-[#334155] bg-[#0B0F1A] px-4 py-3 text-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]" placeholder={t("例如：每周检查一次AI是否推荐我们的企业，并把结果整理给我")} /><button onClick={createFromGoal} disabled={working === 'goal'} className={`${primaryButton} lg:w-40`}>{working === 'goal' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}{t("交给AI整理")}</button></div>
    </section>
    <Section title={t("正在自动完成")} description={t("这些任务会按照设定时间运行；外部发送、发布等高风险操作仍会等待你确认。")}>
      {instances.length === 0 ? <Empty title={t("还没有自动任务")} description={t("从上方描述需求，或启用一个常用任务。")} /> : <div className="grid gap-3 lg:grid-cols-2">{instances.map((item) => <article key={item.id} className="rounded-lg border border-[#273449] bg-[#0B0F1A] p-5"><div className="flex items-start justify-between gap-3"><div><p className="font-medium text-[#F1F5F9]">{item.name}</p><p className="mt-1 text-xs text-[#64748B]">{item.description || item.template_name}</p></div><WorkflowStatus status={item.status} /></div><div className="mt-4 grid grid-cols-2 gap-3 rounded-lg bg-[#111827] p-3 text-xs"><div><p className="text-[#64748B]">{t("下次执行")}</p><p className="mt-1 text-[#CBD5E1]">{item.next_run_at ? formatWorkflowTime(item.next_run_at) : scheduleLabel(item.schedule)}</p></div><div><p className="text-[#64748B]">{t("最近结果")}</p><p className="mt-1 text-[#CBD5E1]">{item.last_run ? (item.last_run.status === 'success' ? t("已完成") : item.last_run.status === 'needs_human' ? t("等待确认") : t("查看执行记录")) : t("尚未运行")}</p></div></div><div className="mt-4 flex gap-2"><button onClick={() => runNow(item)} disabled={Boolean(working)} className={secondaryButton}>{working === `run:${item.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}{t("立即运行")}</button><button onClick={() => toggle(item)} disabled={Boolean(working)} className={secondaryButton}>{item.status === 'active' ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}{item.status === 'active' ? t("暂停") : t("继续")}</button></div></article>)}</div>}
    </Section>
    <Section title={t("常用自动任务")} description={t("只展示当前真实可执行的任务。")}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{templates.map((item) => <article key={item.id} className="rounded-lg border border-[#273449] bg-[#0B0F1A] p-5"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#6366F1]/12 text-[#A5B4FC]"><Clock3 className="h-4 w-4" /></div><p className="mt-4 font-medium text-[#F1F5F9]">{item.name}</p><p className="mt-2 min-h-10 text-xs leading-5 text-[#64748B]">{item.outcome}</p><button onClick={() => useTemplate(item)} disabled={Boolean(working)} className={`${secondaryButton} mt-4 w-full`}>{working === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}{t("启用任务")}</button></article>)}</div>
    </Section>
  </WorkflowPage>
}
