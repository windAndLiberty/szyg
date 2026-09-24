import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Archive,
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ExternalLink,
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
  acquisitionEnqueueCommentBatch,
  acquisitionFindTargets,
  acquisitionGenerateComments,
  acquisitionPreflight,
  type AcquisitionStatsResponse,
  type AcquisitionPlatformStatus,
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
import { translateCurrent, useI18n } from '@/lib/i18n'

type GeneratedComment = {
  original: string
  processed: string
  preflight?: PreflightResult
  queueStatus?: string
  queueItemId?: string
}

type CommentQueueGroup = {
  id: string
  batchId: string
  commentText: string
  createdAt: string
  items: CommentQueueItem[]
}

const MAX_SELECTED_TARGETS = 5

function targetKey(target: AcquisitionTarget): string {
  return `${target.platform}:${target.video_id || target.url || target.title}`
}

function scoreDetailText(detail: AcquisitionTarget['score_detail']): string {
  if (!detail) return translateCurrent("暂无评分说明")
  if (typeof detail === 'string') return detail
  return Object.entries(detail).map(([key, value]) => `${key}: ${String(value)}`).join(' / ')
}

function targetSourceUrl(target: AcquisitionTarget): string {
  const raw = String(target.url || '').trim()
  if (!raw) return ''
  const candidate = raw.startsWith('//') ? `https:${raw}` : raw
  try {
    const url = new URL(candidate)
    return ['http:', 'https:'].includes(url.protocol) ? url.toString() : ''
  } catch {
    return ''
  }
}

function queueBatchId(item: CommentQueueItem): string {
  const metadata = item.metadata && typeof item.metadata === 'object' ? item.metadata : {}
  return String(item.batch_id || metadata.batch_id || '').trim()
}

function legacyQueueGroupId(item: CommentQueueItem, index: number): string {
  const timestamp = Date.parse(String(item.created_at || ''))
  if (!Number.isFinite(timestamp)) return `single:${String(item.id || item.item_id || index)}`
  const tenMinuteWindow = Math.floor(timestamp / (10 * 60 * 1000))
  return `legacy:${tenMinuteWindow}:${queueCommentText(item)}`
}

function queueTargetKey(item: CommentQueueItem): string {
  return `${String(item.platform || '')}:${String(item.video_id || item.target_url || item.video_url || item.video_title || '')}`
}

function queueCommentText(item: CommentQueueItem): string {
  return String(item.comment_text || item.repaired_text || item.text || item.comment || translateCurrent("评论任务"))
}

function queueSourceUrl(item: CommentQueueItem): string {
  const raw = String(item.target_url || item.video_url || '').trim()
  if (!raw) return ''
  const candidate = raw.startsWith('//') ? `https:${raw}` : raw
  try {
    const url = new URL(candidate)
    return ['http:', 'https:'].includes(url.protocol) ? url.toString() : ''
  } catch {
    return ''
  }
}

function isQueueSent(item: CommentQueueItem): boolean {
  return ['sent', 'success', 'completed'].includes(String(item.status || '').toLowerCase())
}

function queueGroupStatus(items: CommentQueueItem[]): string {
  const statuses = items.map((item) => String(item.status || '').toLowerCase())
  if (items.length > 0 && items.every(isQueueSent)) return 'sent'
  if (statuses.some((status) => ['needs_human', 'review', 'pending_review'].includes(status))) return 'needs_human'
  if (statuses.some((status) => ['pending', 'queued', 'running', 'sending', 'processing', 'delayed', 'retrying'].includes(status))) return 'running'
  if (statuses.some((status) => ['failed', 'error', 'blocked'].includes(status))) return 'failed'
  return statuses[0] || 'pending'
}

export default function Intercept() {
  const { t } = useI18n()
  const [keyword, setKeyword] = useState(t("本地生活 获客"))
  const [platforms, setPlatforms] = useState<string[]>(['douyin', 'xhs'])
  const [minScore, setMinScore] = useState(40)
  const [limit, setLimit] = useState(20)
  const [strategy, setStrategy] = useState('balanced')
  const [targets, setTargets] = useState<AcquisitionTarget[]>([])
  const [platformStatuses, setPlatformStatuses] = useState<AcquisitionPlatformStatus[]>([])
  const [selectedTargetKeys, setSelectedTargetKeys] = useState<string[]>([])
  const [comments, setComments] = useState<GeneratedComment[]>([])
  const [selectedCommentIndex, setSelectedCommentIndex] = useState<number | null>(null)
  const [queue, setQueue] = useState<CommentQueueItem[]>([])
  const [stats, setStats] = useState<AcquisitionStatsResponse>({})
  const [loadingTargets, setLoadingTargets] = useState(false)
  const [loadingComments, setLoadingComments] = useState(false)
  const [loadingQueue, setLoadingQueue] = useState(false)
  const [submittingBatch, setSubmittingBatch] = useState(false)
  const [queueView, setQueueView] = useState<'active' | 'archived'>('active')
  const [expandedQueueGroups, setExpandedQueueGroups] = useState<Set<string>>(new Set())
  const [error, setError] = useState('')

  const highScoreCount = useMemo(
    () => targets.filter((item) => Number(item.quality_score || 0) >= 80).length,
    [targets],
  )

  const queueMetrics = useMemo(() => normalizeQueueMetrics(stats), [stats])
  const selectedTargets = useMemo(
    () => targets.filter((item) => selectedTargetKeys.includes(targetKey(item))),
    [targets, selectedTargetKeys],
  )
  const queueGroups = useMemo<CommentQueueGroup[]>(() => {
    const groups = new Map<string, CommentQueueGroup>()
    queue.forEach((item, index) => {
      const batchId = queueBatchId(item)
      const itemId = String(item.id || item.item_id || index)
      let groupId = batchId || legacyQueueGroupId(item, index)
      const legacyGroup = groups.get(groupId)
      if (!batchId && legacyGroup?.items.some((queuedItem) => queueTargetKey(queuedItem) === queueTargetKey(item))) {
        groupId = `single:${itemId}`
      }
      const existing = groups.get(groupId)
      if (existing) {
        existing.items.push(item)
        return
      }
      groups.set(groupId, {
        id: groupId,
        batchId,
        commentText: queueCommentText(item),
        createdAt: String(item.created_at || ''),
        items: [item],
      })
    })
    return Array.from(groups.values())
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .slice(0, 8)
  }, [queue])

  const loadQueue = async (view: 'active' | 'archived' = queueView) => {
    setLoadingQueue(true)
    try {
      const [queueData, statsData] = await Promise.all([
        acquisitionCommentQueue({ archived: view === 'archived', limit: 50 }),
        acquisitionCommentStats(),
      ])
      setQueue(queueData.items || [])
      setStats(statsData || {})
    } catch (e) {
      setError(e instanceof Error ? e.message : t("队列加载失败"))
    } finally {
      setLoadingQueue(false)
    }
  }

  useEffect(() => {
    void loadQueue(queueView)
  }, [queueView])

  useEffect(() => {
    const newestBatch = queueGroups.find((group) => group.items.length > 1)
    if (!newestBatch) return
    setExpandedQueueGroups((previous) => {
      if (previous.size > 0) return previous
      return new Set([newestBatch.id])
    })
  }, [queueGroups])

  const toggleQueueGroup = (groupId: string) => {
    setExpandedQueueGroups((previous) => {
      const next = new Set(previous)
      if (next.has(groupId)) next.delete(groupId)
      else next.add(groupId)
      return next
    })
  }

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
      setError(t("请输入关键词"))
      return
    }
    setError('')
    setLoadingTargets(true)
    setSelectedTargetKeys([])
    setComments([])
    setSelectedCommentIndex(null)
    try {
      const data = await acquisitionFindTargets({
        keyword: keyword.trim(),
        platforms,
        limit,
        min_score: minScore,
      })
      const items = data.targets || data.videos || []
      setTargets(items)
      setPlatformStatuses(data.platforms || [])
    } catch (e) {
      setPlatformStatuses([])
      setError(e instanceof Error ? e.message : t("目标搜索失败"))
    } finally {
      setLoadingTargets(false)
    }
  }

  const toggleTarget = (target: AcquisitionTarget) => {
    const key = targetKey(target)
    setComments([])
    setSelectedCommentIndex(null)
    setSelectedTargetKeys((current) => {
      if (current.includes(key)) return current.filter((item) => item !== key)
      if (current.length >= MAX_SELECTED_TARGETS) {
        setError(t("一次最多选择 {v0} 个视频生成评论", { v0: MAX_SELECTED_TARGETS }))
        return current
      }
      setError('')
      return [...current, key]
    })
  }

  const generateForSelected = async () => {
    if (selectedTargets.length === 0) return
    setLoadingComments(true)
    setError('')
    try {
      const targetSummary = selectedTargets
        .map((target, index) => `${index + 1}. ${target.title}`)
        .join('\n')
      const generated = await acquisitionGenerateComments({
        video_title: `${selectedTargets.length} 个待互动视频`,
        video_description: `请生成能自然用于以下视频讨论区的候选评论。评论不要假装看过未提供的细节，也不要出现营销联系方式。\n${targetSummary}`,
        count: 5,
        strategy,
        shared_across_targets: true,
      })
      const processed = await Promise.all(
        (generated.comments || []).slice(0, 5).map(async (text) => {
          const deai = await acquisitionDeAI(text, selectedTargets[0]?.platform || 'douyin')
          const preflight = await acquisitionPreflight(deai.processed)
          return { original: text, processed: deai.processed, preflight }
        }),
      )
      setComments(processed)
      setSelectedCommentIndex(processed.length > 0 ? 0 : null)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("评论生成失败"))
    } finally {
      setLoadingComments(false)
    }
  }

  const updateCandidate = (index: number, value: string) => {
    setComments((current) => current.map((comment, commentIndex) => commentIndex === index
      ? { ...comment, processed: value, preflight: undefined }
      : comment))
    setSelectedCommentIndex(index)
  }

  const enqueueSelectedComment = async () => {
    if (selectedCommentIndex === null || selectedTargets.length === 0) return
    const selectedComment = comments[selectedCommentIndex]
    if (!selectedComment || selectedComment.queueStatus) return
    const text = selectedComment.processed.trim()
    if (!text) {
      setError(t("评论内容不能为空"))
      return
    }

    setSubmittingBatch(true)
    setError('')
    try {
      const latestCheck = await acquisitionPreflight(text)
      const blocked = latestCheck.decision === 'needs_human' || latestCheck.decision === 'skip' || latestCheck.risk_level === 'high'
      if (blocked) {
        setComments((current) => current.map((comment, index) => index === selectedCommentIndex ? { ...comment, preflight: latestCheck } : comment))
        setError(t("当前评论存在风险，请修改后再发送"))
        return
      }

      const targetList = selectedTargets.map((target, index) => `${index + 1}. ${platformLabel(target.platform)} · ${target.title}`).join('\n')
      const confirmed = confirm(t("确认将这条评论发送到 {v0} 个视频？ {v1} 目标： {v2} 任务会按顺序进入执行队列。", { v0: selectedTargets.length, v1: text, v2: targetList }))
      if (!confirmed) return

      const result = await acquisitionEnqueueCommentBatch({
        targets: selectedTargets.map((target) => ({
          platform: target.platform,
          video_id: String(target.video_id || ''),
          video_title: target.title,
          video_url: target.url || '',
        })),
        text,
        strategy,
        deai: false,
        confirmed: true,
      })
      setComments((current) => current.map((comment, index) => index === selectedCommentIndex
        ? { ...comment, queueStatus: 'queued', queueItemId: result.batch_id, preflight: latestCheck }
        : comment))
      setQueueView('active')
      await loadQueue('active')
      window.setTimeout(() => void loadQueue('active'), 1800)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("评论入队失败"))
    } finally {
      setSubmittingBatch(false)
    }
  }

  return (
    <PageShell
      title={t("智能截流作战台")}
      subtitle={t("发现高质量目标内容，生成安全评论，并把发送动作放进可审核、可观测的执行链路。")}
      icon={Fish}
    >
      {error && (
        <div className="flex items-center justify-between rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-[#FCA5A5] hover:text-white">{t("关闭")}</button>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label={t("发现目标")} value={formatNumber(targets.length)} icon={Target} hint={t("来自当前关键词搜索")} />
        <MetricCard label={t("高分机会")} value={highScoreCount} icon={ShieldCheck} tone="green" hint={t("质量分 80 以上")} />
        <MetricCard label={t("待发送队列")} value={formatNumber(queueMetrics.pending)} icon={MessageSquareText} tone="blue" hint={t("低风险任务自动排队")} />
        <MetricCard label={t("自动修复")} value={formatNumber(queueMetrics.autoRepaired)} icon={ShieldCheck} tone="green" hint={t("文案问题由系统处理")} />
        <MetricCard label={t("延后/重试")} value={formatNumber(queueMetrics.delayed + queueMetrics.retrying)} icon={BarChart3} tone="indigo" hint={t("限流和短暂失败不打扰用户")} />
        <MetricCard label={t("需人工处理")} value={formatNumber(queueMetrics.needsHuman)} icon={AlertTriangle} tone="amber" hint={t("只统计登录、验证码、敏感动作")} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
        <Panel title={t("输入目标")} description={t("先找目标，不直接发送。")}>
          <div className="space-y-4">
            <div>
              <FieldLabel>{t("关键词")}</FieldLabel>
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} className={inputClass} placeholder={t("例如：装修 获客")} />
            </div>
            <div>
              <FieldLabel>{t("平台")}</FieldLabel>
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
                <FieldLabel>{t("最低质量分")}</FieldLabel>
                <input type="number" min={0} max={100} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} className={inputClass} />
              </div>
              <div>
                <FieldLabel>{t("目标数量")}</FieldLabel>
                <input type="number" min={1} max={100} value={limit} onChange={(e) => setLimit(Number(e.target.value))} className={inputClass} />
              </div>
            </div>
            <div>
              <FieldLabel>{t("评论策略")}</FieldLabel>
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className={inputClass}>
                {STRATEGY_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>
            <button onClick={findTargets} disabled={loadingTargets} className={`${buttonPrimary} w-full`}>
              {loadingTargets ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}

              {t("搜索目标")}
            </button>
          </div>

          {platformStatuses.some((item) => !['success', 'unknown'].includes(item.status)) && (
            <div className="mt-4 flex flex-wrap gap-2 border-t border-white/8 pt-3">
              {platformStatuses
                .filter((item) => !['success', 'unknown'].includes(item.status))
                .map((item) => (
                  <div
                    key={item.platform}
                    className="flex min-h-8 items-center gap-2 rounded-md border border-amber-400/20 bg-amber-400/8 px-3 text-xs text-amber-100"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    <span>{platformLabel(item.platform)}</span>
                    <span className="text-amber-100/70">{item.message || t("本轮未发现可评论内容")}</span>
                  </div>
                ))}
            </div>
          )}
        </Panel>

        <Panel
          title={t("筛选目标")}
          description={t("勾选需要触达的视频，一次最多选择 {v0} 个。", { v0: MAX_SELECTED_TARGETS })}
          action={(
            <div className="flex flex-wrap items-center justify-end gap-2">
              {selectedTargets.length > 0 && <span className="text-xs text-[#A5B4FC]">{t("已选")} {selectedTargets.length}  {t("个")}</span>}
              <button onClick={generateForSelected} disabled={selectedTargets.length === 0 || loadingComments} className={buttonPrimary}>
                {loadingComments ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}

                {t("生成评论")}
              </button>
              <button onClick={() => void loadQueue(queueView)} className={buttonSecondary}>{loadingQueue ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}{t("刷新队列")}</button>
            </div>
          )}
        >
          {targets.length === 0 ? (
            <EmptyState title={t("还没有目标内容")} description={t("输入关键词后先搜索目标，系统会返回平台、作者、互动数据和质量评分。")} />
          ) : (
            <div className="overflow-hidden rounded-lg border border-[#1E293B]">
              <table className="w-full text-left text-sm">
                <thead className="bg-[#0B0F1A] text-xs text-[#64748B]">
                  <tr>
                    <th className="w-12 px-3 py-3 text-center">{t("选择")}</th>
                    <th className="px-3 py-3">{t("平台")}</th>
                    <th className="px-3 py-3">{t("标题")}</th>
                    <th className="px-3 py-3">{t("作者")}</th>
                    <th className="px-3 py-3">{t("互动")}</th>
                    <th className="px-3 py-3">{t("质量分")}</th>
                    <th className="px-3 py-3">{t("操作")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1E293B]">
                  {targets.map((item, index) => {
                    const sourceUrl = targetSourceUrl(item)
                    const itemKey = targetKey(item)
                    const isSelected = selectedTargetKeys.includes(itemKey)
                    return (
                    <tr key={`${item.platform}-${item.video_id || index}`} className={isSelected ? 'bg-[#6366F1]/10' : 'hover:bg-[#0B0F1A]/60'}>
                      <td className="px-3 py-3 text-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleTarget(item)}
                          aria-label={t("选择视频：{v0}", { v0: item.title })}
                          className="h-4 w-4 cursor-pointer rounded border-[#475569] bg-[#0B0F1A] accent-[#6366F1]"
                        />
                      </td>
                      <td className="px-3 py-3 text-[#CBD5E1]">{platformLabel(item.platform)}</td>
                      <td className="max-w-sm px-3 py-3">
                        <p className="truncate font-medium text-[#F1F5F9]">{item.title}</p>
                        <p className="mt-1 truncate text-xs text-[#64748B]">{scoreDetailText(item.score_detail)}</p>
                      </td>
                      <td className="px-3 py-3 text-[#94A3B8]">{item.author || '-'}</td>
                      <td className="px-3 py-3 text-xs text-[#94A3B8]">

                        {t("播放")} {formatNumber(item.plays)}  {t("· 评")} {formatNumber(item.comments_count)}
                      </td>
                      <td className="px-3 py-3">
                        <span className={`rounded-full border px-2 py-1 text-xs ${scoreTone(item.quality_score)}`}>
                          {item.quality_score ?? 0}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        {sourceUrl ? (
                          <a
                            href={sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={buttonSecondary}
                          >
                            <ExternalLink className="h-4 w-4" />

                            {t("查看")}
                          </a>
                        ) : (
                          <button disabled className={`${buttonSecondary} cursor-not-allowed opacity-45`} title={t("该内容暂无可用来源链接")}>
                            <ExternalLink className="h-4 w-4" />

                            {t("查看")}
                          </button>
                        )}
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <Panel
          title={t("评论生成与风险预检")}
          description={t("从 5 条候选中选择并编辑一条，再用于全部已选视频。")}
        >
          {comments.length === 0 ? (
            <EmptyState title={t("还没有评论草稿")} description={t("在上方列表勾选视频，然后点击生成评论。")} />
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border border-[#334155] bg-[#0B0F1A] px-4 py-3">
                <p className="text-sm text-[#CBD5E1]">{t("将发送到")} <span className="font-semibold text-[#A5B4FC]">{selectedTargets.length}</span>  {t("个已选视频")}</p>
                <span className="text-xs text-[#64748B]">{t("后台按顺序执行")}</span>
              </div>
              {comments.map((item, index) => {
                const passed = item.preflight?.pass ?? item.preflight?.passed ?? item.preflight?.ok
                const risk = String(item.preflight?.risk_level || item.preflight?.risk || (passed === false ? 'high' : 'low')).toLowerCase()
                const risks = item.preflight?.risks || item.preflight?.reasons || []
                const decision = String(item.preflight?.decision || '')
                const decisionLabel = !item.preflight
                  ? t("发送前重新检查")
                  : decision === 'auto_repair_then_send'
                    ? t("可自动修复")
                    : decision === 'needs_human'
                      ? t("需人工确认")
                      : decision === 'skip'
                        ? t("自动跳过")
                        : t("可自动发送")
                const blocked = decision === 'needs_human' || decision === 'skip' || risk === 'high'
                const isSelected = selectedCommentIndex === index
                return (
                  <div key={index} className={`rounded-lg border p-4 transition-colors ${isSelected ? 'border-[#6366F1] bg-[#6366F1]/10' : 'border-[#1E293B] bg-[#0B0F1A]'}`}>
                    <div className="flex items-start justify-between gap-3">
                      <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-sm font-medium text-[#E2E8F0]">
                        <input
                          type="radio"
                          name="comment-candidate"
                          checked={isSelected}
                          onChange={() => setSelectedCommentIndex(index)}
                          className="h-4 w-4 accent-[#6366F1]"
                        />

                        {t("候选评论")} {index + 1}
                      </label>
                      <span className={`shrink-0 rounded-full border px-2 py-1 text-xs ${blocked ? 'border-[#EF4444]/25 bg-[#EF4444]/10 text-[#FCA5A5]' : risk === 'medium' ? 'border-[#F59E0B]/25 bg-[#F59E0B]/10 text-[#FCD34D]' : 'border-[#10B981]/25 bg-[#10B981]/10 text-[#86EFAC]'}`}>
                        {decisionLabel}
                      </span>
                    </div>
                    <textarea
                      value={item.processed}
                      onFocus={() => setSelectedCommentIndex(index)}
                      onChange={(event) => updateCandidate(index, event.target.value)}
                      rows={3}
                      className="mt-3 w-full resize-y rounded-lg border border-[#334155] bg-[#111827] px-3 py-2 text-sm leading-6 text-[#F1F5F9] outline-none transition-colors focus:border-[#6366F1]"
                      aria-label={t("编辑候选评论 {v0}", { v0: index + 1 })}
                    />
                    <div className="mt-2 flex items-center justify-between text-xs text-[#64748B]">
                      <span>{item.processed.length}  {t("字")}</span>
                      {item.original !== item.processed && item.preflight && <span>{t("已优化表达")}</span>}
                    </div>
                    {item.preflight?.message && <p className="mt-3 text-xs text-[#94A3B8]">{item.preflight.message}</p>}
                    {risks.length > 0 && (
                      <div className="mt-3 rounded-lg border border-[#F59E0B]/20 bg-[#F59E0B]/10 p-3">
                        <p className="text-xs font-medium text-[#FCD34D]">{t("风险提示")}</p>
                        <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-[#FDE68A]">
                          {risks.map((reason, reasonIndex) => <li key={`${reason}-${reasonIndex}`}>{reason}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )
              })}
              <div className="flex justify-end pt-1">
                <button
                  onClick={() => void enqueueSelectedComment()}
                  disabled={selectedCommentIndex === null || submittingBatch || Boolean(selectedCommentIndex !== null && comments[selectedCommentIndex]?.queueStatus)}
                  className={buttonPrimary}
                >
                  {submittingBatch
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : selectedCommentIndex !== null && comments[selectedCommentIndex]?.queueStatus
                      ? <CheckCircle2 className="h-4 w-4" />
                      : <Send className="h-4 w-4" />}
                  {selectedCommentIndex !== null && comments[selectedCommentIndex]?.queueStatus
                    ? t("已进入执行队列")
                    : t("确认群发到 {v0} 个视频", { v0: selectedTargets.length })}
                </button>
              </div>
            </div>
          )}
        </Panel>

        <Panel
          title={t("队列观测")}
          description={queueView === 'active'
            ? t("同一条群发评论按批次合并，展开即可回溯每个原视频。")
            : t("已结束的较早批次保留 180 天，最多保存 3,000 个批次。")}
        >
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="inline-flex rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-1">
              <button
                type="button"
                onClick={() => setQueueView('active')}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${queueView === 'active' ? 'bg-[#6366F1] text-white' : 'text-[#94A3B8] hover:text-[#E2E8F0]'}`}
              >

                {t("当前队列")}
              </button>
              <button
                type="button"
                onClick={() => setQueueView('archived')}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${queueView === 'archived' ? 'bg-[#6366F1] text-white' : 'text-[#94A3B8] hover:text-[#E2E8F0]'}`}
              >
                <Archive className="h-3.5 w-3.5" />

                {t("历史归档")}
              </button>
            </div>
            {queueView === 'archived' && <span className="text-xs text-[#64748B]">{t("自动清理 180 天前记录")}</span>}
          </div>
          {queueGroups.length === 0 ? (
            <EmptyState
              title={queueView === 'active' ? t("暂无队列任务") : t("暂无归档记录")}
              description={queueView === 'active'
                ? t("生成评论并确认后，后续任务会在这里展示状态、失败原因和人工处理提示。")
                : t("较早的已结束批次会在当前队列超过保留上限后自动移入这里。")}
            />
          ) : (
            <div className="space-y-3">
              {queueGroups.map((group) => {
                const expanded = expandedQueueGroups.has(group.id)
                const sentCount = group.items.filter(isQueueSent).length
                const total = group.items.length
                const progress = total > 0 ? Math.round((sentCount / total) * 100) : 0
                const platformsInGroup = Array.from(new Set(group.items.map((item) => platformLabel(item.platform))))
                const singleItem = total === 1 ? group.items[0] : null
                const singleUrl = singleItem ? queueSourceUrl(singleItem) : ''
                return (
                  <div key={group.id} className="overflow-hidden rounded-lg border border-[#1E293B] bg-[#0B0F1A] transition-colors hover:border-[#334155]">
                    <div className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2 text-xs text-[#94A3B8]">
                            <span>{platformsInGroup.join('、')}</span>
                            <span className="h-1 w-1 rounded-full bg-[#475569]" />
                            <span>{total > 1 ? t("{v0} 个视频", { v0: total }) : t("单条评论")}</span>
                            {queueView === 'archived' && <span className="text-[#A5B4FC]">{t("已归档")}</span>}
                            {group.createdAt && <span>{group.createdAt.slice(5, 16).replace('T', ' ')}</span>}
                          </div>
                          <p className="mt-2 line-clamp-2 text-sm leading-6 text-[#F1F5F9]">{group.commentText}</p>
                        </div>
                        <StatusPill status={queueGroupStatus(group.items)} />
                      </div>

                      {total > 1 ? (
                        <div className="mt-4">
                          <div className="mb-2 flex items-center justify-between text-xs">
                            <span className="text-[#94A3B8]">{t("发送进度")}</span>
                            <span className="font-medium text-[#CBD5E1]">{sentCount}/{total}</span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-[#1E293B]">
                            <div className="h-full rounded-full bg-[#10B981] transition-[width] duration-300" style={{ width: `${progress}%` }} />
                          </div>
                          <button
                            type="button"
                            onClick={() => toggleQueueGroup(group.id)}
                            className="mt-3 flex items-center gap-1.5 text-xs font-medium text-[#A5B4FC] transition-colors hover:text-[#C4B5FD]"
                          >
                            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            {expanded ? t("收起发送明细") : t("展开 {v0} 条发送明细", { v0: total })}
                          </button>
                        </div>
                      ) : (
                        <div className="mt-3 flex items-center justify-between gap-3 border-t border-[#1E293B] pt-3">
                          <span className="min-w-0 truncate text-xs text-[#94A3B8]">{String(singleItem?.video_title || t("原视频"))}</span>
                          {singleUrl && (
                            <a href={singleUrl} target="_blank" rel="noreferrer" className="flex shrink-0 items-center gap-1 text-xs font-medium text-[#A5B4FC] hover:text-[#C4B5FD]">

                              {t("查看原视频")} <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          )}
                        </div>
                      )}
                    </div>

                    {total > 1 && expanded && (
                      <div className="border-t border-[#1E293B] bg-[#0F1420] px-4">
                        {group.items.map((item, index) => {
                          const sourceUrl = queueSourceUrl(item)
                          return (
                            <div key={item.id || item.item_id || index} className="flex items-start gap-3 border-b border-[#1E293B] py-3 last:border-b-0">
                              <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${isQueueSent(item) ? 'bg-[#10B981]' : 'bg-[#64748B]'}`} />
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span title={String(item.video_title || '')} className="truncate text-sm text-[#E2E8F0]">{String(item.video_title || t("目标视频 {v0}", { v0: index + 1 }))}</span>
                                  <StatusPill status={item.status} />
                                </div>
                                {(item.error || item.error_msg) && <p className="mt-1 line-clamp-2 text-xs text-[#FCA5A5]">{String(item.error || item.error_msg)}</p>}
                                {item.next_run_at && <p className="mt-1 text-xs text-[#A5B4FC]">{t("预计执行：")}{String(item.next_run_at).slice(5, 16).replace('T', ' ')}</p>}
                              </div>
                              {sourceUrl && (
                                <a href={sourceUrl} target="_blank" rel="noreferrer" className="mt-0.5 flex shrink-0 items-center gap-1 text-xs font-medium text-[#A5B4FC] hover:text-[#C4B5FD]">

                                  {t("查看原视频")} <ExternalLink className="h-3.5 w-3.5" />
                                </a>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
          <div className="mt-4 rounded-lg border border-[#334155] bg-[#0B0F1A] p-3 text-xs leading-5 text-[#64748B]">
            <div className="mb-2 flex items-center gap-2 text-[#CBD5E1]">
              <CheckCircle2 className="h-4 w-4 text-[#10B981]" />

              {t("安全执行规则")}
            </div>

            {t("普通评论会自动预检、修复、排队和重试；只有登录、验证码、账号异常、联系方式、加好友等敏感动作会进入需人工处理。")}
          </div>
        </Panel>
      </div>
    </PageShell>
  )
}
