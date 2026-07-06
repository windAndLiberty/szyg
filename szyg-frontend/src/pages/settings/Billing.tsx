import { CreditCard as BillingIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 计费管理 — 占位页面 (Phase 1 骨架)
 * 后端模块: billing
 */
export default function Billing() {
  return (
    <Placeholder
      title="计费管理"
      description="套餐、用量与账单管理"
      icon={BillingIcon}
      module="billing"
    />
  )
}
