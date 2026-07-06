import { ShieldCheck as RiskControlIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 风控策略 — 占位页面 (Phase 1 骨架)
 * 后端模块: risk
 */
export default function RiskControl() {
  return (
    <Placeholder
      title="风控策略"
      description="频率限制、屏蔽词、安全策略配置"
      icon={RiskControlIcon}
      module="risk"
    />
  )
}
