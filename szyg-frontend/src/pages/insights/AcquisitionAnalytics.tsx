import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BarChart3, Funnel, Loader2, MessageSquare, PieChart, Target, TrendingUp, Users } from 'lucide-react'
import {
  acquisitionCommentStats,
  acquisitionConversions,
  acquisitionFunnel,
  acquisitionLeadStats,
  acquisitionLeads,
  type AcquisitionStatsResponse,
  type LeadItem,
} from '@/lib/api'
import {
  EmptyState,
  MetricCard,
  PageShell,
  Panel,
  formatNumber,
  normalizeQueueMetrics,
  parseFunnelStages,
  platformLabel,
} from '../marketing/MarketingShared'

function numericEntries(data: Record<string, unknown>): [string, number][] {
  return Object.entries(data)
    .filter(([, value]) => typeof value === 'number')
    .map(([key, value]) => [key, Number(value)])
}

export default function AcquisitionAnalytics() {
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [leadStats, setLeadStats] = useState<Record<string, unknown>>({})
  const [funnel, setFunnel] = useState<Record<string, unknown>>({})
  const [commentStats, setCommentStats] = useState<AcquisitionStatsResponse>({})
  const [conversions, setConversions] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const [leadData, leadStatsData, funnelData, commentStatsData, conversionData] = await Promise.all([
          acquisitionLeads({ limit: 100 }),
          acquisitionLeadStats(),
          acquisitionFunnel(),
          acquisitionCommentStats(),
          acquisitionConversions({ limit: 50 }),
        ])
        setLeads(leadData.leads || [])
        setLeadStats(leadStatsData || {})
        setFunnel(funnelData || {})
        setCommentStats(commentStatsData || {})
        setConversions(conversionData.conversions || [])
      } catch (e) {
        setError(e instanceof Error ? e.message : '获客洞察数据加载失败')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const platformCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    leads.forEach((item) => {
      const key = item.platform || 'unknown'
      counts[key] = (counts[key] || 0) + 1
    })
    return Object.entries(counts).sort((a, b) => b[1] - a[1])
  }, [leads])

  const highIntent = leads.filter((item) => ['a', 's', '高', 'high'].includes(String(item.grade || '').toLowerCase())).length
  const funnelStages = parseFunnelStages(funnel)
  const leadStatEntries = numericEntries(leadStats)
  const queueMetrics = normalizeQueueMetrics(commentStats)
  const sent = queueMetrics.sent
  const failed = queueMetrics.failed
  const queued = queueMetrics.pending
  const successRate = sent + failed > 0 ? `${Math.round((sent / (sent + failed)) * 100)}%` : '-'

  return (
    <PageShell title="获客洞察" subtitle="复盘目标发现、评论执行、线索识别和转化阶段表现。" icon={TrendingUp}>
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}

      {loading ? (
        <div className="flex h-64 items-center justify-center text-[#64748B]"><Loader2 className="h-8 w-8 animate-spin" /></div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="线索总数" value={formatNumber(leads.length)} icon={Users} />
            <MetricCard label="高意向线索" value={formatNumber(highIntent)} icon={Target} tone="green" />
            <MetricCard label="评论成功率" value={successRate} icon={MessageSquare} tone="blue" />
            <MetricCard label="待处理队列" value={formatNumber(queued)} icon={AlertTriangle} tone="amber" />
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <Panel title="获客漏斗" description="从线索发现到转化阶段的数量分布。">
              {funnelStages.length === 0 ? (
                <EmptyState title="暂无漏斗数据" description="线索状态更新后会生成漏斗分布。" />
              ) : (
                <div className="space-y-3">
                  {funnelStages.map((item) => {
                    const max = Math.max(...funnelStages.map((stage) => stage.count), 1)
                    return (
                      <div key={item.stage}>
                        <div className="mb-1 flex justify-between text-xs">
                          <span className="text-[#CBD5E1]">{item.label}</span>
                          <span className="text-[#64748B]">{item.count}</span>
                        </div>
                        <div className="h-2 rounded-full bg-[#0B0F1A]">
                          <div className="h-2 rounded-full bg-[#6366F1]" style={{ width: `${Math.max(6, (item.count / max) * 100)}%` }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </Panel>

            <Panel title="平台来源分布" description="判断哪个平台带来更多线索和机会。">
              {platformCounts.length === 0 ? (
                <EmptyState title="暂无平台分布" description="线索产生后会按平台聚合。" />
              ) : (
                <div className="space-y-3">
                  {platformCounts.map(([platform, count]) => (
                    <div key={platform} className="flex items-center justify-between rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-3">
                      <div className="flex items-center gap-2 text-sm text-[#F1F5F9]">
                        <PieChart className="h-4 w-4 text-[#818CF8]" />
                        {platformLabel(platform)}
                      </div>
                      <span className="text-sm text-[#94A3B8]">{count} 条线索</span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <Panel title="评论执行概览" description="用于观察发送成功、失败和排队压力。">
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                  <p className="text-xs text-[#64748B]">已发送</p>
                  <p className="mt-2 text-2xl font-semibold text-[#10B981]">{formatNumber(sent)}</p>
                </div>
                <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                  <p className="text-xs text-[#64748B]">失败</p>
                  <p className="mt-2 text-2xl font-semibold text-[#EF4444]">{formatNumber(failed)}</p>
                </div>
                <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                  <p className="text-xs text-[#64748B]">排队</p>
                  <p className="mt-2 text-2xl font-semibold text-[#F59E0B]">{formatNumber(queued)}</p>
                </div>
              </div>
            </Panel>

            <Panel title="线索统计" description="展示后端线索统计字段，便于快速发现有效指标。">
              {leadStatEntries.length === 0 ? (
                <EmptyState title="暂无线索统计" description="线索积累后会显示等级、状态或来源统计。" />
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  {leadStatEntries.map(([key, value]) => (
                    <div key={key} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                      <p className="text-xs text-[#64748B]">{key}</p>
                      <p className="mt-2 text-xl font-semibold text-[#F1F5F9]">{formatNumber(value)}</p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>

          <Panel title="转化记录" description="最近进入转化链路的记录，用于复盘跟进质量。">
            {conversions.length === 0 ? (
              <EmptyState title="暂无转化记录" description="客户跟进和状态推进后，会在这里出现转化记录。" />
            ) : (
              <div className="overflow-hidden rounded-lg border border-[#1E293B]">
                <table className="w-full text-left text-sm">
                  <thead className="bg-[#0B0F1A] text-xs text-[#64748B]">
                    <tr>
                      <th className="px-3 py-3">客户</th>
                      <th className="px-3 py-3">平台</th>
                      <th className="px-3 py-3">阶段</th>
                      <th className="px-3 py-3">更新时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1E293B]">
                    {conversions.map((item, index) => (
                      <tr key={String(item.id || index)}>
                        <td className="px-3 py-3 text-[#F1F5F9]">{String(item.customer_name || item.user_name || item.name || '未知客户')}</td>
                        <td className="px-3 py-3 text-[#94A3B8]">{platformLabel(String(item.platform || ''))}</td>
                        <td className="px-3 py-3 text-[#CBD5E1]">{String(item.stage || item.status || '-')}</td>
                        <td className="px-3 py-3 text-[#64748B]">{String(item.updated_at || item.created_at || '-')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      )}
    </PageShell>
  )
}
