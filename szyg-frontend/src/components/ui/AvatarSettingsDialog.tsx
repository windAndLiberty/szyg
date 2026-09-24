import { useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Upload, Trash2 } from 'lucide-react'
import UserAvatar from '@/components/ui/UserAvatar'
import { cn } from '@/lib/utils'
import {
  AVATAR_PRESETS,
  clearUserAvatar,
  fileToAvatarDataUrl,
  setAvatarCustom,
  setAvatarPreset,
  useUserAvatar,
} from '@/lib/avatar'
import { useI18n } from '@/lib/i18n'

type AvatarSettingsDialogProps = {
  open: boolean
  onClose: () => void
  /** 显示异常提示（如图片过大） */
  onError?: (message: string) => void
}

const easeOutExpo = [0.16, 1, 0.3, 1] as [number, number, number, number]

/**
 * 头像设置弹窗 — 点击任意位置的用户头像即可打开。
 * 仅支持本地管理：内置头像 / 上传自定义，全部保存于本机，不上传云端。
 */
export default function AvatarSettingsDialog({ open, onClose, onError }: AvatarSettingsDialogProps) {
  const { t } = useI18n()
  const source = useUserAvatar()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [saving, setSaving] = useState(false)

  const handleFile = async (file?: File | null) => {
    if (!file) return
    if (!/^image\//.test(file.type)) {
      onError?.(t("请选择图片文件"))
      return
    }
    setSaving(true)
    try {
      const dataUrl = await fileToAvatarDataUrl(file)
      if (!setAvatarCustom(dataUrl)) {
        onError?.(t("图片过大，本机存储空间不足，请换一张小一点的图片"))
      }
    } catch {
      onError?.(t("图片处理失败，请换一张图片重试"))
    } finally {
      setSaving(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const hasCustom = source.kind !== 'default'

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[80] flex flex-col overflow-y-auto bg-black/60 backdrop-blur-sm p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 14, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 14, scale: 0.96 }}
            transition={{ duration: 0.2, ease: easeOutExpo }}
            onClick={(event) => event.stopPropagation()}
            className="m-auto w-full max-w-md rounded-2xl border border-[#26334B] bg-[#141B2D] shadow-2xl overflow-hidden"
          >
            <div className="flex items-center justify-between px-5 pt-5 pb-4 border-b border-[#1E293B]">
              <h3 className="text-base font-semibold text-[#F1F5F9]">{t("设置头像")}</h3>
              <span className="text-xs text-[#64748B]">{t("仅保存在本机，不会上传云端")}</span>
            </div>

            <div className="px-5 py-5 space-y-6">
              {/* 当前头像预览 */}
              <div className="flex items-center gap-4">
                <UserAvatar className="h-20 w-20 border-2 border-[#26334B]" />
                <div className="text-sm text-[#94A3B8] leading-relaxed">
                  <p>{t("选择你喜欢的内置头像，")}</p>
                  <p>{t("或点击下方按钮上传自己的照片。")}</p>
                </div>
              </div>

              {/* 内置头像选择 */}
              <div>
                <p className="mb-3 text-sm text-[#94A3B8]">{t("内置头像")}</p>
                <div className="grid grid-cols-5 gap-3">
                  {AVATAR_PRESETS.map((src, index) => (
                    <button
                      key={src}
                      type="button"
                      onClick={() => setAvatarPreset(index)}
                      className={cn(
                        'aspect-square w-full rounded-full overflow-hidden border-2 transition-all',
                        source.kind === 'preset' && source.index === index
                          ? 'border-[#6366F1] ring-2 ring-[#6366F1]/40 scale-105'
                          : 'border-[#1E293B] hover:border-[#334155]',
                      )}
                      title={index === 0 ? t("默认头像") : t("内置头像 {v0}", { v0: index + 1 })}
                    >
                      <img src={src} alt={index === 0 ? t("默认头像") : t("内置头像 {v0}", { v0: index + 1 })} loading="lazy" draggable={false} className="h-full w-full object-cover" />
                    </button>
                  ))}
                </div>
              </div>

              {/* 自定义上传 */}
              <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-[#334155] bg-[#0D1321]/60 px-4 py-3">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[rgba(99,102,241,0.15)] text-[#A5B4FC]">
                    <Upload className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[#F1F5F9]">{t("上传自定义头像")}</p>
                    <p className="mt-0.5 text-xs text-[#64748B]">{t("支持 JPG / PNG，将自动压缩后保存在本机")}</p>
                  </div>
                </div>
                <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={(event) => void handleFile(event.target.files?.[0])} />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={saving}
                  className="shrink-0 rounded-lg bg-[#6366F1] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[#818CF8] disabled:opacity-60"
                >
                  {saving ? t("处理中…") : t("选择图片")}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between px-5 py-4 border-t border-[#1E293B]">
              {hasCustom ? (
                <button
                  type="button"
                  onClick={() => clearUserAvatar()}
                  className="inline-flex items-center gap-1.5 text-sm text-[#94A3B8] transition-colors hover:text-[#EF4444]"
                >
                  <Trash2 className="h-4 w-4" />

                  {t("恢复默认头像")}
                </button>
              ) : (
                <span />
              )}
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-[#1E293B] px-4 py-2 text-sm text-[#94A3B8] transition-colors hover:border-[#334155] hover:text-[#F1F5F9]"
              >

                {t("完成")}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}