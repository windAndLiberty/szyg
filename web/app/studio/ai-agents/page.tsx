'use client'

import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Bot, Sparkles, ArrowUpRight, Wrench, MessageSquare } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import { AI_AGENTS, AGENT_CATEGORIES, findAgentById } from '@/lib/ai-agents'
import { useAgentSessions } from '@/lib/use-agent-sessions'
import AgentChatView from '@/components/AgentChatView'

export default function AIAgentsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState('all')
  const [activeAgentId, setActiveAgentId] = useState<string | null>(null)
  const { getSession, send, newSession } = useAgentSessions()

  const filteredAgents = useMemo(() => {
    return AI_AGENTS.filter((agent) => {
      const matchCat = activeCategory === 'all' || agent.category === activeCategory
      const query = searchQuery.trim().toLowerCase()
      if (!query) return matchCat
      const matchName = agent.name.toLowerCase().includes(query)
      const matchDesc = agent.desc.toLowerCase().includes(query)
      return matchCat && (matchName || matchDesc)
    })
  }, [activeCategory, searchQuery])

  const openAgent = (id: string) => {
    setActiveAgentId(id)
  }

  const activeAgent = findAgentById(activeAgentId)
  if (activeAgent) {
    return (
      <AppLayout>
        <AgentChatView
          agent={activeAgent}
          session={getSession(activeAgent.id)}
          onSend={(text) => send(activeAgent, text)}
          onNewChat={() => newSession(activeAgent.id)}
          onBack={() => setActiveAgentId(null)}
        />
      </AppLayout>
    )
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
        {/* Hero */}
        <div className="relative rounded-2xl overflow-hidden glass-card p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 border border-white/5 bg-gradient-to-br from-white/[0.03] to-transparent">
          <div className="absolute right-0 top-0 w-80 h-80 bg-accent/10 blur-3xl rounded-full -mr-20 -mt-20 pointer-events-none" />
          <div className="space-y-2 relative z-10">
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2">
              <Bot className="w-7 h-7 text-accent" />
              AI 智能体
            </h1>
            <p className="text-sm text-white/50 max-w-xl">
              一批开箱即用的小型 AI 专家，覆盖写作、办公、营销与业务咨询场景。点选任一智能体即可开始对话，快速搞定临时、零散的工作任务。
            </p>
          </div>

          <div className="relative w-full md:w-80 flex-shrink-0 z-10">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-white/30" />
            <input
              type="text"
              placeholder="搜索智能体或场景..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-white/10 bg-white/[0.04] text-sm text-white placeholder:text-white/20 hover:border-white/25 focus:border-accent focus:bg-white/[0.06] focus:outline-none transition-all shadow-inner"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-white/30 hover:text-white/60 transition-colors"
              >
                清除
              </button>
            )}
          </div>
        </div>

        {/* Category Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-2 px-2 scrollbar-none">
          {AGENT_CATEGORIES.map((cat) => {
            const isActive = activeCategory === cat.id
            const count = cat.id === 'all'
              ? AI_AGENTS.length
              : AI_AGENTS.filter(a => a.category === cat.id).length
            return (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 whitespace-nowrap flex-shrink-0 ${
                  isActive
                    ? 'bg-accent text-white shadow-lg shadow-accent/20'
                    : 'text-white/40 hover:text-white/70 hover:bg-white/[0.03]'
                }`}
              >
                <span>{cat.label}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  isActive ? 'bg-white/20 text-white' : 'bg-white/5 text-white/30'
                }`}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>

        {/* Agents Grid */}
        <AnimatePresence mode="popLayout">
          {filteredAgents.length > 0 ? (
            <motion.div
              layout
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
            >
              {filteredAgents.map((agent) => {
                const sess = getSession(agent.id)
                const active = sess.streaming || sess.messages.length > 0
                return (
                <motion.div
                  key={agent.id}
                  layout
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.25 }}
                  whileHover={{ y: -4, transition: { duration: 0.15 } }}
                  className="group relative flex flex-col justify-between p-5 rounded-2xl border border-white/5 bg-gradient-to-b from-white/[0.03] to-white/[0.01] hover:border-white/10 hover:from-white/[0.05] hover:to-white/[0.02] shadow-sm transition-all duration-200 cursor-pointer overflow-hidden"
                  onClick={() => openAgent(agent.id)}
                >
                  {agent.isHot && (
                    <div className="absolute top-0 right-0 w-16 h-16 bg-accent/5 blur-xl rounded-full group-hover:bg-accent/10 transition-colors pointer-events-none" />
                  )}

                  <div className="space-y-3.5">
                    <div className="flex items-center justify-between">
                      <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${agent.color} flex items-center justify-center font-bold text-white text-lg shadow-md`}>
                        {agent.letter}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {sess.streaming && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> 对话中
                          </span>
                        )}
                        {agent.isHot && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            HOT
                          </span>
                        )}
                        {agent.useTools && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-sky-500/10 text-sky-400 border border-sky-500/20 flex items-center gap-0.5">
                            <Wrench className="w-2.5 h-2.5" /> 工具
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="space-y-1">
                      <h3 className="text-base font-bold text-white group-hover:text-accent transition-colors flex items-center gap-1">
                        {agent.name}
                        <ArrowUpRight className="w-3.5 h-3.5 opacity-0 -translate-y-0.5 group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:translate-y-0 transition-all text-accent" />
                      </h3>
                      <p className="text-xs text-white/40 leading-relaxed line-clamp-3">
                        {agent.desc}
                      </p>
                    </div>
                  </div>

                  <div className="pt-4 mt-4 border-t border-white/5 flex items-center justify-between">
                    {agent.needsApi ? (
                      <span className="text-[10px] text-amber-400/60">需配置数据源</span>
                    ) : (
                      <span className="text-[10px] text-white/20">开箱即用</span>
                    )}
                    <span className="text-[11px] text-white/20 group-hover:text-accent font-medium flex items-center gap-1 transition-colors">
                      <MessageSquare className="w-3 h-3" />
                      {active ? '继续对话' : '开始对话'}
                    </span>
                  </div>
                </motion.div>
                )
              })}
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="glass-card p-12 text-center max-w-sm mx-auto"
            >
              <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center text-white/20 mx-auto mb-4">
                <Sparkles className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">未找到匹配的智能体</h3>
              <p className="text-xs text-white/30 leading-relaxed">
                试试搜索其他关键词，或在上方切换不同分类
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  )
}
