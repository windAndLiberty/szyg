import { ClipboardList as SopIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * SOP管理 — 占位页面 (Phase 1 骨架)
 * 后端模块: sop
 */
export default function Sop() {
  return (
    <Placeholder
      title="SOP管理"
      description="SOP 模板库与执行记录"
      icon={SopIcon}
      module="sop"
    />
  )
}
