import { GraduationCap as AcademyIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 商学院 — 占位页面 (Phase 1 骨架)
 * 后端模块: academy
 */
export default function Academy() {
  return (
    <Placeholder
      title="商学院"
      description="运营知识学习与最佳实践"
      icon={AcademyIcon}
      module="academy"
    />
  )
}
