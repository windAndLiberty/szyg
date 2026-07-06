import { PenLine as ContentProductionIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 内容生产 — 占位页面 (Phase 1 骨架)
 * 后端模块: image
 */
export default function ContentProduction() {
  return (
    <Placeholder
      title="内容生产"
      description="文生图、文生视频、文案生成、语音合成"
      icon={ContentProductionIcon}
      module="image"
    />
  )
}
