import { useEffect, useState } from 'react'
import {
  AlertTriangle, CheckCircle2, FileText, Image, Layers3, Loader2,
  Send, Sparkles, TrendingUp, Video,
} from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { EmptyState, MetricCard, PageShell, Panel, formatDateTime, formatNumber, platformLabel } from '../marketing/MarketingShared'
import { loadContentInsights, type ContentInsightsResponse } from './insightsApi'
import { translateCurrent, useI18n } from '@/lib/i18n'

const ranges = [{ value: 7, get label() { return translateCurrent("7天") } }, { value: 30, get label() { return translateCurrent("30天") } }, { value: 90, get label() { return translateCurrent("90天") } }]

const typeLabels: Record<string, string> = {
  get image() { return translateCurrent("图片") }, get copy() { return translateCurrent("文案") }, get text() { return translateCurrent("文案") }, get video() { return translateCurrent("视频") }, get voice() { return translateCurrent("语音") }, get audio() { return translateCurrent("语音") }, get graphic() { return translateCurrent("图文") }, get unknown() { return translateCurrent("其他") },
}

const typeIcons = { image: Image, video: Video, copy: FileText, text: FileText, voice: FileText, audio: FileText, graphic: Layers3 }

function percent(value: number | null) {
  return value == null ? '—' : `${value}%`
}

export default function ContentAnalytics() {
  const { t } = useI18n()
  const [days, setDays] = useState(30)
  const [data, setData] = useState<ContentInsightsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    loadContentInsights(days)
      .then((result) => { if (active) setData(result) })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : t("内容洞察加载失败")) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [days])

  return <PageShell title={t("内容洞察")} subtitle={t("观察内容从生成、采纳到真实发布的转化，并与外部市场机会对照。")} icon={TrendingUp}>
    <div className="flex justify-end">
      <div className="inline-flex rounded-lg border border-border bg-background p-1">{ranges.map((item) => <button key={item.value} onClick={() => setDays(item.value)} className={`h-8 rounded-md px-3 text-xs ${days === item.value ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'}`}>{item.label}</button>)}</div>
    </div>
    {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-danger-ink">{error}</div>}
    {loading && !data ? <div className="flex h-64 items-center justify-center text-muted-foreground"><Loader2 className="h-7 w-7 animate-spin" /></div> : data && <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label={t("生成内容")} value={formatNumber(data.summary.generated)} icon={Sparkles} hint={t("最近 {v0} 天", { v0: days })} />
        <MetricCard label={t("已采纳")} value={formatNumber(data.summary.adopted)} icon={CheckCircle2} tone="green" hint={t("采纳率 {v0}", { v0: percent(data.summary.adoption_rate) })} />
        <MetricCard label={t("提交发布")} value={formatNumber(data.summary.published)} icon={Send} tone="blue" hint={t("按账号级发布任务统计")} />
        <MetricCard label={t("发布成功率")} value={percent(data.summary.publish_success_rate)} icon={TrendingUp} tone="amber" hint={t("{v0} 次成功", { v0: data.summary.publish_success })} />
      </div>

      <Panel title={t("内容流转")} description={t("同一时间范围内各阶段的真实数量，不把缺失数据补成转化。")}>
        <div className="grid gap-3 md:grid-cols-4">{data.funnel.map((item, index) => {
          const max = Math.max(data.funnel[0]?.count || 0, 1)
          return <div key={item.stage} className="relative overflow-hidden rounded-lg border border-border bg-background p-4">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-muted"><div className="h-full bg-[#6366F1]" style={{ width: `${Math.min(100, item.count * 100 / max)}%` }} /></div>
            <p className="text-xs text-muted-foreground">{index + 1}. {item.label}</p><p className="mt-2 text-2xl font-semibold text-foreground">{item.count}</p>
          </div>
        })}</div>
      </Panel>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title={t("内容类型")} description={t("企业最近实际生成的内容结构。")}>
          {data.content_types.length ? <div className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.content_types.map((item) => ({ ...item, label: typeLabels[item.name] || item.name }))}><CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} /><XAxis dataKey="label" stroke="#64748B" fontSize={11} tickLine={false} axisLine={false} /><YAxis stroke="#64748B" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} /><Tooltip contentStyle={{ background: 'hsl(var(--popover))', border: '1px solid hsl(var(--border))', borderRadius: 8 }} /><Bar dataKey="value" name={t("生成数量")} fill="#6366F1" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div> : <EmptyState title={t("暂无生成记录")} description={t("生成内容后会按图片、视频、文案和语音进行汇总。")} />}
        </Panel>

        <Panel title={t("发布平台")} description={t("展示发布任务分布，不代表平台作品表现。")}>
          {data.platforms.length ? <div className="space-y-4">{data.platforms.map((item) => {
            const max = Math.max(...data.platforms.map((row) => row.value), 1)
            return <div key={item.name}><div className="mb-2 flex justify-between text-sm"><span className="text-foreground">{platformLabel(item.name)}</span><span className="text-muted-foreground">{item.value}  {t("次")}</span></div><div className="h-2 rounded-full bg-background"><div className="h-2 rounded-full bg-[#38BDF8]" style={{ width: `${Math.max(6, item.value * 100 / max)}%` }} /></div></div>
          })}</div> : <EmptyState title={t("暂无发布记录")} description={t("从素材管理与发布提交内容后会出现平台分布。")} />}
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title={t("最近生成")} description={t("生成内容本身与采纳状态。")}>
          {data.recent_items.length ? <div className="divide-y divide-border">{data.recent_items.slice(0, 8).map((item) => {
            const Icon = typeIcons[item.type as keyof typeof typeIcons] || FileText
            return <div key={item.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"><Icon className="h-4 w-4" /></span><div className="min-w-0 flex-1"><p className="truncate text-sm text-foreground">{item.title}</p><p className="mt-1 text-xs text-muted-foreground">{typeLabels[item.type] || item.type} · {formatDateTime(item.created_at)}</p></div><span className={`rounded-full border px-2 py-1 text-[11px] ${item.adopted ? 'border-[#10B981]/25 bg-[#10B981]/8 text-success-ink' : 'border-border text-muted-foreground'}`}>{item.adopted ? t("已采纳") : t("未采纳")}</span></div>
          })}</div> : <EmptyState title={t("暂无内容")} description={t("内容生成记录会自动进入这里。")} />}
        </Panel>

        <Panel title={t("市场内容机会")} description={t("由市场情报提供，结合企业发布覆盖计算。")}>
          {data.market_opportunities.length ? <div className="space-y-3">{data.market_opportunities.slice(0, 4).map((item) => <div key={item.topic} className="rounded-lg border border-border bg-background p-4"><div className="flex items-center justify-between gap-3"><p className="text-sm font-medium text-foreground">{item.topic}</p><span className="text-xs text-warning-ink">{t("缺口")} {item.gap}</span></div><p className="mt-2 text-xs leading-5 text-muted-foreground">{item.recommendation}</p></div>)}</div> : <EmptyState title={t("暂无市场机会")} description={t("完成一次市场情报分析后，相关主题会进入内容洞察。")} />}
        </Panel>
      </div>

      {data.limitations.map((message) => <div key={message} className="flex items-start gap-2 rounded-lg border border-[#F59E0B]/20 bg-[#F59E0B]/6 px-4 py-3 text-xs leading-5 text-warning-ink"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{message}</div>)}
    </>}
  </PageShell>
}
