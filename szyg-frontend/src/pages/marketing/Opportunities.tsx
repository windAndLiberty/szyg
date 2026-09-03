import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BarChart3, Check, ExternalLink, Loader2, MessageCircle, PlayCircle, Radar, Search, Sparkles } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router'
import {
  acquisitionCommentQueue, acquisitionExecuteCommentCampaign, acquisitionMonitorTargets,
  acquisitionPlanCommentCampaign, runIntelligenceQuery,
  type CommentCampaignItem, type CommentCampaignPlan, type CommentQueueItem,
  type IntelligenceQueryReport, type MonitorTarget,
} from '@/lib/api'
import { EmptyState, PageShell, Panel, PLATFORM_OPTIONS, buttonPrimary, formatDateTime, formatNumber, inputClass, platformLabel } from './MarketingShared'

type View = 'research' | 'comments'
const statusText: Record<string, string> = { success: '已找到真实内容', partial: '部分可用', no_data: '暂未找到内容', needs_login: '需要登录', restricted: '平台限制访问', timeout: '连接超时', unavailable: '暂未接入', failed: '获取失败' }

function MarketResearch() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [report, setReport] = useState<IntelligenceQueryReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const discover = async () => {
    if (query.trim().length < 4) return setError('请具体描述想了解的客户、行业或竞品问题')
    setLoading(true); setError('')
    try {
      const result = await runIntelligenceQuery({ query: query.trim(), use_enterprise_context: true, include_publish_records: true })
      setReport(result.report)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '市场信息分析失败') }
    finally { setLoading(false) }
  }
  const maxPlatform = Math.max(1, ...(report?.platform_distribution || []).map((item) => Number(item.value || 0)))

  return <div className="space-y-5">
    {error && <ErrorBanner text={error} />}
    <section className="rounded-xl border border-[#334155] bg-[#101827] p-5">
      <p className="text-xs font-medium text-[#818CF8]">广泛搜索，不用先添加竞品账号</p>
      <div className="mt-3 flex flex-col gap-3 lg:flex-row">
        <textarea value={query} onChange={(e) => setQuery(e.target.value.slice(0, 500))} className={`${inputClass} min-h-24 flex-1 resize-none`} placeholder="例如：分析最近传统零售企业在私域获客方面遇到的问题、竞品方案和潜在机会" />
        <button onClick={discover} disabled={loading} className={`${buttonPrimary} lg:w-44`}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}AI搜索并整合</button>
      </div>
    </section>
    {report && <>
      <Panel title="AI机会判断" description="综合多个公开来源，不把某个竞品账号当作固定监听对象。">
        <div className="grid gap-3 lg:grid-cols-3">{report.executive_summary.slice(0, 3).map((item, index) => <div key={`${item.title}-${index}`} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4"><p className="text-sm font-medium text-[#F1F5F9]">{item.title}</p><p className="mt-2 text-sm leading-6 text-[#CBD5E1]">{item.finding}</p><p className="mt-2 text-xs text-[#64748B]">{item.why_it_matters}</p></div>)}</div>
      </Panel>
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="信息来源分布" description={`本次使用 ${report.data_scope.relevant_samples || 0} 条相关公开信息`}>
          {report.platform_distribution.length === 0 ? <EmptyState title="暂无可视化样本" description="各来源的真实获取状态会在下方说明。" /> : <div className="space-y-4">{report.platform_distribution.map((item) => <div key={item.name}><div className="mb-1 flex justify-between text-xs"><span className="text-[#CBD5E1]">{platformLabel(item.name)}</span><span className="text-[#64748B]">{item.value} 条</span></div><div className="h-2 overflow-hidden rounded-full bg-[#1E293B]"><div className="h-full rounded-full bg-[#6366F1]" style={{ width: `${Math.max(6, Number(item.value || 0) / maxPlatform * 100)}%` }} /></div></div>)}</div>}
        </Panel>
        <Panel title="市场话题与热度" description="AI将分散信息归并为用户正在讨论的话题。">
          {report.topic_trends.length === 0 ? <EmptyState title="暂无话题趋势" description="扩大问题范围后再试。" /> : <div className="space-y-3">{report.topic_trends.slice(0, 6).map((item) => <div key={item.topic} className="flex items-center gap-3 rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-3"><BarChart3 className="h-4 w-4 text-[#38BDF8]" /><div className="min-w-0 flex-1"><p className="truncate text-sm text-[#E2E8F0]">{item.topic}</p><p className="mt-1 text-xs text-[#64748B]">{item.count} 条讨论 · 互动 {formatNumber(item.engagement)}</p></div></div>)}</div>}
        </Panel>
      </div>
      <Panel title="客户真实声音" description="帮助判断客户在问什么、担心什么，而不是只看指标。">
        <div className="grid gap-3 lg:grid-cols-3">{report.customer_voice.slice(0, 6).map((item, index) => <div key={`${item.theme}-${index}`} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4"><p className="text-sm font-medium text-[#E2E8F0]">{item.theme}</p><p className="mt-2 text-xs leading-5 text-[#94A3B8]">{item.summary}</p><p className="mt-2 text-xs text-[#64748B]">相关表达 {item.count} 条</p></div>)}</div>
      </Panel>
      <Panel title="建议下一步" description="可以继续沉淀客户，或切换到公开评论获客让AI寻找合适视频。">
        <div className="space-y-3">{report.actions.slice(0, 4).map((item, index) => <button key={`${item.title}-${index}`} onClick={() => navigate('/marketing/customers')} className="flex w-full items-center gap-3 rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4 text-left hover:border-[#6366F1]"><div className="flex-1"><p className="text-sm font-medium text-[#F1F5F9]">{item.title}</p><p className="mt-1 text-xs text-[#64748B]">{item.description}</p></div><Check className="h-4 w-4 text-[#64748B]" /></button>)}</div>
      </Panel>
      <Panel title="公开依据与连接状态" description="只显示真实来源；登录失败或平台受限会明确说明。">
        <div className="mb-4 flex flex-wrap gap-2">{report.data_scope.source_health.map((item) => <StatusChip key={`${item.source}-${item.label}`} ok={item.status === 'success'} text={`${item.label}：${statusText[item.status] || item.message || item.status}`} />)}</div>
        <div className="grid gap-3 lg:grid-cols-2">{report.evidence.slice(0, 8).map((item) => <a key={item.id} href={item.source_url || '#'} target="_blank" rel="noreferrer" className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4 hover:border-[#334155]"><p className="text-sm font-medium text-[#E2E8F0]">{item.title}</p><p className="mt-2 line-clamp-2 text-xs leading-5 text-[#64748B]">{item.reason || item.summary}</p></a>)}</div>
      </Panel>
    </>}
  </div>
}

function PublicCommentCampaign() {
  const navigate = useNavigate()
  const [objective, setObjective] = useState('')
  const [platforms, setPlatforms] = useState<string[]>(['douyin', 'xhs', 'bilibili'])
  const [plan, setPlan] = useState<CommentCampaignPlan | null>(null)
  const [items, setItems] = useState<CommentCampaignItem[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [queue, setQueue] = useState<CommentQueueItem[]>([])
  const [targets, setTargets] = useState<MonitorTarget[]>([])
  const [loading, setLoading] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const refreshActivity = () => Promise.all([
    acquisitionCommentQueue({ limit: 8 }).then((data) => setQueue(data.items || [])).catch(() => setQueue([])),
    acquisitionMonitorTargets().then((data) => setTargets((data.targets || []).filter((item) => item.owner === 'comment_campaign'))).catch(() => setTargets([])),
  ])
  useEffect(() => { void refreshActivity() }, [])
  const usableSelected = useMemo(() => [...selected].filter((index) => { const item = items[index]; return Boolean(item?.account_ready && item.comment_text.trim() && item.preflight?.decision !== 'skip') }), [items, selected])

  const createPlan = async () => {
    if (objective.trim().length < 4) return setError('请说明希望找到哪类客户，以及想围绕什么问题交流')
    if (platforms.length === 0) return setError('请至少选择一个平台')
    setLoading(true); setError(''); setSuccess('')
    try {
      const result = await acquisitionPlanCommentCampaign({ objective: objective.trim(), platforms, max_targets: 6, min_score: 35, strategy: 'balanced' })
      setPlan(result); setItems(result.items || [])
      setSelected(new Set((result.items || []).map((item, index) => item.account_ready && item.comment_text ? index : -1).filter((index) => index >= 0)))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'AI寻找视频失败') }
    finally { setLoading(false) }
  }
  const execute = async () => {
    if (usableSelected.length === 0) return setError('没有可以执行的评论，请先登录经营账号并检查评论内容')
    const summary = usableSelected.map((index) => `${platformLabel(items[index].platform)}《${items[index].video_title.slice(0, 28)}》`).join('\n')
    if (!window.confirm(`将使用已连接的经营账号执行 ${usableSelected.length} 条公开评论，并持续监听这些内容的后续回复：\n\n${summary}\n\n确认继续吗？`)) return
    setExecuting(true); setError(''); setSuccess('')
    try {
      const result = await acquisitionExecuteCommentCampaign({ confirmed: true, monitor_replies: true, strategy: 'balanced', items: usableSelected.map((index) => ({ platform: items[index].platform, account_id: items[index].account_id, video_id: items[index].video_id, video_title: items[index].video_title, video_url: items[index].video_url, comment_text: items[index].comment_text.trim() })) })
      setSuccess(`已确认 ${result.items.length} 条评论，系统会错峰执行并监听这些内容的后续回复。`)
      await refreshActivity()
    } catch (cause) { setError(cause instanceof Error ? cause.message : '批量评论未能进入执行队列') }
    finally { setExecuting(false) }
  }

  return <div className="space-y-5">
    {error && <ErrorBanner text={error} />}{success && <div className="rounded-lg border border-[#10B981]/30 bg-[#10B981]/10 px-4 py-3 text-sm text-[#6EE7B7]">{success}</div>}
    <section className="rounded-xl border border-[#334155] bg-[#101827] p-5">
      <p className="text-xs font-medium text-[#818CF8]">告诉AI业务目标，它会自己寻找合适的公开视频</p>
      <textarea value={objective} onChange={(e) => setObjective(e.target.value.slice(0, 500))} className={`${inputClass} mt-3 min-h-24 resize-none`} placeholder="例如：寻找正在讨论门店客流减少、不会做线上营销的中小企业主，以有帮助的建议参与讨论" />
      <div className="mt-4 flex flex-wrap items-center gap-2">{PLATFORM_OPTIONS.map((item) => { const active = platforms.includes(item.value); return <button key={item.value} onClick={() => setPlatforms((current) => active ? current.filter((value) => value !== item.value) : [...current, item.value])} className={`rounded-full border px-3 py-1.5 text-xs ${active ? 'border-[#6366F1] bg-[#6366F1]/15 text-[#C4B5FD]' : 'border-[#334155] text-[#94A3B8]'}`}>{active && <Check className="mr-1 inline h-3 w-3" />}{item.label}</button> })}<button onClick={createPlan} disabled={loading} className={`${buttonPrimary} ml-auto`}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}AI寻找并准备评论</button></div>
    </section>
    {plan && <>
      <Panel title="AI本轮工作思路" description="搜索词来自业务目标和企业资料；每条评论都结合对应视频单独生成。">
        <div className="grid gap-3 lg:grid-cols-3"><InfoBox label="寻找什么" text={plan.brief.search_query} /><InfoBox label="目标客户" text={plan.brief.audience} /><InfoBox label="交流角度" text={plan.brief.engagement_angle} /></div>
        <div className="mt-4 flex flex-wrap gap-2">{plan.platforms.map((item) => <StatusChip key={item.platform} ok={item.status === 'success'} text={`${platformLabel(item.platform)}：${statusText[item.status] || item.message || item.status}`} />)}</div>
      </Panel>
      <Panel title={`待确认评论（${usableSelected.length}/${items.length}）`} description="AI不会把同一句话群发；你可以逐条修改或取消勾选。">
        {items.length === 0 ? <EmptyState title="本轮没有找到合适视频" description="检查平台连接状态，或换一种更具体的客户痛点描述。" /> : <div className="space-y-4">{items.map((item, index) => <CommentCard key={`${item.platform}-${item.video_id || item.video_url}-${index}`} item={item} checked={selected.has(index)} onToggle={() => setSelected((current) => { const next = new Set(current); next.has(index) ? next.delete(index) : next.add(index); return next })} onText={(text) => setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, comment_text: text.slice(0, 300) } : row))} onLogin={() => navigate('/publish/accounts')} />)}</div>}
        {items.length > 0 && <div className="mt-5 flex justify-end"><button onClick={execute} disabled={executing || usableSelected.length === 0} className={buttonPrimary}>{executing ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}确认并批量执行 {usableSelected.length} 条</button></div>}
      </Panel>
    </>}
    <div className="grid gap-5 xl:grid-cols-2"><ActivityPanel queue={queue} /><MonitoringPanel targets={targets} /></div>
    <div className="rounded-lg border border-[#F59E0B]/25 bg-[#F59E0B]/5 p-4 text-xs leading-5 text-[#FCD34D]"><AlertTriangle className="mr-2 inline h-4 w-4" />批量评论仍受平台规则、账号状态和频率限制。系统默认错峰执行，且每批都必须由你确认；不支持的平台不会模拟发送成功。</div>
  </div>
}

function CommentCard({ item, checked, onToggle, onText, onLogin }: { item: CommentCampaignItem; checked: boolean; onToggle: () => void; onText: (text: string) => void; onLogin: () => void }) {
  return <div className={`rounded-lg border p-4 ${checked ? 'border-[#6366F1]/60 bg-[#6366F1]/5' : 'border-[#1E293B] bg-[#0B0F1A]'}`}><div className="flex items-start gap-3"><button onClick={onToggle} className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border ${checked ? 'border-[#6366F1] bg-[#6366F1] text-white' : 'border-[#475569]'}`}>{checked && <Check className="h-3 w-3" />}</button><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="text-xs text-[#818CF8]">{platformLabel(item.platform)}</span><span className="rounded-full border border-[#334155] px-2 py-0.5 text-xs text-[#94A3B8]">匹配度 {Math.round(item.quality_score || 0)}</span>{item.video_url && <a href={item.video_url} target="_blank" rel="noreferrer" className="text-xs text-[#38BDF8] hover:underline">查看原视频 <ExternalLink className="inline h-3 w-3" /></a>}</div><p className="mt-2 text-sm font-medium text-[#F1F5F9]">{item.video_title || '未命名公开内容'}</p><p className="mt-1 text-xs text-[#64748B]">{item.author || '公开作者'} · 播放 {formatNumber(item.plays)} · 评论 {formatNumber(item.comments_count)}</p></div><StatusChip ok={item.account_ready} text={item.account_ready ? `使用 ${item.account_label}` : '经营账号需登录'} /></div><textarea value={item.comment_text} onChange={(e) => onText(e.target.value)} className={`${inputClass} mt-4 min-h-20 resize-y`} placeholder={item.generation_error ? `生成失败：${item.generation_error}` : 'AI将为这条视频单独生成自然、有帮助的评论'} />{!item.account_ready && <button onClick={onLogin} className="mt-3 text-xs text-[#FCD34D] hover:underline">前往渠道账号完成登录</button>}</div>
}

function ActivityPanel({ queue }: { queue: CommentQueueItem[] }) { return <Panel title="最近评论执行" description="这里只展示真实队列状态，不会用占位成功掩盖失败。">{queue.length === 0 ? <EmptyState title="还没有评论任务" description="确认一批评论后，执行过程会显示在这里。" /> : <div className="space-y-3">{queue.slice(0, 6).map((item, index) => <div key={item.id || item.item_id || index} className="flex items-start gap-3 rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-3"><PlayCircle className="mt-0.5 h-4 w-4 text-[#818CF8]" /><div className="min-w-0 flex-1"><p className="truncate text-sm text-[#E2E8F0]">{item.video_title || item.target_url || '公开评论'}</p><p className="mt-1 text-xs text-[#64748B]">{platformLabel(item.platform)} · {formatDateTime(item.created_at)}</p></div><span className="text-xs text-[#94A3B8]">{item.status || '排队中'}</span></div>)}</div>}</Panel> }
function MonitoringPanel({ targets }: { targets: MonitorTarget[] }) { return <Panel title="正在监听的评论机会" description="只追踪已发评论的回复线程，不会把整条视频的其他评论误认为客户回复。">{targets.length === 0 ? <EmptyState title="还没有精确回复监听" description="平台确认评论并返回评论编号后，系统会持续检查这条评论收到的新回复。" /> : <div className="space-y-3">{targets.slice(0, 6).map((item, index) => <div key={item.target_id || item.id || index} className="flex items-start gap-3 rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-3"><Radar className={`mt-0.5 h-4 w-4 ${item.last_error ? 'text-[#F59E0B]' : 'text-[#34D399]'}`} /><div className="min-w-0 flex-1"><p className="truncate text-sm text-[#E2E8F0]">{item.video_title || item.video_url || '公开内容'}</p><p className="mt-1 text-xs text-[#64748B]">{platformLabel(item.platform)} · 精确回复监听 · 最近检查 {formatDateTime(item.last_poll_at)}</p>{item.last_error && <p className="mt-1 text-xs text-[#FCD34D]">{item.last_error}</p>}</div></div>)}</div>}</Panel> }
function ErrorBanner({ text }: { text: string }) { return <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{text}</div> }
function StatusChip({ ok, text }: { ok: boolean; text: string }) { return <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs ${ok ? 'border-[#10B981]/30 bg-[#10B981]/5 text-[#6EE7B7]' : 'border-[#F59E0B]/30 bg-[#F59E0B]/5 text-[#FCD34D]'}`}>{text}</span> }
function InfoBox({ label, text }: { label: string; text: string }) { return <div className="rounded-lg bg-[#0B0F1A] p-4"><p className="text-xs text-[#64748B]">{label}</p><p className="mt-2 text-sm text-[#E2E8F0]">{text}</p></div> }

export default function Opportunities() {
  const [params, setParams] = useSearchParams()
  const [view, setView] = useState<View>(params.get('view') === 'comments' ? 'comments' : 'research')
  const switchView = (next: View) => { setView(next); setParams(next === 'comments' ? { view: 'comments' } : {}) }
  return <PageShell title="客户机会" subtitle="广泛搜索市场信息，或让AI寻找合适的公开视频并准备个性化评论。" icon={Search}><div className="inline-flex w-fit rounded-lg border border-[#334155] bg-[#0B0F1A] p-1"><button onClick={() => switchView('research')} className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm ${view === 'research' ? 'bg-[#1E293B] text-white' : 'text-[#94A3B8]'}`}><Search className="h-4 w-4" />市场与客户机会</button><button onClick={() => switchView('comments')} className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm ${view === 'comments' ? 'bg-[#1E293B] text-white' : 'text-[#94A3B8]'}`}><MessageCircle className="h-4 w-4" />公开评论获客</button></div>{view === 'research' ? <MarketResearch /> : <PublicCommentCampaign />}</PageShell>
}
