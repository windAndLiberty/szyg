'use client'

import { motion } from 'framer-motion'
import AppLayout from '@/components/AppLayout'
import {
  Sparkles, Globe, MessageCircleHeart, BarChart3, Wrench,
  Bot, Clapperboard, FileImage, FileText, Send, MessageSquarePlus,
  Copy, TrendingUp, Tags, Camera, Users, UserCheck, Stethoscope,
  Eye, LayoutDashboard, Newspaper, Pencil, ImagePlus, ArrowLeftRight,
} from 'lucide-react'
import { type FeatureNode } from '@/lib/feature-tree'

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  Sparkles, Globe, MessageCircleHeart, BarChart3, Wrench,
  Bot, Clapperboard, FileImage, FileText, Send, MessageSquarePlus,
  Copy, TrendingUp, Tags, Camera, Users, UserCheck, Stethoscope,
  Eye, LayoutDashboard, Newspaper, Pencil, ImagePlus, ArrowLeftRight,
}

const engineBadge: Record<string, { label: string; color: string }> = {
  'pipeline': { label: '流水线', color: 'bg-sky-500/20 text-sky-300 border-sky-500/30' },
  'state-machine': { label: '状态机', color: 'bg-purple-500/20 text-purple-300 border-purple-500/30' },
  'tool': { label: '工具', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
}

const autoBadge: Record<string, { label: string; color: string }> = {
  'full': { label: '全自动', color: 'bg-emerald-500/20 text-emerald-300' },
  'semi': { label: '半自动', color: 'bg-amber-500/20 text-amber-300' },
  'assist': { label: '辅助', color: 'bg-slate-500/20 text-slate-300' },
}

interface PlaceholderPageProps {
  feature: FeatureNode
}

export default function PlaceholderPage({ feature }: PlaceholderPageProps) {
  const Icon = iconMap[feature.icon] || Wrench
  const engine = feature.engine ? engineBadge[feature.engine] : null
  const auto = feature.automationLevel ? autoBadge[feature.automationLevel] : null

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6 flex items-center justify-center min-h-[60vh]">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
          className="glass-card p-8 md:p-12 text-center max-w-lg w-full"
        >
          {/* Icon */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
            className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-white/5 to-white/[0.02] border border-white/5 flex items-center justify-center"
          >
            <Icon className="w-8 h-8 text-white/20" />
          </motion.div>

          {/* Title + Description */}
          <h1 className="text-xl font-bold text-white mb-2">{feature.label}</h1>
          {feature.description && (
            <p className="text-sm text-white/40 mb-6 max-w-sm mx-auto leading-relaxed">
              {feature.description}
            </p>
          )}

          {/* Engine + Automation badges */}
          <div className="flex items-center justify-center gap-2 mb-6">
            {engine && (
              <span className={`text-xs px-3 py-1.5 rounded-full border ${engine.color}`}>
                ⚙ {engine.label}引擎
              </span>
            )}
            {auto && (
              <span className={`text-xs px-3 py-1.5 rounded-full ${auto.color}`}>
                {auto.label}
              </span>
            )}
          </div>

          {/* Coming Soon */}
          <div className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/[0.03] border border-white/5">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-sm text-white/30">功能开发中，敬请期待</span>
          </div>
        </motion.div>
      </div>
    </AppLayout>
  )
}
