import { apiGet } from '@/lib/api'

export interface InsightSummary {
  published: number
  publish_success_rate: number | null
  leads: number
  conversions: number
  market_opportunities: number
  needs_human: number
}

export interface InsightTrendPoint {
  date: string
  generated: number
  published: number
  leads: number
  conversions: number
}

export interface GlobalInsightItem {
  id: string
  type: 'opportunity' | 'risk' | 'strength' | string
  title: string
  finding: string
  why_it_matters: string
  action: string
  value_score: number
  confidence: string
  source_report_id: string
}

export interface MarketGapItem {
  topic: string
  market_score: number
  enterprise_coverage: number
  gap: number
  recommendation: string
}

export interface InsightDataHealth {
  id: string
  label: string
  status: 'ready' | 'empty' | 'partial' | string
  count: number
  detail: string
  updated_at: string
}

export interface KnowledgeReference {
  document_id: string
  source: string
  heading: string
  locator: string
  excerpt: string
  score?: number
}

export interface GlobalInsightsResponse {
  generated_at: string
  period_days: number
  summary: InsightSummary
  trend: InsightTrendPoint[]
  insights: GlobalInsightItem[]
  market_gap: MarketGapItem[]
  actions: Array<Record<string, unknown>>
  knowledge: {
    stats: Record<string, unknown>
    references: KnowledgeReference[]
  }
  market_report: {
    id: string
    title: string
    query: string
    created_at: string
    confidence: string
    evidence: Array<Record<string, unknown>>
  }
  data_health: InsightDataHealth[]
}

export interface ContentInsightsResponse {
  generated_at: string
  period_days: number
  summary: {
    generated: number
    adopted: number
    adoption_rate: number | null
    published: number
    publish_success: number
    publish_success_rate: number | null
  }
  funnel: Array<{ stage: string; label: string; count: number }>
  content_types: Array<{ name: string; value: number }>
  platforms: Array<{ name: string; value: number }>
  publish_statuses: Array<{ name: string; value: number }>
  recent_items: Array<{ id: string; title: string; type: string; adopted: boolean; created_at: string }>
  market_opportunities: MarketGapItem[]
  limitations: string[]
}

export const loadGlobalInsights = (days: number) =>
  apiGet<GlobalInsightsResponse>(`/api/insights/overview?days=${days}`)

export const loadContentInsights = (days: number) =>
  apiGet<ContentInsightsResponse>(`/api/insights/content?days=${days}`)
