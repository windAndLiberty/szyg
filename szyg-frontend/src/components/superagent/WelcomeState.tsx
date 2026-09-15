import React from 'react'
import { motion } from 'framer-motion'
import {
  Film,
  Loader2,
  ExternalLink,
  BrainCircuit,
  Target,
  UsersRound,
  BarChart3,
  Globe2,
} from 'lucide-react'
import type { CaseCard } from '@/types'
import { product } from '@/lib/product'

type WelcomeStateProps = {
  inputText: string
  setInputText: (v: string) => void
  composer: React.ReactNode
  onCaseClick: (card: CaseCard) => void
  streaming: boolean
  caseCards: CaseCard[]
  caseCardsLoading: boolean
  skillCount: number
  memoryEnabled: boolean
}

const skillShortcuts = [
  {
    label: '代办网页工作',
    prompt: '请告诉我你希望访问的网站和要完成的事情；需要登录、提交或外发时先让我确认。',
    icon: Globe2,
  },
  {
    label: '策划营销内容',
    prompt: '请结合我的企业资料，策划一套适合当前产品的营销内容，并说明推荐平台和执行步骤。',
    icon: Film,
  },
  {
    label: '发现潜在客户',
    prompt: '请结合我的产品与知识库，寻找高相关的潜在客户机会，并给出安全的触达建议。',
    icon: Target,
  },
  {
    label: '推进客户转化',
    prompt: '请分析当前高意向线索，生成个性化跟进建议和下一步行动。',
    icon: UsersRound,
  },
  {
    label: '复盘运营表现',
    prompt: '请汇总最近的内容、发布、获客和转化数据，找出最值得优先处理的问题。',
    icon: BarChart3,
  },
]

const formatLikes = (n: number) => (n >= 10000 ? `${(n / 10000).toFixed(1)}w` : `${n}`)
const sourceLabel: Record<string, string> = {
  bilibili: 'B站',
  douyin: '抖音',
  kuaishou: '快手',
}

const WelcomeState: React.FC<WelcomeStateProps> = ({
  inputText,
  setInputText,
  composer,
  onCaseClick,
  streaming,
  caseCards,
  caseCardsLoading,
  skillCount,
  memoryEnabled,
}) => {
  return (
    <motion.div
      className="flex-1 flex flex-col items-center justify-center px-6 py-10 overflow-y-auto"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* Brand block */}
      <motion.div
        className="flex flex-col items-center gap-4 mb-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        <div className="relative">
          <div
            className="absolute inset-0 rounded-2xl blur-2xl opacity-40"
            style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.6) 0%, transparent 70%)' }}
          />
          <div className="relative w-32 h-32 rounded-2xl overflow-hidden bg-[#0B1020]/70 p-2 shadow-glow-strong">
            <img src={product.logoUrl} alt="超级员工" className="w-full h-full object-contain" />
          </div>
        </div>
        <div className="text-center">
          <p className="text-body-md text-[#94A3B8]">一个超级员工，按需组合内容、获客、转化与运营技能</p>
          <div className="mt-3 flex flex-wrap items-center justify-center gap-2 text-[11px] text-[#64748B]">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#334155] bg-[#111827]/70 px-2.5 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_rgba(16,185,129,0.7)]" />
              超级员工已就绪
            </span>
            {skillCount > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[#334155] bg-[#111827]/70 px-2.5 py-1">
                <BrainCircuit className="h-3 w-3 text-[#818CF8]" />
                {skillCount} 项可复用技能
              </span>
            )}
            {memoryEnabled && (
              <span className="rounded-full border border-[#334155] bg-[#111827]/70 px-2.5 py-1">长期记忆已开启</span>
            )}
          </div>
        </div>
      </motion.div>

      {/* Input box */}
      <motion.div
        className="w-full max-w-2xl mb-5"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        {composer}
      </motion.div>

      <motion.div
        className="mb-9 grid w-full max-w-2xl grid-cols-2 gap-2 md:grid-cols-5"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
      >
        {skillShortcuts.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.label}
              type="button"
              onClick={() => setInputText(item.prompt)}
              disabled={streaming}
              className="flex h-10 min-w-0 items-center justify-center gap-2 rounded-lg border border-[#1E293B] bg-[#111827]/60 px-3 text-xs text-[#94A3B8] transition-all hover:border-[#6366F1]/40 hover:bg-[#6366F1]/8 hover:text-[#E0E7FF] disabled:opacity-50"
            >
              <Icon className="h-3.5 w-3.5 shrink-0 text-[#818CF8]" />
              <span className="truncate">{item.label}</span>
            </button>
          )
        })}
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

        <div className="h-[132px] overflow-x-auto overflow-y-hidden">
          {caseCardsLoading ? (
            <div className="flex h-full items-center justify-center text-[#64748B] gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-[13px]">正在搜索真实推荐案例…</span>
            </div>
          ) : caseCards.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-[#64748B] gap-1">
              <span className="text-[13px]">暂无推荐案例</span>
              <span className="text-[11px]">发送一条消息即可开始对话</span>
            </div>
          ) : (
            <div className="grid h-full min-w-[720px] grid-cols-3 gap-4">
              {caseCards.slice(0, 3).map((card, i) => (
                <motion.div
                  key={`${card.video_url}-${i}`}
                  className="group relative h-full min-w-0 overflow-hidden rounded-card border border-[#1E293B] bg-[#111827] transition-all hover:border-[#6366F1]/30 hover:shadow-card-hover"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 + i * 0.06, duration: 0.4 }}
                  whileHover={{ y: -3 }}
                >
                  <button
                    type="button"
                    onClick={() => onCaseClick(card)}
                    disabled={streaming}
                    className="flex h-full w-full min-w-0 flex-col p-4 text-left disabled:opacity-50"
                  >
                    <div className="flex w-full items-center justify-between gap-2 text-[11px]">
                      <span className="inline-flex items-center gap-1.5 font-medium text-[#818CF8]">
                        <Film className="h-3.5 w-3.5" />
                        {sourceLabel[card.source] || '视频案例'}
                      </span>
                      <span className="shrink-0 text-[#64748B]">♥ {formatLikes(card.likes)}</span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-body-sm font-medium leading-6 text-[#F1F5F9] transition-colors group-hover:text-[#A5B4FC]">
                      {card.title}
                    </p>
                    <p className="mt-auto max-w-[calc(100%-28px)] truncate text-[11px] text-[#64748B]">
                      {card.author || '平台作者'}
                    </p>
                  </button>
                  {card.video_url && (
                    <a
                      href={card.video_url}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(event) => event.stopPropagation()}
                      className="absolute bottom-3 right-3 inline-flex h-7 w-7 items-center justify-center rounded-md text-[#64748B] transition-colors hover:bg-[#1E293B] hover:text-[#C7D2FE] focus:outline-none focus:ring-1 focus:ring-[#6366F1]/50"
                      aria-label={`打开${card.title}`}
                      title="打开原视频"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

export default React.memo(WelcomeState)
