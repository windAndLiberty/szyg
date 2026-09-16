import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, CircleAlert, Loader2, Plus, X } from 'lucide-react'
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
  fetchDigitalHumanRemixes,
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
  type DigitalHumanRemixJob,
  type DigitalHumanScene,
} from '@/lib/api'
import { PublishSelectedDrawer, type Asset as PublishAsset } from './AssetManagement'
import RemixDialog from './RemixDialog'
import StepsBar, { type StepDescriptor } from './digital-human/StepsBar'
import InspirationsPanel from './digital-human/InspirationsPanel'
import ProfileLibrary, { type ProfileDraft, EMPTY_DRAFT } from './digital-human/ProfileLibrary'
import ScriptBoard from './digital-human/ScriptBoard'
import DeliverStep from './digital-human/DeliverStep'
import { freshScene, inferSceneReferenceRole, normalizeSceneOrder, reOrder } from './digital-human/studioUtils'
import { useI18n } from '@/lib/i18n'

const STEPS: StepDescriptor[] = [
  { id: 1, label: 'digitalHuman.step.inspiration' },
  { id: 2, label: 'digitalHuman.step.profile' },
  { id: 3, label: 'digitalHuman.step.script' },
  { id: 4, label: 'digitalHuman.step.publish' },
]

export default function DigitalHumanStudio() {
  const { t } = useI18n()
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
  const [planInstruction, setPlanInstruction] = useState('')
  const [profileDraft, setProfileDraft] = useState<ProfileDraft>(EMPTY_DRAFT)
  const [publishAsset, setPublishAsset] = useState<PublishAsset | null>(null)
  const [remixProfile, setRemixProfile] = useState<DigitalHumanProfile | null>(null)
  const [remixJobs, setRemixJobs] = useState<DigitalHumanRemixJob[]>([])
  const hydrated = useRef(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [cfg, assetData, profileData, inspirationData, projectData, remixData] = await Promise.all([
        fetchDigitalHumanConfig(),
        fetchDigitalHumanAssets(),
        fetchDigitalHumanProfiles(),
        fetchDigitalHumanInspirations(),
        fetchDigitalHumanProjects(),
        fetchDigitalHumanRemixes(),
      ])
      setConfig(cfg)
      setAssets(assetData.items)
      setProfiles(profileData.items)
      setInspirations(inspirationData.items)
      setProjects(projectData.items)
      setRemixJobs(remixData.items)
      let selected = projectData.items[0]
      if (!selected) {
        selected = await createDigitalHumanProject({ name: '我的数字人口播', scenes: [freshScene(1)] })
        setProjects([selected])
      }
      setProject(selected)
      // Show any interrupted high-imitation job again when its profile is opened.
      const resumable = remixData.items.find((item) => !['succeeded', 'failed'].includes(item.status))
      if (resumable) setRemixProfile(profileData.items.find((item) => item.id === resumable.profile_id) || null)
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
  const localizedSteps = useMemo(() => STEPS.map((item) => ({ ...item, label: t(item.label) })), [t])
  const selectedProfile = profiles.find((item) => item.id === project?.profile_id)
  const totalDuration = project?.scenes.reduce((sum, scene) => sum + Number(scene.duration || 0), 0) || 0
  const canGenerate = Boolean(
    project &&
    selectedProfile?.profile_type === 'virtual' &&
    selectedProfile.voice_asset_id &&
    totalDuration >= 4 &&
    totalDuration <= 60,
  )

  const patchProject = useCallback((next: Partial<DigitalHumanProject>) => {
    setProject((current) => (current ? { ...current, ...next } : current))
  }, [])

  const patchScene = useCallback((sceneId: string, patch: Partial<DigitalHumanScene>) => {
    setProject((current) => {
      if (!current) return current
      return { ...current, scenes: current.scenes.map((scene) => scene.id === sceneId ? { ...scene, ...patch } : scene) }
    })
  }, [])

  // Step 1 — inspirations
  const uploadInspiration = useCallback(async (files: File[]) => {
    if (!files.length) return
    setBusy('inspiration-upload')
    try {
      let lastImported: DigitalHumanInspiration | null = null
      for (const file of files) {
        const asset = await uploadDigitalHumanAsset(file, 'inspiration_reference')
        setAssets((current) => [asset, ...current])
        const item = await importDigitalHumanInspiration({ name: file.name, asset_id: asset.id })
        setInspirations((current) => [item, ...current])
        lastImported = item
      }
      if (lastImported) {
        patchProject({ inspiration_ids: [...new Set([...(project?.inspiration_ids || []), lastImported.id])] })
        setNotice('灵感素材已添加，可以开始分析')
      }
    } catch (err) {
      setError(getErrorMessage(err, '灵感素材上传失败'))
    } finally {
      setBusy('')
    }
  }, [patchProject, project?.inspiration_ids])

  const importSourceUrl = useCallback(async (url: string) => {
    const item = await importDigitalHumanInspiration({ name: '链接灵感素材', source_url: url })
    setInspirations((current) => [item, ...current])
    patchProject({ inspiration_ids: [...new Set([...(project?.inspiration_ids || []), item.id])] })
  }, [patchProject, project?.inspiration_ids])

  const analyzeInspiration = useCallback(async (item: DigitalHumanInspiration) => {
    setBusy(`analyze:${item.id}`)
    try {
      const next = await analyzeDigitalHumanInspiration(item.id)
      setInspirations((current) => current.map((row) => row.id === next.id ? next : row))
      setNotice('视频洞察已完成')
    } catch (err) {
      setError(getErrorMessage(err, '素材分析失败'))
    } finally {
      setBusy('')
    }
  }, [])

  const applyAnalysis = useCallback((item: DigitalHumanInspiration) => {
    if (!project) return
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
  }, [patchProject, project])

  const removeInspiration = useCallback(async (item: DigitalHumanInspiration) => {
    await deleteDigitalHumanInspiration(item.id)
    setInspirations((current) => current.filter((row) => row.id !== item.id))
    patchProject({ inspiration_ids: (project?.inspiration_ids || []).filter((id) => id !== item.id) })
  }, [patchProject, project?.inspiration_ids])

  // Step 2 — profiles
  const uploadProfileAvatar = useCallback(async (file: File) => {
    setBusy('profile-avatar')
    try {
      const asset = await uploadDigitalHumanAsset(file, 'avatar_reference')
      setAssets((current) => [asset, ...current])
      setProfileDraft((current) => ({ ...current, avatarIds: [...current.avatarIds, asset.id] }))
    } catch (err) {
      setError(getErrorMessage(err, '形象素材上传失败'))
    } finally {
      setBusy('')
    }
  }, [])

  const uploadProfileVoice = useCallback(async (file: File) => {
    setBusy('profile-voice')
    try {
      const asset = await uploadDigitalHumanAsset(file, 'voice_reference')
      setAssets((current) => [asset, ...current])
      setProfileDraft((current) => ({ ...current, voiceId: asset.id }))
    } catch (err) {
      setError(getErrorMessage(err, '声音素材上传失败'))
    } finally {
      setBusy('')
    }
  }, [])

  const saveProfileDraft = useCallback(async () => {
    if (!profileDraft.avatarIds.length || !profileDraft.voiceId) return
    setBusy('profile-save')
    try {
      const item = await createDigitalHumanProfile({
        name: profileDraft.name || '我的数字人',
        profile_type: profileDraft.profileType,
        avatar_asset_ids: profileDraft.avatarIds,
        voice_asset_id: profileDraft.voiceId,
        cover_asset_id: profileDraft.avatarIds[0] || '',
        default_style: '自然、可信的商业口播',
        outfit: '',
        notes: '',
      })
      setProfiles((current) => [item, ...current])
      patchProject({ profile_id: item.id })
      setProfileDraft(EMPTY_DRAFT)
      setNotice(item.profile_type === 'virtual' ? '数字人形象已保存并选中' : '真人形象已保存，暂不可用于生成')
    } catch (err) {
      setError(getErrorMessage(err, '数字人形象保存失败'))
    } finally {
      setBusy('')
    }
  }, [patchProject, profileDraft])

  const removeProfile = useCallback(async (item: DigitalHumanProfile) => {
    await deleteDigitalHumanProfile(item.id)
    setProfiles((current) => current.filter((row) => row.id !== item.id))
    if (project?.profile_id === item.id) patchProject({ profile_id: '' })
  }, [patchProject, project?.profile_id])

  // Step 3 — scenes
  const requestPlan = useCallback(async () => {
    if (!project) return
    setBusy('plan')
    try {
      const result = await planDigitalHumanProject(project.id, planInstruction)
      patchProject({ scenes: result.scenes })
      setPlanInstruction('')
      setNotice('新编排已生成，请确认后继续')
    } catch (err) {
      setError(getErrorMessage(err, '编排生成失败'))
    } finally {
      setBusy('')
    }
  }, [patchProject, planInstruction, project])

  const reorderScenes = useCallback((fromIndex: number, toIndex: number) => {
    setProject((current) => {
      if (!current) return current
      const next = reOrder(current.scenes, fromIndex, toIndex)
      return { ...current, scenes: normalizeSceneOrder(next) }
    })
  }, [])

  const removeScene = useCallback((sceneId: string) => {
    setProject((current) => {
      if (!current) return current
      return { ...current, scenes: normalizeSceneOrder(current.scenes.filter((scene) => scene.id !== sceneId)) }
    })
  }, [])

  const addScene = useCallback(() => {
    setProject((current) => {
      if (!current) return current
      return { ...current, scenes: [...current.scenes, freshScene(current.scenes.length + 1)] }
    })
  }, [])

  const uploadSceneFiles = useCallback(async (sceneId: string, files: File[]) => {
    if (!project || !files.length) return
    setBusy(`scene-upload:${sceneId}`)
    try {
      const accepted = files.filter((file) => Boolean(inferSceneReferenceRole(file)))
      if (!accepted.length) {
        setError('场景仅支持图片、音频或视频素材')
        return
      }
      const uploaded: string[] = []
      for (const file of accepted) {
        const role = inferSceneReferenceRole(file)
        const asset = await uploadDigitalHumanAsset(file, role, { projectId: project.id })
        setAssets((current) => [asset, ...current])
        uploaded.push(asset.id)
      }
      if (uploaded.length) {
        const scene = project.scenes.find((item) => item.id === sceneId)
        if (scene) {
          const next = [...scene.reference_asset_ids]
          for (const id of uploaded) if (!next.includes(id)) next.push(id)
          patchScene(sceneId, { reference_asset_ids: next })
        }
      }
    } catch (err) {
      setError(getErrorMessage(err, '场景素材上传失败'))
    } finally {
      setBusy('')
    }
  }, [patchScene, project])

  const removeSceneReference = useCallback((sceneId: string, assetId: string) => {
    const scene = project?.scenes.find((item) => item.id === sceneId)
    if (!scene) return
    patchScene(sceneId, { reference_asset_ids: scene.reference_asset_ids.filter((id) => id !== assetId) })
  }, [patchScene, project])

  const requestSceneImage = useCallback(async (scene: DigitalHumanScene) => {
    if (!project || !scene.visual_prompt.trim()) return
    setBusy(`scene-image:${scene.id}`)
    try {
      const asset = await generateDigitalHumanSceneImage(project.id, scene.id, scene.visual_prompt)
      setAssets((current) => [asset, ...current])
      const next = scene.reference_asset_ids.includes(asset.id)
        ? scene.reference_asset_ids
        : [...scene.reference_asset_ids, asset.id]
      patchScene(scene.id, { reference_asset_ids: next })
      setNotice('画面已生成并加入当前场景')
    } catch (err) {
      setError(getErrorMessage(err, '画面生成失败'))
    } finally {
      setBusy('')
    }
  }, [patchScene, project])

  // Step 4 — render
  const startRender = useCallback(async () => {
    if (!project) return
    setBusy('render')
    try {
      const saved = await updateDigitalHumanProject(project.id, project)
      setProject(saved)
      const job = await createDigitalHumanRender(saved.id)
      setRender(job)
      setNotice('生成任务已开始，可在本页查看每个片段进度')
    } catch (err) {
      setError(getErrorMessage(err, '生成任务创建失败'))
    } finally {
      setBusy('')
    }
  }, [project])

  const retryRenderSegment = useCallback(async (segmentId: string) => {
    if (!render) return
    setBusy(`retry:${segmentId}`)
    try {
      setRender(await retryDigitalHumanRenderSegment(render.id, segmentId))
    } catch (err) {
      setError(getErrorMessage(err, '片段重试失败'))
    } finally {
      setBusy('')
    }
  }, [render])

  const openPublish = useCallback(() => {
    if (!render?.material) return
    setPublishAsset({
      id: render.material.id,
      name: render.material.name,
      type: 'video',
      url: render.material.url,
      path: render.material.path,
      size: render.material.size,
      created_at: render.material.created_at,
      source: 'digital_human',
    })
  }, [render])

  const createNewProject = useCallback(async () => {
    const item = await createDigitalHumanProject({ name: `数字人口播 ${projects.length + 1}`, scenes: [freshScene(1)] })
    setProjects((current) => [item, ...current])
    setProject(item)
  }, [projects.length])

  if (loading) {
    return (
      <div className="flex min-h-[520px] items-center justify-center text-[#93A3BB]">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />{t('digitalHuman.loading')}
      </div>
    )
  }

  return (
    <div className="min-h-full bg-[#080C14] text-[#F5F7FB]">
      <div className="border-b border-[#1D2636] px-5 py-5 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">{t('digitalHuman.title')}</h1>
            <p className="mt-1 text-sm text-[#8492A8]">{t('digitalHuman.subtitle')}</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={project?.id || ''}
              onChange={(event) => setProject(projects.find((item) => item.id === event.target.value) || null)}
              className="h-9 border border-[#2A3548] bg-[#101624] px-3 text-sm outline-none"
            >
              {projects.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void createNewProject()}
              className="inline-flex h-9 items-center gap-1.5 bg-[#5965E8] px-3 text-sm hover:bg-[#6873EE]"
            >
              <Plus className="h-4 w-4" />{t('digitalHuman.newProject')}
            </button>
          </div>
        </div>
      </div>

      <StepsBar steps={localizedSteps} current={step} onChange={setStep} />

      {(error || notice) && (
        <div
          className={`mx-5 mt-4 flex items-center justify-between border px-4 py-3 text-sm lg:mx-8 ${
            error ? 'border-[#703748] bg-[#2B131C] text-[#FFB4C1]' : 'border-[#28534B] bg-[#10241F] text-[#82E7CC]'
          }`}
        >
          <span className="flex items-center gap-2">
            {error ? <CircleAlert className="h-4 w-4" /> : <Check className="h-4 w-4" />}
            {error || notice}
          </span>
          <button type="button" onClick={() => { setError(''); setNotice('') }} aria-label={t('digitalHuman.closeNotice')}>
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <main className="px-5 py-6 lg:px-8">
        {step === 1 && (
          <InspirationsPanel
            inspirations={inspirations}
            assetById={assetById}
            busyKey={busy}
            onUpload={(files) => void uploadInspiration(files)}
            onImportUrl={(url) => importSourceUrl(url)}
            onAnalyze={(item) => void analyzeInspiration(item)}
            onRemove={(item) => void removeInspiration(item)}
            onApply={(item) => applyAnalysis(item)}
          />
        )}

        {step === 2 && (
          <>
            <ProfileLibrary
              profiles={profiles}
              assetById={assetById}
              selectedProfileId={project?.profile_id || ''}
              busyKey={busy}
              draft={profileDraft}
              onDraftChange={setProfileDraft}
              onUploadAvatar={(file) => void uploadProfileAvatar(file)}
              onUploadVoice={(file) => void uploadProfileVoice(file)}
              onSaveDraft={() => void saveProfileDraft()}
              onSelectProfile={(profile) => patchProject({ profile_id: profile.id })}
              onRemoveProfile={(profile) => void removeProfile(profile)}
              onRemix={(profile) => setRemixProfile(profile)}
            />
            {remixProfile && (
              <RemixDialog
                profile={remixProfile}
                initialJob={remixJobs.find((item) => item.profile_id === remixProfile.id && !['succeeded', 'failed'].includes(item.status)) || null}
                onClose={() => setRemixProfile(null)}
                onSuccess={(material) => {
                  setPublishAsset(material)
                  setRemixProfile(null)
                }}
              />
            )}
          </>
        )}

        {step === 3 && project && (
          <ScriptBoard
            project={project}
            assetById={assetById}
            busyKey={busy}
            planInstruction={planInstruction}
            onPlanInstructionChange={setPlanInstruction}
            onRequestPlan={() => void requestPlan()}
            onPatchScene={patchScene}
            onReorder={reorderScenes}
            onRemove={removeScene}
            onAddScene={addScene}
            onUploadSceneFiles={(sceneId, files) => void uploadSceneFiles(sceneId, files)}
            onRequestGenerate={(scene) => void requestSceneImage(scene)}
            onRemoveSceneReference={removeSceneReference}
          />
        )}

        {step === 4 && project && (
          <DeliverStep
            project={project}
            config={config}
            render={render}
            selectedProfile={selectedProfile}
            totalDuration={totalDuration}
            canGenerate={canGenerate}
            busyKey={busy}
            onPatch={patchProject}
            onStartRender={() => void startRender()}
            onRetrySegment={(segmentId) => void retryRenderSegment(segmentId)}
            onOpenPublish={openPublish}
          />
        )}

        <div className="mt-8 flex items-center justify-between border-t border-[#1D2636] pt-5">
          <button
            type="button"
            onClick={() => setStep((value) => Math.max(1, value - 1))}
            disabled={step === 1}
            className="inline-flex h-9 items-center gap-2 border border-[#2F3A4E] px-3 text-sm disabled:opacity-30"
          >
            <ArrowLeft className="h-4 w-4" />{t('digitalHuman.previous')}
          </button>
          <div className="text-xs text-[#687790]">{t('digitalHuman.autoSave')}</div>
          <button
            type="button"
            onClick={() => setStep((value) => Math.min(4, value + 1))}
            disabled={step === 4}
            className="inline-flex h-9 items-center gap-2 bg-[#202842] px-3 text-sm disabled:opacity-30"
          >
            {t('digitalHuman.next')}<ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </main>

      {publishAsset && (
        <PublishSelectedDrawer
          assets={[publishAsset]}
          onClose={() => setPublishAsset(null)}
          onSubmitted={() => setPublishAsset(null)}
        />
      )}
    </div>
  )
}
