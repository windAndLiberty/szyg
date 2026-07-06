import { Wrench as ToolsIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 工具管理 — 占位页面 (Phase 1 骨架)
 * 后端模块: tools
 */
export default function Tools() {
  return (
    <Placeholder
      title="工具管理"
      description="工具列表、安装与启停"
      icon={ToolsIcon}
      module="tools"
    />
  )
}
