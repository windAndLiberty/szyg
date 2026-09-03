import React from 'react'
import { motion } from 'framer-motion'
import {
  Search,
  FileText,
  TrendingUp,
  Users,
  Shield,
  Lightbulb,
  CheckCircle2,
} from 'lucide-react'
import type { AgentStatus } from '@/types'
import { cn } from '@/lib/utils'

const iconMap: Record<string, React.ElementType> = {
  Search,
  FileText,
  TrendingUp,
  Users,
  Shield,
  Lightbulb,
}

const statusColors: Record<AgentStatus, string> = {
  Waiting: '#64748B',
  Processing: '#6366F1',
  Complete: '#10B981',
  Error: '#EF4444',
}

const statusGlow: Record<AgentStatus, string> = {
  Waiting: '0 0 0px rgba(100,116,139,0)',
  Processing: '0 0 40px rgba(99,102,241,0.4)',
  Complete: '0 0 30px rgba(16,185,129,0.3)',
  Error: '0 0 30px rgba(239,68,68,0.3)',
}

type AgentNodeProps = {
  id: string
  name: string
  nameEn: string
  icon: string
  status: AgentStatus
  index: number
  isActive: boolean
}

const AgentNodeComponent: React.FC<AgentNodeProps> = ({
  name,
  nameEn,
  icon,
  status,
  index,
  isActive,
}) => {
  const Icon = iconMap[icon] || Search
  const color = statusColors[status]
  const glow = statusGlow[status]

  return (
    <motion.div
      className="flex flex-col items-center gap-3 relative"
      initial={{ opacity: 0, x: -30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{
        duration: 0.6,
        delay: 0.2 + index * 0.1,
        ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
      }}
    >
      {/* Agent number badge */}
      <div
        className={cn(
          'absolute -top-3 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium z-10',
          'border border-[#1E293B] bg-[#1A2235] text-[#64748B]'
        )}
      >
        {index + 1}
      </div>

      {/* Node circle container */}
      <div className="relative">
        {/* Pulsing rings for Processing state */}
        {status === 'Processing' && (
          <>
            <motion.div
              className="absolute inset-0 rounded-full border-[3px] border-[#6366F1]"
              initial={{ scale: 1, opacity: 0.6 }}
              animate={{ scale: 1.8, opacity: 0 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
              style={{ willChange: 'transform, opacity' }}
            />
            <motion.div
              className="absolute inset-0 rounded-full border-[3px] border-[#6366F1]"
              initial={{ scale: 1, opacity: 0.4 }}
              animate={{ scale: 1.8, opacity: 0 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut', delay: 0.5 }}
              style={{ willChange: 'transform, opacity' }}
            />
          </>
        )}

        {/* Main node circle */}
        <motion.div
          className="w-[100px] h-[100px] rounded-full flex items-center justify-center relative z-[1]"
          style={{
            border: `3px solid ${color}`,
            background: 'linear-gradient(180deg, rgba(26,34,53,0.9) 0%, rgba(17,24,39,0.95) 100%)',
            boxShadow: glow,
          }}
          animate={
            isActive
              ? { scale: [1, 1.08, 1] }
              : status === 'Complete'
                ? { scale: [1, 1.05, 1] }
                : { scale: 1 }
          }
          transition={
            isActive
              ? { duration: 1, repeat: Infinity, ease: 'easeInOut' }
              : status === 'Complete'
                ? { duration: 0.5, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] }
                : {}
          }
        >
          {/* Inner circle */}
          <div
            className="w-[84px] h-[84px] rounded-full flex items-center justify-center"
            style={{ background: '#1A2235' }}
          >
            {status === 'Complete' ? (
              <motion.div
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ duration: 0.4, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] }}
              >
                <CheckCircle2 className="w-8 h-8 text-[#10B981]" />
              </motion.div>
            ) : (
              <motion.div
                animate={
                  status === 'Processing'
                    ? { y: [0, -4, 0] }
                    : {}
                }
                transition={
                  status === 'Processing'
                    ? { duration: 1, repeat: Infinity, ease: 'easeInOut' }
                    : {}
                }
              >
                <Icon
                  className="w-8 h-8"
                  style={{ color }}
                />
              </motion.div>
            )}
          </div>
        </motion.div>
      </div>

      {/* Label */}
      <div className="text-center">
        <p className="text-body-sm text-[#94A3B8] font-medium leading-tight">{name}</p>
        <p className="text-[11px] text-[#64748B] leading-tight mt-0.5">{nameEn}</p>
      </div>
    </motion.div>
  )
}

export default React.memo(AgentNodeComponent)
