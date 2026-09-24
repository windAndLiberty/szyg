import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Heart, MessageCircle, Radar, Target, TrendingUp, UserRoundCheck, Users } from 'lucide-react'
import { Link } from 'react-router'
import {
  acquisitionCommentStats,
  acquisitionConversions,
  acquisitionLeads,
  acquisitionMonitorTargets,
  fetchPlatformAccountMetrics,
  type LeadItem,
  type PlatformAccountMetrics,
} from '@/lib/api'
import { EmptyState, MetricCard, PageShell, Panel, normalizeQueueMetrics, platformLabel } from './MarketingShared'
import { useI18n } from '@/lib/i18n'

export default function MarketingWorkbench() {
  const { t } = useI18n()
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [targets, setTargets] = useState<Array<Record<string, unknown>>>([])
  const [conversions, setConversions] = useState<Array<Record<string, unknown>>>([])
  const [sent, setSent] = useState(0)
  const [accountMetrics, setAccountMetrics] = useState<PlatformAccountMetrics | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      acquisitionLeads({ limit: 100 }),
      acquisitionMonitorTargets(),
      acquisitionConversions({ limit: 100 }),
      acquisitionCommentStats(),
      fetchPlatformAccountMetrics(30),
    ]).then(([leadData, targetData, conversionData, stats, metrics]) => {
      setLeads(leadData.leads || [])
      setTargets((targetData.targets || []) as Array<Record<string, unknown>>)
      setConversions(conversionData.conversions || [])
      setSent(normalizeQueueMetrics(stats).sent)
      setAccountMetrics(metrics)
    }).catch((cause) => setError(cause instanceof Error ? cause.message : t("获客数据加载失败")))
  }, [])

  const highIntent = leads.filter((item) => ['a', 's', 'high', '高'].includes(String(item.grade || '').toLowerCase()))
  const pending = leads.filter((item) => !['converted', 'done', 'invalid'].includes(String(item.status || '').toLowerCase()))
  const platformCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    leads.forEach((item) => { counts[item.platform || 'unknown'] = (counts[item.platform || 'unknown'] || 0) + 1 })
    return Object.entries(counts).sort((a, b) => b[1] - a[1])
  }, [leads])
  const topPlatform = platformCounts[0]
  const summary = leads.length === 0
    ? t("还没有形成客户线索。先描述目标客户，AI会从市场信息和公开互动中寻找机会。")
    : t("当前有 {v0} 条线索需要继续处理，其中 {v1} 条意向较高。{v2}", { v0: pending.length, v1: highIntent.length, v2: topPlatform ? t("{v0}贡献的线索最多。", { v0: platformLabel(topPlatform[0]) }) : '' })

  return <PageShell title={t("AI营销获客")} subtitle={t("先看AI判断，再处理今天最值得推进的客户机会。")} icon={TrendingUp}>
    {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
    <section className="rounded-xl border border-[#6366F1]/25 bg-gradient-to-br from-[#171B34] to-[#111827] p-6">
      <p className="text-xs font-medium text-[#A5B4FC]">{t("AI获客简报")}</p>
      <h1 className="mt-3 max-w-4xl text-xl font-semibold leading-8 text-[#F1F5F9]">{summary}</h1>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link to="/marketing/customers" className="inline-flex items-center gap-2 rounded-lg bg-[#6366F1] px-4 py-2 text-sm font-medium text-white">{t("处理今日客户")}<ArrowRight className="h-4 w-4" /></Link>
        <Link to="/marketing/opportunities" className="inline-flex items-center gap-2 rounded-lg border border-[#334155] px-4 py-2 text-sm text-[#CBD5E1]">{t("寻找新机会")}</Link>
      </div>
    </section>

    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard label={t("新发现客户")} value={leads.length} icon={Users} />
      <MetricCard label={t("高意向客户")} value={highIntent.length} icon={Target} tone="green" />
      <MetricCard label={t("已完成互动")} value={sent} icon={MessageCircle} tone="blue" />
      <MetricCard label={t("已进入转化")} value={conversions.length} icon={TrendingUp} tone="amber" />
    </div>

    <div className="grid gap-5 xl:grid-cols-2">
      <Panel title={t("今日建议行动")} description={t("每项建议都直接进入对应客户或机会，不需要先理解系统功能。")}>
        <div className="space-y-3">
          <Action title={t("优先跟进 {v0} 名高意向客户", { v0: highIntent.length })} detail={t("查看客户依据、沟通记录和AI建议回复")} href="/marketing/customers?stage=high" />
          <Action title={t("检查 {v0} 个评论机会", { v0: targets.filter((item) => item.owner === 'comment_campaign').length })} detail={t("只检查已经参与评论的具体内容和新回复")} href="/marketing/opportunities?view=comments" />
          <Action title={t("继续寻找相似客户")} detail={t("用一句话描述客户，AI负责整理市场证据")} href="/marketing/opportunities" />
          <Action title={t("让AI寻找公开视频并准备评论")} detail={t("逐条确认后错峰执行，回复自动进入线索识别")} href="/marketing/opportunities?view=comments" />
        </div>
      </Panel>
      <Panel title={t("渠道结果")} description={t("数据用来解释客户从哪里来，不单独建立报表中心。")}>
        {platformCounts.length === 0 ? <EmptyState title={t("还没有渠道数据")} description={t("发现线索后，这里会说明哪些渠道带来的客户更多。")} /> : <div className="space-y-3">{platformCounts.slice(0, 5).map(([platform, count]) => <div key={platform} className="flex items-center gap-3"><span className="w-20 text-sm text-[#CBD5E1]">{platformLabel(platform)}</span><div className="h-2 flex-1 rounded-full bg-[#0B0F1A]"><div className="h-full rounded-full bg-[#6366F1]" style={{ width: `${Math.max(8, count / platformCounts[0][1] * 100)}%` }} /></div><span className="w-10 text-right text-sm text-[#94A3B8]">{count}</span></div>)}</div>}
      </Panel>
    </div>

    <Panel title={t("自有账号表现")} description={t("只记录你已连接的经营账号；竞品账号不会进入账号监听。")}>
      {!accountMetrics || accountMetrics.accounts.length === 0 ? <EmptyState title={t("还没有自有账号趋势")} description={t("到渠道账号完成登录并同步资料后，这里会开始记录粉丝、作品和获赞变化。")} /> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label={t("账号粉丝")} value={accountMetrics.totals.followers} icon={UserRoundCheck} hint={t("近30天 {v0}{v1}", { v0: accountMetrics.change.followers >= 0 ? '+' : '', v1: accountMetrics.change.followers })} />
        <MetricCard label={t("账号作品")} value={accountMetrics.totals.works_count} icon={Radar} tone="blue" hint={t("近30天 {v0}{v1}", { v0: accountMetrics.change.works_count >= 0 ? '+' : '', v1: accountMetrics.change.works_count })} />
        <MetricCard label={t("累计获赞")} value={accountMetrics.totals.likes_count} icon={Heart} tone="green" hint={t("近30天 {v0}{v1}", { v0: accountMetrics.change.likes_count >= 0 ? '+' : '', v1: accountMetrics.change.likes_count })} />
        <MetricCard label={t("已记录账号")} value={accountMetrics.accounts.length} icon={Users} tone="amber" hint={t("仅自有经营账号")} />
      </div>}
    </Panel>
  </PageShell>
}

function Action({ title, detail, href }: { title: string; detail: string; href: string }) {
  return <Link to={href} className="flex items-center gap-4 rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4 transition-colors hover:border-[#6366F1]"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#6366F1]/12 text-[#818CF8]"><Radar className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="text-sm font-medium text-[#F1F5F9]">{title}</p><p className="mt-1 text-xs text-[#64748B]">{detail}</p></div><ArrowRight className="h-4 w-4 text-[#64748B]" /></Link>
}
