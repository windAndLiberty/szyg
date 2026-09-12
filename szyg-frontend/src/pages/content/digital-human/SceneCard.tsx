import { useCallback, useState, type ChangeEvent, type DragEvent, type ReactNode } from 'react'
import { ArrowDown, ArrowUp, GripVertical, ImagePlus, Loader2, Sparkles, Trash2, X } from 'lucide-react'
import type { DigitalHumanAsset, DigitalHumanScene } from '@/lib/api'
import { inferMediaKind, ROLE_LABELS } from './studioUtils'

const visualModes = [
  ['presenter', '数字人口播'], ['full_image', '全屏插图'], ['product_closeup', '产品特写'],
  ['integrated', '场景融合'], ['creative_cutaway', '创意转场'],
] as const

const presenterModes = [['full', '全屏口播'], ['pip', '画中画'], ['hidden', '隐藏数字人']] as const

export const SCENE_DRAG_MIME = 'application/x-szyg-scene-id'

interface SceneCardProps {
  scene: DigitalHumanScene
  index: number
  total: number
  assets: Map<string, DigitalHumanAsset>
  busyKey?: string
  onPatch: (patch: Partial<DigitalHumanScene>) => void
  onMove: (direction: -1 | 1) => void
  onRemove: () => void
  onPickFiles: (files: File[]) => void
  onRequestGenerate: () => void
  onRemoveReference: (assetId: string) => void
  draggable?: boolean
  onDragStart?: (event: DragEvent<HTMLElement>) => void
  onDragEnd?: (event: DragEvent<HTMLElement>) => void
  draggingOver?: 'before' | 'after' | null
  onDragOverReorder?: (event: DragEvent<HTMLElement>, position: 'before' | 'after') => void
  onDragLeaveReorder?: () => void
  onDropReorder?: (event: DragEvent<HTMLElement>) => void
}

function AssetThumbCompact({ asset }: { asset: DigitalHumanAsset }) {
  const kind = asset.kind
  if (kind === 'image') {
    return <img src={asset.url} alt={asset.name} className="h-8 w-8 shrink-0 rounded border border-[#2A3448] object-cover" />
  }
  if (kind === 'video') {
    return <video src={asset.url} muted preload="metadata" className="h-8 w-8 shrink-0 rounded border border-[#2A3448] object-cover" />
  }
  return <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-[#2A3448] bg-[#111827] text-[#65738A] text-[10px]">AUDIO</div>
}

export default function SceneCard({
  scene,
  index,
  total,
  assets,
  busyKey,
  onPatch,
  onMove,
  onRemove,
  onPickFiles,
  onRequestGenerate,
  onRemoveReference,
  draggable = false,
  onDragStart,
  onDragEnd,
  draggingOver = null,
  onDragOverReorder,
  onDragLeaveReorder,
  onDropReorder,
}: SceneCardProps) {
  const [dropping, setDropping] = useState(false)

  const handleFileDrop = useCallback(
    (event: DragEvent<HTMLElement>) => {
      event.preventDefault()
      setDropping(false)
      if (!event.dataTransfer.types.includes('Files')) return
      const files = Array.from(event.dataTransfer.files).filter((file) => inferMediaKind(file))
      if (!files.length) return
      onPickFiles(files)
    },
    [onPickFiles],
  )

  const handleDragEnter = useCallback((event: DragEvent<HTMLElement>) => {
    if (event.dataTransfer.types.includes('Files')) {
      event.preventDefault()
      setDropping(true)
    }
  }, [])

  const handleDragOver = useCallback((event: DragEvent<HTMLElement>) => {
    if (event.dataTransfer.types.includes('Files')) {
      event.preventDefault()
      event.dataTransfer.dropEffect = 'copy'
    }
  }, [])

  const handleDragLeave = useCallback((event: DragEvent<HTMLElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setDropping(false)
    }
  }, [])

  const canMoveUp = index > 0
  const canMoveDown = index < total - 1
  const isImageBusy = busyKey === `scene-image:${scene.id}`

  return (
    <article
      className={`relative border bg-[#0C111C] transition ${dropping ? 'border-[#818CF8] ring-2 ring-[#6366F1]/30' : 'border-[#242F42]'}`}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleFileDrop}
    >
      {draggingOver === 'before' && (
        <div className="pointer-events-none absolute -top-1 left-0 right-0 h-0.5 bg-[#818CF8]" />
      )}
      {draggingOver === 'after' && (
        <div className="pointer-events-none absolute -bottom-1 left-0 right-0 h-0.5 bg-[#818CF8]" />
      )}
      {dropping && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded bg-[#0B0F1A]/85 text-sm font-medium text-[#C4B5FD]">
          松开即可加入场景素材
        </div>
      )}
      <header
        className="flex items-center justify-between border-b border-[#1F2939] px-4 py-3"
        draggable={draggable}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragOver={onDragOverReorder ? (event) => onDragOverReorder(event, 'before') : undefined}
        onDragLeave={onDragLeaveReorder}
        onDrop={onDropReorder}
      >
        <div className="flex items-center gap-3">
          {draggable ? (
            <span className="cursor-grab text-[#5B6A85] active:cursor-grabbing" aria-label="拖动以重排">
              <GripVertical className="h-4 w-4" />
            </span>
          ) : null}
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#252D5D] text-xs text-[#D6DAFF]">
            {index + 1}
          </span>
          <span className="text-sm font-medium">场景 {index + 1}</span>
          <span className="text-xs text-[#74839A]">{scene.duration} 秒</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onMove(-1)}
            disabled={!canMoveUp}
            aria-label="上移"
            className="p-1 text-[#7E8CA2] disabled:opacity-30"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => onMove(1)}
            disabled={!canMoveDown}
            aria-label="下移"
            className="p-1 text-[#7E8CA2] disabled:opacity-30"
          >
            <ArrowDown className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onRemove}
            aria-label="删除场景"
            className="ml-2 p-1 text-[#7E8CA2] hover:text-[#F48A9B]"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </header>
      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div>
          <label className="text-xs text-[#7F8DA5]">口播文案</label>
          <textarea
            value={scene.spoken_text}
            onChange={(event) => onPatch({ spoken_text: event.target.value })}
            rows={5}
            placeholder="输入这一段数字人要说的话"
            className="mt-2 w-full resize-y border border-[#2A3548] bg-[#080D16] p-3 text-sm leading-7 outline-none focus:border-[#606BE5]"
          />
          <div className="mt-3 grid grid-cols-3 gap-2">
            <label>
              <span className="text-[11px] text-[#718098]">时长</span>
              <div className="mt-1 flex h-9 border border-[#2A3548] bg-[#080D16]">
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={scene.duration}
                  onChange={(event) => onPatch({ duration: Math.max(1, Math.min(30, Number(event.target.value || 1))) })}
                  className="min-w-0 flex-1 bg-transparent px-2 text-sm outline-none"
                />
                <span className="px-2 py-2 text-xs text-[#718098]">秒</span>
              </div>
            </label>
            <label>
              <span className="text-[11px] text-[#718098]">数字人</span>
              <select
                value={scene.presenter_mode}
                onChange={(event) => onPatch({ presenter_mode: event.target.value as DigitalHumanScene['presenter_mode'] })}
                className="mt-1 h-9 w-full border border-[#2A3548] bg-[#080D16] px-2 text-xs"
              >
                {presenterModes.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="text-[11px] text-[#718098]">画面方式</span>
              <select
                value={scene.visual_mode}
                onChange={(event) => onPatch({ visual_mode: event.target.value as DigitalHumanScene['visual_mode'] })}
                className="mt-1 h-9 w-full border border-[#2A3548] bg-[#080D16] px-2 text-xs"
              >
                {visualModes.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <div>
          <label className="text-xs text-[#7F8DA5]">画面提示</label>
          <textarea
            value={scene.visual_prompt}
            onChange={(event) => onPatch({ visual_prompt: event.target.value })}
            rows={3}
            placeholder="描述人物动作、插图内容、产品展示与镜头运动"
            className="mt-2 w-full resize-y border border-[#2A3548] bg-[#080D16] p-3 text-sm leading-6 outline-none focus:border-[#606BE5]"
          />
          <SceneReferences
            scene={scene}
            assets={assets}
            onRemove={onRemoveReference}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 border border-[#34425A] px-2.5 text-xs hover:border-[#6571EE]">
              <ImagePlus className="h-3.5 w-3.5" />
              上传画面
              <input
                type="file"
                multiple
                accept="image/*,video/mp4,video/quicktime,audio/*"
                className="hidden"
                onChange={(event: ChangeEvent<HTMLInputElement>) => onPickFiles(Array.from(event.target.files || []))}
              />
            </label>
            <button
              type="button"
              onClick={onRequestGenerate}
              disabled={!scene.visual_prompt.trim() || isImageBusy}
              className="inline-flex h-8 items-center gap-1.5 border border-[#4E59B9] bg-[#1B2148] px-2.5 text-xs disabled:opacity-40"
            >
              {isImageBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              生成画面
            </button>
            <label className="flex h-8 items-center gap-2 border border-[#34425A] px-2.5 text-xs">
              <input
                type="checkbox"
                checked={scene.subtitle}
                onChange={(event) => onPatch({ subtitle: event.target.checked })}
              />
              显示字幕
            </label>
          </div>
        </div>
      </div>
    </article>
  )
}

function SceneReferences({
  scene,
  assets,
  onRemove,
}: {
  scene: DigitalHumanScene
  assets: Map<string, DigitalHumanAsset>
  onRemove: (assetId: string) => void
}) {
  const items = scene.reference_asset_ids
    .map((id) => assets.get(id))
    .filter((asset): asset is DigitalHumanAsset => Boolean(asset))
  if (!items.length) return <p className="mt-3 text-[11px] text-[#5E6B82]">拖拽文件到当前场景即可加入</p>
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {items.map((asset) => (
        <button
          key={asset.id}
          type="button"
          onClick={() => onRemove(asset.id)}
          className="group flex items-center gap-2 border border-[#34425A] bg-[#111827] p-1 pr-2"
          title="点击移除此素材"
        >
          <AssetThumbCompact asset={asset} />
          <span className="max-w-28 truncate text-xs">@{ROLE_LABELS[asset.role] || '素材'} · {asset.name}</span>
          <X className="h-3 w-3 text-[#6F7E94] group-hover:text-white" />
        </button>
      ))}
    </div>
  )
}

export type SceneCardChildren = (props: { children: ReactNode }) => ReactNode
