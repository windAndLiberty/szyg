import { useState, useMemo, useCallback } from 'react'

import { motion, AnimatePresence } from 'framer-motion'
import {
  DndContext,
  closestCenter,
  DragOverlay,
  useSensor,
  useSensors,
  PointerSensor,
  type DragEndEvent,
  type DragStartEvent,
  type DragOverEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  Plus,
  Calendar,
  Clock,
  Edit3,
  Eye,
  X,
  Mail,
  Phone,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Users,
  Timer,
  BarChart3,
} from 'lucide-react'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { cn } from '@/lib/utils'
import { DealStage } from '@/types'
import type { Deal } from '@/types'
import { deals as initialDeals } from '@/data/mockData'

/* ------------------------------------------------------------------ */
/*  Stage config                                                       */
/* ------------------------------------------------------------------ */

interface StageConfig {
  key: DealStage
  label: string
  color: string
  glow: string
  bgTint: string
}

const STAGES: StageConfig[] = [
  { key: DealStage.InitialContact, label: '初次接触', color: '#8B5CF6', glow: 'rgba(139,92,246,0.3)', bgTint: 'rgba(139,92,246,0.05)' },
  { key: DealStage.NeedsConfirmed,  label: '需求确认', color: '#3B82F6', glow: 'rgba(59,130,246,0.3)', bgTint: 'rgba(59,130,246,0.05)' },
  { key: DealStage.SolutionEval,    label: '方案评估', color: '#06B6D4', glow: 'rgba(6,182,212,0.3)',  bgTint: 'rgba(6,182,212,0.05)' },
  { key: DealStage.Negotiation,     label: '商务谈判', color: '#F59E0B', glow: 'rgba(245,158,11,0.3)', bgTint: 'rgba(245,158,11,0.05)' },
  { key: DealStage.Won,             label: '赢单',     color: '#10B981', glow: 'rgba(16,185,129,0.3)', bgTint: 'rgba(16,185,129,0.05)' },
  { key: DealStage.Lost,            label: '输单',     color: '#EF4444', glow: 'rgba(239,68,68,0.3)',  bgTint: 'rgba(239,68,68,0.05)' },
]

const stageMap: Record<DealStage, StageConfig> = STAGES.reduce((acc, s) => {
  acc[s.key] = s
  return acc
}, {} as Record<DealStage, StageConfig>)

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatCurrency(n: number): string {
  if (n >= 1_000_000) return `¥${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `¥${Math.round(n / 1_000)}K`
  return `¥${n}`
}

function getDaysInStage(deal: Deal): number {
  const updated = new Date(deal.updatedAt)
  const now = new Date()
  return Math.max(1, Math.floor((now.getTime() - updated.getTime()) / (1000 * 60 * 60 * 24)))
}

function getRepInitials(name: string): string {
  return name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()
}

/* ------------------------------------------------------------------ */
/*  Sparkline (mini SVG chart)                                         */
/* ------------------------------------------------------------------ */

function Sparkline({ data, color = '#6366F1', width = 80, height = 32 }: { data: number[]; color?: string; width?: number; height?: number }) {
  if (!data.length) return null
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / range) * height
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.7}
      />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/*  Sortable Deal Card                                                 */
/* ------------------------------------------------------------------ */

function SortableDealCard({
  deal,
  onClick,
}: {
  deal: Deal
  onClick: (deal: Deal) => void
}) {
  const stage = stageMap[deal.stage]
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: deal.id, data: { deal } })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <motion.div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      layout
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2, borderColor: '#334155' }}
      onClick={() => {
        if (!isDragging) onClick(deal)
      }}
      className={cn(
        'relative bg-[#111827] border border-[#1E293B] rounded-card-sm p-4 cursor-grab active:cursor-grabbing group select-none',
        isDragging && 'opacity-80 rotate-2 shadow-[0_16px_48px_rgba(0,0,0,0.4)] z-50'
      )}
    >
      {/* Left stage border */}
      <div
        className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full"
        style={{ backgroundColor: stage.color }}
      />

      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <span className="text-sm font-semibold text-[#F1F5F9] truncate pr-2">{deal.customerName}</span>
        <span className="text-sm font-bold text-[#F1F5F9] shrink-0">{formatCurrency(deal.amount)}</span>
      </div>

      {/* Contact */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-5 h-5 rounded-full bg-[#1A2235] flex items-center justify-center text-[10px] text-[#94A3B8] font-medium">
          {getRepInitials(deal.assignedTo)}
        </div>
        <span className="text-xs text-[#94A3B8]">{deal.assignedTo}</span>
      </div>

      {/* Win rate bar */}
      <div className="mb-3">
        <div className="h-1 bg-[#1A2235] rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${deal.winRate}%` }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="h-full rounded-full"
            style={{ backgroundColor: stage.color }}
          />
        </div>
        <span className="text-[11px] text-[#64748B] mt-1 block">{deal.winRate}% win rate</span>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 text-[#64748B]">
          <Calendar className="w-3 h-3" />
          <span className="text-[11px]">
            {deal.expectedCloseDate ? format(new Date(deal.expectedCloseDate), 'MM-dd', { locale: zhCN }) : '-'}
          </span>
        </div>
        <div className="flex items-center gap-1 text-[#64748B]">
          <Clock className="w-3 h-3" />
          <span className="text-[11px]">{getDaysInStage(deal)}d</span>
        </div>
      </div>

      {/* Hover actions */}
      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-100">
        <button
          onClick={(e) => { e.stopPropagation() }}
          className="p-1 rounded bg-[#1A2235] text-[#94A3B8] hover:text-[#F1F5F9] transition-colors"
        >
          <Edit3 className="w-3 h-3" />
        </button>
        <button
          onClick={(e) => { e.stopPropagation() }}
          className="p-1 rounded bg-[#1A2235] text-[#94A3B8] hover:text-[#F1F5F9] transition-colors"
        >
          <Eye className="w-3 h-3" />
        </button>
      </div>
    </motion.div>
  )
}

/* ------------------------------------------------------------------ */
/*  Deal Card (non-sortable, for overlay)                              */
/* ------------------------------------------------------------------ */

function DealCardOverlay({ deal }: { deal: Deal }) {
  const stage = stageMap[deal.stage]
  return (
    <div className="w-[280px] bg-[#111827] border border-[#1E293B] rounded-card-sm p-4 shadow-[0_16px_48px_rgba(0,0,0,0.4)] rotate-2 opacity-90">
      <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full" style={{ backgroundColor: stage.color }} />
      <div className="flex items-start justify-between mb-2">
        <span className="text-sm font-semibold text-[#F1F5F9]">{deal.customerName}</span>
        <span className="text-sm font-bold text-[#F1F5F9]">{formatCurrency(deal.amount)}</span>
      </div>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-5 h-5 rounded-full bg-[#1A2235] flex items-center justify-center text-[10px] text-[#94A3B8]">
          {getRepInitials(deal.assignedTo)}
        </div>
        <span className="text-xs text-[#94A3B8]">{deal.assignedTo}</span>
      </div>
      <div className="h-1 bg-[#1A2235] rounded-full overflow-hidden mb-1">
        <div className="h-full rounded-full" style={{ width: `${deal.winRate}%`, backgroundColor: stage.color }} />
      </div>
      <span className="text-[11px] text-[#64748B]">{deal.winRate}% win rate</span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Pipeline Summary Bar                                               */
/* ------------------------------------------------------------------ */

function PipelineSummary({ deals }: { deals: Deal[] }) {
  const activeDeals = deals.filter(d => d.stage !== DealStage.Won && d.stage !== DealStage.Lost)
  const totalValue = activeDeals.reduce((sum, d) => sum + d.amount, 0)
  const weightedValue = activeDeals.reduce((sum, d) => sum + d.amount * (d.winRate / 100), 0)
  const avgDealSize = activeDeals.length ? totalValue / activeDeals.length : 0
  const avgWinRate = activeDeals.length
    ? Math.round(activeDeals.reduce((s, d) => s + d.winRate, 0) / activeDeals.length)
    : 0

  const sparkData = [65, 72, 68, 80, 75, 82, 78, 85, 80, 88]

  const stats = [
    { label: 'PIPELINE VALUE', value: formatCurrency(totalValue), sub: `${activeDeals.length} active deals`, icon: BarChart3, spark: true },
    { label: 'WEIGHTED VALUE', value: formatCurrency(weightedValue), sub: `${avgWinRate}% avg win rate`, icon: TrendingUp },
    { label: 'AVG DEAL SIZE', value: formatCurrency(avgDealSize), sub: '+15% vs last month', icon: Users },
    { label: 'AVG SALES CYCLE', value: '45d', sub: '-5 days vs avg', icon: Timer },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="bg-[#111827] border-b border-[#1E293B] px-6 py-4 shrink-0"
    >
      <div className="flex items-center justify-between gap-6 flex-wrap">
        <div className="flex items-center gap-8 flex-wrap">
          {stats.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08, duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
              className="flex items-center gap-3"
            >
              <div className="flex flex-col">
                <span className="text-label text-[#64748B] text-[10px]">{s.label}</span>
                <div className="flex items-center gap-2">
                  <span className="font-display text-[28px] font-bold text-[#F1F5F9] leading-none">{s.value}</span>
                  {s.spark && <Sparkline data={sparkData} />}
                </div>
                <span className={cn(
                  'text-[11px] mt-0.5',
                  s.sub.includes('+') || s.sub.includes('win rate') ? 'text-[#10B981]' : 'text-[#64748B]'
                )}>
                  {s.sub}
                </span>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Stage dots */}
        <div className="flex items-center gap-4">
          {STAGES.map(stage => {
            const count = deals.filter(d => d.stage === stage.key).length
            return (
              <div key={stage.key} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: stage.color }} />
                <span className="text-xs text-[#94A3B8]">{count}</span>
              </div>
            )
          })}
        </div>
      </div>
    </motion.div>
  )
}

/* ------------------------------------------------------------------ */
/*  Quick View Panel (bottom)                                          */
/* ------------------------------------------------------------------ */

function QuickViewPanel({
  deal,
  onClose,
}: {
  deal: Deal | null
  onClose: () => void
}) {
  return (
    <AnimatePresence>
      {deal && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/20 z-40"
            onClick={onClose}
          />
          {/* Panel */}
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="fixed bottom-0 left-[260px] right-0 h-[300px] bg-[#111827] border-t border-[#334155] shadow-[0_-8px_32px_rgba(0,0,0,0.3)] z-50 rounded-t-card-lg"
          >
            <div className="h-full flex flex-col p-6">
              {/* Close button */}
              <button
                onClick={onClose}
                className="absolute top-4 right-4 p-1.5 rounded-lg text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A2235] transition-colors"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="flex-1 grid grid-cols-3 gap-8">
                {/* Left — Overview */}
                <div>
                  <div className="flex items-center gap-3 mb-3">
                    <h3 className="text-heading-md text-[#F1F5F9]">{deal.customerName}</h3>
                    <StageBadge stage={deal.stage} />
                  </div>
                  <div className="font-display text-[28px] font-bold text-[#F1F5F9] mb-3">
                    ¥{deal.amount.toLocaleString()}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="relative w-12 h-12">
                      <svg className="w-12 h-12 -rotate-90">
                        <circle cx="24" cy="24" r="20" fill="none" stroke="#1A2235" strokeWidth="4" />
                        <circle
                          cx="24" cy="24" r="20" fill="none"
                          stroke={stageMap[deal.stage].color}
                          strokeWidth="4"
                          strokeDasharray={`${2 * Math.PI * 20 * (deal.winRate / 100)} ${2 * Math.PI * 20}`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-[11px] font-semibold text-[#F1F5F9]">
                        {deal.winRate}%
                      </span>
                    </div>
                    <div>
                      <div className="text-xs text-[#64748B]">Assigned</div>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="w-6 h-6 rounded-full bg-[#1A2235] flex items-center justify-center text-[10px] text-[#94A3B8]">
                          {getRepInitials(deal.assignedTo)}
                        </div>
                        <span className="text-sm text-[#94A3B8]">{deal.assignedTo}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Center — Context */}
                <div className="border-l border-[#1E293B] pl-8">
                  <h4 className="text-sm font-semibold text-[#F1F5F9] mb-3">Visit Context</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-start gap-2">
                      <Calendar className="w-4 h-4 text-[#64748B] mt-0.5 shrink-0" />
                      <div>
                        <span className="text-[#94A3B8]">Expected close: </span>
                        <span className="text-[#F1F5F9]">
                          {deal.expectedCloseDate ? format(new Date(deal.expectedCloseDate), 'yyyy-MM-dd') : '-'}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <Clock className="w-4 h-4 text-[#64748B] mt-0.5 shrink-0" />
                      <div>
                        <span className="text-[#94A3B8]">Days in stage: </span>
                        <span className="text-[#F1F5F9]">{getDaysInStage(deal)} days</span>
                      </div>
                    </div>
                    {deal.description && (
                      <p className="text-[#94A3B8] text-xs mt-2 leading-relaxed">{deal.description}</p>
                    )}
                  </div>
                </div>

                {/* Right — Actions */}
                <div className="border-l border-[#1E293B] pl-8">
                  <h4 className="text-sm font-semibold text-[#F1F5F9] mb-3">Quick Actions</h4>
                  <div className="flex flex-wrap gap-2">
                    <button className="px-3 py-1.5 rounded-button border border-[#334155] text-xs text-[#94A3B8] hover:text-[#F1F5F9] hover:border-[#64748B] transition-colors flex items-center gap-1.5">
                      <Edit3 className="w-3 h-3" /> Edit Deal
                    </button>
                    <button className="px-3 py-1.5 rounded-button border border-[#334155] text-xs text-[#94A3B8] hover:text-[#F1F5F9] hover:border-[#64748B] transition-colors flex items-center gap-1.5">
                      <Mail className="w-3 h-3" /> Send Email
                    </button>
                    <button className="px-3 py-1.5 rounded-button bg-[#6366F1] text-xs text-white hover:bg-[#818CF8] transition-colors flex items-center gap-1.5">
                      <Phone className="w-3 h-3" /> Schedule Follow-up
                    </button>
                    {deal.stage !== DealStage.Won && (
                      <button className="px-3 py-1.5 rounded-button bg-[rgba(16,185,129,0.15)] text-xs text-[#10B981] hover:bg-[rgba(16,185,129,0.25)] transition-colors flex items-center gap-1.5">
                        <CheckCircle2 className="w-3 h-3" /> Mark Won
                      </button>
                    )}
                    {deal.stage !== DealStage.Lost && (
                      <button className="px-3 py-1.5 rounded-button bg-[rgba(239,68,68,0.15)] text-xs text-[#EF4444] hover:bg-[rgba(239,68,68,0.25)] transition-colors flex items-center gap-1.5">
                        <XCircle className="w-3 h-3" /> Mark Lost
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

/* ------------------------------------------------------------------ */
/*  Stage Badge                                                        */
/* ------------------------------------------------------------------ */

function StageBadge({ stage }: { stage: DealStage }) {
  const cfg = stageMap[stage]
  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium"
      style={{
        backgroundColor: `${cfg.color}20`,
        color: cfg.color,
        boxShadow: `0 0 8px ${cfg.glow}`,
      }}
    >
      {cfg.label}
    </span>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Pipeline Page                                                 */
/* ------------------------------------------------------------------ */

export default function Pipeline() {
  const [allDeals, setAllDeals] = useState<Deal[]>(initialDeals)
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [dragOverStage, setDragOverStage] = useState<DealStage | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const dealsByStage = useMemo(() => {
    const map: Record<DealStage, Deal[]> = {
      [DealStage.InitialContact]: [],
      [DealStage.NeedsConfirmed]: [],
      [DealStage.SolutionEval]: [],
      [DealStage.Negotiation]: [],
      [DealStage.Won]: [],
      [DealStage.Lost]: [],
    }
    for (const d of allDeals) {
      map[d.stage].push(d)
    }
    return map
  }, [allDeals])

  const activeDeal = useMemo(() =>
    activeId ? allDeals.find(d => d.id === activeId) ?? null : null
  , [activeId, allDeals])

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as string)
  }, [])

  const handleDragOver = useCallback((event: DragOverEvent) => {
    const overId = event.over?.id
    if (!overId) { setDragOverStage(null); return }
    const stage = STAGES.find(s => s.key === overId)
    if (stage) setDragOverStage(stage.key)
  }, [])

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event
    setActiveId(null)
    setDragOverStage(null)
    if (!over) return

    const dealId = active.id as string
    const overId = over.id as string

    // Check if dropped on a stage column
    const targetStage = STAGES.find(s => s.key === overId)
    if (targetStage) {
      setAllDeals(prev => prev.map(d =>
        d.id === dealId ? { ...d, stage: targetStage.key, updatedAt: new Date().toISOString() } : d
      ))
      return
    }

    // Sortable reorder within same column
    const overDeal = allDeals.find(d => d.id === overId)
    if (!overDeal) return
    const activeDealData = allDeals.find(d => d.id === dealId)
    if (!activeDealData || activeDealData.stage !== overDeal.stage) return

    const stageDeals = dealsByStage[overDeal.stage]
    const oldIndex = stageDeals.findIndex(d => d.id === dealId)
    const newIndex = stageDeals.findIndex(d => d.id === overId)
    if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
      const reordered = arrayMove(stageDeals, oldIndex, newIndex)
      setAllDeals(prev => {
        const others = prev.filter(d => d.stage !== overDeal.stage)
        return [...others, ...reordered]
      })
    }
  }, [allDeals, dealsByStage])

  return (
    <div className="flex flex-col h-[calc(100dvh-64px)] -mx-8 -mt-8">
      {/* Summary Bar */}
      <PipelineSummary deals={allDeals} />

      {/* Kanban Board */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div
          className="flex-1 overflow-x-auto overflow-y-hidden relative"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        >
          <div className="flex gap-4 h-full p-4 min-w-fit">
            {STAGES.map((stage, colIdx) => (
              <PipelineColumn
                key={stage.key}
                stage={stage}
                deals={dealsByStage[stage.key]}
                colIdx={colIdx}
                isDragOver={dragOverStage === stage.key}
                onCardClick={setSelectedDeal}
              />
            ))}
          </div>
        </div>

        <DragOverlay>
          {activeDeal ? <DealCardOverlay deal={activeDeal} /> : null}
        </DragOverlay>
      </DndContext>

      {/* Quick View Panel */}
      <QuickViewPanel
        deal={selectedDeal}
        onClose={() => setSelectedDeal(null)}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Pipeline Column                                                    */
/* ------------------------------------------------------------------ */

function PipelineColumn({
  stage,
  deals,
  colIdx,
  isDragOver,
  onCardClick,
}: {
  stage: StageConfig
  deals: Deal[]
  colIdx: number
  isDragOver: boolean
  onCardClick: (deal: Deal) => void
}) {
  const { setNodeRef, isOver } = useSortable({
    id: stage.key,
    data: { type: 'column', stage: stage.key },
  })

  const showDropHighlight = isOver || isDragOver

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        delay: colIdx * 0.08,
        duration: 0.4,
        ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
      }}
      className="flex flex-col w-[300px] min-w-[300px] max-w-[360px] h-full rounded-card overflow-hidden"
    >
      {/* Column Header */}
      <div
        className="shrink-0 h-14 flex items-center justify-between px-4 border-t-[3px]"
        style={{
          borderTopColor: stage.color,
          backgroundColor: `${stage.color}10`,
        }}
      >
        <div className="flex items-center gap-2.5">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: stage.color }} />
          <span className="text-heading-sm text-[#F1F5F9] text-sm font-semibold">{stage.label}</span>
        </div>
        <motion.span
          key={deals.length}
          initial={{ scale: 1.3 }}
          animate={{ scale: 1 }}
          className="flex items-center justify-center w-7 h-7 rounded-full bg-[#1A2235] text-xs text-[#94A3B8] font-medium"
        >
          {deals.length}
        </motion.span>
      </div>

      {/* Column Body */}
      <div
        ref={setNodeRef}
        className={cn(
          'flex-1 overflow-y-auto p-3 space-y-3 min-h-0 transition-all duration-200',
          showDropHighlight && 'ring-2 ring-inset rounded-b-card'
        )}
        style={showDropHighlight ? { boxShadow: `inset 0 0 0 2px ${stage.color}` } : {}}
      >
        <SortableContext
          items={deals.map(d => d.id)}
          strategy={verticalListSortingStrategy}
        >
          <AnimatePresence mode="popLayout">
            {deals.map((deal, cardIdx) => (
              <motion.div
                key={deal.id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{
                  delay: 0.4 + colIdx * 0.1 + cardIdx * 0.04,
                  duration: 0.3,
                  ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
                }}
              >
                <SortableDealCard deal={deal} onClick={onCardClick} />
              </motion.div>
            ))}
          </AnimatePresence>
        </SortableContext>

        {/* Empty state */}
        {deals.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 border-2 border-dashed border-[#1E293B] rounded-card-sm">
            <span className="text-xs text-[#64748B]">Drop deals here</span>
          </div>
        )}

        {/* Add button */}
        <button className="w-full flex items-center justify-center gap-1.5 py-2 rounded-card-sm border border-dashed border-[#1E293B] text-[#64748B] hover:text-[#94A3B8] hover:border-[#334155] transition-colors text-xs">
          <Plus className="w-3.5 h-3.5" /> Add deal
        </button>
      </div>
    </motion.div>
  )
}
