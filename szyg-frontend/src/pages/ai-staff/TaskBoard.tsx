import { ListChecks as TaskBoardIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 任务看板 — 占位页面 (Phase 1 骨架)
 * 后端模块: staff
 */
export default function TaskBoard() {
  return (
    <Placeholder
      title="任务看板"
      description="查看执行中任务、历史记录与任务统计"
      icon={TaskBoardIcon}
      module="staff"
    />
  )
}
