export const DealStage = {
  InitialContact: 'InitialContact',
  NeedsConfirmed: 'NeedsConfirmed',
  SolutionEval: 'SolutionEval',
  Negotiation: 'Negotiation',
  Won: 'Won',
  Lost: 'Lost',
} as const

export type DealStage = (typeof DealStage)[keyof typeof DealStage]

export interface Deal {
  id: string
  customerName: string
  customerId: string
  stage: DealStage
  amount: number
  winRate: number
  expectedCloseDate: string
  assignedTo: string
  assignedToAvatar?: string
  lastActivity: string
  description?: string
  createdAt: string
  updatedAt: string
}

export interface Customer {
  id: string
  name: string
  industry: string
  contactName: string
  email: string
  phone: string
  address?: string
  logo?: string
  notes?: string
  dealCount: number
  totalValue: number
  lastVisitDate?: string
  createdAt: string
  updatedAt: string
}

export interface VisitRecord {
  id: string
  customerId: string
  customerName: string
  visitDate: string
  purpose: string
  transcript?: string
  summary?: string
  outcome?: string
  nextSteps?: string
  reportId?: string
  status: 'completed' | 'pending' | 'cancelled'
  createdAt: string
  updatedAt: string
}

export type AgentStatus = 'Waiting' | 'Processing' | 'Complete' | 'Error'

export interface AgentNode {
  id: string
  name: string
  icon: string
  status: AgentStatus
  description: string
  progress: number
  startTime?: string
  endTime?: string
  output?: string
}

export interface MeetingMinutes {
  id: string
  visitId: string
  customerName: string
  meetingDate: string
  attendees: string[]
  keyPoints: string[]
  decisions: string[]
  actionItems: ActionItem[]
  transcript: string
  createdAt: string
}

export interface ActionItem {
  id: string
  text: string
  assignee?: string
  dueDate?: string
  completed: boolean
}

export interface FollowUpStrategy {
  id: string
  dealId: string
  customerName: string
  strategies: StrategyItem[]
  timeline: TimelineItem[]
  createdAt: string
}

export interface StrategyItem {
  id: string
  title: string
  description: string
  priority: 'high' | 'medium' | 'low'
  type: 'email' | 'call' | 'meeting' | 'proposal' | 'demo'
}

export interface TimelineItem {
  id: string
  date: string
  action: string
  completed: boolean
}

export interface EmailDraft {
  id: string
  dealId: string
  customerName: string
  subject: string
  body: string
  type: 'follow-up' | 'proposal' | 'thank-you' | 'introduction'
  tone: 'formal' | 'friendly' | 'urgent'
  generatedAt: string
}

export interface CRMData {
  id: string
  dealId: string
  customerName: string
  syncStatus: 'pending' | 'synced' | 'failed'
  lastSyncedAt?: string
  fields: CRMField[]
}

export interface CRMField {
  field: string
  oldValue: string
  newValue: string
  status: 'updated' | 'new' | 'unchanged'
}

export interface ActivityItem {
  id: string
  type: 'visit' | 'deal_moved' | 'ai_report' | 'new_customer' | 'follow_up' | 'deal_created'
  title: string
  description: string
  timestamp: string
  dealId?: string
  customerId?: string
  reportId?: string
}

export interface KPIData {
  label: string
  value: string
  trend: number
  trendLabel: string
  subtitle: string
  icon: string
}

export interface PipelineColumn {
  stage: DealStage
  deals: Deal[]
  count: number
  totalValue: number
}
