import React from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

const funnelStages = [
  { name: 'Initial Contact', nameCn: '初次接触', color: '#8B5CF6', width: 100 },
  { name: 'Needs Confirmed', nameCn: '需求确认', color: '#3B82F6', width: 88 },
  { name: 'Solution Eval', nameCn: '方案评估', color: '#06B6D4', width: 76 },
  { name: 'Negotiation', nameCn: '商务谈判', color: '#F59E0B', width: 64 },
  { name: 'Won', nameCn: '赢单', color: '#10B981', width: 52 },
  { name: 'Lost', nameCn: '输单', color: '#EF4444', width: 52 },
]

type PipelineFunnelProps = {
  highlightStage?: number | null
  show: boolean
}

const PipelineFunnel: React.FC<PipelineFunnelProps> = ({ highlightStage, show }) => {
  if (!show) return null

  return (
    <motion.div
      className="rounded-card p-5 border border-[#1E293B]"
      style={{
        background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)',
      }}
      initial={{ opacity: 0, x: 30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
    >
      <h3 className="text-heading-sm text-[#F1F5F9] mb-4">Pipeline Funnel</h3>

      <div className="flex flex-col items-center gap-1.5">
        {funnelStages.map((stage, i) => {
          const isHighlighted = highlightStage === i
          const isWonLost = stage.name === 'Won' || stage.name === 'Lost'

          return (
            <motion.div
              key={stage.name}
              className={cn(
                'relative flex items-center justify-center rounded-lg transition-all duration-300',
                isWonLost && 'mt-1'
              )}
              style={{
                width: `${stage.width}%`,
                height: 36,
                background: isHighlighted
                  ? `linear-gradient(90deg, ${stage.color}30, ${stage.color}15)`
                  : 'rgba(13,19,33,0.6)',
                border: `1px solid ${isHighlighted ? stage.color + '60' : '#1E293B'}`,
              }}
              initial={{ opacity: 0, scaleX: 0 }}
              animate={{
                opacity: 1,
                scaleX: 1,
                boxShadow: isHighlighted ? `0 0 16px ${stage.color}30` : 'none',
              }}
              transition={{
                delay: i * 0.08,
                duration: 0.5,
                ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
              }}
            >
              {/* Stage color indicator */}
              <div
                className="absolute left-2 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full"
                style={{ background: stage.color }}
              />

              <span
                className={cn(
                  'text-body-sm font-medium',
                  isHighlighted ? 'text-[#F1F5F9]' : 'text-[#94A3B8]'
                )}
              >
                {stage.nameCn}
              </span>

              {/* Flying deal indicator */}
              {isHighlighted && (
                <motion.div
                  className="absolute -right-2 top-1/2 -translate-y-1/2"
                  initial={{ scale: 0, x: -20 }}
                  animate={{ scale: 1, x: 0 }}
                  transition={{
                    delay: 0.3,
                    duration: 0.5,
                    ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number],
                  }}
                >
                  <div
                    className="w-5 h-5 rounded-full flex items-center justify-center"
                    style={{ background: stage.color }}
                  >
                    <span className="text-[8px] text-white font-bold">¥</span>
                  </div>
                </motion.div>
              )}
            </motion.div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="mt-4 pt-3 border-t border-[#1E293B] grid grid-cols-2 gap-2">
        {funnelStages.slice(0, 4).map((stage) => (
          <div key={stage.name} className="flex items-center gap-1.5">
            <div
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: stage.color }}
            />
            <span className="text-[11px] text-[#64748B]">{stage.nameCn}</span>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

export default React.memo(PipelineFunnel)
