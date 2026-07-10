import { generateImage, getErrorMessage } from '@/lib/api'
import { resolveGeneratedAssetUrl } from '@/lib/generatedAssets'

export const CONTENT_DRAFT_KEY = 'szyg.contentPublish.latestDraft'
const IMAGE_STATE_KEY = 'szyg.contentProduction.imageState'

export interface GeneratedImageAsset {
  url: string
  path: string
}

export interface ContentDraft {
  type: string
  prompt: string
  title: string
  note: string
  tags: string[]
  assets: GeneratedImageAsset[]
  createdAt: string
}

export interface ImageGenerationState {
  loading: boolean
  prompt: string
  style: string
  size: string
  count: number
  results: GeneratedImageAsset[]
  error: string | null
}

type Listener = (state: ImageGenerationState) => void

const listeners = new Set<Listener>()

const defaultState: ImageGenerationState = {
  loading: false,
  prompt: '',
  style: 'none',
  size: '1920x1920',
  count: 1,
  results: [],
  error: null,
}

function loadState(): ImageGenerationState {
  try {
    const raw = localStorage.getItem(IMAGE_STATE_KEY)
    if (!raw) return defaultState
    const saved = JSON.parse(raw) as Partial<ImageGenerationState>
    return {
      ...defaultState,
      ...saved,
      loading: false,
      error: null,
      results: Array.isArray(saved.results) ? saved.results : [],
      count: Math.max(1, Math.min(4, Number(saved.count || defaultState.count))),
    }
  } catch {
    return defaultState
  }
}

let state: ImageGenerationState = loadState()

function persistState() {
  try {
    localStorage.setItem(IMAGE_STATE_KEY, JSON.stringify({ ...state, loading: false, error: null }))
  } catch {
    // Ignore unavailable localStorage or quota errors.
  }
}

function emit() {
  const snapshot = { ...state, results: [...state.results] }
  listeners.forEach((listener) => listener(snapshot))
}

function persistDraft(draft: ContentDraft) {
  const value = JSON.stringify(draft)
  sessionStorage.setItem(CONTENT_DRAFT_KEY, value)
  localStorage.setItem(CONTENT_DRAFT_KEY, value)
}

function persistImageDraft(prompt: string, assets: GeneratedImageAsset[]) {
  const draft: ContentDraft = {
    type: 'image',
    prompt,
    title: 'AI生成图文草稿',
    note: prompt,
    tags: ['AI生成', '内容生产'],
    assets,
    createdAt: new Date().toISOString(),
  }
  persistDraft(draft)
}

export function getImageGenerationState(): ImageGenerationState {
  return { ...state, results: [...state.results] }
}

export function subscribeImageGeneration(listener: Listener): () => void {
  listeners.add(listener)
  listener(getImageGenerationState())
  return () => listeners.delete(listener)
}

export async function startImageDraftGeneration(opts: {
  prompt: string
  style: string
  size: string
  count?: number
}): Promise<void> {
  const prompt = opts.prompt.trim()
  if (!prompt || state.loading) return
  const count = Math.max(1, Math.min(4, opts.count || 1))

  state = {
    loading: true,
    prompt,
    style: opts.style,
    size: opts.size,
    count,
    results: state.results,
    error: null,
  }
  persistState()
  emit()

  try {
    const res = await generateImage(prompt, opts.size, count, opts.style)
    const assets = (res.images || []).map((url, index) => ({
      url: resolveGeneratedAssetUrl(url, res.paths?.[index] || ''),
      path: res.paths?.[index] || url,
    }))
    persistImageDraft(prompt, assets)
    state = {
      loading: false,
      prompt,
      style: opts.style,
      size: opts.size,
      count,
      results: assets,
      error: null,
    }
    persistState()
  } catch (err) {
    state = {
      ...state,
      loading: false,
      error: getErrorMessage(err, '图片生成失败'),
    }
    persistState()
  } finally {
    emit()
  }
}

export function removeGeneratedImageAsset(asset: GeneratedImageAsset): void {
  const target = asset.path || asset.url
  state = {
    ...state,
    results: state.results.filter((item) => (item.path || item.url) !== target),
  }
  persistState()
  persistImageDraft(state.prompt, state.results)
  emit()
}
