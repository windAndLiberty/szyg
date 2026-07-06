import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Rocket, Loader2, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PublishTarget } from './types'

type PublishPanelProps = {
  open: boolean
  onClose: () => void
  onPublish: (target: PublishTarget) => void
  publishing?: boolean
}

const PLATFORMS = [
  { id: 'douyin', label: '抖音', color: '#111111' },
  { id: 'xhs', label: '小红书', color: '#FF2442' },
  { id: 'bilibili', label: 'B站', color: '#FB7299' },
  { id: 'kuaishou', label: '快手', color: '#FF4906' },
  { id: 'wechat_mp', label: '微信', color: '#07C160' },
]

export default function PublishPanel({ open, onClose, onPublish, publishing }: PublishPanelProps) {
  const [platform, setPlatform] = useState('douyin')
  const [title, setTitle] = useState('')
  const [tags, setTags] = useState('')
  const [description, setDescription] = useState('')

  const handlePublish = () => {
    if (!title.trim()) return
    onPublish({
      platform,
      title: title.trim(),
      tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      description: description.trim(),
    })
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
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="relative w-full max-w-md mx-4 rounded-card-lg border border-[#1E293B] overflow-hidden"
            style={{ background: 'linear-gradient(180deg, rgba(26,34,53,0.98) 0%, rgba(17,24,39,0.99) 100%)' }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#1E293B]">
              <h2 className="text-heading-sm text-[#F1F5F9] flex items-center gap-2">
                <Rocket className="w-5 h-5 text-[#10B981]" /> 发布视频
              </h2>
              <button onClick={onClose} className="p-1.5 rounded-lg text-[#64748B] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)]">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-5 space-y-4">
              {/* 平台选择 */}
              <div>
                <label className="block text-body-sm font-medium text-[#94A3B8] mb-2">选择平台</label>
                <div className="flex items-center gap-2 flex-wrap">
                  {PLATFORMS.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => setPlatform(p.id)}
                      className={cn(
                        'px-3 py-1.5 rounded-button text-[12px] font-medium border transition-all',
                        platform === p.id
                          ? 'text-white'
                          : 'bg-[#1A2235] text-[#94A3B8] border-[#1E293B] hover:text-[#F1F5F9]',
                      )}
                      style={platform === p.id ? { background: p.color, borderColor: p.color } : undefined}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 标题 */}
              <div>
                <label className="block text-body-sm font-medium text-[#94A3B8] mb-2">标题</label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="视频标题…"
                  className="w-full h-10 px-4 rounded-card bg-[#0D1321] border border-[#1E293B] text-body-md text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155]"
                  disabled={publishing}
                />
              </div>

              {/* 标签 */}
              <div>
                <label className="block text-body-sm font-medium text-[#94A3B8] mb-2">标签（逗号分隔）</label>
                <input
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="AI, 测试, 视频…"
                  className="w-full h-10 px-4 rounded-card bg-[#0D1321] border border-[#1E293B] text-body-md text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155]"
                  disabled={publishing}
                />
              </div>

              {/* 描述 */}
              <div>
                <label className="block text-body-sm font-medium text-[#94A3B8] mb-2">描述（可选）</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="视频描述…"
                  rows={2}
                  className="w-full bg-[#0D1321] border border-[#1E293B] rounded-card px-4 py-2.5 text-body-sm text-[#F1F5F9] placeholder-[#64748B] resize-none focus:outline-none focus:border-[#334155]"
                  disabled={publishing}
                />
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-[#1E293B] bg-[rgba(0,0,0,0.15)]">
              <button
                onClick={onClose}
                disabled={publishing}
                className="px-4 py-2 rounded-button text-[13px] text-[#94A3B8] hover:text-[#F1F5F9] transition-colors disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={handlePublish}
                disabled={!title.trim() || publishing}
                className="flex items-center gap-2 px-5 py-2 rounded-button text-[13px] font-medium bg-[#10B981] text-white hover:bg-[#34D399] disabled:opacity-40 transition-all active:scale-95 shadow-glow"
              >
                {publishing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> 发布中…
                  </>
                ) : (
                  <>
                    <Rocket className="w-4 h-4" /> 立即发布
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
