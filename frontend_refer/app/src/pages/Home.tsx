import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router'
import { motion } from 'framer-motion'
import {
  TrendingUp,
  Target,
  Zap,
  Calendar,
  ArrowUpRight,
  ArrowDownRight,
  PlusCircle,
  Kanban,
  UserPlus,
  Sparkles,
  ChevronRight,
  FileText,
  Brain,
  CheckCircle,
  AlertCircle,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { DealStage } from '@/types'
import type { Deal } from '@/types'
import {
  deals,
  activities,
  getStageColor,
  getStageLabel,
  formatCurrency,
  getDealsByStage,
  getActiveDeals,
  getTotalPipelineValue,
} from '@/data/mockData'

// ─── Animation Variants ────────────────────────────────────────
const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0 },
  },
}

const cardFromLeft = {
  hidden: { opacity: 0, x: -20 },
  show: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
  },
}

const columnFromBottom = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
  },
}

const itemFromRight = {
  hidden: { opacity: 0, x: 15 },
  show: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
  },
}

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
  },
}

const scaleIn = {
  hidden: { opacity: 0, scale: 0.9 },
  show: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.4, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] },
  },
}

// ─── CountUp Hook ──────────────────────────────────────────────
function useCountUp(end: number, duration: number = 1200, delay: number = 0) {
  const [value, setValue] = useState(0)
  const startTime = useRef<number | null>(null)
  const rafId = useRef<number>(0)

  useEffect(() => {
    const animate = (timestamp: number) => {
      if (startTime.current === null) startTime.current = timestamp
      const elapsed = timestamp - startTime.current

      if (elapsed < delay) {
        rafId.current = requestAnimationFrame(animate)
        return
      }

      const progress = Math.min((elapsed - delay) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3) // ease-out-expo approx
      setValue(Math.floor(eased * end))

      if (progress < 1) {
        rafId.current = requestAnimationFrame(animate)
      }
    }

    rafId.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(rafId.current)
  }, [end, duration, delay])

  return value
}

// ─── KPI Card Component ────────────────────────────────────────
interface KPICardProps {
  label: string
  value: string
  numericValue: number
  isPercentage?: boolean
  prefix?: string
  trend: number
  subtitle: string
  icon: React.ReactNode
  iconColor: string
  index: number
}

function KPICard({ label, value: _value, numericValue, isPercentage, prefix = '', trend, subtitle, icon, iconColor, index }: KPICardProps) {
  const count = useCountUp(numericValue, 1200, index * 100)
  const isPositive = trend >= 0

  const displayValue = isPercentage
    ? `${count}%`
    : prefix === '¥' && numericValue >= 1000000
      ? `${prefix}${(count / 1000000).toFixed(1)}M`
      : prefix === '¥' && numericValue >= 1000
        ? `${prefix}${(count / 1000).toFixed(0)}K`
        : `${prefix}${count}`

  return (
    <motion.div
      variants={cardFromLeft}
      className="glass-card p-5 flex flex-col gap-4 hover:scale-[1.02] hover:border-[#334155] hover:shadow-card-hover transition-all duration-200 cursor-default"
    >
      <div className="flex items-start justify-between">
        <span className="text-label text-[#64748B]">{label}</span>
        <div className="p-2 rounded-lg" style={{ backgroundColor: `${iconColor}15` }}>
          <span style={{ color: iconColor }}>{icon}</span>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-3">
          <span className="kpi-number">{displayValue}</span>
          <span
            className={cn(
              'inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-xs font-medium',
              isPositive
                ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981]'
                : 'bg-[rgba(239,68,68,0.15)] text-[#EF4444]'
            )}
          >
            {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
            {isPositive ? '+' : ''}{trend}%
          </span>
        </div>
        <p className="text-body-sm text-[#94A3B8] mt-1">{subtitle}</p>
      </div>
    </motion.div>
  )
}

// ─── Mini Deal Card ────────────────────────────────────────────
function MiniDealCard({ deal }: { deal: Deal }) {
  const stageColor = getStageColor(deal.stage)
  const stageLabel = getStageLabel(deal.stage)

  return (
    <div
      className="bg-[#111827] border border-[#1E293B] rounded-card-sm p-3 hover:translate-y-[-4px] hover:shadow-card-lift transition-all duration-200 cursor-pointer"
      style={{ borderLeftWidth: 4, borderLeftColor: stageColor }}
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-body-md font-semibold text-[#F1F5F9] truncate">{deal.customerName}</span>
        <span
          className="stage-badge text-[10px] px-2 py-0.5"
          style={{ backgroundColor: `${stageColor}15`, color: stageColor }}
        >
          {stageLabel}
        </span>
      </div>
      <p className="text-body-lg font-bold mb-2" style={{ color: stageColor }}>
        {formatCurrency(deal.amount)}
      </p>
      <div className="flex items-center justify-between">
        <span className="text-body-sm text-[#64748B]">{deal.expectedCloseDate}</span>
        <Avatar className="w-6 h-6">
          <AvatarFallback className="bg-[#1A2235] text-[#94A3B8] text-[10px]">
            {deal.assignedTo.charAt(0)}
          </AvatarFallback>
        </Avatar>
      </div>
    </div>
  )
}

// ─── Pipeline Preview Section ──────────────────────────────────
function PipelinePreview() {
  const activeStages = [
    DealStage.InitialContact,
    DealStage.NeedsConfirmed,
    DealStage.SolutionEval,
    DealStage.Negotiation,
  ]

  return (
    <motion.div
      variants={columnFromBottom}
      initial="hidden"
      animate="show"
      transition={{ delay: 0.4 }}
      className="glass-card p-6 flex-1 min-w-0"
    >
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-heading-md text-[#F1F5F9]">Active Pipeline</h3>
        <Link
          to="/pipeline"
          className="text-body-sm text-[#6366F1] hover:underline flex items-center gap-1"
        >
          View Full Pipeline
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin">
        {activeStages.map((stage, i) => {
          const stageDeals = getDealsByStage(stage)
          const stageColor = getStageColor(stage)
          const displayDeals = stageDeals.slice(0, 3)
          const moreCount = stageDeals.length - 3

          return (
            <motion.div
              key={stage}
              variants={columnFromBottom}
              custom={i}
              className="min-w-[200px] flex-shrink-0"
            >
              {/* Stage Header */}
              <div
                className="flex items-center gap-2 mb-3 pb-2 border-b-2"
                style={{ borderColor: stageColor }}
              >
                <span className="text-label text-[#F1F5F9]">{getStageLabel(stage)}</span>
                <span className="w-6 h-6 rounded-full bg-[#1A2235] flex items-center justify-center text-xs text-[#94A3B8] font-medium">
                  {stageDeals.length}
                </span>
              </div>

              {/* Deal Cards */}
              <div className="space-y-2">
                {displayDeals.map((deal) => (
                  <MiniDealCard key={deal.id} deal={deal} />
                ))}
                {moreCount > 0 && (
                  <Link
                    to="/pipeline"
                    className="block text-center text-body-sm text-[#6366F1] hover:underline py-1"
                  >
                    +{moreCount} more
                  </Link>
                )}
                {stageDeals.length === 0 && (
                  <p className="text-body-sm text-[#64748B] text-center py-4">No deals</p>
                )}
              </div>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

// ─── Activity Feed Section ─────────────────────────────────────
function ActivityFeed() {
  const [filter, setFilter] = useState('All')
  const filters = ['All', 'Visits', 'Deals', 'AI']

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'visit':
        return { icon: <FileText className="w-5 h-5" />, color: '#3B82F6', bg: 'rgba(59,130,246,0.15)' }
      case 'deal_moved':
        return { icon: <TrendingUp className="w-5 h-5" />, color: '#F59E0B', bg: 'rgba(245,158,11,0.15)' }
      case 'ai_report':
        return { icon: <Brain className="w-5 h-5" />, color: '#8B5CF6', bg: 'rgba(139,92,246,0.15)' }
      case 'new_customer':
        return { icon: <UserPlus className="w-5 h-5" />, color: '#10B981', bg: 'rgba(16,185,129,0.15)' }
      case 'follow_up':
        return { icon: <AlertCircle className="w-5 h-5" />, color: '#F59E0B', bg: 'rgba(245,158,11,0.15)' }
      case 'deal_created':
        return { icon: <CheckCircle className="w-5 h-5" />, color: '#10B981', bg: 'rgba(16,185,129,0.15)' }
      default:
        return { icon: <FileText className="w-5 h-5" />, color: '#64748B', bg: 'rgba(100,116,139,0.15)' }
    }
  }

  const getRelativeTime = (timestamp: string) => {
    const now = new Date('2026-02-15T14:00:00Z')
    const then = new Date(timestamp)
    const diff = now.getTime() - then.getTime()
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const days = Math.floor(hours / 24)

    if (hours < 1) return 'Just now'
    if (hours === 1) return '1h ago'
    if (hours < 24) return `${hours}h ago`
    if (days === 1) return 'Yesterday'
    if (days === 2) return '2d ago'
    return `${days}d ago`
  }

  return (
    <motion.div
      variants={columnFromBottom}
      initial="hidden"
      animate="show"
      transition={{ delay: 0.6 }}
      className="glass-card p-6 w-full lg:w-[40%] flex-shrink-0"
    >
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-heading-md text-[#F1F5F9]">Recent Activity</h3>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="bg-[#0D1321] border border-[#1E293B] rounded-lg text-xs text-[#94A3B8] px-2 py-1 focus:outline-none focus:border-[#334155]"
        >
          {filters.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </div>

      <div className="space-y-1 max-h-[400px] overflow-y-auto pr-1">
        {activities.map((activity, i) => {
          const { icon, color, bg } = getActivityIcon(activity.type)

          return (
            <motion.div
              key={activity.id}
              variants={itemFromRight}
              initial="hidden"
              animate="show"
              transition={{ delay: 0.6 + i * 0.05 }}
              className="flex items-start gap-3 p-3 rounded-lg hover:bg-[rgba(255,255,255,0.02)] transition-colors duration-100 cursor-pointer"
            >
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                style={{ backgroundColor: bg, color }}
              >
                {icon}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-body-md text-[#F1F5F9] truncate">{activity.title}</p>
                <p className="text-body-sm text-[#64748B] truncate">{activity.description}</p>
              </div>
              <span className="text-body-sm text-[#64748B] shrink-0 whitespace-nowrap">
                {getRelativeTime(activity.timestamp)}
              </span>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

// ─── Quick Actions Section ─────────────────────────────────────
function QuickActions() {
  const actions = [
    { label: 'New Visit', icon: <PlusCircle className="w-5 h-5" />, to: '/input', variant: 'primary' as const },
    { label: 'View Pipeline', icon: <Kanban className="w-5 h-5" />, to: '/pipeline', variant: 'secondary' as const },
    { label: 'Add Customer', icon: <UserPlus className="w-5 h-5" />, to: '/customers', variant: 'default' as const },
    { label: 'AI Reports', icon: <Sparkles className="w-5 h-5" />, to: '/reports', variant: 'default' as const },
  ]

  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="show"
      transition={{ delay: 0.8 }}
      className="glass-card p-6"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {actions.map((action, i) => (
          <motion.div
            key={action.label}
            variants={scaleIn}
            initial="hidden"
            animate="show"
            transition={{ delay: 0.8 + i * 0.08 }}
          >
            <Link to={action.to} className="block">
              <Button
                variant={action.variant === 'primary' ? 'default' : action.variant === 'secondary' ? 'outline' : 'outline'}
                className={cn(
                  'w-full h-[52px] gap-2 text-sm font-medium',
                  action.variant === 'primary'
                    ? 'bg-[#6366F1] hover:bg-[#818CF8] text-white border-0 hover:scale-105 active:scale-[0.97] transition-all'
                    : action.variant === 'secondary'
                      ? 'border-[#6366F1] text-[#6366F1] hover:bg-[rgba(99,102,241,0.08)] hover:scale-105 active:scale-[0.97] transition-all'
                      : 'border-[#334155] text-[#94A3B8] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#F1F5F9] hover:scale-105 active:scale-[0.97] transition-all'
                )}
              >
                {action.icon}
                {action.label}
              </Button>
            </Link>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

// ─── Performance Chart ─────────────────────────────────────────
const chartData = [
  { date: 'Feb 1', value: 1800000 },
  { date: 'Feb 3', value: 1950000 },
  { date: 'Feb 5', value: 2100000 },
  { date: 'Feb 7', value: 2050000 },
  { date: 'Feb 9', value: 2200000 },
  { date: 'Feb 11', value: 2300000 },
  { date: 'Feb 13', value: 2250000 },
  { date: 'Feb 15', value: 2400000 },
]

function PerformanceChart() {
  const [timeRange, setTimeRange] = useState('7D')
  const ranges = ['7D', '30D', '90D']

  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="show"
      transition={{ delay: 1.0 }}
      className="glass-card p-6"
    >
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-heading-md text-[#F1F5F9]">Pipeline Performance</h3>
        <div className="flex gap-1">
          {ranges.map((r) => (
            <button
              key={r}
              onClick={() => setTimeRange(r)}
              className={cn(
                'px-3 py-1 rounded-lg text-xs font-medium transition-colors',
                timeRange === r
                  ? 'bg-[#6366F1] text-white'
                  : 'text-[#64748B] hover:text-[#94A3B8] hover:bg-[rgba(255,255,255,0.03)]'
              )}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366F1" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#6366F1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: '#64748B', fontSize: 12 }}
              axisLine={{ stroke: '#1E293B' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#64748B', fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `¥${(v / 1000000).toFixed(1)}M`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1A2235',
                border: '1px solid #1E293B',
                borderRadius: '12px',
                color: '#F1F5F9',
                fontSize: '13px',
              }}
              formatter={(value: number) => [`¥${(value / 1000000).toFixed(2)}M`, 'Pipeline Value']}
              labelStyle={{ color: '#94A3B8', marginBottom: '4px' }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#6366F1"
              strokeWidth={2}
              fill="url(#areaGrad)"
              animationDuration={1500}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  )
}

// ─── Main Dashboard Page ───────────────────────────────────────
export default function Home() {
  const activeDeals = getActiveDeals()
  const totalPipeline = getTotalPipelineValue()
  const activeCount = activeDeals.length
  const wonDeals = deals.filter((d) => d.stage === DealStage.Won)
  const lostDeals = deals.filter((d) => d.stage === DealStage.Lost)
  const winRate = wonDeals.length + lostDeals.length > 0
    ? Math.round((wonDeals.length / (wonDeals.length + lostDeals.length)) * 100)
    : 0

  const kpiCards = [
    {
      label: 'PIPELINE VALUE',
      value: formatCurrency(totalPipeline),
      numericValue: totalPipeline,
      prefix: '¥',
      trend: 12.5,
      subtitle: `Across ${activeCount} active deals`,
      icon: <TrendingUp className="w-5 h-5" />,
      iconColor: '#6366F1',
    },
    {
      label: 'ACTIVE DEALS',
      value: `${activeCount}`,
      numericValue: activeCount,
      trend: 14.3,
      subtitle: `${deals.filter((d) => d.stage === DealStage.Negotiation).length} in negotiation stage`,
      icon: <Target className="w-5 h-5" />,
      iconColor: '#3B82F6',
    },
    {
      label: 'WIN RATE (30D)',
      value: `${winRate}%`,
      numericValue: winRate,
      isPercentage: true,
      trend: 5.2,
      subtitle: 'Industry avg: 52%',
      icon: <Zap className="w-5 h-5" />,
      iconColor: '#10B981',
    },
    {
      label: 'VISITS THIS MONTH',
      value: '12',
      numericValue: 12,
      trend: -14.3,
      subtitle: '3 pending follow-up',
      icon: <Calendar className="w-5 h-5" />,
      iconColor: '#F59E0B',
    },
  ]

  return (
    <div className="max-w-container mx-auto space-y-6">
      {/* Section 1: KPI Cards */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4"
      >
        {kpiCards.map((card, i) => (
          <KPICard key={card.label} {...card} index={i} />
        ))}
      </motion.div>

      {/* Section 2: Two-column layout (Pipeline + Activity) */}
      <div className="flex flex-col lg:flex-row gap-6">
        <PipelinePreview />
        <ActivityFeed />
      </div>

      {/* Section 3: Quick Actions */}
      <QuickActions />

      {/* Section 4: Performance Chart */}
      <PerformanceChart />
    </div>
  )
}
