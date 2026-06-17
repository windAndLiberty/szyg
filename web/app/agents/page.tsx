'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Star, MessageCircle, X, Bot, Building2, Target } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'

interface Agent {
  id: string
  name: string
  avatar?: string
  description?: string
  tier?: string
  category?: string
  tags?: string[]
  rating?: number
  usage_count?: number
  model_preference?: string
  temperature?: number
  system_prompt?: string
}

interface Tier {
  key: string
  label: string
}

const tierConfig: Record<string, { icon: React.ReactNode; color: string; border: string }> = {
  base: { icon: <Bot className="w-6 h-6" />, color: 'text-blue-400', border: 'border-t-blue-400' },
  domain: { icon: <Building2 className="w-6 h-6" />, color: 'text-emerald-400', border: 'border-t-emerald-400' },
  task: { icon: <Target className="w-6 h-6" />, color: 'text-amber-400', border: 'border-t-amber-400' },
}

const tierLabels: Record<string, string> = { base: '基础层', domain: '领域层', task: '任务层' }
const tierTypes: Record<string, string> = { base: 'bg-blue-500/10 text-blue-400', domain: 'bg-emerald-500/10 text-emerald-400', task: 'bg-amber-500/10 text-amber-400' }

export default function AgentsPage() {
  const router = useRouter()
  const [allAgents, setAllAgents] = useState<Agent[]>([])
  const [filtered, setFiltered] = useState<Agent[]>([])
  const [tiers, setTiers] = useState<Tier[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [activeTier, setActiveTier] = useState('')
  const [activeCat, setActiveCat] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<Agent | null>(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get('/api/agents/list').catch(() => ({ data: [] })),
      api.get('/api/agents/tiers').catch(() => ({ data: [] })),
      api.get('/api/agents/categories').catch(() => ({ data: [] })),
    ]).then(([aRes, tRes, cRes]) => {
      setAllAgents(aRes.data)
      setFiltered(aRes.data)
      setTiers(tRes.data)
      setCategories(cRes.data)
      setLoading(false)
    })
  }, [])

  useEffect(() => {
    let agents = [...allAgents]
    if (activeTier) agents = agents.filter(a => a.tier === activeTier)
    if (activeCat) agents = agents.filter(a => a.category === activeCat)
    if (search) {
      const q = search.toLowerCase()
      agents = agents.filter(a =>
        a.name?.toLowerCase().includes(q) ||
        a.description?.toLowerCase().includes(q) ||
        a.tags?.some(t => t.toLowerCase().includes(q))
      )
    }
    agents.sort((a, b) => (b.rating || 0) - (a.rating || 0))
    setFiltered(agents)
  }, [activeTier, activeCat, search, allAgents])

  function useAgent(agent: Agent) {
    setSelected(null)
    router.push(`/chat?agent=${agent.id}`)
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-8">
          <h2 className="text-3xl font-bold text-white mb-2">🤖 AI智能体广场</h2>
          <p className="text-white/40">系统提示词层级体系：基础层 → 领域层 → 任务层，按需选用AI专家</p>
        </motion.div>

        {/* Tier cards */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid md:grid-cols-3 gap-4 mb-6"
        >
          {tiers.map((t) => {
            const cfg = tierConfig[t.key] || tierConfig.base
            return (
              <motion.div
                key={t.key}
                whileHover={{ y: -4 }}
                onClick={() => setActiveTier(activeTier === t.key ? '' : t.key)}
                className={`glass-card p-5 cursor-pointer border-t-2 ${cfg.border} ${activeTier === t.key ? 'bg-white/[0.06] border-opacity-100' : ''}`}
              >
                <div className={`w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center ${cfg.color} mb-3`}>
                  {cfg.icon}
                </div>
                <div className="text-white font-semibold">{t.label.split('—')[0]}</div>
                <div className="text-xs text-white/40 mt-1">{t.label.split('—')[1] || ''}</div>
              </motion.div>
            )
          })}
        </motion.div>

        {/* Filters */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="flex flex-wrap items-center gap-3 mb-6">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <input
              type="text"
              placeholder="搜索智能体..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 transition-all text-sm"
            />
          </div>
          <select
            value={activeTier}
            onChange={(e) => setActiveTier(e.target.value)}
            className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 transition-all"
          >
            <option value="" className="bg-[var(--header-bg)]">全部层级</option>
            {tiers.map(t => (
              <option key={t.key} value={t.key} className="bg-[var(--header-bg)]">{t.label.split('—')[0]}</option>
            ))}
          </select>
          <select
            value={activeCat}
            onChange={(e) => setActiveCat(e.target.value)}
            className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 transition-all"
          >
            <option value="" className="bg-[var(--header-bg)]">全部分类</option>
            {categories.map(c => (
              <option key={c} value={c} className="bg-[var(--header-bg)]">{c}</option>
            ))}
          </select>
          <span className="text-xs text-white/20">共 {filtered.length} 个智能体</span>
        </motion.div>

        {/* Agent grid */}
        {loading ? (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="glass-card p-5 h-32 shimmer" />
            ))}
          </div>
        ) : (
          <motion.div
            initial="hidden"
            animate="show"
            variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } }}
            className="grid md:grid-cols-2 xl:grid-cols-3 gap-4"
          >
            {filtered.map((agent) => (
              <motion.div
                key={agent.id}
                variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
                whileHover={{ y: -4 }}
                onClick={() => setSelected(agent)}
                className="glass-card p-5 cursor-pointer flex gap-4 group"
              >
                <div className="text-5xl flex-shrink-0">{agent.avatar}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="text-white font-semibold truncate">{agent.name}</h4>
                    {agent.tier && (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full flex-shrink-0 ${tierTypes[agent.tier] || ''}`}>
                        {tierLabels[agent.tier] || agent.tier}
                      </span>
                    )}
                  </div>
                  <p className="text-white/30 text-xs line-clamp-2 mb-2">{agent.description}</p>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1 text-amber-400">
                      <Star className="w-3 h-3 fill-current" />
                      <span className="text-xs">{agent.rating || 0}</span>
                    </div>
                    <span className="text-xs text-white/20">{agent.usage_count} 次使用</span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {agent.tags?.slice(0, 3).map(t => (
                      <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/40">{t}</span>
                    ))}
                  </div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* Detail Dialog */}
        <AnimatePresence>
          {selected && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
              onClick={() => setSelected(null)}
            >
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.9, opacity: 0 }}
                onClick={(e) => e.stopPropagation()}
                className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-white/10 bg-[var(--header-bg)]/95 backdrop-blur-xl p-6 shadow-2xl"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="text-6xl">{selected.avatar}</div>
                  <button onClick={() => setSelected(null)} className="p-1 rounded-lg hover:bg-white/5 text-white/40 hover:text-white transition-colors">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <h3 className="text-xl font-bold text-white mb-4">{selected.name}</h3>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div className="p-3 rounded-xl bg-white/5">
                    <div className="text-xs text-white/30 mb-1">层级</div>
                    <div className="text-sm text-white">{tierLabels[selected.tier || ''] || selected.tier}</div>
                  </div>
                  <div className="p-3 rounded-xl bg-white/5">
                    <div className="text-xs text-white/30 mb-1">分类</div>
                    <div className="text-sm text-white">{selected.category}</div>
                  </div>
                  <div className="p-3 rounded-xl bg-white/5">
                    <div className="text-xs text-white/30 mb-1">推荐模型</div>
                    <div className="text-sm text-white">{selected.model_preference || '默认'}</div>
                  </div>
                  <div className="p-3 rounded-xl bg-white/5">
                    <div className="text-xs text-white/30 mb-1">温度</div>
                    <div className="text-sm text-white">{selected.temperature}</div>
                  </div>
                </div>
                <div className="mb-4">
                  <div className="text-xs text-white/30 mb-1">描述</div>
                  <p className="text-sm text-white/60">{selected.description}</p>
                </div>
                {selected.system_prompt && (
                  <div className="mb-6">
                    <div className="text-xs text-white/30 mb-2">📋 系统提示词</div>
                    <div className="p-4 rounded-xl bg-white/5 border border-white/5 text-sm text-white/60 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed">
                      {selected.system_prompt}
                    </div>
                  </div>
                )}
                <div className="flex justify-end">
                  <motion.button
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={() => useAgent(selected)}
                    className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white text-sm font-medium flex items-center gap-2 shadow-lg shadow-accent/25"
                  >
                    <MessageCircle className="w-4 h-4" />
                    使用此智能体 → 开始对话
                  </motion.button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  )
}
