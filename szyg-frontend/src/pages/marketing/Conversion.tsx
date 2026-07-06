import { Repeat2 as ConversionIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 客户转化 — 占位页面 (Phase 1 骨架)
 * 后端模块: convert
 */
export default function Conversion() {
  return (
    <Placeholder
      title="客户转化"
      description="转化漏斗与自动回复规则"
      icon={ConversionIcon}
      module="convert"
    />
  )
}
