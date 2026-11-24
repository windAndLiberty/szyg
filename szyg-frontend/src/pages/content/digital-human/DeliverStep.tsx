import { Check, CircleAlert, Loader2, RefreshCw, Send, WandSparkles } from 'lucide-react'
import type { DigitalHumanConfig, DigitalHumanProject, DigitalHumanRender, DigitalHumanProfile } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

interface DeliverStepProps {
  project: DigitalHumanProject
  config: DigitalHumanConfig | null
  render: DigitalHumanRender | null
  selectedProfile: DigitalHumanProfile | null | undefined
  totalDuration: number
  canGenerate: boolean
  busyKey: string
  onPatch: (patch: Partial<DigitalHumanProject>) => void
  onStartRender: () => void
  onRetrySegment: (segmentId: string) => void
  onOpenPublish: () => void
}

export default function DeliverStep({
  project,
  config,
  render,
  selectedProfile,
  totalDuration,
  canGenerate,
  busyKey,
  onPatch,
  onStartRender,
  onRetrySegment,
  onOpenPublish,
}: DeliverStepProps) {
  const { t } = useI18n()
  const durationOver = totalDuration > 60
  return (
    <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
      <section>
        <h2 className="text-base font-semibold">{t('digitalHuman.delivery.settings')}</h2>
        <div className="mt-4 space-y-4">
          <label className="block">
            <span className="text-xs text-muted-foreground">{t('digitalHuman.delivery.name')}</span>
            <input
              value={project.name}
              onChange={(event) => onPatch({ name: event.target.value })}
              className="mt-1 h-10 w-full border border-border bg-card px-3 text-sm outline-none"
            />
          </label>
          <label className="block">
            <span className="text-xs text-muted-foreground">{t('digitalHuman.delivery.style')}</span>
            <textarea
              value={project.visual_style}
              onChange={(event) => onPatch({ visual_style: event.target.value })}
              rows={3}
              className="mt-1 w-full border border-border bg-card p-3 text-sm leading-6 outline-none"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label>
              <span className="text-xs text-muted-foreground">{t('digitalHuman.delivery.ratio')}</span>
              <select
                value={project.ratio}
                onChange={(event) => onPatch({ ratio: event.target.value as DigitalHumanProject['ratio'] })}
                className="mt-1 h-10 w-full border border-border bg-card px-2 text-sm"
              >
                {config?.ratios.map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="text-xs text-muted-foreground">{t('digitalHuman.delivery.quality')}</span>
              <select
                value={project.size}
                onChange={(event) => onPatch({ size: event.target.value as DigitalHumanProject['size'] })}
                className="mt-1 h-10 w-full border border-border bg-card px-2 text-sm"
              >
                <option value="480p">{t('digitalHuman.delivery.smooth')}</option>
                <option value="720p">{t('digitalHuman.delivery.hd')}</option>
              </select>
            </label>
          </div>
          <div className="border-y border-border py-4">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">{t('digitalHuman.delivery.totalDuration')}</span>
              <strong className={durationOver ? 'text-danger-ink' : 'text-foreground'}>{t('digitalHuman.scene.seconds', { seconds: totalDuration })}</strong>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden bg-muted">
              <div
                className={`h-full ${durationOver ? 'bg-[#EF6078]' : 'bg-[#6671F0]'}`}
                style={{ width: `${Math.min(100, (totalDuration / 60) * 100)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{t('digitalHuman.delivery.localMerge')}</p>
          </div>
          {selectedProfile?.profile_type === 'real' && (
            <p className="flex gap-2 border border-danger-ink/35 bg-danger-soft p-3 text-xs leading-5 text-danger-ink">
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              {t('digitalHuman.delivery.realUnavailable')}
            </p>
          )}
          {selectedProfile && !selectedProfile.voice_asset_id && (
            <p className="flex gap-2 border border-warning-ink/35 bg-warning-soft p-3 text-xs text-warning-ink">
              <CircleAlert className="h-4 w-4" />
              {t('digitalHuman.delivery.voiceMissing')}
            </p>
          )}
          <button
            type="button"
            onClick={onStartRender}
            disabled={!canGenerate || busyKey === 'render' || !config?.configured}
            className="flex h-11 w-full items-center justify-center gap-2 bg-primary text-primary-foreground text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busyKey === 'render' ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
            {t('digitalHuman.delivery.generate')}
          </button>
        </div>
      </section>
      <section>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">{t('digitalHuman.delivery.progress')}</h2>
            <p className="mt-1 text-xs text-muted-foreground">{t('digitalHuman.delivery.progressDescription')}</p>
          </div>
          {render?.status === 'succeeded' && (
            <button
              type="button"
              onClick={onOpenPublish}
              className="inline-flex h-9 items-center gap-2 bg-[#20A887] px-4 text-sm"
            >
              <Send className="h-4 w-4" />
              {t('digitalHuman.delivery.publish')}
            </button>
          )}
        </div>
        {!render ? (
          <div className="flex min-h-[200px] flex-col items-center justify-center border border-dashed border-border bg-background/40 px-6 text-center">
            <WandSparkles className="mb-3 h-7 w-7 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">{t('digitalHuman.delivery.ready')}</p>
            <p className="mt-1 max-w-sm text-xs leading-5 text-muted-foreground">{t('digitalHuman.delivery.readyDescription')}</p>
          </div>
        ) : (
          <RenderProgress render={render} onRetrySegment={onRetrySegment} />
        )}
      </section>
    </div>
  )
}

function RenderProgress({
  render,
  onRetrySegment,
}: {
  render: DigitalHumanRender
  onRetrySegment: (segmentId: string) => void
}) {
  const { t } = useI18n();

  return (
    <div>
      <div className="border border-border bg-background p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">
            {render.status === 'succeeded'
              ? t('digitalHuman.delivery.completed')
              : render.status === 'failed'
                ? t('digitalHuman.delivery.needsAttention')
                : t('digitalHuman.delivery.generating')}
          </span>
          <span className="text-sm text-muted-foreground">{render.progress}%</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden bg-muted">
          <div
            className={`h-full transition-all ${
              render.status === 'failed'
                ? 'bg-[#ED667D]'
                : render.status === 'succeeded'
                ? 'bg-[#2BC6A2]'
                : 'bg-[#6873EE]'
            }`}
            style={{ width: `${render.progress}%` }}
          />
        </div>
      </div>
      <div className="mt-3 space-y-2">
        {render.segments.map((segment) => {
          const isDone = segment.status === 'succeeded'
          const isFailed = segment.status === 'failed'
          const isWorking = segment.status === 'processing' || segment.status === 'queued'
          return (
            <div key={segment.id} className="flex items-center gap-3 border border-border bg-background px-4 py-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-xs">
                {segment.index}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm">{t('digitalHuman.delivery.segment', { index: segment.index, seconds: segment.duration })}</p>
                <p className={`mt-0.5 text-xs ${isFailed ? 'text-danger-ink' : 'text-muted-foreground'}`}>
                  {isDone ? t('digitalHuman.delivery.done') : isFailed ? (segment.error || t('digitalHuman.delivery.failed')) : t('digitalHuman.delivery.generating')}
                </p>
              </div>
              {isWorking ? (
                <Loader2 className="h-4 w-4 animate-spin text-accent-ink" />
              ) : isDone ? (
                <Check className="h-4 w-4 text-success-ink" />
              ) : (
                <button
                  type="button"
                  onClick={() => onRetrySegment(segment.id)}
                  className="inline-flex h-8 items-center gap-1 border border-danger-ink/35 px-2 text-xs text-danger-ink"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  {t('digitalHuman.delivery.retry')}
                </button>
              )}
            </div>
          )
        })}
      </div>
      {render.status === 'succeeded' && render.output_url && (
        <video src={render.output_url} controls className="mt-4 max-h-[560px] w-full bg-black" />
      )}
    </div>
  )
}
