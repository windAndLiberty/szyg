import { useState } from 'react'
import { motion } from 'framer-motion'
import { Search, Play, Download, Trash2, Clock, Film, Upload, Wand2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { VideoItem } from './types'

type VideoLibraryProps = {
  videos: VideoItem[]
  onSelect: (video: VideoItem) => void
  onDelete: (id: string) => void
  selectedId?: string | null
}

const TABS = [
  { id: 'all', label: '全部' },
  { id: 'ai', label: 'AI 生成', icon: Wand2 },
  { id: 'upload', label: '我的上传', icon: Upload },
]

export default function VideoLibrary({ videos, onSelect, onDelete, selectedId }: VideoLibraryProps) {
  const [tab, setTab] = useState('all')
  const [search, setSearch] = useState('')

  const filtered = videos.filter((v) => {
    if (tab === 'ai' && v.source !== 'ai') return false
    if (tab === 'upload' && v.source !== 'upload') return false
    if (search.trim() && !v.title.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="w-[260px] shrink-0 border-l border-[#1E293B] bg-[#0B0F1A] flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-3 border-b border-[#1E293B]">
        <h2 className="text-body-md font-semibold text-[#F1F5F9] flex items-center gap-2">
          <Film className="w-4 h-4 text-[#6366F1]" /> 视频库
        </h2>
        <span className="text-[11px] text-[#64748B]">{videos.length} 个视频</span>
      </div>

      {/* Search */}
      <div className="px-3 py-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#64748B]" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索…"
            className="w-full h-8 pl-8 pr-3 rounded-button text-[12px] bg-[#0D1321] border border-[#1E293B] text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155]"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="px-2 pb-2 flex items-center gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-1 py-1 rounded-button text-[11px] font-medium transition-all',
              tab === t.id
                ? 'bg-[#6366F1] text-white'
                : 'text-[#64748B] hover:text-[#F1F5F9]',
            )}
          >
            {t.icon && <t.icon className="w-3 h-3" />}
            {t.label}
          </button>
        ))}
      </div>

      {/* Video grid */}
      <div className="flex-1 overflow-y-auto p-2">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-[#64748B] gap-1">
            <Film className="w-8 h-8 opacity-30" />
            <p className="text-[12px]">暂无视频</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {filtered.map((v) => (
              <motion.button
                key={v.id}
                whileHover={{ y: -2 }}
                onClick={() => onSelect(v)}
                className={cn(
                  'group text-left rounded-card overflow-hidden border transition-all',
                  selectedId === v.id
                    ? 'border-[#6366F1] ring-1 ring-[#6366F1]/30'
                    : 'border-[#1E293B] hover:border-[#334155]',
                )}
              >
                {/* Thumbnail */}
                <div className="relative aspect-video bg-[#0D1321] overflow-hidden">
                  {v.thumbnail ? (
                    <img src={v.thumbnail} alt={v.title} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Play className="w-5 h-5 text-[#334155]" />
                    </div>
                  )}
                  {/* Duration badge */}
                  <div className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-[9px] bg-black/60 text-white/80">
                    {v.duration}s
                  </div>
                  {/* Generate progress */}
                  {v.status === 'generating' && (
                    <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                      <div className="w-full px-3">
                        <div className="h-1 rounded-full bg-white/10 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-[#6366F1]"
                            style={{ width: `${v.progress}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="p-2 bg-[#111827]">
                  <p className="text-[11px] font-medium text-[#F1F5F9] truncate">{v.title}</p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Clock className="w-2.5 h-2.5 text-[#64748B]" />
                    <span className="text-[9px] text-[#64748B]">{v.duration}s · {v.size_mb}MB</span>
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-[9px] text-[#64748B]">
                      {v.created_at.slice(0, 10)}
                    </span>
                    <span className={cn(
                      'text-[9px] font-medium',
                      v.status === 'ready' ? 'text-[#10B981]' : v.status === 'generating' ? 'text-[#F59E0B]' : 'text-[#EF4444]',
                    )}>
                      {v.status === 'ready' ? '✓ 完成' : v.status === 'generating' ? '生成中' : '失败'}
                    </span>
                  </div>
                </div>
              </motion.button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
