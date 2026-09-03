import { useState, useMemo } from 'react'
import { Link } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus,
  Search,
  Calendar,
  Building2,
  Filter,
  FileText,
  Eye,
  Trash2,
  ChevronDown,
  X,
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { cn } from '@/lib/utils'
import { deals, visitRecords, getStageColor, getStageLabel } from '@/data/mockData'
import { DealStage } from '@/types'

// --- Types ---
interface ReportItem {
  id: string
  customerName: string
  customerId: string
  visitDate: string
  dealAmount: number
  stage: DealStage
  winRate: number
  generatedAt: string
  purpose: string
}

// --- Compose report items from deals + visit records ---
function composeReports(): ReportItem[] {
  const reportMap = new Map<string, ReportItem>()

  visitRecords.forEach((vr) => {
    const deal = deals.find((d) => d.customerId === vr.customerId)
    if (deal) {
      reportMap.set(vr.id, {
        id: vr.reportId || `r-${vr.id}`,
        customerName: vr.customerName,
        customerId: vr.customerId,
        visitDate: vr.visitDate,
        dealAmount: deal.amount,
        stage: deal.stage,
        winRate: deal.winRate,
        generatedAt: vr.updatedAt,
        purpose: vr.purpose,
      })
    }
  })

  return Array.from(reportMap.values()).sort(
    (a, b) => new Date(b.generatedAt).getTime() - new Date(a.generatedAt).getTime()
  )
}

const allReports = composeReports()

const stageOptions = [
  { value: 'all', label: '全部阶段' },
  ...Object.values(DealStage).map((s) => ({ value: s, label: getStageLabel(s) })),
]

const customerOptions = [
  { value: 'all', label: '全部客户' },
  ...Array.from(new Set(allReports.map((r) => r.customerName))).map((c) => ({
    value: c,
    label: c,
  })),
]

// --- Stage badge component ---
function StageBadge({ stage }: { stage: DealStage }) {
  const color = getStageColor(stage)
  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium"
      style={{
        backgroundColor: `${color}20`,
        color,
        boxShadow: `0 0 8px ${color}30`,
      }}
    >
      {getStageLabel(stage)}
    </span>
  )
}

// --- Report Card ---
function ReportCard({
  report,
  index,
  onDelete,
}: {
  report: ReportItem
  index: number
  onDelete: (id: string) => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10, scale: 0.95 }}
      transition={{
        duration: 0.4,
        delay: index * 0.08,
        ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
      }}
      whileHover={{
        y: -4,
        transition: { duration: 0.2, ease: [0.25, 1, 0.5, 1] as [number, number, number, number] },
      }}
      className="group gradient-card border border-[#1E293B] rounded-[16px] p-5 hover:border-[#334155] hover:shadow-[0_8px_32px_rgba(99,102,241,0.1)] transition-all duration-200"
    >
      {/* Top row: Customer + Stage */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[#1A2235] border border-[#1E293B] flex items-center justify-center shrink-0">
            <Building2 className="w-5 h-5 text-[#6366F1]" />
          </div>
          <div className="min-w-0">
            <h3 className="text-body-md font-semibold text-[#F1F5F9] truncate">
              {report.customerName}
            </h3>
            <p className="text-body-sm text-[#64748B] truncate">{report.purpose}</p>
          </div>
        </div>
        <StageBadge stage={report.stage} />
      </div>

      {/* Deal amount + Win rate */}
      <div className="flex items-center gap-4 mb-4">
        <div>
          <p className="text-label text-[#64748B] mb-0.5">商机金额</p>
          <p className="font-display text-xl font-bold text-[#F1F5F9]">
            ¥{(report.dealAmount / 1000).toFixed(0)}K
          </p>
        </div>
        <div className="w-px h-10 bg-[#1E293B]" />
        <div>
          <p className="text-label text-[#64748B] mb-0.5">赢率</p>
          <p className="font-display text-xl font-bold text-[#10B981]">{report.winRate}%</p>
        </div>
      </div>

      {/* Date + Actions */}
      <div className="flex items-center justify-between pt-3 border-t border-[#1E293B]">
        <div className="flex items-center gap-1.5 text-[#64748B]">
          <Calendar className="w-3.5 h-3.5" />
          <span className="text-body-sm">
            {format(parseISO(report.visitDate), 'yyyy-MM-dd')}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Link
            to={`/report/${report.id}`}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-body-sm text-[#94A3B8] hover:text-[#6366F1] hover:bg-[rgba(99,102,241,0.08)] transition-colors"
          >
            <Eye className="w-3.5 h-3.5" />
            查看
          </Link>
          <button
            onClick={() => onDelete(report.id)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-body-sm text-[#94A3B8] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.08)] transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            删除
          </button>
        </div>
      </div>
    </motion.div>
  )
}

// --- Empty State ---
function EmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="flex flex-col items-center justify-center py-20"
    >
      <div className="w-20 h-20 rounded-2xl bg-[#1A2235] border border-[#1E293B] flex items-center justify-center mb-5">
        <FileText className="w-10 h-10 text-[#64748B]" />
      </div>
      <h3 className="text-heading-sm text-[#94A3B8] mb-2">暂无报告</h3>
      <p className="text-body-md text-[#64748B] mb-6 text-center max-w-sm">
        您还没有生成任何拜访报告。完成一次客户拜访并录入信息后，AI将为您生成详细的分析报告。
      </p>
      <Link
        to="/input"
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[10px] bg-[#6366F1] text-white text-sm font-medium hover:bg-[#818CF8] hover:scale-105 active:scale-[0.97] transition-all duration-100"
        style={{ boxShadow: '0 0 20px rgba(99,102,241,0.3)' }}
      >
        <Plus className="w-4 h-4" />
        开始录入
      </Link>
    </motion.div>
  )
}

// --- Main Component ---
export default function Reports() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedStage, setSelectedStage] = useState('all')
  const [selectedCustomer, setSelectedCustomer] = useState('all')
  const [dateRange, setDateRange] = useState('all')
  const [reports, setReports] = useState(allReports)
  const [stageDropdownOpen, setStageDropdownOpen] = useState(false)
  const [customerDropdownOpen, setCustomerDropdownOpen] = useState(false)

  const filteredReports = useMemo(() => {
    return reports.filter((r) => {
      const matchesSearch =
        searchQuery === '' ||
        r.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.purpose.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesStage = selectedStage === 'all' || r.stage === selectedStage
      const matchesCustomer = selectedCustomer === 'all' || r.customerName === selectedCustomer
      const matchesDate =
        dateRange === 'all' ||
        (dateRange === '7d' &&
          new Date(r.visitDate) > new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)) ||
        (dateRange === '30d' &&
          new Date(r.visitDate) > new Date(Date.now() - 30 * 24 * 60 * 60 * 1000))
      return matchesSearch && matchesStage && matchesCustomer && matchesDate
    })
  }, [reports, searchQuery, selectedStage, selectedCustomer, dateRange])

  const handleDelete = (id: string) => {
    setReports((prev) => prev.filter((r) => r.id !== id))
  }

  const hasActiveFilters =
    selectedStage !== 'all' || selectedCustomer !== 'all' || dateRange !== 'all' || searchQuery !== ''

  const clearFilters = () => {
    setSearchQuery('')
    setSelectedStage('all')
    setSelectedCustomer('all')
    setDateRange('all')
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="max-w-[1400px] mx-auto"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-heading-lg text-[#F1F5F9] mb-1">拜访报告</h2>
          <p className="text-body-md text-[#64748B]">共 {filteredReports.length} 份报告</p>
        </div>
        <Link
          to="/input"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[10px] bg-[#6366F1] text-white text-sm font-medium hover:bg-[#818CF8] hover:scale-105 active:scale-[0.97] transition-all duration-100"
          style={{ boxShadow: '0 0 20px rgba(99,102,241,0.3)' }}
        >
          <Plus className="w-4 h-4" />
          新建报告
        </Link>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 mb-6 p-4 rounded-[12px] bg-[#111827] border border-[#1E293B]">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索客户名称或拜访目的..."
            className="w-full h-10 pl-10 pr-4 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155] transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#F1F5F9]"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-1.5 h-10 px-3 rounded-[10px] bg-[#0D1321] border border-[#1E293B]">
          <Calendar className="w-4 h-4 text-[#64748B]" />
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-transparent text-sm text-[#94A3B8] focus:outline-none cursor-pointer"
          >
            <option value="all">全部时间</option>
            <option value="7d">近7天</option>
            <option value="30d">近30天</option>
          </select>
        </div>

        {/* Customer Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setCustomerDropdownOpen(!customerDropdownOpen)
              setStageDropdownOpen(false)
            }}
            className={cn(
              'flex items-center gap-2 h-10 px-4 rounded-[10px] border text-sm transition-colors',
              selectedCustomer !== 'all'
                ? 'bg-[rgba(99,102,241,0.1)] border-[#6366F1] text-[#6366F1]'
                : 'bg-[#0D1321] border-[#1E293B] text-[#94A3B8] hover:border-[#334155]'
            )}
          >
            <Building2 className="w-4 h-4" />
            {customerOptions.find((o) => o.value === selectedCustomer)?.label}
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          <AnimatePresence>
            {customerDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                transition={{ duration: 0.15 }}
                className="absolute top-full mt-1.5 right-0 w-48 py-1.5 rounded-[12px] bg-[#1A2235] border border-[#1E293B] shadow-xl z-20"
              >
                {customerOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => {
                      setSelectedCustomer(opt.value)
                      setCustomerDropdownOpen(false)
                    }}
                    className={cn(
                      'w-full text-left px-3 py-2 text-sm transition-colors',
                      selectedCustomer === opt.value
                        ? 'text-[#6366F1] bg-[rgba(99,102,241,0.08)]'
                        : 'text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)]'
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Stage Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setStageDropdownOpen(!stageDropdownOpen)
              setCustomerDropdownOpen(false)
            }}
            className={cn(
              'flex items-center gap-2 h-10 px-4 rounded-[10px] border text-sm transition-colors',
              selectedStage !== 'all'
                ? 'bg-[rgba(99,102,241,0.1)] border-[#6366F1] text-[#6366F1]'
                : 'bg-[#0D1321] border-[#1E293B] text-[#94A3B8] hover:border-[#334155]'
            )}
          >
            <Filter className="w-4 h-4" />
            {stageOptions.find((o) => o.value === selectedStage)?.label}
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          <AnimatePresence>
            {stageDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                transition={{ duration: 0.15 }}
                className="absolute top-full mt-1.5 right-0 w-48 py-1.5 rounded-[12px] bg-[#1A2235] border border-[#1E293B] shadow-xl z-20"
              >
                {stageOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => {
                      setSelectedStage(opt.value)
                      setStageDropdownOpen(false)
                    }}
                    className={cn(
                      'w-full text-left px-3 py-2 text-sm transition-colors',
                      selectedStage === opt.value
                        ? 'text-[#6366F1] bg-[rgba(99,102,241,0.08)]'
                        : 'text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)]'
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Clear filters */}
        <AnimatePresence>
          {hasActiveFilters && (
            <motion.button
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              onClick={clearFilters}
              className="flex items-center gap-1.5 h-10 px-3 rounded-[10px] text-sm text-[#EF4444] hover:bg-[rgba(239,68,68,0.08)] transition-colors"
            >
              <X className="w-3.5 h-3.5" />
              清除筛选
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Report Grid */}
      <AnimatePresence mode="wait">
        {filteredReports.length > 0 ? (
          <motion.div
            key="grid"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
          >
            <AnimatePresence>
              {filteredReports.map((report, index) => (
                <ReportCard
                  key={report.id}
                  report={report}
                  index={index}
                  onDelete={handleDelete}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        ) : (
          <EmptyState />
        )}
      </AnimatePresence>
    </motion.div>
  )
}
