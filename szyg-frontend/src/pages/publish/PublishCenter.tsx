import { Send as PublishCenterIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 发布中心 — 占位页面 (Phase 1 骨架)
 * 后端模块: publisher
 */
export default function PublishCenter() {
  return (
    <Placeholder
      title="发布中心"
      description="视频/图文发布、定时发布、多平台一键发布"
      icon={PublishCenterIcon}
      module="publisher"
    />
  )
}
