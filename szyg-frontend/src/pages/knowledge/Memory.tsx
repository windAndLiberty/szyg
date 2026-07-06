import { BrainCircuit as MemoryIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 长期记忆 — 占位页面 (Phase 1 骨架)
 * 后端模块: memory
 */
export default function Memory() {
  return (
    <Placeholder
      title="长期记忆"
      description="Agent 记忆管理"
      icon={MemoryIcon}
      module="memory"
    />
  )
}
