'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Search, ExternalLink, Flame, Sparkles, DollarSign } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'

interface Tool {
  id: string
  name: string
  desc?: string
  icon?: string
  url?: string
  category?: string
  tags?: string[]
  is_hot?: boolean
  is_new?: boolean
  is_free?: boolean
}

interface Category {
  key: string
  label: string
  count: number
}

export default function HubPage() {
  const [allTools, setAllTools] = useState<Tool[]>([])
  const [filtered, setFiltered] = useState<Tool[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [activeCat, setActiveCat] = useState('')
  const [search, setSearch] = useState('')
  const [hotOnly, setHotOnly] = useState(false)
  const [newOnly, setNewOnly] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get('/api/hub/list').catch(() => ({ data: [] })),
      api.get('/api/hub/categories').catch(() => ({ data: [] })),
    ]).then(([tRes, cRes]) => {
      setAllTools(tRes.data)
      setFiltered(tRes.data)
      setCategories(cRes.data)
      setLoading(false)
    })
  }, [])

  useEffect(() => {
    let tools = allTools
    if (activeCat) tools = tools.filter(t => t.category === activeCat)
    if (search) {
      const q = search.toLowerCase()
      tools = tools.filter(t => t.name?.toLowerCase().includes(q) || t.desc?.toLowerCase().includes(q))
    }
    if (hotOnly) tools = tools.filter(t => t.is_hot)
    if (newOnly) tools = tools.filter(t => t.is_new)
    setFiltered(tools)
  }, [activeCat, search, hotOnly, newOnly, allTools])

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-8">
          <h2 className="text-3xl font-bold text-white mb-2">🔗 AI工具聚合导航</h2>
          <p className="text-white/40">精选200+ AI工具，按分类浏览，快速找到你需要的AI能力</p>
        </motion.div>

        {/* Category tabs */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="flex flex-wrap justify-center gap-2 mb-6">
          <button
            onClick={() => setActiveCat('')}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${activeCat === '' ? 'bg-accent text-white shadow-lg shadow-accent/25' : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white'}`}
          >
            全部
          </button>
          {categories.map((cat) => (
            <button
              key={cat.key}
              onClick={() => setActiveCat(cat.key)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-1.5 ${activeCat === cat.key ? 'bg-accent text-white shadow-lg shadow-accent/25' : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white'}`}
            >
              {cat.label}
              <span className="text-xs opacity-60">{cat.count}</span>
            </button>
          ))}
        </motion.div>

        {/* Search & filters */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="flex flex-wrap items-center gap-3 mb-6">
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <input
              type="text"
              placeholder="搜索AI工具..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 transition-all text-sm"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-white/40 cursor-pointer select-none">
            <input type="checkbox" checked={hotOnly} onChange={(e) => setHotOnly(e.target.checked)} className="rounded border-white/20 bg-white/5 text-accent" />
            仅热门
          </label>
          <label className="flex items-center gap-2 text-sm text-white/40 cursor-pointer select-none">
            <input type="checkbox" checked={newOnly} onChange={(e) => setNewOnly(e.target.checked)} className="rounded border-white/20 bg-white/5 text-accent" />
            最新上线
          </label>
          <span className="text-xs text-white/20">共 {filtered.length} 个工具</span>
        </motion.div>

        {/* Grid */}
        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="glass-card p-5 h-40 shimmer" />
            ))}
          </div>
        ) : (
          <motion.div
            initial="hidden"
            animate="show"
            variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.04 } } }}
            className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
          >
            {filtered.map((tool) => (
              <motion.div
                key={tool.id}
                variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
                whileHover={{ y: -6, scale: 1.02 }}
                onClick={() => tool.url && window.open(tool.url, '_blank')}
                className="glass-card p-5 cursor-pointer group relative overflow-hidden"
              >
                <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <ExternalLink className="w-4 h-4 text-white/40" />
                </div>
                <div className="text-4xl text-center mb-3">{tool.icon}</div>
                <h4 className="text-white font-semibold text-center mb-2">{tool.name}</h4>
                <p className="text-white/30 text-xs text-center mb-4 line-clamp-2">{tool.desc}</p>
                <div className="flex flex-wrap gap-1.5 justify-center">
                  {tool.tags?.slice(0, 2).map((t) => (
                    <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/40">{t}</span>
                  ))}
                  {tool.is_hot && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 flex items-center gap-0.5">
                      <Flame className="w-3 h-3" />热门
                    </span>
                  )}
                  {tool.is_new && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center gap-0.5">
                      <Sparkles className="w-3 h-3" />新品
                    </span>
                  )}
                  {!tool.is_free && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 flex items-center gap-0.5">
                      <DollarSign className="w-3 h-3" />付费
                    </span>
                  )}
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}

        {filtered.length === 0 && !loading && (
          <div className="text-center py-20 text-white/20">
            <Search className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>没有找到匹配的工具</p>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
