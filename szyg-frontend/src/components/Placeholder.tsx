import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import { Sparkles, Construction } from 'lucide-react'

type PlaceholderProps = {
  title: string
  description: string
  icon: LucideIcon
  /** 后端模块标识，提示后续填充时对接的 API */
  module?: string
}

/**
 * 二级页面占位组件 — Phase 1 骨架阶段使用。
 * 遵循 DESIGN_SYSTEM.md 玻璃态卡片 + Framer Motion 入场动画。
 * 后续 Phase B 逐个替换为真实功能页面。
 */
export default function Placeholder({ title, description, icon: Icon, module }: PlaceholderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="flex flex-col items-center justify-center min-h-[60vh] px-6"
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
        className="relative mb-6"
      >
        <div
          className="absolute inset-0 rounded-2xl blur-2xl opacity-40"
          style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.5) 0%, transparent 70%)' }}
        />
        <div className="relative w-20 h-20 rounded-2xl bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center shadow-glow-strong">
          <Icon className="w-10 h-10 text-white" />
        </div>
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="text-display-md text-[#F1F5F9] mb-2"
      >
        {title}
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
        className="text-body-lg text-[#94A3B8] text-center max-w-md mb-8"
      >
        {description}
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.4 }}
        className="glass-card rounded-card-lg border border-[#1E293B] px-6 py-4 flex items-center gap-3"
        style={{ background: 'linear-gradient(135deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)' }}
      >
        <Construction className="w-5 h-5 text-[#F59E0B] shrink-0" />
        <div className="flex flex-col">
          <span className="text-body-md text-[#F1F5F9] font-medium">模块开发中</span>
          <span className="text-body-sm text-[#64748B]">
            {module ? `后端模块: ${module}` : '骨架阶段占位页面'}
          </span>
        </div>
        <Sparkles className="w-4 h-4 text-[#6366F1] ml-2" />
      </motion.div>
    </motion.div>
  )
}
