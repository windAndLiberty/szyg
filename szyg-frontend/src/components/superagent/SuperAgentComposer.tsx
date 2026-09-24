import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  AlertCircle,
  ChevronRight,
  FileText,
  Loader2,
  Paperclip,
  Plus,
  Send,
  Sparkles,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useI18n } from '@/lib/i18n'

export type ComposerAttachment = {
  id: string
  name: string
  size: number
  status: 'uploading' | 'ready' | 'error'
  documentId?: string
  error?: string
}

export type ComposerSkill = {
  id: string
  name: string
  emoji: string
  description: string
  guidance: string
  installed?: boolean
}

type SuperAgentComposerProps = {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  streaming: boolean
  compact?: boolean
  attachments: ComposerAttachment[]
  onFilesSelected: (files: File[]) => void
  onRemoveAttachment: (id: string) => void
  skills: ComposerSkill[]
  selectedSkill: ComposerSkill | null
  onSelectSkill: (skill: ComposerSkill | null) => void
  onDiscoverSkills: () => void
}

type MenuPosition = {
  placement: 'top' | 'bottom'
  left: number
  width: number
  maxHeight: number
  anchor: number
}

function formatFileSize(bytes: number) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${Math.ceil(bytes / 1024)} KB`
  return `${bytes} B`
}

export default function SuperAgentComposer({
  value,
  onChange,
  onSend,
  streaming,
  compact = false,
  attachments,
  onFilesSelected,
  onRemoveAttachment,
  skills,
  selectedSkill,
  onSelectSkill,
  onDiscoverSkills,
}: SuperAgentComposerProps) {
  const { t } = useI18n()
  const [menuOpen, setMenuOpen] = useState(false)
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploading = attachments.some((item) => item.status === 'uploading')
  const hasReadyAttachment = attachments.some((item) => item.status === 'ready')
  const canSend = !streaming && !uploading && (Boolean(value.trim()) || hasReadyAttachment)

  const updateMenuPosition = useCallback(() => {
    const root = rootRef.current
    if (!root) return
    const rect = root.getBoundingClientRect()
    const viewportGap = 12
    const width = Math.min(340, window.innerWidth - viewportGap * 2)
    const left = Math.min(
      Math.max(viewportGap, rect.left),
      Math.max(viewportGap, window.innerWidth - width - viewportGap),
    )
    const availableAbove = Math.max(0, rect.top - viewportGap * 2)
    const availableBelow = Math.max(0, window.innerHeight - rect.bottom - viewportGap * 2)
    const preferred: 'top' | 'bottom' = compact ? 'top' : 'bottom'
    const preferredSpace = preferred === 'top' ? availableAbove : availableBelow
    const alternateSpace = preferred === 'top' ? availableBelow : availableAbove
    const placement = preferredSpace >= 220 || preferredSpace >= alternateSpace
      ? preferred
      : preferred === 'top' ? 'bottom' : 'top'
    const maxHeight = Math.max(180, Math.min(430, placement === 'top' ? availableAbove : availableBelow))
    setMenuPosition({
      placement,
      left,
      width,
      maxHeight,
      anchor: placement === 'top' ? window.innerHeight - rect.top + 10 : rect.bottom + 10,
    })
  }, [compact])

  useEffect(() => {
    if (!menuOpen) return
    updateMenuPosition()
    const close = (event: MouseEvent) => {
      const target = event.target as Node
      if (!rootRef.current?.contains(target) && !menuRef.current?.contains(target)) setMenuOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', closeOnEscape)
    window.addEventListener('resize', updateMenuPosition)
    window.addEventListener('scroll', updateMenuPosition, true)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', closeOnEscape)
      window.removeEventListener('resize', updateMenuPosition)
      window.removeEventListener('scroll', updateMenuPosition, true)
    }
  }, [menuOpen, updateMenuPosition])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (canSend) onSend()
    }
  }

  const chooseFiles = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || [])
    if (files.length > 0) onFilesSelected(files)
    event.target.value = ''
    setMenuOpen(false)
  }

  return (
    <div ref={rootRef} className="relative w-full">
      <div className="rounded-2xl border border-[#273449] bg-[#111827]/95 shadow-[0_16px_50px_rgba(0,0,0,0.26)] transition focus-within:border-[#46536A] focus-within:ring-1 focus-within:ring-[#6366F1]/20">
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 px-3 pt-3">
            {attachments.map((item) => (
              <div
                key={item.id}
                className={cn(
                  'flex min-w-0 max-w-[260px] items-center gap-2 rounded-lg border px-2.5 py-2',
                  item.status === 'error'
                    ? 'border-[#7F1D1D] bg-[#2A1218]'
                    : 'border-[#334155] bg-[#0B1220]',
                )}
              >
                {item.status === 'uploading' ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[#818CF8]" />
                ) : item.status === 'error' ? (
                  <AlertCircle className="h-4 w-4 shrink-0 text-[#F87171]" />
                ) : (
                  <FileText className="h-4 w-4 shrink-0 text-[#A5B4FC]" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-[#E2E8F0]">{item.name}</p>
                  <p className={cn('truncate text-[10px]', item.status === 'error' ? 'text-[#FCA5A5]' : 'text-[#64748B]')}>
                    {item.status === 'uploading'
                      ? t("正在上传…")
                      : item.status === 'error'
                        ? item.error || t("上传失败")
                        : formatFileSize(item.size)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onRemoveAttachment(item.id)}
                  className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-[#64748B] hover:bg-[#1E293B] hover:text-[#E2E8F0]"
                  aria-label={t("移除附件 {v0}", { v0: item.name })}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
          rows={compact ? 2 : 3}
          placeholder={
            selectedSkill
              ? t("使用“{v0}”处理你的任务…", { v0: selectedSkill.name })
              : t("描述任务，或通过 + 添加附件和技能")
          }
          className={cn(
            'w-full resize-none bg-transparent px-4 pt-3.5 text-sm leading-6 text-[#F1F5F9] placeholder-[#64748B] focus:outline-none',
            compact ? 'max-h-36 min-h-[64px]' : 'max-h-48 min-h-[82px]',
          )}
        />

        <div className="flex items-center gap-2 px-3 pb-3">
          <button
            type="button"
            onClick={() => setMenuOpen((current) => !current)}
            disabled={streaming}
            className={cn(
              'grid h-9 w-9 shrink-0 place-items-center rounded-full border transition',
              menuOpen
                ? 'rotate-45 border-[#6366F1] bg-[#312E81]/60 text-[#C7D2FE]'
                : 'border-[#334155] bg-[#0B1220] text-[#94A3B8] hover:border-[#64748B] hover:text-white',
            )}
            aria-label={t("添加附件或技能")}
            aria-expanded={menuOpen}
          >
            <Plus className="h-4.5 w-4.5" />
          </button>

          {selectedSkill && (
            <button
              type="button"
              onClick={() => onSelectSkill(null)}
              className="inline-flex h-8 min-w-0 max-w-[220px] items-center gap-1.5 rounded-full border border-[#4F46E5]/60 bg-[#312E81]/35 px-3 text-xs text-[#C7D2FE] hover:border-[#818CF8]"
              title={t("点击取消加载")}
            >
              <span className="text-sm leading-none" aria-hidden="true">{selectedSkill.emoji}</span>
              <span className="truncate">{selectedSkill.name}</span>
              <X className="h-3 w-3 shrink-0" />
            </button>
          )}

          <span className="ml-auto hidden text-[11px] text-[#64748B] sm:inline">{t("Enter 发送 · Shift+Enter 换行")}</span>
          <button
            type="button"
            onClick={onSend}
            disabled={!canSend}
            className={cn(
              'grid h-9 w-9 shrink-0 place-items-center rounded-full transition',
              canSend
                ? 'bg-[#E2E8F0] text-[#111827] hover:bg-white active:scale-95'
                : 'bg-[#1E293B] text-[#64748B] cursor-not-allowed',
            )}
            aria-label={t("发送")}
          >
            {streaming || uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {menuOpen && menuPosition && createPortal(
        <div
          ref={menuRef}
          className="fixed z-[100] flex overflow-hidden rounded-xl border border-[#334155] bg-[#111827] p-1.5 shadow-[0_22px_70px_rgba(0,0,0,0.5)]"
          style={{
            left: menuPosition.left,
            width: menuPosition.width,
            maxHeight: menuPosition.maxHeight,
            ...(menuPosition.placement === 'top'
              ? { bottom: menuPosition.anchor }
              : { top: menuPosition.anchor }),
          }}
        >
          <div className="flex min-h-0 w-full flex-col">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm text-[#E2E8F0] hover:bg-[#1E293B]"
          >
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#1E293B] text-[#A5B4FC]">
              <Paperclip className="h-4 w-4" />
            </span>
            <span>
              <span className="block font-medium">{t("上传附件")}</span>
              <span className="block text-[11px] text-[#64748B]">{t("文档、表格、图片、音视频，单个不超过 80 MB")}</span>
            </span>
          </button>

          <div className="my-1.5 h-px bg-[#273449]" />
          <div className="px-3 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#64748B]">{t("常用技能")}</div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {skills.map((skill) => (
              <button
                key={skill.id}
                type="button"
                onClick={() => {
                  onSelectSkill(skill)
                  setMenuOpen(false)
                }}
                className={cn(
                  'flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-[#1E293B]',
                  selectedSkill?.id === skill.id && 'bg-[#312E81]/35',
                )}
              >
                <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[#1E293B] text-base leading-none" aria-hidden="true">
                  {skill.emoji}
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-2 text-sm font-medium text-[#E2E8F0]">
                    <span className="truncate">{skill.name}</span>
                    {skill.installed && <span className="rounded bg-[#064E3B]/60 px-1.5 py-0.5 text-[9px] text-[#6EE7B7]">{t("已安装")}</span>}
                  </span>
                  <span className="mt-0.5 block line-clamp-2 text-[11px] leading-4 text-[#64748B]">{skill.description}</span>
                </span>
              </button>
            ))}
          </div>
          <div className="my-1.5 h-px shrink-0 bg-[#273449]" />
          <button
            type="button"
            onClick={() => {
              setMenuOpen(false)
              onDiscoverSkills()
            }}
            className="flex w-full shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm text-[#C7D2FE] hover:bg-[#1E293B]"
          >
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#312E81]/45 text-[#A5B4FC]">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="font-medium">{t("发现更多技能")}</span>
            <ChevronRight className="ml-auto h-4 w-4 text-[#64748B]" />
          </button>
          </div>
        </div>,
        document.body,
      )}

      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={chooseFiles}
        accept=".txt,.md,.pdf,.doc,.docx,.xls,.xlsx,.csv,.ppt,.pptx,.png,.jpg,.jpeg,.webp,.gif,.mp3,.wav,.m4a,.mp4,.mov,.webm"
      />
    </div>
  )
}
