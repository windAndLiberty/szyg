import React, { useMemo } from 'react'
import { motion } from 'framer-motion'
import type { AgentStatus } from '@/types'

// Node positions (percentage of container)
const nodePositions = [
  { x: 8, y: 50 },    // Agent 1
  { x: 24, y: 50 },   // Agent 2
  { x: 40, y: 50 },   // Agent 3
  { x: 56, y: 50 },   // Agent 4
  { x: 72, y: 50 },   // Agent 5
  { x: 88, y: 50 },   // Agent 6
]

// Connections between nodes: (from, to)
const connections: [number, number][] = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 5],
]

type PipelineConnectionsProps = {
  agentStatuses: AgentStatus[]
}

const DataParticle = React.memo(({ delay, pathLength }: { delay: number; pathLength: number }) => (
  <motion.circle
    r="4"
    fill="#6366F1"
    filter="url(#glow)"
    initial={{ offsetDistance: '0%', opacity: 0 }}
    animate={{ offsetDistance: '100%', opacity: [0, 1, 1, 0] }}
    transition={{
      duration: 2,
      delay,
      repeat: Infinity,
      ease: 'linear',
    }}
    style={{
      offsetPath: `path('${pathLength}')`,
      willChange: 'offset-distance, opacity',
    }}
  />
))
DataParticle.displayName = 'DataParticle'

const ConnectionPath = React.memo(({
  from,
  to,
  index,
  isActive,
  isComplete,
}: {
  from: { x: number; y: number }
  to: { x: number; y: number }
  index: number
  isActive: boolean
  isComplete: boolean
}) => {
  const pathD = useMemo(() => {
    const dx = to.x - from.x
    const controlY = from.y - 15
    return `M ${from.x} ${from.y} Q ${from.x + dx * 0.5} ${controlY} ${to.x} ${to.y}`
  }, [from, to])

  return (
    <g>
      {/* Background path (inactive) */}
      <path
        d={pathD}
        fill="none"
        stroke="#1E293B"
        strokeWidth={3}
        strokeLinecap="round"
      />

      {/* Active gradient path */}
      {(isActive || isComplete) && (
        <>
          <defs>
            <linearGradient
              id={`gradient-${index}`}
              x1="0%"
              y1="0%"
              x2="100%"
              y2="0%"
              gradientUnits="userSpaceOnUse"
            >
              <stop offset="0%" stopColor="#6366F1" />
              <stop offset="100%" stopColor="#8B5CF6" />
            </linearGradient>
          </defs>
          <motion.path
            d={pathD}
            fill="none"
            stroke={isComplete ? '#10B981' : `url(#gradient-${index})`}
            strokeWidth={3}
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{
              pathLength: { duration: 0.8, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
              opacity: { duration: 0.3 },
            }}
          />

          {/* Data particles for active connections */}
          {isActive && (
            <>
              {[0, 0.7, 1.4].map((delay, i) => (
                <motion.circle
                  key={i}
                  r="3.5"
                  fill="#6366F1"
                  filter="url(#glow)"
                >
                  <animateMotion
                    dur="2s"
                    begin={`${delay}s`}
                    repeatCount="indefinite"
                    path={pathD}
                  />
                  <animate
                    attributeName="opacity"
                    values="0;1;1;0"
                    dur="2s"
                    begin={`${delay}s`}
                    repeatCount="indefinite"
                  />
                </motion.circle>
              ))}
            </>
          )}
        </>
      )}
    </g>
  )
})
ConnectionPath.displayName = 'ConnectionPath'

const PipelineConnections: React.FC<PipelineConnectionsProps> = ({ agentStatuses }) => {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{ zIndex: 0 }}
    >
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {connections.map(([fromIdx, toIdx], i) => {
        const from = nodePositions[fromIdx]
        const to = nodePositions[toIdx]
        const isActive = agentStatuses[fromIdx] === 'Processing' || agentStatuses[toIdx] === 'Processing'
        const isComplete = agentStatuses[fromIdx] === 'Complete' && agentStatuses[toIdx] === 'Complete'

        return (
          <ConnectionPath
            key={i}
            from={from}
            to={to}
            index={i}
            isActive={isActive}
            isComplete={isComplete}
          />
        )
      })}
    </svg>
  )
}

export default React.memo(PipelineConnections)
