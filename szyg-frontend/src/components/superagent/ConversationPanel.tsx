import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Archive, Plus, MessageSquare, Pin, Trash2, Pencil, X } from 'lucide-react'
import type { Conversation } from '@/types'
import { cn } from '@/lib/utils'
import { translateCurrent, useI18n } from '@/lib/i18n'

type ConversationPanelProps = {
  conversations: Conversation[]
  activeConvId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onPin: (conv: Conversation) => void
  onArchive: (conv: Conversation) => void
  onDelete: (conv: Conversation) => void
  onRename: (conv: Conversation, title: string) => void
}

const formatTime = (iso: string) => {
  if (!iso) return ''
  const date = new Date(iso)
  const diff = Date.now() - date.getTime()
  const hours = Math.floor(diff / (1000 * 60 * 60))
  if (hours < 1) return translateCurrent("刚刚")
  if (hours < 24) return translateCurrent("{v0}小时前", { v0: hours })
  const days = Math.floor(hours / 24)
  if (days < 7) return translateCurrent("{v0}天前", { v0: days })
  return date.toLocaleDateString('zh-CN')
}

type CtxState = { show: boolean; x: number; y: number; conv: Conversation | null }

const ConversationPanel: React.FC<ConversationPanelProps> = ({
  conversations,
  activeConvId,
  onSelect,
  onNew,
  onPin,
  onArchive,
  onDelete,
  onRename,
}) => {
  const { t } = useI18n()
  const [ctx, setCtx] = useState<CtxState>({ show: false, x: 0, y: 0, conv: null })
  const [renaming, setRenaming] = useState<Conversation | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const menuRef = useRef<HTMLDivElement>(null)

  const openCtx = (e: React.MouseEvent, conv: Conversation) => {
    e.preventDefault()
    setCtx({ show: true, x: e.clientX, y: e.clientY, conv })
  }

  const closeCtx = () => setCtx((c) => ({ ...c, show: false }))

  useEffect(() => {
    const handler = () => closeCtx()
    if (ctx.show) {
      window.addEventListener('click', handler)
      return () => window.removeEventListener('click', handler)
    }
  }, [ctx.show])

  const startRename = (conv: Conversation) => {
    closeCtx()
    setRenaming(conv)
    setRenameValue(conv.title)
  }

  const submitRename = () => {
    if (renaming && renameValue.trim()) onRename(renaming, renameValue.trim())
    setRenaming(null)
  }

  const sorted = [...conversations].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  })

  return (
    <div className="w-[280px] shrink-0 bg-[#0B0F1A] border-r border-[#1E293B] flex flex-col">
      <div className="h-12 flex items-center justify-between px-4 border-b border-[#1E293B] shrink-0">
        <span className="text-[13px] font-semibold text-[#F1F5F9]">{t("对话历史")}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={onNew}
            className="p-1 rounded-md text-[#64748B] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)] transition-colors"
            aria-label={t("新建对话")}
            title={t("新建对话")}
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[#64748B] gap-2">
            <MessageSquare className="w-7 h-7 opacity-40" />
            <span className="text-[13px]">{t("暂无对话记录")}</span>
          </div>
        ) : (
          sorted.map((conv) => (
            <div
              key={conv.id}
              onClick={() => onSelect(conv.id)}
              onContextMenu={(e) => openCtx(e, conv)}
              className={cn(
                'group relative px-3 py-2.5 rounded-lg cursor-pointer mb-1 transition-colors',
                conv.id === activeConvId ? 'bg-[rgba(99,102,241,0.1)]' : 'hover:bg-[rgba(255,255,255,0.03)]',
              )}
            >
              <div className="flex items-center gap-1.5 pr-14">
                <span
                  className={cn(
                    'text-[13px] truncate flex-1',
                    conv.id === activeConvId ? 'text-[#6366F1] font-medium' : 'text-[#94A3B8]',
                  )}
                >
                  {conv.title}
                </span>
              </div>
              <div className="text-[11px] text-[#64748B] mt-1">{formatTime(conv.updated_at)}</div>
              <div className="absolute right-2 top-2 flex items-center gap-0.5">
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    onPin(conv)
                  }}
                  className={cn(
                    'inline-flex h-6 w-6 items-center justify-center rounded-md transition-all group-hover:opacity-100 hover:bg-[#1E293B] hover:text-[#C7D2FE] focus:opacity-100 focus:outline-none focus:ring-1 focus:ring-[#6366F1]/50',
                    conv.pinned ? 'text-[#818CF8] opacity-100' : 'text-[#64748B] opacity-0',
                  )}
                  aria-label={conv.pinned ? t("取消置顶") : t("置顶")}
                  title={conv.pinned ? t("取消置顶") : t("置顶")}
                >
                  <Pin className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    onArchive(conv)
                  }}
                  className="inline-flex h-6 w-6 items-center justify-center rounded-md text-[#64748B] opacity-0 transition-all hover:bg-[#1E293B] hover:text-[#F1F5F9] focus:opacity-100 focus:outline-none focus:ring-1 focus:ring-[#6366F1]/50 group-hover:opacity-100 group-focus-within:opacity-100"
                  aria-label={t("归档对话")}
                  title={t("归档")}
                >
                  <Archive className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Context menu */}
      <AnimatePresence>
        {ctx.show && ctx.conv && (
          <motion.div
            ref={menuRef}
            className="fixed z-[200] min-w-[140px] bg-[#1A2235] border border-[#1E293B] rounded-lg shadow-card-lift py-1"
            style={{ left: ctx.x, top: ctx.y }}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => {
                if (ctx.conv) onPin(ctx.conv)
                closeCtx()
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-[13px] text-[#94A3B8] hover:bg-[rgba(255,255,255,0.05)] hover:text-[#F1F5F9] transition-colors"
            >
              <Pin className="w-3.5 h-3.5" /> {ctx.conv.pinned ? t("取消置顶") : t("置顶")}
            </button>
            <button
              onClick={() => ctx.conv && startRename(ctx.conv)}
              className="flex items-center gap-2 w-full px-3 py-2 text-[13px] text-[#94A3B8] hover:bg-[rgba(255,255,255,0.05)] hover:text-[#F1F5F9] transition-colors"
            >
              <Pencil className="w-3.5 h-3.5" />  {t("重命名")}
            </button>
            <button
              onClick={() => {
                if (ctx.conv) onArchive(ctx.conv)
                closeCtx()
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-[13px] text-[#94A3B8] hover:bg-[rgba(255,255,255,0.05)] hover:text-[#F1F5F9] transition-colors"
            >
              <Archive className="w-3.5 h-3.5" />  {t("归档")}
            </button>
            <div className="h-px bg-[#1E293B] my-1" />
            <button
              onClick={() => {
                if (ctx.conv) onDelete(ctx.conv)
                closeCtx()
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-[13px] text-[#EF4444] hover:bg-[rgba(239,68,68,0.08)] transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />  {t("删除")}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Rename modal */}
      <AnimatePresence>
        {renaming && (
          <motion.div
            className="fixed inset-0 z-[210] flex items-center justify-center bg-black/60 backdrop-blur-sm p-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setRenaming(null)}
          >
            <motion.div
              className="w-full max-w-sm rounded-card-lg bg-[#1A2235] border border-[#1E293B] p-5 shadow-card-lift"
              initial={{ scale: 0.95, y: 10 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 10 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-heading-sm text-[#F1F5F9]">{t("重命名对话")}</h3>
                <button onClick={() => setRenaming(null)} className="text-[#64748B] hover:text-[#F1F5F9]">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <input
                autoFocus
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submitRename()}
                className="w-full h-10 px-3 rounded-input bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#334155]"
              />
              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={() => setRenaming(null)}
                  className="px-3 py-2 rounded-button text-sm text-[#94A3B8] hover:bg-[rgba(255,255,255,0.05)] transition-colors"
                >

                  {t("取消")}
                </button>
                <button
                  onClick={submitRename}
                  className="px-4 py-2 rounded-button text-sm font-medium bg-[#6366F1] text-white hover:bg-[#818CF8] transition-colors"
                >

                  {t("确定")}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default React.memo(ConversationPanel)
