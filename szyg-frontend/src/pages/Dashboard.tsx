import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import {
  AlertTriangle, ArrowUpRight, BookOpenText, CheckCircle2, ChevronRight,
  CircleGauge, Database, FileSearch, Lightbulb, Loader2, MessageSquare,
  Send, Sparkles, Target, TrendingUp, Users,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { loadGlobalInsights, type GlobalInsightsResponse, type InsightDataHealth } from './insights/insightsApi'

const rangeOptions = [
  { value: 7, label: '7天' },
  { value: 30, label: '30天' },
  { value: 90, label: '90天' },
]

const panelClass = 'rounded-lg border border-[#1E293B] bg-[#111827]/80'

function formatNumber(value: number | null | undefined) {
  const amount = Number(value || 0)
  if (amount >= 10000) return `${(amount / 10000).toFixed(1)}万`
  if (amount >= 1000) return `${(amount / 1000).toFixed(1)}k`
  return String(Math.round(amount))
}

function formatRate(value: number | null | undefined) {
  return value == null ? '—' : `${value}%`
}

function formatTime(value: string) {
  if (!value) return '尚未同步'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '尚未同步'
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function Metric({ label, value, hint, icon: Icon, tone }: {
  label: string
  value: string
  hint: string
  icon: typeof Send
  tone: 'indigo' | 'green' | 'amber' | 'cyan'
}) {
  const tones = {
    indigo: 'bg-[#6366F1]/12 text-[#A5B4FC]',
    green: 'bg-[#10B981]/12 text-[#6EE7B7]',
    amber: 'bg-[#F59E0B]/12 text-[#FBBF24]',
    cyan: 'bg-[#06B6D4]/12 text-[#67E8F9]',
  }
  return <div className={`${panelClass} p-4`}>
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-xs text-[#64748B]">{label}</p>
        <p className="mt-2 text-2xl font-semibold text-[#F8FAFC]">{value}</p>
      </div>
      <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${tones[tone]}`}><Icon className="h-4 w-4" /></span>
    </div>
    <p className="mt-3 text-xs text-[#64748B]">{hint}</p>
  </div>
}

function HealthRow({ item }: { item: InsightDataHealth }) {
  const ready = item.status === 'ready' || item.status === 'partial'
  return <div className="flex items-center gap-3 py-3">
    <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${ready ? 'bg-[#10B981]/10 text-[#6EE7B7]' : 'bg-[#64748B]/10 text-[#64748B]'}`}>
      {ready ? <CheckCircle2 className="h-4 w-4" /> : <Database className="h-4 w-4" />}
    </span>
    <div className="min-w-0 flex-1">
      <div className="flex items-center justify-between gap-3"><p className="text-sm text-[#E2E8F0]">{item.label}</p><span className="text-xs text-[#64748B]">{item.count}</span></div>
      <p className="mt-1 truncate text-xs text-[#64748B]">{item.detail}</p>
    </div>
  </div>
}

function Empty({ children }: { children: string }) {
  return <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed border-[#334155] bg-[#0B0F1A]/50 px-6 text-center text-sm text-[#64748B]">{children}</div>
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [days, setDays] = useState(30)
  const [data, setData] = useState<GlobalInsightsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    loadGlobalInsights(days)
      .then((result) => { if (active) setData(result) })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : '全局洞察加载失败') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [days])

  const summary = data?.summary
  const topInsight = data?.insights[0]

  return <div className="flex h-full flex-col overflow-auto bg-[#0B0F1A]">
    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#1E293B] px-6 py-5">
      <div>
        <p className="text-sm text-[#94A3B8]">结合企业知识、内部经营数据和外部市场证据，发现值得行动的变化。</p>
        {data && <p className="mt-1 text-xs text-[#475569]">分析更新于 {formatTime(data.generated_at)}</p>}
      </div>
      <div className="inline-flex rounded-lg border border-[#273449] bg-[#0B0F1A] p-1">
        {rangeOptions.map((item) => <button key={item.value} onClick={() => setDays(item.value)} className={`h-8 rounded-md px-3 text-xs transition-colors ${days === item.value ? 'bg-[#273449] text-[#F8FAFC]' : 'text-[#64748B] hover:text-[#CBD5E1]'}`}>{item.label}</button>)}
      </div>
    </div>

    <div className="space-y-5 p-6">
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
      {loading && !data ? <div className="flex h-72 items-center justify-center text-[#64748B]"><Loader2 className="h-7 w-7 animate-spin" /></div> : data && <>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Metric label="成功发布" value={formatNumber(summary?.published)} hint={`最近 ${days} 天`} icon={Send} tone="indigo" />
          <Metric label="发布成功率" value={formatRate(summary?.publish_success_rate)} hint={`${summary?.needs_human || 0} 项需要处理`} icon={CircleGauge} tone="green" />
          <Metric label="新增线索" value={formatNumber(summary?.leads)} hint={`${summary?.conversions || 0} 条进入转化`} icon={Users} tone="cyan" />
          <Metric label="市场机会" value={formatNumber(summary?.market_opportunities)} hint="市场热度高于企业覆盖" icon={Target} tone="amber" />
        </div>

        <section className={`${panelClass} overflow-hidden`}>
          <div className="grid lg:grid-cols-[1.15fr_0.85fr]">
            <div className="border-b border-[#1E293B] p-5 lg:border-b-0 lg:border-r">
              <div className="flex items-center gap-2 text-xs font-medium text-[#A5B4FC]"><Sparkles className="h-4 w-4" />当前最值得关注</div>
              {topInsight ? <>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold text-[#F8FAFC]">{topInsight.title}</h2>
                  <span className="rounded-full border border-[#F59E0B]/25 bg-[#F59E0B]/8 px-2 py-1 text-[11px] text-[#FBBF24]">价值 {topInsight.value_score}</span>
                </div>
                <p className="mt-3 text-sm leading-7 text-[#CBD5E1]">{topInsight.finding}</p>
                <p className="mt-2 text-sm leading-6 text-[#64748B]">{topInsight.why_it_matters}</p>
                <div className="mt-5 flex items-start gap-2 rounded-lg border border-[#334155] bg-[#0B0F1A] p-3"><Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-[#FBBF24]" /><p className="text-sm leading-6 text-[#CBD5E1]">{topInsight.action}</p></div>
              </> : <Empty>数据积累后，这里会优先展示最值得行动的机会或风险。</Empty>}
            </div>
            <div className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div><h2 className="text-sm font-semibold text-[#F1F5F9]">外部证据</h2><p className="mt-1 text-xs text-[#64748B]">来自最近一次市场情报分析</p></div>
                {data.market_report.id && <button onClick={() => navigate('/marketing/intelligence')} className="inline-flex items-center gap-1 text-xs text-[#A5B4FC] hover:text-white">查看市场情报<ChevronRight className="h-3.5 w-3.5" /></button>}
              </div>
              {data.market_report.id ? <div className="mt-5">
                <p className="text-sm font-medium text-[#E2E8F0]">{data.market_report.title}</p>
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#64748B]">{data.market_report.query}</p>
                <div className="mt-4 grid grid-cols-2 gap-3 text-xs"><div className="rounded-lg bg-[#0B0F1A] p-3"><p className="text-[#64748B]">置信度</p><p className="mt-1 text-[#CBD5E1]">{data.market_report.confidence || '待评估'}</p></div><div className="rounded-lg bg-[#0B0F1A] p-3"><p className="text-[#64748B]">有效证据</p><p className="mt-1 text-[#CBD5E1]">{data.market_report.evidence.length} 条</p></div></div>
              </div> : <div className="mt-5"><Empty>尚无市场情报报告，完成一次市场发现后会自动进入全局洞察。</Empty></div>}
            </div>
          </div>
        </section>

        <div className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
          <section className={panelClass}>
            <div className="border-b border-[#1E293B] px-5 py-4"><h2 className="text-sm font-semibold text-[#F1F5F9]">经营趋势</h2><p className="mt-1 text-xs text-[#64748B]">内容生产、发布和线索结果按天汇总</p></div>
            <div className="h-72 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.trend}>
                  <defs><linearGradient id="publishedFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#6366F1" stopOpacity={0.35} /><stop offset="95%" stopColor="#6366F1" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                  <XAxis dataKey="date" stroke="#475569" tickLine={false} axisLine={false} fontSize={11} />
                  <YAxis stroke="#475569" tickLine={false} axisLine={false} allowDecimals={false} fontSize={11} />
                  <Tooltip contentStyle={{ background: '#0B0F1A', border: '1px solid #334155', borderRadius: 8, color: '#E2E8F0' }} />
                  <Area type="monotone" dataKey="generated" name="生成" stroke="#38BDF8" fillOpacity={0} strokeWidth={2} />
                  <Area type="monotone" dataKey="published" name="发布" stroke="#818CF8" fill="url(#publishedFill)" strokeWidth={2} />
                  <Area type="monotone" dataKey="leads" name="线索" stroke="#10B981" fillOpacity={0} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className={panelClass}>
            <div className="border-b border-[#1E293B] px-5 py-4"><h2 className="text-sm font-semibold text-[#F1F5F9]">数据依据</h2><p className="mt-1 text-xs text-[#64748B]">不完整的数据不会被当作零值</p></div>
            <div className="divide-y divide-[#1E293B] px-5">{data.data_health.map((item) => <HealthRow key={item.id} item={item} />)}</div>
          </section>
        </div>

        <div className="grid gap-5 xl:grid-cols-2">
          <section className={panelClass}>
            <div className="flex items-start justify-between gap-4 border-b border-[#1E293B] px-5 py-4"><div><h2 className="text-sm font-semibold text-[#F1F5F9]">市场与企业差距</h2><p className="mt-1 text-xs text-[#64748B]">只展示与企业资料和发布内容相关的主题</p></div><TrendingUp className="h-4 w-4 text-[#818CF8]" /></div>
            <div className="space-y-5 p-5">{data.market_gap.length ? data.market_gap.slice(0, 5).map((item) => <div key={item.topic}>
              <div className="mb-2 flex items-center justify-between gap-3"><span className="text-sm text-[#E2E8F0]">{item.topic}</span><span className="text-xs text-[#FBBF24]">缺口 {item.gap}</span></div>
              <div className="relative h-2 overflow-hidden rounded-full bg-[#1E293B]"><div className="absolute inset-y-0 left-0 rounded-full bg-[#6366F1]" style={{ width: `${Math.min(100, item.market_score)}%` }} /><div className="absolute inset-y-0 left-0 rounded-full bg-[#10B981]" style={{ width: `${Math.min(100, item.enterprise_coverage)}%` }} /></div>
              <div className="mt-2 flex gap-4 text-[11px] text-[#64748B]"><span>市场 {item.market_score}</span><span>企业覆盖 {item.enterprise_coverage}</span></div>
            </div>) : <Empty>完成市场情报分析后，这里会对比外部热度和企业内容覆盖。</Empty>}</div>
          </section>

          <section className={panelClass}>
            <div className="flex items-start justify-between gap-4 border-b border-[#1E293B] px-5 py-4"><div><h2 className="text-sm font-semibold text-[#F1F5F9]">企业知识引用</h2><p className="mt-1 text-xs text-[#64748B]">用于判断市场信号是否真正适合企业</p></div><BookOpenText className="h-4 w-4 text-[#38BDF8]" /></div>
            <div className="divide-y divide-[#1E293B] px-5">{data.knowledge.references.length ? data.knowledge.references.map((item) => <div key={`${item.document_id}-${item.heading}`} className="py-4"><div className="flex items-center gap-2"><FileSearch className="h-4 w-4 text-[#64748B]" /><p className="text-sm text-[#E2E8F0]">{item.source}</p></div><p className="mt-2 text-xs text-[#94A3B8]">{item.heading || item.locator}</p><p className="mt-2 line-clamp-2 text-xs leading-5 text-[#64748B]">{item.excerpt}</p></div>) : <div className="py-5"><Empty>当前主题暂未检索到企业知识引用，结论将降低置信度。</Empty></div>}</div>
          </section>
        </div>

        <section className={panelClass}>
          <div className="border-b border-[#1E293B] px-5 py-4"><h2 className="text-sm font-semibold text-[#F1F5F9]">其他发现</h2><p className="mt-1 text-xs text-[#64748B]">按照业务价值排序，保留可解释的数字依据</p></div>
          {data.insights.length > 1 ? <div className="divide-y divide-[#1E293B]">{data.insights.slice(1).map((item) => <div key={item.id} className="grid gap-3 px-5 py-4 md:grid-cols-[1fr_1.3fr_auto] md:items-center"><div><div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${item.type === 'risk' ? 'bg-[#EF4444]' : item.type === 'strength' ? 'bg-[#10B981]' : 'bg-[#F59E0B]'}`} /><p className="text-sm font-medium text-[#E2E8F0]">{item.title}</p></div><p className="mt-2 text-xs text-[#64748B]">价值 {item.value_score} · {item.confidence === 'high' ? '高置信度' : item.confidence === 'medium' ? '中等置信度' : '待补充证据'}</p></div><p className="text-sm leading-6 text-[#94A3B8]">{item.finding}</p><ArrowUpRight className="h-4 w-4 text-[#475569]" /></div>)}</div> : <div className="p-5"><Empty>更多经营数据积累后，会持续生成新的机会和异常判断。</Empty></div>}
        </section>
      </>}
    </div>
  </div>
}
