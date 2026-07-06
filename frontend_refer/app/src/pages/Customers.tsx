import { useState, useMemo, useCallback } from 'react'
import type { ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  X,
  Building2,
  Flag,
  Kanban,
  ArrowUpDown,
  ChevronDown,
  ChevronRight,
  Plus,
  Phone,
  Mail,
  Calendar,
  Users,
  BarChart3,
  Clock,
  TrendingUp,
  CheckCircle2,
} from 'lucide-react'
import { format, differenceInDays } from 'date-fns'
import { cn } from '@/lib/utils'
import { DealStage } from '@/types'
import type { Customer, Deal } from '@/types'
import { customers as initialCustomers, deals } from '@/data/mockData'

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const INDUSTRIES = ['Technology', 'Software', 'Cloud Services', 'Data Analytics', 'AI/ML', 'Aerospace', 'IoT', 'Manufacturing', 'Consulting', 'Consumer Goods']

const PRIORITIES = [
  { label: 'High', value: 'high', color: '#EF4444' },
  { label: 'Medium', value: 'medium', color: '#F59E0B' },
  { label: 'Low', value: 'low', color: '#3B82F6' },
]

const STAGE_OPTIONS = [
  { key: DealStage.InitialContact, label: '初次接触', color: '#8B5CF6' },
  { key: DealStage.NeedsConfirmed,  label: '需求确认', color: '#3B82F6' },
  { key: DealStage.SolutionEval,    label: '方案评估', color: '#06B6D4' },
  { key: DealStage.Negotiation,     label: '商务谈判', color: '#F59E0B' },
  { key: DealStage.Won,             label: '赢单',     color: '#10B981' },
  { key: DealStage.Lost,            label: '输单',     color: '#EF4444' },
]

const SORT_OPTIONS = [
  { label: '最近拜访', value: 'lastVisit' },
  { label: '交易价值', value: 'dealValue' },
  { label: '公司名称', value: 'name' },
  { label: '优先级',   value: 'priority' },
]

/* ------------------------------------------------------------------ */
/*  Mock enriched customer data                                        */
/* ------------------------------------------------------------------ */

interface EnrichedCustomer extends Customer {
  priority: 'high' | 'medium' | 'low'
  companySize: string
  painPoints: string[]
  keyContact: { name: string; title: string }
  stage?: DealStage
  dealAmount?: number
  visits: { date: string; purpose: string; outcome: string }[]
  contacts: { name: string; title: string; phone: string; email: string; role: string }[]
}

const mockPainPoints: Record<string, string[]> = {
  'c1': ['Reporting speed', 'Month-end delay', 'Data silos'],
  'c2': ['Integration complexity', 'Data migration'],
  'c3': ['Scalability concerns', 'Security review', 'Multi-region sync'],
  'c4': ['Slow analytics', 'Data fragmentation'],
  'c5': ['AI readiness', 'Budget uncertainty'],
  'c6': ['Compliance requirements', 'Legacy system migration'],
  'c7': ['Edge deployment', 'Latency concerns'],
  'c8': ['Workflow automation', 'Limited resources'],
}

const mockCompanySizes: Record<string, string> = {
  'c1': '201-1000 employees',
  'c2': '51-200 employees',
  'c3': '1000+ employees',
  'c4': '51-200 employees',
  'c5': '201-1000 employees',
  'c6': '1000+ employees',
  'c7': '201-1000 employees',
  'c8': '11-50 employees',
}

const mockPriorities: Record<string, 'high' | 'medium' | 'low'> = {
  'c1': 'high', 'c2': 'medium', 'c3': 'high', 'c4': 'low',
  'c5': 'medium', 'c6': 'high', 'c7': 'low', 'c8': 'medium',
}

const mockContacts: Record<string, { name: string; title: string; phone: string; email: string; role: string }[]> = {
  'c1': [
    { name: 'John Smith', title: 'IT Director', phone: '+86 138-0000-1001', email: 'john.smith@acme.com', role: 'Decision Maker' },
    { name: 'Lisa Chen', title: 'Procurement Manager', phone: '+86 138-0000-1010', email: 'lisa@acme.com', role: 'Influencer' },
  ],
  'c2': [
    { name: 'Emily Chen', title: 'VP Engineering', phone: '+86 139-0000-2002', email: 'emily@techstart.io', role: 'Decision Maker' },
  ],
  'c3': [
    { name: 'Michael Wang', title: 'CTO', phone: '+86 137-0000-3003', email: 'm.wang@cloudmax.com', role: 'Decision Maker' },
    { name: 'Sarah Liu', title: 'DevOps Lead', phone: '+86 137-0000-3030', email: 'sarah@cloudmax.com', role: 'Technical Evaluator' },
  ],
  'c4': [
    { name: 'Sarah Li', title: 'Data Science Lead', phone: '+86 136-0000-4004', email: 'sarah@dataflow.cn', role: 'Decision Maker' },
  ],
  'c5': [
    { name: 'David Zhang', title: 'CEO', phone: '+86 135-0000-5005', email: 'david@nexgen.tech', role: 'Decision Maker' },
    { name: 'Anna Wu', title: 'Engineering Manager', phone: '+86 135-0000-5050', email: 'anna@nexgen.tech', role: 'Technical Evaluator' },
  ],
  'c6': [
    { name: 'Linda Liu', title: 'VP Operations', phone: '+86 134-0000-6006', email: 'linda@bluesky.com', role: 'Decision Maker' },
  ],
  'c7': [
    { name: 'Robert Huang', title: 'Director of IoT', phone: '+86 133-0000-7007', email: 'r.huang@smartedge.io', role: 'Decision Maker' },
    { name: 'Jane Park', title: 'Systems Engineer', phone: '+86 133-0000-7070', email: 'jane@smartedge.io', role: 'Technical Evaluator' },
  ],
  'c8': [
    { name: 'Karen Zhao', title: 'CTO', phone: '+86 132-0000-8008', email: 'karen@alphalogix.com', role: 'Decision Maker' },
  ],
}

const mockVisits: Record<string, { date: string; purpose: string; outcome: string }[]> = {
  'c1': [
    { date: '2026-02-15T10:00:00Z', purpose: 'Quarterly review and expansion discussion', outcome: 'Positive - proposal requested' },
    { date: '2026-01-20T14:00:00Z', purpose: 'Product demo for premium features', outcome: 'Customer interested' },
    { date: '2025-12-10T09:00:00Z', purpose: 'Initial discovery meeting', outcome: 'Requirements gathered' },
  ],
  'c2': [
    { date: '2026-02-12T10:00:00Z', purpose: 'Cloud migration planning', outcome: 'Migration plan approved' },
    { date: '2026-01-05T15:00:00Z', purpose: 'Technical deep dive', outcome: 'Architecture confirmed' },
  ],
  'c3': [
    { date: '2026-02-14T14:00:00Z', purpose: 'Platform demo and technical deep-dive', outcome: 'Pending security review' },
    { date: '2026-01-28T10:00:00Z', purpose: 'Security discussion', outcome: 'Security requirements documented' },
  ],
  'c4': [
    { date: '2026-02-14T11:00:00Z', purpose: 'Initial discovery meeting', outcome: 'Discovery complete' },
  ],
  'c5': [
    { date: '2026-02-10T09:30:00Z', purpose: 'AI integration requirements gathering', outcome: 'Requirements documented' },
    { date: '2026-01-15T14:00:00Z', purpose: 'Budget discussion', outcome: 'Budget confirmed for Q2' },
  ],
  'c6': [
    { date: '2026-02-08T15:00:00Z', purpose: 'Solution evaluation - Phase 2', outcome: 'Evaluation ongoing' },
    { date: '2026-01-22T10:00:00Z', purpose: 'Compliance review', outcome: 'Compliance requirements clarified' },
  ],
  'c7': [
    { date: '2026-01-25T09:00:00Z', purpose: 'Final negotiation and pricing', outcome: 'Deal closed' },
    { date: '2025-12-18T14:00:00Z', purpose: 'Technical evaluation', outcome: 'Technical approval granted' },
  ],
  'c8': [
    { date: '2026-02-05T10:00:00Z', purpose: 'Workflow automation demo', outcome: 'Follow-up scheduled' },
  ],
}

function enrichCustomer(c: Customer): EnrichedCustomer {
  const customerDeals = deals.filter(d => d.customerId === c.id)
  const activeDeal = customerDeals[0]
  return {
    ...c,
    priority: mockPriorities[c.id] || 'medium',
    companySize: mockCompanySizes[c.id] || 'Unknown',
    painPoints: mockPainPoints[c.id] || [],
    keyContact: { name: c.contactName, title: 'Key Contact' },
    stage: activeDeal?.stage,
    dealAmount: activeDeal?.amount,
    visits: mockVisits[c.id] || [],
    contacts: mockContacts[c.id] || [],
  }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatCurrency(n?: number): string {
  if (!n) return '¥0'
  if (n >= 1_000_000) return `¥${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `¥${Math.round(n / 1_000)}K`
  return `¥${n}`
}

function getInitials(name: string): string {
  return name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()
}

function getDaysAgo(dateStr?: string): string {
  if (!dateStr) return 'Never'
  const days = differenceInDays(new Date(), new Date(dateStr))
  if (days === 0) return 'Today'
  if (days === 1) return '1 day ago'
  return `${days} days ago`
}

function getStageProgress(stage?: DealStage): number {
  const map: Record<DealStage, number> = {
    [DealStage.InitialContact]: 10,
    [DealStage.NeedsConfirmed]: 30,
    [DealStage.SolutionEval]: 50,
    [DealStage.Negotiation]: 75,
    [DealStage.Won]: 100,
    [DealStage.Lost]: 0,
  }
  return stage ? map[stage] : 0
}

/* ------------------------------------------------------------------ */
/*  Priority Badge                                                     */
/* ------------------------------------------------------------------ */

function PriorityBadge({ priority }: { priority: string }) {
  const cfg = PRIORITIES.find(p => p.value === priority)
  const color = cfg?.color || '#64748B'
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
      <span style={{ color }}>{cfg?.label || priority}</span>
    </span>
  )
}

/* ------------------------------------------------------------------ */
/*  Stage Badge                                                        */
/* ------------------------------------------------------------------ */

function StageBadgeMini({ stage }: { stage?: DealStage }) {
  if (!stage) return null
  const cfg = STAGE_OPTIONS.find(s => s.key === stage)
  if (!cfg) return null
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ backgroundColor: `${cfg.color}20`, color: cfg.color }}
    >
      {cfg.label}
    </span>
  )
}

/* ------------------------------------------------------------------ */
/*  Empty State                                                        */
/* ------------------------------------------------------------------ */

function EmptyCustomersState({ onAdd }: { onAdd: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col items-center justify-center py-20 max-w-[400px] mx-auto text-center"
    >
      <motion.div
        animate={{ y: [0, -8, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        className="mb-6"
      >
        <Users className="w-16 h-16 text-[#64748B] stroke-[1.5]" />
      </motion.div>
      <h3 className="text-heading-md text-[#94A3B8] mb-2">No customers found</h3>
      <p className="text-body-md text-[#64748B] mb-6">
        Try adjusting your filters or add your first customer.
      </p>
      <button
        onClick={onAdd}
        className="px-4 py-2 rounded-button bg-[#6366F1] text-white text-sm font-medium hover:bg-[#818CF8] transition-colors flex items-center gap-2"
      >
        <Plus className="w-4 h-4" /> Add Customer
      </button>
    </motion.div>
  )
}

/* ------------------------------------------------------------------ */
/*  Customer Detail Drawer                                             */
/* ------------------------------------------------------------------ */

type TabId = 'overview' | 'visits' | 'deals' | 'contacts'

const TABS: { id: TabId; label: string }[] = [
  { id: 'overview', label: '概览' },
  { id: 'visits', label: '拜访记录' },
  { id: 'deals', label: '商机' },
  { id: 'contacts', label: '联系人' },
]

function CustomerDetailDrawer({
  customer,
  onClose,
}: {
  customer: EnrichedCustomer | null
  onClose: () => void
}) {
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  const customerDeals = useMemo(() =>
    deals.filter(d => d.customerId === customer?.id)
  , [customer])

  if (!customer) return null

  return (
    <AnimatePresence>
      {customer && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="fixed top-0 right-0 w-[480px] h-full bg-[#111827] border-l border-[#1E293B] z-50 overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="shrink-0 px-6 py-5 border-b border-[#1E293B]">
              <div className="flex items-start justify-between mb-1">
                <div>
                  <h2 className="text-heading-lg text-[#F1F5F9] mb-1">{customer.name}</h2>
                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs bg-[#1A2235] text-[#94A3B8]">
                      {customer.industry}
                    </span>
                    <span className="text-xs text-[#64748B]">{customer.companySize}</span>
                    <PriorityBadge priority={customer.priority} />
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A2235] transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div className="shrink-0 px-6 border-b border-[#1E293B]">
              <div className="flex gap-0">
                {TABS.map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      'relative px-4 py-3 text-sm font-medium transition-colors',
                      activeTab === tab.id ? 'text-[#6366F1]' : 'text-[#64748B] hover:text-[#94A3B8]'
                    )}
                  >
                    {tab.label}
                    {activeTab === tab.id && (
                      <motion.div
                        layoutId="customerTabIndicator"
                        className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#6366F1]"
                        transition={{ duration: 0.2 }}
                      />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto p-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  {activeTab === 'overview' && <OverviewTab customer={customer} deals={customerDeals} />}
                  {activeTab === 'visits' && <VisitsTab customer={customer} />}
                  {activeTab === 'deals' && <DealsTab deals={customerDeals} />}
                  {activeTab === 'contacts' && <ContactsTab customer={customer} />}
                </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

/* ------------------------------------------------------------------ */
/*  Tab Components                                                     */
/* ------------------------------------------------------------------ */

function OverviewTab({ customer, deals }: { customer: EnrichedCustomer; deals: Deal[] }) {
  const totalValue = deals.reduce((s, d) => s + d.amount, 0)
  const avgWinRate = deals.length ? Math.round(deals.reduce((s, d) => s + d.winRate, 0) / deals.length) : 0

  return (
    <div className="space-y-6">
      {/* Metrics */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total Visits', value: String(customer.visits.length), icon: Calendar },
          { label: 'Active Deals', value: String(deals.length), icon: BarChart3 },
          { label: 'Pipeline Value', value: formatCurrency(totalValue), icon: TrendingUp },
        ].map(m => (
          <div key={m.label} className="bg-[#1A2235] rounded-card-sm p-3 border border-[#1E293B]">
            <div className="flex items-center gap-1.5 mb-1">
              <m.icon className="w-3.5 h-3.5 text-[#64748B]" />
              <span className="text-[10px] text-[#64748B] uppercase tracking-wider">{m.label}</span>
            </div>
            <span className="font-display text-xl font-bold text-[#F1F5F9]">{m.value}</span>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div>
        <h4 className="text-sm font-semibold text-[#F1F5F9] mb-2">Customer Summary</h4>
        <p className="text-sm text-[#94A3B8] leading-relaxed">
          {customer.name} is a {customer.priority} priority customer in the {customer.industry} industry.
          They have {customer.visits.length} recorded visits and {deals.length} active deal{deals.length !== 1 ? 's' : ''}.
          {customer.painPoints.length > 0 && ` Key concerns include ${customer.painPoints.join(', ')}.`}
        </p>
      </div>

      {/* Pain Points */}
      {customer.painPoints.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-[#F1F5F9] mb-2">Known Pain Points</h4>
          <div className="flex flex-wrap gap-2">
            {customer.painPoints.map((pp, i) => (
              <span
                key={i}
                className="inline-flex items-center px-2.5 py-1 rounded-full text-xs bg-[#1A2235] text-[#94A3B8] border border-[#1E293B]"
              >
                {pp}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Deal Performance */}
      {deals.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-[#F1F5F9] mb-2">Deal Performance</h4>
          <div className="bg-[#1A2235] rounded-card-sm p-4 border border-[#1E293B]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#64748B]">Average Win Rate</span>
              <span className="text-sm font-semibold text-[#F1F5F9]">{avgWinRate}%</span>
            </div>
            <div className="h-2 bg-[#0D1321] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-[#6366F1]"
                style={{ width: `${avgWinRate}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* First Contact */}
      <div className="flex items-center gap-2 text-xs text-[#64748B]">
        <Clock className="w-3.5 h-3.5" />
        <span>First contact: {format(new Date(customer.createdAt), 'MMM yyyy')}</span>
      </div>
    </div>
  )
}

function VisitsTab({ customer }: { customer: EnrichedCustomer }) {
  const sortedVisits = [...customer.visits].sort((a, b) =>
    new Date(b.date).getTime() - new Date(a.date).getTime()
  )

  return (
    <div className="space-y-4">
      {sortedVisits.length === 0 ? (
        <div className="text-center py-12 text-[#64748B] text-sm">No visits recorded</div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-[15px] top-0 bottom-0 w-[2px] bg-[#1E293B]" />

          {sortedVisits.map((visit, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08 }}
              className="relative flex gap-4 mb-5 last:mb-0"
            >
              {/* Dot */}
              <div className="relative z-10 w-8 h-8 rounded-full bg-[#1A2235] border-2 border-[#6366F1] flex items-center justify-center shrink-0">
                <Calendar className="w-3.5 h-3.5 text-[#6366F1]" />
              </div>

              {/* Content */}
              <div className="flex-1 bg-[#1A2235] rounded-card-sm p-4 border border-[#1E293B]">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-[#F1F5F9]">
                    {format(new Date(visit.date), 'yyyy-MM-dd HH:mm')}
                  </span>
                  <CheckCircle2 className="w-4 h-4 text-[#10B981]" />
                </div>
                <p className="text-sm text-[#94A3B8] mb-2">{visit.purpose}</p>
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-[#64748B]">Outcome:</span>
                  <span className="text-[11px] text-[#10B981]">{visit.outcome}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

function DealsTab({ deals: customerDeals }: { deals: Deal[] }) {
  if (customerDeals.length === 0) {
    return <div className="text-center py-12 text-[#64748B] text-sm">No deals for this customer</div>
  }

  return (
    <div className="space-y-3">
      {customerDeals.map((deal, i) => {
        const stageCfg = STAGE_OPTIONS.find(s => s.key === deal.stage)
        return (
          <motion.div
            key={deal.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="bg-[#1A2235] rounded-card-sm p-4 border border-[#1E293B]"
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <span className="text-sm font-semibold text-[#F1F5F9] block mb-1">{deal.customerName}</span>
                {stageCfg && (
                  <span
                    className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
                    style={{ backgroundColor: `${stageCfg.color}20`, color: stageCfg.color }}
                  >
                    {stageCfg.label}
                  </span>
                )}
              </div>
              <span className="text-sm font-bold text-[#F1F5F9]">¥{deal.amount.toLocaleString()}</span>
            </div>

            {/* Win rate */}
            <div className="mb-2">
              <div className="h-1.5 bg-[#0D1321] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${deal.winRate}%`, backgroundColor: stageCfg?.color || '#6366F1' }}
                />
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-[11px] text-[#64748B]">{deal.winRate}% win rate</span>
                <span className="text-[11px] text-[#64748B]">
                  Close: {deal.expectedCloseDate ? format(new Date(deal.expectedCloseDate), 'yyyy-MM-dd') : '-'}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 mt-2">
              <div className="w-5 h-5 rounded-full bg-[#0D1321] flex items-center justify-center text-[9px] text-[#94A3B8]">
                {getInitials(deal.assignedTo)}
              </div>
              <span className="text-xs text-[#94A3B8]">{deal.assignedTo}</span>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}

function ContactsTab({ customer }: { customer: EnrichedCustomer }) {
  if (customer.contacts.length === 0) {
    return <div className="text-center py-12 text-[#64748B] text-sm">No contacts recorded</div>
  }

  return (
    <div className="space-y-3">
      {customer.contacts.map((contact, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08 }}
          className="bg-[#1A2235] rounded-card-sm p-4 border border-[#1E293B]"
        >
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-full bg-[#6366F1]/20 flex items-center justify-center text-sm font-semibold text-[#818CF8] shrink-0">
              {getInitials(contact.name)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-sm font-semibold text-[#F1F5F9]">{contact.name}</span>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#0D1321] text-[#94A3B8]">
                  {contact.role}
                </span>
              </div>
              <span className="text-xs text-[#94A3B8] block mb-2">{contact.title}</span>
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5 text-[#64748B]">
                  <Phone className="w-3 h-3" />
                  <span className="text-xs">{contact.phone}</span>
                </div>
                <div className="flex items-center gap-1.5 text-[#64748B]">
                  <Mail className="w-3 h-3" />
                  <span className="text-xs truncate">{contact.email}</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      ))}

      <button className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-card-sm border border-dashed border-[#1E293B] text-[#64748B] hover:text-[#94A3B8] hover:border-[#334155] transition-colors text-sm">
        <Plus className="w-4 h-4" /> Add Contact
      </button>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Customers Page                                                */
/* ------------------------------------------------------------------ */

export default function Customers() {
  const [customers] = useState<Customer[]>(initialCustomers)
  const [search, setSearch] = useState('')
  const [industryFilter, setIndustryFilter] = useState<string[]>([])
  const [priorityFilter, setPriorityFilter] = useState<string[]>([])
  const [stageFilter, setStageFilter] = useState<string[]>([])
  const [sortBy, setSortBy] = useState('lastVisit')
  const [selectedCustomer, setSelectedCustomer] = useState<EnrichedCustomer | null>(null)

  // Filter dropdown state
  const [openFilter, setOpenFilter] = useState<string | null>(null)

  const enrichedCustomers = useMemo(() =>
    customers.map(enrichCustomer)
  , [customers])

  const filteredCustomers = useMemo(() => {
    let result = [...enrichedCustomers]

    // Search
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(c =>
        c.name.toLowerCase().includes(q) ||
        c.industry.toLowerCase().includes(q) ||
        c.contactName.toLowerCase().includes(q)
      )
    }

    // Industry filter
    if (industryFilter.length > 0) {
      result = result.filter(c => industryFilter.includes(c.industry))
    }

    // Priority filter
    if (priorityFilter.length > 0) {
      result = result.filter(c => priorityFilter.includes(c.priority))
    }

    // Stage filter
    if (stageFilter.length > 0) {
      result = result.filter(c => c.stage && stageFilter.includes(c.stage))
    }

    // Sort
    switch (sortBy) {
      case 'lastVisit':
        result.sort((a, b) => {
          const da = a.lastVisitDate ? new Date(a.lastVisitDate).getTime() : 0
          const db = b.lastVisitDate ? new Date(b.lastVisitDate).getTime() : 0
          return db - da
        })
        break
      case 'dealValue':
        result.sort((a, b) => (b.dealAmount || 0) - (a.dealAmount || 0))
        break
      case 'name':
        result.sort((a, b) => a.name.localeCompare(b.name))
        break
      case 'priority': {
        const order = { high: 0, medium: 1, low: 2 }
        result.sort((a, b) => order[a.priority] - order[b.priority])
        break
      }
    }

    return result
  }, [enrichedCustomers, search, industryFilter, priorityFilter, stageFilter, sortBy])

  const activeFilters = useMemo(() => {
    const filters: { label: string; onRemove: () => void }[] = []
    industryFilter.forEach(f => {
      filters.push({ label: f, onRemove: () => setIndustryFilter(prev => prev.filter(x => x !== f)) })
    })
    priorityFilter.forEach(f => {
      const cfg = PRIORITIES.find(p => p.value === f)
      filters.push({ label: cfg?.label || f, onRemove: () => setPriorityFilter(prev => prev.filter(x => x !== f)) })
    })
    stageFilter.forEach(f => {
      const cfg = STAGE_OPTIONS.find(s => s.key === f)
      filters.push({ label: cfg?.label || f, onRemove: () => setStageFilter(prev => prev.filter(x => x !== f)) })
    })
    return filters
  }, [industryFilter, priorityFilter, stageFilter])

  const toggleFilter = useCallback((set: React.Dispatch<React.SetStateAction<string[]>>, value: string) => {
    set(prev => prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value])
  }, [])

  const clearAllFilters = useCallback(() => {
    setIndustryFilter([])
    setPriorityFilter([])
    setStageFilter([])
    setSearch('')
  }, [])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <motion.h2
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="text-display-md text-[#F1F5F9]"
        >
          客户中心
        </motion.h2>
        <motion.button
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="px-4 py-2 rounded-button bg-[#6366F1] text-white text-sm font-medium hover:bg-[#818CF8] transition-colors flex items-center gap-2"
        >
          <Plus className="w-4 h-4" /> 新建客户
        </motion.button>
      </div>

      {/* Search & Filter Bar */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
        className="bg-[#111827] rounded-card p-4 border border-[#1E293B]"
      >
        <div className="flex items-center gap-3 flex-wrap">
          {/* Search */}
          <div className="relative flex-1 min-w-[280px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by company name, contact, or industry..."
              className="w-full h-11 pl-10 pr-10 rounded-input bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155] transition-colors"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#F1F5F9]"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Industry Filter */}
          <FilterDropdown
            icon={<Building2 className="w-4 h-4" />}
            label="Industry"
            isOpen={openFilter === 'industry'}
            onToggle={() => setOpenFilter(openFilter === 'industry' ? null : 'industry')}
            onClose={() => setOpenFilter(null)}
          >
            {INDUSTRIES.map(ind => (
              <label key={ind} className="flex items-center gap-2 px-3 py-2 text-sm text-[#94A3B8] hover:bg-[#1A2235] cursor-pointer rounded">
                <input
                  type="checkbox"
                  checked={industryFilter.includes(ind)}
                  onChange={() => toggleFilter(setIndustryFilter, ind)}
                  className="rounded border-[#334155] bg-[#0D1321] text-[#6366F1] focus:ring-[#6366F1]"
                />
                {ind}
              </label>
            ))}
          </FilterDropdown>

          {/* Priority Filter */}
          <FilterDropdown
            icon={<Flag className="w-4 h-4" />}
            label="Priority"
            isOpen={openFilter === 'priority'}
            onToggle={() => setOpenFilter(openFilter === 'priority' ? null : 'priority')}
            onClose={() => setOpenFilter(null)}
          >
            {PRIORITIES.map(p => (
              <label key={p.value} className="flex items-center gap-2 px-3 py-2 text-sm text-[#94A3B8] hover:bg-[#1A2235] cursor-pointer rounded">
                <input
                  type="checkbox"
                  checked={priorityFilter.includes(p.value)}
                  onChange={() => toggleFilter(setPriorityFilter, p.value)}
                  className="rounded border-[#334155] bg-[#0D1321] text-[#6366F1] focus:ring-[#6366F1]"
                />
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
                {p.label}
              </label>
            ))}
          </FilterDropdown>

          {/* Stage Filter */}
          <FilterDropdown
            icon={<Kanban className="w-4 h-4" />}
            label="Stage"
            isOpen={openFilter === 'stage'}
            onToggle={() => setOpenFilter(openFilter === 'stage' ? null : 'stage')}
            onClose={() => setOpenFilter(null)}
          >
            {STAGE_OPTIONS.map(s => (
              <label key={s.key} className="flex items-center gap-2 px-3 py-2 text-sm text-[#94A3B8] hover:bg-[#1A2235] cursor-pointer rounded">
                <input
                  type="checkbox"
                  checked={stageFilter.includes(s.key)}
                  onChange={() => toggleFilter(setStageFilter, s.key)}
                  className="rounded border-[#334155] bg-[#0D1321] text-[#6366F1] focus:ring-[#6366F1]"
                />
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
                {s.label}
              </label>
            ))}
          </FilterDropdown>

          {/* Sort */}
          <FilterDropdown
            icon={<ArrowUpDown className="w-4 h-4" />}
            label={SORT_OPTIONS.find(s => s.value === sortBy)?.label || 'Sort'}
            isOpen={openFilter === 'sort'}
            onToggle={() => setOpenFilter(openFilter === 'sort' ? null : 'sort')}
            onClose={() => setOpenFilter(null)}
          >
            {SORT_OPTIONS.map(s => (
              <button
                key={s.value}
                onClick={() => { setSortBy(s.value); setOpenFilter(null) }}
                className={cn(
                  'w-full text-left px-3 py-2 text-sm rounded hover:bg-[#1A2235] transition-colors',
                  sortBy === s.value ? 'text-[#6366F1] font-medium' : 'text-[#94A3B8]'
                )}
              >
                {s.label}
              </button>
            ))}
          </FilterDropdown>
        </div>

        {/* Active filter badges */}
        <AnimatePresence>
          {activeFilters.length > 0 && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="flex items-center gap-2 mt-3 flex-wrap overflow-hidden"
            >
              {activeFilters.map((f, i) => (
                <motion.span
                  key={`${f.label}-${i}`}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs bg-[#1A2235] text-[#94A3B8] border border-[#1E293B]"
                >
                  {f.label}
                  <button onClick={f.onRemove} className="hover:text-[#F1F5F9]">
                    <X className="w-3 h-3" />
                  </button>
                </motion.span>
              ))}
              <button
                onClick={clearAllFilters}
                className="text-xs text-[#6366F1] hover:text-[#818CF8] transition-colors ml-1"
              >
                Clear all
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Customer Grid */}
      {filteredCustomers.length === 0 ? (
        <EmptyCustomersState onAdd={() => {}} />
      ) : (
        <motion.div
          layout
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
        >
          <AnimatePresence mode="popLayout">
            {filteredCustomers.map((customer, i) => (
              <motion.div
                key={customer.id}
                layout
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{
                  delay: i * 0.05,
                  duration: 0.4,
                  ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
                }}
              >
                <CustomerCard customer={customer} onClick={() => setSelectedCustomer(customer)} />
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      )}

      {/* Detail Drawer */}
      <CustomerDetailDrawer
        customer={selectedCustomer}
        onClose={() => setSelectedCustomer(null)}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Customer Card                                                      */
/* ------------------------------------------------------------------ */

function CustomerCard({
  customer,
  onClick,
}: {
  customer: EnrichedCustomer
  onClick: () => void
}) {
  const stageCfg = STAGE_OPTIONS.find(s => s.key === customer.stage)
  const stageProgress = getStageProgress(customer.stage)

  return (
    <motion.div
      whileHover={{ y: -4, borderColor: '#334155' }}
      transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] as [number, number, number, number] }}
      onClick={onClick}
      className="bg-gradient-to-b from-[rgba(26,34,53,0.8)] to-[rgba(17,24,39,0.95)] border border-[#1E293B] rounded-card p-5 cursor-pointer min-h-[200px] flex flex-col hover:shadow-[0_12px_32px_rgba(0,0,0,0.2)]"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <h3 className="text-heading-sm text-[#F1F5F9] truncate pr-2 text-base font-semibold">{customer.name}</h3>
        <PriorityBadge priority={customer.priority} />
      </div>

      {/* Industry & Size */}
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] bg-[#1A2235] text-[#94A3B8]">
          {customer.industry}
        </span>
        <span className="text-[11px] text-[#64748B]">{customer.companySize}</span>
      </div>

      {/* Key Contact */}
      <div className="flex items-center gap-2.5 mb-3">
        <div className="w-8 h-8 rounded-full bg-[#6366F1]/20 flex items-center justify-center text-xs font-semibold text-[#818CF8]">
          {getInitials(customer.keyContact.name)}
        </div>
        <div>
          <div className="text-sm font-medium text-[#F1F5F9]">{customer.keyContact.name}</div>
          <div className="text-[11px] text-[#64748B]">{customer.keyContact.title}</div>
        </div>
      </div>

      {/* Deal Info */}
      {customer.dealAmount && stageCfg && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1.5">
            <StageBadgeMini stage={customer.stage} />
            <span className="text-sm font-bold text-[#F1F5F9]">{formatCurrency(customer.dealAmount)}</span>
          </div>
          <div className="h-1 bg-[#0D1321] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{ width: `${stageProgress}%`, backgroundColor: stageCfg.color }}
            />
          </div>
        </div>
      )}

      {/* Visit History */}
      <div className="flex items-center gap-2 mb-3 text-[#64748B]">
        <Clock className="w-3 h-3" />
        <span className="text-[11px]">Last visit: {getDaysAgo(customer.lastVisitDate)}</span>
        <span className="text-[#1E293B]">·</span>
        <span className="text-[11px]">{customer.visits.length} visits</span>
      </div>

      {/* Pain Points */}
      {customer.painPoints.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {customer.painPoints.slice(0, 3).map((pp, i) => (
            <span
              key={i}
              className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] bg-[#1A2235] text-[#94A3B8] border border-[#1E293B]"
            >
              {pp}
            </span>
          ))}
          {customer.painPoints.length > 3 && (
            <span className="text-[10px] text-[#64748B]">+{customer.painPoints.length - 3} more</span>
          )}
        </div>
      )}

      {/* Bottom */}
      <div className="mt-auto pt-3 border-t border-[#1E293B]">
        <span className="text-xs text-[#6366F1] font-medium flex items-center gap-1 hover:gap-2 transition-all">
          View Profile <ChevronRight className="w-3 h-3" />
        </span>
      </div>
    </motion.div>
  )
}

/* ------------------------------------------------------------------ */
/*  Filter Dropdown                                                    */
/* ------------------------------------------------------------------ */

function FilterDropdown({
  icon,
  label,
  isOpen,
  onToggle,
  onClose,
  children,
}: {
  icon: ReactNode
  label: string
  isOpen: boolean
  onToggle: () => void
  onClose: () => void
  children: ReactNode
}) {
  return (
    <div className="relative">
      <button
        onClick={onToggle}
        className={cn(
          'flex items-center gap-1.5 h-9 px-3 rounded-input bg-[#0D1321] border text-sm transition-colors',
          isOpen ? 'border-[#6366F1] text-[#F1F5F9]' : 'border-[#1E293B] text-[#94A3B8] hover:border-[#334155] hover:text-[#F1F5F9]'
        )}
      >
        {icon}
        <span className="max-w-[80px] truncate">{label}</span>
        <ChevronDown className={cn('w-3.5 h-3.5 transition-transform', isOpen && 'rotate-180')} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <>
            <div className="fixed inset-0 z-30" onClick={onClose} />
            <motion.div
              initial={{ opacity: 0, y: -4, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.98 }}
              transition={{ duration: 0.15 }}
              className="absolute top-full left-0 mt-1 w-52 bg-[#1A2235] border border-[#1E293B] rounded-card-sm shadow-xl z-40 py-1.5 overflow-hidden"
            >
              {children}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
