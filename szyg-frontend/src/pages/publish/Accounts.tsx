import { KeyRound as AccountsIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 账号管理 — 占位页面 (Phase 1 骨架)
 * 后端模块: platforms
 */
export default function Accounts() {
  return (
    <Placeholder
      title="账号管理"
      description="平台登录状态、扫码登录、Cookie 管理"
      icon={AccountsIcon}
      module="platforms"
    />
  )
}
