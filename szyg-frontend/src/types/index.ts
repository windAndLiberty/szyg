export interface DigitalHuman {
  id: string
  name: string
  avatar: string
  status: 'active' | 'training' | 'idle' | 'error'
  type: 'sales' | 'customer_service' | 'marketing' | 'data_analyst' | 'custom'
  model: string
  createdAt: string
  lastActive: string
  interactions: number
  successRate: number
  description: string
}

export interface DashboardKPI {
  label: string
  value: string
  numericValue: number
  trend: number
  subtitle: string
  icon: string
  iconColor: string
}

export interface ActivityItem {
  id: string
  type: 'agent_created' | 'agent_deployed' | 'interaction' | 'report_generated' | 'alert' | 'system'
  title: string
  description: string
  timestamp: string
}

export interface TaskQueueItem {
  id: string
  name: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  createdAt: string
  priority: 'high' | 'medium' | 'low'
}

// Super Agent Chat — 与后端 /api/hermes/chat SSE 事件对齐
export type ChatRole = 'user' | 'assistant' | 'system'
export type ChatMessageType = 'text' | 'image' | 'video_pending' | 'tool_result' | 'video'

export interface ToolCall {
  id: string
  tool: string
  status: 'success' | 'error' | 'running'
}

export interface ChatMessage {
  id: string
  role: ChatRole
  type: ChatMessageType
  content: string
  timestamp: number
  image_url?: string
  prompt?: string
  video_url?: string
  task_id?: string
  status?: string
  progress?: number
  toolCall?: ToolCall
  isStreaming?: boolean
}

export interface Conversation {
  id: string
  title: string
  updated_at: string
  pinned: boolean
}

// 欢迎页精选案例 — 来自后端 /api/hermes/case-cards (真实抖音短视频)
export interface CaseCard {
  title: string
  cover_url: string
  video_url: string
  author: string
  likes: number
}
