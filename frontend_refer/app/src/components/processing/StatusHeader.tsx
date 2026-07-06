import React from 'react'
import { motion } from 'framer-motion'
// Icons used inline for completion state

type StatusHeaderProps = {
  statusText: string
  stepText: string
  progress: number
  isComplete: boolean
}

const StatusHeader: React.FC<StatusHeaderProps> = ({
  statusText,
  stepText,
  progress,
  isComplete,
}) => {
  return (
    <motion.div
      className="rounded-card p-6 border border-[#1E293B]"
      style={{
        background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)',
      }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
    >
      <div className="flex items-center gap-6">
        {/* Spinner */}
        <div className="relative w-12 h-12 shrink-0">
          {isComplete ? (
            <motion.div
              className="w-12 h-12 rounded-full bg-[#10B981]/15 flex items-center justify-center"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.4, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] }}
            >
              <svg className="w-6 h-6 text-[#10B981]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <motion.path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 13l4 4L19 7"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
                />
              </svg>
            </motion.div>
          ) : (
            <div className="w-12 h-12 relative">
              <motion.div
                className="absolute inset-0"
                animate={{ rotate: 360 }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
              >
                {[0, 120, 240].map((offset) => (
                  <div
                    key={offset}
                    className="absolute w-2 h-2 rounded-full bg-[#6366F1]"
                    style={{
                      top: '50%',
                      left: '50%',
                      transform: `rotate(${offset}deg) translateY(-18px) translate(-50%, -50%)`,
                      transformOrigin: '0 0',
                    }}
                  />
                ))}
              </motion.div>
            </div>
          )}
        </div>

        {/* Status text */}
        <div className="flex-1 min-w-0">
          <motion.p
            className="text-heading-sm text-[#F1F5F9]"
            key={statusText}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {statusText}
          </motion.p>
          <p className="text-body-md text-[#94A3B8] mt-0.5">{stepText}</p>
        </div>

        {/* Progress percentage */}
        <motion.div
          className="text-[36px] font-display font-bold text-[#6366F1] shrink-0 tabular-nums"
          key={progress}
          initial={{ scale: 1.2 }}
          animate={{ scale: 1 }}
          transition={{ duration: 0.2 }}
        >
          {progress}%
        </motion.div>
      </div>

      {/* Progress bar */}
      <div className="mt-4 h-1.5 rounded-full bg-[#0D1321] overflow-hidden relative">
        <div
          className="absolute inset-0 rounded-full opacity-20"
          style={{
            background: 'linear-gradient(90deg, #8B5CF6 0%, #3B82F6 25%, #06B6D4 50%, #F59E0B 75%, #10B981 100%)',
          }}
        />
        <motion.div
          className="h-full rounded-full relative"
          style={{
            background: 'linear-gradient(90deg, #8B5CF6 0%, #3B82F6 25%, #06B6D4 50%, #F59E0B 75%, #10B981 100%)',
            boxShadow: '0 0 12px rgba(99,102,241,0.4)',
          }}
          initial={{ width: '0%' }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
        />
      </div>
    </motion.div>
  )
}

export default React.memo(StatusHeader)
