import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Wand2, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { VideoGenParams } from './types'
import { GEN_DEFAULTS } from './types'

type CreateDialogProps = {
  open: boolean
  onClose: () => void
  onSubmit: (params: VideoGenParams) => void
  generating?: boolean
}

const STYLES = [
  { id: 'realistic', label: '写实' },
  { id: 'anime', label: '动漫' },
  { id: 'cinematic', label: '电影感' },
  { id: 'cyberpunk', label: '赛博朋克' },
]

const DURATIONS = [3, 5, 10, 15]

export default function CreateDialog({ open, onClose, onSubmit, generating }: CreateDialogProps) {
  const [params, setParams] = useState<VideoGenParams>(GEN_DEFAULTS)

  const update = (k: keyof VideoGenParams, v: string | number) =>
    setParams((p) => ({ ...p, [k]: v }))

  const handleSubmit = () => {
    if (!params.prompt.trim()) return
    onSubmit(params)
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

          {/* Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="relative w-full max-w-lg mx-4 rounded-card-lg border border-[#1E293B] overflow-hidden"
            style={{ background: 'linear-gradient(180deg, rgba(26,34,53,0.98) 0%, rgba(17,24,39,0.99) 100%)' }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#1E293B]">
              <h2 className="text-heading-sm text-[#F1F5F9] flex items-center gap-2">
                <Wand2 className="w-5 h-5 text-[#6366F1]" /> AI 生成视频
              </h2>
              <button onClick={onClose} className="p-1.5 rounded-lg text-[#64748B] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)]">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-5 space-y-4">
              {/* Prompt */}
              <div>
                <label className="block text-body-sm font-medium text-[#94A3B8] mb-2">
                  描述你想要的视频内容
                </label>
                <textarea
                  value={params.prompt}
                  onChange={(e) => update('prompt', e.target.value)}
                  placeholder="例如：海浪拍打岩石的慢镜头，电影感，柔和光线…"
                  rows={3}
                  className="w-full bg-[#0D1321] border border-[#1E293B] rounded-card px-4 py-3 text-body-md text-[#F1F5F9] placeholder-[#64748B] resize-none focus:outline-none focus:border-[#334155] transition-colors"
                  disabled={generating}
                />
              </div>

              {/* 快捷风格标签 */}
              <div className="flex items-center gap-2 flex-wrap">
                {STYLES.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => update('style', s.id)}
                    className={cn(
                      'px-3 py-1 rounded-button text-[12px] font-medium transition-all border',
                      params.style === s.id
                        ? 'bg-[#6366F1] text-white border-[#6366F1]'
                        : 'bg-[#1A2235] text-[#94A3B8] border-[#1E293B] hover:text-[#F1F5F9]',
                    )}
                    disabled={generating}
                  >
                    {s.label}
                  </button>
                ))}
              </div>

              {/* 参数行 */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] text-[#64748B] mb-1">时长</label>
                  <select
                    value={params.duration}
                    onChange={(e) => update('duration', Number(e.target.value))}
                    className="w-full bg-[#0D1321] border border-[#1E293B] rounded-button px-3 py-2 text-body-sm text-[#F1F5F9] focus:outline-none focus:border-[#334155]"
                    disabled={generating}
                  >
                    {DURATIONS.map((d) => (
                      <option key={d} value={d}>{d}s</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] text-[#64748B] mb-1">模式</label>
                  <select
                    value={params.mode}
                    onChange={(e) => update('mode', e.target.value)}
                    className="w-full bg-[#0D1321] border border-[#1E293B] rounded-button px-3 py-2 text-body-sm text-[#F1F5F9] focus:outline-none focus:border-[#334155]"
                    disabled={generating}
                  >
                    <option value="text-to-video">文生视频</option>
                    <option value="image-to-video">图生视频</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] text-[#64748B] mb-1">模型</label>
                  <select
                    value={params.model}
                    onChange={(e) => update('model', e.target.value)}
                    className="w-full bg-[#0D1321] border border-[#1E293B] rounded-button px-3 py-2 text-body-sm text-[#F1F5F9] focus:outline-none focus:border-[#334155]"
                    disabled={generating}
                  >
                    <option value="doubao-video">豆包视频</option>
                    <option value="seaweed">Seaweed</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-[#1E293B] bg-[rgba(0,0,0,0.15)]">
              <button
                onClick={onClose}
                disabled={generating}
                className="px-4 py-2 rounded-button text-[13px] text-[#94A3B8] hover:text-[#F1F5F9] transition-colors disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={handleSubmit}
                disabled={!params.prompt.trim() || generating}
                className="flex items-center gap-2 px-5 py-2 rounded-button text-[13px] font-medium bg-[#6366F1] text-white hover:bg-[#818CF8] disabled:opacity-40 transition-all active:scale-95 shadow-glow"
              >
                {generating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> 生成中…
                  </>
                ) : (
                  <>
                    <Wand2 className="w-4 h-4" /> 开始生成
                  </>
                )}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
