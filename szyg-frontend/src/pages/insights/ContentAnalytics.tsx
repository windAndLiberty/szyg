import { LineChart as ContentAnalyticsIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 内容分析 — 占位页面 (Phase 1 骨架)
 * 后端模块: content-analytics
 */
export default function ContentAnalytics() {
  return (
    <Placeholder
      title="内容分析"
      description="内容表现排名与最佳发布时间分析"
      icon={ContentAnalyticsIcon}
      module="content-analytics"
    />
  )
}
