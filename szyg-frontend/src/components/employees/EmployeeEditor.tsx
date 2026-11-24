import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { ArrowLeft, Check, ChevronDown, LoaderCircle, Upload, X } from 'lucide-react'
import { useI18n } from '@/lib/i18n'
import { fileToAvatarDataUrl } from '@/lib/avatar'
import { apiGet } from '@/lib/api'
import RobotAvatar, { defaultRobotPreset, robotPresets, DIRECTOR_AVATAR, XIAOYU_AVATAR } from '@/components/ui/RobotAvatar'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'

export type AccessMode = 'read-only' | 'guarded' | 'workspace' | 'full'
export type EmployeeProfile = {
  name: string
  title: string
  instructions: string
  avatar: string
  model: string
  permissionMode: AccessMode
}
export const employeeModels = [
  ['doubao-seed-evolving', 'Doubao Seed Evolving'],
  ['deepseek-v4-1-flash-economy-261017', 'DeepSeek-V4.1-Flash'],
  ['kimi-k3-1-pro-261024', 'Kimi-k3.1-pro'],
] as const

type ModelRate = { input: number; cached_input: number; output: number }
export type EmployeeModelInfo = { id: string; available: boolean; status: string; pricing?: ModelRate & { peak?: ModelRate } }

export function employeeModelUnavailableReason(catalog: EmployeeModelInfo[], id: string) {
  const status = catalog.find(item => item.id === id)?.status
  if (status === 'gateway_upgrade_required') return 'employee.modelGatewayUpdate'
  if (status === 'unavailable') return 'employee.modelUnavailable'
}
export function useEmployeeModels() {
  const [catalog, setCatalog] = useState<EmployeeModelInfo[]>([])
  useEffect(() => {
    let mounted = true
    void apiGet<{items:EmployeeModelInfo[]}>('/api/cloud/employee-models').then(result => {
      if (mounted && Array.isArray(result?.items)) setCatalog(result.items)
    }).catch(() => {})
    return () => { mounted = false }
  }, [])
  return catalog
}

export function ModelNote({ value, catalog, compact = false }: {
  value: string
  catalog: EmployeeModelInfo[]
  compact?: boolean
}) {
  const { t } = useI18n()
  const rate = catalog.find(item => item.id === value)?.pricing
  if (compact || !rate) return null
  const formattedRate = (price: ModelRate) => t('employee.tokenPrices', {
    input: price.input, cached: price.cached_input, output: price.output,
  })
  return <div className="space-y-1 text-xs leading-5 text-muted-foreground">
    <p>{t('employee.priceUnit')}</p>
    <p>{rate.peak && t('employee.offPeak')}{formattedRate(rate)}</p>
    {rate.peak && <><p>{t('employee.peak')}{formattedRate(rate.peak)}</p><p>{t('employee.peakTime')}</p></>}
  </div>
}

export function ModelPicker({ value, onChange, catalog, disabled = false }: {
  value: string; onChange: (value: string) => void; catalog: EmployeeModelInfo[]; disabled?: boolean
}) {
  const { t } = useI18n()
  return <span className="relative inline-flex max-w-full items-center">
    <select aria-label={t('employee.model')} disabled={disabled} className="employee-select" value={value} onChange={event => onChange(event.target.value)}>
      <option value="auto">{t('employee.autoModel')}</option>
      {employeeModels.map(([id, label]) => {
        const reason = employeeModelUnavailableReason(catalog, id)
        return <option key={id} value={id} disabled={Boolean(reason)}>{label}{reason ? ' · ' + t(reason) : ''}</option>
      })}
    </select>
    <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-muted-foreground" />
  </span>
}

export function AccessSwitch({ value, onChange, disabled }: { value: AccessMode; onChange: (mode: AccessMode) => void; disabled?: boolean }) {
  const { t } = useI18n()
  const full = value === 'full'
  return <label className={'inline-flex cursor-pointer items-center gap-2 whitespace-nowrap text-xs font-medium' + (full ? ' text-danger-ink' : '')}>
    <Switch className="data-[state=checked]:bg-destructive" checked={full} disabled={disabled} aria-label={t('employee.fullAccess')}
      onCheckedChange={checked => onChange(checked ? 'full' : 'guarded')} />
    {t('employee.fullAccess')}
  </label>
}

function AvatarPicker({ value, onChange, identity, onLoading }: { value: string; onChange: (avatar: string) => void; identity: string; onLoading: (loading: boolean) => void }) {
  const { t } = useI18n()
  const input = useRef<HTMLInputElement>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const activePreset = value || defaultRobotPreset(identity)
  async function upload(file: File | undefined) {
    if (!file) return
    setError('')
    if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
      setError(t('employee.fileTypes')); return
    }
    setLoading(true); onLoading(true)
    try { onChange(await fileToAvatarDataUrl(file, 256)) }
    catch { setError(t('图片处理失败，请换一张图片重试')) }
    finally { setLoading(false); onLoading(false) }
  }
  return <fieldset disabled={loading} className="min-w-0">
    <legend className="employee-field-label">{t('employee.avatar')}</legend>
    <div className="flex flex-wrap items-center gap-2">
      <RobotAvatar identity={identity} avatar={activePreset} className="mr-1 h-12 w-12 rounded-xl" />
      <div className="flex flex-wrap items-center gap-1.5 border-l pl-3">
        {[XIAOYU_AVATAR, DIRECTOR_AVATAR, ...robotPresets].map(preset => <button type="button" key={preset} aria-pressed={activePreset === preset}
          aria-label={preset === XIAOYU_AVATAR ? t('小妤') : preset === DIRECTOR_AVATAR ? t('director.name') : t('employee.preset', { number: robotPresets.indexOf(preset) + 1 })} onClick={() => { setError(''); onChange(preset) }}
          className="rounded-[10px] border-2 border-transparent p-0.5 hover:bg-muted aria-pressed:border-primary">
          <RobotAvatar identity={identity} avatar={preset} className="block h-8 w-8 rounded-md" />
        </button>)}
        <button type="button" title={t('employee.upload')} aria-label={t('employee.upload')} onClick={() => input.current?.click()}
          className="grid h-9 w-9 place-items-center rounded-lg border border-dashed border-input hover:bg-muted">
          {loading ? <LoaderCircle size={16} className="animate-spin"/> : <Upload size={16}/>}
        </button>
        <input ref={input} type="file" className="hidden" accept="image/png,image/jpeg,image/webp" onChange={e => { const file=e.target.files?.[0]; e.target.value=''; void upload(file) }}/>
      </div>
    </div>
    {error && <p role="alert" className="mt-2 text-sm text-danger-ink">{error}</p>}
  </fieldset>
}

export function EmployeeModal({ title, children, onClose, busy = false }: { title: string; children: ReactNode; onClose: () => void; busy?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => { const node = ref.current!; node.showModal(); return () => node.close() }, [])
  return <dialog ref={ref} aria-labelledby={titleId} className="employee-modal" onCancel={e => {e.preventDefault(); if (!busy) onClose()}}
    onClick={e => { if (!busy && e.target === ref.current) { const b = ref.current!.getBoundingClientRect(); if (e.clientX < b.left || e.clientX > b.right || e.clientY < b.top || e.clientY > b.bottom) onClose() } }}>
    <header className="flex items-center justify-between gap-3 border-b px-6 py-4">
      <h2 id={titleId} className="text-lg font-semibold tracking-tight">{title}</h2>
      <CloseButton disabled={busy} onClick={onClose}/>
    </header>
    {children}
  </dialog>
}
function CloseButton({onClick,disabled}: {onClick: () => void; disabled?: boolean}) {
  const {t}=useI18n()
  return <button type="button" disabled={disabled} aria-label={t('关闭')} onClick={onClick} className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"><X size={17}/></button>
}

export function EmployeeEditor({ mode, initial, identity, onSave, onClose, catalog }: {
  mode: 'create' | 'details' | 'avatar'; catalog: EmployeeModelInfo[]; initial: EmployeeProfile; identity: string; onClose: () => void
  onSave: (profile: EmployeeProfile, original: EmployeeProfile) => Promise<void>
}) {
  const { t } = useI18n()
  const [original] = useState(initial)
  const [draft, setDraft] = useState(() => mode === 'create' ? { ...initial, avatar: XIAOYU_AVATAR } : initial)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const submitting = useRef(false)
  const patch = (value: Partial<EmployeeProfile>) => setDraft(previous => ({...previous,...value}))
  const avatarOnly = mode === 'avatar'
  const busy = uploading || saving
  const title = mode === 'create' ? t('新建员工') : avatarOnly ? t('更换头像') : t('employee.details')
  const form = <form className="flex min-h-0 flex-col" onSubmit={async event => {
    event.preventDefault()
    if (busy || submitting.current || (!avatarOnly && !draft.name.trim())) return
    submitting.current = true; setSaving(true); setError('')
    try { await onSave({...draft,name:draft.name.trim(),instructions:draft.instructions.trim()}, original); onClose() }
    catch (reason) {setError(reason instanceof Error ? reason.message : t('操作暂时没有完成，请稍后重试。'))}
    finally { submitting.current = false; setSaving(false) }
  }}>
    <fieldset disabled={saving} className="min-h-0 space-y-5 overflow-auto px-6 py-5">
      <AvatarPicker value={draft.avatar} identity={identity} onChange={avatar => patch({avatar})} onLoading={setUploading}/>
      {!avatarOnly && <>
        <label className="block"><span className="employee-field-label">{t('employee.name')}</span>
          <input autoFocus={mode === 'create'} className="employee-input" required maxLength={80}
            value={draft.name} onChange={event => patch({name: event.target.value})} />
        </label>
        <label className="block"><span className="employee-field-label">{t('employee.instructions')}</span>
          <textarea rows={4} maxLength={8000} className="employee-input min-h-24 resize-y leading-6" value={draft.instructions}
            onChange={e=>patch({instructions:e.target.value})}/></label>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
          <label className="text-sm font-medium">{t('employee.defaultModel')}</label>
          <ModelPicker value={draft.model} catalog={catalog} onChange={model=>patch({model})}/>
        </div>
        <ModelNote value={draft.model} catalog={catalog}/>
        <div>
          <AccessSwitch value={draft.permissionMode} onChange={permissionMode=>patch({permissionMode})}/>
          {draft.permissionMode === 'full' && <p role="status" className="mt-2 text-xs leading-5 text-danger-ink">{t('employee.fullAccessRisk')}</p>}
        </div>
      </>}
    </fieldset>
    {error && <p role="alert" className="mx-6 mb-3 rounded-lg bg-danger-soft p-3 text-sm text-danger-ink">{error}</p>}
    <footer className="flex justify-end gap-2 border-t px-6 py-3">
      <Button type="button" variant="outline" disabled={busy} onClick={onClose}>{t(mode === 'details' ? 'employee.backChat' : '取消')}</Button>
      <Button type="submit" disabled={busy || (!avatarOnly && !draft.name.trim())}>{saving ? <LoaderCircle className="animate-spin"/> : <Check/>}{t(mode === 'create' ? '创建' : 'employee.save')}</Button>
    </footer>
  </form>
  if (mode !== 'details') return <EmployeeModal title={title} onClose={onClose} busy={busy}>{form}</EmployeeModal>
  return <section className="min-w-0 flex-1 overflow-y-auto bg-background">
    <div className="mx-auto max-w-2xl py-5">
      <header className="flex items-center gap-3 border-b px-6 pb-4">
        <button type="button" disabled={busy} onClick={onClose} aria-label={t('employee.backChat')} className="rounded-lg border p-2 hover:bg-muted"><ArrowLeft size={16}/></button>
        <div><h2 className="text-lg font-semibold">{initial.name}</h2><p className="text-xs text-muted-foreground">{title}</p></div>
      </header>{form}
    </div>
  </section>
}
