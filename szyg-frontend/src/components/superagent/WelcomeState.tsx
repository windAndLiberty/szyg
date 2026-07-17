import React from 'react'
import { motion } from 'framer-motion'
import { Send, Film, Loader2, ExternalLink } from 'lucide-react'
import type { CaseCard } from '@/types'
import { cn } from '@/lib/utils'

type WelcomeStateProps = {
  inputText: string
  setInputText: (v: string) => void
  onSend: () => void
  onCaseClick: (card: CaseCard) => void
  streaming: boolean
  caseCards: CaseCard[]
  caseCardsLoading: boolean
}

const formatLikes = (n: number) => (n >= 10000 ? `${(n / 10000).toFixed(1)}w` : `${n}`)

const WelcomeState: React.FC<WelcomeStateProps> = ({
  inputText,
  setInputText,
  onSend,
  onCaseClick,
  streaming,
  caseCards,
  caseCardsLoading,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <motion.div
      className="flex-1 flex flex-col items-center justify-center px-6 py-10 overflow-y-auto"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* Brand block */}
      <motion.div
        className="flex flex-col items-center gap-4 mb-10"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        <div className="relative">
          <div
            className="absolute inset-0 rounded-2xl blur-2xl opacity-40"
            style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.6) 0%, transparent 70%)' }}
          />
          <div className="relative w-32 h-32 rounded-2xl overflow-hidden shadow-glow-strong">
            <img src="/logo1.jpg" alt="超级员工" className="w-full h-full object-cover" />
          </div>
        </div>
        <div className="text-center">
          <p className="text-body-md text-[#94A3B8]">智能体协同 · 一句话调度真实工具与生成</p>
        </div>
      </motion.div>

      {/* Input box */}
      <motion.div
        className="w-full max-w-2xl mb-10"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        <div className="relative rounded-card-lg border border-[#1E293B] bg-[#111827]/80 backdrop-blur-md focus-within:border-[#334155] focus-within:ring-1 focus-within:ring-[#6366F1]/20 transition-all overflow-hidden">
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={streaming}
            rows={3}
            placeholder="描述你想要生成的视频或图片，或直接派发任务，例如：搜索抖音AI培训视频并截流"
            className="w-full bg-transparent text-body-md text-[#F1F5F9] placeholder-[#64748B] px-4 py-3.5 resize-none focus:outline-none"
          />
          <div className="flex items-center justify-between px-3 pb-3">
            <span className="text-[11px] text-[#64748B]">Enter 发送 · Shift+Enter 换行</span>
            <button
              onClick={onSend}
              disabled={streaming || !inputText.trim()}
              className={cn(
                'flex items-center justify-center w-12 h-12 rounded-button transition-all',
                inputText.trim() && !streaming
                  ? 'bg-[#6366F1] text-white hover:bg-[#818CF8] active:scale-95 shadow-glow'
                  : 'bg-[#1A2235] text-[#64748B] cursor-not-allowed',
              )}
              aria-label="发送"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </motion.div>

      {/* === CASE CARDS SECTION === */}
      <motion.div
        className="w-full max-w-4xl"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        <div className="flex items-center gap-2 mb-4">
          <Film className="w-4 h-4 text-[#6366F1]" />
          <span className="text-heading-sm text-[#F1F5F9]">智能员工 · 精选案例</span>
        </div>

        {caseCardsLoading ? (
          <div className="flex items-center justify-center py-10 text-[#64748B] gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-[13px]">正在搜索真实推荐案例…</span>
          </div>
        ) : caseCards.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-[#64748B] gap-1">
            <span className="text-[13px]">暂无推荐案例</span>
            <span className="text-[11px]">发送一条消息即可开始对话</span>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
            {caseCards.map((card, i) => (
              <motion.button
                key={`${card.video_url}-${i}`}
                onClick={() => onCaseClick(card)}
                disabled={streaming}
                className="group text-left rounded-card overflow-hidden border border-[#1E293B] hover:border-[#6366F1]/30 hover:shadow-card-hover transition-all disabled:opacity-50"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 + i * 0.06, duration: 0.4 }}
                whileHover={{ y: -4 }}
              >
                <div className="relative aspect-video overflow-hidden bg-[#0D1321]">
                  {card.cover_url ? (
                    <img
                      src={card.cover_url}
                      alt={card.title}
                      loading="lazy"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Film className="w-6 h-6 text-[#334155]" />
                    </div>
                  )}
                  <div className="absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-black/40 backdrop-blur-sm border border-white/10">
                    <Film className="w-3 h-3 text-[#06B6D4]" />
                    <span className="text-[9px] font-medium text-white uppercase">视频</span>
                  </div>
                  <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded-md bg-black/40 backdrop-blur-sm border border-white/10">
                    <span className="text-[9px] font-medium text-white/90">♥ {formatLikes(card.likes)}</span>
                  </div>
                </div>
                <div className="p-3 bg-[#111827]">
                  <p className="text-body-sm text-[#F1F5F9] font-medium line-clamp-2 group-hover:text-[#6366F1] transition-colors">
                    {card.title}
                  </p>
                  <p className="mt-1 text-[11px] text-[#64748B] flex items-center gap-1">
                    <span className="truncate">{card.author}</span>
                    <ExternalLink className="w-3 h-3 shrink-0" />
                  </p>
                </div>
              </motion.button>
            ))}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}

export default React.memo(WelcomeState)
