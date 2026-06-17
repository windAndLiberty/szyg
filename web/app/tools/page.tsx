'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { Search, Box, Cloud, Monitor, ArrowRight } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'

interface Tool {
  id: string
  title: string
  desc?: string
  icon?: string
  is_yun?: boolean
  version?: string
  category?: string
  windows_canshu?: string
}

export default function ToolsPage() {
  const router = useRouter()
  const [allTools, setAllTools] = useState<Tool[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')

  const filtered = allTools.filter(t => {
    if (category && t.category !== category) return false
    if (search) {
      const q = search.toLowerCase()
      return (t.title?.toLowerCase().includes(q) || t.desc?.toLowerCase().includes(q))
    }
    return true
  })

  useEffect(() => {
    Promise.all([
      api.get('/api/tools/catalog').catch(() => ({ data: [] })),
      api.get('/api/tools/categories').catch(() => ({ data: [] })),
    ]).then(([tRes, cRes]) => {
      setAllTools(tRes.data)
      setCategories(cRes.data)
    })
  }, [])

  function openTool(tool: Tool) {
    if (tool.windows_canshu) {
      try {
        const args = JSON.parse(`[${tool.windows_canshu}]`)
        router.push(args[0] || '/chat')
      } catch { router.push('/chat') }
    }
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6"
        >
          <h2 className="text-2xl font-bold text-white mb-2">🧰 工具市场</h2>
          <p className="text-white/40 text-sm">发现和管理你的 AI 工具</p>
        </motion.div>

        <div className="flex flex-wrap gap-3 mb-6">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <input
              type="text"
              placeholder="搜索工具..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 transition-all text-sm"
            />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 transition-all"
          >
            <option value="" className="bg-[var(--header-bg)]">全部分类</option>
            {categories.map(c => (
              <option key={c} value={c} className="bg-[var(--header-bg)]">{c}</option>
            ))}
          </select>
        </div>

        <motion.div
          initial="hidden"
          animate="show"
          variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } }}
          className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
        >
          {filtered.map((tool, i) => (
            <motion.div
              key={tool.id}
              variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
              whileHover={{ y: -6, scale: 1.02 }}
              onClick={() => openTool(tool)}
              className="glass-card p-5 cursor-pointer group relative overflow-hidden"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative z-10">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent/20 to-purple-500/20 flex items-center justify-center text-accent mb-4 group-hover:shadow-lg group-hover:shadow-accent/20 transition-shadow">
                  <Box className="w-7 h-7" />
                </div>
                <h4 className="text-white font-semibold mb-1">{tool.title}</h4>
                <p className="text-white/30 text-xs mb-4 line-clamp-2">{tool.desc}</p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full flex items-center gap-1 ${tool.is_yun ? 'bg-blue-500/10 text-blue-400' : 'bg-amber-500/10 text-amber-400'}`}>
                      {tool.is_yun ? <Cloud className="w-3 h-3" /> : <Monitor className="w-3 h-3" />}
                      {tool.is_yun ? '云端' : '本地'}
                    </span>
                    <span className="text-xs text-white/20">v{tool.version}</span>
                  </div>
                  <ArrowRight className="w-4 h-4 text-white/20 group-hover:text-accent group-hover:translate-x-1 transition-all" />
                </div>
              </div>
            </motion.div>
          ))}
        </motion.div>

        {filtered.length === 0 && (
          <div className="text-center py-20 text-white/20">
            <Box className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>没有找到匹配的工具</p>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
