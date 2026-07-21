import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { motion } from 'framer-motion'
import {
  Search,
  Upload,
  Trash2,
  X,
  Grid3X3,
  List,
  FileImage,
  FileVideo,
  FileAudio,
  FileText,
  Loader2,
  FolderOpen,
  Sparkles,
  Wand2,
  Check,
  Send,
  AlertCircle,
  RefreshCw,
  Newspaper,
  Images,
} from 'lucide-react'
import {
  analyzeGraphicComposition,
  analyzeVideoComposition,
  createSauNoteTask,
  createSauVideoTask,
  createVideoComposition,
  fetchPlatformAccounts,
  fetchPublishingProfiles,
  generatePublishCopy,
  generatePublishTitle,
  getErrorMessage,
  getVideoConfig,
  openPlatformAccountPublish,
  revealGeneratedMedia,
  pollVideoTask,
  prepareGraphicComposition,
  prepareVideoComposition,
  saveGraphicComposition,
  updateGeneratedDocument,
  type ComposeAnalyzeResult,
  type ComposePrepareResult,
  type ComposeQuestion,
  type ComposeVideoParams,
  type ChannelAccount,
  type GraphicAnalyzeResult,
  type GraphicDraft,
  type GraphicPrepareResult,
  type PublishingProfile,
  type SauCreateResponse,
  type VideoModelConfig,
} from '@/lib/api'
import { resolveGeneratedAssetUrl } from '@/lib/generatedAssets'

type AssetType = 'all' | 'image' | 'video' | 'audio' | 'text'
const MAX_COMPOSE_ASSETS = 5

interface Asset {
  id: string
  name: string
  type: 'image' | 'video' | 'audio' | 'text'
  url?: string
  path?: string
  size: number
  created_at: string
  source?: string
  image_order?: string[]
  image_anchors?: Array<{ asset_id: string; anchor_after_paragraph?: number; caption?: string }>
  used_asset_ids?: string[]
}

const ASSET_TYPE_FILTERS: { key: AssetType; label: string; icon: typeof FileImage }[] = [
  { key: 'all', label: '全部', icon: Grid3X3 },
  { key: 'image', label: '图片', icon: FileImage },
  { key: 'video', label: '视频', icon: FileVideo },
  { key: 'audio', label: '音频', icon: FileAudio },
  { key: 'text', label: '文案', icon: FileText },
]

const TYPE_ICONS: Record<string, typeof FileImage> = {
  image: FileImage,
  video: FileVideo,
  audio: FileAudio,
  text: FileText,
}
const PUBLISH_TITLE_LIMITS: Record<string, Partial<Record<'note' | 'video', number>>> = {
  douyin: { note: 20, video: 20 },
  xhs: { note: 20, video: 20 },
  tencent: { note: 22, video: 30 },
  weibo: { note: 80, video: 80 },
}
const PUBLISH_CHANNELS: Array<{
  id: string
  label: string
  types: Array<'note' | 'video'>
  note?: string
}> = [
  { id: 'douyin', label: '抖音', types: ['note', 'video'] },
  { id: 'xhs', label: '小红书', types: ['note', 'video'] },
  { id: 'kuaishou', label: '快手', types: ['note', 'video'] },
  { id: 'bilibili', label: 'B站', types: ['video'], note: '视频投稿' },
  { id: 'tencent', label: '视频号', types: ['note', 'video'], note: '桌面辅助' },
  { id: 'weibo', label: '微博', types: ['note', 'video'], note: '桌面辅助' },
  { id: 'youtube', label: 'YouTube', types: ['video'], note: '海外视频' },
]
const GRAPHIC_DRAFT_TITLE_LIMIT = 20

function normalizePublishTitle(title: string, limit: number): { value: string; truncated: boolean } {
  const cleaned = title
    .trim()
    .replace(/^[#\s"'“”《》]+|[#\s"'“”《》]+$/g, '')
    .replace(/\s+/g, '')
    .replace(/[#《》"'“”]/g, '')
  if (limit <= 0) return { value: cleaned, truncated: false }
  const chars = Array.from(cleaned)
  return { value: chars.slice(0, limit).join(''), truncated: chars.length > limit }
}

function formatFileSize(bytes: number): string {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function assetUrl(asset: Asset): string {
  return resolveGeneratedAssetUrl(asset.url || '', asset.path || '')
}

function accountAvatarUrl(account: ChannelAccount): string {
  if (!account.avatar_url) return ''
  if (account.platform === 'bilibili' || account.platform === 'weibo') {
    return `/api/platform-accounts/avatar?url=${encodeURIComponent(account.avatar_url)}`
  }
  return account.avatar_url
}

function isGraphicDraftAsset(asset: Asset): boolean {
  return asset.type === 'text' && (
    asset.source === 'one_click_graphic' ||
    Boolean(asset.image_order?.length) ||
    Boolean(asset.image_anchors?.length) ||
    Boolean(asset.used_asset_ids?.length)
  )
}

function cleanTextAssetContent(value: string): string {
  return value
    .split(/\r?\n/)
    .filter((line) => {
      const trimmed = line.trim()
      return trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('需求：')
    })
    .join('\n')
    .trim()
}

function TextAssetPreview({ asset, mode, version = 0 }: { asset: Asset; mode: 'card' | 'preview'; version?: number }) {
  const [content, setContent] = useState('')
  const [savedContent, setSavedContent] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    const url = assetUrl(asset)
    if (!url) {
      setContent('')
      setError('')
      return
    }

    const textUrl = `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}-${version}`
    fetch(textUrl, { cache: 'no-store' })
      .then((res) => {
        if (!res.ok) throw new Error('文案内容加载失败')
        return res.text()
      })
      .then((text) => {
        if (!cancelled) {
          const cleaned = cleanTextAssetContent(text)
          setContent(cleaned)
          setSavedContent(cleaned)
          setError('')
        }
      })
      .catch(() => {
        if (!cancelled) setError('文案内容加载失败')
      })

    return () => {
      cancelled = true
    }
  }, [asset, version])

  const dirty = content.trim() !== savedContent.trim()

  const saveContent = useCallback(async () => {
    if (!content.trim()) return
    setSaving(true)
    setError('')
    try {
      const doc = [`# ${asset.name.replace(/\.[^.]+$/, '') || '文案素材'}`, '', content.trim()].join('\n')
      await updateGeneratedDocument({ path: asset.path, url: asset.url, content: doc })
      setSavedContent(content)
      window.dispatchEvent(new CustomEvent('szyg:document-updated', { detail: { path: asset.path, url: asset.url, source: 'assets' } }))
    } catch (err) {
      setError(getErrorMessage(err, '保存文案修改失败'))
    } finally {
      setSaving(false)
    }
  }, [asset.name, asset.path, asset.url, content])

  if (mode === 'card') {
    return (
      <div className="flex h-full w-full flex-col justify-between rounded-lg bg-[#0B0F1A] p-4">
        <FileText className="h-8 w-8 text-[#6366F1]" />
        <p className="mt-3 line-clamp-5 text-[15px] leading-8 tracking-[0.01em] text-[#F1F5F9]">
          {error || content || '文案内容读取中...'}
        </p>
      </div>
    )
  }

  return (
    <div className="w-[min(760px,80vw)] rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-5">
      <div className="mb-2 text-[11px] text-[#64748B]">文案内容</div>
      <textarea
        value={error ? error : content}
        disabled={Boolean(error)}
        onChange={(event) => setContent(event.target.value)}
        className="min-h-[320px] w-full resize-y rounded-xl border border-[#1E293B] bg-[#020617] px-4 py-4 text-[15px] leading-8 tracking-[0.01em] text-[#F1F5F9] outline-none transition-colors focus:border-[#6366F1] disabled:opacity-70"
        placeholder="文案内容读取中..."
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="text-[11px] text-[#64748B]">
          {dirty ? '内容已修改，点击保存后才会写入文件。' : '已保存'}
        </div>
        {dirty && (
          <button
            type="button"
            onClick={saveContent}
            disabled={saving || !content.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-[#6366F1] px-3 py-1.5 text-body-xs text-white transition-colors hover:bg-[#5558E6] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
            保存
          </button>
        )}
      </div>
    </div>
  )
}

function GraphicDraftPreview({
  asset,
  mode,
  version = 0,
  assetsById,
}: {
  asset: Asset
  mode: 'card' | 'preview'
  version?: number
  assetsById: Map<string, Asset>
}) {
  const [content, setContent] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const url = assetUrl(asset)
    if (!url) {
      setContent('')
      setError('')
      return
    }

    const textUrl = `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}-${version}`
    fetch(textUrl, { cache: 'no-store' })
      .then((res) => {
        if (!res.ok) throw new Error('图文草稿加载失败')
        return res.text()
      })
      .then((text) => {
        if (!cancelled) {
          setContent(text)
          setError('')
        }
      })
      .catch(() => {
        if (!cancelled) setError('图文草稿加载失败')
      })

    return () => {
      cancelled = true
    }
  }, [asset, version])

  const parsed = useMemo(() => parseGraphicMarkdown(content), [content])
  const visualIds = useMemo(() => {
    const fromAnchors = (asset.image_anchors || []).map((item) => item.asset_id)
    return Array.from(new Set([
      ...(asset.image_order || []),
      ...fromAnchors,
      ...(asset.used_asset_ids || []),
      ...parsed.imageOrder,
    ])).filter(Boolean)
  }, [asset.image_anchors, asset.image_order, asset.used_asset_ids, parsed.imageOrder])

  const visualAssets = useMemo(() => (
    visualIds
      .map((id) => assetsById.get(id))
      .filter((item): item is Asset => Boolean(item && (item.type === 'image' || item.type === 'video')))
  ), [assetsById, visualIds])

  const paragraphs = useMemo(() => (
    (parsed.body || content)
      .split(/\n{2,}|\r?\n/)
      .map((item) => item.trim())
      .filter((item) => item && !item.startsWith('##'))
  ), [content, parsed.body])

  if (mode === 'card') {
    return (
      <div className="flex h-full w-full flex-col justify-between overflow-hidden rounded-lg border border-[#38BDF8]/20 bg-gradient-to-br from-[#082F49]/70 via-[#0B1220] to-[#111827] p-4">
        <div>
          <div className="mb-3 flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#38BDF8]/30 bg-[#0EA5E9]/10 px-2 py-1 text-[11px] text-[#BAE6FD]">
              <Newspaper className="h-3.5 w-3.5" />
              图文草稿
            </span>
            {visualAssets.length > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-[#1E293B]/80 px-2 py-1 text-[11px] text-[#94A3B8]">
                <Images className="h-3.5 w-3.5" />
                {visualAssets.length}
              </span>
            )}
          </div>
          <h3 className="line-clamp-2 text-[15px] font-semibold leading-6 text-[#F8FAFC]">
            {error || parsed.title || asset.name.replace(/\.[^.]+$/, '') || '图文草稿'}
          </h3>
          <p className="mt-2 line-clamp-4 text-[13px] leading-6 text-[#CBD5E1]">
            {error || parsed.body || '图文内容读取中...'}
          </p>
        </div>

        <div className="mt-3">
          {visualAssets.length > 0 ? (
            <div className="grid grid-cols-3 gap-1.5">
              {visualAssets.slice(0, 3).map((visual) => (
                <div key={visual.id} className="aspect-square overflow-hidden rounded-md border border-[#1E293B] bg-[#020617]">
                  {visual.type === 'image' ? (
                    <img src={assetUrl(visual)} alt={visual.name} className="h-full w-full object-cover" />
                  ) : (
                    <video src={assetUrl(visual)} muted preload="metadata" className="h-full w-full object-cover" />
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-md border border-dashed border-[#334155] px-3 py-2 text-[11px] text-[#64748B]">
              暂无配图引用
            </div>
          )}
          {parsed.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {parsed.tags.slice(0, 3).map((tag) => (
                <span key={tag} className="rounded-full bg-[#6366F1]/15 px-2 py-0.5 text-[10px] text-[#C7D2FE]">
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="w-[min(860px,82vw)] rounded-xl border border-[#1E293B] bg-[#0B0F1A]">
      <div className="border-b border-[#1E293B] px-5 py-4">
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-[#38BDF8]/30 bg-[#0EA5E9]/10 px-2.5 py-1 text-[11px] text-[#BAE6FD]">
          <Newspaper className="h-3.5 w-3.5" />
          图文发布草稿
        </div>
        <h2 className="text-[22px] font-semibold leading-8 text-[#F8FAFC]">
          {error || parsed.title || asset.name.replace(/\.[^.]+$/, '') || '图文草稿'}
        </h2>
        {(parsed.platformSuggestion.length > 0 || visualAssets.length > 0) && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-[#94A3B8]">
            {parsed.platformSuggestion.map((platform) => (
              <span key={platform} className="rounded-full bg-[#1E293B] px-2 py-1">{platform}</span>
            ))}
            {visualAssets.length > 0 && (
              <span className="rounded-full bg-[#1E293B] px-2 py-1">{visualAssets.length} 个配图素材</span>
            )}
          </div>
        )}
      </div>

      <div className="max-h-[62vh] overflow-auto p-5">
        {visualAssets.length > 0 && (
          <div className="mb-5 grid gap-3" style={{ gridTemplateColumns: visualAssets.length === 1 ? '1fr' : 'repeat(3, minmax(0, 1fr))' }}>
            {visualAssets.slice(0, 6).map((visual) => (
              <figure key={visual.id} className="overflow-hidden rounded-xl border border-[#1E293B] bg-[#111827]">
                <div className="aspect-[4/3] bg-[#020617]">
                  {visual.type === 'image' ? (
                    <img src={assetUrl(visual)} alt={visual.name} className="h-full w-full object-cover" />
                  ) : (
                    <video src={assetUrl(visual)} muted preload="metadata" className="h-full w-full object-cover" />
                  )}
                </div>
                <figcaption className="truncate px-3 py-2 text-[11px] text-[#94A3B8]">{visual.name}</figcaption>
              </figure>
            ))}
          </div>
        )}

        <article className="rounded-xl border border-[#1E293B] bg-[#111827] p-5">
          <div className="space-y-4 text-[15px] leading-8 tracking-[0.01em] text-[#CBD5E1]">
            {paragraphs.length > 0 ? paragraphs.map((paragraph, index) => (
              <p key={`${index}-${paragraph.slice(0, 16)}`} className="whitespace-pre-wrap break-words">{paragraph}</p>
            )) : <p>{error || '图文内容读取中...'}</p>}
          </div>
          {parsed.tags.length > 0 && (
            <div className="mt-5 flex flex-wrap gap-2">
              {parsed.tags.map((tag) => (
                <span key={tag} className="rounded-full bg-[#6366F1]/15 px-2.5 py-1 text-[11px] text-[#C7D2FE]">#{tag}</span>
              ))}
            </div>
          )}
        </article>

        {(parsed.imageAnchorsText || parsed.publishNotes) && (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {parsed.imageAnchorsText && (
              <section className="rounded-xl border border-[#1E293B] bg-[#111827] p-4">
                <div className="mb-2 text-body-xs text-[#64748B]">配图位置</div>
                <p className="whitespace-pre-wrap text-body-sm leading-6 text-[#CBD5E1]">{parsed.imageAnchorsText}</p>
              </section>
            )}
            {parsed.publishNotes && (
              <section className="rounded-xl border border-[#1E293B] bg-[#111827] p-4">
                <div className="mb-2 text-body-xs text-[#64748B]">发布建议</div>
                <p className="whitespace-pre-wrap text-body-sm leading-6 text-[#CBD5E1]">{parsed.publishNotes}</p>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function splitTags(raw: string): string[] {
  return raw.split(/[,，#\s]+/).map((item) => item.trim()).filter(Boolean)
}

function uniqueAssets(items: Asset[]): Asset[] {
  const seen = new Set<string>()
  return items.filter((item) => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
}

function assetPath(asset: Asset): string {
  return asset.path || asset.url || ''
}

function toComposeAssetRef(asset: Asset) {
  return {
    id: asset.id,
    name: asset.name,
    type: asset.type as 'image' | 'video' | 'audio' | 'text',
    url: asset.url,
    path: asset.path,
  }
}

function titleFromAsset(asset?: Asset): string {
  if (!asset) return '未命名内容'
  return asset.name.replace(/\.[^.]+$/, '') || asset.name
}

async function readTextAsset(asset: Asset): Promise<string> {
  const url = assetUrl(asset)
  if (!url) return ''
  const response = await fetch(url)
  if (!response.ok) return ''
  return response.text()
}

function sectionText(markdown: string, heading: string): string {
  const pattern = new RegExp(`(?:^|\\n)##\\s*${heading}\\s*\\n([\\s\\S]*?)(?=\\n##\\s|$)`)
  return markdown.match(pattern)?.[1]?.trim() || ''
}

function parseGraphicMarkdown(markdown: string) {
  const title = markdown.match(/^#\s+(.+)$/m)?.[1]?.trim() || ''
  const bodyStart = markdown.replace(/^#\s+.+\r?\n+/, '')
  const body = bodyStart.split(/\r?\n##\s+/)[0]?.trim() || ''
  const tagText = sectionText(markdown, '标签')
  const tags = splitTags(tagText)
  const orderText = sectionText(markdown, '配图顺序')
  const imageOrder = Array.from(orderText.matchAll(/(?:^|\n)\s*(?:\d+\.\s*)?([a-zA-Z]+:[\w-]+)/g)).map((match) => match[1])
  const platformSuggestion = splitTags(sectionText(markdown, '平台建议'))
  const publishNotes = sectionText(markdown, '发布建议')
  const imageAnchorsText = sectionText(markdown, '配图位置')
  return { title, body, tags, imageOrder, platformSuggestion, publishNotes, imageAnchorsText }
}

async function expandGraphicDraftAssets(selected: Asset[], allAssets: Asset[]): Promise<Asset[]> {
  const assetsById = new Map(allAssets.map((asset) => [asset.id, asset]))
  const expanded: Asset[] = []

  for (const asset of selected) {
    expanded.push(asset)
    if (asset.type !== 'text') continue

    let imageIds = asset.image_order || []
    if (imageIds.length === 0 && asset.used_asset_ids?.length) {
      imageIds = asset.used_asset_ids
    }
    if (imageIds.length === 0) {
      try {
        imageIds = parseGraphicMarkdown(await readTextAsset(asset)).imageOrder
      } catch {
        imageIds = []
      }
    }

    imageIds.forEach((id) => {
      const ref = assetsById.get(id)
      if (ref && (ref.type === 'image' || ref.type === 'video')) {
        expanded.push(ref)
      }
    })
  }

  return uniqueAssets(expanded)
}

function PublishSelectedDrawer({
  assets,
  directGraphicDraftId = '',
  onClose,
  onSubmitted,
}: {
  assets: Asset[]
  directGraphicDraftId?: string
  onClose: () => void
  onSubmitted: (result: SauCreateResponse) => void
}) {
  const videos = assets.filter((asset) => asset.type === 'video')
  const images = assets.filter((asset) => asset.type === 'image')
  const texts = assets.filter((asset) => asset.type === 'text')
  const [accounts, setAccounts] = useState<ChannelAccount[]>([])
  const [profiles, setProfiles] = useState<PublishingProfile[]>([])
  const [platform, setPlatform] = useState('douyin')
  const [targetMode, setTargetMode] = useState<'accounts' | 'profile'>('accounts')
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState('')
  const [mode, setMode] = useState<'video' | 'note'>(() => (videos.length > 0 && images.length === 0 ? 'video' : 'note'))
  const [title, setTitle] = useState(titleFromAsset(videos[0] || images[0] || texts[0]))
  const [titleTouched, setTitleTouched] = useState(false)
  const [titleGenerating, setTitleGenerating] = useState(false)
  const [titleCandidates, setTitleCandidates] = useState<string[]>([])
  const [autoTitleDone, setAutoTitleDone] = useState(false)
  const [titleNotice, setTitleNotice] = useState('')
  const [body, setBody] = useState('')
  const [tags, setTags] = useState('SZYG AI生成')
  const [publishImageAnchors, setPublishImageAnchors] = useState<NonNullable<GraphicDraft['image_anchors']>>([])
  const [headless, setHeadless] = useState(true)
  const [tencentPublishMode, setTencentPublishMode] = useState<'auto' | 'manual'>('auto')
  const [loadingText, setLoadingText] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [targetsLoading, setTargetsLoading] = useState(true)
  const [targetsSyncedAt, setTargetsSyncedAt] = useState('')

  const singleGraphicDraftAsset = useMemo(
    () => assets.find((asset) => asset.id === directGraphicDraftId && isGraphicDraftAsset(asset)) || null,
    [assets, directGraphicDraftId],
  )
  const canRegeneratePublishCopy = !singleGraphicDraftAsset

  useEffect(() => {
    if (singleGraphicDraftAsset?.image_anchors?.length) {
      setPublishImageAnchors(singleGraphicDraftAsset.image_anchors.map((anchor) => ({
        asset_id: anchor.asset_id,
        anchor_after_paragraph: anchor.anchor_after_paragraph || 1,
        caption: anchor.caption,
      })))
    }
  }, [singleGraphicDraftAsset])

  const applyTitleInput = useCallback((raw: string) => {
    const limit = PUBLISH_TITLE_LIMITS[platform]?.[mode] || 0
    const normalized = normalizePublishTitle(raw, limit)
    setTitle(normalized.value)
    setTitleNotice(normalized.truncated ? `标题已自动截断为${limit}字符` : '')
    setTitleTouched(true)
    return normalized.value
  }, [mode, platform])

  const refreshPublishTargets = useCallback(async (silent = false) => {
    if (!silent) setTargetsLoading(true)
    try {
      const [accountData, profileData] = await Promise.all([
        fetchPlatformAccounts(),
        fetchPublishingProfiles(),
      ])
      setAccounts(accountData.accounts || [])
      setProfiles(profileData.profiles || [])
      setTargetsSyncedAt(new Date().toISOString())
      setError('')
    } catch (err) {
      setAccounts([])
      setProfiles([])
      setError(getErrorMessage(err, '账号和发布配置档案同步失败'))
    } finally {
      if (!silent) setTargetsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshPublishTargets(false)
  }, [refreshPublishTargets])

  useEffect(() => {
    void refreshPublishTargets(true)
  }, [platform, refreshPublishTargets])

  useEffect(() => {
    if (texts.length === 0) return
    let cancelled = false
    setLoadingText(true)
    Promise.all(texts.map(readTextAsset))
      .then((values) => {
        if (!cancelled) {
          const parsedValues = values.map(parseGraphicMarkdown)
          const titleValue = parsedValues.find((value) => value.title)?.title
          const tagValues = parsedValues.flatMap((value) => value.tags)
          const bodyValues = parsedValues.map((value, index) => value.body || values[index].replace(/^#\s+/gm, '').trim()).filter(Boolean)
          if (titleValue) {
            const normalized = normalizePublishTitle(titleValue, PUBLISH_TITLE_LIMITS[platform]?.[mode] || 0)
            setTitle(normalized.value)
            if (normalized.truncated) setTitleNotice('标题已自动截断为20字符')
          }
          if (tagValues.length > 0) setTags(Array.from(new Set(tagValues)).join(' '))
          const merged = bodyValues.join('\n\n').trim()
          if (merged) setBody(merged)
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingText(false)
      })
    return () => {
      cancelled = true
    }
  }, [mode, platform, texts])

  const accountById = useMemo(() => new Map(accounts.map((account) => [account.id, account])), [accounts])
  const profileAccounts = useCallback((profile: PublishingProfile | undefined) => {
    if (!profile) return []
    return profile.account_ids
      .map((accountId) => accountById.get(accountId))
      .filter(Boolean) as ChannelAccount[]
  }, [accountById])
  const platformAccounts = useMemo(() => accounts.filter((item) => item.platform === platform), [accounts, platform])
  const selectedProfile = profiles.find((item) => item.id === selectedProfileId)
  const selectedProfileAccounts = profileAccounts(selectedProfile)
  const selectedProfilePlatformAccounts = selectedProfileAccounts.filter((item) => item.platform === platform)
  const selectedTargets = targetMode === 'profile'
    ? selectedProfilePlatformAccounts.map((item) => item.id)
    : selectedAccountIds
  const isTencentDesktopAssist = platform === 'tencent'
  const isAccountReady = (account: ChannelAccount | undefined) => Boolean(account && (
    account.session?.valid || (account.platform === 'tencent' && account.status === 'connected')
  ))
  const loggedIn = targetMode === 'profile'
    ? selectedProfilePlatformAccounts.some((item) => isAccountReady(item))
    : platformAccounts.some((item) => selectedAccountIds.includes(item.id) && isAccountReady(item))
  const canVideo = videos.length > 0
  const canNote = images.length > 0
  const availablePublishChannels = useMemo(
    () => PUBLISH_CHANNELS.filter((channel) => channel.types.includes(mode)),
    [mode],
  )
  useEffect(() => {
    if (availablePublishChannels.some((channel) => channel.id === platform)) return
    const fallback = availablePublishChannels[0]?.id
    if (fallback) {
      setPlatform(fallback)
      setTargetMode('accounts')
    }
  }, [availablePublishChannels, platform])
  const titleLimit = PUBLISH_TITLE_LIMITS[platform]?.[mode] || 0
  const titleLength = Array.from(title).length
  const currentChannelLabel = PUBLISH_CHANNELS.find((item) => item.id === platform)?.label || platform
  const titleError = titleLimit > 0 && titleLength > titleLimit
    ? `${currentChannelLabel}标题不能超过${titleLimit}字符，当前${titleLength}字符`
    : ''
  const canSubmit = mode === 'video'
    ? Boolean(canVideo && title.trim() && selectedTargets.length > 0 && !titleError && !targetsLoading)
    : Boolean(canNote && title.trim() && selectedTargets.length > 0 && !titleError && !targetsLoading)

  const titleContext = useMemo(() => {
    return [body, titleFromAsset(videos[0] || images[0] || texts[0]), assets.map((asset) => asset.name).join(' ')].filter(Boolean).join('\n').trim()
  }, [assets, body, images, texts, videos])
  const bodyParagraphs = useMemo(
    () => body.split(/\n{2,}|\r?\n/).map((item) => item.trim()).filter(Boolean),
    [body],
  )
  const imageById = useMemo(() => new Map(images.map((asset) => [asset.id, asset])), [images])
  const anchoredImages = useMemo(() => {
    const groups = new Map<number, Array<{ asset: Asset; caption?: string }>>()
    const used = new Set<string>()
    publishImageAnchors.forEach((anchor) => {
      const asset = imageById.get(anchor.asset_id)
      if (!asset) return
      used.add(asset.id)
      const after = Math.max(1, Math.min(anchor.anchor_after_paragraph || 1, Math.max(1, bodyParagraphs.length)))
      const list = groups.get(after) || []
      list.push({ asset, caption: anchor.caption })
      groups.set(after, list)
    })
    return { groups, used }
  }, [bodyParagraphs.length, imageById, publishImageAnchors])
  const unanchoredImages = useMemo(
    () => images.filter((asset) => !anchoredImages.used.has(asset.id)),
    [anchoredImages.used, images],
  )

  useEffect(() => {
    const validIds = platformAccounts.map((item) => item.id)
    setSelectedAccountIds((prev) => prev.filter((id) => validIds.includes(id)))
  }, [platformAccounts])

  useEffect(() => {
    if (selectedAccountIds.length === 0 && platformAccounts.length > 0 && targetMode === 'accounts') {
      const firstValid = platformAccounts.find((item) => item.session?.valid) || platformAccounts[0]
      setSelectedAccountIds([firstValid.id])
    }
  }, [platformAccounts, selectedAccountIds.length, targetMode])

  useEffect(() => {
    if (targetMode !== 'profile') return
    if (selectedProfileId && profiles.some((profile) => profile.id === selectedProfileId)) return
    setSelectedProfileId(profiles[0]?.id || '')
  }, [profiles, selectedProfileId, targetMode])

  useEffect(() => {
    setAutoTitleDone(false)
    setTitleCandidates([])
  }, [platform, mode])

  useEffect(() => {
    if (availablePublishChannels.some((channel) => channel.id === platform)) return
    setPlatform(availablePublishChannels[0]?.id || 'douyin')
    setTargetMode('accounts')
  }, [availablePublishChannels, platform])

  const requestGeneratedTitle = useCallback(async (replaceUserTitle = false) => {
    if (!canRegeneratePublishCopy) return
    const content = titleContext || body || assets.map((asset) => asset.name).join('\n')
    if (!content.trim()) return
    if (!replaceUserTitle && (titleTouched || autoTitleDone)) return
    setTitleGenerating(true)
    try {
      const result = await generatePublishCopy({
        platform,
        kind: mode,
        assets: assets.map(toComposeAssetRef),
        content,
        current_title: title,
        current_body: body,
        tags: splitTags(tags),
      })
      const nextTitle = normalizePublishTitle(result.title, result.limit || titleLimit)
      setTitle(nextTitle.value)
      setTitleCandidates((result.candidates || []).map((item) => normalizePublishTitle(item, result.limit || titleLimit).value).filter(Boolean))
      if (result.body?.trim()) setBody(result.body.trim())
      if (result.tags?.length) setTags(result.tags.join(' '))
      setPublishImageAnchors(result.image_anchors || [])
      setTitleNotice(nextTitle.truncated ? `标题已自动截断为${result.limit || titleLimit}字符` : '已生成发布内容')
      setAutoTitleDone(true)
      setError('')
      if (replaceUserTitle) setTitleTouched(false)
    } catch (err) {
      if (replaceUserTitle) {
        setError(getErrorMessage(err, '标题生成失败'))
      }
    } finally {
      setTitleGenerating(false)
    }
  }, [assets, autoTitleDone, body, canRegeneratePublishCopy, mode, platform, tags, title, titleContext, titleTouched, titleLimit])

  useEffect(() => {
    if (!canRegeneratePublishCopy) return
    if (!titleContext || titleTouched || autoTitleDone) return
    const timer = window.setTimeout(() => {
      void requestGeneratedTitle(false)
    }, 350)
    return () => window.clearTimeout(timer)
  }, [autoTitleDone, canRegeneratePublishCopy, requestGeneratedTitle, titleContext, titleTouched])

  useEffect(() => {
    if (!canRegeneratePublishCopy) return
    if (!titleError || !titleContext || titleGenerating) return
    const timer = window.setTimeout(() => {
      void requestGeneratedTitle(true)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [canRegeneratePublishCopy, requestGeneratedTitle, titleContext, titleError, titleGenerating])

  async function handleSubmit() {
    let submitTitle = title.trim()
    if (titleLimit > 0 && Array.from(submitTitle).length > titleLimit) {
      setSubmitting(true)
      setError('')
      try {
        const content = titleContext || body || assets.map((asset) => asset.name).join('\n')
        const result = await generatePublishTitle({
          platform,
          kind: mode,
          content,
          current_title: submitTitle,
          tags: splitTags(tags),
        })
        const normalized = normalizePublishTitle(result.title, result.limit || titleLimit)
        submitTitle = normalized.value
        setTitle(submitTitle)
        setTitleCandidates((result.candidates || []).map((item) => normalizePublishTitle(item, result.limit || titleLimit).value).filter(Boolean))
        setTitleNotice(normalized.truncated ? `标题已自动截断为${result.limit || titleLimit}字符` : '已生成一句短标题')
      } catch {
        const normalized = normalizePublishTitle(submitTitle, titleLimit)
        submitTitle = normalized.value
        setTitle(submitTitle)
        if (normalized.truncated) setTitleNotice(`标题已自动截断为${titleLimit}字符`)
      } finally {
        setSubmitting(false)
      }
    }
    const submitTitleValid = Boolean(submitTitle && (!titleLimit || Array.from(submitTitle).length <= titleLimit))
    const canSubmitNow = mode === 'video'
      ? Boolean(canVideo && submitTitleValid && selectedTargets.length > 0)
      : Boolean(canNote && submitTitleValid && selectedTargets.length > 0)
    if (!canSubmitNow) return
    setSubmitting(true)
    setError('')
    try {
      await refreshPublishTargets(true)
      if (isTencentDesktopAssist) {
        const accountId = selectedTargets[0]
        if (!accountId) {
          setError('请选择一个视频号账号')
          return
        }
        const opened = await openPlatformAccountPublish(accountId, {
          title: submitTitle,
          desc: body.trim(),
          tags: splitTags(tags),
          file_path: mode === 'video' ? assetPath(videos[0]) : '',
          asset_paths: assets.map(assetPath).filter(Boolean),
          mode,
          auto_publish: tencentPublishMode === 'auto',
        })
        onSubmitted({
          ok: true,
          task_id: opened.task_id || opened.execution_id || `manual_tencent_${Date.now()}`,
          execution_id: opened.execution_id || '',
          task: {
            id: opened.task_id || opened.execution_id || `manual_tencent_${Date.now()}`,
            platform: 'tencent',
            status: opened.run?.status || 'running',
            title: submitTitle,
            message: opened.message,
          },
          run: opened.run,
        } as unknown as SauCreateResponse)
        return
      }
      const result = mode === 'video'
        ? await createSauVideoTask({
            platform,
            file_path: assetPath(videos[0]),
            title: submitTitle,
            desc: body.trim(),
            tags: splitTags(tags),
            headless,
            target_account_ids: targetMode === 'accounts' ? selectedAccountIds : [],
            profile_id: targetMode === 'profile' ? selectedProfileId : undefined,
          })
        : await createSauNoteTask({
            platform,
            image_paths: images.map(assetPath).filter(Boolean),
            title: submitTitle,
            note: body.trim(),
            tags: splitTags(tags),
            headless,
            target_account_ids: targetMode === 'accounts' ? selectedAccountIds : [],
            profile_id: targetMode === 'profile' ? selectedProfileId : undefined,
          })
      onSubmitted(result)
    } catch (err) {
      setError(getErrorMessage(err, '发布任务创建失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/55 backdrop-blur-sm">
      <button className="min-w-0 flex-1" aria-label="关闭发布确认" onClick={onClose} />
      <aside className="flex h-full w-full max-w-[760px] flex-col border-l border-[#1E293B] bg-[#0B1120] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#1E293B] px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-[#F8FAFC]">确认发布</h2>
            <p className="mt-1 text-sm text-[#64748B]">素材路径已自动带入，只需确认渠道、标题和正文。</p>
          </div>
          <button onClick={onClose} className="rounded-md p-2 text-[#64748B] transition-colors hover:bg-[#111827] hover:text-[#F8FAFC]">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          <div className="space-y-5">
            <section className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-4">
              <div className="mb-3 text-body-sm font-medium text-[#E2E8F0]">已选素材</div>
              <div className="grid grid-cols-3 gap-2">
                {assets.map((asset) => (
                  <div key={asset.id} className="overflow-hidden rounded-lg border border-[#1E293B] bg-[#020617]">
                    <div className="aspect-square">{asset.type === 'text' ? <TextAssetPreview asset={asset} mode="card" /> : (
                      asset.type === 'image'
                        ? <img src={assetUrl(asset)} className="h-full w-full object-cover" alt={asset.name} />
                        : asset.type === 'video'
                          ? <video src={assetUrl(asset)} muted preload="metadata" className="h-full w-full object-cover" />
                          : <div className="flex h-full items-center justify-center"><FileAudio className="h-8 w-8 text-[#6366F1]" /></div>
                    )}</div>
                    <div className="truncate px-2 py-1.5 text-[11px] text-[#94A3B8]">{asset.name}</div>
                  </div>
                ))}
              </div>
              {videos.length > 1 && <div className="mt-3 text-body-xs text-[#F59E0B]">视频发布会使用第一条视频，其余素材可作为下次发布使用。</div>}
              {assets.some((asset) => asset.type === 'audio') && <div className="mt-3 text-body-xs text-[#94A3B8]">音频素材暂不直接提交给发布平台，可作为内容制作参考。</div>}
            </section>

            <section className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-4">
              <div className="mb-3 text-body-sm font-medium text-[#E2E8F0]">发布类型</div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setMode('note')}
                  disabled={!canNote}
                  className={`rounded-lg border px-3 py-2 text-body-sm transition-colors ${mode === 'note' ? 'border-[#6366F1] bg-[#6366F1]/20 text-[#C4B5FD]' : 'border-[#334155] text-[#94A3B8] hover:bg-[#1E293B] disabled:cursor-not-allowed disabled:opacity-40'}`}
                >
                  图文发布
                </button>
                <button
                  type="button"
                  onClick={() => setMode('video')}
                  disabled={!canVideo}
                  className={`rounded-lg border px-3 py-2 text-body-sm transition-colors ${mode === 'video' ? 'border-[#6366F1] bg-[#6366F1]/20 text-[#C4B5FD]' : 'border-[#334155] text-[#94A3B8] hover:bg-[#1E293B] disabled:cursor-not-allowed disabled:opacity-40'}`}
                >
                  视频发布
                </button>
              </div>
            </section>

            <section className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-body-sm font-medium text-[#E2E8F0]">发布账号</div>
                <div className="text-[11px] text-[#64748B]">已选 {selectedTargets.length} 个账号</div>
              </div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#1E293B] bg-[#020617] px-3 py-2">
                <div className="flex min-w-0 items-center gap-2 text-[11px] text-[#94A3B8]">
                  {targetsLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-[#818CF8]" /> : <Check className="h-3.5 w-3.5 text-[#10B981]" />}
                  <span className="truncate">
                    {targetsLoading
                      ? '正在从渠道账号同步最新登录状态和档案'
                      : targetsSyncedAt
                        ? `已同步最新账号状态 · ${new Date(targetsSyncedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
                        : '发布前会自动同步最新账号状态'}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => refreshPublishTargets(false)}
                  disabled={targetsLoading}
                  className="inline-flex items-center gap-1.5 rounded-md border border-[#334155] bg-[#0B1120] px-2.5 py-1.5 text-[11px] text-[#CBD5E1] transition-colors hover:border-[#6366F1] hover:text-[#F8FAFC] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {targetsLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  刷新账号
                </button>
              </div>
              <div className="mb-3 grid grid-cols-2 gap-2">
                {availablePublishChannels.map((item) => {
                  const count = accounts.filter((account) => account.platform === item.id).length
                  const validCount = accounts.filter((account) => account.platform === item.id && account.session?.valid).length
                  const assistCount = accounts.filter((account) => account.platform === item.id && account.status === 'connected').length
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        setPlatform(item.id)
                        setTargetMode('accounts')
                      }}
                      className={`rounded-lg border px-3 py-2 text-left transition-colors ${platform === item.id ? 'border-[#6366F1] bg-[#6366F1]/20' : 'border-[#334155] bg-[#020617] hover:bg-[#1E293B]'}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-body-sm text-[#F1F5F9]">{item.label}</div>
                        {item.note && <span className="rounded-full bg-[#111827] px-2 py-0.5 text-[10px] text-[#94A3B8]">{item.note}</span>}
                      </div>
                      <div className={`mt-1 text-[11px] ${validCount > 0 || assistCount > 0 ? 'text-[#86EFAC]' : 'text-[#F59E0B]'}`}>
                        {item.id === 'tencent'
                          ? assistCount > 0 ? `${assistCount}/${count || 10} 在线` : '需要打开助手登录'
                          : validCount > 0 ? `${validCount}/${count || 10} 可用` : '需要登录账号'}
                      </div>
                    </button>
                  )
                })}
              </div>
              <div className="mb-3 rounded-lg border border-[#1E293B] bg-[#020617] px-3 py-2 text-[11px] leading-5 text-[#94A3B8]">
                {mode === 'note'
                  ? '图文发布支持抖音、小红书、快手、视频号和微博；视频号与微博会使用真实桌面浏览器辅助发布。'
                  : platform === 'tencent' || platform === 'weibo'
                    ? `${currentChannelLabel}当前采用真实桌面浏览器辅助发布，确认后会自动填写并提交。`
                    : '视频发布会显示已接入或保留执行能力的渠道，请选择已登录账号或发布配置档案。'}
              </div>
              <div className="mb-3 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setTargetMode('accounts')}
                  className={`rounded-lg border px-3 py-2 text-body-sm transition-colors ${targetMode === 'accounts' ? 'border-[#6366F1] bg-[#6366F1]/20 text-[#C4B5FD]' : 'border-[#334155] text-[#94A3B8] hover:bg-[#1E293B]'}`}
                >
                  选择账号
                </button>
                <button
                  type="button"
                  onClick={() => setTargetMode('profile')}
                  className={`rounded-lg border px-3 py-2 text-body-sm transition-colors ${targetMode === 'profile' ? 'border-[#6366F1] bg-[#6366F1]/20 text-[#C4B5FD]' : 'border-[#334155] text-[#94A3B8] hover:bg-[#1E293B]'}`}
                >
                  发布配置档案
                </button>
              </div>
              {targetMode === 'accounts' ? (
                <div className="space-y-2">
                  {platformAccounts.length === 0 ? (
                    <div className="rounded-lg border border-[#334155] bg-[#020617] p-3 text-body-xs text-[#94A3B8]">
                      当前平台暂无账号，请先到“渠道账号”添加并登录。
                    </div>
                  ) : platformAccounts.map((account) => {
                    const checked = selectedAccountIds.includes(account.id)
                    const displayName = account.nickname?.trim() || account.label || account.id
                    const secondary = account.nickname?.trim() && account.label ? account.label : (account.platform_label || account.platform)
                    return (
                      <button
                        key={account.id}
                        type="button"
                        onClick={() => {
                          setSelectedAccountIds((prev) => checked ? prev.filter((id) => id !== account.id) : [...prev, account.id])
                        }}
                        className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left transition-colors ${checked ? 'border-[#10B981] bg-[#10B981]/10' : 'border-[#334155] bg-[#020617] hover:bg-[#1E293B]'}`}
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          {account.avatar_url ? (
                            <img src={accountAvatarUrl(account)} alt={displayName} className="h-8 w-8 shrink-0 rounded-full border border-[#334155] object-cover" />
                          ) : (
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#334155] bg-[#111827] text-xs text-[#94A3B8]">
                              {displayName.slice(0, 1)}
                            </div>
                          )}
                          <div className="min-w-0">
                          <div className="truncate text-body-sm text-[#F1F5F9]">{displayName}</div>
                          <div className="mt-0.5 truncate text-[11px] text-[#64748B]">{secondary}</div>
                          <div className={`mt-1 text-[11px] ${account.session?.valid ? 'text-[#86EFAC]' : 'text-[#F59E0B]'}`}>
                            {isAccountReady(account) ? '账号可用' : '需要登录'}
                          </div>
                          </div>
                        </div>
                        {checked && <Check className="h-4 w-4 shrink-0 text-[#10B981]" />}
                      </button>
                    )
                  })}
                </div>
              ) : (
                <div className="space-y-2">
                  {profiles.length === 0 ? (
                    <div className="rounded-lg border border-[#334155] bg-[#020617] p-3 text-body-xs text-[#94A3B8]">
                      暂无发布配置档案，请先到“渠道账号”创建账号组。
                    </div>
                  ) : profiles.map((profile) => {
                    const checked = selectedProfileId === profile.id
                    const linkedAccounts = profileAccounts(profile)
                    const currentPlatformAccounts = linkedAccounts.filter((account) => account.platform === platform)
                    const onlineCount = currentPlatformAccounts.filter((account) => isAccountReady(account)).length
                    const platformNames = Array.from(new Set(linkedAccounts.map((account) => account.platform_label || account.platform))).slice(0, 3)
                    return (
                      <button
                        key={profile.id}
                        type="button"
                        onClick={() => setSelectedProfileId(profile.id)}
                        className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${checked ? 'border-[#10B981] bg-[#10B981]/10' : 'border-[#334155] bg-[#020617] hover:bg-[#1E293B]'}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate text-body-sm text-[#F1F5F9]">{profile.name}</div>
                            <div className="mt-1 text-[11px] text-[#94A3B8]">
                              当前渠道 {currentPlatformAccounts.length} 个账号 · {onlineCount} 个可用{platformNames.length > 0 ? ` · 全组含 ${platformNames.join(' / ')}` : ''}
                            </div>
                          </div>
                          {checked && <Check className="h-4 w-4 shrink-0 text-[#10B981]" />}
                        </div>
                        {currentPlatformAccounts.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {currentPlatformAccounts.slice(0, 5).map((account) => {
                              const name = account.nickname?.trim() || account.label || account.id
                              return (
                                <span
                                  key={account.id}
                                  className={`max-w-[150px] truncate rounded-full border px-2 py-1 text-[11px] ${
                                    isAccountReady(account)
                                      ? 'border-[#10B981]/25 bg-[#10B981]/10 text-[#86EFAC]'
                                      : 'border-[#F59E0B]/25 bg-[#F59E0B]/10 text-[#FDE68A]'
                                  }`}
                                  title={name}
                                >
                                  {name}
                                </span>
                              )
                            })}
                          </div>
                        ) : (
                          <div className="mt-3 rounded-lg border border-[#F59E0B]/25 bg-[#F59E0B]/10 px-3 py-2 text-[11px] text-[#FDE68A]">
                            这组里暂时没有当前渠道账号，切换渠道或回到“渠道账号”补充账号即可。
                          </div>
                        )}
                      </button>
                    )
                  })}
                </div>
              )}
                {!loggedIn && (
                <div className="mt-3 flex gap-2 rounded-lg border border-[#F59E0B]/30 bg-[#F59E0B]/10 p-3 text-body-xs text-[#FDE68A]">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {isTencentDesktopAssist
                    ? '请先到“渠道账号”点击视频号的“打开助手”，在普通浏览器中完成登录后再回来发布。'
                    : '当前发布目标可能需要先到“渠道账号”完成登录，提交后如果登录失效会进入需处理状态。'}
                </div>
              )}
            </section>

            {isTencentDesktopAssist && (
              <section className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-body-sm font-medium text-[#E2E8F0]">视频号发布方式</div>
                    <div className="mt-1 text-body-xs text-[#64748B]">位置、链接、合集、音乐、活动和定时发表属于可选运营项。</div>
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => setTencentPublishMode('auto')}
                    className={`rounded-lg border px-3 py-3 text-left transition-colors ${tencentPublishMode === 'auto' ? 'border-[#10B981] bg-[#10B981]/10' : 'border-[#334155] bg-[#020617] hover:bg-[#1E293B]'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-body-sm font-medium text-[#F8FAFC]">一键发布</span>
                      {tencentPublishMode === 'auto' && <Check className="h-4 w-4 text-[#10B981]" />}
                    </div>
                    <p className="mt-1 text-body-xs leading-5 text-[#94A3B8]">
                      自动上传素材、填写标题和正文，并点击发表。适合不需要补充位置、链接、音乐的内容。
                    </p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setTencentPublishMode('manual')}
                    className={`rounded-lg border px-3 py-3 text-left transition-colors ${tencentPublishMode === 'manual' ? 'border-[#6366F1] bg-[#6366F1]/15' : 'border-[#334155] bg-[#020617] hover:bg-[#1E293B]'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-body-sm font-medium text-[#F8FAFC]">填好后我来确认</span>
                      {tencentPublishMode === 'manual' && <Check className="h-4 w-4 text-[#A5B4FC]" />}
                    </div>
                    <p className="mt-1 text-body-xs leading-5 text-[#94A3B8]">
                      只填写图片/视频、标题和正文，然后停在视频号页面，方便你补位置、链接等信息后手动发表。
                    </p>
                  </button>
                </div>
                {tencentPublishMode === 'manual' && (
                  <div className="mt-3 rounded-lg border border-[#6366F1]/25 bg-[#6366F1]/10 px-3 py-2 text-body-xs leading-5 text-[#C4B5FD]">
                    发布看板会显示“需处理”，表示 SZYG 已完成必要信息填写，正在等待你在视频号页面确认。
                  </div>
                )}
              </section>
            )}

            <section className="space-y-3 rounded-lg border border-[#1E293B] bg-[#0F172A] p-4">
              <label>
                <span className="mb-1 flex items-center justify-between gap-3 text-body-xs text-[#64748B]">
                  <span>标题短语</span>
                  {titleLimit > 0 && (
                    <span className={titleError ? 'text-[#FCA5A5]' : 'text-[#64748B]'}>
                      {titleLength}/{titleLimit}
                    </span>
                  )}
                </span>
                <input
                  value={title}
                  maxLength={titleLimit || undefined}
                  placeholder={titleLimit ? `一句短语，最多${titleLimit}字符` : '一句短语'}
                  onChange={(event) => {
                    applyTitleInput(event.target.value)
                  }}
                  onInput={(event) => {
                    const target = event.currentTarget
                    const nextValue = normalizePublishTitle(target.value, titleLimit).value
                    if (target.value !== nextValue) target.value = nextValue
                  }}
                  onPaste={(event) => {
                    if (!titleLimit) return
                    event.preventDefault()
                    const pasted = event.clipboardData.getData('text')
                    const input = event.currentTarget
                    const start = input.selectionStart ?? title.length
                    const end = input.selectionEnd ?? title.length
                    const merged = `${title.slice(0, start)}${pasted}${title.slice(end)}`
                    applyTitleInput(merged)
                  }}
                  onBlur={(event) => {
                    applyTitleInput(event.target.value)
                  }}
                  className={`h-10 w-full rounded-lg border bg-[#020617] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1] ${titleError ? 'border-[#EF4444]' : 'border-[#1E293B]'}`}
                />
                {canRegeneratePublishCopy && (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => requestGeneratedTitle(true)}
                      disabled={titleGenerating || !titleContext}
                      className="inline-flex items-center gap-1.5 rounded-md border border-[#334155] bg-[#111827] px-2.5 py-1.5 text-body-xs text-[#CBD5E1] transition-colors hover:border-[#6366F1] hover:text-[#F8FAFC] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {titleGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                      {titleGenerating ? '生成中' : '重新生成文案'}
                    </button>
                    {titleCandidates.slice(0, 3).filter((item) => item && item !== title).map((candidate) => (
                      <button
                        key={candidate}
                        type="button"
                        onClick={() => {
                          setTitle(candidate)
                          setTitleNotice('')
                          setTitleTouched(true)
                        }}
                        className="max-w-full truncate rounded-md border border-[#1E293B] bg-[#020617] px-2.5 py-1.5 text-body-xs text-[#94A3B8] transition-colors hover:border-[#6366F1] hover:text-[#E0E7FF]"
                        title={candidate}
                      >
                        {candidate}
                      </button>
                    ))}
                  </div>
                )}
                {titleNotice && <div className="mt-1 text-body-xs text-[#FBBF24]">{titleNotice}</div>}
                {titleError && <div className="mt-1 text-body-xs text-[#FCA5A5]">{titleError}</div>}
              </label>
              <label>
                <span className="mb-1 block text-body-xs text-[#64748B]">正文 / 描述</span>
                <textarea
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  rows={9}
                  placeholder={loadingText ? '正在读取文案素材...' : '补充发布正文、视频描述或产品卖点'}
                  className="min-h-[220px] w-full resize-y rounded-lg border border-[#1E293B] bg-[#020617] px-3 py-3 text-body-sm leading-7 text-[#F1F5F9] outline-none focus:border-[#6366F1]"
                />
              </label>
              {mode === 'note' && images.length > 0 && (
                <section className="rounded-xl border border-[#1E293B] bg-[#020617] p-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <span className="text-body-xs font-medium text-[#94A3B8]">图文预览</span>
                    <span className="text-[11px] text-[#475569]">
                      {publishImageAnchors.length > 0 ? '图片已按 AI 建议插入' : '图片会随图文一起发布'}
                    </span>
                  </div>
                  <article className="max-h-[420px] overflow-auto rounded-lg border border-[#111827] bg-[#0B1120] p-4">
                    {(bodyParagraphs.length > 0 ? bodyParagraphs : ['正文内容将在这里预览。']).map((paragraph, index) => {
                      const after = index + 1
                      const inserted = anchoredImages.groups.get(after) || []
                      return (
                        <div key={`${after}-${paragraph.slice(0, 16)}`} className="mb-4 last:mb-0">
                          <p className="whitespace-pre-wrap break-words text-[14px] leading-7 tracking-[0.01em] text-[#CBD5E1]">
                            {paragraph}
                          </p>
                          {inserted.length > 0 && (
                            <div className="mt-3 grid gap-2 sm:grid-cols-2">
                              {inserted.map(({ asset, caption }) => (
                                <figure key={asset.id} className="overflow-hidden rounded-lg border border-[#1E293B] bg-[#020617]">
                                  <div className="aspect-[4/3] bg-[#111827]">
                                    <img src={assetUrl(asset)} alt={asset.name} className="h-full w-full object-cover" />
                                  </div>
                                  {(caption || asset.name) && (
                                    <figcaption className="truncate px-3 py-2 text-[11px] text-[#64748B]">
                                      {caption || asset.name}
                                    </figcaption>
                                  )}
                                </figure>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                    {unanchoredImages.length > 0 && (
                      <div className="mt-4 border-t border-[#1E293B] pt-4">
                        <div className="mb-2 text-[11px] text-[#64748B]">
                          {publishImageAnchors.length > 0 ? '未指定段落的配图' : '配图'}
                        </div>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {unanchoredImages.map((asset) => (
                            <figure key={asset.id} className="overflow-hidden rounded-lg border border-[#1E293B] bg-[#020617]">
                              <div className="aspect-[4/3] bg-[#111827]">
                                <img src={assetUrl(asset)} alt={asset.name} className="h-full w-full object-cover" />
                              </div>
                              <figcaption className="truncate px-3 py-2 text-[11px] text-[#64748B]">{asset.name}</figcaption>
                            </figure>
                          ))}
                        </div>
                      </div>
                    )}
                  </article>
                </section>
              )}
              <label>
                <span className="mb-1 block text-body-xs text-[#64748B]">标签</span>
                <input
                  value={tags}
                  onChange={(event) => setTags(event.target.value)}
                  className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#020617] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
                />
              </label>
              {!isTencentDesktopAssist && (
                <label className="flex items-center gap-2 text-body-xs text-[#94A3B8]">
                  <input type="checkbox" checked={headless} onChange={(event) => setHeadless(event.target.checked)} />
                  后台运行浏览器
                </label>
              )}
            </section>

            {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-3 text-body-sm text-[#FCA5A5]">{error}</div>}
          </div>
        </div>

        <div className="border-t border-[#1E293B] px-5 py-4">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit || submitting}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#10B981] px-4 py-2.5 text-body-sm font-medium text-white transition-colors hover:bg-[#059669] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            {isTencentDesktopAssist && tencentPublishMode === 'manual' ? '填好后等待我确认' : '确认发布'}
          </button>
        </div>
      </aside>
    </div>
  )
}

export default function AssetManagement() {
  const navigate = useNavigate()
  const [assets, setAssets] = useState<Asset[]>([])
  const [filter, setFilter] = useState<AssetType>('all')
  const [search, setSearch] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [previewAsset, setPreviewAsset] = useState<Asset | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [composeOpen, setComposeOpen] = useState(false)
  const [graphicOpen, setGraphicOpen] = useState(false)
  const [publishOpen, setPublishOpen] = useState(false)
  const [publishAssets, setPublishAssets] = useState<Asset[]>([])
  const [directGraphicDraftId, setDirectGraphicDraftId] = useState('')
  const [toast, setToast] = useState('')
  const [documentVersion, setDocumentVersion] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadAssets = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/publisher/materials')
      if (!res.ok) throw new Error('素材加载失败')
      const data = await res.json()
      setAssets(data.items || data.materials || [])
    } catch {
      setError('素材加载失败')
      setAssets([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAssets()
  }, [loadAssets])

  useEffect(() => {
    const handleDocumentUpdated = () => {
      setDocumentVersion((value) => value + 1)
      loadAssets()
    }
    window.addEventListener('szyg:document-updated', handleDocumentUpdated)
    return () => window.removeEventListener('szyg:document-updated', handleDocumentUpdated)
  }, [loadAssets])

  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setError(null)

    try {
      for (const file of Array.from(files)) {
        const formData = new FormData()
        formData.append('file', file)
        const res = await fetch('/api/publisher/materials/upload', {
          method: 'POST',
          body: formData,
        })
        if (!res.ok) throw new Error(`上传失败: ${file.name}`)
      }
      await loadAssets()
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }, [loadAssets])

  const handleDelete = useCallback(async (id: string) => {
    try {
      await fetch(`/api/publisher/materials/${encodeURIComponent(id)}`, { method: 'DELETE' })
      setAssets((prev) => prev.filter((item) => item.id !== id))
      setSelectedIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    } catch {
      setError('移除失败')
    }
  }, [])

  const handleBulkDelete = useCallback(async () => {
    if (selectedIds.size === 0) return
    try {
      for (const id of selectedIds) {
        await fetch(`/api/publisher/materials/${encodeURIComponent(id)}`, { method: 'DELETE' })
      }
      setAssets((prev) => prev.filter((item) => !selectedIds.has(item.id)))
      setSelectedIds(new Set())
    } catch {
      setError('批量移除失败')
    }
  }, [selectedIds])

  const handleOpen = useCallback(async (asset: Asset) => {
    if (!asset.url && !asset.path) return
    try {
      await revealGeneratedMedia({ path: asset.path, url: asset.url })
    } catch {
      setError('打开所在位置失败')
    }
  }, [])

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(''), 2200)
    return () => window.clearTimeout(timer)
  }, [toast])

  const selectedAssets = useMemo(
    () => assets.filter((asset) => selectedIds.has(asset.id)),
    [assets, selectedIds],
  )
  const assetsById = useMemo(() => new Map(assets.map((asset) => [asset.id, asset])), [assets])

  const handlePublishSelected = useCallback(async () => {
    if (selectedAssets.length === 0) return
    const expandedAssets = await expandGraphicDraftAssets(selectedAssets, assets)
    const images = expandedAssets.filter((asset) => asset.type === 'image')
    const videos = expandedAssets.filter((asset) => asset.type === 'video')
    const audios = expandedAssets.filter((asset) => asset.type === 'audio')
    if (expandedAssets.length === audios.length) {
      setToast('音频需要搭配图片、视频或文案后再发布')
      return
    }
    if (videos.length === 0 && images.length === 0) {
      setToast('发布至少需要一张图片或一个视频')
      return
    }
    setDirectGraphicDraftId(selectedAssets.length === 1 && isGraphicDraftAsset(selectedAssets[0]) ? selectedAssets[0].id : '')
    setPublishAssets(expandedAssets)
    setPublishOpen(true)
  }, [assets, selectedAssets])

  const filteredAssets = assets.filter((asset) => {
    if (filter !== 'all' && asset.type !== filter) return false
    if (search && !asset.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })
  const filteredAssetIds = filteredAssets.map((asset) => asset.id)
  const allFilteredSelected = filteredAssetIds.length > 0 && filteredAssetIds.every((id) => selectedIds.has(id))

  const toggleSelectAll = useCallback(() => {
    setSelectedIds((prev) => {
      if (allFilteredSelected) {
        const next = new Set(prev)
        filteredAssetIds.forEach((id) => next.delete(id))
        return next
      }
      return new Set([...prev, ...filteredAssetIds])
    })
  }, [allFilteredSelected, filteredAssetIds])

  const openGraphicCompose = useCallback(() => {
    if (selectedAssets.length > MAX_COMPOSE_ASSETS) {
      setToast(`最多${MAX_COMPOSE_ASSETS}个素材`)
      return
    }
    setGraphicOpen(true)
  }, [selectedAssets.length])

  const openVideoCompose = useCallback(() => {
    if (selectedAssets.length > MAX_COMPOSE_ASSETS) {
      setToast(`最多${MAX_COMPOSE_ASSETS}个素材`)
      return
    }
    setComposeOpen(true)
  }, [selectedAssets.length])
  const composeDisabled = selectedAssets.length === 0 || selectedAssets.length > MAX_COMPOSE_ASSETS
  const composeDisabledReason = selectedAssets.length > MAX_COMPOSE_ASSETS
    ? `一键图文和一键成片最多支持${MAX_COMPOSE_ASSETS}个素材`
    : selectedAssets.length === 0
      ? '请先选择素材'
      : ''

  const renderAssetMedia = (asset: Asset, mode: 'card' | 'preview') => {
    const url = assetUrl(asset)
    const Icon = TYPE_ICONS[asset.type] || FileImage
    const previewClass = 'max-w-full max-h-[60vh] mx-auto rounded-lg'

    if (!url) {
      return <Icon className={mode === 'card' ? 'w-12 h-12 text-[#334155]' : 'w-16 h-16 text-[#334155] mx-auto'} />
    }
    if (asset.type === 'image') {
      return <img src={url} alt={asset.name} className={mode === 'card' ? 'w-full h-full object-cover' : previewClass} />
    }
    if (asset.type === 'video') {
      return <video src={url} controls={mode === 'preview'} preload="metadata" muted={mode === 'card'} className={mode === 'card' ? 'w-full h-full object-cover' : previewClass} />
    }
    if (asset.type === 'audio') {
      return (
        <div className="flex h-full w-full flex-col items-center justify-center gap-3 px-4">
          <Icon className="w-12 h-12 text-[#6366F1]" />
          <audio src={url} controls className="w-full" onClick={(e) => e.stopPropagation()} />
        </div>
      )
    }
    if (asset.type === 'text') {
      if (isGraphicDraftAsset(asset)) {
        return <GraphicDraftPreview asset={asset} mode={mode} version={documentVersion} assetsById={assetsById} />
      }
      return <TextAssetPreview asset={asset} mode={mode} version={documentVersion} />
    }
    return <Icon className={mode === 'card' ? 'w-12 h-12 text-[#334155]' : 'w-16 h-16 text-[#334155] mx-auto'} />
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="flex flex-col h-full"
    >
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#1E293B]">
        <div className="flex items-center gap-3">
          <p className="text-body-sm text-[#94A3B8]">管理素材，选中后可组合生成或发布到渠道</p>
          {selectedIds.size > 0 && (
            <>
              <button
                onClick={handleBulkDelete}
                className="ml-2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#EF4444]/20 text-[#EF4444] hover:bg-[#EF4444]/30 text-body-sm transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                移除 ({selectedIds.size})
              </button>
              <button
                onClick={handlePublishSelected}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#10B981] text-white hover:bg-[#059669] text-body-sm transition-colors"
              >
                <Send className="w-4 h-4" />
                发布
              </button>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span title={composeDisabledReason}>
            <button
              onClick={openGraphicCompose}
              disabled={composeDisabled}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6366F1] hover:bg-[#5558E6] disabled:bg-[#1E293B] disabled:text-[#64748B] disabled:cursor-not-allowed text-body-sm text-white transition-colors"
            >
              <FileText className="w-4 h-4" />
              一键图文
            </button>
          </span>
          <span title={composeDisabledReason}>
            <button
              onClick={openVideoCompose}
              disabled={composeDisabled}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6366F1] hover:bg-[#5558E6] disabled:bg-[#1E293B] disabled:text-[#64748B] disabled:cursor-not-allowed text-body-sm text-white transition-colors"
            >
              <Sparkles className="w-4 h-4" />
              一键成片
            </button>
          </span>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-4 py-2 bg-[#6366F1] hover:bg-[#5558E6] disabled:opacity-50 rounded-lg text-body-sm text-white transition-colors"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            上传
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,video/*,audio/*,.txt,.md"
            className="hidden"
            onChange={(event) => handleUpload(event.target.files)}
          />
        </div>
      </div>

      <div className="border-b border-[#1E293B] px-6 py-3">
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索素材..."
              className="w-full pl-9 pr-4 py-2 bg-[#0B0F1A] border border-[#1E293B] rounded-lg text-body-sm text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#6366F1]"
            />
          </div>

          <div className="flex gap-1">
            {ASSET_TYPE_FILTERS.map((item) => (
              <button
                key={item.key}
                onClick={() => setFilter(item.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-body-xs transition-all ${
                  filter === item.key
                    ? 'bg-[#6366F1]/20 text-[#6366F1] border border-[#6366F1]/30'
                    : 'text-[#94A3B8] hover:bg-[#1E293B]'
                }`}
              >
                <item.icon className="w-3.5 h-3.5" />
                {item.label}
              </button>
            ))}
          </div>

          <div className="flex gap-1 border-l border-[#1E293B] pl-4">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-md transition-colors ${
                viewMode === 'grid' ? 'bg-[#1E293B] text-[#F1F5F9]' : 'text-[#64748B] hover:text-[#94A3B8]'
              }`}
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 rounded-md transition-colors ${
                viewMode === 'list' ? 'bg-[#1E293B] text-[#F1F5F9]' : 'text-[#64748B] hover:text-[#94A3B8]'
              }`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="mt-2 flex max-w-md items-center gap-3">
          <button
            onClick={toggleSelectAll}
            disabled={filteredAssetIds.length === 0}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-body-xs transition-all disabled:cursor-not-allowed disabled:opacity-40 ${
              allFilteredSelected
                ? 'bg-[#1E293B] text-[#CBD5E1] border border-[#334155] hover:bg-[#263449]'
                : 'text-[#94A3B8] border border-transparent hover:bg-[#1E293B]'
            }`}
          >
            <Check className="w-3.5 h-3.5" />
            {allFilteredSelected ? '取消全选' : '全选'}
          </button>
          <span className="text-body-xs text-[#64748B]">
            当前列表 {filteredAssetIds.length} 个，已选 {selectedIds.size} 个
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {error && (
          <div className="mb-4 glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-[#EF4444] hover:text-[#DC2626]">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 text-[#6366F1] animate-spin" />
          </div>
        ) : filteredAssets.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <FolderOpen className="w-16 h-16 text-[#334155] mb-4" />
            <p className="text-body-lg text-[#94A3B8] mb-2">暂无素材</p>
            <p className="text-body-sm text-[#64748B] mb-4">点击上传按钮添加素材</p>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-4 py-2 bg-[#6366F1] hover:bg-[#5558E6] rounded-lg text-body-sm text-white transition-colors"
            >
              <Upload className="w-4 h-4" />
              上传素材
            </button>
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {filteredAssets.map((asset) => {
              const graphicDraft = isGraphicDraftAsset(asset)
              return (
                <div
                  key={asset.id}
                  className={`glass-card rounded-card-lg border overflow-hidden cursor-pointer transition-all hover:border-[#6366F1]/50 ${
                    selectedIds.has(asset.id)
                      ? 'border-[#6366F1] ring-1 ring-[#6366F1]/30'
                      : graphicDraft
                        ? 'border-[#38BDF8]/30 hover:border-[#38BDF8]/60'
                        : 'border-[#1E293B]'
                  }`}
                  onClick={() => setPreviewAsset(asset)}
                >
                  <div className="aspect-square bg-[#0B0F1A] flex items-center justify-center relative">
                    {renderAssetMedia(asset, 'card')}
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        toggleSelect(asset.id)
                      }}
                      className={`absolute top-2 left-2 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        selectedIds.has(asset.id)
                          ? 'bg-[#6366F1] border-[#6366F1]'
                          : 'border-[#475569] bg-[#0B0F1A]/80'
                      }`}
                    >
                      {selectedIds.has(asset.id) && (
                        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>
                  </div>

                  <div className="p-3">
                    <div className="flex items-center gap-2">
                      {graphicDraft && (
                        <span className="shrink-0 rounded bg-[#0EA5E9]/15 px-1.5 py-0.5 text-[10px] text-[#BAE6FD]">图文</span>
                      )}
                      <p className="min-w-0 truncate text-body-sm text-[#F1F5F9]">{asset.name}</p>
                    </div>
                    <p className="text-body-xs text-[#64748B] mt-1">
                      {graphicDraft ? '图文发布草稿' : formatFileSize(asset.size)}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredAssets.map((asset) => {
              const graphicDraft = isGraphicDraftAsset(asset)
              const Icon = graphicDraft ? Newspaper : (TYPE_ICONS[asset.type] || FileImage)
              return (
                <div
                  key={asset.id}
                  className={`glass-card rounded-card-lg border flex items-center gap-4 px-4 py-3 cursor-pointer transition-all hover:border-[#6366F1]/50 ${
                    selectedIds.has(asset.id)
                      ? 'border-[#6366F1]'
                      : graphicDraft
                        ? 'border-[#38BDF8]/30 hover:border-[#38BDF8]/60'
                        : 'border-[#1E293B]'
                  }`}
                  onClick={() => setPreviewAsset(asset)}
                >
                  <button
                    onClick={(event) => {
                      event.stopPropagation()
                      toggleSelect(asset.id)
                    }}
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                      selectedIds.has(asset.id) ? 'bg-[#6366F1] border-[#6366F1]' : 'border-[#475569]'
                    }`}
                  >
                    {selectedIds.has(asset.id) && (
                      <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>

                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${graphicDraft ? 'bg-[#0EA5E9]/15' : 'bg-[#1E293B]'}`}>
                    <Icon className={`w-5 h-5 ${graphicDraft ? 'text-[#7DD3FC]' : 'text-[#64748B]'}`} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="min-w-0 truncate text-body-sm text-[#F1F5F9]">{asset.name}</p>
                      {graphicDraft && (
                        <span className="shrink-0 rounded bg-[#0EA5E9]/15 px-1.5 py-0.5 text-[10px] text-[#BAE6FD]">图文草稿</span>
                      )}
                    </div>
                    <p className="text-body-xs text-[#64748B]">{graphicDraft ? '包含正文、标签、配图顺序和发布建议' : formatFileSize(asset.size)}</p>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        handleOpen(asset)
                      }}
                      className="p-2 rounded-lg hover:bg-[#1E293B] text-[#64748B] hover:text-[#F1F5F9] transition-colors"
                    >
                      <FolderOpen className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        handleDelete(asset.id)
                      }}
                      className="p-2 rounded-lg hover:bg-[#EF4444]/20 text-[#64748B] hover:text-[#EF4444] transition-colors"
                      title="从素材管理与发布中移除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {previewAsset && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setPreviewAsset(null)}
        >
          <div
            className="glass-card rounded-card-xl border border-[#1E293B] max-w-4xl max-h-[90vh] overflow-hidden"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#1E293B]">
              <div className="flex items-center gap-3">
                {(() => {
                  const Icon = isGraphicDraftAsset(previewAsset) ? Newspaper : (TYPE_ICONS[previewAsset.type] || FileImage)
                  return <Icon className="w-5 h-5 text-[#6366F1]" />
                })()}
                <div>
                  <p className="text-body-md text-[#F1F5F9] font-medium">{previewAsset.name}</p>
                  <p className="text-body-xs text-[#64748B]">
                    {formatFileSize(previewAsset.size)} · {new Date(previewAsset.created_at).toLocaleDateString('zh-CN')}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setPreviewAsset(null)}
                className="p-2 rounded-lg hover:bg-[#1E293B] text-[#64748B] hover:text-[#F1F5F9] transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6">
              {renderAssetMedia(previewAsset, 'preview')}
            </div>

            <div className="flex justify-end gap-2 px-6 py-4 border-t border-[#1E293B]">
              <button
                onClick={() => handleOpen(previewAsset)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#1E293B] hover:bg-[#334155] text-[#F1F5F9] text-body-sm transition-colors"
              >
                <FolderOpen className="w-4 h-4" />
                所在位置
              </button>
              <button
                onClick={() => {
                  handleDelete(previewAsset.id)
                  setPreviewAsset(null)
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#EF4444]/20 hover:bg-[#EF4444]/30 text-[#EF4444] text-body-sm transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                移除
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-5 left-5 z-[60] rounded-lg border border-[#6366F1]/40 bg-[#111827] px-4 py-2 text-body-sm text-[#E0E7FF] shadow-2xl">
          {toast}
        </div>
      )}

      {graphicOpen && (
        <ComposeGraphicDrawer
          assets={selectedAssets}
          onClose={() => setGraphicOpen(false)}
          onSaved={loadAssets}
        />
      )}

      {composeOpen && (
        <ComposeVideoDrawer
          assets={selectedAssets}
          onClose={() => setComposeOpen(false)}
          onGenerated={loadAssets}
        />
      )}

      {publishOpen && (
        <PublishSelectedDrawer
          assets={publishAssets}
          directGraphicDraftId={directGraphicDraftId}
          onClose={() => {
            setPublishOpen(false)
            setDirectGraphicDraftId('')
          }}
          onSubmitted={(result) => {
            setPublishOpen(false)
            setDirectGraphicDraftId('')
            setSelectedIds(new Set())
            const isTencentAssist = result.run?.platform === 'tencent' && result.run?.executor_type === 'desktop'
            setToast(isTencentAssist || result.task_id?.startsWith('manual_tencent_') ? '视频号发布任务已提交，可在发布看板查看结果' : '发布任务已创建，可在发布看板查看结果')
            navigate('/publish/center')
          }}
        />
      )}
    </motion.div>
  )
}

const GRAPHIC_STATE_KEY = 'szyg.assetManagement.composeGraphicState'

function questionDefaults(questions: ComposeQuestion[]): Record<string, string> {
  const defaults: Record<string, string> = {}
  questions.forEach((question) => {
    defaults[question.id] = question.recommended || question.options[0]?.value || ''
  })
  return defaults
}

function ComposeGraphicDrawer({
  assets,
  onClose,
  onSaved,
}: {
  assets: Asset[]
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const [step, setStep] = useState<'analyze' | 'questions' | 'draft' | 'saved'>('analyze')
  const [analysis, setAnalysis] = useState<GraphicAnalyzeResult | null>(null)
  const [prepared, setPrepared] = useState<GraphicPrepareResult | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [userInstruction, setUserInstruction] = useState('')
  const [draft, setDraft] = useState<GraphicDraft | null>(null)
  const [savedPath, setSavedPath] = useState('')
  const [loading, setLoading] = useState<'analyze' | 'prepare' | 'save' | null>('analyze')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [selectedAnalysisItem, setSelectedAnalysisItem] = useState<GraphicAnalyzeResult['assets'][number] | null>(null)

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(GRAPHIC_STATE_KEY) || '{}')
      if (saved?.step) setStep(saved.step)
      if (saved?.analysis) setAnalysis(saved.analysis)
      if (saved?.prepared) {
        setPrepared(saved.prepared)
        setDraft(saved.prepared.draft || null)
      }
      if (saved?.answers) setAnswers(saved.answers)
      if (saved?.userInstruction) setUserInstruction(saved.userInstruction)
      if (saved?.savedPath) setSavedPath(saved.savedPath)
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    localStorage.setItem(GRAPHIC_STATE_KEY, JSON.stringify({ step, analysis, prepared: draft && prepared ? { ...prepared, draft } : prepared, answers, userInstruction, savedPath }))
  }, [step, analysis, prepared, draft, answers, userInstruction, savedPath])

  const runAnalyze = useCallback(async (instruction = '') => {
    setLoading('analyze')
    setError('')
    setAnalysis(null)
    setPrepared(null)
    setDraft(null)
    setSavedPath('')
    try {
      const data = await analyzeGraphicComposition(assets.map((asset) => ({
        id: asset.id,
        name: asset.name,
        type: asset.type,
        url: asset.url,
        path: asset.path,
      })), instruction)
      setAnalysis(data)
      setAnswers(questionDefaults(data.questions))
      setStep('questions')
    } catch (err) {
      setError(getErrorMessage(err, '素材理解失败'))
    } finally {
      setLoading(null)
    }
  }, [assets])

  useEffect(() => {
    if (!analysis && assets.length > 0) {
      runAnalyze()
    }
  }, [analysis, assets.length, runAnalyze])

  const handlePrepare = useCallback(async () => {
    if (!analysis) return
    setLoading('prepare')
    setError('')
    try {
      const data = await prepareGraphicComposition({
        analysis,
        answers: Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer })),
        user_instruction: userInstruction,
      })
      setPrepared(data)
      setDraft(data.draft)
      setStep('draft')
    } catch (err) {
      setError(getErrorMessage(err, '图文草稿生成失败'))
    } finally {
      setLoading(null)
    }
  }, [analysis, answers, userInstruction])

  const handleRegenerateAnalysis = useCallback(() => {
    runAnalyze(userInstruction)
  }, [runAnalyze, userInstruction])

  const updateDraft = useCallback((patch: Partial<GraphicDraft>) => {
    setDraft((current) => current ? { ...current, ...patch } : current)
  }, [])

  useEffect(() => {
    if (!draft?.title) return
    const normalized = normalizePublishTitle(draft.title, GRAPHIC_DRAFT_TITLE_LIMIT)
    if (normalized.value !== draft.title) {
      updateDraft({ title: normalized.value })
      setNotice(`标题已自动截断为${GRAPHIC_DRAFT_TITLE_LIMIT}字符`)
    }
  }, [draft?.title, updateDraft])

  const graphicPreviewAssets = useMemo(() => {
    if (!draft) return assets.filter((asset) => asset.type === 'image' || asset.type === 'video')
    const visualAssets = assets.filter((asset) => asset.type === 'image' || asset.type === 'video')
    const byId = new Map(visualAssets.map((asset) => [asset.id, asset]))
    const ordered = draft.image_order.map((id) => byId.get(id)).filter((asset): asset is Asset => Boolean(asset))
    const extras = visualAssets.filter((asset) => !ordered.some((item) => item.id === asset.id))
    return [...ordered, ...extras]
  }, [assets, draft])

  const draftParagraphs = useMemo(() => {
    return (draft?.body || '').split(/\n{2,}|\r?\n/).map((item) => item.trim()).filter(Boolean)
  }, [draft?.body])

  const graphicAssetsById = useMemo(() => {
    return new Map(graphicPreviewAssets.map((asset) => [asset.id, asset]))
  }, [graphicPreviewAssets])

  const graphicAnchorsByParagraph = useMemo(() => {
    const grouped = new Map<number, Array<{ asset: Asset; caption: string }>>()
    const anchors = draft?.image_anchors || []
    anchors.forEach((anchor) => {
      const asset = graphicAssetsById.get(anchor.asset_id)
      if (!asset) return
      const paragraph = Math.max(0, Number(anchor.anchor_after_paragraph) || 0)
      const list = grouped.get(paragraph) || []
      list.push({ asset, caption: anchor.caption || '' })
      grouped.set(paragraph, list)
    })
    return grouped
  }, [draft?.image_anchors, graphicAssetsById])

  const updateDraftTitle = useCallback((raw: string) => {
    const normalized = normalizePublishTitle(raw, GRAPHIC_DRAFT_TITLE_LIMIT)
    updateDraft({ title: normalized.value })
    setNotice(normalized.truncated ? `标题已自动截断为${GRAPHIC_DRAFT_TITLE_LIMIT}字符` : '')
  }, [updateDraft])

  const updateImageAnchor = useCallback((assetId: string, patch: { anchor_after_paragraph?: number; caption?: string }) => {
    setDraft((current) => {
      if (!current) return current
      const anchors = [...(current.image_anchors || [])]
      const index = anchors.findIndex((item) => item.asset_id === assetId)
      const next = {
        asset_id: assetId,
        anchor_after_paragraph: 1,
        caption: '',
        ...(index >= 0 ? anchors[index] : {}),
        ...patch,
      }
      if (index >= 0) anchors[index] = next
      else anchors.push(next)
      return { ...current, image_anchors: anchors }
    })
  }, [])

  const renderAnchoredAssets = (paragraph: number) => {
    const anchored = graphicAnchorsByParagraph.get(paragraph) || []
    if (anchored.length === 0) return null
    return (
      <div className="my-4 grid gap-3" style={{ gridTemplateColumns: anchored.length === 1 ? '1fr' : 'repeat(2, minmax(0, 1fr))' }}>
        {anchored.map(({ asset, caption }) => (
          <figure key={`${paragraph}-${asset.id}`} className="overflow-hidden rounded-xl border border-[#1E293B] bg-[#0B0F1A]">
            <div className="aspect-[4/3] bg-[#111827]">
              {asset.type === 'image' ? (
                <img src={assetUrl(asset)} alt={asset.name} className="h-full w-full object-cover" />
              ) : (
                <video src={assetUrl(asset)} muted preload="metadata" className="h-full w-full object-cover" />
              )}
            </div>
            <figcaption className="px-3 py-2 text-[11px] leading-5 text-[#94A3B8]">
              {caption || asset.name}
            </figcaption>
          </figure>
        ))}
      </div>
    )
  }

  const handleSave = useCallback(async () => {
    if (!draft || !prepared) return
    setLoading('save')
    setError('')
    try {
      const result = await saveGraphicComposition({
        draft,
        used_assets: prepared.used_assets,
        filename: draft.title,
      })
      setSavedPath(result.path || result.name)
      setStep('saved')
      await onSaved()
    } catch (err) {
      setError(getErrorMessage(err, '图文草稿保存失败'))
    } finally {
      setLoading(null)
    }
  }, [draft, prepared, onSaved])

  const renderQuestion = (question: ComposeQuestion) => (
    <div key={question.id} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
      <div className="mb-3 text-body-sm font-medium text-[#F1F5F9]">{question.question}</div>
      {question.options.length > 0 ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {question.options.map((option) => {
            const selected = answers[question.id] === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setAnswers((prev) => ({ ...prev, [question.id]: option.value }))}
                className={`rounded-lg border px-3 py-2 text-left text-body-sm transition-all ${
                  selected
                    ? 'border-[#6366F1]/70 bg-[#6366F1]/20 text-[#E0E7FF]'
                    : 'border-[#1E293B] bg-[#111827] text-[#94A3B8] hover:border-[#475569] hover:text-[#F1F5F9]'
                }`}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      ) : (
        <textarea
          value={answers[question.id] || ''}
          onChange={(event) => setAnswers((prev) => ({ ...prev, [question.id]: event.target.value }))}
          className="h-20 w-full resize-none rounded-lg border border-[#1E293B] bg-[#111827] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
        />
      )}
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-5xl flex-col border-l border-[#1E293B] bg-[#020617] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#1E293B] px-6 py-4">
          <div>
            <div className="flex items-center gap-2 text-heading-sm text-[#F1F5F9]">
              <FileText className="h-5 w-5 text-[#A5B4FC]" />
              一键图文
            </div>
            <div className="mt-1 text-body-xs text-[#64748B]">
              已选 {assets.length} 个素材 · AI 理解素材 · 生成发布草稿包
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-[#64748B] transition-colors hover:bg-[#1E293B] hover:text-[#F1F5F9]">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid flex-1 min-h-0 grid-cols-[280px_1fr]">
          <aside className="overflow-auto border-r border-[#1E293B] p-4">
            <div className="mb-3 text-body-xs text-[#64748B]">已选素材</div>
            <div className="space-y-3">
              {assets.map((asset) => (
                <div key={asset.id} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-3">
                  <div className="aspect-video overflow-hidden rounded-md bg-[#111827]">
                    {asset.type === 'image' ? (
                      <img src={assetUrl(asset)} alt={asset.name} className="h-full w-full object-cover" />
                    ) : asset.type === 'video' ? (
                      <video src={assetUrl(asset)} muted preload="metadata" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center">
                        {(() => {
                          const Icon = TYPE_ICONS[asset.type] || FileText
                          return <Icon className="h-8 w-8 text-[#6366F1]" />
                        })()}
                      </div>
                    )}
                  </div>
                  <div className="mt-2 truncate text-body-xs text-[#F1F5F9]">{asset.name}</div>
                  <div className="text-[11px] text-[#64748B]">{asset.type}</div>
                </div>
              ))}
            </div>
          </aside>

          <main className="min-h-0 overflow-auto p-6">
            <div className="mb-5 grid grid-cols-4 gap-2">
              {[
                ['analyze', '素材理解'],
                ['questions', '确认方向'],
                ['draft', '图文草稿'],
                ['saved', '保存素材'],
              ].map(([key, label], index) => (
                <div
                  key={key}
                  className={`rounded-lg border px-3 py-2 text-center text-body-xs ${
                    step === key
                      ? 'border-[#6366F1]/70 bg-[#6366F1]/20 text-[#E0E7FF]'
                      : 'border-[#1E293B] bg-[#0B0F1A] text-[#64748B]'
                  }`}
                >
                  {index + 1}. {label}
                </div>
              ))}
            </div>

            {error && (
              <div className="mb-4 rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-body-sm text-[#FCA5A5]">
                {error}
              </div>
            )}

            {loading === 'analyze' && (
              <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-[#1E293B] bg-[#0B0F1A]">
                <Loader2 className="mb-4 h-8 w-8 animate-spin text-[#6366F1]" />
                <div className="text-body-md text-[#F1F5F9]">AI 正在理解素材</div>
              </div>
            )}

            {analysis && step !== 'analyze' && (
              <div className="mb-4 rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                <div className="mb-2 flex items-center gap-2 text-body-sm font-medium text-[#F1F5F9]">
                  <Check className="h-4 w-4 text-[#10B981]" />
                  素材理解结果
                </div>
                <p className="text-body-sm leading-6 text-[#CBD5E1]">{analysis.summary || '已完成素材理解。'}</p>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {analysis.assets.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setSelectedAnalysisItem(item)}
                      className="rounded-md border border-[#1E293B] bg-[#111827] p-3 text-left transition-all hover:border-[#6366F1]/60 hover:bg-[#162033] focus:outline-none focus:ring-1 focus:ring-[#6366F1]/60"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-body-xs text-[#F1F5F9]">{item.name}</span>
                        <span className={`shrink-0 rounded px-2 py-0.5 text-[11px] ${item.status === 'success' ? 'bg-[#10B981]/15 text-[#86EFAC]' : 'bg-[#EF4444]/15 text-[#FCA5A5]'}`}>
                          {item.status}
                        </span>
                      </div>
                      <div className="mt-1 text-[11px] text-[#A5B4FC]">{item.role || item.type}</div>
                      <div className="mt-2 line-clamp-3 text-body-xs leading-5 text-[#94A3B8]">{item.summary || item.error || '暂无摘要'}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {step === 'questions' && analysis && (
              <div className="space-y-4">
                <div className="text-body-sm text-[#94A3B8]">根据素材内容，AI 只需要你确认几个图文方向。</div>
                {analysis.questions.map(renderQuestion)}
                <label className="block">
                  <span className="mb-2 block text-body-xs text-[#64748B]">补充要求</span>
                  <textarea
                    value={userInstruction}
                    onChange={(event) => setUserInstruction(event.target.value)}
                    placeholder="例如：偏小红书种草语气，突出门店优惠，不要太夸张。"
                    className="h-24 w-full resize-none rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none placeholder:text-[#475569] focus:border-[#6366F1]"
                  />
                </label>
                <div className="flex items-center justify-between gap-3">
                  <button
                    onClick={handlePrepare}
                    disabled={loading === 'prepare'}
                    className="inline-flex items-center gap-2 rounded-lg bg-[#6366F1] px-5 py-2.5 text-body-sm text-white transition-colors hover:bg-[#5558E6] disabled:opacity-50"
                  >
                    {loading === 'prepare' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    生成图文草稿
                  </button>
                  <button
                    onClick={handleRegenerateAnalysis}
                    disabled={loading === 'analyze'}
                    className="inline-flex items-center gap-2 rounded-lg border border-[#334155] bg-[#111827] px-4 py-2.5 text-body-sm text-[#CBD5E1] transition-colors hover:border-[#6366F1]/60 hover:text-[#F1F5F9] disabled:opacity-50"
                  >
                    {loading === 'analyze' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
                    重新生成
                  </button>
                </div>
              </div>
            )}

            {step === 'draft' && draft && (
              <div className="space-y-4">
                <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                  <div className="mb-2 text-body-sm font-medium text-[#F1F5F9]">图文草稿包</div>
                  <p className="text-body-sm leading-6 text-[#CBD5E1]">{prepared?.summary || '已生成可发布的图文草稿。'}</p>
                </div>
                <div className="grid gap-4 xl:grid-cols-[minmax(320px,0.9fr)_minmax(420px,1.1fr)]">
                  <section className="overflow-hidden rounded-xl border border-[#1E293B] bg-[#0B0F1A]">
                    <div className="flex items-center justify-between border-b border-[#1E293B] px-4 py-3">
                      <div className="text-body-sm font-medium text-[#F1F5F9]">图文预览</div>
                      <div className="text-[11px] text-[#64748B]">{graphicPreviewAssets.length} 个视觉素材</div>
                    </div>
                    <div className="p-4">
                      <article className="mt-4 rounded-lg border border-[#1E293B] bg-[#111827] p-4">
                        <h3 className="text-heading-sm leading-7 text-[#F8FAFC]">{draft.title || '未命名图文标题'}</h3>
                        {renderAnchoredAssets(0)}
                        <div className="mt-3 space-y-4 text-body-sm leading-7 text-[#CBD5E1]">
                          {draftParagraphs.length > 0 ? draftParagraphs.map((paragraph, index) => (
                            <div key={`${index}-${paragraph.slice(0, 12)}`}>
                              <p className="whitespace-pre-wrap break-words">{paragraph}</p>
                              {renderAnchoredAssets(index + 1)}
                            </div>
                          )) : <p>暂无正文</p>}
                        </div>
                        {draft.tags.length > 0 && (
                          <div className="mt-4 flex flex-wrap gap-2">
                            {draft.tags.map((tag) => (
                              <span key={tag} className="rounded-full bg-[#6366F1]/15 px-2.5 py-1 text-[11px] text-[#C7D2FE]">#{tag}</span>
                            ))}
                          </div>
                        )}
                      </article>
                      {draft.publish_notes && (
                        <div className="mt-3 rounded-lg border border-[#1E293B] bg-[#111827] p-3 text-body-xs leading-5 text-[#94A3B8]">
                          {draft.publish_notes}
                        </div>
                      )}
                    </div>
                  </section>

                  <section className="space-y-3">
                    <label className="block">
                      <span className="mb-2 flex items-center justify-between gap-3 text-body-xs text-[#64748B]">
                        <span>标题</span>
                        <span>{Array.from(draft.title || '').length}/{GRAPHIC_DRAFT_TITLE_LIMIT}</span>
                      </span>
                      <input
                        value={draft.title}
                        maxLength={GRAPHIC_DRAFT_TITLE_LIMIT}
                        onChange={(event) => updateDraftTitle(event.target.value)}
                        onPaste={(event) => {
                          event.preventDefault()
                          const input = event.currentTarget
                          const start = input.selectionStart ?? draft.title.length
                          const end = input.selectionEnd ?? draft.title.length
                          const pasted = event.clipboardData.getData('text')
                          updateDraftTitle(`${draft.title.slice(0, start)}${pasted}${draft.title.slice(end)}`)
                        }}
                        className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
                      />
                      {notice && <div className="mt-1 text-body-xs text-[#FBBF24]">{notice}</div>}
                    </label>
                    <label className="block">
                      <span className="mb-2 block text-body-xs text-[#64748B]">正文</span>
                      <textarea
                        value={draft.body}
                        onChange={(event) => updateDraft({ body: event.target.value })}
                        className="h-52 w-full resize-none rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm leading-6 text-[#F1F5F9] outline-none focus:border-[#6366F1]"
                      />
                    </label>
                    <div className="grid gap-3 md:grid-cols-2">
                      <label className="block">
                        <span className="mb-2 block text-body-xs text-[#64748B]">标签</span>
                        <input
                          value={draft.tags.join('，')}
                          onChange={(event) => updateDraft({ tags: event.target.value.split(/[，,]/).map((item) => item.trim().replace(/^#/, '')).filter(Boolean) })}
                          className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
                        />
                      </label>
                      <label className="block">
                        <span className="mb-2 block text-body-xs text-[#64748B]">平台建议</span>
                        <input
                          value={draft.platform_suggestion.join('，')}
                          onChange={(event) => updateDraft({ platform_suggestion: event.target.value.split(/[，,]/).map((item) => item.trim()).filter(Boolean) })}
                          className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
                        />
                      </label>
                    </div>
                    <label className="block">
                      <span className="mb-2 block text-body-xs text-[#64748B]">配图顺序</span>
                      <input
                        value={draft.image_order.join('，')}
                        onChange={(event) => updateDraft({ image_order: event.target.value.split(/[，,]/).map((item) => item.trim()).filter(Boolean) })}
                        className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
                      />
                    </label>
                    {graphicPreviewAssets.length > 0 && (
                      <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-3">
                        <div className="mb-3 text-body-xs text-[#64748B]">配图位置</div>
                        <div className="space-y-3">
                          {graphicPreviewAssets.map((asset) => {
                            const anchor = (draft.image_anchors || []).find((item) => item.asset_id === asset.id)
                            return (
                              <div key={asset.id} className="grid gap-2 rounded-lg border border-[#1E293B] bg-[#111827] p-3 md:grid-cols-[minmax(0,1fr)_120px]">
                                <div className="min-w-0">
                                  <div className="truncate text-body-xs text-[#F1F5F9]">{asset.name}</div>
                                  <input
                                    value={anchor?.caption || ''}
                                    onChange={(event) => updateImageAnchor(asset.id, { caption: event.target.value })}
                                    placeholder="配图说明"
                                    className="mt-2 w-full rounded-md border border-[#1E293B] bg-[#0B0F1A] px-2 py-1.5 text-body-xs text-[#CBD5E1] outline-none focus:border-[#6366F1]"
                                  />
                                </div>
                                <label className="block">
                                  <span className="mb-1 block text-[11px] text-[#64748B]">插入段落后</span>
                                  <input
                                    type="number"
                                    min={0}
                                    max={Math.max(1, draftParagraphs.length)}
                                    value={anchor?.anchor_after_paragraph ?? 1}
                                    onChange={(event) => updateImageAnchor(asset.id, { anchor_after_paragraph: Math.max(0, Math.min(Math.max(1, draftParagraphs.length), Number(event.target.value) || 0)) })}
                                    className="h-9 w-full rounded-md border border-[#1E293B] bg-[#0B0F1A] px-2 text-body-xs text-[#CBD5E1] outline-none focus:border-[#6366F1]"
                                  />
                                </label>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}
                    <label className="block">
                      <span className="mb-2 block text-body-xs text-[#64748B]">发布建议</span>
                      <textarea
                        value={draft.publish_notes}
                        onChange={(event) => updateDraft({ publish_notes: event.target.value })}
                        className="h-24 w-full resize-none rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm leading-6 text-[#F1F5F9] outline-none focus:border-[#6366F1]"
                      />
                    </label>
                  </section>
                </div>
                <button
                  onClick={handleSave}
                  disabled={loading === 'save'}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#6366F1] px-5 py-2.5 text-body-sm text-white transition-colors hover:bg-[#5558E6] disabled:opacity-50"
                >
                  {loading === 'save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                  保存到素材管理
                </button>
              </div>
            )}

            {step === 'saved' && (
              <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-[#1E293B] bg-[#0B0F1A] text-center">
                <Check className="mb-4 h-10 w-10 text-[#10B981]" />
                <div className="text-body-lg text-[#F1F5F9]">图文草稿已保存</div>
                <div className="mt-2 max-w-xl break-all text-body-sm text-[#64748B]">{savedPath}</div>
              </div>
            )}
          </main>
        </div>

        {selectedAnalysisItem && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center bg-black/55 px-6 backdrop-blur-sm"
            onClick={() => setSelectedAnalysisItem(null)}
          >
            <div
              className="w-full max-w-2xl rounded-xl border border-[#1E293B] bg-[#020617] shadow-2xl"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-4 border-b border-[#1E293B] px-5 py-4">
                <div className="min-w-0">
                  <div className="truncate text-body-md font-medium text-[#F1F5F9]">{selectedAnalysisItem.name}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="rounded bg-[#6366F1]/15 px-2 py-0.5 text-[#A5B4FC]">{selectedAnalysisItem.role || selectedAnalysisItem.type}</span>
                    <span className={`rounded px-2 py-0.5 ${selectedAnalysisItem.status === 'success' ? 'bg-[#10B981]/15 text-[#86EFAC]' : 'bg-[#EF4444]/15 text-[#FCA5A5]'}`}>
                      {selectedAnalysisItem.status}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedAnalysisItem(null)}
                  className="rounded-lg p-2 text-[#64748B] transition-colors hover:bg-[#1E293B] hover:text-[#F1F5F9]"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="max-h-[55vh] overflow-auto px-5 py-4">
                <div className="whitespace-pre-wrap break-words text-body-sm leading-7 text-[#CBD5E1]">
                  {selectedAnalysisItem.summary || selectedAnalysisItem.error || '暂无摘要'}
                </div>
              </div>
              <div className="flex justify-end border-t border-[#1E293B] px-5 py-4">
                <button
                  type="button"
                  onClick={() => setSelectedAnalysisItem(null)}
                  className="rounded-lg bg-[#1E293B] px-4 py-2 text-body-sm text-[#F1F5F9] transition-colors hover:bg-[#334155]"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

type ComposeTaskItem = {
  taskId: string
  status: string
  progress: number
  model: string
  unsupportedFeatures?: string[]
  videoUrl?: string
  downloadUrl?: string
  localPath?: string
  error?: string
}

const COMPOSE_STATE_KEY = 'szyg.assetManagement.composeVideoState'
const COMPOSE_STATE_VERSION = 3
const DEFAULT_COMPOSE_MODEL = 'doubao-seedance-1.5-pro'

function normalizeTaskStatus(status: string): string {
  if (status === 'succeed') return 'succeeded'
  return status || 'queued'
}

function taskStatusLabel(status: string): string {
  return {
    queued: '等待生成',
    running: '正在生成',
    processing: '正在生成',
    succeeded: '生成完成',
    failed: '生成失败',
  }[normalizeTaskStatus(status)] || '处理中'
}

function videoQualityLabel(modelId: string, label = ''): string {
  const labels: Record<string, string> = {
    'doubao-seedance-1.5-pro': '基础模式',
    'doubao-seedance-2.0-fast': '快速模式',
    'doubao-seedance-2.0': '高质量模式',
    'doubao-seedance-2.5': '专业模式',
  }
  if (labels[modelId]) return labels[modelId]
  return /seedance|doubao|model|endpoint|provider/i.test(label) ? '智能模式' : (label || '智能模式')
}

function formatUnsupportedFeature(feature: string): string {
  const labels: Record<string, string> = {
    audio_reference_input: '音频参考输入',
    visual_reference_input: '当前生成服务不支持直接输入参考图片或视频，已使用 AI 理解后的素材信息生成',
    visual_reference_upload: '视觉参考素材上传',
  }
  return labels[feature] || feature
}

function defaultComposeParams(): ComposeVideoParams {
  return {
    platform: 'douyin_xhs',
    scenario: 'product_seed',
    duration: 15,
    size: '720p',
    ratio: '9:16',
    native_audio: true,
    count: 1,
    user_instruction: '',
    model: DEFAULT_COMPOSE_MODEL,
  }
}

function normalizeComposeParams(params?: Partial<ComposeVideoParams>, savedVersion = COMPOSE_STATE_VERSION): ComposeVideoParams {
  const next = { ...defaultComposeParams(), ...(params || {}) }
  if (savedVersion < COMPOSE_STATE_VERSION && next.model === 'doubao-seedance-2.0') {
    next.model = DEFAULT_COMPOSE_MODEL
  }
  return next
}

function ComposeVideoDrawer({
  assets,
  onClose,
  onGenerated,
}: {
  assets: Asset[]
  onClose: () => void
  onGenerated: () => Promise<void>
}) {
  const [step, setStep] = useState<'analyze' | 'questions' | 'prepare' | 'tasks'>('analyze')
  const [analysis, setAnalysis] = useState<ComposeAnalyzeResult | null>(null)
  const [prepared, setPrepared] = useState<ComposePrepareResult | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [params, setParams] = useState<ComposeVideoParams>(() => defaultComposeParams())
  const [tasks, setTasks] = useState<ComposeTaskItem[]>([])
  const [loading, setLoading] = useState<'analyze' | 'prepare' | 'create' | null>('analyze')
  const [error, setError] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [videoModels, setVideoModels] = useState<VideoModelConfig[]>([])
  const hasSavedParamsRef = useRef(false)

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(COMPOSE_STATE_KEY) || '{}')
      const savedVersion = Number(saved?.version || 0)
      if (saved?.tasks?.length) setTasks(saved.tasks)
      if (saved?.prepared) setPrepared(saved.prepared)
      if (saved?.analysis) setAnalysis(saved.analysis)
      if (saved?.params) {
        const migratedDefault = savedVersion < COMPOSE_STATE_VERSION && saved.params?.model === 'doubao-seedance-2.0'
        hasSavedParamsRef.current = !migratedDefault
        setParams(normalizeComposeParams(saved.params, savedVersion))
      }
      if (saved?.answers) setAnswers(saved.answers)
      if (saved?.step) setStep(saved.step)
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    getVideoConfig()
      .then((config) => {
        if (cancelled) return
        setVideoModels(config.models || [])
        setParams((current) => {
          const requestedModel = hasSavedParamsRef.current ? current.model : (config.compose_default_model || current.model)
          const requestedProfile = (config.models || []).find((model) => model.id === requestedModel)
          const fallbackProfile = (config.models || []).find((model) => model.available !== false)
          const selectedProfile = requestedProfile?.available === false ? fallbackProfile : requestedProfile
          const requestedSize = config.defaults?.size || current.size
          const requestedDuration = config.defaults?.duration || current.duration
          return {
            ...current,
            duration: selectedProfile
              ? Math.min(selectedProfile.max_duration, Math.max(selectedProfile.min_duration, requestedDuration))
              : requestedDuration,
            size: selectedProfile?.sizes.includes(requestedSize) ? requestedSize : (selectedProfile?.sizes[0] || current.size),
            ratio: config.defaults?.ratio || current.ratio,
            native_audio: config.defaults?.native_audio ?? current.native_audio,
            count: config.defaults?.count || current.count,
            model: selectedProfile?.id || requestedModel,
          }
        })
      })
      .catch(() => {
        /* keep local fallback defaults */
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    localStorage.setItem(COMPOSE_STATE_KEY, JSON.stringify({ version: COMPOSE_STATE_VERSION, step, analysis, prepared, answers, params, tasks }))
  }, [step, analysis, prepared, answers, params, tasks])

  const currentModelLabel = useMemo(() => {
    const configured = videoModels.find((model) => model.id === params.model)
    return videoQualityLabel(params.model, configured?.label)
  }, [params.model, videoModels])

  const runAnalyze = useCallback(async () => {
    setLoading('analyze')
    setError('')
    setAnalysis(null)
    setPrepared(null)
    setTasks([])
    try {
      const data = await analyzeVideoComposition(assets.map((asset) => ({
        id: asset.id,
        name: asset.name,
        type: asset.type,
        url: asset.url,
        path: asset.path,
      })))
      setAnalysis(data)
      const defaults: Record<string, string> = {}
      data.questions.forEach((question) => {
        defaults[question.id] = question.recommended || question.options[0]?.value || ''
      })
      setAnswers(defaults)
      setStep('questions')
    } catch (err) {
      setError(getErrorMessage(err, '素材理解失败'))
    } finally {
      setLoading(null)
    }
  }, [assets])

  useEffect(() => {
    if (!analysis && assets.length > 0) {
      runAnalyze()
    }
  }, [analysis, assets.length, runAnalyze])

  const handlePrepare = useCallback(async (revisionPrompt?: string) => {
    if (!analysis) return
    setLoading('prepare')
    setError('')
    try {
      const nextParams = revisionPrompt
        ? {
            ...params,
            user_instruction: [
              params.user_instruction?.trim(),
              '请根据用户已编辑的最终提示词重新整理成片方案，保留素材理解、确认问题答案和当前视频参数作为上下文。',
              `用户已编辑的最终提示词：${revisionPrompt.trim()}`,
            ].filter(Boolean).join('\n\n'),
          }
        : params
      const data = await prepareVideoComposition({
        analysis,
        answers: Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer })),
        params: nextParams,
      })
      setPrepared(data)
      setStep('prepare')
    } catch (err) {
      setError(getErrorMessage(err, '成片方案生成失败'))
    } finally {
      setLoading(null)
    }
  }, [analysis, answers, params])

  const handleRegeneratePrepared = useCallback(() => {
    if (!prepared?.final_prompt.trim()) return
    handlePrepare(prepared.final_prompt)
  }, [handlePrepare, prepared])

  const handleCreate = useCallback(async () => {
    if (!prepared) return
    setLoading('create')
    setError('')
    try {
      const data = await createVideoComposition({ prepared, params })
      const nextTasks = (data.tasks || [{ task_id: data.task_id, status: data.status, model: data.model, prompt: data.final_prompt || '' }]).map((task) => {
        const composeTask = task as typeof task & { unsupported_features?: string[] }
        return {
        taskId: task.task_id,
        status: normalizeTaskStatus(task.status),
        progress: 0,
        model: task.model || params.model,
        unsupportedFeatures: composeTask.unsupported_features || data.unsupported_features || [],
        }
      })
      setTasks(nextTasks)
      setStep('tasks')
    } catch (err) {
      setError(getErrorMessage(err, '一键成片提交失败'))
    } finally {
      setLoading(null)
    }
  }, [prepared, params])

  useEffect(() => {
    if (!tasks.some((task) => !['succeeded', 'failed'].includes(normalizeTaskStatus(task.status)))) return
    const timer = window.setInterval(async () => {
      const next = await Promise.all(tasks.map(async (task) => {
        if (['succeeded', 'failed'].includes(normalizeTaskStatus(task.status))) return task
        try {
          const status = await pollVideoTask(task.taskId, task.model)
          const normalized = normalizeTaskStatus(status.status)
          return {
            ...task,
            status: normalized,
            progress: status.progress || (normalized === 'succeeded' ? 100 : task.progress),
            videoUrl: status.video_url || task.videoUrl,
            downloadUrl: status.download_url || task.downloadUrl,
            localPath: status.local_path || task.localPath,
            error: status.error || task.error,
          }
        } catch (err) {
          return { ...task, error: getErrorMessage(err, '任务查询失败') }
        }
      }))
      setTasks(next)
      if (next.some((task) => normalizeTaskStatus(task.status) === 'succeeded')) {
        await onGenerated()
      }
    }, 3000)
    return () => window.clearInterval(timer)
  }, [tasks, onGenerated])

  const renderQuestion = (question: ComposeQuestion) => (
    <div key={question.id} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
      <div className="mb-3 text-body-sm font-medium text-[#F1F5F9]">{question.question}</div>
      {question.options.length > 0 ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {question.options.map((option) => {
            const selected = answers[question.id] === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setAnswers((prev) => ({ ...prev, [question.id]: option.value }))}
                className={`rounded-lg border px-3 py-2 text-left text-body-sm transition-all ${
                  selected
                    ? 'border-[#6366F1]/70 bg-[#6366F1]/20 text-[#E0E7FF]'
                    : 'border-[#1E293B] bg-[#111827] text-[#94A3B8] hover:border-[#475569] hover:text-[#F1F5F9]'
                }`}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      ) : (
        <textarea
          value={answers[question.id] || ''}
          onChange={(event) => setAnswers((prev) => ({ ...prev, [question.id]: event.target.value }))}
          className="h-20 w-full resize-none rounded-lg border border-[#1E293B] bg-[#111827] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
        />
      )}
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-5xl flex-col border-l border-[#1E293B] bg-[#020617] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#1E293B] px-6 py-4">
          <div>
            <div className="flex items-center gap-2 text-heading-sm text-[#F1F5F9]">
              <Wand2 className="h-5 w-5 text-[#A5B4FC]" />
              一键成片
            </div>
            <div className="mt-1 text-body-xs text-[#64748B]">
              已选 {assets.length}/{MAX_COMPOSE_ASSETS} 个素材 · AI 理解素材 · {currentModelLabel}
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-[#64748B] transition-colors hover:bg-[#1E293B] hover:text-[#F1F5F9]">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid flex-1 min-h-0 grid-cols-[280px_1fr]">
          <aside className="overflow-auto border-r border-[#1E293B] p-4">
            <div className="mb-3 text-body-xs text-[#64748B]">已选素材</div>
            <div className="space-y-3">
              {assets.map((asset) => (
                <div key={asset.id} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-3">
                  <div className="aspect-video overflow-hidden rounded-md bg-[#111827]">
                    {asset.type === 'image' ? (
                      <img src={assetUrl(asset)} alt={asset.name} className="h-full w-full object-cover" />
                    ) : asset.type === 'video' ? (
                      <video src={assetUrl(asset)} muted preload="metadata" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center">
                        {(() => {
                          const Icon = TYPE_ICONS[asset.type] || FileText
                          return <Icon className="h-8 w-8 text-[#6366F1]" />
                        })()}
                      </div>
                    )}
                  </div>
                  <div className="mt-2 truncate text-body-xs text-[#F1F5F9]">{asset.name}</div>
                  <div className="text-[11px] text-[#64748B]">{asset.type}</div>
                </div>
              ))}
            </div>
          </aside>

          <main className="min-h-0 overflow-auto p-6">
            <div className="mb-5 grid grid-cols-4 gap-2">
              {[
                ['analyze', '素材理解'],
                ['questions', '确认方向'],
                ['prepare', '成片方案'],
                ['tasks', '生成任务'],
              ].map(([key, label], index) => (
                <div
                  key={key}
                  className={`rounded-lg border px-3 py-2 text-center text-body-xs ${
                    step === key
                      ? 'border-[#6366F1]/70 bg-[#6366F1]/20 text-[#E0E7FF]'
                      : 'border-[#1E293B] bg-[#0B0F1A] text-[#64748B]'
                  }`}
                >
                  {index + 1}. {label}
                </div>
              ))}
            </div>

            {error && (
              <div className="mb-4 rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-body-sm text-[#FCA5A5]">
                {error}
              </div>
            )}

            {loading === 'analyze' && (
              <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-[#1E293B] bg-[#0B0F1A]">
                <Loader2 className="mb-4 h-8 w-8 animate-spin text-[#6366F1]" />
                <div className="text-body-md text-[#F1F5F9]">AI 正在理解素材</div>
              </div>
            )}

            {analysis && step !== 'analyze' && (
              <div className="mb-4 rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                <div className="mb-2 flex items-center gap-2 text-body-sm font-medium text-[#F1F5F9]">
                  <Check className="h-4 w-4 text-[#10B981]" />
                  素材理解结果
                </div>
                <p className="text-body-sm leading-6 text-[#CBD5E1]">{analysis.summary || '已完成素材理解。'}</p>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {analysis.assets.map((item) => (
                    <div key={item.id} className="rounded-md border border-[#1E293B] bg-[#111827] p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-body-xs text-[#F1F5F9]">{item.name}</span>
                        <span className={`shrink-0 rounded px-2 py-0.5 text-[11px] ${item.status === 'success' ? 'bg-[#10B981]/15 text-[#86EFAC]' : 'bg-[#EF4444]/15 text-[#FCA5A5]'}`}>
                          {item.status}
                        </span>
                      </div>
                      <div className="mt-1 text-[11px] text-[#A5B4FC]">{item.role || item.type}</div>
                      <div className="mt-2 line-clamp-3 text-body-xs leading-5 text-[#94A3B8]">{item.summary || item.error || '暂无摘要'}</div>
                    </div>
                  ))}
                </div>
                {analysis.warnings.length > 0 && (
                  <div className="mt-3 text-body-xs text-[#FBBF24]">{analysis.warnings.join('；')}</div>
                )}
              </div>
            )}

            {step === 'questions' && analysis && (
              <div className="space-y-4">
                <div className="text-body-sm text-[#94A3B8]">根据素材内容，AI 只需要你确认下面几个关键方向。</div>
                {analysis.questions.map(renderQuestion)}
                <ComposeParamsPanel params={params} models={videoModels} onChange={setParams} advancedOpen={advancedOpen} onToggleAdvanced={() => setAdvancedOpen((value) => !value)} />
                <button
                  onClick={() => handlePrepare()}
                  disabled={loading === 'prepare'}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#6366F1] px-5 py-2.5 text-body-sm text-white transition-colors hover:bg-[#5558E6] disabled:opacity-50"
                >
                  {loading === 'prepare' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  生成成片方案
                </button>
              </div>
            )}

            {step === 'prepare' && prepared && (
              <div className="space-y-4">
                <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                  <div className="mb-2 text-body-sm font-medium text-[#F1F5F9]">成片方案</div>
                  <p className="text-body-sm leading-6 text-[#CBD5E1]">{prepared.summary || '已生成分镜和最终提示词。'}</p>
                </div>
                <div className="grid gap-3">
                  {prepared.storyboard.map((shot, index) => (
                    <div key={shot.id || index} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                      <div className="mb-2 text-body-sm font-medium text-[#F1F5F9]">镜头 {index + 1} · {shot.title}</div>
                      <div className="text-body-xs leading-6 text-[#94A3B8]">{shot.scene}</div>
                      <div className="mt-2 text-[11px] text-[#64748B]">{shot.duration}s · {shot.shot_size} · {shot.camera}</div>
                    </div>
                  ))}
                </div>
                <label className="block">
                  <span className="mb-2 block text-body-xs text-[#64748B]">最终提示词</span>
                  <textarea
                    value={prepared.final_prompt}
                    onChange={(event) => setPrepared((current) => current ? { ...current, final_prompt: event.target.value } : current)}
                    className="h-40 w-full resize-none rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
                  />
                  <div className="mt-3 flex justify-end">
                    <button
                      type="button"
                      onClick={handleRegeneratePrepared}
                      disabled={loading === 'prepare' || !prepared.final_prompt.trim()}
                      className="inline-flex items-center gap-2 rounded-lg border border-[#334155] bg-[#111827] px-4 py-2 text-body-sm text-[#CBD5E1] transition-colors hover:border-[#6366F1]/60 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {loading === 'prepare' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                      重新生成
                    </button>
                  </div>
                </label>
                {prepared.unsupported_features.filter((feature) => feature !== 'audio_reference_input').length > 0 && (
                  <div className="rounded-lg border border-[#F59E0B]/30 bg-[#F59E0B]/10 p-3 text-body-xs text-[#FCD34D]">
                    暂不支持：{prepared.unsupported_features.filter((feature) => feature !== 'audio_reference_input').map(formatUnsupportedFeature).join('、')}
                  </div>
                )}
                <button
                  onClick={handleCreate}
                  disabled={loading === 'create'}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#6366F1] px-5 py-2.5 text-body-sm text-white transition-colors hover:bg-[#5558E6] disabled:opacity-50"
                >
                  {loading === 'create' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
                  确认生成视频
                </button>
              </div>
            )}

            {step === 'tasks' && (
              <div className="space-y-3">
                {tasks.map((task, index) => (
                  <div key={task.taskId} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-body-sm font-medium text-[#F1F5F9]">生成视频 {index + 1}</div>
                      <span className="rounded-md bg-[#1E293B] px-3 py-1 text-body-xs text-[#CBD5E1]">{taskStatusLabel(task.status)}</span>
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#1E293B]">
                      <div className="h-full bg-[#6366F1]" style={{ width: `${Math.min(100, task.progress || (task.status === 'succeeded' ? 100 : 12))}%` }} />
                    </div>
                    {task.videoUrl && (
                      <video src={resolveGeneratedAssetUrl(task.videoUrl, task.localPath || '')} controls className="mt-4 max-h-72 w-full rounded-lg bg-black" />
                    )}
                    {(task.unsupportedFeatures || []).filter((feature) => feature !== 'audio_reference_input').length > 0 && (
                      <div className="mt-3 rounded-lg border border-[#F59E0B]/30 bg-[#F59E0B]/10 p-3 text-body-xs leading-5 text-[#FCD34D]">
                        {(task.unsupportedFeatures || []).filter((feature) => feature !== 'audio_reference_input').map(formatUnsupportedFeature).join('；')}
                      </div>
                    )}
                    {task.error && <div className="mt-3 text-body-xs text-[#FCA5A5]">{task.error}</div>}
                  </div>
                ))}
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  )
}

function ComposeParamsPanel({
  params,
  models,
  onChange,
  advancedOpen,
  onToggleAdvanced,
}: {
  params: ComposeVideoParams
  models: VideoModelConfig[]
  onChange: (params: ComposeVideoParams) => void
  advancedOpen: boolean
  onToggleAdvanced: () => void
}) {
  const update = (patch: Partial<ComposeVideoParams>) => onChange({ ...params, ...patch })
  const selectedModel = models.find((model) => model.id === params.model)
  return (
    <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
      <button type="button" onClick={onToggleAdvanced} className="mb-3 text-body-sm font-medium text-[#C4B5FD]">
        {advancedOpen ? '收起高级参数' : '展开高级参数'}
      </button>
      {advancedOpen && (
        <div className="grid gap-3 md:grid-cols-3">
          <label>
            <span className="mb-1 block text-body-xs text-[#64748B]">生成质量</span>
            <select value={params.model} onChange={(event) => {
              const nextModel = models.find((model) => model.id === event.target.value)
              update({
                model: event.target.value,
                duration: nextModel ? Math.min(nextModel.max_duration, Math.max(nextModel.min_duration, params.duration)) : params.duration,
                size: nextModel && !nextModel.sizes.includes(params.size) ? (nextModel.sizes[0] || params.size) : params.size,
              })
            }} className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#111827] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]">
              {(models.length ? models : [{ id: params.model, label: params.model } as VideoModelConfig]).map((model) => (
                <option key={model.id} value={model.id} disabled={model.available === false}>{videoQualityLabel(model.id, model.label)}{model.available === false ? '（暂未开放）' : ''}</option>
              ))}
            </select>
          </label>
          <label>
            <span className="mb-1 block text-body-xs text-[#64748B]">平台</span>
            <select value={params.platform} onChange={(event) => update({ platform: event.target.value })} className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#111827] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]">
              <option value="douyin_xhs">抖音/小红书通用</option>
              <option value="douyin">抖音</option>
              <option value="xhs">小红书</option>
              <option value="tiktok">TikTok</option>
            </select>
          </label>
          <label>
            <span className="mb-1 block text-body-xs text-[#64748B]">视频类型</span>
            <select value={params.scenario} onChange={(event) => update({ scenario: event.target.value })} className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#111827] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]">
              <option value="product_seed">产品种草</option>
              <option value="store_promo">门店宣传</option>
              <option value="brand_ad">品牌广告</option>
              <option value="knowledge">知识口播</option>
            </select>
          </label>
          <label>
            <span className="mb-1 block text-body-xs text-[#64748B]">比例</span>
            <select value={params.ratio} onChange={(event) => update({ ratio: event.target.value })} className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#111827] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]">
              <option value="9:16">9:16 竖屏</option>
              <option value="1:1">1:1 方形</option>
              <option value="16:9">16:9 横屏</option>
            </select>
          </label>
          <label>
            <span className="mb-1 block text-body-xs text-[#64748B]">时长</span>
            <select value={params.duration} onChange={(event) => update({ duration: Number(event.target.value) })} className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#111827] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]">
              {[6, 10, 15, 30].map((value) => <option key={value} value={value} disabled={Boolean(selectedModel && (value < selectedModel.min_duration || value > selectedModel.max_duration))}>{value} 秒</option>)}
            </select>
          </label>
          <label>
            <span className="mb-1 block text-body-xs text-[#64748B]">分辨率</span>
            <select value={params.size} onChange={(event) => update({ size: event.target.value })} className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#111827] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]">
              <option value="1080p" disabled={Boolean(selectedModel && !selectedModel.sizes.includes('1080p'))}>1080p</option>
              <option value="4K" disabled={Boolean(!selectedModel?.sizes.includes('4K'))}>4K{selectedModel?.sizes.includes('4K') ? '' : '（暂未开放）'}</option>
              <option value="720p" disabled={Boolean(selectedModel && !selectedModel.sizes.includes('720p'))}>720p</option>
            </select>
          </label>
          <label>
            <span className="mb-1 block text-body-xs text-[#64748B]">生成数量</span>
            <select value={params.count} onChange={(event) => update({ count: Number(event.target.value) })} className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#111827] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]">
              {[1, 2, 3, 4].map((value) => <option key={value} value={value}>{value} 个</option>)}
            </select>
          </label>
          <label className="md:col-span-3 flex items-center gap-3 rounded-lg border border-[#1E293B] bg-[#111827] px-3 py-2">
            <input type="checkbox" checked={params.native_audio} onChange={(event) => update({ native_audio: event.target.checked })} className="accent-[#6366F1]" />
            <span className="text-body-sm text-[#F1F5F9]">Native Audio 原生声音</span>
          </label>
          <label className="md:col-span-3">
            <span className="mb-1 block text-body-xs text-[#64748B]">补充说明</span>
            <textarea value={params.user_instruction || ''} onChange={(event) => update({ user_instruction: event.target.value })} className="h-20 w-full resize-none rounded-lg border border-[#1E293B] bg-[#111827] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]" placeholder="例如：突出产品质感和成交转化，结尾加行动引导" />
          </label>
        </div>
      )}
    </div>
  )
}
