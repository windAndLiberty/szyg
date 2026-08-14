import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  ChevronRight,
  CircleAlert,
  ClipboardPaste,
  FileAudio,
  FileImage,
  FileVideo,
  ImagePlus,
  Link2,
  Loader2,
  Mic2,
  Plus,
  RefreshCw,
  Save,
  Send,
  Sparkles,
  Trash2,
  Upload,
  UserRound,
  WandSparkles,
  X,
} from 'lucide-react'
import {
  analyzeDigitalHumanInspiration,
  createDigitalHumanProfile,
  createDigitalHumanProject,
  createDigitalHumanRender,
  deleteDigitalHumanInspiration,
  deleteDigitalHumanProfile,
  fetchDigitalHumanAssets,
  fetchDigitalHumanConfig,
  fetchDigitalHumanInspirations,
  fetchDigitalHumanProfiles,
  fetchDigitalHumanProjects,
  fetchDigitalHumanRender,
  generateDigitalHumanSceneImage,
  getErrorMessage,
  importDigitalHumanInspiration,
  planDigitalHumanProject,
  retryDigitalHumanRenderSegment,
  updateDigitalHumanProject,
  uploadDigitalHumanAsset,
  type DigitalHumanAsset,
  type DigitalHumanConfig,
  type DigitalHumanInspiration,
  type DigitalHumanProfile,
  type DigitalHumanProject,
  type DigitalHumanRender,
  type DigitalHumanScene,
} from '@/lib/api'
import { PublishSelectedDrawer, type Asset as PublishAsset } from './AssetManagement'

const STEPS = [
  { id: 1, label: '灵感视频素材' },
  { id: 2, label: '数字人形象' },
  { id: 3, label: '文案与画面' },
  { id: 4, label: '生成与发布' },
]

const ROLE_LABELS: Record<string, string> = {
  avatar_reference: '人物', product_reference: '产品', background_reference: '背景',
  motion_reference: '动作', voice_reference: '声音', brand_asset: '品牌',
  inspiration_reference: '灵感', scene_reference: '背景',
}

const visualModes = [
  ['presenter', '数字人口播'], ['full_image', '全屏插图'], ['product_closeup', '产品特写'],
  ['integrated', '场景融合'], ['creative_cutaway', '创意转场'],
] as const

const presenterModes = [['full', '全屏口播'], ['pip', '画中画'], ['hidden', '隐藏数字人']] as const

function freshScene(order: number): DigitalHumanScene {
  return {
    id: `scene_${crypto.randomUUID().slice(0, 8)}`,
    order,
    spoken_text: '',
    visual_prompt: '',
    duration: 5,
    presenter_mode: 'full',
    visual_mode: 'presenter',
    reference_asset_ids: [],
    transition: '自然衔接',
    subtitle: true,
    sound_prompt: '保留清晰自然的人声',
  }
}

function mediaIcon(kind: string) {
  if (kind === 'audio') return FileAudio
  if (kind === 'video') return FileVideo
  return FileImage
}

function AssetThumb({ asset, compact = false }: { asset: DigitalHumanAsset; compact?: boolean }) {
  const Icon = mediaIcon(asset.kind)
  const size = compact ? 'h-9 w-9' : 'h-14 w-14'
  return (
    <div className={`${size} shrink-0 overflow-hidden rounded-md border border-[#2A3448] bg-[#0A0E18]`}>
      {asset.kind === 'image' ? (
        <img src={asset.url} alt={asset.name} className="h-full w-full object-cover" />
      ) : asset.kind === 'video' ? (
        <video src={asset.url} muted preload="metadata" className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-[#8EA0BA]"><Icon className="h-5 w-5" /></div>
      )}
    </div>
  )
}

function EmptyState({ icon: Icon, title, text }: { icon: typeof Sparkles; title: string; text: string }) {
  return (
    <div className="flex min-h-52 flex-col items-center justify-center border border-dashed border-[#2B3850] bg-[#0B101B]/40 px-6 text-center">
      <Icon className="mb-3 h-7 w-7 text-[#7184A3]" />
      <p className="text-sm font-medium text-[#E7ECF5]">{title}</p>
      <p className="mt-1 max-w-sm text-xs leading-5 text-[#7F8DA5]">{text}</p>
    </div>
  )
}

export default function DigitalHumanStudio() {
  const [step, setStep] = useState(1)
  const [config, setConfig] = useState<DigitalHumanConfig | null>(null)
  const [assets, setAssets] = useState<DigitalHumanAsset[]>([])
  const [profiles, setProfiles] = useState<DigitalHumanProfile[]>([])
  const [inspirations, setInspirations] = useState<DigitalHumanInspiration[]>([])
  const [projects, setProjects] = useState<DigitalHumanProject[]>([])
  const [project, setProject] = useState<DigitalHumanProject | null>(null)
  const [render, setRender] = useState<DigitalHumanRender | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourceUrlMenu, setSourceUrlMenu] = useState<{ x: number; y: number } | null>(null)
  const [planInstruction, setPlanInstruction] = useState('')
  const [showProfileForm, setShowProfileForm] = useState(false)
  const [profileName, setProfileName] = useState('')
  const [profileType, setProfileType] = useState<'virtual' | 'real'>('virtual')
  const [profileAvatarIds, setProfileAvatarIds] = useState<string[]>([])
  const [profileVoiceId, setProfileVoiceId] = useState('')
  const [publishAsset, setPublishAsset] = useState<PublishAsset | null>(null)
  const hydrated = useRef(false)
  const inspirationInput = useRef<HTMLInputElement>(null)
  const sourceUrlInput = useRef<HTMLInputElement>(null)
  const avatarInput = useRef<HTMLInputElement>(null)
  const voiceInput = useRef<HTMLInputElement>(null)
  const sceneUploadInput = useRef<HTMLInputElement>(null)
  const [sceneUploadTarget, setSceneUploadTarget] = useState('')

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [cfg, assetData, profileData, inspirationData, projectData] = await Promise.all([
        fetchDigitalHumanConfig(), fetchDigitalHumanAssets(), fetchDigitalHumanProfiles(),
        fetchDigitalHumanInspirations(), fetchDigitalHumanProjects(),
      ])
      setConfig(cfg)
      setAssets(assetData.items)
      setProfiles(profileData.items)
      setInspirations(inspirationData.items)
      setProjects(projectData.items)
      let selected = projectData.items[0]
      if (!selected) {
        selected = await createDigitalHumanProject({ name: '我的数字人口播', scenes: [freshScene(1)] })
        setProjects([selected])
      }
      setProject(selected)
      setError('')
      window.setTimeout(() => { hydrated.current = true }, 0)
    } catch (err) {
      setError(getErrorMessage(err, '数字人创作加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void loadAll() }, [loadAll])

  useEffect(() => {
    if (!sourceUrlMenu) return
    const close = () => setSourceUrlMenu(null)
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    window.addEventListener('blur', close)
    window.addEventListener('scroll', close, true)
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      window.removeEventListener('blur', close)
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [sourceUrlMenu])

  useEffect(() => {
    if (!project || !hydrated.current) return
    const timer = window.setTimeout(async () => {
      try {
        const saved = await updateDigitalHumanProject(project.id, project)
        setProjects((current) => current.map((item) => item.id === saved.id ? saved : item))
      } catch (err) {
        setError(getErrorMessage(err, '项目保存失败'))
      }
    }, 700)
    return () => window.clearTimeout(timer)
  }, [project])

  useEffect(() => {
    if (!render || render.status !== 'processing') return
    const timer = window.setInterval(async () => {
      try {
        const current = await fetchDigitalHumanRender(render.id)
        setRender(current)
        if (current.status === 'succeeded') setNotice('成片已生成并保存到素材管理')
      } catch (err) {
        setError(getErrorMessage(err, '生成进度更新失败'))
      }
    }, 5000)
    return () => window.clearInterval(timer)
  }, [render])

  const assetById = useMemo(() => new Map(assets.map((item) => [item.id, item])), [assets])
  const selectedProfile = profiles.find((item) => item.id === project?.profile_id)
  const totalDuration = project?.scenes.reduce((sum, scene) => sum + Number(scene.duration || 0), 0) || 0
  const canGenerate = Boolean(project && selectedProfile?.profile_type === 'virtual' && selectedProfile.voice_asset_id && totalDuration >= 4 && totalDuration <= 60)

  function patchProject(next: Partial<DigitalHumanProject>) {
    setProject((current) => current ? { ...current, ...next } : current)
  }

  function patchScene(sceneId: string, next: Partial<DigitalHumanScene>) {
    if (!project) return
    patchProject({ scenes: project.scenes.map((scene) => scene.id === sceneId ? { ...scene, ...next } : scene) })
  }

  function reorderScene(index: number, direction: -1 | 1) {
    if (!project) return
    const target = index + direction
    if (target < 0 || target >= project.scenes.length) return
    const scenes = [...project.scenes]
    ;[scenes[index], scenes[target]] = [scenes[target], scenes[index]]
    patchProject({ scenes: scenes.map((scene, order) => ({ ...scene, order: order + 1 })) })
  }

  async function uploadInspiration(files: FileList | null) {
    const file = files?.[0]
    if (!file) return
    setBusy('inspiration-upload')
    try {
      const asset = await uploadDigitalHumanAsset(file, 'inspiration_reference')
      const item = await importDigitalHumanInspiration({ name: file.name, asset_id: asset.id })
      setAssets((current) => [asset, ...current])
      setInspirations((current) => [item, ...current])
      patchProject({ inspiration_ids: [...new Set([...(project?.inspiration_ids || []), item.id])] })
      setNotice('灵感素材已添加，可以开始分析')
    } catch (err) { setError(getErrorMessage(err, '灵感素材上传失败')) } finally { setBusy('') }
  }

  async function addSourceUrl() {
    if (!sourceUrl.trim()) return
    setBusy('source-url')
    try {
      const item = await importDigitalHumanInspiration({ name: '链接灵感素材', source_url: sourceUrl.trim() })
      setInspirations((current) => [item, ...current])
      patchProject({ inspiration_ids: [...new Set([...(project?.inspiration_ids || []), item.id])] })
      setSourceUrl('')
    } catch (err) { setError(getErrorMessage(err, '链接导入失败')) } finally { setBusy('') }
  }

  async function pasteSourceUrl() {
    setSourceUrlMenu(null)
    try {
      const text = await navigator.clipboard.readText()
      if (!text.trim()) {
        setNotice('剪贴板中没有可粘贴的内容')
        return
      }
      setSourceUrl(text.trim())
      window.requestAnimationFrame(() => sourceUrlInput.current?.focus())
    } catch {
      sourceUrlInput.current?.focus()
      setError('未能读取剪贴板，请使用 Ctrl+V 粘贴')
    }
  }

  async function analyzeInspiration(item: DigitalHumanInspiration) {
    setBusy(`analyze:${item.id}`)
    try {
      const next = await analyzeDigitalHumanInspiration(item.id)
      setInspirations((current) => current.map((row) => row.id === next.id ? next : row))
      setNotice('视频洞察已完成')
    } catch (err) { setError(getErrorMessage(err, '素材分析失败')) } finally { setBusy('') }
  }

  function applyAnalysis(item: DigitalHumanInspiration) {
    const segments = item.analysis?.segments || []
    const scenes = segments.map((segment, index) => freshScene(index + 1)).map((scene, index) => {
      const raw = segments[index]
      return {
        ...scene,
        spoken_text: String(raw.spoken_text || ''),
        visual_prompt: String(raw.visual_prompt || ''),
        duration: Math.max(1, Math.min(30, Number(raw.duration || 5))),
        visual_mode: (String(raw.visual_mode || 'presenter') as DigitalHumanScene['visual_mode']),
      }
    })
    if (!scenes.length && item.analysis?.transcript) {
      scenes.push({ ...freshScene(1), spoken_text: item.analysis.transcript, visual_prompt: item.analysis.visual_structure || '' })
    }
    if (scenes.length) {
      patchProject({ scenes })
      setStep(3)
      setNotice('洞察结果已应用，所有内容仍可自由修改')
    }
  }

  async function removeInspiration(item: DigitalHumanInspiration) {
    await deleteDigitalHumanInspiration(item.id)
    setInspirations((current) => current.filter((row) => row.id !== item.id))
    patchProject({ inspiration_ids: (project?.inspiration_ids || []).filter((id) => id !== item.id) })
  }

  async function uploadProfileAsset(kind: 'avatar' | 'voice', files: FileList | null) {
    const file = files?.[0]
    if (!file) return
    setBusy(`profile-${kind}`)
    try {
      const asset = await uploadDigitalHumanAsset(file, kind === 'avatar' ? 'avatar_reference' : 'voice_reference')
      setAssets((current) => [asset, ...current])
      if (kind === 'avatar') setProfileAvatarIds((current) => [...current, asset.id])
      else setProfileVoiceId(asset.id)
    } catch (err) { setError(getErrorMessage(err, '形象素材上传失败')) } finally { setBusy('') }
  }

  async function saveProfile() {
    setBusy('profile-save')
    try {
      const item = await createDigitalHumanProfile({
        name: profileName || '我的数字人', profile_type: profileType,
        avatar_asset_ids: profileAvatarIds, voice_asset_id: profileVoiceId,
        cover_asset_id: profileAvatarIds[0] || '', default_style: '自然、可信的商业口播', outfit: '', notes: '',
      })
      setProfiles((current) => [item, ...current])
      patchProject({ profile_id: item.id })
      setShowProfileForm(false)
      setProfileName(''); setProfileAvatarIds([]); setProfileVoiceId(''); setProfileType('virtual')
      setNotice(item.profile_type === 'virtual' ? '数字人形象已保存并选中' : '真人形象已保存，暂不可用于生成')
    } catch (err) { setError(getErrorMessage(err, '数字人形象保存失败')) } finally { setBusy('') }
  }

  async function removeProfile(item: DigitalHumanProfile) {
    await deleteDigitalHumanProfile(item.id)
    setProfiles((current) => current.filter((row) => row.id !== item.id))
    if (project?.profile_id === item.id) patchProject({ profile_id: '' })
  }

  async function askAiToPlan() {
    if (!project) return
    setBusy('plan')
    try {
      const result = await planDigitalHumanProject(project.id, planInstruction)
      patchProject({ scenes: result.scenes })
      setPlanInstruction('')
      setNotice('新编排已生成，请确认后继续')
    } catch (err) { setError(getErrorMessage(err, '编排生成失败')) } finally { setBusy('') }
  }

  async function uploadSceneAsset(files: FileList | null) {
    const file = files?.[0]
    if (!file || !project || !sceneUploadTarget) return
    setBusy(`scene-upload:${sceneUploadTarget}`)
    try {
      const role = file.type.startsWith('audio/') ? 'voice_reference' : file.type.startsWith('video/') ? 'motion_reference' : 'scene_reference'
      const asset = await uploadDigitalHumanAsset(file, role, { projectId: project.id })
      setAssets((current) => [asset, ...current])
      const scene = project.scenes.find((item) => item.id === sceneUploadTarget)
      if (scene) patchScene(scene.id, { reference_asset_ids: [...scene.reference_asset_ids, asset.id] })
    } catch (err) { setError(getErrorMessage(err, '场景素材上传失败')) } finally { setBusy('') }
  }

  async function generateSceneImage(scene: DigitalHumanScene) {
    if (!project || !scene.visual_prompt.trim()) return
    setBusy(`scene-image:${scene.id}`)
    try {
      const asset = await generateDigitalHumanSceneImage(project.id, scene.id, scene.visual_prompt)
      setAssets((current) => [asset, ...current])
      patchScene(scene.id, { reference_asset_ids: [...scene.reference_asset_ids, asset.id] })
      setNotice('画面已生成并加入当前场景')
    } catch (err) { setError(getErrorMessage(err, '画面生成失败')) } finally { setBusy('') }
  }

  async function startRender() {
    if (!project) return
    setBusy('render')
    try {
      const saved = await updateDigitalHumanProject(project.id, project)
      setProject(saved)
      const job = await createDigitalHumanRender(saved.id)
      setRender(job)
      setNotice('生成任务已开始，可在本页查看每个片段进度')
    } catch (err) { setError(getErrorMessage(err, '生成任务创建失败')) } finally { setBusy('') }
  }

  async function retrySegment(segmentId: string) {
    if (!render) return
    setBusy(`retry:${segmentId}`)
    try { setRender(await retryDigitalHumanRenderSegment(render.id, segmentId)) }
    catch (err) { setError(getErrorMessage(err, '片段重试失败')) }
    finally { setBusy('') }
  }

  function openPublish() {
    if (!render?.material) return
    setPublishAsset({
      id: render.material.id, name: render.material.name, type: 'video', url: render.material.url,
      path: render.material.path, size: render.material.size, created_at: render.material.created_at,
      source: 'digital_human',
    })
  }

  if (loading) return <div className="flex min-h-[520px] items-center justify-center text-[#93A3BB]"><Loader2 className="mr-2 h-5 w-5 animate-spin" />正在打开创作区</div>

  return (
    <div className="min-h-full bg-[#080C14] text-[#F5F7FB]">
      <div className="border-b border-[#1D2636] px-5 py-5 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">数字人创作</h1>
            <p className="mt-1 text-sm text-[#8492A8]">从灵感到成片，在每一步保留你的创作自由。</p>
          </div>
          <div className="flex items-center gap-2">
            <select value={project?.id || ''} onChange={(event) => setProject(projects.find((item) => item.id === event.target.value) || null)} className="h-9 border border-[#2A3548] bg-[#101624] px-3 text-sm outline-none">
              {projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
            <button onClick={async () => { const item = await createDigitalHumanProject({ name: `数字人口播 ${projects.length + 1}`, scenes: [freshScene(1)] }); setProjects((current) => [item, ...current]); setProject(item) }} className="inline-flex h-9 items-center gap-1.5 bg-[#5965E8] px-3 text-sm hover:bg-[#6873EE]"><Plus className="h-4 w-4" />新作品</button>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto border-b border-[#1D2636] px-5 lg:px-8">
        <div className="flex min-w-[720px] items-center">
          {STEPS.map((item, index) => (
            <button key={item.id} onClick={() => setStep(item.id)} className={`group flex h-16 flex-1 items-center justify-center gap-3 border-b-2 text-sm transition ${step === item.id ? 'border-[#7C86FF] text-white' : 'border-transparent text-[#77869D] hover:text-[#C9D1DE]'}`}>
              <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${step === item.id ? 'bg-[#6671F0] text-white' : step > item.id ? 'bg-[#244A43] text-[#5CE0BE]' : 'bg-[#182131] text-[#8492A8]'}`}>{step > item.id ? <Check className="h-3.5 w-3.5" /> : item.id}</span>
              {item.label}
              {index < STEPS.length - 1 && <ChevronRight className="ml-auto h-4 w-4 text-[#344158]" />}
            </button>
          ))}
        </div>
      </div>

      {(error || notice) && (
        <div className={`mx-5 mt-4 flex items-center justify-between border px-4 py-3 text-sm lg:mx-8 ${error ? 'border-[#703748] bg-[#2B131C] text-[#FFB4C1]' : 'border-[#28534B] bg-[#10241F] text-[#82E7CC]'}`}>
          <span className="flex items-center gap-2">{error ? <CircleAlert className="h-4 w-4" /> : <Check className="h-4 w-4" />}{error || notice}</span>
          <button onClick={() => { setError(''); setNotice('') }} aria-label="关闭提示"><X className="h-4 w-4" /></button>
        </div>
      )}

      <main className="px-5 py-6 lg:px-8">
        {step === 1 && (
          <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
            <section>
              <h2 className="text-base font-semibold">添加灵感</h2>
              <p className="mt-1 text-xs leading-5 text-[#7F8DA5]">用于理解表达方式与画面结构，不会复制素材中的人物或声音。</p>
              <input ref={inspirationInput} type="file" accept="image/*,video/mp4,video/quicktime" className="hidden" onChange={(event) => void uploadInspiration(event.target.files)} />
              <button onClick={() => inspirationInput.current?.click()} className="mt-4 flex h-32 w-full flex-col items-center justify-center border border-dashed border-[#33425A] bg-[#0D1320] text-sm text-[#B9C4D5] hover:border-[#6671F0]">
                {busy === 'inspiration-upload' ? <Loader2 className="mb-2 h-6 w-6 animate-spin" /> : <Upload className="mb-2 h-6 w-6" />}
                上传视频或图片
              </button>
              <div className="mt-4 flex gap-2">
                <div className="relative min-w-0 flex-1"><Link2 className="absolute left-3 top-2.5 h-4 w-4 text-[#65738A]" /><input ref={sourceUrlInput} value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} onContextMenu={(event) => { event.preventDefault(); setSourceUrlMenu({ x: Math.min(event.clientX, window.innerWidth - 132), y: Math.min(event.clientY, window.innerHeight - 48) }) }} placeholder="粘贴公开素材链接" className="h-9 w-full border border-[#2A3548] bg-[#0D1320] pl-9 pr-3 text-sm outline-none focus:border-[#6571EE]" /></div>
                <button onClick={() => void addSourceUrl()} disabled={!sourceUrl.trim() || busy === 'source-url'} className="h-9 border border-[#34425A] px-3 text-sm text-[#CED6E3] disabled:opacity-40">导入</button>
              </div>
            </section>
            <section>
              <div className="mb-4 flex items-center justify-between"><div><h2 className="text-base font-semibold">视频洞察</h2><p className="mt-1 text-xs text-[#7F8DA5]">提取文案、卖点、镜头节奏与可复用场景。</p></div><span className="text-xs text-[#687790]">{inspirations.length} 项</span></div>
              {inspirations.length === 0 ? <EmptyState icon={FileVideo} title="还没有灵感素材" text="添加一段你欣赏的内容，系统会把可复用的表达结构整理出来。" /> : (
                <div className="space-y-3">
                  {inspirations.map((item) => {
                    const asset = assetById.get(item.asset_id)
                    return <article key={item.id} className="border border-[#222D40] bg-[#0C111D] p-4">
                      <div className="flex items-start gap-3">{asset ? <AssetThumb asset={asset} /> : <div className="flex h-14 w-14 items-center justify-center bg-[#151D2B]"><Link2 className="h-5 w-5 text-[#8090A8]" /></div>}<div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{item.name}</p><p className="mt-1 truncate text-xs text-[#718098]">{item.source_url || asset?.name}</p></div><button onClick={() => void removeInspiration(item)} aria-label="移除灵感"><Trash2 className="h-4 w-4 text-[#6F7E94] hover:text-[#F48A9B]" /></button></div>
                      {item.analysis && <div className="mt-4 grid gap-3 border-t border-[#1E2939] pt-4 md:grid-cols-2"><div><span className="text-[11px] text-[#718098]">开场钩子</span><p className="mt-1 text-sm leading-6 text-[#D7DDE8]">{item.analysis.hook || '已完成内容理解'}</p></div><div><span className="text-[11px] text-[#718098]">核心卖点</span><p className="mt-1 text-sm leading-6 text-[#D7DDE8]">{item.analysis.selling_points?.join(' · ') || '等待整理'}</p></div><div className="md:col-span-2"><span className="text-[11px] text-[#718098]">文案</span><p className="mt-1 line-clamp-3 text-sm leading-6 text-[#AEB9CA]">{item.analysis.transcript || '未识别到明确口播'}</p></div></div>}
                      <div className="mt-4 flex justify-end gap-2"><button onClick={() => void analyzeInspiration(item)} className="inline-flex h-8 items-center gap-1.5 border border-[#34425A] px-3 text-xs">{busy === `analyze:${item.id}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}{item.analysis ? '重新分析' : '开始分析'}</button>{item.analysis && <button onClick={() => applyAnalysis(item)} className="inline-flex h-8 items-center gap-1.5 bg-[#5965E8] px-3 text-xs"><ArrowRight className="h-3.5 w-3.5" />应用到创作</button>}</div>
                    </article>
                  })}
                </div>
              )}
            </section>
          </div>
        )}

        {step === 2 && (
          <div>
            <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-base font-semibold">数字人形象库</h2><p className="mt-1 text-xs text-[#7F8DA5]">人物和声音绑定保存，后续作品可以直接复用。</p></div><button onClick={() => setShowProfileForm((value) => !value)} className="inline-flex h-9 items-center gap-1.5 bg-[#5965E8] px-3 text-sm"><Plus className="h-4 w-4" />新建形象</button></div>
            {showProfileForm && <div className="mb-6 grid gap-5 border-y border-[#283448] bg-[#0D1320] px-4 py-5 lg:grid-cols-[240px_1fr_1fr_auto]">
              <div><label className="text-xs text-[#8795AA]">形象名称</label><input value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder="例如：品牌讲解员" className="mt-2 h-10 w-full border border-[#2B374B] bg-[#080D16] px-3 text-sm outline-none" /><div className="mt-3 flex gap-2"><button onClick={() => setProfileType('virtual')} className={`h-8 flex-1 border text-xs ${profileType === 'virtual' ? 'border-[#6974F1] bg-[#252B63]' : 'border-[#2B374B]'}`}>虚拟人物</button><button onClick={() => setProfileType('real')} className={`h-8 flex-1 border text-xs ${profileType === 'real' ? 'border-[#6974F1] bg-[#252B63]' : 'border-[#2B374B]'}`}>真人形象</button></div></div>
              <div><label className="text-xs text-[#8795AA]">人物参考</label><input ref={avatarInput} type="file" accept="image/*,video/mp4,video/quicktime" className="hidden" onChange={(event) => void uploadProfileAsset('avatar', event.target.files)} /><button onClick={() => avatarInput.current?.click()} className="mt-2 flex h-24 w-full items-center justify-center border border-dashed border-[#34425A] text-sm text-[#B8C2D2]"><UserRound className="mr-2 h-5 w-5" />上传图片或视频</button><div className="mt-2 flex gap-2">{profileAvatarIds.map((id) => assetById.get(id)).filter(Boolean).map((asset) => <AssetThumb key={asset!.id} asset={asset!} compact />)}</div></div>
              <div><label className="text-xs text-[#8795AA]">绑定声音</label><input ref={voiceInput} type="file" accept="audio/*,video/mp4,video/quicktime" className="hidden" onChange={(event) => void uploadProfileAsset('voice', event.target.files)} /><button onClick={() => voiceInput.current?.click()} className="mt-2 flex h-24 w-full items-center justify-center border border-dashed border-[#34425A] text-sm text-[#B8C2D2]"><Mic2 className="mr-2 h-5 w-5" />上传音频或有声视频</button>{profileVoiceId && <p className="mt-2 truncate text-xs text-[#83D9C2]">已绑定：{assetById.get(profileVoiceId)?.name}</p>}</div>
              <div className="flex items-end"><button onClick={() => void saveProfile()} disabled={!profileAvatarIds.length || !profileVoiceId || busy === 'profile-save'} className="inline-flex h-10 items-center gap-2 bg-[#5965E8] px-4 text-sm disabled:opacity-40">{busy === 'profile-save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}保存</button></div>
            </div>}
            {profiles.length === 0 ? <EmptyState icon={UserRound} title="建立第一个数字人形象" text="上传虚拟人物参考和声音，保存后可以在所有数字人口播作品中复用。" /> : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{profiles.map((item) => { const cover = assetById.get(item.cover_asset_id || item.avatar_asset_ids[0]); const selected = project?.profile_id === item.id; return <article key={item.id} onClick={() => patchProject({ profile_id: item.id })} className={`cursor-pointer border p-4 transition ${selected ? 'border-[#6974F1] bg-[#171D3B]' : 'border-[#242F42] bg-[#0D121D] hover:border-[#3B4860]'}`}><div className="flex items-start gap-3">{cover ? <AssetThumb asset={cover} /> : <div className="flex h-14 w-14 items-center justify-center bg-[#151D2B]"><UserRound className="h-6 w-6" /></div>}<div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate text-sm font-medium">{item.name}</p>{selected && <Check className="h-4 w-4 text-[#7D87FF]" />}</div><p className="mt-1 text-xs text-[#7F8DA5]">{item.profile_type === 'virtual' ? '虚拟人物 · 可生成' : '真人形象 · 暂不可生成'}</p><p className="mt-2 truncate text-xs text-[#A7B2C3]">{item.voice_asset_id ? `声音：${assetById.get(item.voice_asset_id)?.name || '已绑定'}` : '未绑定声音'}</p></div><button onClick={(event) => { event.stopPropagation(); void removeProfile(item) }} aria-label="删除形象"><Trash2 className="h-4 w-4 text-[#6E7D93] hover:text-[#F48A9B]" /></button></div></article>})}</div>}
          </div>
        )}

        {step === 3 && project && (
          <div>
            <div className="mb-5 flex flex-wrap items-end justify-between gap-4"><div><h2 className="text-base font-semibold">文案与画面</h2><p className="mt-1 text-xs text-[#7F8DA5]">每张卡片代表一段可独立调整的画面，插图和素材会在指定场景中出现。</p></div><div className="flex gap-2"><input value={planInstruction} onChange={(event) => setPlanInstruction(event.target.value)} placeholder="告诉 AI 你想怎样调整" className="h-9 w-64 border border-[#2B374B] bg-[#0D1320] px-3 text-sm outline-none" /><button onClick={() => void askAiToPlan()} disabled={busy === 'plan'} className="inline-flex h-9 items-center gap-1.5 border border-[#535FCB] bg-[#202653] px-3 text-sm">{busy === 'plan' ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}AI 编排</button></div></div>
            <input ref={sceneUploadInput} type="file" accept="image/*,video/*,audio/*" className="hidden" onChange={(event) => void uploadSceneAsset(event.target.files)} />
            <div className="space-y-4">{project.scenes.map((scene, index) => <article key={scene.id} className="border border-[#242F42] bg-[#0C111C]"><header className="flex items-center justify-between border-b border-[#1F2939] px-4 py-3"><div className="flex items-center gap-3"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#252D5D] text-xs text-[#D6DAFF]">{index + 1}</span><span className="text-sm font-medium">场景 {index + 1}</span><span className="text-xs text-[#74839A]">{scene.duration} 秒</span></div><div className="flex items-center gap-1"><button onClick={() => reorderScene(index, -1)} disabled={index === 0} aria-label="上移"><ArrowUp className="h-4 w-4 text-[#7E8CA2] disabled:opacity-30" /></button><button onClick={() => reorderScene(index, 1)} disabled={index === project.scenes.length - 1} aria-label="下移"><ArrowDown className="h-4 w-4 text-[#7E8CA2]" /></button><button onClick={() => patchProject({ scenes: project.scenes.filter((item) => item.id !== scene.id).map((item, order) => ({ ...item, order: order + 1 })) })} aria-label="删除场景"><Trash2 className="ml-2 h-4 w-4 text-[#7E8CA2] hover:text-[#F48A9B]" /></button></div></header><div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]"><div><label className="text-xs text-[#7F8DA5]">口播文案</label><textarea value={scene.spoken_text} onChange={(event) => patchScene(scene.id, { spoken_text: event.target.value })} rows={5} placeholder="输入这一段数字人要说的话" className="mt-2 w-full resize-y border border-[#2A3548] bg-[#080D16] p-3 text-sm leading-7 outline-none focus:border-[#606BE5]" /><div className="mt-3 grid grid-cols-3 gap-2"><label><span className="text-[11px] text-[#718098]">时长</span><div className="mt-1 flex h-9 border border-[#2A3548] bg-[#080D16]"><input type="number" min={1} max={30} value={scene.duration} onChange={(event) => patchScene(scene.id, { duration: Math.max(1, Math.min(30, Number(event.target.value || 1))) })} className="min-w-0 flex-1 bg-transparent px-2 text-sm outline-none" /><span className="px-2 py-2 text-xs text-[#718098]">秒</span></div></label><label><span className="text-[11px] text-[#718098]">数字人</span><select value={scene.presenter_mode} onChange={(event) => patchScene(scene.id, { presenter_mode: event.target.value as DigitalHumanScene['presenter_mode'] })} className="mt-1 h-9 w-full border border-[#2A3548] bg-[#080D16] px-2 text-xs">{presenterModes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label><span className="text-[11px] text-[#718098]">画面方式</span><select value={scene.visual_mode} onChange={(event) => patchScene(scene.id, { visual_mode: event.target.value as DigitalHumanScene['visual_mode'] })} className="mt-1 h-9 w-full border border-[#2A3548] bg-[#080D16] px-2 text-xs">{visualModes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div></div><div><label className="text-xs text-[#7F8DA5]">画面提示</label><textarea value={scene.visual_prompt} onChange={(event) => patchScene(scene.id, { visual_prompt: event.target.value })} rows={3} placeholder="描述人物动作、插图内容、产品展示与镜头运动" className="mt-2 w-full resize-y border border-[#2A3548] bg-[#080D16] p-3 text-sm leading-6 outline-none focus:border-[#606BE5]" /><div className="mt-3 flex flex-wrap gap-2">{scene.reference_asset_ids.map((id) => assetById.get(id)).filter(Boolean).map((asset) => <button key={asset!.id} onClick={() => patchScene(scene.id, { reference_asset_ids: scene.reference_asset_ids.filter((id) => id !== asset!.id) })} className="group flex items-center gap-2 border border-[#34425A] bg-[#111827] p-1 pr-2"><AssetThumb asset={asset!} compact /><span className="max-w-28 truncate text-xs">@{ROLE_LABELS[asset!.role] || '素材'} · {asset!.name}</span><X className="h-3 w-3 text-[#6F7E94] group-hover:text-white" /></button>)}</div><div className="mt-3 flex flex-wrap gap-2"><button onClick={() => { setSceneUploadTarget(scene.id); sceneUploadInput.current?.click() }} className="inline-flex h-8 items-center gap-1.5 border border-[#34425A] px-2.5 text-xs"><ImagePlus className="h-3.5 w-3.5" />上传画面</button><button onClick={() => void generateSceneImage(scene)} disabled={!scene.visual_prompt.trim() || busy === `scene-image:${scene.id}`} className="inline-flex h-8 items-center gap-1.5 border border-[#4E59B9] bg-[#1B2148] px-2.5 text-xs disabled:opacity-40">{busy === `scene-image:${scene.id}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}生成画面</button><label className="flex h-8 items-center gap-2 border border-[#34425A] px-2.5 text-xs"><input type="checkbox" checked={scene.subtitle} onChange={(event) => patchScene(scene.id, { subtitle: event.target.checked })} />显示字幕</label></div></div></div></article>)}</div>
            <button onClick={() => patchProject({ scenes: [...project.scenes, freshScene(project.scenes.length + 1)] })} className="mt-4 flex h-12 w-full items-center justify-center gap-2 border border-dashed border-[#34425A] text-sm text-[#AEB9CA] hover:border-[#6571EE]"><Plus className="h-4 w-4" />添加场景</button>
          </div>
        )}

        {step === 4 && project && (
          <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]"><section><h2 className="text-base font-semibold">成片设置</h2><div className="mt-4 space-y-4"><label className="block"><span className="text-xs text-[#7F8DA5]">作品名称</span><input value={project.name} onChange={(event) => patchProject({ name: event.target.value })} className="mt-1 h-10 w-full border border-[#2A3548] bg-[#0D1320] px-3 text-sm outline-none" /></label><label className="block"><span className="text-xs text-[#7F8DA5]">视觉风格</span><textarea value={project.visual_style} onChange={(event) => patchProject({ visual_style: event.target.value })} rows={3} className="mt-1 w-full border border-[#2A3548] bg-[#0D1320] p-3 text-sm leading-6 outline-none" /></label><div className="grid grid-cols-2 gap-3"><label><span className="text-xs text-[#7F8DA5]">视频比例</span><select value={project.ratio} onChange={(event) => patchProject({ ratio: event.target.value as DigitalHumanProject['ratio'] })} className="mt-1 h-10 w-full border border-[#2A3548] bg-[#0D1320] px-2 text-sm">{config?.ratios.map((value) => <option key={value}>{value}</option>)}</select></label><label><span className="text-xs text-[#7F8DA5]">清晰度</span><select value={project.size} onChange={(event) => patchProject({ size: event.target.value as DigitalHumanProject['size'] })} className="mt-1 h-10 w-full border border-[#2A3548] bg-[#0D1320] px-2 text-sm"><option value="480p">流畅</option><option value="720p">高清</option></select></label></div><div className="border-y border-[#223047] py-4"><div className="flex justify-between text-sm"><span className="text-[#8D9AAF]">总时长</span><strong className={totalDuration > 60 ? 'text-[#FF8FA3]' : 'text-white'}>{totalDuration} 秒</strong></div><div className="mt-2 h-1.5 overflow-hidden bg-[#1B2535]"><div className={`h-full ${totalDuration > 60 ? 'bg-[#EF6078]' : 'bg-[#6671F0]'}`} style={{ width: `${Math.min(100, totalDuration / 60 * 100)}%` }} /></div><p className="mt-2 text-xs text-[#718098]">系统会自动分段生成并在本机合成为一个视频。</p></div>{selectedProfile?.profile_type === 'real' && <p className="flex gap-2 border border-[#65404A] bg-[#27151B] p-3 text-xs leading-5 text-[#F5AAB7]"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />当前版本暂不能使用真人形象生成，请选择虚拟人物。</p>}{selectedProfile && !selectedProfile.voice_asset_id && <p className="flex gap-2 border border-[#65543A] bg-[#251E12] p-3 text-xs text-[#EDC67D]"><CircleAlert className="h-4 w-4" />该形象尚未绑定声音。</p>}<button onClick={() => void startRender()} disabled={!canGenerate || busy === 'render' || !config?.configured} className="flex h-11 w-full items-center justify-center gap-2 bg-[#5965E8] text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40">{busy === 'render' ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}生成视频</button></div></section><section><div className="mb-4 flex items-center justify-between"><div><h2 className="text-base font-semibold">生成进度</h2><p className="mt-1 text-xs text-[#7F8DA5]">每个片段独立生成，失败时只需重试对应片段。</p></div>{render?.status === 'succeeded' && <button onClick={openPublish} className="inline-flex h-9 items-center gap-2 bg-[#20A887] px-4 text-sm"><Send className="h-4 w-4" />发布成片</button>}</div>{!render ? <EmptyState icon={WandSparkles} title="准备生成你的数字人口播" text="确认形象、声音、场景和总时长后开始生成。" /> : <div><div className="border border-[#263247] bg-[#0C111D] p-4"><div className="flex items-center justify-between"><span className="text-sm font-medium">{render.status === 'succeeded' ? '成片已完成' : render.status === 'failed' ? '部分片段需要处理' : '正在生成'}</span><span className="text-sm text-[#AAB5C6]">{render.progress}%</span></div><div className="mt-3 h-2 overflow-hidden bg-[#1A2332]"><div className={`h-full transition-all ${render.status === 'failed' ? 'bg-[#ED667D]' : render.status === 'succeeded' ? 'bg-[#2BC6A2]' : 'bg-[#6873EE]'}`} style={{ width: `${render.progress}%` }} /></div></div><div className="mt-3 space-y-2">{render.segments.map((segment) => <div key={segment.id} className="flex items-center gap-3 border border-[#222D40] bg-[#0B101A] px-4 py-3"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#1C2638] text-xs">{segment.index}</span><div className="min-w-0 flex-1"><p className="text-sm">片段 {segment.index} · {segment.duration} 秒</p><p className={`mt-0.5 text-xs ${segment.status === 'failed' ? 'text-[#F28A9C]' : 'text-[#78879E]'}`}>{segment.status === 'succeeded' ? '已完成' : segment.status === 'failed' ? (segment.error || '生成失败') : '生成中'}</p></div>{segment.status === 'processing' || segment.status === 'queued' ? <Loader2 className="h-4 w-4 animate-spin text-[#7B85FF]" /> : segment.status === 'succeeded' ? <Check className="h-4 w-4 text-[#4DD7B5]" /> : <button onClick={() => void retrySegment(segment.id)} className="inline-flex h-8 items-center gap-1 border border-[#704052] px-2 text-xs text-[#F0A0AD]"><RefreshCw className="h-3.5 w-3.5" />重试</button>}</div>)}</div>{render.status === 'succeeded' && render.output_url && <video src={render.output_url} controls className="mt-4 max-h-[560px] w-full bg-black" />}</div>}</section></div>
        )}

        <div className="mt-8 flex items-center justify-between border-t border-[#1D2636] pt-5"><button onClick={() => setStep((value) => Math.max(1, value - 1))} disabled={step === 1} className="inline-flex h-9 items-center gap-2 border border-[#2F3A4E] px-3 text-sm disabled:opacity-30"><ArrowLeft className="h-4 w-4" />上一步</button><div className="text-xs text-[#687790]">项目自动保存</div><button onClick={() => setStep((value) => Math.min(4, value + 1))} disabled={step === 4} className="inline-flex h-9 items-center gap-2 bg-[#202842] px-3 text-sm disabled:opacity-30">下一步<ArrowRight className="h-4 w-4" /></button></div>
      </main>

      {sourceUrlMenu && (
        <div className="fixed inset-0 z-[120]" onPointerDown={() => setSourceUrlMenu(null)} onContextMenu={(event) => { event.preventDefault(); setSourceUrlMenu(null) }}>
          <div className="fixed w-32 overflow-hidden rounded-md border border-[#344158] bg-[#111827] p-1 shadow-[0_14px_36px_rgba(0,0,0,0.45)]" style={{ left: sourceUrlMenu.x, top: sourceUrlMenu.y }} onPointerDown={(event) => event.stopPropagation()}>
            <button type="button" onClick={() => void pasteSourceUrl()} className="flex h-8 w-full items-center gap-2 rounded px-2.5 text-left text-sm text-[#E2E8F0] transition hover:bg-[#202B3D]">
              <ClipboardPaste className="h-4 w-4 text-[#8F9BFF]" />粘贴
            </button>
          </div>
        </div>
      )}

      {publishAsset && <PublishSelectedDrawer assets={[publishAsset]} onClose={() => setPublishAsset(null)} onSubmitted={() => setPublishAsset(null)} />}
    </div>
  )
}
