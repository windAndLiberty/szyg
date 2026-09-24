import { autoLogin, getToken } from '@/lib/api'

export interface KnowledgeDocument {
  id: string
  filename: string
  extension: string
  mime_type: string
  size: number
  status: 'queued' | 'parsing' | 'normalizing' | 'indexing' | 'ready' | 'failed' | 'needs_human'
  progress: number
  stage: string
  error: string
  collection: string
  parser: string
  chunk_count: number
  job_id: string
  created_at: string
  updated_at: string
  source_available: boolean
  markdown_available: boolean
  markdown?: string
  duplicate?: boolean
}

export interface KnowledgeStats {
  total_docs: number
  total_chunks: number
  total_bytes: number
  processing: number
  last_update: string | null
  storage_dir: string
  supported_extensions: string[]
}

export interface KnowledgeResult {
  chunk_id: string
  document_id: string
  filename: string
  collection: string
  heading: string
  locator: string
  content: string
  score: number
}

async function request<T>(url: string, init: RequestInit = {}, retried = false): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(url, { ...init, headers, cache: 'no-store' })
  if (response.status === 401 && !retried && await autoLogin()) return request<T>(url, init, true)
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json()
      message = typeof payload.detail === 'string' ? payload.detail : message
    } catch { /* response is not JSON */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export async function listKnowledgeDocuments(filters: { q?: string; collection?: string; status?: string } = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value) })
  return request<{ items: KnowledgeDocument[] }>(`/api/knowledge/documents?${params}`)
}

export async function getKnowledgeDocument(id: string) {
  return request<KnowledgeDocument>(`/api/knowledge/documents/${encodeURIComponent(id)}`)
}

export async function getKnowledgeStats() {
  return request<KnowledgeStats>('/api/knowledge/stats')
}

export async function getKnowledgeCollections() {
  return request<{ items: Array<{ name: string; count: number }> }>('/api/knowledge/collections')
}

export async function uploadKnowledgeDocument(file: File, collection: string) {
  const body = new FormData()
  body.append('file', file)
  body.append('collection', collection)
  return request<KnowledgeDocument & { taskId?: string }>('/api/knowledge/documents', { method: 'POST', body })
}

export async function deleteKnowledgeDocument(id: string) {
  return request<{ ok: boolean }>(`/api/knowledge/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export async function reparseKnowledgeDocument(id: string) {
  return request<KnowledgeDocument>(`/api/knowledge/documents/${encodeURIComponent(id)}/reparse`, { method: 'POST' })
}

export async function testKnowledgeRetrieval(query: string, collection = '', topK = 5) {
  return request<{ results: KnowledgeResult[] }>('/api/knowledge/retrieval/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, collection, top_k: topK }),
  })
}

export function knowledgeSourceUrl(id: string) {
  return `/api/knowledge/documents/${encodeURIComponent(id)}/source`
}
