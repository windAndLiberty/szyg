import { CalendarDays as ContentCalendarIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'
import { useI18n } from '@/lib/i18n'

/**
 * 内容日历 — 占位页面 (Phase 1 骨架)
 * 后端模块: scheduler
 */
export default function ContentCalendar() {
  const { t } = useI18n();

  return (
    <Placeholder
      title={t("内容日历")}
      description={t("日历视图与发布计划编排")}
      icon={ContentCalendarIcon}
      module="scheduler"
    />
  )
}
