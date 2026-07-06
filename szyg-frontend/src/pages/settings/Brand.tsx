import { Palette as BrandIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 品牌配置 — 占位页面 (Phase 1 骨架)
 * 后端模块: oem
 */
export default function Brand() {
  return (
    <Placeholder
      title="品牌配置"
      description="OEM 白标、品牌名称与视觉定制"
      icon={BrandIcon}
      module="oem"
    />
  )
}
