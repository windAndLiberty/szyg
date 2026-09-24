import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  Archive,
  BookOpen,
  ExternalLink,
  FileText,
  MonitorCog,
  Music2,
  Play,
  Search,
  Tv,
  Youtube,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  fetchExecutions,
  fetchPlatforms,
  getErrorMessage,
  type ExecutionArchiveInfo,
  type ExecutionRun,
  type PlatformInfo,
} from '@/lib/api'
import { getPublishedPostInfo } from '@/components/publish/PublishedPostLink'
import { translateCurrent, useI18n } from '@/lib/i18n'

type PublishMode = 'video' | 'note'
type CapabilityStatus = 'available' | 'login_required' | 'desktop' | 'planned'
const PAGE_SIZE = 10

const PLATFORM_CAPABILITIES: Array<{
  id: string
  label: string
  icon: typeof Music2
  contentTypes: PublishMode[]
  status: CapabilityStatus
  risk: string
  description: string
  supportsLinkBack: boolean
}> = [
  { id: 'douyin', get label() { return translateCurrent("抖音") }, icon: Music2, contentTypes: ['video', 'note'], status: 'available', get risk() { return translateCurrent("严格") }, get description() { return translateCurrent("短视频和图文发布已接入，支持作品链接回写。") }, supportsLinkBack: true },
  { id: 'xhs', get label() { return translateCurrent("小红书") }, icon: BookOpen, contentTypes: ['video', 'note'], status: 'available', get risk() { return translateCurrent("严格") }, get description() { return translateCurrent("适合种草图文和短视频，支持作品链接回写。") }, supportsLinkBack: true },
  { id: 'kuaishou', get label() { return translateCurrent("快手") }, icon: Play, contentTypes: ['video', 'note'], status: 'login_required', get risk() { return translateCurrent("中等") }, get description() { return translateCurrent("发布能力已预留，登录后进入稳定性验证。") }, supportsLinkBack: false },
  { id: 'tencent', get label() { return translateCurrent("视频号") }, icon: MonitorCog, contentTypes: ['video', 'note'], status: 'desktop', get risk() { return translateCurrent("中等") }, get description() { return translateCurrent("图文和视频走真实桌面浏览器辅助发布。") }, supportsLinkBack: false },
  { id: 'bilibili', get label() { return translateCurrent("B站") }, icon: Tv, contentTypes: ['video'], status: 'planned', get risk() { return translateCurrent("中等") }, get description() { return translateCurrent("适合长视频和知识内容，待接入发布验收。") }, supportsLinkBack: false },
  { id: 'youtube', label: 'YouTube', icon: Youtube, contentTypes: ['video'], status: 'login_required', get risk() { return translateCurrent("宽松") }, get description() { return translateCurrent("适合海外渠道，需要先完成账号配置。") }, supportsLinkBack: false },
  { id: 'weibo', get label() { return translateCurrent("微博") }, icon: FileText, contentTypes: ['video', 'note'], status: 'desktop', get risk() { return translateCurrent("中等") }, get description() { return translateCurrent("图文和视频走真实桌面浏览器辅助发布。") }, supportsLinkBack: false },
]

function statusText(status: string) {
  if (status === 'success') return translateCurrent("已发布")
  if (status === 'failed') return translateCurrent("失败")
  if (status === 'running') return translateCurrent("发布中")
  if (status === 'queued') return translateCurrent("排队中")
  if (status === 'needs_human') return translateCurrent("需处理")
  if (status === 'paused') return translateCurrent("已暂停")
  if (status === 'cancelled') return translateCurrent("已取消")
  return status || translateCurrent("未知")
}
function statusVariant(status: string): 'success' | 'warning' | 'error' | 'muted' | 'info' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running' || status === 'queued') return 'info'
  if (status === 'needs_human' || status === 'paused') return 'warning'
  return 'muted'
}

function formatTime(value: string) {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return '-'
  }
}

function formatDuration(ms: number) {
  if (!ms) return '-'
  const seconds = Math.round(ms / 1000)
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

function platformLabel(id: string) {
  return PLATFORM_CAPABILITIES.find((item) => item.id === id)?.label || id || '-'
}

function runFailureMessage(run: ExecutionRun) {
  const resultMessage = typeof run.result?.message === 'string' ? run.result.message : ''
  return run.error_message || resultMessage || ''
}

function publishProgress(run: ExecutionRun) {
  if (run.status === 'success') return { percent: 100, get label() { return translateCurrent("发布完成") } }
  if (run.status === 'failed' || run.status === 'needs_human' || run.status === 'cancelled') return { percent: 100, label: statusText(run.status) }
  if (run.status === 'queued') return { percent: 10, get label() { return translateCurrent("等待执行") } }
  const step = run.current_step_id || ''
  if (step === 'validate_material') return { percent: 25, get label() { return translateCurrent("检查素材") } }
  if (step === 'platform_preflight') return { percent: 40, get label() { return translateCurrent("检查账号") } }
  if (step === 'execute_upload') return { percent: 72, get label() { return translateCurrent("正在发布") } }
  if (step === 'detect_result') return { percent: 90, get label() { return translateCurrent("确认结果") } }
  return { percent: run.status === 'running' ? 32 : 0, label: run.status === 'running' ? translateCurrent("执行中") : statusText(run.status) }
}

function progressTone(status: string) {
  if (status === 'success') return 'bg-[#22C55E]'
  if (status === 'failed' || status === 'needs_human') return 'bg-[#F59E0B]'
  if (status === 'cancelled') return 'bg-[#64748B]'
  return 'bg-[#38BDF8]'
}

function capabilityState(capability: (typeof PLATFORM_CAPABILITIES)[number], platform?: PlatformInfo) {
  if (platform?.session?.valid) return { get label() { return translateCurrent("可发布") }, variant: 'success' as const }
  if (capability.status === 'available') return { get label() { return translateCurrent("需登录") }, variant: 'warning' as const }
  if (capability.status === 'login_required') return { get label() { return translateCurrent("需配置") }, variant: 'warning' as const }
  if (capability.status === 'desktop') return { get label() { return translateCurrent("需接管") }, variant: 'info' as const }
  return { get label() { return translateCurrent("待接入") }, variant: 'muted' as const }
}

export default function PublishCenter() {
  const { t } = useI18n()
  const [runs, setRuns] = useState<ExecutionRun[]>([])
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([])
  const [archiveInfo, setArchiveInfo] = useState<ExecutionArchiveInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [keyword, setKeyword] = useState('')
  const [platformFilter, setPlatformFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sortBy, setSortBy] = useState('created_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [includeArchived, setIncludeArchived] = useState(false)
  const [page, setPage] = useState(1)

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    if (!silent) setLoadError('')
    try {
      const [executionResult, platformResult] = await Promise.all([
        fetchExecutions({
          limit: 300,
          task_type: 'publish_video,publish_note',
          keyword: keyword.trim(),
          platform: platformFilter === 'all' ? '' : platformFilter,
          status: statusFilter === 'all' ? '' : statusFilter,
          sort_by: sortBy,
          sort_dir: sortDir,
          include_archived: includeArchived,
        }),
        fetchPlatforms(),
      ])
      setRuns(executionResult.runs || [])
      setArchiveInfo(executionResult.archive || null)
      setPlatforms(platformResult.platforms || [])
      setLoadError('')
    } catch (err) {
      setLoadError(getErrorMessage(err, t("发布数据暂不可用")))
    } finally {
      setLoading(false)
    }
  }, [includeArchived, keyword, platformFilter, sortBy, sortDir, statusFilter])

  useEffect(() => {
    load()
    const timer = window.setInterval(() => load(true), 8000)
    return () => window.clearInterval(timer)
  }, [load])

  useEffect(() => {
    setPage(1)
  }, [includeArchived, keyword, platformFilter, sortBy, sortDir, statusFilter])

  const platformMap = useMemo(() => new Map(platforms.map((item) => [item.id, item])), [platforms])
  const today = new Date().toDateString()
  const activeRuns = runs.filter((run) => !run.archived)
  const todaysRuns = activeRuns.filter((run) => new Date(run.created_at).toDateString() === today)
  const summary = {
    published: todaysRuns.filter((run) => run.status === 'success').length,
    running: activeRuns.filter((run) => run.status === 'running' || run.status === 'queued').length,
    needsHuman: activeRuns.filter((run) => run.status === 'needs_human' || run.status === 'failed').length,
    available: PLATFORM_CAPABILITIES.filter((item) => platformMap.get(item.id)?.session?.valid).length,
  }
  const totalPages = Math.max(1, Math.ceil(runs.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const pageStart = (currentPage - 1) * PAGE_SIZE
  const pageRuns = runs.slice(pageStart, pageStart + PAGE_SIZE)

  useEffect(() => {
    setPage((value) => Math.min(value, totalPages))
  }, [totalPages])

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#080D16] px-4 py-5 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1480px] flex-col gap-5">
        <p className="px-1 text-sm text-[#94A3B8]">

          {t("查看多平台发布结果、队列进度、作品入口和需要处理的问题。")}
        </p>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {[
            { label: t("今日已发布"), value: summary.published, hint: t("已拿到平台结果"), color: 'text-[#22C55E]' },
            { label: t("发布中"), value: summary.running, hint: t("正在自动执行"), color: 'text-[#38BDF8]' },
            { label: t("待处理"), value: summary.needsHuman, hint: t("失败或需人工"), color: 'text-[#F59E0B]' },
            { label: t("可用渠道"), value: summary.available, hint: t("共 {v0} 个渠道", { v0: PLATFORM_CAPABILITIES.length }), color: 'text-[#A78BFA]' },
          ].map((metric) => (
            <div key={metric.label} className="rounded-md border border-[#1C2940] bg-[#0D1422] px-4 py-3">
              <div className="text-xs text-[#64748B]">{metric.label}</div>
              <div className="mt-1 flex items-end gap-3">
                <span className={`text-2xl font-semibold ${metric.color}`}>{metric.value}</span>
                <span className="pb-1 text-xs text-[#94A3B8]">{metric.hint}</span>
              </div>
            </div>
          ))}
        </section>

        {loadError && (
          <section className="flex items-start gap-3 rounded-md border border-[#7F1D1D] bg-[#450A0A]/35 px-4 py-3 text-sm text-[#FCA5A5]">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <div className="font-medium text-[#FEE2E2]">{t("发布数据暂不可用")}</div>
              <div className="mt-1 text-xs leading-5 text-[#FCA5A5]">{loadError}</div>
            </div>
          </section>
        )}

        <section>
          <main className="rounded-md border border-[#1C2940] bg-[#0D1422]">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1C2940] px-5 py-4">
              <div>
                <h2 className="text-base font-semibold text-[#F8FAFC]">{t("发布记录")}</h2>
                <p className="mt-1 text-sm text-[#64748B]">{t("最近发布任务、执行状态和作品链接集中在这里。")}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {archiveInfo && (
                  <Badge variant="muted">
                    <Archive className="h-3.5 w-3.5" />

                    {t("活跃")} {archiveInfo.active_publish_records}/{archiveInfo.active_limit}  {t("· 归档")} {archiveInfo.archived_publish_records}
                  </Badge>
                )}
                <Badge variant="muted">{runs.length}  {t("条记录")}</Badge>
              </div>
            </div>

            <div className="grid gap-3 border-b border-[#1C2940] px-5 py-4 lg:grid-cols-[minmax(220px,1fr)_160px_160px_160px_120px]">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#64748B]" />
                <input
                  value={keyword}
                  onChange={(event) => setKeyword(event.target.value)}
                  placeholder={t("搜索标题、账号、平台、错误原因或任务ID")}
                  className="h-10 w-full rounded-md border border-[#1C2940] bg-[#080D16] pl-9 pr-3 text-sm text-[#F8FAFC] outline-none transition-colors placeholder:text-[#475569] focus:border-[#6366F1]"
                />
              </label>
              <select
                value={platformFilter}
                onChange={(event) => setPlatformFilter(event.target.value)}
                className="h-10 rounded-md border border-[#1C2940] bg-[#080D16] px-3 text-sm text-[#CBD5E1] outline-none focus:border-[#6366F1]"
              >
                <option value="all">{t("全部平台")}</option>
                {PLATFORM_CAPABILITIES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="h-10 rounded-md border border-[#1C2940] bg-[#080D16] px-3 text-sm text-[#CBD5E1] outline-none focus:border-[#6366F1]"
              >
                <option value="all">{t("全部状态")}</option>
                <option value="success">{t("已发布")}</option>
                <option value="running">{t("发布中")}</option>
                <option value="queued">{t("排队中")}</option>
                <option value="needs_human">{t("需处理")}</option>
                <option value="failed">{t("失败")}</option>
                <option value="cancelled">{t("已取消")}</option>
              </select>
              <select
                value={sortBy}
                onChange={(event) => setSortBy(event.target.value)}
                className="h-10 rounded-md border border-[#1C2940] bg-[#080D16] px-3 text-sm text-[#CBD5E1] outline-none focus:border-[#6366F1]"
              >
                <option value="created_at">{t("创建时间")}</option>
                <option value="finished_at">{t("完成时间")}</option>
                <option value="duration_ms">{t("耗时")}</option>
                <option value="platform">{t("平台")}</option>
                <option value="status">{t("状态")}</option>
                <option value="title">{t("标题")}</option>
              </select>
              <button
                type="button"
                onClick={() => setSortDir((value) => value === 'desc' ? 'asc' : 'desc')}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-[#1C2940] bg-[#080D16] px-3 text-sm text-[#CBD5E1] transition-colors hover:border-[#6366F1] hover:text-[#F8FAFC]"
              >
                {sortDir === 'desc' ? t("降序") : t("升序")}
              </button>
              <label className="flex items-center gap-2 text-xs text-[#94A3B8] lg:col-span-5">
                <input
                  type="checkbox"
                  checked={includeArchived}
                  onChange={(event) => setIncludeArchived(event.target.checked)}
                  className="h-4 w-4 accent-[#6366F1]"
                />

                {t("显示归档记录")}
              </label>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead className="border-b border-[#1C2940] text-xs uppercase tracking-[0.08em] text-[#64748B]">
                  <tr>
                    <th className="px-5 py-3 font-medium">{t("内容")}</th>
                    <th className="px-4 py-3 font-medium">{t("平台")}</th>
                    <th className="px-4 py-3 font-medium">{t("账号")}</th>
                    <th className="px-4 py-3 font-medium">{t("类型")}</th>
                    <th className="px-4 py-3 font-medium">{t("状态")}</th>
                    <th className="px-4 py-3 font-medium">{t("时间")}</th>
                    <th className="px-4 py-3 font-medium">{t("耗时")}</th>
                    <th className="px-4 py-3 font-medium">{t("作品")}</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-5 py-16 text-center text-[#64748B]">

                        {t("暂无发布记录。请在“素材管理与发布”中选择素材并确认发布。")}
                      </td>
                    </tr>
                  ) : pageRuns.map((run) => {
                    const post = getPublishedPostInfo(run.result, run.platform)
                    const showPostLink = run.status === 'success' && post?.url
                    const progress = publishProgress(run)
                    return (
                      <tr key={run.id} className="border-b border-[#111827] hover:bg-[#111827]/60">
                        <td className="max-w-[340px] px-5 py-4">
                          <div className="truncate font-medium text-[#F8FAFC]">{run.title || run.input?.title as string || run.task_type}</div>
                          {run.archived && (
                            <div className="mt-1 flex min-w-0 items-center gap-2 text-xs text-[#64748B]">
                              <span className="shrink-0 rounded bg-[#1E293B] px-1.5 py-0.5 text-[10px] text-[#94A3B8]">{t("已归档")}</span>
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-4 text-[#CBD5E1]">{platformLabel(run.platform)}</td>
                        <td className="px-4 py-4 text-[#CBD5E1]">{run.account_label || (run.input?.account_label as string) || '-'}</td>
                        <td className="px-4 py-4 text-[#CBD5E1]">{run.task_type === 'publish_note' ? t("图文") : t("视频")}</td>
                        <td className="px-4 py-4">
                          <div className="flex flex-col items-start gap-1">
                            <Badge variant={statusVariant(run.status)}>{statusText(run.status)}</Badge>
                            {(run.status === 'queued' || run.status === 'running') && (
                              <div className="mt-1 w-36">
                                <div className="mb-1 flex items-center justify-between text-[11px] text-[#64748B]">
                                  <span>{progress.label}</span>
                                  <span>{progress.percent}%</span>
                                </div>
                                <div className="h-1.5 overflow-hidden rounded-full bg-[#1E293B]">
                                  <div
                                    className={`h-full rounded-full transition-all duration-500 ${progressTone(run.status)}`}
                                    style={{ width: `${progress.percent}%` }}
                                  />
                                </div>
                              </div>
                            )}
                            {run.status !== 'success' && runFailureMessage(run) && (
                              <span className="max-w-[180px] text-xs leading-5 text-[#FCA5A5]" title={runFailureMessage(run)}>
                                {runFailureMessage(run)}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-4 text-xs text-[#94A3B8]">{formatTime(run.finished_at || run.started_at || run.created_at)}</td>
                        <td className="px-4 py-4 text-xs text-[#94A3B8]">{formatDuration(run.duration_ms)}</td>
                        <td className="px-4 py-4">
                          {showPostLink ? (
                            <Button type="button" size="sm" variant="outline" onClick={() => window.open(post.url, '_blank', 'noopener,noreferrer')}>
                              <ExternalLink className="h-4 w-4" />
                              {post.label}
                            </Button>
                          ) : (
                            <span className="text-xs text-[#64748B]">-</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {runs.length > 0 && (
              <div className="flex flex-col gap-3 border-t border-[#1C2940] px-5 py-4 text-sm text-[#94A3B8] sm:flex-row sm:items-center sm:justify-between">
                <div>

                  {t("第")} {pageStart + 1}-{Math.min(pageStart + PAGE_SIZE, runs.length)}  {t("条，共")} {runs.length}  {t("条")}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={currentPage <= 1}
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                  >

                    {t("上一页")}
                  </Button>
                  <span className="min-w-16 text-center text-xs text-[#64748B]">
                    {currentPage} / {totalPages}
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={currentPage >= totalPages}
                    onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                  >

                    {t("下一页")}
                  </Button>
                </div>
              </div>
            )}
          </main>

        </section>
      </div>

    </div>
  )
}
