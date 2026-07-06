import { Fish as InterceptIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 智能截流 — 占位页面 (Phase 1 骨架)
 * 后端模块: acquisition
 */
export default function Intercept() {
  return (
    <Placeholder
      title="智能截流"
      description="搜索目标视频、配置截流策略、执行评论"
      icon={InterceptIcon}
      module="acquisition"
    />
  )
}
