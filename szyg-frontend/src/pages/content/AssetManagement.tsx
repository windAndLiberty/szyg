import { Image as AssetManagementIcon } from 'lucide-react'  // eslint-disable-line
import Placeholder from '@/components/Placeholder'

/**
 * 素材管理 — 占位页面 (Phase 1 骨架)
 * 后端模块: materials
 */
export default function AssetManagement() {
  return (
    <Placeholder
      title="素材管理"
      description="上传、预览、删除素材，AI 生成物归档"
      icon={AssetManagementIcon}
      module="materials"
    />
  )
}
