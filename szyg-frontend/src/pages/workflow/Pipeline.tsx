import { GitBranch as PipelineIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 流水线编排 — 占位页面 (Phase 1 骨架)
 * 后端模块: pipeline
 */
export default function Pipeline() {
  return (
    <Placeholder
      title="流水线编排"
      description="可视化画布、节点配置与流水线模板"
      icon={PipelineIcon}
      module="pipeline"
    />
  )
}
