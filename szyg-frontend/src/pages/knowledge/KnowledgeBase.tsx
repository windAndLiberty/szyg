import { Database as KnowledgeBaseIcon } from 'lucide-react'
import Placeholder from '@/components/Placeholder'

/**
 * 知识管理 — 占位页面 (Phase 1 骨架)
 * 后端模块: knowledge
 */
export default function KnowledgeBase() {
  return (
    <Placeholder
      title="知识管理"
      description="文档管理与向量检索（RAG）"
      icon={KnowledgeBaseIcon}
      module="knowledge"
    />
  )
}
