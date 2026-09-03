import { UsersRound as TeamIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 团队管理 — 占位页面 (Phase 1 骨架)
 * 后端模块: team
 */
export default function Team() {
  return (
    <Placeholder
      title="团队管理"
      description="团队成员、角色权限管理"
      icon={TeamIcon}
      module="team"
    />
  )
}
