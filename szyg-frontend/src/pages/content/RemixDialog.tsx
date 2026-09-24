import { useCallback, useEffect, useRef, useState } from 'react'
import {
  CheckCircle2,
  CircleAlert,
  FileVideo,
  ImagePlus,
  Loader2,
  RefreshCw,
  Send,
  Sparkles,
  Upload,
  WandSparkles,
  X,
} from 'lucide-react'
import {
  createDigitalHumanRemix,
  fetchDigitalHumanRemix,
  getErrorMessage,
  resumeDigitalHumanRemix,
  type DigitalHumanProfile,
  type DigitalHumanRemixJob,
} from '@/lib/api'
import type { Asset as PublishAsset } from './AssetManagement'
import DropZone from './digital-human/DropZone'
import { useI18n } from '@/lib/i18n'

interface RemixDialogProps {
  profile: DigitalHumanProfile
  initialJob?: DigitalHumanRemixJob | null
  onClose: () => void
  onSuccess: (material: PublishAsset) => void
}

const STATUS_LABELS: Record<string, string> = {
  queued: 'digitalHuman.remix.status.queued',
  analyzing: 'digitalHuman.remix.status.analyzing',
  tts_synthesizing: 'digitalHuman.remix.status.tts',
  rendering: 'digitalHuman.remix.status.rendering',
  post_processing: 'digitalHuman.remix.status.postProcessing',
  succeeded: 'digitalHuman.remix.status.succeeded',
  failed: 'digitalHuman.remix.status.failed',
  waiting_credits: 'digitalHuman.remix.status.waitingCredits',
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

export default function RemixDialog({ profile, initialJob = null, onClose, onSuccess }: RemixDialogProps) {
  const { t } = useI18n()
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [videoPreview, setVideoPreview] = useState<string>('')
  const [backgroundMode, setBackgroundMode] = useState<'auto' | 'uploaded'>('auto')
  const [backgroundFile, setBackgroundFile] = useState<File | null>(null)
  const [backgroundPreview, setBackgroundPreview] = useState<string>('')
  const [job, setJob] = useState<DigitalHumanRemixJob | null>(initialJob)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const backgroundInputRef = useRef<HTMLInputElement>(null)
  const [paused, setPaused] = useState(false)

  // A remix is a server-side durable job.  When the studio is reopened after a
  // browser, network, or desktop interruption, use the restored job rather
  // than asking the user to upload the source video again.
  useEffect(() => { setJob(initialJob) }, [initialJob?.id])

  useEffect(() => {
    if (videoFile) {
      const url = URL.createObjectURL(videoFile)
      setVideoPreview(url)
      return () => URL.revokeObjectURL(url)
    }
    setVideoPreview('')
    return undefined
  }, [videoFile])

  useEffect(() => {
    if (backgroundFile) {
      const url = URL.createObjectURL(backgroundFile)
      setBackgroundPreview(url)
      return () => URL.revokeObjectURL(url)
    }
    setBackgroundPreview('')
    return undefined
  }, [backgroundFile])

  useEffect(() => {
    if (!job) return
    if (job.status === 'succeeded' || job.status === 'failed' || job.status === 'waiting_credits') return
    let cancelled = false
    const onVisibility = () => setPaused(document.visibilityState === 'hidden')
    document.addEventListener('visibilitychange', onVisibility)
    onVisibility()
    const timer = window.setInterval(async () => {
      if (cancelled || paused) return
      try {
        const next = await fetchDigitalHumanRemix(job.id)
        if (cancelled) return
        setJob(next)
        if (next.status === 'succeeded' && next.material) {
          onSuccess(next.material as unknown as PublishAsset)
        }
      } catch (err) {
        if (cancelled) return
        setError(getErrorMessage(err, t('digitalHuman.remix.error.progress')))
      }
    }, 5000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [job?.id, job?.status, paused, onSuccess, t])

  const handleVideoSelect = useCallback((files: File[]) => {
    const file = files?.[0] || null
    if (!file) return
    if (!/mp4|mov|quicktime/i.test(file.type) && !/\.(mp4|mov)$/i.test(file.name)) {
      setError(t('digitalHuman.remix.error.videoFormat'))
      return
    }
    if (file.size > 200 * 1024 * 1024) {
      setError(t('digitalHuman.remix.error.videoSize'))
      return
    }
    setError('')
    setVideoFile(file)
  }, [t])

  const handleBackgroundSelect = useCallback((files: FileList | null) => {
    const file = files?.[0] || null
    if (!file) return
    if (!/image\//.test(file.type) && !/\.(jpe?g|png|webp)$/i.test(file.name)) {
      setError(t('digitalHuman.remix.error.imageFormat'))
      return
    }
    if (file.size > 30 * 1024 * 1024) {
      setError(t('digitalHuman.remix.error.imageSize'))
      return
    }
    setError('')
    setBackgroundFile(file)
  }, [t])

  const handleSubmit = useCallback(async () => {
    if (!videoFile || submitting) return
    setSubmitting(true)
    setError('')
    try {
      const result = await createDigitalHumanRemix(
        profile.id,
        videoFile,
        backgroundMode === 'uploaded' ? backgroundFile || undefined : undefined,
      )
      const next = await fetchDigitalHumanRemix(result.task_id)
      setJob(next)
    } catch (err) {
      setError(getErrorMessage(err, t('digitalHuman.remix.error.submit')))
    } finally {
      setSubmitting(false)
    }
  }, [videoFile, backgroundFile, backgroundMode, profile.id, submitting, t])

  const handleReset = useCallback(() => {
    setJob(null)
    setError('')
  }, [])

  const isProcessing = !!job && !['succeeded', 'failed', 'waiting_credits'].includes(job.status)
  const statusLabel = job ? (STATUS_LABELS[job.status] ? t(STATUS_LABELS[job.status]) : job.status) : ''

  return (
    <section className="relative mt-6 w-full overflow-hidden border border-[#283448] bg-[#0B1019] shadow-[0_12px_32px_rgba(0,0,0,0.28)]">
        <header className="flex items-center justify-between border-b border-[#1E2A3D] px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-white">{t('digitalHuman.remix.title')}</h2>
            <p className="mt-1 text-xs text-[#7E8DA5]">{t('digitalHuman.remix.description', { name: profile.name })}</p>
          </div>
          <button onClick={onClose} className="text-[#8A98B3] hover:text-white" aria-label={t('digitalHuman.remix.collapse')}>
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="space-y-6 px-6 py-5">
          {!job && (
            <>
              <section>
                <label className="text-xs text-[#7E8DA5]">{t('digitalHuman.remix.source')}</label>
                {!videoFile ? (
                  <DropZone
                    accept="video/mp4,video/quicktime,.mp4,.mov"
                    multiple={false}
                    onFiles={handleVideoSelect}
                    icon={<Upload className="mb-2 h-6 w-6 text-[#8EA0BA]" />}
                    title={t('digitalHuman.remix.uploadVideo')}
                    hint={t('digitalHuman.remix.videoFormats')}
                    overlayLabel={t('digitalHuman.remix.dropVideo')}
                    size="lg"
                    className="mt-2"
                  />
                ) : (
                  <div className="mt-2 flex items-start gap-4 border border-[#283448] bg-[#0D1320] p-3">
                    <div className="h-24 w-32 shrink-0 overflow-hidden border border-[#1E2939] bg-black">
                      {videoPreview ? (
                        <video src={videoPreview} muted preload="metadata" className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-[#5E6B82]">
                          <FileVideo className="h-6 w-6" />
                        </div>
                      )}
                    </div>
                    <div className="min-w-0 flex-1 text-sm">
                      <p className="truncate font-medium text-white">{videoFile.name}</p>
                      <p className="mt-1 text-xs text-[#7F8DA5]">{formatBytes(videoFile.size)}</p>
                      <button
                        onClick={() => setVideoFile(null)}
                        className="mt-3 inline-flex h-7 items-center gap-1 border border-[#34425A] px-2 text-xs text-[#B8C2D2] hover:border-[#6571EE]"
                      >
                        {t('digitalHuman.remix.reselect')}
                      </button>
                    </div>
                  </div>
                )}
              </section>

              <section>
                <span className="text-xs text-[#7E8DA5]">{t('digitalHuman.remix.background')}</span>
                <div className="mt-2 grid grid-cols-2 gap-3">
                  {(
                    [
                      { key: 'auto', label: t('digitalHuman.remix.backgroundAuto'), desc: t('digitalHuman.remix.backgroundAutoDescription') },
                      { key: 'uploaded', label: t('digitalHuman.remix.backgroundCustom'), desc: t('digitalHuman.remix.backgroundCustomDescription') },
                    ] as const
                  ).map((option) => {
                    const active = backgroundMode === option.key
                    return (
                      <button
                        key={option.key}
                        onClick={() => setBackgroundMode(option.key)}
                        className={`flex h-full flex-col items-start gap-1 border p-3 text-left transition ${
                          active
                            ? 'border-[#6974F1] bg-[#171D3B]'
                            : 'border-[#283448] bg-[#0D1320] hover:border-[#3B4860]'
                        }`}
                      >
                        <span className="text-sm font-medium text-white">{option.label}</span>
                        <span className="text-[11px] text-[#7E8DA5]">{option.desc}</span>
                      </button>
                    )
                  })}
                </div>

                {backgroundMode === 'uploaded' && (
                  <div className="mt-3">
                    <input
                      ref={backgroundInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="hidden"
                      onChange={(event) => handleBackgroundSelect(event.target.files)}
                    />
                    {!backgroundFile ? (
                      <button
                        onClick={() => backgroundInputRef.current?.click()}
                        className="flex h-28 w-full flex-col items-center justify-center border border-dashed border-[#34425A] text-sm text-[#B8C2D2] hover:border-[#6571EE]"
                      >
                        <ImagePlus className="mb-2 h-5 w-5 text-[#8EA0BA]" />
                        {t('digitalHuman.remix.uploadBackground')}
                      </button>
                    ) : (
                      <div className="flex items-start gap-4 border border-[#283448] bg-[#0D1320] p-3">
                        <div className="h-20 w-28 shrink-0 overflow-hidden border border-[#1E2939] bg-black">
                          {backgroundPreview ? (
                            <img src={backgroundPreview} alt={t('digitalHuman.remix.backgroundPreview')} className="h-full w-full object-cover" />
                          ) : null}
                        </div>
                        <div className="min-w-0 flex-1 text-sm">
                          <p className="truncate font-medium text-white">{backgroundFile.name}</p>
                          <p className="mt-1 text-xs text-[#7F8DA5]">{formatBytes(backgroundFile.size)}</p>
                          <button
                            onClick={() => setBackgroundFile(null)}
                            className="mt-2 inline-flex h-7 items-center gap-1 border border-[#34425A] px-2 text-xs text-[#B8C2D2] hover:border-[#6571EE]"
                          >
                            {t('digitalHuman.remix.reselect')}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </section>

              {error && (
                <div className="flex items-start gap-2 border border-[#7A2A3A] bg-[#1A0E14] px-3 py-2 text-sm text-[#FF9DAD]">
                  <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="flex items-center justify-between border-t border-[#1E2A3D] pt-4">
                  <span className="text-xs text-[#7F8DA5]">{t('digitalHuman.remix.durableHint')}</span>
                <button
                  onClick={handleSubmit}
                  disabled={!videoFile || submitting}
                  className="inline-flex h-10 items-center gap-2 bg-[#5965E8] px-5 text-sm font-medium text-white disabled:opacity-40"
                >
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
                  {t('digitalHuman.remix.generate')}
                </button>
              </div>
            </>
          )}

          {job && (
            <section className="space-y-4">
              <div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[#8D9AAF]">{statusLabel}</span>
                  <span className="text-white">{job.progress}%</span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden bg-[#1B2535]">
                  <div
                    className={`h-full ${job.status === 'failed' ? 'bg-[#EF6078]' : 'bg-[#6671F0]'}`}
                    style={{ width: `${Math.min(100, job.progress)}%` }}
                  />
                </div>
              </div>

              {job.segments.length > 0 && (
                <div className="grid gap-2 sm:grid-cols-3">
                  {job.segments.map((segment) => {
                    const complete = segment.status === 'succeeded'
                    const active = ['queued', 'running', 'processing'].includes(segment.status)
                    return (
                      <div key={segment.index} className="border border-[#283448] bg-[#0D1320] px-3 py-2 text-xs">
                        <div className="flex items-center justify-between text-[#C8D2E2]">
                          <span>{t('digitalHuman.remix.segment', { index: segment.index })}</span>
                          <span className={complete ? 'text-[#7BD3B5]' : active ? 'text-[#8F9AFF]' : 'text-[#9AA8BC]'}>
                            {complete ? t('digitalHuman.remix.segmentDone') : active ? t('digitalHuman.remix.segmentWorking') : t('digitalHuman.remix.segmentPending')}
                          </span>
                        </div>
                        <p className="mt-1 text-[#71809A]">{t('digitalHuman.scene.seconds', { seconds: Number(segment.duration || 0).toFixed(1) })}</p>
                      </div>
                    )
                  })}
                </div>
              )}

              {job.status === 'succeeded' && job.output_url && (
                <div className="space-y-3 border border-[#1F3A4A] bg-[#0D1B25] p-4">
                  <div className="flex items-center gap-2 text-sm text-[#7BD3B5]">
                    <CheckCircle2 className="h-4 w-4" />
                    {t('digitalHuman.remix.completed')}
                  </div>
                  <video
                    src={job.output_url}
                    controls
                    className="aspect-video w-full border border-[#1E2939] bg-black"
                  />
                  <div className="flex flex-wrap justify-end gap-2">
                    <button
                      onClick={handleReset}
                      className="inline-flex h-9 items-center gap-1.5 border border-[#34425A] px-3 text-sm text-[#D7DDE8] hover:border-[#6571EE]"
                    >
                      <RefreshCw className="h-4 w-4" />
                      {t('digitalHuman.remix.regenerate')}
                    </button>
                    {job.material && (
                      <button
                        onClick={() => onSuccess(job.material as unknown as PublishAsset)}
                        className="inline-flex h-9 items-center gap-1.5 bg-[#5965E8] px-4 text-sm font-medium text-white"
                      >
                        <Send className="h-4 w-4" />
                        {t('digitalHuman.remix.publish')}
                      </button>
                    )}
                  </div>
                </div>
              )}

              {job.status === 'failed' && (
                <div className="space-y-3 border border-[#7A2A3A] bg-[#1A0E14] p-4">
                  <div className="flex items-start gap-2 text-sm text-[#FF9DAD]">
                    <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <p className="font-medium">{t('digitalHuman.remix.failed')}</p>
                      <p className="mt-1 text-xs text-[#C18B96]">{job.error || t('digitalHuman.remix.failedDescription')}</p>
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={handleReset}
                      className="inline-flex h-9 items-center gap-1.5 bg-[#5965E8] px-4 text-sm font-medium text-white"
                    >
                      <RefreshCw className="h-4 w-4" />
                      {t('digitalHuman.remix.regenerate')}
                    </button>
                  </div>
                </div>
              )}

              {job.status === 'waiting_credits' && (
                <div className="space-y-3 border border-[#755B25] bg-[#19150C] p-4">
                  <div className="flex items-start gap-2 text-sm text-[#F0C96B]">
                    <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <p className="font-medium">{t('digitalHuman.remix.paused')}</p>
                      <p className="mt-1 text-xs text-[#BDA66D]">{t('digitalHuman.remix.resumeDescription', { message: job.error || t('digitalHuman.remix.addCredits') })}</p>
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <button
                      onClick={async () => {
                        try {
                          setError('')
                          setJob(await resumeDigitalHumanRemix(job.id))
                        } catch (err) {
                          setError(getErrorMessage(err, t('digitalHuman.remix.error.resume')))
                        }
                      }}
                      className="inline-flex h-9 items-center gap-1.5 bg-[#5965E8] px-4 text-sm font-medium text-white"
                    >
                      <RefreshCw className="h-4 w-4" />
                      {t('digitalHuman.remix.resume')}
                    </button>
                  </div>
                </div>
              )}

              {isProcessing && (
                <div className="flex items-center gap-2 text-xs text-[#7E8DA5]">
                  <Sparkles className="h-3.5 w-3.5 animate-pulse text-[#6571EE]" />
                  {t('digitalHuman.remix.processingHint')}
                </div>
              )}

              {error && (
                <div className="flex items-start gap-2 border border-[#7A2A3A] bg-[#1A0E14] px-3 py-2 text-sm text-[#FF9DAD]">
                  <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
            </section>
          )}
        </div>
    </section>
  )
}
