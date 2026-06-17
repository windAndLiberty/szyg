'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles, Globe, MessageCircleHeart, BarChart3, Wrench,
  Bot, Clapperboard, FileImage, FileText, Send, MessageSquarePlus,
  Copy, TrendingUp, Tags, Camera, Users, UserCheck, Stethoscope,
  Eye, LayoutDashboard, Newspaper, Pencil, ImagePlus, ArrowLeftRight,
  ChevronDown, ChevronsUpDown, Compass,
} from 'lucide-react'
import { featureTree, findL1ByPath } from '@/lib/feature-tree'
import { cn } from '@/lib/utils'

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  Sparkles, Globe, MessageCircleHeart, BarChart3, Wrench,
  Bot, Clapperboard, FileImage, FileText, Send, MessageSquarePlus,
  Copy, TrendingUp, Tags, Camera, Users, UserCheck, Stethoscope,
  Eye, LayoutDashboard, Newspaper, Pencil, ImagePlus, ArrowLeftRight,
  Compass,
}

const l1Colors: Record<string, { bg: string; text: string; glow: string }> = {
  'ai-studio': { bg: 'from-violet-500/20 to-purple-500/20', text: 'text-violet-300', glow: 'shadow-violet-500/20' },
  'public-traffic': { bg: 'from-sky-500/20 to-blue-500/20', text: 'text-sky-300', glow: 'shadow-sky-500/20' },
  'private-domain': { bg: 'from-emerald-500/20 to-teal-500/20', text: 'text-emerald-300', glow: 'shadow-emerald-500/20' },
  'data-insight': { bg: 'from-amber-500/20 to-orange-500/20', text: 'text-amber-300', glow: 'shadow-amber-500/20' },
  'toolbox': { bg: 'from-slate-500/20 to-gray-500/20', text: 'text-slate-300', glow: 'shadow-slate-500/20' },
}

const automationBadge = {
  full: { label: '自动', color: 'bg-emerald-500/20 text-emerald-300' },
  semi: { label: '半自动', color: 'bg-amber-500/20 text-amber-300' },
  assist: { label: '辅助', color: 'bg-slate-500/20 text-slate-300' },
}

interface FeatureNavProps {
  mobile?: boolean
  onNavigate?: () => void
}

export default function FeatureNav({ mobile, onNavigate }: FeatureNavProps) {
  const pathname = usePathname()
  const activeL1 = findL1ByPath(pathname || '')
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    // 默认展开当前所在 L1
    if (activeL1) return { [activeL1.id]: true }
    return { 'ai-studio': true }
  })

  const toggle = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  return (
    <nav className={cn('space-y-1', mobile && 'px-2 py-2')}>
      {featureTree.map((l1) => {
        const isL1Active = activeL1?.id === l1.id
        const isExpanded = expanded[l1.id]
        const colors = l1Colors[l1.id] || l1Colors.toolbox
        const L1Icon = iconMap[l1.icon] || Wrench

        return (
          <div key={l1.id}>
            {/* L1 Header */}
            <button
              onClick={() => toggle(l1.id)}
              className={cn(
                'w-full flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                isL1Active
                  ? `bg-gradient-to-r ${colors.bg} ${colors.text} shadow-lg ${colors.glow}`
                  : 'text-white/50 hover:text-white/80 hover:bg-white/[0.03]'
              )}
            >
              <L1Icon className={cn('w-4 h-4 flex-shrink-0', isL1Active && colors.text)} />
              <span className="flex-1 text-left">{l1.label}</span>
              <ChevronDown
                className={cn(
                  'w-3.5 h-3.5 transition-transform duration-300',
                  isExpanded && 'rotate-180'
                )}
              />
            </button>

            {/* L2 Children */}
            <AnimatePresence initial={false}>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                  className="overflow-hidden"
                >
                  <div className="ml-2 mt-1 space-y-0.5 border-l border-white/5 pl-2">
                    {l1.children?.map((l2) => {
                      const isActive = pathname === l2.path
                      const L2Icon = iconMap[l2.icon] || Wrench
                      const auto = l2.automationLevel
                        ? automationBadge[l2.automationLevel]
                        : null

                      return (
                        <Link
                          key={l2.id}
                          href={l2.path || '#'}
                          onClick={onNavigate}
                          className={cn(
                            'group flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all duration-200',
                            isActive
                              ? 'bg-white/10 text-white shadow-sm'
                              : 'text-white/40 hover:text-white/70 hover:bg-white/[0.03]'
                          )}
                        >
                          <L2Icon className={cn('w-3.5 h-3.5 flex-shrink-0', isActive && 'text-accent')} />
                          <span className="flex-1 truncate">{l2.label}</span>

                          {l2.badge && (
                            <span
                              className={cn(
                                'text-[10px] px-1.5 py-0.5 rounded-full font-medium',
                                l2.badge === 'new' && 'bg-accent/20 text-accent',
                                l2.badge === 'hot' && 'bg-orange-500/20 text-orange-300',
                                l2.badge === 'beta' && 'bg-purple-500/20 text-purple-300'
                              )}
                            >
                              {l2.badge === 'new' ? '新' : l2.badge === 'hot' ? '热' : 'β'}
                            </span>
                          )}

                          {auto && !l2.badge && (
                            <span className={cn('text-[10px] px-1.5 py-0.5 rounded-full', auto.color)}>
                              {auto.label}
                            </span>
                          )}
                        </Link>
                      )
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )
      })}
    </nav>
  )
}
