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
  size?: string
  enhanced_prompt?: string
}

export async function generateImage(prompt: string, size = '1920x1920'): Promise<ImageGenResult> {
  return apiPost<ImageGenResult>('/api/image/generate', { prompt, size })
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
