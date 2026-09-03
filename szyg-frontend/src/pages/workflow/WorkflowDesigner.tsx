import { useMemo, useState } from 'react'
import {
  AlertTriangle, ArrowDown, ArrowUp, BookOpen, Check, ChevronLeft, ChevronRight,
  Database, FileText, GripVertical, Loader2, Plus, Sparkles, Trash2, Users, X,
} from 'lucide-react'
import {
  activateWorkflowDraft, createWorkflowDraft, designWorkflowDraft, reviseWorkflowDraft,
  updateWorkflowDraft, validateWorkflowDraft, type WorkflowCapability, type WorkflowCondition,
  type WorkflowDraft, type WorkflowSchedule, type WorkflowStep,
} from './workflowApi'
import { iconButton, inputClass, primaryButton, secondaryButton } from './WorkflowShared'

type Props = {
  mode: 'ai' | 'manual'
  capabilities: WorkflowCapability[]
  onClose: () => void
  onActivated: () => void
}

const contextOptions = [
  { key: 'knowledge', label: '企业资料', icon: BookOpen },
  { key: 'accounts', label: '渠道账号', icon: Database },
  { key: 'leads', label: '客户线索', icon: Users },
  { key: 'materials', label: '素材内容', icon: FileText },
  { key: 'publish_records', label: '发布记录', icon: FileText },
] as const

const operatorLabels: Record<WorkflowCondition['operator'], string> = {
  equals: '等于', not_equals: '不等于', contains: '包含', gt: '大于', lt: '小于', empty: '为空', not_empty: '不为空',
}

const riskLabels = { low: '自动执行', medium: '自动处理', high: '执行时确认' }

export default function WorkflowDesigner({ mode, capabilities, onClose, onActivated }: Props) {
  const [stage, setStage] = useState<1 | 2 | 3>(1)
  const [goal, setGoal] = useState('')
  const [context, setContext] = useState<WorkflowDraft['context']>({ knowledge: true, accounts: false, leads: false, materials: false, publish_records: false })
  const [scheduleType, setScheduleType] = useState<WorkflowSchedule['type']>('daily')
  const [time, setTime] = useState('09:00')
  const [draft, setDraft] = useState<WorkflowDraft | null>(null)
  const [revision, setRevision] = useState('')
  const [adding, setAdding] = useState(false)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')

  const schedule = useMemo<WorkflowSchedule>(() => scheduleType === 'manual' ? { type: 'manual' } : { type: scheduleType, time }, [scheduleType, time])
  const executionLabel = (actionId: string | undefined, riskLevel: WorkflowStep['risk_level']) => {
    const capability = capabilities.find((item) => item.action_id === actionId)
    return capability?.execution_mode === 'manual' ? '需要你完成' : riskLabels[riskLevel || 'medium']
  }

  const begin = async () => {
    if (!goal.trim()) return
    setWorking('design')
    setError('')
    try {
      const created = await createWorkflowDraft({ goal: goal.trim(), context, schedule, notification: 'in_app' })
      if (mode === 'ai') {
        const designed = await designWorkflowDraft(created.id)
        setDraft(designed)
      } else {
        setDraft({ ...created, name: '我的工作流方案', description: goal.trim(), outcome: '按计划完成目标并记录结果' })
      }
      setStage(2)
    } catch (e) {
      setError(e instanceof Error ? e.message : '方案设计失败，请稍后重试')
    } finally { setWorking('') }
  }

  const patchDraft = (changes: Partial<WorkflowDraft>) => setDraft((current) => current ? { ...current, ...changes } : current)
  const patchStep = (index: number, changes: Partial<WorkflowStep>) => {
    if (!draft) return
    const steps = [...draft.steps]
    steps[index] = { ...steps[index], ...changes }
    patchDraft({ steps })
  }
  const moveStep = (index: number, offset: number) => {
    if (!draft) return
    const target = index + offset
    if (target < 0 || target >= draft.steps.length) return
    const steps = [...draft.steps]
    ;[steps[index], steps[target]] = [steps[target], steps[index]]
    patchDraft({ steps })
  }
  const removeStep = (index: number) => draft && patchDraft({ steps: draft.steps.filter((_, itemIndex) => itemIndex !== index) })
  const addCapability = (capability: WorkflowCapability) => {
    if (!draft) return
    const step: WorkflowStep = {
      id: `step_${Date.now()}`, name: capability.name, description: capability.description,
      skill_name: capability.skill_name, action_id: capability.action_id, params: {}, condition: null,
      risk_level: capability.risk_level, confirmation_policy: capability.risk_level === 'high' ? 'every_run' : 'automatic',
      requires_confirmation: capability.risk_level === 'high', on_failure: capability.risk_level === 'high' ? 'needs_human' : 'stop',
    }
    patchDraft({ steps: [...draft.steps, step] })
    setAdding(false)
  }

  const revise = async () => {
    if (!draft || !revision.trim()) return
    setWorking('revise'); setError('')
    try { setDraft(await reviseWorkflowDraft(draft.id, revision.trim())); setRevision('') }
    catch (e) { setError(e instanceof Error ? e.message : '方案调整失败') }
    finally { setWorking('') }
  }

  const saveAndCheck = async () => {
    if (!draft || !draft.name.trim() || draft.steps.length === 0) return
    setWorking('validate'); setError('')
    try {
      const saved = await updateWorkflowDraft(draft.id, {
        name: draft.name.trim(), description: draft.description, outcome: draft.outcome,
        context: draft.context, schedule: draft.schedule, steps: draft.steps,
      })
      const validation = await validateWorkflowDraft(saved.id)
      const next = { ...saved, validation }
      setDraft(next)
      if (validation.valid) setStage(3)
      else setError(validation.issues.join('；'))
    } catch (e) { setError(e instanceof Error ? e.message : '方案检查失败') }
    finally { setWorking('') }
  }

  const activate = async () => {
    if (!draft) return
    setWorking('activate'); setError('')
    try { await activateWorkflowDraft(draft.id); onActivated() }
    catch (e) { setError(e instanceof Error ? e.message : '方案启用失败') }
    finally { setWorking('') }
  }

  const renderCondition = (step: WorkflowStep, index: number) => {
    if (!draft || index === 0) return null
    const condition = step.condition
    if (!condition) return <button onClick={() => patchStep(index, { condition: { step_id: draft.steps[index - 1].id, field: '', operator: 'not_empty', value: '' } })} className="mt-3 text-xs text-[#818CF8] hover:text-[#A5B4FC]">+ 添加执行条件</button>
    const needsValue = !['empty', 'not_empty'].includes(condition.operator)
    return (
      <div className="mt-3 rounded-lg border border-[#334155] bg-[#0A101C] p-3">
        <div className="mb-2 flex items-center justify-between"><span className="text-xs text-[#94A3B8]">仅当</span><button onClick={() => patchStep(index, { condition: null })} className="text-xs text-[#64748B] hover:text-[#FCA5A5]">移除条件</button></div>
        <div className="grid gap-2 md:grid-cols-3">
          <select value={condition.step_id} onChange={(e) => patchStep(index, { condition: { ...condition, step_id: e.target.value } })} className={inputClass}>{draft.steps.slice(0, index).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
          <input value={condition.field} onChange={(e) => patchStep(index, { condition: { ...condition, field: e.target.value } })} className={inputClass} placeholder="结果字段，如 needs_human" />
          <select value={condition.operator} onChange={(e) => patchStep(index, { condition: { ...condition, operator: e.target.value as WorkflowCondition['operator'] } })} className={inputClass}>{Object.entries(operatorLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        </div>
        {needsValue && <input value={String(condition.value ?? '')} onChange={(e) => patchStep(index, { condition: { ...condition, value: e.target.value } })} className={`${inputClass} mt-2`} placeholder="比较值" />}
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60" onMouseDown={(e) => { if (e.currentTarget === e.target) onClose() }}>
      <aside className="h-full w-full max-w-3xl overflow-y-auto border-l border-[#273449] bg-[#0F1624] shadow-2xl">
        <div className="sticky top-0 z-20 border-b border-[#273449] bg-[#0F1624]/95 px-6 py-5 backdrop-blur">
          <div className="flex items-start justify-between">
            <div><p className="text-xs text-[#818CF8]">{mode === 'ai' ? 'AI 协助设计' : '手动创建'}</p><h2 className="mt-1 text-lg font-semibold text-[#F1F5F9]">创建工作流方案</h2></div>
            <button onClick={onClose} className={iconButton}><X className="h-4 w-4" /></button>
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2">{['描述目标', '调整方案', '确认启用'].map((label, index) => <div key={label} className={`h-1.5 rounded-full ${stage >= index + 1 ? 'bg-[#6366F1]' : 'bg-[#273449]'}`} title={label} />)}</div>
        </div>

        <div className="space-y-6 p-6">
          {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}

          {stage === 1 && <>
            <div><label className="mb-2 block text-sm font-medium text-[#E2E8F0]">希望系统帮你完成什么？</label><textarea value={goal} onChange={(e) => setGoal(e.target.value)} rows={7} className={`${inputClass} resize-none text-sm leading-7`} placeholder="例如：每天上午 9 点检查所有渠道账号，发现掉线就提醒我，并整理昨天新增的高意向客户。" /></div>
            <div><p className="mb-3 text-sm font-medium text-[#E2E8F0]">设计时参考</p><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{contextOptions.map(({ key, label, icon: Icon }) => <button key={key} onClick={() => setContext({ ...context, [key]: !context[key] })} className={`flex h-12 items-center gap-3 rounded-lg border px-3 text-sm transition-colors ${context[key] ? 'border-[#6366F1] bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#334155] text-[#94A3B8] hover:border-[#475569]'}`}><span className={`flex h-5 w-5 items-center justify-center rounded border ${context[key] ? 'border-[#818CF8] bg-[#6366F1]' : 'border-[#475569]'}`}>{context[key] && <Check className="h-3.5 w-3.5 text-white" />}</span><Icon className="h-4 w-4" />{label}</button>)}</div></div>
            <div><p className="mb-3 text-sm font-medium text-[#E2E8F0]">运行计划</p><div className="grid grid-cols-3 gap-2">{(['manual', 'daily', 'weekly'] as WorkflowSchedule['type'][]).map((value) => <button key={value} onClick={() => setScheduleType(value)} className={`rounded-lg border px-3 py-2.5 text-sm ${scheduleType === value ? 'border-[#6366F1] bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#334155] text-[#94A3B8]'}`}>{value === 'manual' ? '手动运行' : value === 'daily' ? '每天' : '每周'}</button>)}</div>{scheduleType !== 'manual' && <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className={`${inputClass} mt-3 max-w-48`} />}</div>
            <button onClick={begin} disabled={!goal.trim() || working === 'design'} className={`${primaryButton} w-full py-3`}>{working === 'design' ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === 'ai' ? <Sparkles className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}{mode === 'ai' ? '设计方案' : '开始创建'}</button>
          </>}

          {stage === 2 && draft && <>
            <div className="grid gap-4 md:grid-cols-2"><div><label className="mb-2 block text-xs text-[#94A3B8]">方案名称</label><input value={draft.name} onChange={(e) => patchDraft({ name: e.target.value })} className={inputClass} /></div><div><label className="mb-2 block text-xs text-[#94A3B8]">完成后得到</label><input value={draft.outcome} onChange={(e) => patchDraft({ outcome: e.target.value })} className={inputClass} /></div></div>
            {mode === 'ai' && <div className="flex gap-2"><input value={revision} onChange={(e) => setRevision(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') revise() }} className={inputClass} placeholder="继续调整，例如：不要发送消息，只生成清单" /><button onClick={revise} disabled={!revision.trim() || working === 'revise'} className={secondaryButton}>{working === 'revise' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}调整</button></div>}
            <div className="space-y-3">{draft.steps.map((step, index) => <div key={step.id} className="rounded-lg border border-[#2B3850] bg-[#111A2A] p-4"><div className="flex gap-3"><GripVertical className="mt-2 h-4 w-4 shrink-0 text-[#475569]" /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#6366F1]/15 text-xs text-[#A5B4FC]">{index + 1}</span><input value={step.name} onChange={(e) => patchStep(index, { name: e.target.value })} className="min-w-40 flex-1 bg-transparent text-sm font-medium text-[#E2E8F0] outline-none" /><span className={`rounded-full px-2 py-1 text-[11px] ${step.risk_level === 'high' ? 'bg-[#F59E0B]/12 text-[#FBBF24]' : step.risk_level === 'medium' ? 'bg-[#3B82F6]/12 text-[#93C5FD]' : 'bg-[#10B981]/12 text-[#6EE7B7]'}`}>{executionLabel(step.action_id, step.risk_level)}</span></div><textarea value={step.description} onChange={(e) => patchStep(index, { description: e.target.value })} rows={2} className="mt-2 w-full resize-none bg-transparent text-xs leading-5 text-[#94A3B8] outline-none" />{renderCondition(step, index)}</div><div className="flex shrink-0 flex-col gap-1"><button onClick={() => moveStep(index, -1)} disabled={index === 0} className={iconButton}><ArrowUp className="h-3.5 w-3.5" /></button><button onClick={() => moveStep(index, 1)} disabled={index === draft.steps.length - 1} className={iconButton}><ArrowDown className="h-3.5 w-3.5" /></button><button onClick={() => removeStep(index)} className={iconButton}><Trash2 className="h-3.5 w-3.5" /></button></div></div></div>)}</div>
            <div><button onClick={() => setAdding(!adding)} className={`${secondaryButton} w-full border-dashed`}><Plus className="h-4 w-4" />添加一步</button>{adding && <div className="mt-2 max-h-72 overflow-y-auto rounded-lg border border-[#334155] bg-[#111827] p-2">{capabilities.map((item) => <button key={item.action_id} onClick={() => addCapability(item)} className="flex w-full items-start justify-between gap-3 rounded-lg px-3 py-3 text-left hover:bg-[#1E293B]"><span><span className="block text-sm text-[#E2E8F0]">{item.name}</span><span className="mt-1 block text-xs text-[#64748B]">{item.description}</span></span><span className="shrink-0 text-[11px] text-[#94A3B8]">{item.execution_mode === 'manual' ? '需要你完成' : riskLabels[item.risk_level || 'medium']}</span></button>)}</div>}</div>
            <div className="flex gap-3 border-t border-[#273449] pt-5"><button onClick={() => setStage(1)} className={`${secondaryButton} flex-1`}><ChevronLeft className="h-4 w-4" />上一步</button><button onClick={saveAndCheck} disabled={!draft.name.trim() || draft.steps.length === 0 || working === 'validate'} className={`${primaryButton} flex-1`}>{working === 'validate' ? <Loader2 className="h-4 w-4 animate-spin" /> : <ChevronRight className="h-4 w-4" />}检查方案</button></div>
          </>}

          {stage === 3 && draft && <>
            <div className="rounded-lg border border-[#10B981]/25 bg-[#10B981]/8 p-4"><div className="flex items-center gap-2 text-sm font-medium text-[#A7F3D0]"><Check className="h-4 w-4" />方案已通过检查</div><p className="mt-2 text-xs leading-5 text-[#6EE7B7]/80">启用后将按照计划运行。查询、整理和内部处理会自动完成，外部发布或发送等操作仍会等待你确认。</p></div>
            <div className="rounded-lg border border-[#273449] bg-[#0B0F1A] p-5"><h3 className="text-base font-semibold text-[#F1F5F9]">{draft.name}</h3><p className="mt-2 text-sm leading-6 text-[#94A3B8]">{draft.description}</p><div className="mt-5 space-y-3">{draft.steps.map((step, index) => <div key={step.id} className="flex items-start gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#6366F1]/15 text-xs text-[#A5B4FC]">{index + 1}</span><div><p className="text-sm text-[#E2E8F0]">{step.name}</p><p className="mt-1 text-xs text-[#64748B]">{step.description}</p>{step.risk_level === 'high' && <p className="mt-1 inline-flex items-center gap-1 text-xs text-[#FBBF24]"><AlertTriangle className="h-3 w-3" />执行时需要确认</p>}</div></div>)}</div></div>
            <div className="flex gap-3"><button onClick={() => setStage(2)} className={`${secondaryButton} flex-1`}><ChevronLeft className="h-4 w-4" />继续调整</button><button onClick={activate} disabled={working === 'activate'} className={`${primaryButton} flex-1 py-3`}>{working === 'activate' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}确认并启用</button></div>
          </>}
        </div>
      </aside>
    </div>
  )
}
