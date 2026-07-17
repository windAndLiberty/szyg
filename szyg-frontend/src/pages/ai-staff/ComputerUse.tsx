import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Eye,
  Hand,
  Loader2,
  MonitorCog,
  MousePointerClick,
  RefreshCw,
  Square,
  TerminalSquare,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  cancelExecution,
  createComputerUseTask,
  fetchComputerUseStatus,
  fetchExecutions,
  getComputerUseTask,
  observeComputerUse,
  type ComputerUseObservation,
  type ComputerUseStatus,
  type ExecutionRun,
  type ExecutionStep,
  type AuditEvent,
  type Observation,
} from '@/lib/api'

const APP_OPTIONS = [
  { value: 'unknown', label: '未确定' },
  { value: 'windows', label: '当前桌面' },
  { value: 'notepad', label: '记事本' },
  { value: 'explorer', label: '资源管理器' },
  { value: 'browser', label: '网页/浏览器' },
  { value: 'chrome', label: '已打开的浏览器' },
  { value: 'wechat', label: '微信' },
  { value: 'jianying', label: '剪映' },
]

const TASK_TEMPLATES = [
  {
    label: '写一段文字',
    app: 'notepad',
    instruction: '打开记事本并输入一段测试文字',
    text: '这是电脑使用模块的测试输入',
    url: '',
  },
  {
    label: '打开网页',
    app: 'browser',
    instruction: '打开网页并检查页面是否正常显示',
    text: '',
    url: 'https://example.com',
  },
  {
    label: '整理文件夹',
    app: 'explorer',
    instruction: '打开资源管理器并查看指定文件夹',
    text: '',
    url: '',
  },
  {
    label: '观察当前桌面',
    app: 'windows',
    instruction: '观察当前桌面并告诉我有哪些可操作内容',
    text: '',
    url: '',
  },
  {
    label: '自定义任务',
    app: 'unknown',
    instruction: '',
    text: '',
    url: '',
  },
]

const MODE_OPTIONS = [
  { value: 'assisted', label: '辅助执行' },
  { value: 'observe_only', label: '只观察' },
  { value: 'execute', label: '自动执行' },
] as const

function statusLabel(status: string) {
  if (status === 'success') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '运行中'
  if (status === 'queued') return '排队中'
  if (status === 'needs_human') return '需人工'
  if (status === 'paused') return '已暂停'
  if (status === 'cancelled') return '已取消'
  return status || '未知'
}

function statusVariant(status: string): 'success' | 'warning' | 'error' | 'muted' {
  if (status === 'success') return 'success'
  if (status === 'failed' || status === 'cancelled') return 'error'
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

function appLabel(value: string) {
  return APP_OPTIONS.find((item) => item.value === value)?.label || value || 'Windows'
}

function cleanDisplayText(value: string, fallback: string) {
  if (!value) return fallback
  return value.includes('\uFFFD') ? fallback : value
}

function sourceLabel(value?: string) {
  if (value === 'uia') return '结构'
  if (value === 'ocr') return '文字'
  if (value === 'dom') return '网页'
  if (value === 'clustered') return '聚合'
  if (value === 'vision') return '视觉'
  return value || '未知'
}

function providerLabel(value?: string) {
  if (value === 'terminator') return '桌面结构'
  if (value === 'playwright') return '浏览器网页'
  if (value === 'vision') return '视觉兜底'
  return '基础观察'
}

export default function ComputerUse() {
  const [status, setStatus] = useState<ComputerUseStatus | null>(null)
  const [observation, setObservation] = useState<ComputerUseObservation | null>(null)
  const [runs, setRuns] = useState<ExecutionRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState('')
  const [detail, setDetail] = useState<(ExecutionRun & {
    steps: ExecutionStep[]
    audit: AuditEvent[]
    observations: Observation[]
    debug_screenshot: string
  }) | null>(null)
  const [instruction, setInstruction] = useState('打开记事本并输入一段测试文字')
  const [targetApp, setTargetApp] = useState('notepad')
  const [mode, setMode] = useState<'observe_only' | 'assisted' | 'execute'>('assisted')
  const [text, setText] = useState('这是电脑使用模块的测试输入')
  const [url, setUrl] = useState('')
  const [targetSelector, setTargetSelector] = useState('')
  const [expectedResult, setExpectedResult] = useState('')
  const [filePaths, setFilePaths] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [observing, setObserving] = useState(false)
  const [error, setError] = useState('')
  const observedElements = useMemo(() => (observation?.elements || []).slice(0, 8), [observation])
  const sourceCounts = observation?.source_counts || {}
  const providers = observation?.providers || status?.providers || status?.health?.providers || {}
  const omni = providers.omniparser

  async function load(selected = selectedRunId) {
    setError('')
    try {
      const [statusResult, executionResult] = await Promise.all([
        fetchComputerUseStatus(),
        fetchExecutions(80),
      ])
      const computerRuns = (executionResult.runs || []).filter((run) => run.task_type === 'computer_use')
      setStatus(statusResult)
      setRuns(computerRuns)
      const nextSelected = selected || computerRuns[0]?.id || ''
      setSelectedRunId(nextSelected)
      if (nextSelected) {
        const task = await getComputerUseTask(nextSelected)
        setDetail(task)
      } else {
        setDetail(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const timer = window.setInterval(() => load(), 8000)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleObserve() {
    setObserving(true)
    setError('')
    try {
      const result = await observeComputerUse()
      setObservation(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : '观察失败')
    } finally {
      setObserving(false)
    }
  }

  async function handleCreate() {
    if (!instruction.trim()) {
      setError('请输入要完成的电脑使用目标')
      return
    }
    setCreating(true)
    setError('')
    try {
      const resolvedTargetApp = targetApp === 'unknown' ? 'windows' : targetApp
      const result = await createComputerUseTask({
        instruction,
        target_app: resolvedTargetApp,
        url,
        mode,
        expected_result: expectedResult,
        target_selector: targetSelector,
        files: filePaths.split('\n').map((item) => item.trim()).filter(Boolean),
        max_steps: 8,
        require_confirmation: true,
        sensitive_policy: 'handoff',
        text,
      })
      setSelectedRunId(result.execution_id)
      await load(result.execution_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  function applyTemplate(template: typeof TASK_TEMPLATES[number]) {
    setTargetApp(template.app)
    setInstruction(template.instruction)
    setText(template.text)
    setUrl(template.url)
    setTargetSelector('')
    setExpectedResult('')
    setFilePaths('')
    setMode(template.app === 'windows' ? 'observe_only' : 'assisted')
  }

  async function handleSelect(runId: string) {
    setSelectedRunId(runId)
    try {
      setDetail(await getComputerUseTask(runId))
    } catch (err) {
      setError(err instanceof Error ? err.message : '详情加载失败')
    }
  }

  async function handleCancel(runId: string) {
    setError('')
    try {
      await cancelExecution(runId)
      await load(runId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '取消失败')
    }
  }

  const activeRuns = useMemo(
    () => runs.filter((run) => ['queued', 'running', 'paused'].includes(run.status)),
    [runs],
  )
  const humanRuns = useMemo(
    () => runs.filter((run) => run.status === 'needs_human'),
    [runs],
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-[#94A3B8]">
            <span>{activeRuns.length} 个运行中</span>
            <span className="text-[#334155]">/</span>
            <span>{humanRuns.length} 个需人工</span>
            <span className="text-[#334155]">/</span>
            <span>{status?.health?.available ? '本机执行组件已就绪' : '本机执行组件未就绪'}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={handleObserve} disabled={observing}>
            {observing ? <Loader2 className="animate-spin" /> : <Eye />}
            观察桌面
          </Button>
          <Button variant="outline" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            刷新
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-[#7F1D1D] bg-[#450A0A]/40 px-4 py-3 text-sm text-[#FCA5A5]">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-[320px_minmax(0,1fr)_340px] gap-4 max-2xl:grid-cols-[300px_minmax(0,1fr)] max-xl:grid-cols-1">
        <aside className="flex min-h-0 flex-col gap-4">
          <section className="rounded-md border border-[#1E293B] bg-[#111827]">
            <div className="border-b border-[#1E293B] px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-[#E2E8F0]">
                <MonitorCog className="h-4 w-4 text-[#38BDF8]" />
                本机能力
              </div>
            </div>
            <div className="space-y-3 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#94A3B8]">执行组件</span>
                <Badge variant={status?.health?.available ? 'success' : 'warning'}>
                  {status?.health?.available ? '已就绪' : '未就绪'}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#94A3B8]">视觉兜底</span>
                <Badge variant={omni?.available ? 'success' : omni?.source_available ? 'warning' : 'muted'}>
                  {omni?.available ? '已就绪' : omni?.source_available ? '未就绪' : '未配置'}
                </Badge>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-md border border-[#1E293B] bg-[#0B1120] px-2 py-2">
                  <div className="text-[#64748B]">源码</div>
                  <div className={omni?.source_available ? 'mt-1 text-[#86EFAC]' : 'mt-1 text-[#64748B]'}>
                    {omni?.source_available ? '存在' : '缺失'}
                  </div>
                </div>
                <div className="rounded-md border border-[#1E293B] bg-[#0B1120] px-2 py-2">
                  <div className="text-[#64748B]">权重</div>
                  <div className={omni?.weights_ready ? 'mt-1 text-[#86EFAC]' : 'mt-1 text-[#FBBF24]'}>
                    {omni?.weights_ready ? '就绪' : '待配置'}
                  </div>
                </div>
                <div className="rounded-md border border-[#1E293B] bg-[#0B1120] px-2 py-2">
                  <div className="text-[#64748B]">服务</div>
                  <div className={omni?.service_ready ? 'mt-1 text-[#86EFAC]' : 'mt-1 text-[#64748B]'}>
                    {omni?.service_ready ? '运行' : '未运行'}
                  </div>
                </div>
              </div>
              <p className="rounded-md bg-[#0F172A] px-3 py-2 text-xs leading-6 text-[#94A3B8]">
                {omni?.message || status?.health?.message || '正在检查本机能力'}
              </p>
            </div>
          </section>

          <section className="rounded-md border border-[#1E293B] bg-[#111827]">
            <div className="border-b border-[#1E293B] px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-[#E2E8F0]">
                <MousePointerClick className="h-4 w-4 text-[#A78BFA]" />
                创建任务
              </div>
            </div>
            <div className="space-y-3 p-4">
              <div>
                <div className="mb-2 text-xs font-medium text-[#94A3B8]">常用任务</div>
                <div className="grid grid-cols-2 gap-2">
                  {TASK_TEMPLATES.map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      onClick={() => applyTemplate(item)}
                      className={`rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                        targetApp === item.app && instruction === item.instruction
                          ? 'border-[#2563EB] bg-[#172554]/60 text-[#DBEAFE]'
                          : 'border-[#1E293B] bg-[#0B1120] text-[#CBD5E1] hover:border-[#334155]'
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-[#94A3B8]">要操作的软件</label>
                <select
                  value={targetApp}
                  onChange={(event) => setTargetApp(event.target.value)}
                  className="h-10 w-full rounded-md border border-[#1E293B] bg-[#0F172A] px-3 text-sm text-[#F8FAFC] outline-none focus:border-[#6366F1]"
                >
                  {APP_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>
              <label className="block text-xs font-medium text-[#94A3B8]">想让电脑做什么</label>
              <textarea
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                className="min-h-[104px] w-full resize-none rounded-md border border-[#1E293B] bg-[#0F172A] px-3 py-2 text-sm text-[#F8FAFC] outline-none transition-colors placeholder:text-[#475569] focus:border-[#6366F1]"
                placeholder={targetApp === 'unknown' ? '帮我操作当前电脑上的软件，完成我描述的目标' : '例如：打开记事本并输入一段测试文字'}
              />
              {(targetApp === 'browser' || url) && (
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-[#94A3B8]">网页地址</label>
                  <input
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                    className="h-10 w-full rounded-md border border-[#1E293B] bg-[#0F172A] px-3 text-sm text-[#F8FAFC] outline-none transition-colors placeholder:text-[#475569] focus:border-[#6366F1]"
                    placeholder="例如：https://example.com"
                  />
                </div>
              )}
              {targetApp === 'notepad' && (
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-[#94A3B8]">要输入的内容</label>
                  <textarea
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    className="min-h-[74px] w-full resize-none rounded-md border border-[#1E293B] bg-[#0F172A] px-3 py-2 text-sm text-[#F8FAFC] outline-none transition-colors placeholder:text-[#475569] focus:border-[#6366F1]"
                    placeholder="输入要写到记事本里的文字"
                  />
                </div>
              )}
              <button
                type="button"
                onClick={() => setShowAdvanced((value) => !value)}
                className="w-full rounded-md border border-[#1E293B] bg-[#0B1120] px-3 py-2 text-left text-xs text-[#94A3B8] transition-colors hover:border-[#334155]"
              >
                {showAdvanced ? '收起高级选项' : '高级选项'}
              </button>
              {showAdvanced && (
                <div className="space-y-3 rounded-md border border-[#1E293B] bg-[#0B1120] p-3">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-[#94A3B8]">执行方式</label>
                    <select
                      value={mode}
                      onChange={(event) => setMode(event.target.value as typeof mode)}
                      className="h-9 w-full rounded-md border border-[#1E293B] bg-[#0F172A] px-3 text-sm text-[#F8FAFC] outline-none focus:border-[#6366F1]"
                    >
                      {MODE_OPTIONS.map((item) => (
                        <option key={item.value} value={item.value}>{item.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-[#94A3B8]">页面目标</label>
                    <input
                      value={targetSelector}
                      onChange={(event) => setTargetSelector(event.target.value)}
                      className="h-9 w-full rounded-md border border-[#1E293B] bg-[#0F172A] px-3 text-sm text-[#F8FAFC] outline-none transition-colors placeholder:text-[#475569] focus:border-[#6366F1]"
                      placeholder="有明确网页控件时填写，可不填"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-[#94A3B8]">完成后应看到</label>
                    <input
                      value={expectedResult}
                      onChange={(event) => setExpectedResult(event.target.value)}
                      className="h-9 w-full rounded-md border border-[#1E293B] bg-[#0F172A] px-3 text-sm text-[#F8FAFC] outline-none transition-colors placeholder:text-[#475569] focus:border-[#6366F1]"
                      placeholder="例如页面上出现某段文字"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-[#94A3B8]">本地文件</label>
                    <textarea
                      value={filePaths}
                      onChange={(event) => setFilePaths(event.target.value)}
                      className="min-h-[62px] w-full resize-none rounded-md border border-[#1E293B] bg-[#0F172A] px-3 py-2 text-sm text-[#F8FAFC] outline-none transition-colors placeholder:text-[#475569] focus:border-[#6366F1]"
                      placeholder="需要上传或处理文件时，每行一个路径"
                    />
                  </div>
                </div>
              )}
              <Button onClick={handleCreate} disabled={creating} className="w-full">
                {creating ? <Loader2 className="animate-spin" /> : <TerminalSquare />}
                开始执行
              </Button>
            </div>
          </section>
        </aside>

        <main className="flex min-h-[680px] flex-col rounded-md border border-[#1E293B] bg-[#0F172A]">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1E293B] px-5 py-4">
            <div>
              <div className="text-sm font-medium text-[#E2E8F0]">执行证据</div>
              <div className="mt-1 text-xs text-[#64748B]">
                {detail ? `${statusLabel(detail.status)} · ${formatTime(detail.updated_at)}` : '选择任务后查看'}
              </div>
            </div>
            {detail?.status === 'running' || detail?.status === 'queued' ? (
              <Button variant="outline" size="sm" onClick={() => handleCancel(detail.id)}>
                <Square />
                取消任务
              </Button>
            ) : null}
          </div>

          <div className="grid flex-1 grid-cols-[minmax(0,1fr)_280px] gap-0 max-2xl:grid-cols-1">
            <div className="min-h-0 overflow-auto p-5">
              {detail ? (
                <div className="space-y-4">
                  <div className="rounded-md border border-[#1E293B] bg-[#111827] p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h2 className="text-lg font-semibold text-[#F8FAFC]">{detail.title || '电脑使用任务'}</h2>
                        <p className="mt-2 text-sm leading-6 text-[#94A3B8]">
                          {appLabel(detail.platform)} · {detail.current_step_id || '等待执行'}
                        </p>
                      </div>
                      <Badge variant={statusVariant(detail.status)}>{statusLabel(detail.status)}</Badge>
                    </div>
                    {detail.error_message && (
                      <div className="mt-3 rounded-md border border-[#7C2D12] bg-[#431407]/40 px-3 py-2 text-sm text-[#FDBA74]">
                        {detail.error_code ? `${detail.error_code}：` : ''}{detail.error_message}
                      </div>
                    )}
                  </div>

                  <section className="rounded-md border border-[#1E293B] bg-[#111827]">
                    <div className="border-b border-[#1E293B] px-4 py-3 text-sm font-medium text-[#E2E8F0]">步骤</div>
                    <div className="divide-y divide-[#1E293B]">
                      {detail.steps.length === 0 ? (
                        <div className="px-4 py-8 text-center text-sm text-[#64748B]">暂无步骤</div>
                      ) : detail.steps.map((step) => (
                        <div key={step.id} className="flex gap-3 px-4 py-3">
                          <div className="mt-0.5">
                            {step.status === 'success' ? (
                              <CheckCircle2 className="h-4 w-4 text-[#10B981]" />
                            ) : step.status === 'failed' ? (
                              <XCircle className="h-4 w-4 text-[#EF4444]" />
                            ) : step.status === 'needs_human' ? (
                              <Hand className="h-4 w-4 text-[#F59E0B]" />
                            ) : (
                              <Clock3 className="h-4 w-4 text-[#38BDF8]" />
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="text-sm font-medium text-[#E2E8F0]">{step.name}</div>
                              <span className="text-xs text-[#64748B]">{formatTime(step.started_at)}</span>
                            </div>
                            <div className="mt-1 text-xs text-[#64748B]">{step.action}</div>
                            {step.error_message && (
                              <div className="mt-2 text-xs text-[#FCA5A5]">{step.error_message}</div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-md border border-[#1E293B] bg-[#111827]">
                    <div className="border-b border-[#1E293B] px-4 py-3 text-sm font-medium text-[#E2E8F0]">观察记录</div>
                    <div className="space-y-2 p-4">
                      {detail.observations.length === 0 ? (
                        <div className="rounded-md border border-dashed border-[#334155] px-4 py-8 text-center text-sm text-[#64748B]">
                          暂无观察记录
                        </div>
                      ) : detail.observations.map((item) => (
                        <div key={item.id} className="rounded-md border border-[#1E293B] bg-[#0B1120] px-3 py-2">
                          <div className="text-sm text-[#E2E8F0]">{item.summary}</div>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[#64748B]">
                            <span>{item.type}</span>
                            <span>{formatTime(item.created_at)}</span>
                            {item.artifact_path && <span className="break-all text-[#38BDF8]">{item.artifact_path}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              ) : (
                <div className="flex h-full items-center justify-center rounded-md border border-dashed border-[#334155] text-sm text-[#64748B]">
                  暂无电脑使用任务
                </div>
              )}
            </div>

            <aside className="border-l border-[#1E293B] bg-[#0B1120] p-4 max-2xl:border-l-0 max-2xl:border-t">
              <div className="mb-3 text-sm font-medium text-[#E2E8F0]">最近任务</div>
              <div className="max-h-[620px] space-y-2 overflow-auto">
                {runs.length === 0 ? (
                  <div className="rounded-md border border-dashed border-[#334155] px-3 py-8 text-center text-sm text-[#64748B]">
                    暂无任务
                  </div>
                ) : runs.map((run) => (
                  <button
                    key={run.id}
                    onClick={() => handleSelect(run.id)}
                    className={`w-full rounded-md border px-3 py-3 text-left transition-colors ${
                      selectedRunId === run.id
                        ? 'border-[#2563EB] bg-[#172554]/60'
                        : 'border-[#1E293B] bg-[#0F172A] hover:border-[#334155]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 text-sm font-medium text-[#E2E8F0]">
                        <span className="line-clamp-1">{run.title || '电脑使用任务'}</span>
                      </div>
                      <Badge variant={statusVariant(run.status)}>{statusLabel(run.status)}</Badge>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-xs text-[#64748B]">
                      <span>{appLabel(run.platform)}</span>
                      <span>{formatTime(run.updated_at)}</span>
                    </div>
                  </button>
                ))}
              </div>
            </aside>
          </div>
        </main>

        <aside className="flex min-h-0 flex-col gap-4 max-2xl:col-span-2 max-xl:col-span-1">
          <section className="rounded-md border border-[#1E293B] bg-[#111827]">
            <div className="border-b border-[#1E293B] px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-[#E2E8F0]">
                <Eye className="h-4 w-4 text-[#38BDF8]" />
                当前观察
              </div>
            </div>
            <div className="space-y-3 p-4">
              <div className="rounded-md bg-[#0F172A] px-3 py-2 text-sm leading-6 text-[#94A3B8]">
                {observation
                  ? cleanDisplayText(observation.summary, '窗口标题编码异常，请查看可见应用列表')
                  : status?.health?.available
                    ? '本机执行组件已就绪，可观察桌面或创建任务'
                    : '点击观察桌面获取当前状态'}
              </div>
              {observation?.primary_provider && (
                <div className="flex items-center justify-between rounded-md border border-[#1E293B] bg-[#0B1120] px-3 py-2 text-xs">
                  <span className="text-[#64748B]">主观察能力</span>
                  <span className="font-medium text-[#E2E8F0]">{providerLabel(observation.primary_provider)}</span>
                </div>
              )}
              {observation?.vision?.message && (
                <div className="rounded-md border border-[#334155] bg-[#0B1120] px-3 py-2 text-xs leading-5 text-[#94A3B8]">
                  {observation.vision.message}
                </div>
              )}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-md border border-[#1E293B] bg-[#0B1120] p-3">
                  <div className="text-[#64748B]">可见窗口</div>
                  <div className="mt-1 text-lg font-semibold text-[#F8FAFC]">
                    {observation?.windows?.length ?? status?.windows?.length ?? 0}
                  </div>
                </div>
                <div className="rounded-md border border-[#1E293B] bg-[#0B1120] p-3">
                  <div className="text-[#64748B]">截图状态</div>
                  <div className="mt-1 text-lg font-semibold text-[#F8FAFC]">
                    {observation?.screenshot?.ok ? '已记录' : '未记录'}
                  </div>
                </div>
                <div className="rounded-md border border-[#1E293B] bg-[#0B1120] p-3">
                  <div className="text-[#64748B]">识别控件</div>
                  <div className="mt-1 text-lg font-semibold text-[#F8FAFC]">
                    {observation?.element_count ?? observation?.elements?.length ?? 0}
                  </div>
                </div>
                <div className="rounded-md border border-[#1E293B] bg-[#0B1120] p-3">
                  <div className="text-[#64748B]">观察来源</div>
                  <div className="mt-1 truncate text-sm font-semibold text-[#F8FAFC]">
                    {Object.keys(sourceCounts).length > 0
                      ? Object.entries(sourceCounts).map(([key, count]) => `${sourceLabel(key)}${count}`).join(' / ')
                      : '-'}
                  </div>
                </div>
              </div>
              {observation?.screenshot?.path && (
                <div className="break-all rounded-md border border-[#1E293B] bg-[#0B1120] px-3 py-2 text-xs text-[#38BDF8]">
                  {observation.screenshot.path}
                </div>
              )}
              {observedElements.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-medium text-[#94A3B8]">识别到的控件</div>
                  {observedElements.map((item, index) => (
                    <div key={`${item.source || 'source'}-${item.index || index}`} className="rounded-md border border-[#1E293B] bg-[#0B1120] px-3 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate text-sm text-[#E2E8F0]">
                          {cleanDisplayText(item.name || item.role || '未命名控件', '控件名称编码异常')}
                        </span>
                        <span className="shrink-0 rounded bg-[#1E293B] px-2 py-0.5 text-[11px] text-[#94A3B8]">
                          {sourceLabel(item.source)}{item.index ? ` #${item.index}` : ''}
                        </span>
                      </div>
                      <div className="mt-1 truncate text-xs text-[#64748B]">{item.role || '未知类型'}</div>
                      {item.selector && (
                        <div className="mt-1 truncate text-xs text-[#38BDF8]">{item.selector}</div>
                      )}
                      {item.bounds && Object.keys(item.bounds).length > 0 && (
                        <div className="mt-1 truncate text-xs text-[#64748B]">
                          坐标 {String(item.bounds.x ?? '-')} / {String(item.bounds.y ?? '-')} · {String(item.bounds.width ?? '-')} x {String(item.bounds.height ?? '-')}
                        </div>
                      )}
                      <div className="mt-1 text-xs text-[#64748B]">
                        {item.actionable ? '可执行' : '仅观察'}
                      </div>
                      {item.source === 'vision' && (
                        <div className="mt-1 text-xs text-[#FBBF24]">
                          视觉候选{typeof item.confidence === 'number' ? ` · 置信度 ${Math.round(item.confidence * 100)}%` : ''}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="rounded-md border border-[#1E293B] bg-[#111827]">
            <div className="border-b border-[#1E293B] px-4 py-3 text-sm font-medium text-[#E2E8F0]">
              可见应用
            </div>
            <div className="max-h-[360px] space-y-2 overflow-auto p-3">
              {(observation?.windows || status?.windows || []).length === 0 ? (
                <div className="rounded-md border border-dashed border-[#334155] px-3 py-6 text-center text-sm text-[#64748B]">
                  暂未识别窗口
                </div>
              ) : (observation?.windows || status?.windows || []).map((item, index) => (
                <div key={`${item.pid || index}-${item.title}`} className="rounded-md border border-[#1E293B] bg-[#0F172A] px-3 py-2">
                  <div className="line-clamp-1 text-sm text-[#E2E8F0]">{item.title || '未命名窗口'}</div>
                  <div className="mt-1 text-xs text-[#64748B]">{item.process || '未知进程'} · {item.pid || '-'}</div>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}
