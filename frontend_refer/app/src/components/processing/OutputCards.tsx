import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, ArrowRightLeft, TrendingUp, Users, Shield, Lightbulb, Sparkles } from 'lucide-react'
import type { OutputData } from './usePipelineSimulation'

const categoryColors: Record<string, { bg: string; text: string }> = {
  company: { bg: 'rgba(139,92,246,0.15)', text: '#8B5CF6' },
  person: { bg: 'rgba(59,130,246,0.15)', text: '#3B82F6' },
  budget: { bg: 'rgba(16,185,129,0.15)', text: '#10B981' },
  pain: { bg: 'rgba(239,68,68,0.15)', text: '#EF4444' },
  competitor: { bg: 'rgba(245,158,11,0.15)', text: '#F59E0B' },
  timeline: { bg: 'rgba(6,182,212,0.15)', text: '#06B6D4' },
}

type OutputCardsProps = {
  data: OutputData
  hasInfoExtract: boolean
  hasDealCard: boolean
  hasProfileUpdates: boolean
  hasCompAnalysis: boolean
  hasStrategy: boolean
  isComplete: boolean
}

// ---------- Extracted Info Card ----------
const InfoCard: React.FC<{ data: OutputData; show: boolean }> = React.memo(({ data, show }) => (
  <AnimatePresence>
    {show && (
      <motion.div
        className="rounded-card p-5 border border-[#1E293B] flex-1 min-w-0"
        style={{
          background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)',
        }}
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-[rgba(99,102,241,0.1)] flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-[#6366F1]" />
          </div>
          <h3 className="text-heading-sm text-[#F1F5F9]">Key Information</h3>
          <span className="text-[11px] text-[#64748B] ml-auto">{data.extractedFields.length} items</span>
        </div>

        <div className="flex flex-wrap gap-2">
          <AnimatePresence>
            {data.extractedFields.map((field, i) => {
              const colors = categoryColors[field.category] || categoryColors.company
              return (
                <motion.span
                  key={`${field.label}-${field.value}`}
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-body-sm font-medium"
                  style={{
                    background: colors.bg,
                    color: colors.text,
                  }}
                  initial={{ opacity: 0, scale: 0.5, y: 10 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  transition={{
                    delay: i * 0.08,
                    duration: 0.4,
                    ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
                  }}
                >
                  {field.value}
                </motion.span>
              )
            })}
          </AnimatePresence>

          {data.extractedFields.length === 0 && (
            <div className="w-full h-20 rounded-lg bg-[#0D1321]/50 border border-dashed border-[#1E293B] flex items-center justify-center">
              <span className="text-body-sm text-[#64748B]">Waiting for extraction...</span>
            </div>
          )}
        </div>
      </motion.div>
    )}
  </AnimatePresence>
))
InfoCard.displayName = 'InfoCard'

// ---------- Deal Card ----------
const DealCard: React.FC<{ data: OutputData; show: boolean }> = React.memo(({ data, show }) => (
  <AnimatePresence>
    {show && (
      <motion.div
        className="rounded-card p-5 border border-[#1E293B] flex-1 min-w-0"
        style={{
          background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)',
          borderLeft: '4px solid #06B6D4',
        }}
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-[rgba(6,182,212,0.1)] flex items-center justify-center">
            <TrendingUp className="w-3.5 h-3.5 text-[#06B6D4]" />
          </div>
          <h3 className="text-heading-sm text-[#F1F5F9]">Deal Preview</h3>
        </div>

        {data.dealAmount > 0 ? (
          <div className="space-y-3">
            <p className="text-body-md text-[#94A3B8]">Acme Corp</p>

            <motion.p
              className="text-[32px] font-display font-bold text-[#10B981] leading-none"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              {'\u00A5'}{data.dealAmount.toLocaleString()}
            </motion.p>

            <div className="flex items-center gap-3">
              <span
                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-label"
                style={{
                  background: 'rgba(6,182,212,0.15)',
                  color: '#06B6D4',
                }}
              >
                {data.dealStage}
              </span>
            </div>

            {/* Win rate circular progress */}
            <div className="flex items-center gap-3 pt-1">
              <div className="relative w-12 h-12">
                <svg className="w-12 h-12 -rotate-90" viewBox="0 0 48 48">
                  <circle cx="24" cy="24" r="20" fill="none" stroke="#1E293B" strokeWidth="4" />
                  <motion.circle
                    cx="24"
                    cy="24"
                    r="20"
                    fill="none"
                    stroke="#6366F1"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 20}`}
                    initial={{ strokeDashoffset: 2 * Math.PI * 20 }}
                    animate={{ strokeDashoffset: 2 * Math.PI * 20 * (1 - data.winRate / 100) }}
                    transition={{ duration: 1, delay: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-[11px] font-medium text-[#F1F5F9]">
                  {data.winRate}%
                </span>
              </div>
              <div>
                <p className="text-body-sm text-[#94A3B8]">Win Rate</p>
                <p className="text-body-sm text-[#64748B]">Exp. close: Sep 30, 2026</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="w-full h-32 rounded-lg bg-[#0D1321]/50 border border-dashed border-[#1E293B] flex items-center justify-center">
            <span className="text-body-sm text-[#64748B]">Waiting for deal rating...</span>
          </div>
        )}
      </motion.div>
    )}
  </AnimatePresence>
))
DealCard.displayName = 'DealCard'

// ---------- Profile Updates Card ----------
const ProfileCard: React.FC<{ data: OutputData; show: boolean }> = React.memo(({ data, show }) => (
  <AnimatePresence>
    {show && (
      <motion.div
        className="rounded-card p-5 border border-[#1E293B] flex-1 min-w-0"
        style={{
          background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)',
        }}
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-[rgba(59,130,246,0.1)] flex items-center justify-center">
            <Users className="w-3.5 h-3.5 text-[#3B82F6]" />
          </div>
          <h3 className="text-heading-sm text-[#F1F5F9]">Profile Updates</h3>
        </div>

        {data.profileUpdates.length > 0 ? (
          <div className="space-y-2.5">
            <AnimatePresence>
              {data.profileUpdates.map((update, i) => (
                <motion.div
                  key={`${update.field}-${i}`}
                  className="flex items-start gap-2.5 p-2.5 rounded-lg bg-[#0D1321]/60"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{
                    delay: i * 0.1,
                    duration: 0.4,
                    ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
                  }}
                >
                  {update.type === 'added' ? (
                    <Plus className="w-4 h-4 text-[#10B981] shrink-0 mt-0.5" />
                  ) : (
                    <ArrowRightLeft className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
                  )}
                  <div className="min-w-0">
                    <p className="text-body-sm text-[#94A3B8]">
                      {update.type === 'added' ? 'Added' : 'Updated'}: {update.field}
                    </p>
                    <p className="text-body-sm text-[#F1F5F9] font-medium">
                      {update.type === 'updated' && update.oldValue ? (
                        <>
                          <span className="text-[#64748B] line-through">{update.oldValue}</span>
                          {' '}
                          <ArrowRightLeft className="w-3 h-3 inline text-[#F59E0B]" />
                          {' '}
                          <span className="text-[#10B981]">{update.value}</span>
                        </>
                      ) : (
                        update.value
                      )}
                    </p>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        ) : (
          <div className="w-full h-20 rounded-lg bg-[#0D1321]/50 border border-dashed border-[#1E293B] flex items-center justify-center">
            <span className="text-body-sm text-[#64748B]">Waiting for profile update...</span>
          </div>
        )}
      </motion.div>
    )}
  </AnimatePresence>
))
ProfileCard.displayName = 'ProfileCard'

// ---------- Competitive Analysis Card ----------
const CompAnalysisCard: React.FC<{ data: OutputData; show: boolean }> = React.memo(({ data, show }) => (
  <AnimatePresence>
    {show && (
      <motion.div
        className="rounded-card p-5 border border-[#1E293B] flex-1 min-w-0"
        style={{
          background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)',
        }}
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-[rgba(245,158,11,0.1)] flex items-center justify-center">
            <Shield className="w-3.5 h-3.5 text-[#F59E0B]" />
          </div>
          <h3 className="text-heading-sm text-[#F1F5F9]">Competitive Analysis</h3>
        </div>

        {data.compDimensions.length > 0 ? (
          <div className="space-y-3">
            {data.compDimensions.map((dim, i) => (
              <div key={dim.name}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-body-sm text-[#94A3B8]">{dim.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-[#6366F1] w-6 shrink-0 text-right">Us</span>
                  <div className="flex-1 h-2 bg-[#0D1321] rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-[#6366F1] to-[#8B5CF6]"
                      initial={{ width: 0 }}
                      animate={{ width: `${dim.ourScore}%` }}
                      transition={{
                        delay: i * 0.15,
                        duration: 0.8,
                        ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
                      }}
                    />
                  </div>
                  <span className="text-[10px] text-[#F1F5F9] w-7 shrink-0">{dim.ourScore}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] text-[#EF4444] w-6 shrink-0 text-right">CX</span>
                  <div className="flex-1 h-2 bg-[#0D1321] rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-[#EF4444] to-[#F87171]"
                      initial={{ width: 0 }}
                      animate={{ width: `${dim.compScore}%` }}
                      transition={{
                        delay: i * 0.15 + 0.1,
                        duration: 0.8,
                        ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
                      }}
                    />
                  </div>
                  <span className="text-[10px] text-[#F1F5F9] w-7 shrink-0">{dim.compScore}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="w-full h-20 rounded-lg bg-[#0D1321]/50 border border-dashed border-[#1E293B] flex items-center justify-center">
            <span className="text-body-sm text-[#64748B]">Waiting for analysis...</span>
          </div>
        )}
      </motion.div>
    )}
  </AnimatePresence>
))
CompAnalysisCard.displayName = 'CompAnalysisCard'

// ---------- Strategy Card ----------
const StrategyCard: React.FC<{ data: OutputData; show: boolean }> = React.memo(({ data, show }) => (
  <AnimatePresence>
    {show && (
      <motion.div
        className="rounded-card p-5 border border-[#1E293B] flex-1 min-w-0"
        style={{
          background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)',
        }}
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      >
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-[rgba(16,185,129,0.1)] flex items-center justify-center">
            <Lightbulb className="w-3.5 h-3.5 text-[#10B981]" />
          </div>
          <h3 className="text-heading-sm text-[#F1F5F9]">Follow-up Strategy</h3>
        </div>

        {data.strategyActions.length > 0 ? (
          <div className="space-y-3">
            {data.strategyText && (
              <motion.p
                className="text-body-md text-[#94A3B8] leading-relaxed"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
              >
                {data.strategyText}
              </motion.p>
            )}

            <div className="space-y-2 pt-2">
              {data.strategyActions.map((action, i) => {
                const priorityColors = {
                  high: { bg: 'rgba(239,68,68,0.12)', text: '#EF4444', label: 'High' },
                  medium: { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B', label: 'Med' },
                  low: { bg: 'rgba(16,185,129,0.12)', text: '#10B981', label: 'Low' },
                }
                const colors = priorityColors[action.priority]
                return (
                  <motion.div
                    key={i}
                    className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#0D1321]/60"
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{
                      delay: 0.3 + i * 0.1,
                      duration: 0.3,
                      ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
                    }}
                  >
                    <span
                      className="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0"
                      style={{ background: colors.bg, color: colors.text }}
                    >
                      {colors.label}
                    </span>
                    <span className="text-body-sm text-[#F1F5F9]">{action.text}</span>
                  </motion.div>
                )
              })}
            </div>
          </div>
        ) : (
          <div className="w-full h-20 rounded-lg bg-[#0D1321]/50 border border-dashed border-[#1E293B] flex items-center justify-center">
            <span className="text-body-sm text-[#64748B]">Waiting for strategy...</span>
          </div>
        )}
      </motion.div>
    )}
  </AnimatePresence>
))
StrategyCard.displayName = 'StrategyCard'

// ---------- Main OutputCards Component ----------
const OutputCards: React.FC<OutputCardsProps> = ({
  data,
  hasInfoExtract,
  hasDealCard,
  hasProfileUpdates,
  hasCompAnalysis,
  hasStrategy,
  isComplete,
}) => {
  return (
    <div className="space-y-4">
      {/* First row: Info + Deal + Profile */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <InfoCard data={data} show={hasInfoExtract} />
        <DealCard data={data} show={hasDealCard} />
        <ProfileCard data={data} show={hasProfileUpdates} />
      </div>

      {/* Second row: Comp Analysis + Strategy */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CompAnalysisCard data={data} show={hasCompAnalysis} />
        <StrategyCard data={data} show={hasStrategy || isComplete} />
      </div>
    </div>
  )
}

export default React.memo(OutputCards)
