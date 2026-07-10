import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  Eye,
  Fish,
  Loader2,
  MessageSquareText,
  Search,
  Send,
  ShieldCheck,
  Target,
} from 'lucide-react'
import {
  acquisitionCommentQueue,
  acquisitionCommentStats,
  acquisitionDeAI,
  acquisitionFindTargets,
  acquisitionGenerateComments,
  acquisitionPreflight,
  type AcquisitionStatsResponse,
  type AcquisitionTarget,
  type CommentQueueItem,
  type PreflightResult,
} from '@/lib/api'
import {
  EmptyState,
  FieldLabel,
  MetricCard,
  PLATFORM_OPTIONS,
  PageShell,
  Panel,
  STRATEGY_OPTIONS,
  StatusPill,
  buttonPrimary,
  buttonSecondary,
  formatNumber,
  inputClass,
  normalizeQueueMetrics,
  platformLabel,
  scoreTone,
} from './MarketingShared'

type GeneratedComment = {
  original: string
  processed: string
  preflight?: PreflightResult
}

function scoreDetailText(detail: AcquisitionTarget['score_detail']): string {
  if (!detail) return '暂无评分说明'
  if (typeof detail === 'string') return detail
  return Object.entries(detail).map(([key, value]) => `${key}: ${String(value)}`).join(' / ')
}

export default function Intercept() {
  const [keyword, setKeyword] = useState('本地生活 获客')
  const [platforms, setPlatforms] = useState<string[]>(['douyin', 'xhs'])
  const [minScore, setMinScore] = useState(40)
  const [limit, setLimit] = useState(20)
  const [strategy, setStrategy] = useState('balanced')
  const [targets, setTargets] = useState<AcquisitionTarget[]>([])
  const [selected, setSelected] = useState<AcquisitionTarget | null>(null)
  const [comments, setComments] = useState<GeneratedComment[]>([])
  const [queue, setQueue] = useState<CommentQueueItem[]>([])
  const [stats, setStats] = useState<AcquisitionStatsResponse>({})
  const [loadingTargets, setLoadingTargets] = useState(false)
  const [loadingComments, setLoadingComments] = useState(false)
  const [loadingQueue, setLoadingQueue] = useState(false)
  const [error, setError] = useState('')

  const highScoreCount = useMemo(
    () => targets.filter((item) => Number(item.quality_score || 0) >= 80).length,
    [targets],
  )

  const queueMetrics = useMemo(() => normalizeQueueMetrics(stats), [stats])
  const selectedPlatform = selected?.platform || platforms[0] || 'douyin'

  const loadQueue = async () => {
    setLoadingQueue(true)
    try {
      const [queueData, statsData] = await Promise.all([
        acquisitionCommentQueue({ limit: 8 }),
        acquisitionCommentStats(),
      ])
      setQueue(queueData.items || [])
      setStats(statsData || {})
    } catch (e) {
      setError(e instanceof Error ? e.message : '队列加载失败')
    } finally {
      setLoadingQueue(false)
    }
  }

  useEffect(() => {
    loadQueue()
  }, [])

  const togglePlatform = (value: string) => {
    setPlatforms((prev) => {
      if (prev.includes(value)) {
        const next = prev.filter((item) => item !== value)
        return next.length ? next : prev
      }
      return [...prev, value]
    })
  }

  const findTargets = async () => {
    if (!keyword.trim()) {
      setError('请输入关键词')
      return
    }
    setError('')
    setLoadingTargets(true)
    setComments([])
    try {
      const data = await acquisitionFindTargets({
        keyword: keyword.trim(),
        platforms,
        limit,
        min_score: minScore,
      })
      const items = data.targets || data.videos || []
      setTargets(items)
      setSelected(items[0] || null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '目标搜索失败')
    } finally {
      setLoadingTargets(false)
    }
  }

  const generateForSelected = async () => {
    if (!selected) return
    setLoadingComments(true)
    setError('')
    try {
      const generated = await acquisitionGenerateComments({
        video_title: selected.title,
        video_description: selected.description || '',
        count: 3,
        strategy,
      })
      const processed = await Promise.all(
        (generated.comments || []).map(async (text) => {
          const deai = await acquisitionDeAI(text, selectedPlatform)
          const preflight = await acquisitionPreflight(deai.processed)
          return { original: text, processed: deai.processed, preflight }
        }),
      )
      setComments(processed)
    } catch (e) {
      setError(e instanceof Error ? e.message : '评论生成失败')
    } finally {
      setLoadingComments(false)
    }
  }

  const confirmExternalAction = (label: string) => {
    if (confirm(`确认${label}？请确保账号状态、目标内容和话术风险已经人工检查。`)) {
      alert('v1 已保留确认入口。真实发送将接入队列执行与 Execution Kernel 观测。')
    }
  }

  return (
    <PageShell
      title="智能截流作战台"
      subtitle="发现高质量目标内容，生成安全评论，并把发送动作放进可审核、可观测的执行链路。"
      icon={Fish}
    >
      {error && (
        <div className="flex items-center justify-between rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-[#FCA5A5] hover:text-white">关闭</button>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="发现目标" value={formatNumber(targets.length)} icon={Target} hint="来自当前关键词搜索" />
        <MetricCard label="高分机会" value={highScoreCount} icon={ShieldCheck} tone="green" hint="质量分 80 以上" />
        <MetricCard label="待发送队列" value={formatNumber(queueMetrics.pending)} icon={MessageSquareText} tone="blue" hint="评论队列观测" />
        <MetricCard label="需人工处理" value={formatNumber(queueMetrics.needsHuman)} icon={AlertTriangle} tone="amber" hint="失败、跳过或需人工确认" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
        <Panel title="输入目标" description="先找目标，不直接发送。">
          <div className="space-y-4">
            <div>
              <FieldLabel>关键词</FieldLabel>
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} className={inputClass} placeholder="例如：装修 获客" />
            </div>
            <div>
              <FieldLabel>平台</FieldLabel>
              <div className="grid grid-cols-2 gap-2">
                {PLATFORM_OPTIONS.map((item) => (
                  <button
                    key={item.value}
                    onClick={() => togglePlatform(item.value)}
                    className={`rounded-lg border px-3 py-2 text-sm transition-colors ${
                      platforms.includes(item.value)
                        ? 'border-[#6366F1] bg-[#6366F1]/15 text-[#C4B5FD]'
                        : 'border-[#334155] bg-[#0B0F1A] text-[#94A3B8] hover:border-[#6366F1]'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel>最低质量分</FieldLabel>
                <input type="number" min={0} max={100} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} className={inputClass} />
              </div>
              <div>
                <FieldLabel>目标数量</FieldLabel>
                <input type="number" min={1} max={100} value={limit} onChange={(e) => setLimit(Number(e.target.value))} className={inputClass} />
              </div>
            </div>
            <div>
              <FieldLabel>评论策略</FieldLabel>
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className={inputClass}>
                {STRATEGY_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>
            <button onClick={findTargets} disabled={loadingTargets} className={`${buttonPrimary} w-full`}>
              {loadingTargets ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              搜索目标
            </button>
          </div>
        </Panel>

        <Panel
          title="筛选目标"
          description="按质量分排序查看目标内容，选择后生成评论草稿。"
          action={<button onClick={loadQueue} className={buttonSecondary}>{loadingQueue ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}刷新队列</button>}
        >
          {targets.length === 0 ? (
            <EmptyState title="还没有目标内容" description="输入关键词后先搜索目标，系统会返回平台、作者、互动数据和质量评分。" />
          ) : (
            <div className="overflow-hidden rounded-lg border border-[#1E293B]">
              <table className="w-full text-left text-sm">
                <thead className="bg-[#0B0F1A] text-xs text-[#64748B]">
                  <tr>
                    <th className="px-3 py-3">平台</th>
                    <th className="px-3 py-3">标题</th>
                    <th className="px-3 py-3">作者</th>
                    <th className="px-3 py-3">互动</th>
                    <th className="px-3 py-3">质量分</th>
                    <th className="px-3 py-3">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1E293B]">
                  {targets.map((item, index) => (
                    <tr key={`${item.platform}-${item.video_id || index}`} className={selected === item ? 'bg-[#6366F1]/10' : 'hover:bg-[#0B0F1A]/60'}>
                      <td className="px-3 py-3 text-[#CBD5E1]">{platformLabel(item.platform)}</td>
                      <td className="max-w-sm px-3 py-3">
                        <p className="truncate font-medium text-[#F1F5F9]">{item.title}</p>
                        <p className="mt-1 truncate text-xs text-[#64748B]">{scoreDetailText(item.score_detail)}</p>
                      </td>
                      <td className="px-3 py-3 text-[#94A3B8]">{item.author || '-'}</td>
                      <td className="px-3 py-3 text-xs text-[#94A3B8]">
                        播放 {formatNumber(item.plays)} · 评 {formatNumber(item.comments_count)}
                      </td>
                      <td className="px-3 py-3">
                        <span className={`rounded-full border px-2 py-1 text-xs ${scoreTone(item.quality_score)}`}>
                          {item.quality_score ?? 0}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <button onClick={() => setSelected(item)} className={buttonSecondary}>
                          <Eye className="h-4 w-4" />
                          查看
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <Panel
          title="评论生成与风险预检"
          description="生成评论后自动 DeAI，并逐条展示发前检查结果。"
          action={
            <button onClick={generateForSelected} disabled={!selected || loadingComments} className={buttonPrimary}>
              {loadingComments ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
              生成评论
            </button>
          }
        >
          {!selected ? (
            <EmptyState title="请选择目标内容" description="选中一个目标后，可以生成评论草稿、去 AI 味并做风险预检。" />
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-[#F1F5F9]">{selected.title}</p>
                    <p className="mt-1 text-xs text-[#64748B]">{platformLabel(selected.platform)} · {selected.author || '未知作者'} · 质量分 {selected.quality_score ?? 0}</p>
                  </div>
                  {selected.url && (
                    <a className="text-xs text-[#818CF8] hover:text-white" href={selected.url} target="_blank" rel="noreferrer">打开来源</a>
                  )}
                </div>
              </div>

              {comments.length === 0 ? (
                <EmptyState title="还没有评论草稿" description="点击生成评论后，系统会展示原文、DeAI 文本和预检结果。" />
              ) : (
                <div className="space-y-3">
                  {comments.map((item, index) => {
                    const passed = item.preflight?.pass ?? item.preflight?.passed ?? item.preflight?.ok
                    const risk = String(item.preflight?.risk_level || item.preflight?.risk || (passed === false ? 'high' : 'low')).toLowerCase()
                    const risks = item.preflight?.risks || item.preflight?.reasons || []
                    const blocked = passed === false || risk === 'high'
                    return (
                      <div key={`${item.processed}-${index}`} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <p className="text-xs text-[#64748B]">DeAI 后评论</p>
                            <p className="mt-2 text-sm leading-6 text-[#F1F5F9]">{item.processed}</p>
                            {item.original !== item.processed && (
                              <p className="mt-2 text-xs leading-5 text-[#64748B]">原始：{item.original}</p>
                            )}
                          </div>
                          <span className={`rounded-full border px-2 py-1 text-xs ${blocked ? 'border-[#EF4444]/25 bg-[#EF4444]/10 text-[#FCA5A5]' : risk === 'medium' ? 'border-[#F59E0B]/25 bg-[#F59E0B]/10 text-[#FCD34D]' : 'border-[#10B981]/25 bg-[#10B981]/10 text-[#86EFAC]'}`}>
                            {blocked ? '预检未通过' : risk === 'medium' ? '中风险需确认' : '预检通过'}
                          </span>
                        </div>
                        {item.preflight?.message && <p className="mt-3 text-xs text-[#94A3B8]">{item.preflight.message}</p>}
                        {risks.length > 0 && (
                          <div className="mt-3 rounded-lg border border-[#F59E0B]/20 bg-[#F59E0B]/10 p-3">
                            <p className="text-xs font-medium text-[#FCD34D]">风险提示</p>
                            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-[#FDE68A]">
                              {risks.map((reason, reasonIndex) => <li key={`${reason}-${reasonIndex}`}>{reason}</li>)}
                            </ul>
                          </div>
                        )}
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button onClick={() => confirmExternalAction('加入待发送队列')} className={buttonSecondary}>
                            <MessageSquareText className="h-4 w-4" />
                            预览队列入口
                          </button>
                          <button onClick={() => confirmExternalAction('发送评论')} disabled={blocked} className={buttonSecondary}>
                            <Send className="h-4 w-4" />
                            {blocked ? '高风险需人工' : '预览发送确认'}
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </Panel>

        <Panel title="队列观测" description="发送动作必须进入可观测状态，不做黑箱执行。">
          {queue.length === 0 ? (
            <EmptyState title="暂无队列任务" description="生成评论并确认后，后续任务会在这里展示状态、失败原因和人工处理提示。" />
          ) : (
            <div className="space-y-3">
              {queue.map((item, index) => (
                <div key={item.id || item.item_id || index} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs text-[#94A3B8]">{platformLabel(item.platform)}</span>
                    <StatusPill status={item.status} />
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-[#F1F5F9]">{item.text || item.comment || item.video_title || '评论任务'}</p>
                  {item.error && <p className="mt-2 text-xs text-[#FCA5A5]">{item.error}</p>}
                </div>
              ))}
            </div>
          )}
          <div className="mt-4 rounded-lg border border-[#334155] bg-[#0B0F1A] p-3 text-xs leading-5 text-[#64748B]">
            <div className="mb-2 flex items-center gap-2 text-[#CBD5E1]">
              <CheckCircle2 className="h-4 w-4 text-[#10B981]" />
              安全执行规则
            </div>
            评论发送、私信、自动回复必须经过预览、预检和人工确认。高风险、验证码、账号异常会进入需人工处理。
          </div>
        </Panel>
      </div>
    </PageShell>
  )
}
