// ── AI视频工作台 — 共享类型 ──

export type PageStatus = 'idle' | 'generating' | 'previewing' | 'editing' | 'publishing' | 'error'

export interface VideoItem {
  id: string
  title: string
  thumbnail?: string
  url: string
  duration: number    // 秒
  size_mb: number
  resolution: string  // "1920×1080"
  status: 'generating' | 'ready' | 'error'
  progress: number    // 0-100
  created_at: string
  source: 'ai' | 'upload'
  published?: boolean
}

export interface EditStep {
  tool: string       // cut | concat | speed | title | mix_audio | extract_frame
  label: string      // 显示名称
  params: Record<string, unknown>
}

export interface PublishTarget {
  platform: string   // douyin | xhs | bilibili | kuaishou | wechat_mp
  title: string
  tags: string[]
  description: string
  scheduled_at?: string
}

export interface TemplateInfo {
  id: string
  name: string
  description: string
  category: string
  preview_url?: string
}

export interface VideoGenParams {
  prompt: string
  duration: number   // 3 | 5 | 10 | 15
  style: string      // realistic | anime | cinematic | cyberpunk
  mode: string       // text-to-video | image-to-video
  model: string      // doubao-video | seaweed
  image_url?: string
}

export const GEN_DEFAULTS: VideoGenParams = {
  prompt: '',
  duration: 5,
  style: 'realistic',
  mode: 'text-to-video',
  model: 'doubao-video',
}
