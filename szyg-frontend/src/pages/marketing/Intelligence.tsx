import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import cloud from 'd3-cloud'
import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  CircleGauge,
  CheckCircle2,
  Clock3,
  FileText,
  History,
  Layers3,
  Lightbulb,
  Loader2,
  MessageCircleMore,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  fetchIntelligenceQueryReports,
  getErrorMessage,
  runIntelligenceQuery,
  type IntelligenceQueryReport,
} from '@/lib/api'
import {
  EmptyState,
  PageShell,
  buttonPrimary,
  buttonSecondary,
  formatDateTime,
} from './MarketingShared'
import { translateCurrent, useI18n } from '@/lib/i18n'

const loadingStages = ['理解你的诉求', '整理企业资料', '查找公开信息', '筛选有效信号', '生成情报报告']

const confidenceLabels: Record<string, string> = {
  get high() { return translateCurrent("高可信度") },
  get medium() { return translateCurrent("中等可信度") },
  get low() { return translateCurrent("初步判断") },
}

const relationLabels: Record<string, string> = {
  get customer_need() { return translateCurrent("客户需求") },
  get content_opportunity() { return translateCurrent("内容机会") },
  get competitor_move() { return translateCurrent("同行动作") },
  get market_change() { return translateCurrent("市场变化") },
}

const sourceStatusLabels: Record<string, string> = {
  get success() { return translateCurrent("已获取") },
  get partial() { return translateCurrent("部分获取") },
  get no_data() { return translateCurrent("本轮无数据") },
  get needs_login() { return translateCurrent("需要登录") },
  get restricted() { return translateCurrent("需要验证") },
  get timeout() { return translateCurrent("读取超时") },
  get unavailable() { return translateCurrent("暂不可用") },
  get failed() { return translateCurrent("读取失败") },
}

function sourceStatusClass(status: string): string {
  if (status === 'success') return 'bg-[#34D399]'
  if (status === 'partial') return 'bg-[#FBBF24]'
  if (status === 'no_data') return 'bg-[#64748B]'
  return 'bg-[#FB7185]'
}

function relativeTime(value: string): string {
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) return '-'
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))
  if (seconds < 60) return translateCurrent("刚刚")
  if (seconds < 3600) return translateCurrent("{v0}分钟前", { v0: Math.floor(seconds / 60) })
  if (seconds < 86400) return translateCurrent("{v0}小时前", { v0: Math.floor(seconds / 3600) })
  if (seconds < 2592000) return translateCurrent("{v0}天前", { v0: Math.floor(seconds / 86400) })
  return formatDateTime(value)
}

const accentPalette = ['#6366F1', '#22D3EE', '#34D399', '#FBBF24', '#FB7185', '#A78BFA', '#60A5FA', '#2DD4BF']

function Metric({
  label,
  value,
  hint,
  icon: Icon,
  accent,
}: {
  label: string
  value: string | number
  hint: string
  icon: typeof Activity
  accent: string
}) {
  return (
    <div className="group relative min-w-0 px-5 py-4">
      <span className="absolute inset-x-5 top-0 h-px opacity-70" style={{ backgroundColor: accent }} />
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-[#94A3B8]">{label}</p>
        <Icon className="h-4 w-4" style={{ color: accent }} />
      </div>
      <p className="mt-3 text-2xl font-semibold text-[#F8FAFC]">{value}</p>
      <p className="mt-1 truncate text-xs text-[#64748B]">{hint}</p>
    </div>
  )
}

function IntelligenceCard({
  title,
  description,
  icon: Icon,
  children,
  className = '',
}: {
  title: string
  description?: string
  icon: typeof Activity
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`overflow-hidden rounded-lg border border-[#1E293B] bg-[#0F1625] ${className}`}>
      <div className="flex items-start gap-3 border-b border-[#1E293B] px-5 py-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#182238] text-[#A5B4FC]">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-[#F1F5F9]">{title}</h3>
          {description && <p className="mt-1 text-xs leading-5 text-[#64748B]">{description}</p>}
        </div>
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

interface CloudWord {
  text: string
  weight: number
  size: number
  x?: number
  y?: number
  rotate?: number
}

function SemanticWordCloud({ words }: { words: Array<{ text: string; weight: number }> }) {
  const { t } = useI18n()
  const containerRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(560)
  const [layoutWords, setLayoutWords] = useState<CloudWord[]>([])
  const height = 340

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const updateWidth = () => setWidth(Math.max(300, Math.floor(element.getBoundingClientRect().width)))
    updateWidth()
    const observer = new ResizeObserver(updateWidth)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!words.length) {
      setLayoutWords([])
      return
    }
    const maximum = Math.max(1, ...words.map((item) => Number(item.weight || 0)))
    const minimum = Math.min(...words.map((item) => Number(item.weight || 0)))
    const range = Math.max(1, maximum - minimum)
    let seed = 20260718
    const seededRandom = () => {
      seed = (seed * 9301 + 49297) % 233280
      return seed / 233280
    }
    const prepared = words.slice(0, 24).map((item) => ({
      text: item.text,
      weight: item.weight,
      size: 11 + ((Number(item.weight || 0) - minimum) / range) * 17,
    }))
    const layout = cloud<CloudWord>()
      .size([Math.max(280, width * 0.88), height * 0.68])
      .words(prepared)
      .padding(3)
      .rotate(() => 0)
      .font('Microsoft YaHei')
      .fontWeight((item) => item.size >= 23 ? 700 : item.size >= 17 ? 600 : 500)
      .fontSize((item) => item.size)
      .random(seededRandom)
      .on('end', (result) => setLayoutWords(result))
    layout.start()
    return () => {
      layout.stop()
    }
  }, [width, words])

  return (
    <div ref={containerRef} className="h-[340px] w-full overflow-hidden">
      <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t("关键语义词云")}>
        <path
          d="M92 262C55 262 31 237 36 205C40 177 62 158 91 158C101 113 139 84 184 91C210 52 265 37 307 63C345 37 400 50 421 91C464 83 503 111 511 153C543 158 566 180 567 210C568 241 543 264 508 264H94Z"
          transform={`scale(${width / 600} ${height / 360})`}
          fill="#111B2B"
          stroke="#2A3851"
          strokeWidth="1.5"
        />
        <g transform={`translate(${width / 2}, ${height / 2 + 6})`}>
          {layoutWords.map((word, index) => (
            <text
              key={`${word.text}-${index}`}
              x={word.x || 0}
              y={word.y || 0}
              textAnchor="middle"
              dominantBaseline="middle"
              transform={`rotate(${word.rotate || 0}, ${word.x || 0}, ${word.y || 0})`}
              fill={accentPalette[index % accentPalette.length]}
              fontFamily="Microsoft YaHei, sans-serif"
              fontSize={word.size}
          fontWeight={word.size >= 23 ? 700 : word.size >= 17 ? 600 : 500}
              className="cursor-default transition-opacity hover:opacity-75"
            >
              <title>{t("{v0} · 权重 {v1}", { v0: word.text, v1: word.weight })}</title>
              {word.text}
            </text>
          ))}
        </g>
      </svg>
    </div>
  )
}

export default function Intelligence() {
  const { t } = useI18n()
  const [query, setQuery] = useState('')
  const [useEnterprise, setUseEnterprise] = useState(true)
  const [report, setReport] = useState<IntelligenceQueryReport | null>(null)
  const [history, setHistory] = useState<IntelligenceQueryReport[]>([])
  const [historyOpen, setHistoryOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingStage, setLoadingStage] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchIntelligenceQueryReports(20)
      .then((data) => {
        setHistory(data.items || [])
        setReport(data.items?.[0] || null)
      })
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!loading) return
    const timer = window.setInterval(() => {
      setLoadingStage((current) => Math.min(current + 1, loadingStages.length - 1))
    }, 2600)
    return () => window.clearInterval(timer)
  }, [loading])

  const maxTopicScore = useMemo(
    () => Math.max(1, ...(report?.topic_trends || []).map((item) => item.score)),
    [report],
  )
  const qualityTotal = Math.max(1, Number(report?.data_scope.relevant_samples || 0) + Number(report?.data_scope.filtered_samples || 0))
  const qualityRate = Math.round((Number(report?.data_scope.relevant_samples || 0) / qualityTotal) * 100)
  const qualityData = [
    { get name() { return translateCurrent("有效信号") }, value: Number(report?.data_scope.relevant_samples || 0), color: '#34D399' },
    { get name() { return translateCurrent("已过滤") }, value: Number(report?.data_scope.filtered_samples || 0), color: '#263247' },
  ]
  const confidenceScore = report?.data_scope.confidence === 'high' ? 88 : report?.data_scope.confidence === 'medium' ? 68 : 48
  const sourceHealth = report?.data_scope.source_health || []
  const activeSourceCount = sourceHealth.filter((item) => item.status === 'success' || item.status === 'partial').length
  const sourceMetricValue = sourceHealth.length ? `${activeSourceCount}/${sourceHealth.length}` : Number(report?.data_scope.platforms.length || 0)

  const discover = async () => {
    const question = query.trim()
    if (question.length < 4 || loading) return
    setLoading(true)
    setLoadingStage(0)
    setError('')
    try {
      const result = await runIntelligenceQuery({
        query: question,
        use_enterprise_context: useEnterprise,
        include_publish_records: useEnterprise,
      })
      setReport(result.report)
      setHistory((current) => [result.report, ...current.filter((item) => item.id !== result.report.id)].slice(0, 20))
    } catch (cause) {
      setError(getErrorMessage(cause, t("暂时没有完成这次情报发现，请稍后重试")))
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageShell
      title={t("市场情报")}
      subtitle={t("研究外部市场、用户声音和内容趋势，为全局洞察提供可验证的市场证据。")}
      icon={TrendingUp}
    >
      <section className="pb-2">
        <div className="mx-auto max-w-6xl">
          <div className="mb-3 flex items-center gap-2 text-xs font-medium text-[#64748B]">
            <Radar className="h-3.5 w-3.5 text-[#818CF8]" />

            {t("从一个具体问题开始")}
          </div>
          <div className="overflow-hidden rounded-lg border border-[#334155] bg-[#101827] transition-colors focus-within:border-[#6366F1] focus-within:shadow-[0_0_0_3px_rgba(99,102,241,0.08)]">
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value.slice(0, 500))}
              onKeyDown={(event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') void discover()
              }}
              rows={3}
              className="w-full resize-none bg-transparent px-5 py-4 text-base leading-7 text-[#F8FAFC] outline-none placeholder:text-[#475569]"
              placeholder={t("例如：最近家长选择 AI 英语陪练时最关心什么？哪些内容方向值得我们下周重点测试？")}
            />
            <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-t border-[#1E293B] bg-[#0D1422] px-4 py-2.5">
              <button
                type="button"
                role="switch"
                aria-checked={useEnterprise}
                onClick={() => setUseEnterprise((current) => !current)}
                className="inline-flex items-center gap-2.5 text-sm text-[#CBD5E1]"
              >
                <span className={`relative h-5 w-9 rounded-full transition-colors ${useEnterprise ? 'bg-[#6366F1]' : 'bg-[#334155]'}`}>
                  <span className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${useEnterprise ? 'translate-x-4' : 'translate-x-0'}`} />
                </span>

                {t("结合企业资料")}
              </button>
              <div className="flex items-center gap-2">
                <button className={buttonSecondary} onClick={() => setHistoryOpen(true)}>
                  <History className="h-4 w-4" />

                  {t("历史报告")}
                </button>
                <button className={buttonPrimary} onClick={() => void discover()} disabled={query.trim().length < 4 || loading}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}

                  {t("发现情报")}
                </button>
              </div>
            </div>
          </div>
          {error && <p className="mt-3 text-sm text-[#FCA5A5]">{error}</p>}
        </div>
      </section>

      {loading && (
        <div className="mx-auto flex min-h-80 max-w-3xl flex-col items-center justify-center py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[#6366F1]/15 text-[#A5B4FC]">
            <Search className="h-5 w-5 animate-pulse" />
          </div>
          <p className="mt-5 text-base font-medium text-[#F1F5F9]">{t(loadingStages[loadingStage])}</p>
          <p className="mt-2 text-sm text-[#64748B]">{t("正在把纷杂信息整理成与你的产品有关的判断")}</p>
          <div className="mt-6 flex items-center gap-2">
            {loadingStages.map((stage, index) => (
              <span
                key={stage}
                className={`h-1.5 w-10 rounded-full transition-colors ${index <= loadingStage ? 'bg-[#6366F1]' : 'bg-[#1E293B]'}`}
              />
            ))}
          </div>
        </div>
      )}

      {!loading && !report && (
        <EmptyState
          title={t("从一个真实的营销问题开始")}
          description={t("不必先配置竞品账号。描述产品、客户或市场问题，系统会自动寻找公开证据并过滤无关信息。")}
        />
      )}

      {!loading && report && (
        <div className="space-y-5 pb-8">
          <section className="overflow-hidden rounded-lg border border-[#25324A] bg-[#101827]">
            <div className="grid gap-6 px-6 py-6 xl:grid-cols-[1fr_220px] xl:items-center">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 text-xs text-[#64748B]">
                  <span>{relativeTime(report.created_at)}</span>
                  <span>·</span>
                  <span>{report.plan.time_range || t("近期公开信息")}</span>
                  <span className="rounded-md border border-[#34D399]/25 bg-[#34D399]/10 px-2 py-1 text-[#6EE7B7]">
                    {confidenceLabels[report.data_scope.confidence] || t("初步判断")}
                  </span>
                </div>
                <h2 className="mt-4 max-w-4xl text-xl font-semibold leading-8 text-[#F8FAFC]">{report.title || report.query}</h2>
                {report.title && report.title !== report.query && <p className="mt-2 max-w-4xl text-sm leading-6 text-[#94A3B8]">{report.query}</p>}
                <div className="mt-4 flex flex-wrap gap-2">
                  {(report.plan.search_keywords || []).slice(0, 5).map((keyword) => (
                    <span key={keyword} className="rounded-md border border-[#334155] bg-[#0B111D] px-2.5 py-1 text-xs text-[#94A3B8]">{keyword}</span>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-4 border-t border-[#1E293B] pt-4 xl:block xl:border-l xl:border-t-0 xl:pl-6 xl:pt-0">
                <div className="text-3xl font-semibold text-[#6EE7B7]">{confidenceScore}</div>
                <div className="mt-1 text-xs text-[#64748B]">{t("情报可信度 / 100")}</div>
                <div className="mt-3 h-1.5 flex-1 overflow-hidden rounded-full bg-[#1E293B] xl:w-full">
                  <div className="h-full rounded-full bg-[#34D399]" style={{ width: `${confidenceScore}%` }} />
                </div>
              </div>
            </div>
          </section>

          <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-[#1E293B] bg-[#0F1625] md:grid-cols-4 md:divide-x md:divide-[#1E293B]">
            <Metric label={t("有效信号")} value={report.data_scope.relevant_samples} hint={t("过滤 {v0} 条噪声", { v0: report.data_scope.filtered_samples })} icon={ShieldCheck} accent="#34D399" />
            <Metric label={t("关键主题")} value={report.topic_trends.length} hint={t("按营销价值排序")} icon={Target} accent="#6366F1" />
            <Metric label={t("企业内容")} value={report.data_scope.published_records} hint={report.data_scope.use_enterprise_context ? t("已参与差距分析") : t("本次未关联")} icon={Layers3} accent="#22D3EE" />
            <Metric label={t("公开来源")} value={sourceMetricValue} hint={sourceHealth.length ? t("本轮实际可用来源") : t("跨来源交叉判断")} icon={Radar} accent="#FBBF24" />
          </div>

          {sourceHealth.length > 0 && (
            <section className="overflow-hidden rounded-lg border border-[#1E293B] bg-[#0F1625]">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1E293B] px-5 py-3.5">
                <div>
                  <h3 className="text-sm font-semibold text-[#F1F5F9]">{t("数据覆盖")}</h3>
                  <p className="mt-1 text-xs text-[#64748B]">{t("每个渠道独立读取，单个渠道异常不会影响整份报告")}</p>
                </div>
                <span className="text-xs text-[#64748B]">{activeSourceCount}  {t("个来源可用")}</span>
              </div>
              <div className="grid sm:grid-cols-2 xl:grid-cols-3">
                {sourceHealth.map((item) => {
                  const healthy = item.status === 'success' || item.status === 'partial'
                  const StatusIcon = healthy ? CheckCircle2 : AlertCircle
                  return (
                    <div key={item.source} className="flex min-w-0 items-start gap-3 border-b border-[#1E293B] px-5 py-4 sm:border-r last:border-r-0">
                      <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${sourceStatusClass(item.status)}`} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-3">
                          <p className="truncate text-sm font-medium text-[#E2E8F0]">{item.label}</p>
                          <span className={`inline-flex shrink-0 items-center gap-1 text-[11px] ${healthy ? 'text-[#6EE7B7]' : 'text-[#94A3B8]'}`}>
                            <StatusIcon className="h-3 w-3" />
                            {sourceStatusLabels[item.status] || t("待确认")}
                          </span>
                        </div>
                        <p className="mt-1 truncate text-xs text-[#64748B]">{item.item_count > 0 ? t("{v0} 条公开内容", { v0: item.item_count }) : item.message}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          <div className="grid gap-5 xl:grid-cols-[1.45fr_0.55fr]">
            <IntelligenceCard title={t("今日判断")} description={t("把最值得关注的结论放在最前面")} icon={Zap}>
              <div className="divide-y divide-[#1E293B]">
                {report.executive_summary.map((item, index) => (
                  <div key={`${item.title}-${index}`} className="grid gap-3 py-4 first:pt-0 last:pb-0 md:grid-cols-[38px_1fr]">
                    <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[#6366F1]/30 bg-[#6366F1]/10 text-xs font-semibold text-[#A5B4FC]">{String(index + 1).padStart(2, '0')}</div>
                    <div>
                      <p className="text-sm font-semibold leading-6 text-[#F1F5F9]">{item.title}</p>
                      <p className="mt-1 text-sm leading-6 text-[#CBD5E1]">{item.finding}</p>
                      {item.why_it_matters && <p className="mt-2 border-l-2 border-[#334155] pl-3 text-xs leading-5 text-[#64748B]">{item.why_it_matters}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </IntelligenceCard>

            <IntelligenceCard title={t("样本质量")} description={t("有效信号在本轮采集中的占比")} icon={CircleGauge}>
              <div className="relative mx-auto h-44 max-w-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={qualityData} dataKey="value" innerRadius={58} outerRadius={76} startAngle={90} endAngle={-270} stroke="none">
                      {qualityData.map((item) => <Cell key={item.name} fill={item.color} />)}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-semibold text-[#F8FAFC]">{qualityRate}%</span>
                  <span className="mt-1 text-[11px] text-[#64748B]">{t("有效占比")}</span>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                {report.data_scope.platforms.slice(0, 5).map((platform) => (
                  <span key={platform} className="rounded-md bg-[#182238] px-2 py-1 text-[11px] text-[#94A3B8]">{platform}</span>
                ))}
              </div>
            </IntelligenceCard>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <IntelligenceCard title={t("需求热度")} description={t("主题评分综合相关度、互动信号与营销价值")} icon={TrendingUp}>
              {report.topic_trends.length ? (
                <div className="h-[340px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={report.topic_trends.slice(0, 8)} layout="vertical" margin={{ top: 0, right: 22, left: 18, bottom: 0 }}>
                      <CartesianGrid stroke="#1E293B" horizontal={false} strokeDasharray="3 5" />
                      <XAxis type="number" domain={[0, maxTopicScore]} hide />
                      <YAxis type="category" dataKey="topic" width={150} tick={{ fill: '#94A3B8', fontSize: 12 }} axisLine={false} tickLine={false} />
                      <Tooltip cursor={{ fill: '#18223888' }} contentStyle={{ background: '#0B111D', border: '1px solid #334155', borderRadius: 6, color: '#F8FAFC' }} />
                      <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={12}>
                        {report.topic_trends.slice(0, 8).map((item, index) => <Cell key={item.topic} fill={accentPalette[index % accentPalette.length]} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : <EmptyState title={t("样本不足")} description={t("本轮没有形成稳定的市场主题。")} />}
            </IntelligenceCard>

            <IntelligenceCard title={t("关键语义")} description={t("只展示语义筛选后仍有营销价值的表达")} icon={Activity}>
              {report.word_cloud.length ? (
                <SemanticWordCloud words={report.word_cloud} />
              ) : <EmptyState title={t("暂未形成关键语义")} description={t("增加有效公开样本后会自动生成。")} />}
            </IntelligenceCard>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <IntelligenceCard title={t("客户在意什么")} description={t("从评论和相关内容中整理真实决策信号")} icon={MessageCircleMore}>
              {report.customer_voice.length ? (
                <div className="space-y-2">
                  {report.customer_voice.slice(0, 6).map((item, index) => (
                    <div key={`${item.theme}-${index}`} className="group rounded-md border border-transparent px-3 py-3 transition-colors hover:border-[#2B3952] hover:bg-[#131D2E]">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-2.5">
                          <span className="h-2 w-2 shrink-0 rounded-sm" style={{ backgroundColor: accentPalette[index % accentPalette.length] }} />
                          <p className="truncate text-sm font-medium text-[#F1F5F9]">{item.theme}</p>
                        </div>
                        <span className="shrink-0 text-[11px] text-[#64748B]">{Number(item.count || 0) > 0 ? t("{v0} 条信号", { v0: item.count }) : item.type}</span>
                      </div>
                      <p className="mt-2 pl-4 text-sm leading-6 text-[#94A3B8]">{item.summary}</p>
                    </div>
                  ))}
                </div>
              ) : <EmptyState title={t("暂未识别明确需求")} description={t("现有证据不足以形成可信的客户声音聚类。")} />}
            </IntelligenceCard>

            <IntelligenceCard title={t("内容机会")} description={t("把市场信号转成可验证的表达方向")} icon={Lightbulb}>
              {report.content_patterns.length ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {report.content_patterns.slice(0, 6).map((item, index) => (
                    <div key={`${item.pattern}-${index}`} className="relative overflow-hidden rounded-md border border-[#263247] bg-[#111B2B] p-4">
                      <span className="absolute inset-y-0 left-0 w-0.5" style={{ backgroundColor: accentPalette[(index + 2) % accentPalette.length] }} />
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-medium leading-6 text-[#F1F5F9]">{item.pattern}</p>
                        <span className="text-[11px] font-semibold text-[#64748B]">{String(index + 1).padStart(2, '0')}</span>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-[#94A3B8]">{item.finding}</p>
                      {item.recommendation && <p className="mt-3 border-t border-[#263247] pt-3 text-xs leading-5 text-[#A5B4FC]">{item.recommendation}</p>}
                    </div>
                  ))}
                </div>
              ) : <EmptyState title={t("内容规律仍不稳定")} description={t("本轮不强行给出缺少证据的内容公式。")} />}
            </IntelligenceCard>
          </div>

          <IntelligenceCard title={t("企业内容与市场差距")} description={t("同时比较市场关注度与企业现有覆盖，不再依赖难扫读的表格")} icon={Target}>
            {report.market_gap.length ? (
              <div className="space-y-1">
                <div className="hidden grid-cols-[minmax(180px,1fr)_150px_150px_minmax(180px,1fr)] gap-5 border-b border-[#1E293B] px-3 pb-3 text-[11px] text-[#64748B] md:grid">
                  <span>{t("市场主题")}</span><span>{t("市场关注")}</span><span>{t("企业覆盖")}</span><span>{t("建议")}</span>
                </div>
                {report.market_gap.slice(0, 8).map((item, index) => (
                  <div key={item.topic} className="grid gap-3 rounded-md px-3 py-3 transition-colors hover:bg-[#131D2E] md:grid-cols-[minmax(180px,1fr)_150px_150px_minmax(180px,1fr)] md:items-center md:gap-5">
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="text-[11px] font-semibold text-[#475569]">{String(index + 1).padStart(2, '0')}</span>
                      <span className="line-clamp-2 text-sm font-medium text-[#E2E8F0]">{item.topic}</span>
                    </div>
                    <div>
                      <div className="mb-1.5 flex justify-between text-[11px] text-[#64748B]"><span>{t("关注")}</span><span>{item.market_score}</span></div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-[#1E293B]"><div className="h-full rounded-full bg-[#6366F1]" style={{ width: `${Math.min(100, item.market_score)}%` }} /></div>
                    </div>
                    <div>
                      <div className="mb-1.5 flex justify-between text-[11px] text-[#64748B]"><span>{t("覆盖")}</span><span>{item.enterprise_coverage}%</span></div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-[#1E293B]"><div className="h-full rounded-full bg-[#22D3EE]" style={{ width: `${Math.min(100, item.enterprise_coverage)}%` }} /></div>
                    </div>
                    <p className="text-xs leading-5 text-[#94A3B8]">{item.recommendation}</p>
                  </div>
                ))}
              </div>
            ) : <EmptyState title={t("暂无可比较主题")} description={t("关联企业资料并获得有效市场样本后才能计算差距。")} />}
          </IntelligenceCard>

          <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
            <IntelligenceCard title={t("建议下一步")} description={t("建议用于决策，不会自动修改内容或启动发布")} icon={Zap}>
              {report.actions.length ? (
                <div className="space-y-3">
                  {report.actions.map((item, index) => (
                    <div key={`${item.title}-${index}`} className="flex gap-3 rounded-md border border-[#263247] bg-[#111B2B] p-4">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#34D399]/10 text-xs font-semibold text-[#6EE7B7]">{index + 1}</span>
                      <div>
                        <p className="text-sm font-medium leading-6 text-[#F1F5F9]">{item.title}</p>
                        <p className="mt-1 text-xs leading-5 text-[#94A3B8]">{item.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : <EmptyState title={t("暂不建议立即行动")} description={t("有效证据不足时，系统不会为了填满页面而生成建议。")} />}
            </IntelligenceCard>

            <IntelligenceCard title={t("代表性证据")} description={t("只展示最相关的 {v0} 条，保留判断依据但不铺满原始数据", { v0: Math.min(5, report.evidence.length) })} icon={FileText}>
              {report.evidence.length ? (
                <div className="divide-y divide-[#1E293B]">
                  {report.evidence.slice(0, 5).map((item, index) => (
                    <div key={item.id} className="group flex items-start gap-3 py-4 first:pt-0 last:pb-0">
                      <span className="mt-0.5 text-[11px] font-semibold text-[#475569]">{String(index + 1).padStart(2, '0')}</span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-md bg-[#182238] px-2 py-0.5 text-[11px] text-[#CBD5E1]">{relationLabels[item.relation_type] || t("公开信号")}</span>
                          <span className="text-[11px] text-[#64748B]">{item.source}</span>
                          <span className="text-[11px] text-[#34D399]">{t("价值")} {item.marketing_value || '-'}</span>
                        </div>
                        <p className="mt-2 line-clamp-2 text-sm font-medium leading-6 text-[#E2E8F0]">{item.title}</p>
                        <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#64748B]">{item.reason || item.summary}</p>
                      </div>
                      {item.source_url && (
                        <button
                          title={t("查看公开来源")}
                          onClick={() => window.open(item.source_url, '_blank', 'noopener,noreferrer')}
                          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[#334155] text-[#64748B] transition-colors hover:border-[#6366F1] hover:text-white"
                        >
                          <ArrowUpRight className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : <EmptyState title={t("没有足够的代表性证据")} description={t("本轮已过滤掉不相关或不可验证的信息。")} />}
            </IntelligenceCard>
          </div>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-[#1E293B] pt-4 text-xs text-[#64748B]">
            <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5" />{t("已过滤")} {report.data_scope.filtered_samples}  {t("条低相关信息")}</span>
            {report.data_scope.knowledge_sources.length > 0 && <span className="inline-flex items-center gap-1.5"><BookOpen className="h-3.5 w-3.5" />{t("关联")} {report.data_scope.knowledge_sources.length}  {t("份企业资料")}</span>}
            <span className="inline-flex items-center gap-1.5"><Clock3 className="h-3.5 w-3.5" />{formatDateTime(report.updated_at)}</span>
          </div>
        </div>
      )}

      {historyOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/55" onMouseDown={() => setHistoryOpen(false)}>
          <aside className="h-full w-full max-w-md overflow-y-auto border-l border-[#334155] bg-[#0B0F1A] shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[#1E293B] bg-[#0B0F1A] px-5 py-4">
              <div>
                <h2 className="text-sm font-semibold text-[#F1F5F9]">{t("历史报告")}</h2>
                <p className="mt-1 text-xs text-[#64748B]">{t("保留最近 20 次情报判断")}</p>
              </div>
              <button title={t("关闭")} onClick={() => setHistoryOpen(false)} className="flex h-8 w-8 items-center justify-center rounded-md text-[#94A3B8] hover:bg-[#1E293B] hover:text-white">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="divide-y divide-[#1E293B] px-5">
              {history.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    setReport(item)
                    setQuery(item.query)
                    setUseEnterprise(item.data_scope.use_enterprise_context)
                    setHistoryOpen(false)
                  }}
                  className="group flex w-full items-center gap-3 py-4 text-left"
                >
                  <FileText className="h-4 w-4 shrink-0 text-[#64748B] group-hover:text-[#A5B4FC]" />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-sm leading-5 text-[#CBD5E1] group-hover:text-white">{item.query}</p>
                    <p className="mt-1 text-xs text-[#64748B]">{relativeTime(item.created_at)} · {item.data_scope.relevant_samples}  {t("条有效样本")}</p>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-[#475569]" />
                </button>
              ))}
              {!history.length && <div className="py-12 text-center text-sm text-[#64748B]">{t("还没有历史报告")}</div>}
            </div>
          </aside>
        </div>
      )}
    </PageShell>
  )
}
