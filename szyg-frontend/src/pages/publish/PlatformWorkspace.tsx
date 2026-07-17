import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Globe2,
  Loader2,
  MonitorCog,
  Music2,
  RefreshCw,
  ShieldCheck,
  TerminalSquare,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { fetchExecutions, fetchPlatforms, type ExecutionRun, type PlatformInfo } from '@/lib/api'
import { PublishedPostLink } from '@/components/publish/PublishedPostLink'

const PLATFORM_NAMES: Record<string, string> = {
  douyin: '抖音',
  xhs: '小红书',
  kuaishou: '快手',
  bilibili: 'B站',
  wechat_mp: '公众号',
}

function statusText(status: string) {
  if (status === 'success') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '运行中'
  if (status === 'queued') return '排队中'
  if (status === 'needs_human') return '需人工处理'
  if (status === 'paused') return '已暂停'
  if (status === 'cancelled') return '已取消'
  return status || '未知'
}

function statusVariant(status: string): 'success' | 'warning' | 'error' | 'muted' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running' || status === 'queued' || status === 'needs_human' || status === 'paused') return 'warning'
  return 'muted'
}

function formatTime(value: string) {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '-'
  }
}

function summarizeExecutionError(run?: ExecutionRun) {
  if (!run?.error_message) return run?.status === 'needs_human' ? '等待人工接管' : '任务失败'
  const fileMissingMatch = run.error_message.match(/File not found:\s*([^\r\n]+)/i)
  if (fileMissingMatch?.[1]) return `素材文件不存在：${fileMissingMatch[1]}`
  const firstLine = run.error_message.split(/\r?\n/).find((line) => line.trim())
  return firstLine?.trim() || '任务失败'
}

function platformOnline(platform: PlatformInfo) {
  return Boolean(platform.session?.valid)
}

export default function PlatformWorkspace() {
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([])
  const [runs, setRuns] = useState<ExecutionRun[]>([])
  const [selectedPlatform, setSelectedPlatform] = useState('douyin')
  const [selectedRunId, setSelectedRunId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [platformResult, taskResult] = await Promise.all([
        fetchPlatforms(),
        fetchExecutions(40),
      ])
      setPlatforms(platformResult.platforms || [])
      setRuns(taskResult.runs || [])
      if (!selectedRunId && taskResult.runs?.[0]) setSelectedRunId(taskResult.runs[0].id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const timer = window.setInterval(load, 8000)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selectedPlatformInfo = useMemo(
    () => platforms.find((item) => item.id === selectedPlatform),
    [platforms, selectedPlatform],
  )

  const selectedRun = useMemo(
    () => runs.find((item) => item.id === selectedRunId),
    [runs, selectedRunId],
  )

  const activeTasks = runs.filter((task) => task.status === 'running' || task.status === 'queued')
  const failedTasks = runs.filter((task) => task.status === 'failed' || task.status === 'needs_human')

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-[#94A3B8]">
            <span>{activeTasks.length} 个进行中</span>
            <span className="text-[#334155]">/</span>
            <span>{failedTasks.length} 个待处理</span>
          </div>
        </div>
        <Button variant="outline" onClick={load} disabled={loading}>
          {loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
          刷新
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-[#7F1D1D] bg-[#450A0A]/40 px-4 py-3 text-sm text-[#FCA5A5]">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="grid min-h-[680px] grid-cols-[280px_minmax(0,1fr)_320px] gap-4 max-2xl:grid-cols-[260px_minmax(0,1fr)] max-xl:grid-cols-1">
        <aside className="flex min-h-0 flex-col gap-4">
          <section className="rounded-md border border-[#1E293B] bg-[#111827]">
            <div className="border-b border-[#1E293B] px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-[#E2E8F0]">
                <Globe2 className="h-4 w-4 text-[#38BDF8]" />
                平台
              </div>
            </div>
            <div className="space-y-2 p-3">
              {platforms.map((platform) => {
                const isSelected = platform.id === selectedPlatform
                const online = platformOnline(platform)
                return (
                  <button
                    key={platform.id}
                    onClick={() => setSelectedPlatform(platform.id)}
                    className={`flex w-full items-center gap-3 rounded-md border px-3 py-3 text-left transition-colors ${
                      isSelected
                        ? 'border-[#2563EB] bg-[#172554]/60'
                        : 'border-transparent bg-transparent hover:bg-[#1A2235]'
                    }`}
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-md bg-[#0F172A]">
                      <Music2 className="h-4 w-4 text-[#67E8F9]" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-[#F1F5F9]">
                        {PLATFORM_NAMES[platform.id] || platform.name || platform.id}
                      </div>
                      <div className="mt-1 text-xs text-[#64748B]">
                        {platform.nickname || platform.meta?.publish_mode || '未绑定昵称'}
                      </div>
                    </div>
                    <span className={`h-2.5 w-2.5 rounded-full ${online ? 'bg-[#22C55E]' : 'bg-[#475569]'}`} />
                  </button>
                )
              })}
            </div>
          </section>

          <section className="rounded-md border border-[#1E293B] bg-[#111827]">
            <div className="border-b border-[#1E293B] px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-[#E2E8F0]">
                <Clock3 className="h-4 w-4 text-[#A78BFA]" />
                执行任务
              </div>
            </div>
            <div className="max-h-[360px] space-y-2 overflow-auto p-3">
              {runs.length === 0 ? (
                <div className="rounded-md border border-dashed border-[#334155] px-3 py-6 text-center text-sm text-[#64748B]">
                  暂无任务
                </div>
              ) : runs.map((task) => (
                <button
                  key={task.id}
                  onClick={() => setSelectedRunId(task.id)}
                  className={`w-full rounded-md border px-3 py-3 text-left transition-colors ${
                    selectedRunId === task.id
                      ? 'border-[#2563EB] bg-[#172554]/60'
                      : 'border-[#1E293B] bg-[#0F172A] hover:border-[#334155]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 text-sm font-medium text-[#E2E8F0]">
                      <span className="line-clamp-1">{task.title || task.task_type}</span>
                    </div>
                    <Badge variant={statusVariant(task.status)}>{statusText(task.status)}</Badge>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-[#64748B]">
                    <span>{PLATFORM_NAMES[task.platform] || task.platform}</span>
                    <span>{formatTime(task.updated_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <main className="flex min-h-0 flex-col rounded-md border border-[#1E293B] bg-[#0F172A]">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1E293B] px-5 py-4">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[#172554]">
                <MonitorCog className="h-5 w-5 text-[#60A5FA]" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="truncate text-base font-semibold text-[#F8FAFC]">
                    {PLATFORM_NAMES[selectedPlatform] || selectedPlatform} 执行观测
                  </h2>
                  {selectedPlatformInfo?.session?.valid ? (
                    <Badge variant="success"><CheckCircle2 className="mr-1 h-3 w-3" />在线</Badge>
                  ) : (
                    <Badge variant="muted">未连接</Badge>
                  )}
                </div>
                <div className="mt-1 text-sm text-[#64748B]">
                  {selectedRun ? `${statusText(selectedRun.status)} · ${selectedRun.current_step_id || selectedRun.executor_type}` : '待命'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" disabled>
                <TerminalSquare />
                人工接管
              </Button>
            </div>
          </div>

          <div className="relative flex min-h-[540px] flex-1 items-center justify-center overflow-hidden bg-[#020617]">
            <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(30,41,59,0.18)_1px,transparent_1px),linear-gradient(rgba(30,41,59,0.18)_1px,transparent_1px)] bg-[size:32px_32px]" />
            <div className="relative mx-6 flex max-w-[520px] flex-col items-center text-center">
              <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-md border border-[#334155] bg-[#0F172A]">
                <MonitorCog className="h-8 w-8 text-[#38BDF8]" />
              </div>
              <div className="text-lg font-semibold text-[#E2E8F0]">执行观测中心</div>
              <div className="mt-3 max-w-[520px] text-sm leading-6 text-[#94A3B8]">
                {selectedRun?.status === 'failed' || selectedRun?.status === 'needs_human'
                  ? summarizeExecutionError(selectedRun)
                  : selectedRun?.status === 'running'
                    ? '自动化执行中，关键步骤将记录日志和证据'
                    : '等待执行任务'}
              </div>
            </div>
          </div>
        </main>

        <aside className="flex min-h-0 flex-col gap-4 max-2xl:col-span-2 max-xl:col-span-1">
          <section className="rounded-md border border-[#1E293B] bg-[#111827]">
            <div className="border-b border-[#1E293B] px-4 py-3 text-sm font-medium text-[#E2E8F0]">
              当前平台
            </div>
            <div className="space-y-4 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-[#94A3B8]">账号</span>
                <span className="truncate text-sm font-medium text-[#F1F5F9]">
                  {selectedPlatformInfo?.nickname || '-'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-[#94A3B8]">会话</span>
                {selectedPlatformInfo?.session?.valid ? (
                  <Badge variant="success">有效</Badge>
                ) : (
                  <Badge variant="muted">无效</Badge>
                )}
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-[#94A3B8]">Cookie</span>
                <span className="text-sm text-[#CBD5E1]">{selectedPlatformInfo?.session?.cookie_count ?? 0}</span>
              </div>
            </div>
          </section>

          <section className="rounded-md border border-[#1E293B] bg-[#111827]">
            <div className="border-b border-[#1E293B] px-4 py-3 text-sm font-medium text-[#E2E8F0]">
              当前执行
            </div>
            <div className="space-y-4 p-4">
              {selectedRun ? (
                <>
                  <div>
                    <div className="text-sm font-medium text-[#F8FAFC]">{selectedRun.title || selectedRun.task_type}</div>
                    <div className="mt-2 text-xs text-[#64748B]">{selectedRun.id}</div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[#94A3B8]">状态</span>
                    <Badge variant={statusVariant(selectedRun.status)}>{statusText(selectedRun.status)}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[#94A3B8]">执行器</span>
                    <span className="text-sm text-[#CBD5E1]">{selectedRun.executor_type}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[#94A3B8]">耗时</span>
                    <span className="text-sm text-[#CBD5E1]">
                      {selectedRun.duration_ms ? `${Math.round(selectedRun.duration_ms / 1000)}s` : '-'}
                    </span>
                  </div>
                  {selectedRun.error_code && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-[#94A3B8]">错误码</span>
                      <Badge variant="error">{selectedRun.error_code}</Badge>
                    </div>
                  )}
                  {selectedRun.error_message && (
                    <div className="max-h-48 overflow-auto rounded-md border border-[#7F1D1D] bg-[#450A0A]/30 p-3 text-xs leading-5 text-[#FCA5A5]">
                      {selectedRun.error_message}
                    </div>
                  )}
                  <PublishedPostLink result={selectedRun.result} platform={selectedRun.platform} />
                </>
              ) : (
                <div className="rounded-md border border-dashed border-[#334155] px-3 py-6 text-center text-sm text-[#64748B]">
                  未选择任务
                </div>
              )}
            </div>
          </section>

          <section className="rounded-md border border-[#1E293B] bg-[#111827]">
            <div className="flex items-center gap-2 border-b border-[#1E293B] px-4 py-3 text-sm font-medium text-[#E2E8F0]">
              <ShieldCheck className="h-4 w-4 text-[#22C55E]" />
              安全边界
            </div>
            <div className="space-y-3 p-4 text-sm text-[#94A3B8]">
              <div className="flex items-center justify-between">
                <span>Node 权限</span>
                <Badge variant="success">关闭</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>DesktopExecutor</span>
                <Badge variant="warning">预留</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>MobileExecutor</span>
                <Badge variant="warning">预留</Badge>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}
