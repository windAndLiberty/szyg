import type { DigitalHumanAssetRole, DigitalHumanScene } from '@/lib/api'

export type MediaKind = 'image' | 'video' | 'audio'

const VIDEO_EXTS = ['mp4', 'mov', 'quicktime']
const AUDIO_EXTS = ['mp3', 'wav', 'm4a', 'aac']
const IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'webp', 'gif']

export function inferMediaKind(file: File): MediaKind | null {
  const mime = (file.type || '').toLowerCase()
  if (mime.startsWith('image/')) return 'image'
  if (mime.startsWith('video/')) return 'video'
  if (mime.startsWith('audio/')) return 'audio'
  const ext = (file.name.split('.').pop() || '').toLowerCase()
  if (VIDEO_EXTS.includes(ext)) return 'video'
  if (AUDIO_EXTS.includes(ext)) return 'audio'
  if (IMAGE_EXTS.includes(ext)) return 'image'
  return null
}

export function inferSceneReferenceRole(file: File): DigitalHumanAssetRole {
  const kind = inferMediaKind(file)
  if (kind === 'audio') return 'voice_reference'
  if (kind === 'video') return 'motion_reference'
  return 'scene_reference'
}

export function acceptForSceneReference(): string {
  return 'image/*,video/mp4,video/quicktime,audio/*'
}

export function acceptForAvatar(): string {
  return 'image/*,video/mp4,video/quicktime'
}

export function acceptForVoice(): string {
  return 'audio/*,video/mp4,video/quicktime'
}

export function acceptForInspiration(): string {
  return 'image/*,video/mp4,video/quicktime'
}

export function freshScene(order: number): DigitalHumanScene {
  return {
    id: `scene_${crypto.randomUUID().slice(0, 8)}`,
    order,
    spoken_text: '',
    visual_prompt: '',
    duration: 5,
    presenter_mode: 'full',
    visual_mode: 'presenter',
    reference_asset_ids: [],
    transition: '自然衔接',
    subtitle: true,
    sound_prompt: '保留清晰自然的人声',
  }
}

export function reOrder<T>(items: T[], fromIndex: number, toIndex: number): T[] {
  if (fromIndex === toIndex) return items
  const next = items.slice()
  const [picked] = next.splice(fromIndex, 1)
  next.splice(toIndex, 0, picked)
  return next
}

export function normalizeSceneOrder(scenes: DigitalHumanScene[]): DigitalHumanScene[] {
  return scenes.map((scene, index) => ({ ...scene, order: index + 1 }))
}

export const ROLE_LABELS: Record<string, string> = {
  avatar_reference: 'digitalHuman.role.person',
  product_reference: 'digitalHuman.role.product',
  background_reference: 'digitalHuman.role.background',
  motion_reference: 'digitalHuman.role.motion',
  voice_reference: 'digitalHuman.role.voice',
  brand_asset: 'digitalHuman.role.brand',
  inspiration_reference: 'digitalHuman.role.inspiration',
  scene_reference: 'digitalHuman.role.background',
}
