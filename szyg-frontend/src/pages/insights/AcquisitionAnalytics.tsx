import { TrendingUp as AcquisitionAnalyticsIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 获客分析 — 占位页面 (Phase 1 骨架)
 * 后端模块: acquisition-analytics
 */
export default function AcquisitionAnalytics() {
  return (
    <Placeholder
      title="获客分析"
      description="截流效果与转化归因分析"
      icon={AcquisitionAnalyticsIcon}
      module="acquisition-analytics"
    />
  )
}
