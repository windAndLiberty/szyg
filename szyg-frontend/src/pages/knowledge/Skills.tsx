import { Cpu as SkillsIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 技能市场 — 占位页面 (Phase 1 骨架)
 * 后端模块: skills
 */
export default function Skills() {
  return (
    <Placeholder
      title="技能市场"
      description="MCP 工具管理与技能安装"
      icon={SkillsIcon}
      module="skills"
    />
  )
}
