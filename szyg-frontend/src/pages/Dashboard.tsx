import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  Bot,
  MessageSquare,
  TrendingUp,
  Clock,
  Zap,
  FileText,
  AlertTriangle,
  Settings,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import {
  useDigitalHumans,
  useDashboardTasks,
  useActivities,
  useInteractionTrend,
  useDistribution,
} from '@/lib/hooks'
import { getStatusColor, getStatusLabel } from '@/lib/format'
import type { DigitalHuman, ActivityItem, TaskQueueItem } from '@/types'
// ─── Animation Variants ─────────────────────────────────────────────
const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1, ease: 'easeOut' as const } },
}
const cardVariants = {
  hidden: { opacity: 0, x: -30, y: 20 },
  visible: { opacity: 1, x: 0, y: 0, transition: { duration: 0.6, ease: 'easeOut' as const } },
}

// ─── KPI Card Component ─────────────────────────────────────────────
interface KPICardProps {
  label: string
  value: string | number
  trend: string
  trendUp: boolean
  subtitle: string
  icon: React.ReactNode
  index: number
}

function KPICard({ label, value, trend, trendUp, subtitle, icon, index }: KPICardProps) {
  return (
    <motion.div
      variants={cardVariants}
      custom={index}
      className="relative overflow-hidden rounded-xl p-5"
      style={{ background: 'linear-gradient(135deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)', border: '1px solid #1E293B' }}
    >
      <div className="flex items-start justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: '#94A3B8' }}>{label}</span>
        <div className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ background: 'rgba(99,102,241,0.15)' }}>{icon}</div>
      </div>
      <div className="mt-3 flex items-end gap-3">
        <span className="text-[42px] font-bold leading-none" style={{ color: '#F1F5F9' }}>{value}</span>
        <div className="mb-1.5 flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium" style={{ background: trendUp ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)', color: trendUp ? '#10B981' : '#EF4444' }}>
          {trendUp ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
          {trend}
        </div>
      </div>
      <p className="mt-2 text-sm" style={{ color: '#64748B' }}>{subtitle}</p>
    </motion.div>
  )
}

// ─── Activity / Task helper maps ────────────────────────────────────
const activityIconMap: Record<string, { icon: React.ReactNode; bg: string; color: string }> = {
  agent_deployed: { icon: <Zap className="h-4 w-4" />, bg: 'rgba(99,102,241,0.15)', color: '#6366F1' },
  interaction: { icon: <MessageSquare className="h-4 w-4" />, bg: 'rgba(6,182,212,0.15)', color: '#06B6D4' },
  report_generated: { icon: <FileText className="h-4 w-4" />, bg: 'rgba(16,185,129,0.15)', color: '#10B981' },
  alert: { icon: <AlertTriangle className="h-4 w-4" />, bg: 'rgba(239,68,68,0.15)', color: '#EF4444' },
  agent_created: { icon: <Bot className="h-4 w-4" />, bg: 'rgba(139,92,246,0.15)', color: '#8B5CF6' },
  system: { icon: <Settings className="h-4 w-4" />, bg: 'rgba(100,116,139,0.15)', color: '#64748B' },
}

function getTaskTypeLabel(type: string): string {
  const map: Record<string, string> = { content: '内容', acquisition: '获客', conversion: '转化', dispatch: '调度', 任务: '任务' }
  return map[type] || type
}

function PriorityBadge({ priority }: { priority: string }) {
  const cfg: Record<string, { color: string; bg: string }> = {
    high: { color: '#EF4444', bg: 'rgba(239,68,68,0.15)' },
    medium: { color: '#F59E0B', bg: 'rgba(245,158,11,0.15)' },
    low: { color: '#64748B', bg: 'rgba(100,116,139,0.15)' },
  }
  const c = cfg[priority] || cfg.medium
  return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded" style={{ color: c.color, background: c.bg }}>{priority === 'high' ? '高' : priority === 'medium' ? '中' : '低'}</span>
}

function TaskStatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { color: string; bg: string; label: string }> = {
    completed: { color: '#10B981', bg: 'rgba(16,185,129,0.15)', label: '已完成' },
    running: { color: '#6366F1', bg: 'rgba(99,102,241,0.15)', label: '运行中' },
    pending: { color: '#F59E0B', bg: 'rgba(245,158,11,0.15)', label: '等待中' },
    failed: { color: '#EF4444', bg: 'rgba(239,68,68,0.15)', label: '失败' },
  }
  const c = cfg[status] || cfg.pending
  return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded" style={{ color: c.color, background: c.bg }}>{c.label}</span>
}

// === MAIN COMPONENT MARKER ===
export default function Dashboard() {
  const [timeRange, setTimeRange] = useState<'7D' | '30D' | '90D'>('7D')

  const { data: dhData } = useDigitalHumans()
  const { data: taskData } = useDashboardTasks()
  const { data: actData } = useActivities()
  const { data: trendData } = useInteractionTrend(timeRange)
  const { data: distData } = useDistribution()
  const digitalHumans = dhData?.digitalHumans ?? []
  const taskQueue = taskData?.tasks ?? []
  const activities = actData?.activities ?? []
  const chartData = trendData?.chartData ?? []
  const distributionData = distData?.distribution ?? []

  const kpiData = useMemo(() => {
    const totalAgents = digitalHumans.length
    const today = new Date(new Date().setHours(0, 0, 0, 0))
    const todayInteractions = digitalHumans.reduce((sum, dh) => {
      const lastActive = new Date(dh.lastActive)
      if (!Number.isNaN(lastActive.getTime()) && lastActive >= today) return sum + dh.interactions
      return sum
    }, 0)
    const avgSuccessRate = digitalHumans.length
      ? Number((digitalHumans.reduce((sum, dh) => sum + dh.successRate, 0) / digitalHumans.length).toFixed(1))
      : 0
    const queueLength = taskQueue.filter((t) => t.status !== 'completed').length
    const runningCount = digitalHumans.filter((d) => d.status === 'active' || d.status === 'training').length
    const highPriority = taskQueue.filter((t) => t.priority === 'high' && t.status !== 'completed').length

    return [
      { label: '数字员工总数', value: totalAgents, trend: `${runningCount} 运行中`, trendUp: runningCount > 0, subtitle: '实时在线员工', icon: <Bot className="h-4 w-4" style={{ color: '#6366F1' }} /> },
      { label: '今日交互次数', value: todayInteractions.toLocaleString(), trend: todayInteractions > 0 ? '今日' : '0', trendUp: todayInteractions > 0, subtitle: '当日累计任务处理', icon: <MessageSquare className="h-4 w-4" style={{ color: '#6366F1' }} /> },
      { label: '平均成功率', value: `${avgSuccessRate}%`, trend: avgSuccessRate >= 50 ? '健康' : '待提升', trendUp: avgSuccessRate >= 50, subtitle: '基于真实任务完成度', icon: <TrendingUp className="h-4 w-4" style={{ color: '#6366F1' }} /> },
      { label: '任务队列', value: queueLength, trend: `${highPriority} 高优`, trendUp: false, subtitle: '待处理任务数', icon: <Clock className="h-4 w-4" style={{ color: '#6366F1' }} /> },
    ]
  }, [digitalHumans, taskQueue])

  const filteredChartData = useMemo(() => chartData, [chartData])

  // === RENDER MARKER ===
  return (
    <motion.div variants={containerVariants} initial="hidden" animate="visible" className="space-y-6">
      <motion.div variants={cardVariants}>
        <h1 className="text-display-md font-display text-[#F1F5F9] mb-2">运营仪表盘</h1>
        <p className="text-body-lg text-[#94A3B8]">实时掌握数字员工运营状态与业务指标</p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {kpiData.map((kpi, i) => <KPICard key={kpi.label} {...kpi} index={i} />)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <motion.div variants={cardVariants} className="lg:col-span-2 rounded-xl p-5" style={{ background: 'linear-gradient(135deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)', border: '1px solid #1E293B' }}>
          <div className="flex items-center justify-between mb-4">
            <div><h2 className="text-base font-semibold" style={{ color: '#F1F5F9' }}>交互趋势</h2><p className="mt-0.5 text-xs" style={{ color: '#64748B' }}>基于真实对话与任务数据</p></div>
            <div className="flex items-center gap-1 p-1 bg-[#0D1321] rounded-lg border border-[#1E293B]">
              {(['7D', '30D', '90D'] as const).map((r) => (
                <button key={r} onClick={() => setTimeRange(r)} className={cn('px-2.5 py-1 rounded text-xs font-medium transition-all', timeRange === r ? 'bg-[#1A2235] text-[#F1F5F9] border border-[#334155]' : 'text-[#64748B] hover:text-[#94A3B8]')}>{r}</button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={filteredChartData}>
              <defs>
                <linearGradient id="colorInteractions" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#6366F1" stopOpacity={0.4} /><stop offset="95%" stopColor="#6366F1" stopOpacity={0} /></linearGradient>
                <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#10B981" stopOpacity={0.3} /><stop offset="95%" stopColor="#10B981" stopOpacity={0} /></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
              <XAxis dataKey="date" stroke="#64748B" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#64748B" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: '#0D1321', border: '1px solid #1E293B', borderRadius: 8, fontSize: 12 }} labelStyle={{ color: '#94A3B8' }} />
              <Area type="monotone" dataKey="interactions" stroke="#6366F1" strokeWidth={2} fill="url(#colorInteractions)" name="交互数" />
              <Area type="monotone" dataKey="successRate" stroke="#10B981" strokeWidth={2} fill="url(#colorSuccess)" name="成功率%" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>
        {/* === DIST MARKER === */}
        <motion.div variants={cardVariants} className="rounded-xl p-5" style={{ background: 'linear-gradient(135deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)', border: '1px solid #1E293B' }}>
          <h2 className="text-base font-semibold mb-1" style={{ color: '#F1F5F9' }}>数字员工分布</h2>
          <p className="text-xs mb-2" style={{ color: '#64748B' }}>按业务类型任务量占比</p>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={distributionData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3}>
                {distributionData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#0D1321', border: '1px solid #1E293B', borderRadius: 8, fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-3 space-y-1.5">
            {distributionData.map((d) => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{ background: d.color }} /><span style={{ color: '#94A3B8' }}>{d.name}</span></div>
                <span style={{ color: '#64748B' }}>{d.value}%</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
      {/* === BOTTOM MARKER === */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <motion.div variants={cardVariants} className="rounded-xl p-5" style={{ background: 'linear-gradient(135deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)', border: '1px solid #1E293B' }}>
          <div className="mb-4 flex items-center justify-between">
            <div><h2 className="text-base font-semibold" style={{ color: '#F1F5F9' }}>实时动态</h2><p className="mt-0.5 text-xs" style={{ color: '#64748B' }}>系统事件与任务状态</p></div>
            <Badge variant="outline" className="text-xs" style={{ borderColor: '#1E293B', color: '#94A3B8' }}>{activities.length} 条</Badge>
          </div>
          <div className="space-y-3 max-h-[360px] overflow-y-auto">
            {activities.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-[#64748B] gap-1"><Clock className="w-6 h-6 opacity-40" /><span className="text-xs">暂无动态</span></div>
            ) : activities.map((act) => {
              const cfg = activityIconMap[act.type] || activityIconMap.system
              return (
                <motion.div key={act.id} className="flex items-start gap-3 rounded-lg p-2.5" style={{ background: 'rgba(15,23,42,0.4)' }} whileHover={{ background: 'rgba(15,23,42,0.6)' }} transition={{ duration: 0.2 }}>
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg shrink-0" style={{ background: cfg.bg }}><span style={{ color: cfg.color }}>{cfg.icon}</span></div>
                  <div className="min-w-0 flex-1"><p className="text-sm font-medium truncate" style={{ color: '#F1F5F9' }}>{act.title}</p><p className="text-xs mt-0.5 line-clamp-2" style={{ color: '#64748B' }}>{act.description}</p></div>
                </motion.div>
              )
            })}
          </div>
        </motion.div>

        <motion.div variants={cardVariants} className="rounded-xl p-5" style={{ background: 'linear-gradient(135deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)', border: '1px solid #1E293B' }}>
          <div className="mb-4 flex items-center justify-between">
            <div><h2 className="text-base font-semibold" style={{ color: '#F1F5F9' }}>任务队列</h2><p className="mt-0.5 text-xs" style={{ color: '#64748B' }}>当前运行中的任务与待处理事项</p></div>
            <Badge variant="outline" className="text-xs" style={{ borderColor: '#1E293B', color: '#94A3B8' }}>{taskQueue.filter((t) => t.status !== 'completed').length} 进行中</Badge>
          </div>
          <div className="flex flex-col gap-3 max-h-[360px] overflow-y-auto">
            {taskQueue.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-[#64748B] gap-1"><Clock className="w-6 h-6 opacity-40" /><span className="text-xs">暂无任务</span></div>
            ) : taskQueue.map((task) => {
              const progressColor = task.status === 'completed' ? '#10B981' : task.status === 'running' ? '#6366F1' : '#F59E0B'
              return (
                <motion.div key={task.id} className="flex items-center gap-4 rounded-lg p-3" style={{ background: 'rgba(15,23,42,0.4)' }} whileHover={{ background: 'rgba(15,23,42,0.6)' }} transition={{ duration: 0.2 }}>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2"><span className="truncate text-sm font-medium" style={{ color: '#F1F5F9' }}>{task.name}</span><span className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(99,102,241,0.1)', color: '#94A3B8' }}>{getTaskTypeLabel(task.type)}</span></div>
                    <div className="mt-2 flex items-center gap-3"><div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: 'rgba(30,41,59,0.8)' }}><motion.div className="h-full rounded-full" style={{ background: progressColor }} initial={{ width: 0 }} animate={{ width: `${task.progress}%` }} transition={{ duration: 0.8, ease: 'easeOut' }} /></div><span className="w-8 text-right text-xs font-medium" style={{ color: '#94A3B8' }}>{task.progress}%</span></div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3"><PriorityBadge priority={task.priority} /><TaskStatusBadge status={task.status} /></div>
                </motion.div>
              )
            })}
          </div>
        </motion.div>
      </div>
    </motion.div>
  )
}
