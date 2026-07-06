import { Radar as ListenIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 舆情监听 — 占位页面 (Phase 1 骨架)
 * 后端模块: listen
 */
export default function Listen() {
  return (
    <Placeholder
      title="舆情监听"
      description="关键词配置、监听结果流、预警通知"
      icon={ListenIcon}
      module="listen"
    />
  )
}
