import { useCallback, useState, type DragEvent } from 'react'
import { Loader2, Plus, WandSparkles } from 'lucide-react'
import type { DigitalHumanAsset, DigitalHumanProject, DigitalHumanScene } from '@/lib/api'
import SceneCard, { SCENE_DRAG_MIME } from './SceneCard'
import { freshScene, normalizeSceneOrder, reOrder } from './studioUtils'

interface ScriptBoardProps {
  project: DigitalHumanProject
  assetById: Map<string, DigitalHumanAsset>
  busyKey: string
  planInstruction: string
  onPlanInstructionChange: (value: string) => void
  onRequestPlan: () => void
  onPatchScene: (sceneId: string, patch: Partial<DigitalHumanScene>) => void
  onReorder: (fromIndex: number, toIndex: number) => void
  onRemove: (sceneId: string) => void
  onAddScene: () => void
  onUploadSceneFiles: (sceneId: string, files: File[]) => void
  onRequestGenerate: (scene: DigitalHumanScene) => void
  onRemoveSceneReference: (sceneId: string, assetId: string) => void
}

export default function ScriptBoard({
  project,
  assetById,
  busyKey,
  planInstruction,
  onPlanInstructionChange,
  onRequestPlan,
  onPatchScene,
  onReorder,
  onRemove,
  onAddScene,
  onUploadSceneFiles,
  onRequestGenerate,
  onRemoveSceneReference,
}: ScriptBoardProps) {
  const [draggingId, setDraggingId] = useState<string | null>(null)
  const [hoverTarget, setHoverTarget] = useState<{ id: string; position: 'before' | 'after' } | null>(null)

  const handleDragStart = useCallback((event: DragEvent<HTMLElement>, sceneId: string) => {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData(SCENE_DRAG_MIME, sceneId)
    event.dataTransfer.setData('text/plain', sceneId)
    setDraggingId(sceneId)
  }, [])

  const handleDragEnd = useCallback(() => {
    setDraggingId(null)
    setHoverTarget(null)
  }, [])

  const handleDragOver = useCallback(
    (event: DragEvent<HTMLElement>, sceneId: string, position: 'before' | 'after') => {
      if (!event.dataTransfer.types.includes(SCENE_DRAG_MIME) && !event.dataTransfer.types.includes('text/plain')) {
        return
      }
      event.preventDefault()
      event.dataTransfer.dropEffect = 'move'
      if (hoverTarget?.id !== sceneId || hoverTarget.position !== position) {
        setHoverTarget({ id: sceneId, position })
      }
    },
    [hoverTarget],
  )

  const handleDragLeave = useCallback(() => {
    setHoverTarget(null)
  }, [])

  const handleDrop = useCallback(
    (event: DragEvent<HTMLElement>, targetId: string) => {
      const movedId = event.dataTransfer.getData(SCENE_DRAG_MIME) || event.dataTransfer.getData('text/plain')
      event.preventDefault()
      setHoverTarget(null)
      setDraggingId(null)
      if (!movedId || movedId === targetId) return
      const fromIndex = project.scenes.findIndex((scene) => scene.id === movedId)
      const targetIndex = project.scenes.findIndex((scene) => scene.id === targetId)
      if (fromIndex < 0 || targetIndex < 0) return
      const position = hoverTarget?.position ?? 'before'
      const insertAt = position === 'before' ? targetIndex : targetIndex + 1
      const next = reOrder(project.scenes, fromIndex, insertAt > fromIndex ? insertAt - 1 : insertAt)
      onReorder(fromIndex, next.findIndex((scene) => scene.id === movedId))
    },
    [hoverTarget, onReorder, project.scenes],
  )

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold">文案与画面</h2>
          <p className="mt-1 text-xs text-[#7F8DA5]">每张卡片代表一段可独立调整的画面，插图和素材会在指定场景中出现。</p>
        </div>
        <div className="flex gap-2">
          <input
            value={planInstruction}
            onChange={(event) => onPlanInstructionChange(event.target.value)}
            placeholder="告诉 AI 你想怎样调整"
            className="h-9 w-64 border border-[#2B374B] bg-[#0D1320] px-3 text-sm outline-none"
          />
          <button
            type="button"
            onClick={onRequestPlan}
            disabled={busyKey === 'plan'}
            className="inline-flex h-9 items-center gap-1.5 border border-[#535FCB] bg-[#202653] px-3 text-sm"
          >
            {busyKey === 'plan' ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
            AI 编排
          </button>
        </div>
      </div>
      <div className="space-y-4">
        {project.scenes.map((scene, index) => (
          <SceneCard
            key={scene.id}
            scene={scene}
            index={index}
            total={project.scenes.length}
            assets={assetById}
            busyKey={busyKey}
            draggable
            onDragStart={(event) => handleDragStart(event, scene.id)}
            onDragEnd={handleDragEnd}
            draggingOver={draggingId && draggingId !== scene.id && hoverTarget?.id === scene.id ? hoverTarget.position : null}
            onDragOverReorder={(event, position) => handleDragOver(event, scene.id, position)}
            onDragLeaveReorder={handleDragLeave}
            onDropReorder={(event) => handleDrop(event, scene.id)}
            onPatch={(patch) => onPatchScene(scene.id, patch)}
            onMove={(direction) => {
              const target = index + direction
              if (target < 0 || target >= project.scenes.length) return
              onReorder(index, target)
            }}
            onRemove={() => onRemove(scene.id)}
            onPickFiles={(files) => onUploadSceneFiles(scene.id, files)}
            onRequestGenerate={() => onRequestGenerate(scene)}
            onRemoveReference={(assetId) => onRemoveSceneReference(scene.id, assetId)}
          />
        ))}
      </div>
      <button
        type="button"
        onClick={onAddScene}
        className="mt-4 flex h-12 w-full items-center justify-center gap-2 border border-dashed border-[#34425A] text-sm text-[#AEB9CA] hover:border-[#6571EE]"
      >
        <Plus className="h-4 w-4" />
        添加场景
      </button>
    </div>
  )
}

export { freshScene, normalizeSceneOrder }
