'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import {
  Sparkles, Globe, MessageCircleHeart, BarChart3, Wrench,
  ArrowRight, Flame, Box,
} from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'
import { featureTree, findFeatureByPath } from '@/lib/feature-tree'

const l1Icons: Record<string, React.ReactNode> = {
  'ai-studio': <Sparkles className="w-5 h-5" />,
  'public-traffic': <Globe className="w-5 h-5" />,
  'private-domain': <MessageCircleHeart className="w-5 h-5" />,
  'data-insight': <BarChart3 className="w-5 h-5" />,
  'toolbox': <Wrench className="w-5 h-5" />,
}

const l1Colors: Record<string, string> = {
  'ai-studio': 'from-violet-500/20 to-purple-500/20',
  'public-traffic': 'from-sky-500/20 to-blue-500/20',
  'private-domain': 'from-emerald-500/20 to-teal-500/20',
  'data-insight': 'from-amber-500/20 to-orange-500/20',
  'toolbox': 'from-slate-500/20 to-gray-500/20',
}

interface Announcement {
  id: string
  title: string
  content: string
  level: string
}

export default function DashboardPage() {
  const router = useRouter()
  const [stats, setStats] = useState({ total: 0, installed: 0, agents: 0, commentTasks: 0 })
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [recentTasks, setRecentTasks] = useState<any[]>([])

  useEffect(() => {
    Promise.all([
      api.get('/api/tools/catalog').catch(() => ({ data: [] })),
      api.get('/api/tools/installed').catch(() => ({ data: [] })),
      api.get('/api/agents/list').catch(() => ({ data: [] })),
      api.get('/api/comment/tasks', { params: { limit: 5 } }).catch(() => ({ data: [] })),
      api.get('/api/announce/list').catch(() => ({ data: [] })),
    ]).then(([toolRes, installRes, agentRes, commentRes, announceRes]) => {
      setStats({
        total: toolRes.data.length,
        installed: installRes.data.length,
        agents: agentRes.data.length,
        commentTasks: commentRes.data.length,
      })
      setRecentTasks(commentRes.data.slice(0, 3))
      setAnnouncements(announceRes.data?.slice(0, 3) || [])
    })
  }, [])

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
        {/* Announcements */}
        {announcements.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-2"
          >
            {announcements.map((a) => (
              <div
                key={a.id}
                className="glass-card px-4 py-3 flex items-center gap-3 border-l-4 border-l-accent"
              >
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
                  <Flame className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <div className="text-sm font-medium text-white">{a.title}</div>
                  <div className="text-xs text-white/40">{a.content}</div>
                </div>
              </div>
            ))}
          </motion.div>
        )}

        {/* Quick Stats */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ staggerChildren: 0.1 }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        >
          <StatCard title="工具总数" value={stats.total} icon={<Box className="w-5 h-5" />} color="from-blue-500/20 to-cyan-500/20" />
          <StatCard title="已安装" value={stats.installed} icon={<Box className="w-5 h-5" />} color="from-emerald-500/20 to-teal-500/20" />
          <StatCard title="AI智能体" value={stats.agents} icon={<Sparkles className="w-5 h-5" />} color="from-purple-500/20 to-pink-500/20" />
          <StatCard title="评论任务" value={stats.commentTasks} icon={<MessageCircleHeart className="w-5 h-5" />} color="from-orange-500/20 to-amber-500/20" />
        </motion.div>

        {/* Feature Tree Quick Access */}
        <div className="space-y-4">
          <h2 className="text-white font-semibold flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" />
            功能导航
          </h2>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {featureTree.map((l1, i) => (
              <motion.div
                key={l1.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className="glass-card overflow-hidden"
              >
                <div className={cn('px-4 py-3 border-b border-white/5 bg-gradient-to-r', l1Colors[l1.id])}>
                  <div className="flex items-center gap-2">
                    <span className="text-white/80">{l1Icons[l1.id]}</span>
                    <span className="font-semibold text-white">{l1.label}</span>
                    <span className="text-xs text-white/40 ml-auto">{l1.children?.length} 功能</span>
                  </div>
                  <p className="text-xs text-white/40 mt-1">{l1.description}</p>
                </div>
                <div className="p-2 space-y-0.5">
                  {l1.children?.map((l2) => (
                    <button
                      key={l2.id}
                      onClick={() => l2.path && router.push(l2.path)}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-white/60 hover:text-white hover:bg-white/[0.03] transition-all text-left group"
                    >
                      <span className="flex-1">{l2.label}</span>
                      {l2.badge && (
                        <span className={cn(
                          'text-[10px] px-1.5 py-0.5 rounded-full font-medium',
                          l2.badge === 'new' && 'bg-accent/20 text-accent',
                          l2.badge === 'hot' && 'bg-orange-500/20 text-orange-300',
                          l2.badge === 'beta' && 'bg-purple-500/20 text-purple-300'
                        )}>
                          {l2.badge === 'new' ? '新' : l2.badge === 'hot' ? '热' : 'β'}
                        </span>
                      )}
                      <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity text-white/30" />
                    </button>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        {recentTasks.length > 0 && (
          <div className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-white font-semibold flex items-center gap-2">
                <MessageCircleHeart className="w-4 h-4 text-sky-400" />
                最近评论任务
              </h3>
              <button
                onClick={() => router.push('/public/smart-comment')}
                className="text-sm text-accent hover:text-accent-light flex items-center gap-1 transition-colors"
              >
                全部 <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="space-y-2">
              {recentTasks.map((task: any) => (
                <div
                  key={task.id}
                  onClick={() => router.push('/public/smart-comment')}
                  className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5 hover:border-white/10 transition-colors cursor-pointer"
                >
                  <div className={cn(
                    'w-2 h-2 rounded-full',
                    task.status === 'monitoring' ? 'bg-sky-400' :
                    task.status === 'paused' ? 'bg-red-400' :
                    task.status === 'executed' ? 'bg-emerald-400' : 'bg-amber-400'
                  )} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate">{task.name}</div>
                    <div className="text-xs text-white/30">{task.target_account}</div>
                  </div>
                  <div className="text-xs text-white/30">
                    成功 {task.total_executed} / 失败 {task.total_failed}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}

function StatCard({ title, value, icon, color }: { title: string; value: number; icon: React.ReactNode; color: string }) {
  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -2 }}
      className="glass-card p-4 relative overflow-hidden"
    >
      <div className={cn('absolute -right-4 -top-4 w-20 h-20 rounded-full bg-gradient-to-br blur-2xl opacity-50', color)} />
      <div className="relative z-10">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-white/10 to-white/5 flex items-center justify-center text-accent mb-2">
          {icon}
        </div>
        <div className="text-2xl font-bold text-white">{value}</div>
        <div className="text-xs text-white/40">{title}</div>
      </div>
    </motion.div>
  )
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(' ')
}
