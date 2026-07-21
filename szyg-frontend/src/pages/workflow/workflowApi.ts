import { autoLogin, getToken } from '@/lib/api'

export type WorkflowInstanceStatus = 'draft' | 'active' | 'paused' | 'disabled'
export type WorkflowRunStatus = 'queued' | 'running' | 'success' | 'failed' | 'paused' | 'needs_human' | 'cancelled'

export interface WorkflowStep {
  id: string
  name: string
  description: string
  on_failure: 'stop' | 'retry' | 'skip' | 'needs_human'
  requires_confirmation: boolean
  skill_name?: string
  action_id?: string
  params?: Record<string, unknown>
  condition?: WorkflowCondition | null
  risk_level?: 'low' | 'medium' | 'high'
  confirmation_policy?: 'automatic' | 'every_run'
}

export interface WorkflowCondition {
  step_id: string
  field: string
  operator: 'equals' | 'not_equals' | 'contains' | 'gt' | 'lt' | 'empty' | 'not_empty'
  value?: unknown
}

export interface WorkflowCapability {
  skill_name: string
  action_id: string
  name: string
  description: string
  risk_level: 'low' | 'medium' | 'high'
  business_objects: string[]
  input_schema: Record<string, unknown>
  execution_mode: 'builtin' | 'manual'
}

export interface WorkflowDraft {
  id: string
  goal: string
  name: string
  description: string
  outcome: string
  status: 'draft' | 'active'
  context: { knowledge: boolean; accounts: boolean; leads: boolean; materials: boolean; publish_records: boolean }
  schedule: WorkflowSchedule
  notification: string
  steps: WorkflowStep[]
  validation: { valid: boolean; issues: string[]; warnings?: string[] }
  version: number
}

export interface WorkflowTemplate {
  id: string
  name: string
  category: string
  category_label: string
  description: string
  outcome: string
  icon: string
  risk_level: 'low' | 'medium' | 'high'
  estimated_minutes: number
  steps: WorkflowStep[]
  available: boolean
  config_schema: Record<string, unknown>
}

export interface WorkflowSchedule {
  type: 'manual' | 'daily' | 'weekly' | 'interval' | 'once'
  time?: string
  weekdays?: number[]
  interval_minutes?: number
  at?: string
  label?: string
}

export interface WorkflowInstance {
  id: string
  template_id: string
  template_name: string
  name: string
  description?: string
  status: WorkflowInstanceStatus
  schedule: WorkflowSchedule
  config: Record<string, unknown>
  human_policy: 'pause_on_risk' | 'always_confirm_external' | 'notify_only'
  created_at: string
  updated_at: string
  next_run_at?: string
  definition_id?: string
  definition_version?: number
  latest_definition_version?: number
  upgrade_available?: boolean
  last_run?: WorkflowRun
}

export interface WorkflowRun {
  id: string
  instance_id: string
  instance_name: string
  template_id: string
  status: WorkflowRunStatus
  current_step_id?: string
  result?: Record<string, unknown>
  error_code?: string
  error_message?: string
  created_at: string
  started_at?: string
  finished_at?: string
  duration_ms?: number
}

export interface WorkflowSop {
  id: string
  name: string
  description: string
  category: string
  category_label: string
  source: 'builtin' | 'custom'
  template_id?: string
  outcome?: string
  version?: number
  versions?: Array<{ version: number; saved_at: string; name?: string; description?: string }>
  available?: boolean
  enabled: boolean
  steps: WorkflowStep[]
  created_at?: string
  updated_at?: string
  execution_count?: number
  success_rate?: number
  recent_runs?: WorkflowRun[]
}

export interface WorkflowOverview {
  templates: number
  active_instances: number
  running: number
  needs_human: number
  success_today: number
}

async function request<T>(method: string, url: string, body?: unknown, retry = false): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  })
  if (response.status === 401 && !retry) {
    const nextToken = await autoLogin()
    if (nextToken) return request<T>(method, url, body, true)
  }
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const data = await response.json()
      message = String(data.detail?.message || data.detail || data.message || message)
    } catch {
      // Keep the HTTP status when the backend did not return JSON.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const workflowOverview = () => request<WorkflowOverview>('GET', '/api/workflows/overview')
export const workflowTemplates = () => request<{ items: WorkflowTemplate[]; total: number }>('GET', '/api/workflows/templates')
export const workflowInstances = () => request<{ items: WorkflowInstance[]; total: number }>('GET', '/api/workflows/instances')
export const workflowRuns = (limit = 50) => request<{ items: WorkflowRun[]; total: number }>('GET', `/api/workflows/runs?limit=${limit}`)
export const workflowRunDetail = (id: string) => request<{
  run: WorkflowRun
  steps: Array<Record<string, unknown>>
  audit: Array<Record<string, unknown>>
  observations: Array<Record<string, unknown>>
}>('GET', `/api/workflows/runs/${id}`)
export const workflowSops = () => request<{ items: WorkflowSop[]; total: number }>('GET', '/api/workflows/sops')
export const workflowCapabilities = () => request<{ items: WorkflowCapability[]; total: number }>('GET', '/api/workflows/capabilities')

export const createWorkflowDraft = (payload: {
  goal: string
  context: WorkflowDraft['context']
  schedule: WorkflowSchedule
  notification: string
}) => request<WorkflowDraft>('POST', '/api/workflows/drafts', payload)

export const designWorkflowDraft = (id: string) => request<WorkflowDraft>('POST', `/api/workflows/drafts/${id}/design`)
export const reviseWorkflowDraft = (id: string, instruction: string) =>
  request<WorkflowDraft>('POST', `/api/workflows/drafts/${id}/revise`, { instruction })
export const updateWorkflowDraft = (id: string, payload: Partial<WorkflowDraft>) =>
  request<WorkflowDraft>('PUT', `/api/workflows/drafts/${id}`, payload)
export const validateWorkflowDraft = (id: string) =>
  request<WorkflowDraft['validation']>('POST', `/api/workflows/drafts/${id}/validate`)
export const activateWorkflowDraft = (id: string) =>
  request<WorkflowInstance>('POST', `/api/workflows/drafts/${id}/activate`)

export const createWorkflowInstance = (payload: {
  template_id?: string
  definition_id?: string
  name: string
  description?: string
  schedule: WorkflowSchedule
  config: Record<string, unknown>
  human_policy: WorkflowInstance['human_policy']
}) => request<WorkflowInstance>('POST', '/api/workflows/instances', payload)

export const updateWorkflowInstance = (id: string, payload: Partial<WorkflowInstance>) =>
  request<WorkflowInstance>('PUT', `/api/workflows/instances/${id}`, payload)

export const updateWorkflowSchedule = (id: string, schedule: WorkflowSchedule) =>
  request<WorkflowInstance>('PUT', `/api/workflows/instances/${id}/schedule`, schedule)

export const upgradeWorkflowInstance = (id: string) =>
  request<WorkflowInstance>('POST', `/api/workflows/instances/${id}/upgrade`)

export const deleteWorkflowInstance = (id: string) => request<{ ok: boolean }>('DELETE', `/api/workflows/instances/${id}`)
export const runWorkflowInstance = (id: string) => request<WorkflowRun>('POST', `/api/workflows/instances/${id}/run`)
export const controlWorkflowRun = (id: string, action: 'pause' | 'resume' | 'retry' | 'cancel') =>
  request<WorkflowRun>('POST', `/api/workflows/runs/${id}/${action}`)
export const confirmWorkflowRun = (id: string) => request<WorkflowRun>('POST', `/api/workflows/runs/${id}/confirm`)
export const cloneWorkflowSop = (id: string) => request<WorkflowSop>('POST', `/api/workflows/sops/${id}/clone`)
export const updateWorkflowSop = (id: string, payload: Partial<WorkflowSop>) =>
  request<WorkflowSop>('PUT', `/api/workflows/sops/${id}`, payload)
export const deleteWorkflowSop = (id: string) => request<{ ok: boolean }>('DELETE', `/api/workflows/sops/${id}`)
