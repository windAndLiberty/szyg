import { Users as CustomersIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 客户资产 — 占位页面 (Phase 1 骨架)
 * 后端模块: customers
 */
export default function Customers() {
  return (
    <Placeholder
      title="客户资产"
      description="客户列表、标签管理与互动时间线"
      icon={CustomersIcon}
      module="customers"
    />
  )
}
