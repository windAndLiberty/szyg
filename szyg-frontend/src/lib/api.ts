/**
 * szyg-frontend API 客户端 — 真实联通 szyg 后端 (FastAPI, port 8000).
 *
 * - 云账户会话由本地后端代理；长期凭证不会进入浏览器存储。
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
  // Kept as a compatibility shim for older call sites. Cloud session recovery
  // happens inside the local backend and never returns a token to the renderer.
  return null
}

export function toUserFacingMessage(value: unknown, fallback = '操作未完成，请稍后重试'): string {
  const raw = String(value || '').trim()
  if (!raw) return fallback

  if (/total tokens of image and text exceed|max message tokens|context length/i.test(raw)) {
    return '素材或文字内容较多，请减少内容后重试'
  }
  if (/duration[^\n]*(not valid|invalid)|specified duration/i.test(raw)) {
    return '当前时长不受支持，请调整后重试'
  }
  if (/invalid role|role must be specified|task_type[^\n]*not support/i.test(raw)) {
    return '当前参考素材组合暂不受支持，请调整素材后重试'
  }
  if (/method not allowed/i.test(raw)) return '当前操作暂不可用'

  const hasTechnicalDetail = /seedance|seedream|doubao|qwen|volcengine|火山方舟|火山引擎|\bprovider\b|\bendpoint\b|ep-(?:m-)?[\w-]+|invalidendpointormodel|model id|推理服务|接入点/i.test(raw)
  if (hasTechnicalDetail && /failed|error|not found|does not exist|not configured|invalid|不可用|未配置|失败|无权限|拒绝/i.test(raw)) {
    return '当前智能服务暂时不可用，请稍后重试'
  }

  return raw
    .replace(/doubao-seedance-[\w.-]+|seedance(?:\s*[\w.-]+)?/gi, '视频生成服务')
    .replace(/doubao-seed(?:ream)?-[\w.-]+|qwen[\w.-]*/gi, '智能服务')
    .replace(/VolcEngine|火山方舟|火山引擎/gi, '智能服务')
    .replace(/ep-(?:m-)?[\w-]+/gi, '服务配置')
    .replace(/Execution\s*Kernel/gi, '任务系统')
    .replace(/Hermes/gi, '超级员工')
    .replace(/Playwright|OmniParser|RPA/gi, '自动操作服务')
    .replace(/API\s*Key/gi, '服务凭证')
    .replace(/\bProvider\b/gi, '服务')
}

export function getErrorMessage(err: unknown, fallback = '请求失败'): string {
  const any = err as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = any?.response?.data?.detail
  if (typeof detail === 'string') return toUserFacingMessage(detail, fallback)
  if (detail && typeof detail === 'object' && 'message' in detail) return toUserFacingMessage((detail as { message: unknown }).message, fallback)
  return toUserFacingMessage(any?.message, fallback)
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
    cache: 'no-store',
  })

  if (!res.ok) {
    let detail: unknown = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch {
      /* ignore */
    }
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const rawMessage = String((detail as { message: unknown }).message)
      console.error(`[API] ${method} ${url}:`, rawMessage)
      throw new Error(toUserFacingMessage(rawMessage))
    }
    const rawMessage = String(detail)
    console.error(`[API] ${method} ${url}:`, rawMessage)
    throw new Error(toUserFacingMessage(rawMessage))
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (!text) return undefined as T
  try {
    return JSON.parse(text) as T
  } catch {
    const contentType = res.headers.get('content-type') || 'unknown'
    throw new Error(`接口返回格式异常：${url}（${contentType}）`)
  }
}

export const apiGet = <T = unknown>(url: string): Promise<T> => request<T>('GET', url)
export const apiPost = <T = unknown>(url: string, body?: unknown): Promise<T> => request<T>('POST', url, body)
export const apiPut = <T = unknown>(url: string, body?: unknown): Promise<T> => request<T>('PUT', url, body)
export const apiDel = <T = unknown>(url: string): Promise<T> => request<T>('DELETE', url)

export interface CloudSession {
  configured: boolean
  authenticated: boolean
  message?: string
  user?: { id: string; email: string; display_name: string; role: string; organization_id: string }
  device?: { id: string; name: string; status: string; last_seen_at?: string }
}

export interface CloudUsage {
  period: 'day'
  timezone: string
  period_start: string
  period_end: string
  today_credits: number
  as_of: string
  used: Record<string, number>
  quotas: Record<string, number>
}

export interface CloudBillingBreakdown {
  capability: string
  credits: number
  requests: number
}

export interface CloudCreditRecord {
  id: string
  kind: 'recharge' | 'adjustment'
  credits: number
  payment_amount_cny: number
  currency: string
  note: string
  reference_id: string
  created_at: string
}

export interface CloudUsageRecord {
  id: string
  capability: string
  credits: number
  status: string
  created_at: string
}

export interface CloudBilling {
  balance_credits: number
  credited_credits: number
  spent_credits: number
  today_credits: number
  thirty_day_credits: number
  timezone: string
  as_of: string
  breakdown: CloudBillingBreakdown[]
  recharges: CloudCreditRecord[]
  recent_usage: CloudUsageRecord[]
}

export const fetchCloudSession = () => apiGet<CloudSession>('/api/cloud/session')
export const loginCloud = (email: string, password: string, totp_code = '') =>
  apiPost<CloudSession>('/api/cloud/login', { email, password, totp_code })
export const activateCloud = (invitation_code: string, display_name: string, password: string) =>
  apiPost<CloudSession>('/api/cloud/activate', { invitation_code, display_name, password })
export const logoutCloud = () => apiPost<{ ok: boolean }>('/api/cloud/logout')
export const fetchCloudDevices = () => apiGet<{ items: Array<Record<string, unknown>> }>('/api/cloud/devices')
export const fetchCloudEntitlements = () => apiGet<Record<string, unknown>>('/api/cloud/entitlements')
export const fetchCloudUsage = () => apiGet<CloudUsage>('/api/cloud/usage')
export const fetchCloudBilling = () => apiGet<CloudBilling>('/api/cloud/billing')

export interface CompetitorAccount {
  id: string
  platform: string
  platform_label: string
  name: string
  profile_url: string
  handle: string
  avatar_url?: string
  followers?: number | null
  following?: number | null
  works_count?: number | null
  bio?: string
  tags: string[]
  sync_status: string
  sync_message: string
  last_sync_at?: string
  recent_items?: Array<Record<string, unknown>>
  created_at: string
  updated_at: string
}

export interface IntelligenceOverview {
  total_competitors: number
  synced_competitors: number
  needs_sync: number
  platforms: Record<string, number>
  available_platforms: Array<{ value: string; label: string }>
}

export interface IntelligenceBusinessProfile {
  id: string
  product_name: string
  industry: string
  audience: string
  region: string
  goals: string[]
  selling_points: string[]
  seed_keywords: string[]
  platforms: string[]
  use_knowledge_base?: boolean
  knowledge_query?: string
  created_at: string
  updated_at: string
}

export interface IntelligenceContentItem {
  id: string
  platform: string
  platform_label: string
  keyword: string
  title: string
  description: string
  author: string
  source_url: string
  cover?: string
  plays: number
  likes: number
  comments_count: number
  shares: number
  favorites?: number
  coins?: number
  danmaku?: number
  author_id?: string
  author_profile_url?: string
  author_followers?: number
  author_following?: number
  comment_samples?: Array<Record<string, unknown>>
  comment_insights?: {
    sample_count: number
    questions: string[]
    needs: string[]
    summary: string
  }
  published_at?: string
  quality_score: number
  score_detail?: Record<string, unknown>
  engagement?: number
  hot_score?: number
  is_breakout?: boolean
  breakout_reason?: string
  comparison_sample_size?: number
  source_name?: string
  collection_method?: string
  collected_at?: string
  data_quality?: string
  relevance_score?: number
}

export interface IntelligenceCandidate {
  id: string
  platform: string
  platform_label: string
  name: string
  profile_url: string
  author_id?: string
  followers?: number
  following?: number
  evidence_url: string
  reason: string
  matched_items: number
  top_title: string
  tags: string[]
}

export interface IntelligenceDiscovery {
  id: string
  profile: IntelligenceBusinessProfile
  keywords: string[]
  platforms: string[]
  search_plans: Array<{ platform: string; platform_label: string; keyword: string; search_url: string }>
  content_items: IntelligenceContentItem[]
  top_content?: IntelligenceContentItem[]
  candidates: IntelligenceCandidate[]
  summary?: IntelligenceReportSummary
  analysis?: IntelligenceAnalysis
  action_suggestions?: IntelligenceActionSuggestion[]
  knowledge_context?: Array<{ content: string; source: string; score?: number }>
  knowledge_sources?: string[]
  errors: Array<{ platform: string; keyword: string; message: string }>
  created_at: string
  updated_at: string
}

export interface IntelligenceReportSummary {
  headline: string
  content_count: number
  candidate_count: number
  platforms: Record<string, number>
  keywords: Record<string, number>
  error_count: number
  confidence: string
}

export interface IntelligenceActionSuggestion {
  id: string
  type: string
  priority: number
  title: string
  description: string
  reason: string
  source_item_ids: string[]
  source_urls: string[]
  created_at: string
}

export interface IntelligenceAnalysis {
  top_topics: Array<{
    topic: string
    count: number
    engagement: number
    top_title: string
    source_url: string
    avg_quality_score: number
  }>
  demand_signals: Array<{
    text: string
    source_title: string
    source_url: string
    platform: string
    platform_label: string
  }>
  account_opportunities: Array<{
    name: string
    platform: string
    platform_label: string
    profile_url: string
    evidence_url: string
    matched_items: number
    followers?: number | null
    reason: string
  }>
  content_angles: Array<{
    title: string
    description: string
    source_url: string
    platform_label: string
    priority: number
  }>
}

export interface IntelligenceMonitoringDigest {
  account_count: number
  accounts_with_updates: number
  recent_item_count: number
  account_updates: Array<{
    account_id: string
    name: string
    platform: string
    platform_label: string
    profile_url: string
    followers?: number | null
    recent_count: number
    last_sync_at: string
  }>
  top_recent_items: Array<{
    id?: string
    title: string
    url: string
    account_name: string
    platform: string
    platform_label: string
    plays?: number
    likes?: number
    comments_count?: number
    favorites?: number
    coins?: number
    danmaku?: number
    engagement?: number
    published_at?: string
  }>
  latest_items: Array<Record<string, unknown>>
}

export interface IntelligenceDailyReport {
  discovery_id?: string
  summary: IntelligenceReportSummary
  analysis?: IntelligenceAnalysis
  monitoring?: IntelligenceMonitoringDigest
  action_suggestions: IntelligenceActionSuggestion[]
  top_content: IntelligenceContentItem[]
  visualization?: IntelligenceVisualization
  market_signals?: IntelligenceMarketSignal[]
  knowledge_sources?: string[]
  updated_at: string
}

export interface IntelligenceMarketSignal {
  id: string
  type: 'breakout' | 'demand' | 'competitor_update' | string
  level: 'high' | 'medium' | 'info' | string
  title: string
  summary: string
  platform: string
  platform_label: string
  source_url: string
  source_name: string
  observed_at: string
  score: number
}

export interface IntelligenceVisualization {
  platform_distribution: Array<{ platform: string; label: string; count: number }>
  topic_engagement: Array<{ topic: string; engagement: number; count: number; quality: number }>
  collection_timeline: Array<{ date: string; content: number; competitors: number }>
  account_growth: Array<{
    entity_id: string
    name: string
    platform: string
    followers?: number | null
    growth?: number | null
    points: Array<{ time: string; followers?: number | null }>
  }>
  data_sources: Array<{
    name: string
    method: string
    count: number
    quality: string
    last_collected_at: string
  }>
  breakouts: IntelligenceContentItem[]
  sample_size: number
  updated_at: string
}

export interface IntelligenceInformationSource {
  id: string
  name: string
  url: string
  keywords: string[]
  enabled: boolean
  status: 'pending' | 'success' | 'failed' | string
  last_sync_at: string
  last_error: string
  item_count: number
  created_at: string
  updated_at: string
}

export interface IntelligenceMarketNewsItem {
  id: string
  title: string
  summary: string
  source_url: string
  source_id: string
  source_name: string
  collection_method: string
  data_quality: string
  published_at: string
  collected_at: string
  relevance_score: number
  matched_keywords: string[]
}

export interface IntelligenceContentBrief {
  id: string
  discovery_id?: string
  title: string
  objective: string
  platform_suggestion: string[]
  outline: string[]
  reference_topic?: string
  reference_content?: string
  demand_signals: Array<Record<string, unknown>>
  source_urls: string[]
  notes?: string
  status: string
  created_at: string
  updated_at: string
}

export interface IntelligenceQueryReport {
  id: string
  query: string
  title: string
  status: string
  plan: {
    intent: string
    focus: string
    search_keywords: string[]
    exclude_topics: string[]
    platforms: string[]
    time_range: string
  }
  executive_summary: Array<{
    title: string
    finding: string
    why_it_matters: string
    confidence: string
  }>
  word_cloud: Array<{ text: string; weight: number }>
  topic_trends: Array<{ topic: string; count: number; engagement: number; score: number }>
  platform_distribution: Array<{ name: string; value: number }>
  customer_voice: Array<{ theme: string; type: string; summary: string; count: number }>
  content_patterns: Array<{ pattern: string; finding: string; recommendation: string }>
  industry_moves: Array<{ title: string; summary: string; impact: string }>
  market_gap: Array<{
    topic: string
    market_score: number
    enterprise_coverage: number
    gap: number
    recommendation: string
  }>
  actions: Array<{ title: string; description: string; priority: string | number }>
  evidence: Array<{
    id: string
    title: string
    summary: string
    source: string
    source_url: string
    relation_type: string
    marketing_value: number
    reason: string
    metrics: { plays: number; likes: number; comments: number; favorites: number }
  }>
  data_scope: {
    raw_samples: number
    relevant_samples: number
    filtered_samples: number
    platforms: string[]
    knowledge_sources: string[]
    published_records: number
    use_enterprise_context: boolean
    confidence: string
    semantic_model_used: boolean
    narrative_model_used: boolean
    source_health: Array<{
      source: string
      label: string
      source_type: string
      method: string
      status: 'success' | 'partial' | 'no_data' | 'needs_login' | 'restricted' | 'timeout' | 'unavailable' | 'failed'
      item_count: number
      attempted_queries: number
      successful_queries: number
      duration_ms: number
      error_code: string
      message: string
    }>
  }
  created_at: string
  updated_at: string
}

export interface IntelligenceDiscoverPayload {
  product_name: string
  industry?: string
  audience?: string
  region?: string
  goals?: string[]
  selling_points?: string[]
  seed_keywords?: string[]
  platforms?: string[]
  use_knowledge_base?: boolean
  knowledge_query?: string
  max_keywords?: number
  per_keyword_limit?: number
}

export async function fetchIntelligenceOverview(): Promise<IntelligenceOverview> {
  const data = await apiGet<{ overview: IntelligenceOverview }>('/api/intelligence/overview')
  return data.overview
}

export async function fetchBusinessProfiles(): Promise<{ items: IntelligenceBusinessProfile[]; total: number }> {
  return apiGet('/api/intelligence/business-profiles')
}

export async function discoverIntelligence(payload: IntelligenceDiscoverPayload): Promise<{ discovery: IntelligenceDiscovery }> {
  return apiPost('/api/intelligence/discover', payload)
}

export async function fetchDiscoveries(limit = 5): Promise<{ items: IntelligenceDiscovery[]; total: number }> {
  return apiGet(`/api/intelligence/discoveries?limit=${limit}`)
}

export async function fetchIntelligenceDailyReport(): Promise<IntelligenceDailyReport> {
  const data = await apiGet<{ report: IntelligenceDailyReport }>('/api/intelligence/reports/daily')
  return data.report
}

export async function fetchIntelligenceSources(): Promise<{ items: IntelligenceInformationSource[]; total: number }> {
  return apiGet('/api/intelligence/sources')
}

export async function createIntelligenceSource(payload: {
  name?: string
  url: string
  keywords?: string[]
}): Promise<{ item: IntelligenceInformationSource }> {
  return apiPost('/api/intelligence/sources', payload)
}

export async function updateIntelligenceSource(
  sourceId: string,
  payload: Partial<Pick<IntelligenceInformationSource, 'name' | 'url' | 'keywords' | 'enabled'>>,
): Promise<{ item: IntelligenceInformationSource }> {
  return apiPut(`/api/intelligence/sources/${encodeURIComponent(sourceId)}`, payload)
}

export async function deleteIntelligenceSource(sourceId: string): Promise<{ ok: boolean }> {
  return apiDel(`/api/intelligence/sources/${encodeURIComponent(sourceId)}`)
}

export async function fetchMarketNews(limit = 50): Promise<{ items: IntelligenceMarketNewsItem[]; total: number }> {
  return apiGet(`/api/intelligence/market-news?limit=${limit}`)
}

export async function collectMarketNews(payload: {
  profile_id?: string
  include_auto_search?: boolean
} = {}): Promise<{
  items: IntelligenceMarketNewsItem[]
  total: number
  keywords: string[]
  knowledge_sources: string[]
  updated_at: string
}> {
  return apiPost('/api/intelligence/market-news/collect', payload)
}

export async function fetchIntelligenceBriefs(limit = 5): Promise<{ items: IntelligenceContentBrief[]; total: number }> {
  return apiGet(`/api/intelligence/briefs?limit=${limit}`)
}

export async function runIntelligenceQuery(payload: {
  query: string
  use_enterprise_context?: boolean
  include_publish_records?: boolean
}): Promise<{ report: IntelligenceQueryReport }> {
  return apiPost('/api/intelligence/query', payload)
}

export async function fetchIntelligenceQueryReports(limit = 20): Promise<{ items: IntelligenceQueryReport[]; total: number }> {
  return apiGet(`/api/intelligence/query-reports?limit=${limit}`)
}

export async function fetchIntelligenceQueryReport(reportId: string): Promise<{ report: IntelligenceQueryReport }> {
  return apiGet(`/api/intelligence/query-reports/${encodeURIComponent(reportId)}`)
}

export async function createIntelligenceBrief(payload: { angle_index?: number; title?: string; notes?: string; source?: string; source_url?: string } = {}): Promise<{ brief: IntelligenceContentBrief }> {
  return apiPost('/api/intelligence/briefs', payload)
}

export async function acceptDiscoveryCandidate(discoveryId: string, candidateId: string): Promise<{ item: CompetitorAccount }> {
  return apiPost(`/api/intelligence/discoveries/${encodeURIComponent(discoveryId)}/accept`, { candidate_id: candidateId })
}

export async function fetchCompetitors(params: { platform?: string; keyword?: string } = {}): Promise<{
  items: CompetitorAccount[]
  total: number
}> {
  const query = new URLSearchParams()
  if (params.platform) query.set('platform', params.platform)
  if (params.keyword) query.set('keyword', params.keyword)
  return apiGet(`/api/intelligence/competitors${query.toString() ? `?${query.toString()}` : ''}`)
}

export async function createCompetitor(payload: {
  profile_url: string
  platform?: string
  name?: string
  tags?: string[]
}): Promise<{ item: CompetitorAccount }> {
  return apiPost('/api/intelligence/competitors', payload)
}

export async function syncCompetitor(competitorId: string): Promise<{ item: CompetitorAccount }> {
  return apiPost(`/api/intelligence/competitors/${encodeURIComponent(competitorId)}/sync`)
}

export async function syncCompetitors(params: { platform?: string; limit?: number } = {}): Promise<{
  items: CompetitorAccount[]
  total: number
}> {
  const query = new URLSearchParams()
  if (params.platform) query.set('platform', params.platform)
  if (params.limit) query.set('limit', String(params.limit))
  return apiPost(`/api/intelligence/competitors/sync-all${query.toString() ? `?${query.toString()}` : ''}`)
}

export async function deleteCompetitor(competitorId: string): Promise<{ ok: boolean }> {
  return apiDel(`/api/intelligence/competitors/${encodeURIComponent(competitorId)}`)
}

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

export interface AdoptMaterialResult {
  ok: boolean
  material: Record<string, unknown>
  existed: boolean
}

export async function adoptMaterial(payload: {
  path?: string
  url?: string
  name?: string
  tags?: string[]
  source?: string
}): Promise<AdoptMaterialResult> {
  return apiPost<AdoptMaterialResult>('/api/publisher/materials/adopt', payload)
}

export async function unadoptMaterial(payload: {
  path?: string
  url?: string
  material_id?: string
}): Promise<{ ok: boolean; removed: number; path: string }> {
  return apiPost<{ ok: boolean; removed: number; path: string }>('/api/publisher/materials/unadopt', payload)
}

export type GenerationHistoryType = 'image' | 'video' | 'audio' | 'text'

export interface GenerationHistoryItem {
  id: string
  type: GenerationHistoryType
  title: string
  prompt: string
  summary: string
  url: string
  path: string
  filename: string
  size: number
  created_at: string
  updated_at?: string
  adopted: boolean
  material_id?: string
  meta?: Record<string, unknown>
}

export async function fetchGenerationHistory(kind?: GenerationHistoryType): Promise<{
  items: GenerationHistoryItem[]
  total: number
  limits: Record<string, number>
}> {
  return apiGet(`/api/publisher/generation-history${kind ? `?kind=${encodeURIComponent(kind)}` : ''}`)
}

export async function recordGenerationHistory(payload: {
  type: GenerationHistoryType
  path?: string
  url?: string
  title?: string
  prompt?: string
  summary?: string
  meta?: Record<string, unknown>
}): Promise<{ ok: boolean; item: GenerationHistoryItem; limits: Record<string, number> }> {
  return apiPost('/api/publisher/generation-history', payload)
}

export interface VideoCreateResult {
  ok: boolean
  task_id: string
  tasks?: Array<{
    task_id: string
    status: string
    model: string
    prompt: string
    duration: number
    size: string
    ratio: string
  }>
  status: string
  model: string
  prompt: string
  final_prompt?: string
  duration?: number
  size?: string
  ratio?: string
  count?: number
  unsupported_features?: string[]
}

export interface VideoTaskResult {
  status: string
  video_url?: string
  download_url?: string
  local_path?: string
  progress?: number
  error?: string
}

export interface VideoPromptOptimizeResult {
  final_prompt: string
  negative_prompt: string
  audio_prompt: string
  summary: string
  optimized_by: string
}

export interface VideoStoryboardShot {
  id: string
  title: string
  duration: number
  scene: string
  camera: string
  shot_size: string
  narration: string
  audio: string
  prompt: string
}

export interface VideoStoryboardCharacterLock {
  enabled: boolean
  character_name: string
  identity: string
  age_range: string
  gender: string
  appearance: string
  hairstyle: string
  outfit: string
  temperament: string
  consistency_prompt: string
}

export interface VideoStoryboardResult {
  character_lock: VideoStoryboardCharacterLock[]
  shots: VideoStoryboardShot[]
  final_prompt: string
  summary: string
  generated_by: string
}

export async function optimizeVideoPrompt(payload: {
  prompt: string
  duration: number
  ratio: string
  native_audio: boolean
  model?: string
  style?: string
}): Promise<VideoPromptOptimizeResult> {
  return apiPost<VideoPromptOptimizeResult>('/api/video/optimize-prompt', payload)
}

export async function createVideoStoryboard(payload: {
  prompt: string
  duration: number
  ratio: string
  native_audio: boolean
  model?: string
  shot_count?: number
}): Promise<VideoStoryboardResult> {
  return apiPost<VideoStoryboardResult>('/api/video/storyboard', payload)
}

export async function createVideo(prompt: string, opts?: {
  duration?: number
  size?: string
  ratio?: string
  count?: number
  native_audio?: boolean
  prompt_optimize?: boolean
  final_prompt?: string
  model?: string
  image_url?: string
}): Promise<VideoCreateResult> {
  return apiPost<VideoCreateResult>('/api/video/create', {
    prompt,
    duration: opts?.duration ?? 6,
    size: opts?.size ?? '720p',
    ratio: opts?.ratio ?? '9:16',
    count: opts?.count ?? 1,
    native_audio: opts?.native_audio ?? false,
    prompt_optimize: opts?.prompt_optimize ?? true,
    final_prompt: opts?.final_prompt ?? '',
    model: opts?.model ?? 'doubao-seedance-2.0-fast',
    image_url: opts?.image_url ?? '',
  })
}

export async function pollVideoTask(taskId: string, model = 'doubao-seedance-2.0-fast'): Promise<VideoTaskResult> {
  return apiGet<VideoTaskResult>(`/api/video/task/${taskId}?model=${encodeURIComponent(model)}`)
}

export type DigitalHumanAssetRole =
  | 'avatar_reference'
  | 'product_reference'
  | 'background_reference'
  | 'motion_reference'
  | 'voice_reference'
  | 'brand_asset'

export interface DigitalHumanAsset {
  id: string
  name: string
  alias?: string
  role: DigitalHumanAssetRole
  kind: 'image' | 'video' | 'audio'
  content_type: string
  size: number
  path: string
  url: string
}

export interface DigitalHumanConfig {
  ok: boolean
  provider: string
  model_label: string
  configured: boolean
  configuration_message: string
  durations: number[]
  sizes: Array<'720p' | '1080p' | '4K'>
  ratios: Array<'9:16' | '16:9' | '1:1'>
  max_assets: number
  max_inline_asset_mb: number
  native_audio: boolean
}

export interface DigitalHumanCreateResult {
  ok: boolean
  task_id: string
  status: string
  model: string
  model_label: string
  prompt: string
  asset_ids: string[]
}

export async function fetchDigitalHumanConfig(): Promise<DigitalHumanConfig> {
  return apiGet<DigitalHumanConfig>('/api/digital-human/config')
}

export async function uploadDigitalHumanAsset(file: File, role: DigitalHumanAssetRole): Promise<DigitalHumanAsset> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('role', role)
  const send = async (retry = false): Promise<DigitalHumanAsset> => {
    const token = getToken()
    const res = await fetch('/api/digital-human/assets', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: formData,
    })
    if (res.status === 401 && !retry && await autoLogin()) return send(true)
    if (!res.ok) {
      const data = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(data.detail || `素材上传失败：${res.status}`)
    }
    const data = await res.json() as { asset: DigitalHumanAsset }
    return data.asset
  }
  return send()
}

export async function removeDigitalHumanAsset(assetId: string): Promise<void> {
  await apiDel(`/api/digital-human/assets/${encodeURIComponent(assetId)}`)
}

export async function createDigitalHumanVideo(payload: {
  script: string
  asset_ids: string[]
  asset_aliases: Record<string, string>
  duration: number
  size: '720p' | '1080p' | '4K'
  ratio: '9:16' | '16:9' | '1:1'
  native_audio: boolean
  style: string
  avatar_position: 'center' | 'left' | 'right' | 'full'
  background_prompt: string
}): Promise<DigitalHumanCreateResult> {
  return apiPost<DigitalHumanCreateResult>('/api/digital-human/create', payload)
}

export interface ComposeAssetRef {
  id: string
  name: string
  type: 'image' | 'video' | 'audio' | 'text'
  url?: string
  path?: string
}

export interface ComposeQuestion {
  id: string
  question: string
  type: string
  options: Array<{ label: string; value: string }>
  recommended?: string
}

export interface ComposeAssetAnalysis {
  id: string
  name: string
  type: 'image' | 'video' | 'audio' | 'text'
  role: string
  summary: string
  status: string
  provider_ref?: string
  provider_type?: string
  error?: string
}

export interface ComposeAnalyzeResult {
  ok: boolean
  model: string
  assets: ComposeAssetAnalysis[]
  questions: ComposeQuestion[]
  summary: string
  warnings: string[]
}

export interface ComposeVideoParams {
  platform: string
  scenario: string
  duration: number
  size: string
  ratio: string
  native_audio: boolean
  count: number
  user_instruction?: string
  model: string
}

export interface VideoModelConfig {
  id: string
  provider_model?: string
  label: string
  available?: boolean
  sizes: string[]
  min_duration: number
  max_duration: number
  native_audio: boolean
}

export interface VideoConfigResult {
  ok: boolean
  default_model: string
  compose_default_model: string
  defaults: {
    duration: number
    size: string
    ratio: string
    native_audio: boolean
    count: number
  }
  models: VideoModelConfig[]
}

export async function getVideoConfig(): Promise<VideoConfigResult> {
  return apiGet<VideoConfigResult>('/api/video/config')
}

export interface ComposePrepareResult {
  ok: boolean
  storyboard: VideoStoryboardShot[]
  final_prompt: string
  used_assets: ComposeAssetAnalysis[]
  unsupported_features: string[]
  warnings: string[]
  summary: string
}

export interface ComposeCreateResult extends VideoCreateResult {
  used_assets?: ComposeAssetAnalysis[]
  unsupported_features?: string[]
}

export async function analyzeVideoComposition(assets: ComposeAssetRef[]): Promise<ComposeAnalyzeResult> {
  return apiPost<ComposeAnalyzeResult>('/api/video/compose/analyze', { assets })
}

export async function prepareVideoComposition(payload: {
  analysis: ComposeAnalyzeResult
  answers: Array<{ question_id: string; answer: string }>
  params: ComposeVideoParams
}): Promise<ComposePrepareResult> {
  return apiPost<ComposePrepareResult>('/api/video/compose/prepare', payload)
}

export async function createVideoComposition(payload: {
  prepared: ComposePrepareResult
  params: ComposeVideoParams
}): Promise<ComposeCreateResult> {
  return apiPost<ComposeCreateResult>('/api/video/compose/create', payload)
}

export interface GraphicAnalyzeResult {
  ok: boolean
  model: string
  assets: ComposeAssetAnalysis[]
  questions: ComposeQuestion[]
  summary: string
  warnings: string[]
}

export interface GraphicDraft {
  title: string
  body: string
  tags: string[]
  platform_suggestion: string[]
  image_order: string[]
  image_anchors?: Array<{
    asset_id: string
    anchor_after_paragraph: number
    caption?: string
  }>
  material_summary: string
  publish_notes: string
}

export interface GraphicPrepareResult {
  ok: boolean
  draft: GraphicDraft
  used_assets: ComposeAssetAnalysis[]
  warnings: string[]
  summary: string
}

export interface GraphicSaveResult {
  ok: boolean
  id: string
  name: string
  type: string
  url: string
  path: string
  size: number
  created_at: string
  source: string
}

export async function analyzeGraphicComposition(assets: ComposeAssetRef[], userInstruction = ''): Promise<GraphicAnalyzeResult> {
  return apiPost<GraphicAnalyzeResult>('/api/content/graphic/analyze', { assets, user_instruction: userInstruction })
}

export async function prepareGraphicComposition(payload: {
  analysis: GraphicAnalyzeResult
  answers: Array<{ question_id: string; answer: string }>
  user_instruction?: string
}): Promise<GraphicPrepareResult> {
  return apiPost<GraphicPrepareResult>('/api/content/graphic/prepare', payload)
}

export async function saveGraphicComposition(payload: {
  draft: GraphicDraft
  used_assets: ComposeAssetAnalysis[]
  filename?: string
}): Promise<GraphicSaveResult> {
  return apiPost<GraphicSaveResult>('/api/content/graphic/save', payload)
}

export interface CopyGenerateResult {
  ok: boolean
  copies: string[]
  char_counts?: number[]
  within_range?: boolean[]
  raw_text?: string
}

export async function generateCopy(payload: {
  prompt: string
  copy_type: string
  count: number
  min_words: number
  max_words: number
}): Promise<CopyGenerateResult> {
  return apiPost<CopyGenerateResult>('/api/content/copy/generate', payload)
}

export interface TtsVoice {
  id: string
  name: string
  provider_voice: string
  gender: string
  tags: string[]
  scene: string
  description: string
  demo_text: string
}

export interface TtsResult {
  ok: boolean
  url: string
  path: string
  filename: string
  voice: string
  emotion: string
  speed: number
  pitch: number
  preview: boolean
  estimated_duration: number
}

export interface InterpretVoiceResult {
  voice: string
  emotion: string
  speed: number
  pitch: number
  summary: string
  interpreted_by: string
}

export interface TtsPayload {
  text: string
  voice: string
  voice_prompt?: string
  scene?: string
  emotion?: string
  speed?: number
  pitch?: number
  format?: 'mp3'
  preview?: boolean
}

export async function fetchTtsVoices(): Promise<{ voices: TtsVoice[] }> {
  return apiGet<{ voices: TtsVoice[] }>('/api/tts/voices')
}

export async function previewTts(payload: TtsPayload): Promise<TtsResult> {
  return apiPost<TtsResult>('/api/tts/preview', payload)
}

export async function synthesizeTts(payload: TtsPayload): Promise<TtsResult> {
  return apiPost<TtsResult>('/api/tts/synthesize', payload)
}

export async function interpretVoicePrompt(payload: {
  voice_prompt: string
  voice: string
  scene: string
  emotion: string
  speed: number
  pitch: number
}): Promise<InterpretVoiceResult> {
  return apiPost<InterpretVoiceResult>('/api/tts/interpret-voice', payload)
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
  updated_at?: string
}

export async function saveGeneratedDocument(title: string, content: string, extension = 'md'): Promise<SaveDocumentResult> {
  return apiPost<SaveDocumentResult>('/api/media/documents/save', { title, content, extension })
}

export async function updateGeneratedDocument(asset: { path?: string; url?: string; content: string }): Promise<SaveDocumentResult> {
  return apiPost<SaveDocumentResult>('/api/media/documents/update', asset)
}

export async function openGeneratedMedia(asset: { path?: string; url?: string }): Promise<{ ok: boolean; path: string }> {
  return apiPost<{ ok: boolean; path: string }>('/api/media/files/open', asset)
}

export async function revealGeneratedMedia(asset: { path?: string; url?: string }): Promise<{ ok: boolean; path: string; directory: string }> {
  return apiPost<{ ok: boolean; path: string; directory: string }>('/api/media/files/reveal', asset)
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
  session_id?: string
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

export interface ChannelAccount {
  id: string
  platform: string
  platform_label?: string
  label: string
  nickname?: string
  avatar_url?: string
  profile_url?: string
  platform_user_id?: string
  followers?: number
  following?: number
  works_count?: number
  likes_count?: number
  sync_status?: string
  sync_message?: string
  last_profile_sync_at?: string
  status: string
  session_path: string
  sau_account_name?: string
  created_at: string
  updated_at?: string
  last_login_at?: string
  last_publish_at?: string
  enabled?: boolean
  is_default?: boolean
  session: PlatformInfo['session'] & { path?: string }
}

export interface PlatformAccountsResponse {
  ok: boolean
  accounts: ChannelAccount[]
  total: number
  limits: {
    per_platform: number
    total: number
  }
}

export interface PublishingProfile {
  id: string
  name: string
  description?: string
  account_ids: string[]
  accounts?: ChannelAccount[]
  created_at: string
  updated_at: string
}

export interface PublishingProfilesResponse {
  ok: boolean
  profiles: PublishingProfile[]
}

export async function fetchPlatforms(): Promise<PlatformListResponse> {
  return apiGet<PlatformListResponse>('/api/platforms')
}

export async function fetchPlatformAccounts(platform = ''): Promise<PlatformAccountsResponse> {
  const query = platform ? `?platform=${encodeURIComponent(platform)}` : ''
  return apiGet<PlatformAccountsResponse>(`/api/platform-accounts${query}`)
}

export async function createPlatformAccount(payload: { platform: string; label?: string }): Promise<{ ok: boolean; account: ChannelAccount }> {
  return apiPost('/api/platform-accounts', payload)
}

export async function loginPlatformAccount(accountId: string, timeout = 900): Promise<{ ok: boolean; account: ChannelAccount; message: string; result: Record<string, unknown> }> {
  return apiPost(`/api/platform-accounts/${encodeURIComponent(accountId)}/login?timeout=${timeout}`)
}

export interface OpenPlatformAccountPublishPayload {
  title?: string
  desc?: string
  tags?: string[]
  file_path?: string
  asset_paths?: string[]
  mode?: 'video' | 'note' | string
  auto_publish?: boolean
}

export async function openPlatformAccountPublish(
  accountId: string,
  payload: OpenPlatformAccountPublishPayload = {},
): Promise<{ ok: boolean; account: ChannelAccount; url: string; message: string; task_id?: string; execution_id?: string; run?: ExecutionRun }> {
  return apiPost(`/api/platform-accounts/${encodeURIComponent(accountId)}/open-publish`, payload)
}

export async function syncPlatformAccountProfile(accountId: string): Promise<{ ok: boolean; account: ChannelAccount; message: string }> {
  return apiPost(`/api/platform-accounts/${encodeURIComponent(accountId)}/sync-profile`)
}

export async function deletePlatformAccountSession(accountId: string): Promise<{ ok: boolean; account: ChannelAccount }> {
  return apiDel(`/api/platform-accounts/${encodeURIComponent(accountId)}/session`)
}

export interface WechatDesktopOpenResult {
  ok: boolean
  focused?: boolean
  message: string
  user_prompt: string
  window?: Record<string, unknown>
  safe_actions?: Record<string, boolean>
}

export async function openWechatDesktop(): Promise<WechatDesktopOpenResult> {
  return apiPost<WechatDesktopOpenResult>('/api/wechat/desktop/open')
}

export interface WechatDesktopCaptureResult {
  ok: boolean
  message: string
  calibration: Record<string, unknown>
  validation: Record<string, unknown>
  account?: ChannelAccount | null
  click?: { x: number; y: number }
  window?: Record<string, unknown>
  safe_actions?: Record<string, boolean>
}

export async function captureWechatInputClick(timeoutSeconds = 15, accountId = ''): Promise<WechatDesktopCaptureResult> {
  const query = new URLSearchParams({ timeout_seconds: String(timeoutSeconds) })
  if (accountId) query.set('account_id', accountId)
  return apiPost<WechatDesktopCaptureResult>(`/api/wechat/desktop/capture-input-click?${query.toString()}`)
}

export async function fetchPublishingProfiles(): Promise<PublishingProfilesResponse> {
  return apiGet('/api/publishing-profiles')
}

export async function createPublishingProfile(payload: { name: string; account_ids: string[]; description?: string }): Promise<{ ok: boolean; profile: PublishingProfile }> {
  return apiPost('/api/publishing-profiles', payload)
}

export async function updatePublishingProfile(profileId: string, payload: { name: string; account_ids: string[]; description?: string }): Promise<{ ok: boolean; profile: PublishingProfile }> {
  return apiPut(`/api/publishing-profiles/${encodeURIComponent(profileId)}`, payload)
}

export async function deletePublishingProfile(profileId: string): Promise<{ ok: boolean; profile_id: string }> {
  return apiDel(`/api/publishing-profiles/${encodeURIComponent(profileId)}`)
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

export async function triggerPlatformLogin(platform: string, timeout = 900): Promise<LoginTriggerResponse> {
  return apiPost<LoginTriggerResponse>(`/api/platforms/${platform}/login?timeout=${timeout}`)
}

export interface SauTask {
  id: string
  execution_id?: string
  kind: string
  platform: string
  account_id?: string
  account_label?: string
  profile_id?: string
  batch_id?: string
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
  batch_id?: string
  execution_ids?: string[]
  tasks?: SauTask[]
  runs?: ExecutionRun[]
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
  account_id?: string
  target_account_ids?: string[]
  profile_id?: string
}

export interface CreateSauNotePayload {
  platform: string
  image_paths: string[]
  title: string
  note?: string
  tags?: string[]
  schedule?: string
  headless?: boolean
  account_id?: string
  target_account_ids?: string[]
  profile_id?: string
}

export async function createSauVideoTask(payload: CreateSauVideoPayload): Promise<SauCreateResponse> {
  return apiPost<SauCreateResponse>('/api/sau/upload-video-async', payload)
}

export async function createSauNoteTask(payload: CreateSauNotePayload): Promise<SauCreateResponse> {
  return apiPost<SauCreateResponse>('/api/sau/upload-note-async', payload)
}

export interface GeneratePublishTitlePayload {
  platform: string
  kind?: 'note' | 'video'
  content?: string
  current_title?: string
  tags?: string[]
}

export interface GeneratePublishTitleResponse {
  ok: boolean
  title: string
  candidates: string[]
  limit: number
  platform: string
  kind: string
  model: string
  reason?: string
}

export async function generatePublishTitle(payload: GeneratePublishTitlePayload): Promise<GeneratePublishTitleResponse> {
  return apiPost<GeneratePublishTitleResponse>('/api/sau/generate-title', payload)
}

export interface GeneratePublishCopyPayload extends GeneratePublishTitlePayload {
  assets?: ComposeAssetRef[]
  current_body?: string
}

export interface GeneratePublishCopyResponse extends GeneratePublishTitleResponse {
  body: string
  tags: string[]
  image_anchors?: Array<{
    asset_id: string
    anchor_after_paragraph: number
    caption?: string
  }>
  visual_model?: string
  visual_summary?: string
  asset_summaries?: Array<{ id?: string; role?: string; summary?: string }>
}

export async function generatePublishCopy(payload: GeneratePublishCopyPayload): Promise<GeneratePublishCopyResponse> {
  return apiPost<GeneratePublishCopyResponse>('/api/sau/generate-publish-copy', payload)
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
  account_id?: string
  account_label?: string
  profile_id?: string
  batch_id?: string
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
  archived?: boolean
}

export interface ExecutionArchiveInfo {
  active_publish_records: number
  archived_publish_records: number
  active_limit: number
  archive_limit: number
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

export interface FetchExecutionsOptions {
  limit?: number
  status?: string
  platform?: string
  task_type?: string
  keyword?: string
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  include_archived?: boolean
}

export async function fetchExecutions(options: number | FetchExecutionsOptions = 100): Promise<{ runs: ExecutionRun[]; archive?: ExecutionArchiveInfo }> {
  const params = new URLSearchParams()
  if (typeof options === 'number') {
    params.set('limit', String(options))
  } else {
    params.set('limit', String(options.limit ?? 100))
    Object.entries(options).forEach(([key, value]) => {
      if (key === 'limit') return
      if (value === undefined || value === null || value === '') return
      params.set(key, String(value))
    })
  }
  return apiGet<{ runs: ExecutionRun[]; archive?: ExecutionArchiveInfo }>(`/api/executions?${params.toString()}`)
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

// ── 电脑使用 API ──────────────────────────────────────────────

export interface ComputerUseHealth {
  ok: boolean
  backend: string
  available: boolean
  windows_only: boolean
  platform: string
  terminator: {
    available: boolean
    command: boolean
    npx: boolean
    node: boolean
    python_package: boolean
  }
  vision_fallback: {
    enabled: boolean
    backend: string
  }
  providers?: ComputerUseProviders
  message: string
}

export interface ComputerUseProviderStatus {
  available: boolean
  message?: string
  source_available?: boolean
  source_dir?: string
  url?: string
  python?: string
  python_available?: boolean
  weights_ready?: boolean
  missing_weights?: string[]
  service_ready?: boolean
  process_running?: boolean
}

export interface ComputerUseProviders {
  terminator?: ComputerUseProviderStatus
  playwright?: ComputerUseProviderStatus
  omniparser?: ComputerUseProviderStatus
  [key: string]: ComputerUseProviderStatus | undefined
}

export interface ComputerUseWindow {
  pid?: number
  process?: string
  title?: string
}

export interface ComputerUseElement {
  id?: string | number | null
  index?: string
  source?: string
  role?: string
  name?: string
  selector?: string
  bounds?: Record<string, unknown>
  confidence?: number
  actionable?: boolean
}

export interface ComputerUseObservation {
  ok: boolean
  health?: ComputerUseHealth
  providers?: ComputerUseProviders
  primary_provider?: string
  active_window?: ComputerUseWindow
  windows?: ComputerUseWindow[]
  screenshot?: {
    ok: boolean
    path: string
    message?: string
    created_at?: string
  }
  elements?: ComputerUseElement[]
  tree?: Record<string, unknown>
  formatted?: string
  element_count?: number
  source_counts?: Record<string, number>
  vision?: {
    ok: boolean
    message?: string
    element_count?: number
  }
  summary: string
  created_at: string
}

export interface ComputerUseStatus {
  ok: boolean
  health: ComputerUseHealth
  active_window: ComputerUseWindow
  windows: ComputerUseWindow[]
  providers?: ComputerUseProviders
  backend_version: string
  vision_fallback_enabled: boolean
}

export interface CreateComputerUseTaskPayload {
  instruction: string
  target_app?: string
  url?: string
  mode?: 'observe_only' | 'assisted' | 'execute'
  expected_result?: string
  target_selector?: string
  files?: string[]
  steps?: Array<{ action: string; target?: string; selector?: string; text?: string; file_path?: string; value?: string; url?: string; provider?: string }>
  max_steps?: number
  require_confirmation?: boolean
  allowed_actions?: string[]
  sensitive_policy?: string
  text?: string
}

export interface ComputerUseCreateResponse {
  ok: boolean
  task_id: string
  execution_id: string
  run: ExecutionRun
}

export async function fetchComputerUseStatus(): Promise<ComputerUseStatus> {
  return apiGet<ComputerUseStatus>('/api/computer-use/status')
}

export async function observeComputerUse(): Promise<ComputerUseObservation> {
  return apiPost<ComputerUseObservation>('/api/computer-use/observe')
}

export async function openComputerUseBrowser(url: string): Promise<ComputerUseObservation> {
  return apiPost<ComputerUseObservation>('/api/computer-use/browser/open', { url })
}

export async function fetchComputerUseTree(payload: {
  process?: string
  title?: string
  include_ocr?: boolean
  include_browser_dom?: boolean
  include_omniparser?: boolean
  include_gemini_vision?: boolean
} = {}): Promise<ComputerUseObservation> {
  return apiPost<ComputerUseObservation>('/api/computer-use/tree', payload)
}

export async function createComputerUseTask(payload: CreateComputerUseTaskPayload): Promise<ComputerUseCreateResponse> {
  return apiPost<ComputerUseCreateResponse>('/api/computer-use/tasks', payload)
}

export async function getComputerUseTask(taskId: string): Promise<ExecutionRun & {
  steps: ExecutionStep[]
  audit: AuditEvent[]
  observations: Observation[]
  debug_screenshot: string
}> {
  return apiGet(`/api/computer-use/tasks/${taskId}`)
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
  platforms?: AcquisitionPlatformStatus[]
}

export interface AcquisitionPlatformStatus {
  platform: string
  status: string
  error_code?: string
  message?: string
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
  decision?: string
  status?: string
  risk_codes?: string[]
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
  batch_id?: string
  platform?: string
  video_id?: string
  status?: string
  text?: string
  comment?: string
  comment_text?: string
  original_text?: string
  repaired_text?: string
  risk_codes?: string[]
  decision?: string
  repair_attempts?: number
  next_run_at?: string
  target_url?: string
  video_url?: string
  video_title?: string
  created_at?: string
  sent_at?: string
  updated_at?: string
  error?: string
  error_msg?: string
  metadata?: Record<string, unknown>
  platform_result?: Record<string, unknown>
  archived?: boolean
  archived_at?: string
  [key: string]: unknown
}

export interface CommentQueueResponse {
  items: CommentQueueItem[]
  total: number
  archive?: {
    total_items?: number
    total_batches?: number
    batch_limit?: number
    retention_days?: number
  }
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
  shared_across_targets?: boolean
}): Promise<GenerateCommentResponse> {
  return apiPost('/api/acquisition/comments/generate', payload)
}

export async function acquisitionDeAI(text: string, platform = 'douyin'): Promise<DeAIResponse> {
  return apiPost('/api/acquisition/comments/deai', { text, platform })
}

export async function acquisitionPreflight(text: string): Promise<PreflightResult> {
  return apiPost('/api/acquisition/comments/preflight', { text })
}

export async function acquisitionEnqueueComment(payload: {
  platform: string
  video_id?: string
  video_title?: string
  video_url?: string
  text: string
  strategy?: string
  deai?: boolean
  confirmed: boolean
}): Promise<{ ok: boolean; item: { id: string; execution_id: string; status: string } }> {
  return apiPost('/api/acquisition/comments/enqueue', payload)
}

export async function acquisitionEnqueueCommentBatch(payload: {
  targets: Array<{
    platform: string
    video_id?: string
    video_title?: string
    video_url?: string
  }>
  text: string
  strategy?: string
  deai?: boolean
  confirmed: boolean
}): Promise<{
  ok: boolean
  batch_id: string
  items: Array<{ id: string; execution_id: string; status: string; platform: string; video_title: string }>
}> {
  return apiPost('/api/acquisition/comments/enqueue-batch', payload)
}

export async function acquisitionCommentQueue(params?: { status?: string; platform?: string; archived?: boolean; limit?: number; offset?: number }): Promise<CommentQueueResponse> {
  const query = new URLSearchParams()
  if (params?.status) query.set('status', params.status)
  if (params?.platform) query.set('platform', params.platform)
  if (params?.archived) query.set('archived', 'true')
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

export interface PrivateDomainOverview {
  ok: boolean
  metrics: {
    pending: number
    high_intent: number
    followed_today: number
    overdue: number
  }
  wechat: {
    state: 'not_connected' | 'connected' | 'calibrated' | string
    connected: boolean
    calibrated: boolean
    label: string
    window?: Record<string, unknown>
    calibration?: Record<string, unknown>
    validation?: Record<string, unknown>
  }
}

export interface PrivateDomainQueueResponse {
  ok: boolean
  items: LeadItem[]
  total: number
}

export async function privateDomainOverview(): Promise<PrivateDomainOverview> {
  return apiGet('/api/private-domain/overview')
}

export async function privateDomainQueue(limit = 50): Promise<PrivateDomainQueueResponse> {
  return apiGet(`/api/private-domain/queue?limit=${encodeURIComponent(String(limit))}`)
}

export async function privateDomainCreateFollowup(payload: {
  lead_id?: string
  customer_id?: string
  customer_name?: string
  platform?: string
  action?: string
  reply_text?: string
  next_reminder_at?: string
  notes?: string
}): Promise<{ ok: boolean; followup: Record<string, unknown> }> {
  return apiPost('/api/private-domain/followups', payload)
}

export async function privateDomainCreateWechatDraft(payload: {
  lead_id?: string
  customer_id?: string
  customer_name?: string
  message: string
  source?: string
}): Promise<{ ok: boolean; draft: MessageItem; message: string; wechat: PrivateDomainOverview['wechat'] }> {
  return apiPost('/api/private-domain/wechat/draft', payload)
}

// ── 本地小模型 API ──────────────────────────────────────────────

export interface LocalLlmModelStatus {
  id: string
  label: string
  installed: boolean
  valid: boolean
  bundled: boolean
  required: boolean
  path: string
  size_bytes: number
}

export interface LocalLlmStatus {
  ok: boolean
  enabled: boolean
  base_url: string
  runtime_ready: boolean
  current_model: string
  server: {
    available: boolean
    path: string
    backend?: string
    selection_mode?: string
    process_running: boolean
    pid?: number | null
    log_path: string
  }
  runtimes?: Record<string, {
    backend: string
    available: boolean
    path: string
    root: string
  }>
  acceleration?: {
    mode: string
    selected_backend: string
    vulkan?: {
      available: boolean
      loader_exists: boolean
      loader_path: string
      gpus: Array<{ Name?: string; AdapterRAM?: number; DriverVersion?: string; VideoProcessor?: string }>
    }
  }
  models: Record<string, LocalLlmModelStatus>
  download: {
    running?: boolean
    status?: string
    model?: string
    received?: number
    total?: number
    percent?: number
    error?: string
  }
}

export async function fetchLocalLlmStatus(): Promise<LocalLlmStatus> {
  return apiGet<LocalLlmStatus>('/api/local-llm/status')
}

export async function startLocalLlm(model = 'qwen3-4b'): Promise<{ success: boolean; message: string; status?: LocalLlmStatus }> {
  return apiPost(`/api/local-llm/start?model=${encodeURIComponent(model)}`)
}

export async function stopLocalLlm(): Promise<{ success: boolean; message: string; status?: LocalLlmStatus }> {
  return apiPost('/api/local-llm/stop')
}

export async function chatLocalLlm(prompt: string): Promise<{ success: boolean; message: string; model?: string }> {
  return apiPost('/api/local-llm/chat', { prompt })
}

export async function downloadLocalLlm8b(): Promise<{ success: boolean; message: string }> {
  return apiPost('/api/local-llm/models/qwen3-8b/download')
}

export async function deleteLocalLlm8b(): Promise<{ success: boolean; message: string; status?: LocalLlmStatus }> {
  return apiDel('/api/local-llm/models/qwen3-8b')
}

export async function streamHermesChat(opts: StreamChatOpts): Promise<void> {
  const payload = {
    model: opts.model,
    messages: opts.messages,
    stream: true,
    agent_id: opts.agent_id,
    session_id: opts.session_id,
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
