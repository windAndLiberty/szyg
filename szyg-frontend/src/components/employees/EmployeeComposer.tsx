import { useEffect, useId, useRef, useState, type Dispatch, type KeyboardEvent, type MouseEvent, type SetStateAction } from 'react'
import { ArrowUp, BrainCircuit, Check, ChevronUp, LoaderCircle, Mic, Paperclip, Plus, Puzzle, Search, ShieldAlert, ShieldCheck, Square, Wrench, X } from 'lucide-react'
import { useKeepAlivePageActive } from '@/lib/hooks'
import { useI18n } from '@/lib/i18n'
import type { useConversationExperts } from '@/lib/useConversationExperts'
import { employeeModels, employeeModelUnavailableReason, type AccessMode, type EmployeeModelInfo } from './EmployeeEditor'
import { useConversationResources } from './useConversationResources'
import { useDictation } from './useDictation'
import { useEmployeeMedia, type EmployeeAsset } from './DirectorMedia'
import './EmployeeComposer.css'

type Panel = 'add' | 'access' | 'model'
const addCategories = {
  experts: { label:'composer.experts', search:'composer.searchExpert' },
  skills: { label:'composer.skills', search:'composer.searchSkill' },
  capabilities: { label:'composer.capabilities', search:'composer.searchCapability' },
} as const
type AddCategory = keyof typeof addCategories
type Props = {
  value: string
  onChange: (value: string) => void
  onTranscribed: (text: string) => void
  director: boolean
  agentId: string
  sessionKey: string
  createSession: () => Promise<string | null>
  assets: EmployeeAsset[]
  onAssetsChange: Dispatch<SetStateAction<EmployeeAsset[]>>
  onSend: (text: string) => boolean
  onStop?: () => void
  disabled: boolean
  settingsDisabled: boolean
  sending: boolean
  readOnly: boolean
  model: string
  modelCatalog: EmployeeModelInfo[]
  onModelChange: (model: string) => void
  access: AccessMode
  onAccessChange: (mode: AccessMode) => void
  reasoning: boolean
  reasoningFixed: boolean
  onReasoningChange: () => void
  experts: ReturnType<typeof useConversationExperts>
}
const accessLabels = { guarded: 'composer.guarded', workspace: 'composer.workspace', 'read-only': 'composer.readOnly', full: 'employee.fullAccess' } as const

export default function EmployeeComposer(props: Props) {
  const { t } = useI18n()
  const { experts, access, model } = props
  const [panel, setPanel] = useState<Panel | null>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<AddCategory>('experts')
  const popup = useRef<HTMLDivElement>(null)
  const opener = useRef<HTMLButtonElement | null>(null)
  const popupId = useId()
  const pageActive = useKeepAlivePageActive()
  const voice = useDictation(pageActive && !props.disabled, props.onTranscribed)
  const fileInput = useRef<HTMLInputElement>(null)
  const media = useEmployeeMedia(pageActive && !props.disabled, props.assets, props.onAssetsChange)
  const resourceOptions = {agentId:props.agentId,sessionKey:props.sessionKey,createSession:props.createSession,
    disabled:props.disabled || props.settingsDisabled || props.readOnly}
  const skills = useConversationResources('skills', resourceOptions)
  const capabilities = useConversationResources('capabilities', resourceOptions)
  const resourceBusy = skills.busy || capabilities.busy || experts.busy
  const voiceBusy = voice.state !== 'idle'
  const canSend = !props.disabled && !props.settingsDisabled && !props.sending && !voiceBusy && (!!props.value.trim() || media.assets.length > 0) && !resourceBusy && !media.busy
  function send() {
    if (!canSend) return
    if (props.onSend(media.message(props.value))) media.clear()
  }
  const availableModels = [['auto', t('composer.auto')], ...employeeModels]
  const modelName = availableModels.find(([id]) => id === model)?.[1] || model
  const search = query.trim().toLocaleLowerCase()
  const filtered = experts.catalog.filter(expert => (expert.name + ' ' + expert.slug + ' ' + expert.division + ' ' + expert.description).toLocaleLowerCase().includes(search))

  const isCapability = category === 'capabilities'
  const resource = isCapability ? capabilities : skills
  const ResourceIcon = isCapability ? Wrench : Puzzle
  const shownResources = resource.catalog.filter(item => [item.name, item.title, item.domain, item.description].join(' ').toLocaleLowerCase().includes(search))
  const searchLabel = t(addCategories[category].search)

  function chooseCategory(next: AddCategory) {
    setCategory(next)
    setQuery('')
    if (next === 'experts') void experts.loadCatalog()
    else void (next === 'skills' ? skills : capabilities).loadCatalog()
  }

  function closePanel(restore = false) {
    setPanel(null)
    if (restore) opener.current?.focus()
  }
  function togglePanel(next: Panel, button: HTMLButtonElement) {
    if (panel === next) { closePanel(); return }
    opener.current = button
    if (next === 'add') chooseCategory(category)
    setPanel(next)
  }
  useEffect(() => {
    if (!panel) return
    const dismiss = (event: PointerEvent | FocusEvent) => {
      if (event.target instanceof Node && !popup.current?.contains(event.target) && !opener.current?.contains(event.target)) setPanel(null)
    }
    const focus = popup.current?.querySelector<HTMLElement>('input')
      || popup.current?.querySelector<HTMLElement>('[aria-pressed="true"]:not(:disabled)')
      || popup.current?.querySelector<HTMLElement>('button:not(:disabled)')
    focus?.focus({preventScroll:true})
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('focusin', dismiss)
    return () => {
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('focusin', dismiss)
    }
  }, [panel])
  useEffect(() => { if (!pageActive || props.disabled) setPanel(null) }, [pageActive, props.disabled])

  function onPanelKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') { event.preventDefault(); closePanel(true); return }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'))
    if (!buttons.length) return
    event.preventDefault()
    const index = buttons.findIndex(item => item === document.activeElement)
    const next = event.key === 'ArrowDown' ? index + 1 : index < 0 ? buttons.length - 1 : index - 1
    buttons[(next + buttons.length) % buttons.length].focus()
  }
  function panelButton(which: Panel, label: string) {
    return {
      'aria-expanded': panel === which, 'aria-haspopup': 'dialog' as const, 'aria-controls': panel === which ? popupId : undefined,
      'aria-label': label, title: label, disabled: props.settingsDisabled || props.disabled || resourceBusy,
      onClick: (event: MouseEvent<HTMLButtonElement>) => togglePanel(which, event.currentTarget),
    }
  }
  const accessLabel = t(accessLabels[access])
  const voiceLabel = t(voice.state === 'recording' ? 'composer.voiceFinish' : 'composer.microphone')
  return <div className="employee-composer-frame">
    <div className="employee-composer"
      onDragOver={event => { if (event.dataTransfer.types.includes('Files')) event.preventDefault() }}
      onDrop={event => {
        if (!event.dataTransfer.files.length) return
        event.preventDefault()
        if (!props.disabled && !props.settingsDisabled) void media.add(Array.from(event.dataTransfer.files))
      }}>
      <input ref={fileInput} type="file" hidden multiple accept="image/*,video/*,audio/*"
        aria-label={t('director.import')} onChange={event => {
          const files = Array.from(event.target.files || [])
          event.target.value = ''
          void media.add(files)
        }}/>
      {media.assets.length > 0 && <div className="composer-chips">
        {media.assets.map(asset => <button key={asset.url} type="button" className="composer-chip"
          onClick={() => media.remove(asset.url)} aria-label={t('director.detach', {name:asset.name})}>
          <Paperclip size={13}/><span>{asset.name}</span><X size={13}/>
        </button>)}
      </div>}
      {media.busy && <div className="composer-notice composer-voice" role="status"><LoaderCircle size={14} className="animate-spin"/>{t('director.importing')}</div>}
      {props.readOnly && <p className="composer-notice">{t('employee.historyOnly')}</p>}
      {experts.active.length > 0 && <div className="composer-chips">
        {experts.active.map(expert => <button type="button" key={expert.slug} className="composer-chip"
          disabled={props.disabled || props.settingsDisabled || experts.busy} onClick={() => void experts.detach(expert.slug)}
          aria-label={t('composer.removeExpert', {name:expert.name})} title={expert.source === 'auto' ? t('composer.autoExpert') : expert.description}>
          <span>{expert.name}</span><X size={13} aria-hidden="true"/>
        </button>)}
      </div>}
      {skills.selected.length > 0 && <div className="composer-chips">
        {skills.selected.map(name => <button type="button" key={name} className="composer-chip"
          disabled={props.disabled || props.settingsDisabled || skills.busy}
          onClick={() => void skills.change('detach',name)} aria-label={t('composer.removeSkill',{name})}>
          <Puzzle size={13} aria-hidden="true"/><span>{name}</span><X size={13} aria-hidden="true"/>
        </button>)}
      </div>}
      {capabilities.selected.length > 0 && <div className="composer-chips">
        {capabilities.selected.map(name => {
          const title = capabilities.titles[name] || name
          return <button type="button" key={name} className="composer-chip" disabled={props.disabled || props.settingsDisabled || resourceBusy}
            onClick={() => void capabilities.change('detach',name)} aria-label={t('composer.removeCapability',{name:title})}>
            <Wrench size={13} aria-hidden="true"/><span>{title}</span><X size={13} aria-hidden="true"/>
          </button>
        })}
      </div>}
      <textarea rows={2} aria-label={t('composer.draft')} placeholder={t(props.director ? 'director.placeholder' : '交代目标、资料和完成标准…')} value={props.value}
        disabled={props.disabled} onChange={event => props.onChange(event.target.value)} onPaste={event => {
          if (props.settingsDisabled) return
          const files = Array.from(event.clipboardData.files).filter(file => /^(image|audio|video)\//.test(file.type))
          if (!files.length) return
          event.preventDefault()
          void media.add(files)
        }} onKeyDown={event => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229) {
            event.preventDefault()
            send()
          }
        }}/>
      {voiceBusy && <div className="composer-notice composer-voice" role="status">
        {voice.state === 'recording' ? <span className="composer-record-dot"/> : <LoaderCircle size={14} className="animate-spin"/>}
        {voice.state === 'recording' ? t('composer.recording',{time:Math.floor(voice.seconds / 60) + ':' + String(voice.seconds % 60).padStart(2, '0')}) : t(voice.state === 'requesting' ? 'composer.requesting' : 'composer.transcribing')}
        <button type="button" onClick={voice.cancel}>{t('取消')}</button>
      </div>}
      {(media.error || voice.error || experts.error || skills.error || capabilities.error) && <p className="composer-notice text-danger-ink" role="alert">{media.error || voice.error || experts.error || skills.error || capabilities.error}</p>}
      <div className="composer-toolbar">
        <button type="button" className="composer-control composer-icon" {...panelButton('add', t('composer.add'))}><Plus size={19}/></button>
        <button type="button" className={'composer-control composer-access' + (access === 'full' ? ' composer-danger' : '')}
          {...panelButton('access', t('composer.access') + ' · ' + accessLabel)}>
          {access === 'full' ? <ShieldAlert size={16}/> : <ShieldCheck size={16}/>}<span>{accessLabel}</span><ChevronUp size={12}/>
        </button>
        <div className="composer-spacer"/>
        <button type="button" className="composer-control composer-model" {...panelButton('model', t('employee.model') + ' · ' + modelName)}>
          <span>{modelName}</span><ChevronUp size={13}/>
        </button>
        <button type="button" className={'composer-control composer-icon' + (voice.state === 'recording' ? ' composer-danger' : '')}
          disabled={props.disabled || props.sending || voice.state === 'requesting' || voice.state === 'transcribing'}
          aria-label={voiceLabel} title={voice.state === 'idle' ? t('composer.voiceHint') : voiceLabel} onClick={() => void voice.toggle()}>
          {voice.state === 'transcribing' || voice.state === 'requesting' ? <LoaderCircle className="animate-spin" size={16}/> : voice.state === 'recording' ? <Square size={14} fill="currentColor"/> : <Mic size={17}/>}
        </button>
        {props.sending ? <button type="button" className="composer-send" title={t('停止')} aria-label={t('停止')} disabled={!props.onStop} onClick={props.onStop}><Square size={13} fill="currentColor"/></button>
          : <button type="button" className="composer-send" title={t('发送')} aria-label={t('发送')} disabled={!canSend} onClick={send}><ArrowUp size={18} strokeWidth={2.5}/></button>}

        {panel && <div className={'composer-popup composer-popup-' + panel} id={popupId} ref={popup} role="dialog" aria-label={t(panel === 'add' ? 'composer.add' : panel === 'access' ? 'composer.access' : 'employee.model')} onKeyDown={onPanelKey}>
          {panel === 'add' && <>
            <button type="button" className="composer-option" disabled={media.busy || props.settingsDisabled}
              onClick={() => { closePanel(true); fileInput.current?.click() }}><Paperclip size={15}/><span>{t('director.import')}</span></button>
            <div className="composer-add-categories" role="group" aria-label={t('composer.add')}>
              {(['experts','skills','capabilities'] as const).map(key => <button key={key} type="button" aria-pressed={category === key}
                onClick={() => chooseCategory(key)}>{t(addCategories[key].label)}</button>)}
            </div>
            <label className="composer-search"><Search size={15}/><input value={query} aria-label={searchLabel} placeholder={searchLabel} onChange={event => setQuery(event.target.value)}/></label>
            <div className="composer-results">
              {category !== 'experts' ? (
                resource.loading ? <p className="composer-notice" role="status">{t('settings.loading')}</p>
                : resource.loadError ? <p className="composer-notice">{t(isCapability ? 'composer.capabilityLoadFailed' : 'composer.skillLoadFailed')} <button type="button" onClick={() => void resource.loadCatalog()}>{t('composer.retry')}</button></p>
                : !shownResources.length ? <p className="composer-notice">{t(isCapability ? (search ? 'composer.noCapabilityMatches' : 'composer.noCapability') : (search ? 'composer.noSkillMatches' : 'composer.noSkill'))}</p>
                : shownResources.map(item => {
                  const selected = resource.selected.includes(item.name)
                  return <button type="button" className="composer-option" key={item.name} aria-pressed={selected} disabled={resourceBusy || props.settingsDisabled}
                    onClick={() => { closePanel(true); void resource.change(selected ? 'detach' : 'attach',item.name) }}>
                    <ResourceIcon size={15} aria-hidden="true"/>
                    <span className="composer-expert-info"><strong>{item.title || item.name}</strong>{item.description && <small>{item.description}</small>}</span>
                    {selected && <Check size={15}/>}
                  </button>
                })
              ) : experts.loading && !experts.catalog.length ? <p className="composer-notice" role="status">{t('settings.loading')}</p>
                : !filtered.length ? <p className="composer-notice">{experts.error ? <button type="button" onClick={() => void experts.loadCatalog()}>{t('composer.retry')}</button> : t('composer.noExpert')}</p> : filtered.map(expert => {
                  const selected = experts.active.some(item => item.slug === expert.slug)
                  return <button type="button" key={expert.slug} className="composer-option" aria-pressed={selected} disabled={experts.busy || props.settingsDisabled}
                    onClick={() => { closePanel(true); void (selected ? experts.detach(expert.slug) : experts.attach(expert.slug)) }}>
                    <span className="composer-expert-info"><strong>{expert.name}</strong><small>{expert.description}</small></span>{selected && <Check size={15}/>}
                  </button>
                })}
            </div>
          </>}
          {panel === 'access' && <>
            <h3>{t('composer.access')}</h3>
            {(['guarded', ...(access === 'workspace' || access === 'read-only' ? [access] : []), 'full'] as AccessMode[]).map(mode =>
              <button type="button" key={mode} className={'composer-option' + (mode === 'full' ? ' composer-danger' : '')} aria-pressed={access === mode} disabled={props.settingsDisabled}
                onClick={() => { props.onAccessChange(mode); if (mode !== 'full') closePanel(true) }}>
                {mode === 'full' ? <ShieldAlert size={16}/> : <ShieldCheck size={16}/>}<span>{t(accessLabels[mode])}</span>{access === mode && <Check size={15}/>}
              </button>)}
            {access === 'full' && <p className="composer-risk">{t('employee.fullAccessRisk')}</p>}
          </>}
          {panel === 'model' && <>
            <h3>{t('employee.model')}</h3>
            {availableModels.map(([id, label]) => {
              const reason = employeeModelUnavailableReason(props.modelCatalog, id)
              return <button type="button" key={id} className="composer-option" aria-pressed={model === id} disabled={props.settingsDisabled || Boolean(reason)}
                onClick={() => { closePanel(true); props.onModelChange(id) }}>
                <span>{label}{reason ? ' · ' + t(reason) : ''}</span>{model === id && <Check size={15}/>}
              </button>
            })}
            <div className="composer-menu-footer"><button type="button" className="composer-option" role="switch" aria-checked={props.reasoning}
              title={t(props.reasoningFixed ? 'employee.fixedReasoning' : 'employee.reasoningHint')} disabled={props.reasoningFixed || props.settingsDisabled} onClick={props.onReasoningChange}>
              <BrainCircuit size={15}/><span>{t('深度思考')}</span><i className={'composer-switch' + (props.reasoning ? ' is-on' : '')} aria-hidden="true"/>
            </button></div>
          </>}
        </div>}
      </div>
    </div>
  </div>
}
