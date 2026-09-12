import { useCallback, useState } from 'react'
import { ArrowRight, ClipboardPaste, FileVideo, Link2, Loader2, RefreshCw, Trash2, Upload } from 'lucide-react'
import type { DigitalHumanAsset, DigitalHumanInspiration, InspirationAnalysis } from '@/lib/api'
import DropZone from './DropZone'
import { acceptForInspiration } from './studioUtils'

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
      setError(err instanceof Error ? err.message : '链接导入失败')
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
        <h2 className="text-base font-semibold">添加灵感</h2>
        <p className="mt-1 text-xs leading-5 text-[#7F8DA5]">
          用于理解表达方式与画面结构，不会复制素材中的人物或声音。
        </p>
        <div className="mt-4">
          <DropZone
            accept={acceptForInspiration()}
            onFiles={onUpload}
            busy={busyKey === 'inspiration-upload'}
            size="lg"
            icon={<Upload className="mb-2 h-6 w-6" />}
            title={busyKey === 'inspiration-upload' ? '正在上传' : '拖入或点击上传'}
            hint="支持图片、mp4、mov，可一次添加多个"
            overlayLabel="松开即可加入灵感"
          />
        </div>
        <div className="mt-4 flex gap-2">
          <div className="relative min-w-0 flex-1">
            <Link2 className="absolute left-3 top-2.5 h-4 w-4 text-[#65738A]" />
            <input
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              onContextMenu={onContextMenu}
              placeholder="粘贴公开素材链接"
              className="h-9 w-full border border-[#2A3548] bg-[#0D1320] pl-9 pr-3 text-sm outline-none focus:border-[#6571EE]"
            />
          </div>
          <button
            type="button"
            onClick={() => void submitUrl()}
            disabled={!sourceUrl.trim() || importing}
            className="h-9 border border-[#34425A] px-3 text-sm text-[#CED6E3] disabled:opacity-40"
          >
            {importing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : '导入'}
          </button>
        </div>
        {error && (
          <p className="mt-2 text-xs text-[#F48A9B]">{error}</p>
        )}
      </section>
      <section>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">视频洞察</h2>
            <p className="mt-1 text-xs text-[#7F8DA5]">
              提取文案、卖点、镜头节奏与可复用场景。
            </p>
          </div>
          <span className="text-xs text-[#687790]">{inspirations.length} 项</span>
        </div>
        {inspirations.length === 0 ? (
          <div className="flex min-h-[200px] flex-col items-center justify-center border border-dashed border-[#2B3850] bg-[#0B101B]/40 px-6 text-center">
            <FileVideo className="mb-3 h-7 w-7 text-[#7184A3]" />
            <p className="text-sm font-medium text-[#E7ECF5]">还没有灵感素材</p>
            <p className="mt-1 max-w-sm text-xs leading-5 text-[#7F8DA5]">
              添加一段你欣赏的内容，系统会把可复用的表达结构整理出来。
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
            setError('剪贴板中没有可粘贴的内容')
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
  const analysis = item.analysis
  return (
    <article className="border border-[#222D40] bg-[#0C111D] p-4">
      <div className="flex items-start gap-3">
        {asset ? (
          asset.kind === 'image' ? (
            <img src={asset.url} alt={asset.name} className="h-14 w-14 shrink-0 rounded-md border border-[#2A3448] object-cover" />
          ) : asset.kind === 'video' ? (
            <video src={asset.url} muted preload="metadata" className="h-14 w-14 shrink-0 rounded-md border border-[#2A3448] object-cover" />
          ) : (
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-md border border-[#2A3448] bg-[#111827] text-[#65738A]">AUDIO</div>
          )
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-md border border-[#2A3448] bg-[#151D2B]">
            <Link2 className="h-5 w-5 text-[#8090A8]" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{item.name}</p>
          <p className="mt-1 truncate text-xs text-[#718098]">{item.source_url || asset?.name}</p>
        </div>
        <button type="button" onClick={onRemove} aria-label="移除灵感" className="p-1 text-[#6F7E94] hover:text-[#F48A9B]">
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
      {analysis && <AnalysisPanel analysis={analysis} />}
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onAnalyze}
          className="inline-flex h-8 items-center gap-1.5 border border-[#34425A] px-3 text-xs"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          {analysis ? '重新分析' : '开始分析'}
        </button>
        {analysis && (
          <button type="button" onClick={onApply} className="inline-flex h-8 items-center gap-1.5 bg-[#5965E8] px-3 text-xs">
            <ArrowRight className="h-3.5 w-3.5" />
            应用到创作
          </button>
        )}
      </div>
    </article>
  )
}

function AnalysisPanel({ analysis }: { analysis: InspirationAnalysis }) {
  return (
    <div className="mt-4 grid gap-3 border-t border-[#1E2939] pt-4 md:grid-cols-2">
      <div>
        <span className="text-[11px] text-[#718098]">开场钩子</span>
        <p className="mt-1 text-sm leading-6 text-[#D7DDE8]">{analysis.hook || '已完成内容理解'}</p>
      </div>
      <div>
        <span className="text-[11px] text-[#718098]">核心卖点</span>
        <p className="mt-1 text-sm leading-6 text-[#D7DDE8]">{analysis.selling_points?.join(' · ') || '等待整理'}</p>
      </div>
      <div className="md:col-span-2">
        <span className="text-[11px] text-[#718098]">文案</span>
        <p className="mt-1 line-clamp-3 text-sm leading-6 text-[#AEB9CA]">{analysis.transcript || '未识别到明确口播'}</p>
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
        className="fixed w-32 overflow-hidden rounded-md border border-[#344158] bg-[#111827] p-1 shadow-[0_14px_36px_rgba(0,0,0,0.45)]"
        style={{ left: position.x, top: position.y }}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          onClick={onPaste}
          className="flex h-8 w-full items-center gap-2 rounded px-2.5 text-left text-sm text-[#E2E8F0] transition hover:bg-[#202B3D]"
        >
          <ClipboardPaste className="h-4 w-4 text-[#8F9BFF]" />粘贴
        </button>
      </div>
    </div>
  )
}
