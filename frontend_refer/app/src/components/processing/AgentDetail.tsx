import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  FileText,
  TrendingUp,
  Users,
  Shield,
  Lightbulb,
  Check,
  Loader2,
} from 'lucide-react'
import type { AgentStatus } from '@/types'

const iconMap: Record<string, React.ElementType> = {
  Search,
  FileText,
  TrendingUp,
  Users,
  Shield,
  Lightbulb,
}

type AgentDetailProps = {
  agentId: string
  agentName: string
  icon: string
  status: AgentStatus
  progress: number
  isVisible: boolean
}

const AgentDetail: React.FC<AgentDetailProps> = ({
  agentName,
  icon,
  status,
  isVisible,
}) => {
  const Icon = iconMap[icon] || Search

  return (
    <AnimatePresence mode="wait">
      {isVisible && (
        <motion.div
          className="rounded-card p-5 border border-[#1E293B] max-w-lg mx-auto"
          style={{
            background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)',
          }}
          initial={{ opacity: 0, y: -15, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -10, scale: 0.95 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
        >
          <div className="flex items-center gap-4">
            {/* Spinning icon */}
            <div className="w-14 h-14 rounded-xl bg-[rgba(99,102,241,0.08)] border border-[#1E293B] flex items-center justify-center shrink-0">
              {status === 'Complete' ? (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ duration: 0.3, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] }}
                >
                  <Check className="w-6 h-6 text-[#10B981]" />
                </motion.div>
              ) : (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                >
                  <Icon className="w-6 h-6 text-[#6366F1]" />
                </motion.div>
              )}
            </div>

            <div className="flex-1 min-w-0">
              <h4 className="text-heading-sm text-[#F1F5F9]">{agentName}</h4>
              <p className="text-body-sm text-[#94A3B8] mt-0.5">
                {status === 'Processing' ? 'Processing...' : status === 'Complete' ? 'Complete' : 'Waiting'}
              </p>
            </div>

            {status === 'Processing' && (
              <Loader2 className="w-5 h-5 text-[#6366F1] animate-spin shrink-0" />
            )}
          </div>

          {/* Animated processing items */}
          {status === 'Processing' && (
            <motion.div
              className="mt-4 space-y-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="flex items-center gap-2"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.2, duration: 0.3 }}
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-[#6366F1] animate-pulse" />
                  <div className="h-3 rounded bg-[#1E293B] w-32 animate-pulse" />
                </motion.div>
              ))}
            </motion.div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default React.memo(AgentDetail)
