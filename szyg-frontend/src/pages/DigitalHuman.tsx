import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  Plus,
  Bot,
  UploadCloud,
  X,
  Filter,
  Activity,
  CheckCircle2,
  TrendingUp,
  Clock,
  Cpu,
  MoreHorizontal,
} from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useDigitalHumans } from '@/lib/hooks'
import { getStatusColor, getStatusLabel, getTypeLabel } from '@/lib/format'

// ─── Animation Variants ────────────────────────────────────────
const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.1 },
  },
}

const cardVariants = {
  hidden: { opacity: 0, y: 24 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
  },
}

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
  },
}

const floatAnimation = {
  animate: {
    y: [0, -10, 0],
    transition: {
      duration: 3,
      repeat: Infinity,
      ease: 'easeInOut' as const,
    },
  },
}

// ─── Status Badge Variant Mapping ──────────────────────────────
const statusBadgeVariantMap: Record<
  string,
  'success' | 'warning' | 'default' | 'error'
> = {
  active: 'success',
  training: 'warning',
  idle: 'default',
  error: 'error',
}

// ─── Type Color Map for Avatar Gradients ───────────────────────
const typeGradientMap: Record<string, string> = {
  sales: 'from-[#6366F1] to-[#818CF8]',
  customer_service: 'from-[#10B981] to-[#34D399]',
  marketing: 'from-[#F59E0B] to-[#FBBF24]',
  data_analyst: 'from-[#3B82F6] to-[#60A5FA]',
  custom: 'from-[#8B5CF6] to-[#A78BFA]',
}

// ─── Helper: Format relative time ──────────────────────────────
function getRelativeTime(timestamp: string): string {
  const now = new Date()
  const then = new Date(timestamp)
  const diff = now.getTime() - then.getTime()
  const minutes = Math.floor(diff / (1000 * 60))
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const days = Math.floor(hours / 24)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days === 1) return '昨天'
  if (days < 7) return `${days} 天前`
  return `${Math.floor(days / 7)} 周前`
}

// ─── Helper: Format number ─────────────────────────────────────
function formatNumber(num: number): string {
  if (num >= 10000) return `${(num / 10000).toFixed(1)}w`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}k`
  return num.toString()
}

// ─── Type Select Options ───────────────────────────────────────
const typeOptions = [
  { value: 'all', label: '全部类型' },
  { value: 'sales', label: '销售' },
  { value: 'customer_service', label: '客服' },
  { value: 'marketing', label: '营销' },
  { value: 'data_analyst', label: '数据分析' },
  { value: 'custom', label: '定制' },
]

const statusOptions = [
  { value: 'all', label: '全部状态' },
  { value: 'active', label: '运行中' },
  { value: 'training', label: '训练中' },
  { value: 'idle', label: '待机' },
  { value: 'error', label: '异常' },
]

// ─── Filter Tag Component ──────────────────────────────────────
function FilterTag({
  label,
  onRemove,
}: {
  label: string
  onRemove: () => void
}) {
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-[rgba(99,102,241,0.12)] text-[#818CF8] border border-[rgba(99,102,241,0.2)]"
    >
      {label}
      <button
        onClick={onRemove}
        className="ml-0.5 hover:text-[#F1F5F9] transition-colors"
      >
        <X className="w-3 h-3" />
      </button>
    </motion.span>
  )
}

// ─── Digital Human Card Component ──────────────────────────────
function DigitalHumanCard({
  dh,
  index,
}: {
  dh: import('@/types').DigitalHuman
  index: number
}) {
  const statusColor = getStatusColor(dh.status)
  const statusLabel = getStatusLabel(dh.status)
  const typeLabel = getTypeLabel(dh.type)
  const gradientClass = typeGradientMap[dh.type] || 'from-[#6366F1] to-[#818CF8]'

  return (
    <motion.div
      variants={cardVariants}
      custom={index}
      whileHover={{
        y: -4,
        transition: { duration: 0.2, ease: 'easeOut' as const },
      }}
      className={cn(
        'group glass-card p-5 flex flex-col gap-4 cursor-pointer',
        'hover:border-[#334155] hover:shadow-[0_8px_32px_rgba(0,0,0,0.3)]',
        'transition-shadow duration-300'
      )}
    >
      {/* Card Header: Avatar + Name + Status */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Avatar className="w-11 h-11">
            <AvatarFallback
              className={cn(
                'bg-gradient-to-br text-white text-sm font-semibold',
                gradientClass
              )}
            >
              {dh.avatar}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <h3 className="text-body-md font-semibold text-[#F1F5F9] truncate">
              {dh.name}
            </h3>
            <Badge variant={statusBadgeVariantMap[dh.status] || 'default'}>
              <span className="flex items-center gap-1">
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{
                    backgroundColor: statusColor,
                    boxShadow: `0 0 6px ${statusColor}`,
                  }}
                />
                {statusLabel}
              </span>
            </Badge>
          </div>
        </div>
        <button className="text-[#64748B] hover:text-[#94A3B8] transition-colors opacity-0 group-hover:opacity-100">
          <MoreHorizontal className="w-4 h-4" />
        </button>
      </div>

      {/* Type + Model */}
      <div className="flex items-center gap-2">
        <span
          className="text-body-sm font-medium px-2 py-0.5 rounded-md"
          style={{
            backgroundColor: `${statusColor}12`,
            color: statusColor,
          }}
        >
          {typeLabel}
        </span>
        <span className="text-body-sm text-[#64748B] flex items-center gap-1">
          <Cpu className="w-3 h-3" />
          {dh.model}
        </span>
      </div>

      {/* Description */}
      <p className="text-body-sm text-[#94A3B8] line-clamp-2 leading-relaxed min-h-[2.5em]">
        {dh.description}
      </p>

      {/* Stats Row */}
      <div className="flex items-center gap-4 pt-1">
        <div className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-[#6366F1]" />
          <span className="text-body-sm text-[#F1F5F9] font-medium">
            {formatNumber(dh.interactions)}
          </span>
          <span className="text-body-sm text-[#64748B]">次交互</span>
        </div>
        <div className="flex items-center gap-1.5">
          <CheckCircle2
            className="w-3.5 h-3.5"
            style={{
              color: dh.successRate >= 90 ? '#10B981' : '#F59E0B',
            }}
          />
          <span className="text-body-sm text-[#F1F5F9] font-medium">
            {dh.successRate}%
          </span>
          <span className="text-body-sm text-[#64748B]">成功率</span>
        </div>
      </div>

      {/* Divider */}
      <div className="h-px bg-[#1E293B]" />

      {/* Footer: Last Active */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-body-sm text-[#64748B]">
          <Clock className="w-3.5 h-3.5" />
          <span>{getRelativeTime(dh.lastActive)}</span>
        </div>
        <TrendingUp className="w-4 h-4 text-[#6366F1] opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </motion.div>
  )
}

// ─── Empty State Component ─────────────────────────────────────
function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className="flex flex-col items-center justify-center py-20 gap-6"
    >
      <motion.div
        variants={floatAnimation}
        animate="animate"
        className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#6366F1]/20 to-[#818CF8]/10 border border-[#6366F1]/20 flex items-center justify-center"
      >
        <Bot className="w-10 h-10 text-[#6366F1]" />
      </motion.div>
      <div className="text-center space-y-2">
        <h3 className="text-heading-sm text-[#F1F5F9]">暂无数字员工</h3>
        <p className="text-body-md text-[#94A3B8]">
          点击上方按钮创建你的第一个数字员工
        </p>
      </div>
      <Button
        onClick={onCreate}
        className="bg-[#6366F1] hover:bg-[#818CF8] text-white gap-2 h-10 px-5"
      >
        <Plus className="w-4 h-4" />
        新建数字员工
      </Button>
    </motion.div>
  )
}

// ─── Upload Area Component ─────────────────────────────────────
function UploadArea() {
  const [isDragging, setIsDragging] = useState(false)

  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="show"
      className={cn(
        'glass-card p-8 flex flex-col items-center justify-center gap-4',
        'border-dashed border-2',
        isDragging
          ? 'border-[#6366F1] bg-[rgba(99,102,241,0.05)]'
          : 'border-[#1E293B] hover:border-[#334155]'
      )}
      onDragEnter={() => setIsDragging(true)}
      onDragLeave={() => setIsDragging(false)}
      onDrop={() => setIsDragging(false)}
    >
      <div
        className={cn(
          'w-14 h-14 rounded-xl flex items-center justify-center transition-colors',
          isDragging
            ? 'bg-[rgba(99,102,241,0.15)]'
            : 'bg-[#1A2235]'
        )}
      >
        <UploadCloud
          className={cn(
            'w-7 h-7 transition-colors',
            isDragging ? 'text-[#6366F1]' : 'text-[#64748B]'
          )}
        />
      </div>
      <div className="text-center space-y-1">
        <p className="text-body-md text-[#F1F5F9]">
          拖拽文件到此处，或
          <span className="text-[#6366F1] hover:underline cursor-pointer ml-1">
            点击上传
          </span>
        </p>
        <p className="text-body-sm text-[#64748B]">
          支持 .json, .yaml 配置文件
        </p>
      </div>
    </motion.div>
  )
}

// ─── Main Page Component ───────────────────────────────────────
export default function DigitalHuman() {
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [showUpload, setShowUpload] = useState(false)

  const { data: dhData } = useDigitalHumans()
  const digitalHumans = dhData?.digitalHumans ?? []

  // Filter logic
  const filteredHumans = useMemo(() => {
    return digitalHumans.filter((dh) => {
      const matchesSearch =
        !searchQuery ||
        dh.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        dh.description.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesType = typeFilter === 'all' || dh.type === typeFilter
      const matchesStatus =
        statusFilter === 'all' || dh.status === statusFilter
      return matchesSearch && matchesType && matchesStatus
    })
  }, [digitalHumans, searchQuery, typeFilter, statusFilter])

  // Active filter tags
  const activeFilters = useMemo(() => {
    const filters: { label: string; onRemove: () => void }[] = []
    if (typeFilter !== 'all') {
      filters.push({
        label: `类型: ${getTypeLabel(typeFilter)}`,
        onRemove: () => setTypeFilter('all'),
      })
    }
    if (statusFilter !== 'all') {
      filters.push({
        label: `状态: ${getStatusLabel(statusFilter)}`,
        onRemove: () => setStatusFilter('all'),
      })
    }
    return filters
  }, [typeFilter, statusFilter])

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* ─── Page Header ───────────────────────────────────────── */}
      <motion.div
        variants={fadeUp}
        initial="hidden"
        animate="show"
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4"
      >
        <div>
          <h1 className="text-display-md text-[#F1F5F9]">数字人管理</h1>
          <p className="text-body-md text-[#94A3B8] mt-1">
            管理你的数字员工，查看运行状态与性能指标
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => setShowUpload(!showUpload)}
            className="gap-2"
          >
            <UploadCloud className="w-4 h-4" />
            导入配置
          </Button>
          <Button className="bg-[#6366F1] hover:bg-[#818CF8] text-white gap-2 h-10 px-5">
            <Plus className="w-4 h-4" />
            新建数字员工
          </Button>
        </div>
      </motion.div>

      {/* ─── Upload Area (Collapsible) ─────────────────────────── */}
      <AnimatePresence>
        {showUpload && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <UploadArea />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Search & Filter Bar ───────────────────────────────── */}
      <motion.div
        variants={fadeUp}
        initial="hidden"
        animate="show"
        transition={{ delay: 0.15 }}
        className="glass-card p-4 flex flex-col sm:flex-row gap-3"
      >
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
          <Input
            placeholder="搜索数字员工名称..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 bg-[#0D1321] border-[#1E293B] focus:border-[#334155]"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#94A3B8]"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Type Filter */}
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="h-10 w-[160px] rounded-md border border-[#1E293B] bg-[#0D1321] pl-9 pr-8 text-sm text-[#F1F5F9] focus:outline-none focus:border-[#334155] focus:ring-1 focus:ring-[#6366F1]/20 appearance-none cursor-pointer"
          >
            {typeOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
            <svg
              className="w-4 h-4 text-[#64748B]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        </div>

        {/* Status Filter */}
        <div className="relative">
          <Activity className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 w-[160px] rounded-md border border-[#1E293B] bg-[#0D1321] pl-9 pr-8 text-sm text-[#F1F5F9] focus:outline-none focus:border-[#334155] focus:ring-1 focus:ring-[#6366F1]/20 appearance-none cursor-pointer"
          >
            {statusOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
            <svg
              className="w-4 h-4 text-[#64748B]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        </div>
      </motion.div>

      {/* ─── Active Filter Tags ────────────────────────────────── */}
      <AnimatePresence>
        {activeFilters.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center gap-2 flex-wrap"
          >
            <span className="text-body-sm text-[#64748B]">已筛选:</span>
            <AnimatePresence>
              {activeFilters.map((filter, i) => (
                <FilterTag key={i} label={filter.label} onRemove={filter.onRemove} />
              ))}
            </AnimatePresence>
            <button
              onClick={() => {
                setTypeFilter('all')
                setStatusFilter('all')
              }}
              className="text-body-sm text-[#6366F1] hover:underline ml-1"
            >
              清除全部
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Results Count ─────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <p className="text-body-sm text-[#64748B]">
          共 <span className="text-[#F1F5F9] font-medium">{filteredHumans.length}</span> 个数字员工
        </p>
      </div>

      {/* ─── Digital Human Card Grid ───────────────────────────── */}
      {filteredHumans.length > 0 ? (
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
        >
          {filteredHumans.map((dh, index) => (
            <DigitalHumanCard key={dh.id} dh={dh} index={index} />
          ))}
        </motion.div>
      ) : (
        <EmptyState onCreate={() => {}} />
      )}
    </div>
  )
}
