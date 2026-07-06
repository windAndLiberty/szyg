import { CalendarDays as ContentCalendarIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 内容日历 — 占位页面 (Phase 1 骨架)
 * 后端模块: scheduler
 */
export default function ContentCalendar() {
  return (
    <Placeholder
      title="内容日历"
      description="日历视图与发布计划编排"
      icon={ContentCalendarIcon}
      module="scheduler"
    />
  )
}
