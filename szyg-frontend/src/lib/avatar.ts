/**
 * 用户头像 — 完全本地化管理（仅前端，云端不参与）。
 * - 内置头像图库位于 src/assets/human_avatar，随应用编译进产物。
 * - 图库第 1 张（avatar-0）为全局默认头像，其余供用户自由选择。
 * - 支持用户上传本机图片（压缩后以 dataURL 存入 localStorage）。
 * - 头像永不离开本机浏览器存储。
 */

import { useEffect, useState } from 'react'

const AVATAR_KEY = 'szyg:user-avatar'
const AVATAR_CHANGED_EVENT = 'szyg:avatar-changed'

/** 内置头像图库（随应用编译打包，默认第 1 张） */
const builtinModules = import.meta.glob<{ default: string }>('@/assets/human_avatar/*.png', { eager: true })
export const AVATAR_PRESETS: string[] = Object.entries(builtinModules)
  .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))
  .map(([, module]) => module.default)

export const DEFAULT_AVATAR_SRC = AVATAR_PRESETS[0] ?? '/logo1.png'

export type AvatarSource = { kind: 'default' } | { kind: 'preset'; index: number } | { kind: 'custom'; dataUrl: string }

export function getUserAvatarSource(): AvatarSource {
  try {
    const raw = localStorage.getItem(AVATAR_KEY)
    if (!raw) return { kind: 'default' }
    const data = JSON.parse(raw)
    if (typeof data?.custom === 'string' && data.custom.startsWith('data:image')) {
      return { kind: 'custom', dataUrl: data.custom }
    }
    if (typeof data?.presetIndex === 'number' && data.presetIndex >= 0 && data.presetIndex < AVATAR_PRESETS.length) {
      return { kind: 'preset', index: data.presetIndex }
    }
  } catch {
    /* 损坏数据按默认处理 */
  }
  return { kind: 'default' }
}

export function getUserAvatarSrc(): string {
  const source = getUserAvatarSource()
  if (source.kind === 'custom') return source.dataUrl
  if (source.kind === 'preset') return AVATAR_PRESETS[source.index]
  return DEFAULT_AVATAR_SRC
}

export function getAvatarPresetSrc(index: number): string {
  return AVATAR_PRESETS[Math.max(0, Math.min(AVATAR_PRESETS.length - 1, index))]
}

function notifyAvatarChanged(): void {
  window.dispatchEvent(new CustomEvent(AVATAR_CHANGED_EVENT))
}

export function setAvatarPreset(index: number): void {
  try {
    localStorage.setItem(AVATAR_KEY, JSON.stringify({ presetIndex: index }))
  } catch {
    return
  }
  notifyAvatarChanged()
}

export function setAvatarCustom(dataUrl: string): boolean {
  try {
    localStorage.setItem(AVATAR_KEY, JSON.stringify({ custom: dataUrl }))
  } catch {
    return false // 存储空间不足（图片过大）
  }
  notifyAvatarChanged()
  return true
}

export function clearUserAvatar(): void {
  localStorage.removeItem(AVATAR_KEY)
  notifyAvatarChanged()
}

/** 订阅头像变化（同窗口自定义事件 + 跨窗口 storage 事件） */
export function useUserAvatar(): AvatarSource {
  const [source, setSource] = useState<AvatarSource>(getUserAvatarSource)
  useEffect(() => {
    const update = () => setSource(getUserAvatarSource())
    window.addEventListener(AVATAR_CHANGED_EVENT, update)
    window.addEventListener('storage', update)
    return () => {
      window.removeEventListener(AVATAR_CHANGED_EVENT, update)
      window.removeEventListener('storage', update)
    }
  }, [])
  return source
}

/** 读取本地图片并压缩为 dataURL（上限 512px，PNG 透明保留、其余转 JPEG） */
export function fileToAvatarDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('读取失败'))
    reader.onload = () => {
      const image = new Image()
      image.onerror = () => reject(new Error('图片解析失败'))
      image.onload = () => {
        const max = 512
        const scale = Math.min(1, max / Math.max(image.width, image.height))
        const canvas = document.createElement('canvas')
        canvas.width = Math.max(1, Math.round(image.width * scale))
        canvas.height = Math.max(1, Math.round(image.height * scale))
        const ctx = canvas.getContext('2d')
        if (!ctx) return reject(new Error('图片处理失败'))
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height)
        const isPng = /png|webp/i.test(file.type)
        resolve(canvas.toDataURL(isPng ? 'image/png' : 'image/jpeg', 0.9))
      }
      image.src = String(reader.result)
    }
    reader.readAsDataURL(file)
  })
}