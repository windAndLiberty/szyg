/**
 * szyg-frontend API 客户端 — 真实联通 szyg 后端 (FastAPI, port 8000).
 *
 * - JWT Bearer 鉴权，token 存 localStorage；401 自动以 admin/admin123 重新登录后重试。
 * - 开发态经 Vite 代理 (/api → 127.0.0.1:8000)；生产态后端直接托管 SPA，同源。
 * - 绝不使用模拟数据：所有数据均来自后端真实接口。
 */

const TOKEN_KEY = 'token'
const USER_KEY = 'user'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getCurrentUser(): { username: string } | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export async function autoLogin(): Promise<string | null> {
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin', password: 'admin123' }),
    })
    if (!res.ok) return null
    const data = await res.json()
    if (data.access_token) {
      localStorage.setItem(TOKEN_KEY, data.access_token)
      localStorage.setItem(USER_KEY, JSON.stringify(data.user || { username: 'admin' }))
      return data.access_token as string
    }
  } catch (e) {
    console.error('Auto login failed:', e)
  }
  return null
}

export function getErrorMessage(err: unknown, fallback = '请求失败'): string {
  const any = err as { response?: { data?: { detail?: string } }; message?: string }
  return any?.response?.data?.detail || any?.message || fallback
}

async function request<T>(method: string, url: string, body?: unknown, _retry = false): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && !_retry) {
    const newToken = await autoLogin()
    if (newToken) return request<T>(method, url, body, true)
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

export const apiGet = <T = unknown>(url: string): Promise<T> => request<T>('GET', url)
export const apiPost = <T = unknown>(url: string, body?: unknown): Promise<T> => request<T>('POST', url, body)
export const apiPut = <T = unknown>(url: string, body?: unknown): Promise<T> => request<T>('PUT', url, body)
export const apiDel = <T = unknown>(url: string): Promise<T> => request<T>('DELETE', url)

// ── 真实图片/视频生成 REST 调用 ──────────────────────────────────────
// hermes/chat SSE 不产出 image/video 事件；生成走独立 REST 端点。

export interface ImageGenResult {
  backend: string
  images: string[]
  paths?: string[]
  size?: string
  count?: number
  enhanced_prompt?: string
  final_prompt?: string
}

export async function generateImage(prompt: string, size = '1920x1920', count = 1, style = 'none'): Promise<ImageGenResult> {
  return apiPost<ImageGenResult>('/api/image/generate', { prompt, size, count, style })
}

export interface VideoCreateResult {
  ok: boolean
  task_id: string
  status: string
  model: string
  prompt: string
}

export interface VideoTaskResult {
  status: string
  video_url?: string
  download_url?: string
  progress?: number
  error?: string
}

export async function createVideo(prompt: string, opts?: { duration?: number; size?: string; model?: string; image_url?: string }): Promise<VideoCreateResult> {
  return apiPost<VideoCreateResult>('/api/video/create', {
    prompt,
    duration: opts?.duration ?? 5,
    size: opts?.size ?? '720p',
    model: opts?.model ?? 'doubao-video',
    image_url: opts?.image_url ?? '',
  })
}

export async function pollVideoTask(taskId: string, model = 'doubao-video'): Promise<VideoTaskResult> {
  return apiGet<VideoTaskResult>(`/api/video/task/${taskId}?model=${encodeURIComponent(model)}`)
}

export interface MediaStorageLocation {
  kind: 'image' | 'video' | 'audio' | 'document'
  key: 'image_dir' | 'video_dir' | 'audio_dir' | 'document_dir'
  label: string
  path: string
  default_path: string
}

export interface MediaStorageConfig {
  image_dir: string
  video_dir: string
  audio_dir: string
  document_dir: string
  defaults: Record<string, string>
  locations: MediaStorageLocation[]
}

export async function fetchMediaStorage(): Promise<MediaStorageConfig> {
  return apiGet<MediaStorageConfig>('/api/media/storage')
}

export async function updateMediaStorage(payload: Partial<Pick<MediaStorageConfig, 'image_dir' | 'video_dir' | 'audio_dir' | 'document_dir'>>): Promise<MediaStorageConfig> {
  return apiPut<MediaStorageConfig>('/api/media/storage', payload)
}

export interface SaveDocumentResult {
  ok: boolean
  path: string
  url: string
  filename: string
}

export async function saveGeneratedDocument(title: string, content: string, extension = 'md'): Promise<SaveDocumentResult> {
  return apiPost<SaveDocumentResult>('/api/media/documents/save', { title, content, extension })
}

export async function openGeneratedMedia(asset: { path?: string; url?: string }): Promise<{ ok: boolean; path: string }> {
  return apiPost<{ ok: boolean; path: string }>('/api/media/files/open', asset)
}

export async function deleteGeneratedMedia(asset: { path?: string; url?: string }): Promise<{ ok: boolean; deleted: boolean; path: string }> {
  return apiPost<{ ok: boolean; deleted: boolean; path: string }>('/api/media/files/delete', asset)
}

export type HermesEvent = {
  type: string
  content?: string
  tool?: string
  id?: string
  args?: unknown
  result?: string
  url?: string
  prompt?: string
  task_id?: string
  status?: string
  progress?: number
  [k: string]: unknown
}

export interface StreamChatOpts {
  model: string
  messages: { role: string; content: string }[]
  agent_id?: string
  expert_prompt?: string  // AI人才市场专家 prompt（独立通道）
  onEvent: (ev: HermesEvent) => void
  signal?: AbortSignal
}

async function postChat(body: unknown, signal?: AbortSignal): Promise<Response> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch('/api/hermes/chat', { method: 'POST', headers, body: JSON.stringify(body), signal })
}

// ── 平台账号管理 API ──────────────────────────────────────────

export interface PlatformInfo {
  id: string
  name: string
  adapter: string
  state: string
  initialized: boolean
  nickname: string
  followers: number
  session: {
    has_session: boolean
    cookie_count: number
    valid: boolean
    saved_at: string
    cookie_expiry: string | null
  }
  meta: {
    risk_level: string
    risk_label: string
    login_mode: string
    publish_mode: string
    description: string
  }
}

export interface PlatformListResponse {
  status: string
  platforms: PlatformInfo[]
  total: number
}

export interface LoginTriggerResponse {
  ok: boolean
  platform: string
  status: string
  message: string
  login_url: string
}

export async function fetchPlatforms(): Promise<PlatformListResponse> {
  return apiGet<PlatformListResponse>('/api/platforms')
}

export async function getPlatformDetail(platform: string): Promise<{
  status: string
  platform: string
  registered: boolean
  state: string
  login: { is_logged_in: boolean; account_name: string; message: string; cookie_valid_until: string }
  session: PlatformInfo['session']
  meta: PlatformInfo['meta']
}> {
  return apiGet(`/api/platforms/${platform}`)
}

export async function triggerPlatformLogin(platform: string, timeout = 600): Promise<LoginTriggerResponse> {
  return apiPost<LoginTriggerResponse>(`/api/platforms/${platform}/login?timeout=${timeout}`)
}

export interface SauTask {
  id: string
  execution_id?: string
  kind: string
  platform: string
  title: string
  status: 'queued' | 'running' | 'success' | 'failed' | string
  progress: string
  created_at: string
  updated_at: string
  started_at: string
  finished_at: string
  duration_ms: number
  payload: Record<string, unknown>
  result: Record<string, unknown>
  error: string
  error_code?: string
  debug_screenshot: string
}

export interface SauTaskListResponse {
  tasks: SauTask[]
}

export async function fetchSauTasks(limit = 30): Promise<SauTaskListResponse> {
  return apiGet<SauTaskListResponse>(`/api/sau/tasks?limit=${limit}`)
}

export async function getSauTask(taskId: string): Promise<SauTask> {
  return apiGet<SauTask>(`/api/sau/tasks/${taskId}`)
}

export interface SauCreateResponse {
  ok: boolean
  task_id: string
  execution_id: string
  task: SauTask
  run: ExecutionRun
}

export interface CreateSauVideoPayload {
  platform: string
  file_path: string
  title: string
  desc?: string
  tags?: string[]
  thumbnail_path?: string
  schedule?: string
  headless?: boolean
}

export interface CreateSauNotePayload {
  platform: string
  image_paths: string[]
  title: string
  note?: string
  tags?: string[]
  schedule?: string
  headless?: boolean
}

export async function createSauVideoTask(payload: CreateSauVideoPayload): Promise<SauCreateResponse> {
  return apiPost<SauCreateResponse>('/api/sau/upload-video-async', payload)
}

export async function createSauNoteTask(payload: CreateSauNotePayload): Promise<SauCreateResponse> {
  return apiPost<SauCreateResponse>('/api/sau/upload-note-async', payload)
}

export async function deletePlatformSession(platform: string): Promise<{ ok: boolean; platform: string }> {
  return apiDel(`/api/platforms/${platform}/sessions`)
}

// ── 任务看板 API ──────────────────────────────────────────────

export interface TaskItem {
  id: string
  name: string
  description: string
  type: string           // publish | generate | workflow | tool | check | health | notify | custom
  type_label: string     // 发布内容 / AI生成 / 工作流 …
  type_icon: string      // emoji icon
  platform: string       // target platform name
  status: string         // running | completed | failed | pending
  priority: number
  tags: string[]
  created_at: string
  started_at: string
  finished_at: string
  progress: string       // running: dynamic progress text
  result: string         // completed: result summary
  error: string          // failed: error message
}

export interface TaskLogEntry {
  id: string
  type: string
  message: string
  timestamp: string
  status: 'success' | 'error' | 'info'
  duration_ms: number
  action?: string
  error_code?: string
  artifact_path?: string
}

export interface TaskDetail extends TaskItem {
  executions: Array<{
    id: string
    job_id: string
    job_name: string
    status: string
    started_at: string
    finished_at: string
    duration_ms: number
    retry_count: number
    result: string
    error: string
    step_id?: string
    error_code?: string
  }>
  logs: TaskLogEntry[]
  action: string
  action_config: Record<string, unknown>
  trigger_type: string
  trigger_config: Record<string, unknown>
  execution_run?: ExecutionRun
  steps?: ExecutionStep[]
  audit?: AuditEvent[]
  observations?: Observation[]
  debug_screenshot?: string
}

export interface ExecutionRun {
  id: string
  task_type: string
  title: string
  platform: string
  executor_type: 'browser' | 'desktop' | 'mobile' | 'api' | string
  status: 'queued' | 'running' | 'success' | 'failed' | 'paused' | 'needs_human' | 'cancelled' | string
  current_step_id: string
  input: Record<string, unknown>
  result: Record<string, unknown>
  error_code: string
  error_message: string
  source_task_id: string
  created_at: string
  updated_at: string
  started_at: string
  finished_at: string
  duration_ms: number
}

export interface ExecutionStep {
  id: string
  run_id: string
  step_id: string
  name: string
  executor_type: string
  status: string
  action: string
  created_at: string
  started_at: string
  finished_at: string
  duration_ms: number
  attempt: number
  error_code: string
  error_message: string
}

export interface AuditEvent {
  id: string
  run_id: string
  step_id: string
  action: string
  status: string
  message: string
  error_code: string
  artifact_path: string
  duration_ms: number
  created_at: string
}

export interface Observation {
  id: string
  run_id: string
  step_id: string
  type: string
  summary: string
  artifact_path: string
  created_at: string
}

export async function fetchExecutions(limit = 100): Promise<{ runs: ExecutionRun[] }> {
  return apiGet<{ runs: ExecutionRun[] }>(`/api/executions?limit=${limit}`)
}

export async function getExecution(runId: string): Promise<ExecutionRun & {
  steps: ExecutionStep[]
  audit: AuditEvent[]
  observations: Observation[]
}> {
  return apiGet(`/api/executions/${runId}`)
}

export async function retryExecution(runId: string): Promise<{ ok: boolean; run: ExecutionRun }> {
  return apiPost(`/api/executions/${runId}/retry`)
}

export async function resumeExecution(runId: string): Promise<{ ok: boolean; run: ExecutionRun }> {
  return apiPost(`/api/executions/${runId}/resume`)
}

export async function cancelExecution(runId: string): Promise<{ ok: boolean; run: ExecutionRun }> {
  return apiPost(`/api/executions/${runId}/cancel`)
}

export interface TaskListResponse {
  tasks: TaskItem[]
  counts: {
    all: number
    running: number
    needs_human: number
    completed: number
    failed: number
  }
}

export async function fetchTasks(status: string = 'all', search: string = ''): Promise<TaskListResponse> {
  const params = new URLSearchParams({ status, limit: '100' })
  if (search) params.set('search', search)
  return apiGet<TaskListResponse>(`/api/tasks?${params.toString()}`)
}

export async function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return apiGet<TaskDetail>(`/api/tasks/${taskId}`)
}

export async function retryTask(taskId: string): Promise<{ ok: boolean; task_id: string; execution_id: string }> {
  return apiPost(`/api/tasks/${taskId}/retry`)
}

export async function cancelTask(taskId: string): Promise<{ ok: boolean; task_id: string }> {
  return apiPost(`/api/tasks/${taskId}/cancel`)
}

// Acquisition center API

export interface AcquisitionSearchRequest {
  keyword: string
  platforms: string[]
  limit: number
  min_score?: number
}

export interface AcquisitionTarget {
  video_id?: string
  platform: string
  title: string
  description?: string
  author?: string
  author_followers?: number
  url?: string
  cover?: string
  plays?: number
  likes?: number
  comments_count?: number
  shares?: number
  published_at?: string
  quality_score?: number
  score_detail?: string | Record<string, unknown>
  [key: string]: unknown
}

export interface AcquisitionTargetResponse {
  keyword: string
  total: number
  videos?: AcquisitionTarget[]
  targets?: AcquisitionTarget[]
}

export interface GenerateCommentResponse {
  comments: string[]
  count: number
}

export interface DeAIResponse {
  original: string
  processed: string
}

export interface PreflightResult {
  pass?: boolean
  passed?: boolean
  ok?: boolean
  risk_level?: string
  risk?: string
  score?: number
  message?: string
  risks?: string[]
  reasons?: string[]
  suggestions?: string[]
  [key: string]: unknown
}

export interface CommentQueueItem {
  id?: string
  item_id?: string
  platform?: string
  status?: string
  text?: string
  comment?: string
  target_url?: string
  video_title?: string
  created_at?: string
  updated_at?: string
  error?: string
  [key: string]: unknown
}

export interface CommentQueueResponse {
  items: CommentQueueItem[]
  total: number
}

export interface AcquisitionStatsResponse {
  queue?: Record<string, unknown>
  rate_limits?: Record<string, unknown>
  [key: string]: unknown
}

export interface MonitorTarget {
  target_id?: string
  id?: string
  platform?: string
  video_id?: string
  video_title?: string
  video_url?: string
  owner?: string
  status?: string
  poll_interval?: number
  last_poll_at?: string
  last_checked_at?: string
  created_at?: string
  [key: string]: unknown
}

export interface LeadItem {
  id?: string
  lead_id?: string
  platform?: string
  user_name?: string
  author_name?: string
  comment_text?: string
  content?: string
  grade?: string
  status?: string
  score?: number
  lead_score?: number
  source_title?: string
  created_at?: string
  updated_at?: string
  notes?: string
  [key: string]: unknown
}

export interface CustomerItem {
  id?: string
  name?: string
  platform?: string
  source?: string
  status?: string
  grade?: string
  tags?: string[]
  owner?: string
  lastMessage?: string
  last_interaction?: string
  next_action?: string
  [key: string]: unknown
}

export interface MessageItem {
  id?: string
  customer_id?: string
  sender?: string
  text?: string
  time?: string
  created_at?: string
  [key: string]: unknown
}

export interface ReplyTemplateItem {
  id?: string
  name?: string
  keywords?: string[]
  content?: string
  enabled?: boolean
  created_at?: string
}

export async function acquisitionSearch(payload: AcquisitionSearchRequest): Promise<AcquisitionTargetResponse> {
  return apiPost('/api/acquisition/search', payload)
}

export async function acquisitionAggregate(payload: AcquisitionSearchRequest): Promise<AcquisitionTargetResponse> {
  return apiPost('/api/acquisition/search/aggregate', payload)
}

export async function acquisitionFindTargets(payload: AcquisitionSearchRequest): Promise<AcquisitionTargetResponse> {
  return apiPost('/api/acquisition/intercept/find-targets', payload)
}

export async function acquisitionGenerateComments(payload: {
  video_title: string
  video_description?: string
  count?: number
  strategy?: string
}): Promise<GenerateCommentResponse> {
  return apiPost('/api/acquisition/comments/generate', payload)
}

export async function acquisitionDeAI(text: string, platform = 'douyin'): Promise<DeAIResponse> {
  return apiPost('/api/acquisition/comments/deai', { text, platform })
}

export async function acquisitionPreflight(text: string): Promise<PreflightResult> {
  return apiPost('/api/acquisition/comments/preflight', { text })
}

export async function acquisitionCommentQueue(params?: { status?: string; platform?: string; limit?: number; offset?: number }): Promise<CommentQueueResponse> {
  const query = new URLSearchParams()
  if (params?.status) query.set('status', params.status)
  if (params?.platform) query.set('platform', params.platform)
  if (params?.limit) query.set('limit', String(params.limit))
  if (params?.offset) query.set('offset', String(params.offset))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiGet(`/api/acquisition/comments/queue${suffix}`)
}

export async function acquisitionCommentStats(): Promise<AcquisitionStatsResponse> {
  return apiGet('/api/acquisition/comments/stats')
}

export async function acquisitionMonitorTargets(): Promise<{ targets: MonitorTarget[]; total: number }> {
  return apiGet('/api/acquisition/monitor/targets')
}

export async function acquisitionAddMonitorTarget(payload: {
  platform: string
  video_id?: string
  video_title?: string
  video_url?: string
  owner?: string
  poll_interval?: number
}): Promise<{ ok: boolean; target_id: string }> {
  return apiPost('/api/acquisition/monitor/targets', payload)
}

export async function acquisitionLeads(params?: { status?: string; grade?: string; platform?: string; limit?: number }): Promise<{ leads: LeadItem[]; total: number }> {
  const query = new URLSearchParams()
  if (params?.status) query.set('status', params.status)
  if (params?.grade) query.set('grade', params.grade)
  if (params?.platform) query.set('platform', params.platform)
  if (params?.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiGet(`/api/acquisition/leads${suffix}`)
}

export async function acquisitionLeadStats(): Promise<Record<string, unknown>> {
  return apiGet('/api/acquisition/leads/stats')
}

export async function acquisitionFunnel(): Promise<Record<string, unknown>> {
  return apiGet('/api/acquisition/leads/funnel')
}

export async function acquisitionConversions(params?: { stage?: string; platform?: string; limit?: number }): Promise<{ conversions: Record<string, unknown>[]; total: number }> {
  const query = new URLSearchParams()
  if (params?.stage) query.set('stage', params.stage)
  if (params?.platform) query.set('platform', params.platform)
  if (params?.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiGet(`/api/acquisition/conversions${suffix}`)
}

export async function acquisitionGenerateReply(payload: {
  comment_text: string
  author_name?: string
  platform?: string
}): Promise<{
  reply: string
  lead_score: number
  grade: string
  score_detail: Record<string, number>
}> {
  return apiPost('/api/acquisition/auto-reply/generate', payload)
}

export async function acquisitionScoreComment(payload: {
  comment_text: string
  author_name?: string
  platform?: string
}): Promise<Record<string, unknown>> {
  return apiPost('/api/acquisition/auto-reply/score', payload)
}

export async function acquisitionCustomers(search = '', limit = 50): Promise<{ customers: CustomerItem[]; total: number }> {
  const query = new URLSearchParams({ limit: String(limit) })
  if (search) query.set('search', search)
  return apiGet(`/api/acquisition/customers?${query.toString()}`)
}

export async function acquisitionMessages(customerId = ''): Promise<{ messages: MessageItem[]; total: number }> {
  const query = new URLSearchParams()
  if (customerId) query.set('customer_id', customerId)
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiGet(`/api/acquisition/messages${suffix}`)
}

export async function acquisitionReplyTemplates(): Promise<{ templates: ReplyTemplateItem[]; total: number }> {
  return apiGet('/api/acquisition/reply-templates')
}

export async function streamHermesChat(opts: StreamChatOpts): Promise<void> {
  const payload = {
    model: opts.model,
    messages: opts.messages,
    stream: true,
    agent_id: opts.agent_id,
    expert_prompt: opts.expert_prompt || '',
  }
  let res = await postChat(payload, opts.signal)
  if (res.status === 401) {
    const newToken = await autoLogin()
    if (newToken) res = await postChat(payload, opts.signal)
  }
  if (!res.ok || !res.body) {
    let detail = `HTTP ${res.status}`
    try {
      detail = (await res.json()).detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        opts.onEvent(JSON.parse(line.slice(6)) as HermesEvent)
      } catch {
        /* skip malformed */
      }
    }
  }
}
