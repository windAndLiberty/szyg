import { useCallback, useState } from 'react'
import { ArrowRight, ClipboardPaste, FileVideo, Link2, Loader2, RefreshCw, Trash2, Upload } from 'lucide-react'
import type { DigitalHumanAsset, DigitalHumanInspiration, InspirationAnalysis } from '@/lib/api'
import DropZone from './DropZone'
import { acceptForInspiration } from './studioUtils'
import { useI18n } from '@/lib/i18n'

interface InspirationsPanelProps {
  inspirations: DigitalHumanInspiration[]
  assetById: Map<string, DigitalHumanAsset>
  busyKey: string
  onUpload: (files: File[]) => void
  onImportUrl: (url: string) => Promise<void> | void
  onAnalyze: (item: DigitalHumanInspiration) => void
  onRemove: (item: DigitalHumanInspiration) => void
  onApply: (item: DigitalHumanInspiration) => void
}

export default function InspirationsPanel({
  inspirations,
  assetById,
  busyKey,
  onUpload,
  onImportUrl,
  onAnalyze,
  onRemove,
  onApply,
}: InspirationsPanelProps) {
  const { t } = useI18n()
  const [sourceUrl, setSourceUrl] = useState('')
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')

  const submitUrl = useCallback(async () => {
    if (!sourceUrl.trim() || importing) return
    setError('')
    setImporting(true)
    try {
      await onImportUrl(sourceUrl.trim())
      setSourceUrl('')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('digitalHuman.importFailed'))
    } finally {
      setImporting(false)
    }
  }, [sourceUrl, importing, onImportUrl])

  const onContextMenu = useCallback(
    (event: React.MouseEvent<HTMLInputElement>) => {
      event.preventDefault()
      setMenu({
        x: Math.min(event.clientX, window.innerWidth - 132),
        y: Math.min(event.clientY, window.innerHeight - 48),
      })
    },
    [],
  )

  return (
    <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
      <section>
        <h2 className="text-base font-semibold">{t('digitalHuman.inspiration.add')}</h2>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          {t('digitalHuman.inspiration.description')}
        </p>
        <div className="mt-4">
          <DropZone
            accept={acceptForInspiration()}
            onFiles={onUpload}
            busy={busyKey === 'inspiration-upload'}
            size="lg"
            icon={<Upload className="mb-2 h-6 w-6" />}
            title={t(busyKey === 'inspiration-upload' ? 'digitalHuman.inspiration.uploading' : 'digitalHuman.inspiration.upload')}
            hint={t('digitalHuman.inspiration.formats')}
            overlayLabel={t('digitalHuman.inspiration.drop')}
          />
        </div>
        <div className="mt-4 flex gap-2">
          <div className="relative min-w-0 flex-1">
            <Link2 className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              onContextMenu={onContextMenu}
              placeholder={t('digitalHuman.inspiration.url')}
              className="h-9 w-full border border-border bg-card pl-9 pr-3 text-sm outline-none focus:border-[#6571EE]"
            />
          </div>
          <button
            type="button"
            onClick={() => void submitUrl()}
            disabled={!sourceUrl.trim() || importing}
            className="h-9 border border-border px-3 text-sm text-foreground disabled:opacity-40"
          >
            {importing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : t('digitalHuman.inspiration.import')}
          </button>
        </div>
        {error && (
          <p className="mt-2 text-xs text-danger-ink">{error}</p>
        )}
      </section>
      <section>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">{t('digitalHuman.insight.title')}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {t('digitalHuman.insight.description')}
            </p>
          </div>
          <span className="text-xs text-muted-foreground">{t('digitalHuman.insight.count', { count: inspirations.length })}</span>
        </div>
        {inspirations.length === 0 ? (
          <div className="flex min-h-[200px] flex-col items-center justify-center border border-dashed border-border bg-background/40 px-6 text-center">
            <FileVideo className="mb-3 h-7 w-7 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">{t('digitalHuman.insight.empty')}</p>
            <p className="mt-1 max-w-sm text-xs leading-5 text-muted-foreground">
              {t('digitalHuman.insight.emptyDescription')}
            </p>
          </div>
        ) : (
          <ul className="space-y-3">
            {inspirations.map((item) => {
              const asset = assetById.get(item.asset_id)
              return (
                <li key={item.id}>
                  <InspirationItem
                    item={item}
                    asset={asset}
                    busy={busyKey === `analyze:${item.id}`}
                    onAnalyze={() => onAnalyze(item)}
                    onRemove={() => onRemove(item)}
                    onApply={() => onApply(item)}
                  />
                </li>
              )
            })}
          </ul>
        )}
      </section>
      {menu && (
        <ContextMenu
          position={menu}
          onClose={() => setMenu(null)}
          onPaste={async () => {
            setMenu(null)
            try {
              const text = await navigator.clipboard.readText()
              if (text.trim()) {
                setSourceUrl(text.trim())
                return
              }
            } catch {
              /* fall through */
            }
            setError(t('digitalHuman.clipboardEmpty'))
          }}
        />
      )}
    </div>
  )
}

interface InspirationItemProps {
  item: DigitalHumanInspiration
  asset: DigitalHumanAsset | undefined
  busy: boolean
  onAnalyze: () => void
  onRemove: () => void
  onApply: () => void
}

function InspirationItem({ item, asset, busy, onAnalyze, onRemove, onApply }: InspirationItemProps) {
  const { t } = useI18n()
  const analysis = item.analysis
  return (
    <article className="border border-border bg-background p-4">
      <div className="flex items-start gap-3">
        {asset ? (
          asset.kind === 'image' ? (
            <img src={asset.url} alt={asset.name} className="h-14 w-14 shrink-0 rounded-md border border-border object-cover" />
          ) : asset.kind === 'video' ? (
            <video src={asset.url} muted preload="metadata" className="h-14 w-14 shrink-0 rounded-md border border-border object-cover" />
          ) : (
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-md border border-border bg-card text-muted-foreground">AUDIO</div>
          )
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-md border border-border bg-card">
            <Link2 className="h-5 w-5 text-muted-foreground" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{item.name}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">{item.source_url || asset?.name}</p>
        </div>
        <button type="button" onClick={onRemove} aria-label={t('digitalHuman.insight.remove')} className="p-1 text-muted-foreground hover:text-danger-ink">
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
      {analysis && <AnalysisPanel analysis={analysis} />}
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onAnalyze}
          className="inline-flex h-8 items-center gap-1.5 border border-border px-3 text-xs"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          {t(analysis ? 'digitalHuman.insight.reanalyze' : 'digitalHuman.insight.analyze')}
        </button>
        {analysis && (
          <button type="button" onClick={onApply} className="inline-flex h-8 items-center gap-1.5 bg-primary text-primary-foreground px-3 text-xs">
            <ArrowRight className="h-3.5 w-3.5" />
            {t('digitalHuman.insight.apply')}
          </button>
        )}
      </div>
    </article>
  )
}

function AnalysisPanel({ analysis }: { analysis: InspirationAnalysis }) {
  const { t } = useI18n()
  return (
    <div className="mt-4 grid gap-3 border-t border-border pt-4 md:grid-cols-2">
      <div>
        <span className="text-[11px] text-muted-foreground">{t('digitalHuman.insight.hook')}</span>
        <p className="mt-1 text-sm leading-6 text-foreground">{analysis.hook || t('digitalHuman.insight.understood')}</p>
      </div>
      <div>
        <span className="text-[11px] text-muted-foreground">{t('digitalHuman.insight.sellingPoints')}</span>
        <p className="mt-1 text-sm leading-6 text-foreground">{analysis.selling_points?.join(' · ') || t('digitalHuman.insight.pending')}</p>
      </div>
      <div className="md:col-span-2">
        <span className="text-[11px] text-muted-foreground">{t('digitalHuman.insight.script')}</span>
        <p className="mt-1 line-clamp-3 text-sm leading-6 text-muted-foreground">{analysis.transcript || t('digitalHuman.insight.noTranscript')}</p>
      </div>
    </div>
  )
}

function ContextMenu({
  position,
  onClose,
  onPaste,
}: {
  position: { x: number; y: number }
  onClose: () => void
  onPaste: () => void
}) {
  const { t } = useI18n()
  return (
    <div
      className="fixed inset-0 z-[120]"
      onPointerDown={onClose}
      onContextMenu={(event) => {
        event.preventDefault()
        onClose()
      }}
    >
      <div
        className="fixed w-32 overflow-hidden rounded-md border border-border bg-card p-1 shadow-[0_14px_36px_rgba(0,0,0,0.45)]"
        style={{ left: position.x, top: position.y }}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          onClick={onPaste}
          className="flex h-8 w-full items-center gap-2 rounded px-2.5 text-left text-sm text-foreground transition hover:bg-muted"
        >
          <ClipboardPaste className="h-4 w-4 text-accent-ink" />{t('digitalHuman.paste')}
        </button>
      </div>
    </div>
  )
}
