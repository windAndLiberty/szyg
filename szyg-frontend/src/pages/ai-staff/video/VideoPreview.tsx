import { useRef } from 'react'
import { motion } from 'framer-motion'
import { Loader2, Play, Maximize2, Download, Scissors, Send, Clock, Film } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { VideoItem } from './types'

type VideoPreviewProps = {
  video: VideoItem | null
  status: 'idle' | 'generating' | 'previewing' | 'editing' | 'publishing' | 'error'
  progress: number
  progressPrompt?: string
  inputText: string
  setInputText: (v: string) => void
  onSend: () => void
  streaming: boolean
  messages: PreviewMessage[]
  error?: string | null
}

export interface PreviewMessage {
  role: string
  content: string
  isStreaming?: boolean
}

const QUICK_CMDS = ['裁剪前10秒', '加背景音乐', '叠加标题', '导出封面']

export default function VideoPreview({
  video, status, progress, progressPrompt, inputText, setInputText,
  onSend, streaming, messages, error,
}: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  return (
    <div className="flex-1 flex flex-col min-w-0 min-h-0">
      {/* ── 预览区（上半部分）── */}
      <div className="shrink-0 p-4">
        <div className="rounded-card-lg border border-[#1E293B] overflow-hidden"
          style={{ background: 'linear-gradient(180deg, rgba(26,34,53,0.6) 0%, rgba(13,19,33,0.9) 100%)' }}>

          {/* 进度卡片 */}
          {(status === 'generating' || status === 'idle') && !video && (
            <div className="aspect-video flex flex-col items-center justify-center gap-4 p-8">
              {status === 'generating' ? (
                <>
                  <div className="relative w-16 h-16">
                    <motion.div
                      className="absolute inset-0 rounded-full border-[3px] border-[#6366F1]"
                      animate={{ scale: [1, 1.5, 1], opacity: [0.6, 0, 0.6] }}
                      transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
                    />
                    <div className="w-16 h-16 rounded-full bg-[#1A2235] border border-[#1E293B] flex items-center justify-center">
                      <Loader2 className="w-7 h-7 text-[#6366F1] animate-spin" />
                    </div>
                  </div>
                  <div className="text-center">
                    <p className="text-body-md font-medium text-[#F1F5F9]">视频生成中…</p>
                    {progressPrompt && (
                      <p className="text-body-sm text-[#64748B] mt-1 line-clamp-1">{progressPrompt}</p>
                    )}
                  </div>
                  <div className="w-full max-w-xs">
                    <div className="flex items-center justify-between text-[11px] text-[#64748B] mb-1.5">
                      <span>进度</span>
                      <span className="tabular-nums">{progress}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-[#0D1321] overflow-hidden">
                      <motion.div
                        className="h-full rounded-full"
                        style={{
                          background: 'linear-gradient(90deg, #8B5CF6, #3B82F6, #06B6D4, #10B981)',
                          boxShadow: '0 0 12px rgba(99,102,241,0.4)',
                        }}
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
                      />
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div className="w-20 h-20 rounded-2xl bg-[#1A2235] border border-[#1E293B] flex items-center justify-center">
                    <Film className="w-10 h-10 text-[#334155]" />
                  </div>
                  <div className="text-center">
                    <p className="text-body-md font-medium text-[#94A3B8]">尚无视频</p>
                    <p className="text-body-sm text-[#64748B] mt-1">
                      使用 AI 生成 或 上传视频开始创作
                    </p>
                  </div>
                </>
              )}
            </div>
          )}

          {/* 视频播放器 */}
          {video && (status === 'previewing' || status === 'idle') && (
            <div>
              <div className="relative aspect-video bg-black">
                <video
                  ref={videoRef}
                  src={video.url}
                  controls
                  className="w-full h-full object-contain"
                  poster={video.thumbnail}
                />
              </div>
              {/* 视频信息栏 */}
              <div className="flex items-center gap-4 px-4 py-2.5 border-t border-[#1E293B] bg-[rgba(0,0,0,0.2)]">
                <div className="flex-1 min-w-0">
                  <p className="text-body-sm font-medium text-[#F1F5F9] truncate">{video.title}</p>
                  <p className="text-[11px] text-[#64748B]">
                    <Clock className="w-3 h-3 inline mr-1" />
                    {video.duration}s · {video.resolution} · {video.size_mb}MB
                  </p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button className="p-2 rounded-lg text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)]" title="放大">
                    <Maximize2 className="w-4 h-4" />
                  </button>
                  <button className="p-2 rounded-lg text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)]" title="下载">
                    <Download className="w-4 h-4" />
                  </button>
                  <button className="p-2 rounded-lg text-[#F59E0B] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)]" title="裁剪">
                    <Scissors className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 错误状态 */}
          {status === 'error' && (
            <div className="aspect-video flex flex-col items-center justify-center gap-3 p-8">
              <div className="w-16 h-16 rounded-full bg-[#EF4444]/15 flex items-center justify-center">
                <span className="text-2xl">⚠️</span>
              </div>
              <p className="text-body-md font-medium text-[#F1F5F9]">生成失败</p>
              {error && <p className="text-body-sm text-[#EF4444] max-w-sm text-center">{error}</p>}
              <p className="text-body-sm text-[#94A3B8]">请稍后重试</p>
            </div>
          )}
        </div>
      </div>

      {/* ── 对话消息流（下半部分）── */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 space-y-3 pb-2">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-[#64748B] gap-2">
            <p className="text-body-sm">输入剪辑指令或描述要生成的视频…</p>
            <div className="flex items-center gap-1.5 flex-wrap justify-center">
              {QUICK_CMDS.map((cmd) => (
                <button
                  key={cmd}
                  onClick={() => setInputText(cmd)}
                  className="px-2.5 py-1 rounded-button text-[11px] bg-[#1A2235] border border-[#1E293B] text-[#94A3B8] hover:text-[#F1F5F9] hover:border-[#334155] transition-colors"
                >
                  {cmd}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={cn('flex gap-3', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
              {msg.role === 'user' ? null : (
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center shrink-0 mt-0.5">
                  <Film className="w-3.5 h-3.5 text-white" />
                </div>
              )}
              <div className={cn(
                'max-w-[80%] rounded-card-lg px-4 py-2.5 text-body-sm leading-relaxed',
                msg.role === 'user'
                  ? 'bg-[#6366F1] text-white'
                  : 'bg-[#1A2235] text-[#F1F5F9] border border-[#1E293B]',
              )}>
                <span className="whitespace-pre-wrap break-words">{msg.content}</span>
                {msg.isStreaming && (
                  <span className="inline-block w-[7px] h-[14px] bg-[#6366F1] ml-0.5 align-middle animate-pulse" />
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── 输入框 ── */}
      <div className="shrink-0 px-4 py-3 border-t border-[#1E293B]">
        <div className="flex items-center gap-2">
          <input
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend() } }}
            placeholder="输入剪辑指令，或描述要生成的视频…"
            disabled={streaming}
            className="flex-1 h-11 px-4 rounded-card bg-[#0D1321] border border-[#1E293B] text-body-md text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155] transition-colors disabled:opacity-50"
          />
          <button
            onClick={onSend}
            disabled={!inputText.trim() || streaming}
            className="w-11 h-11 rounded-card bg-[#6366F1] text-white flex items-center justify-center hover:bg-[#818CF8] active:scale-95 transition-all disabled:opacity-40 shrink-0"
          >
            {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  )
}
