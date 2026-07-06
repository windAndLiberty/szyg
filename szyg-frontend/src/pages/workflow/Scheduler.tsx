import { Clock as SchedulerIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 调度引擎 — 占位页面 (Phase 1 骨架)
 * 后端模块: scheduler
 */
export default function Scheduler() {
  return (
    <Placeholder
      title="调度引擎"
      description="定时任务管理、任务队列与执行日志"
      icon={SchedulerIcon}
      module="scheduler"
    />
  )
}
