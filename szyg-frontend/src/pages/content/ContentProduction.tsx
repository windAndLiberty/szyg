import { useState, useCallback, useEffect, useMemo, useRef, type ClipboardEvent, type DragEvent, type MouseEvent } from 'react'
import { Link } from 'react-router'
import { motion } from 'framer-motion'
import {
  Image as ImageIcon,
  Video as VideoIcon,
  FileText as TextIcon,
  Mic as MicIcon,
  ExternalLink,
  Copy,
  Check,
  Loader2,
  Lightbulb,
  Send,
  Sparkles,
  Trash2,
  History,
  X,
  Plus,
  BarChart3,
} from 'lucide-react'
import ContentAnalytics from '../insights/ContentAnalytics'
import {
  adoptMaterial,
  unadoptMaterial,
  fetchGenerationHistory,
  recordGenerationHistory,
  createVideo,
  pollVideoTask,
  optimizeVideoPrompt,
  createVideoStoryboard,
  fetchTtsVoices,
  generateCopy,
  getErrorMessage,
  interpretVoicePrompt,
  previewTts,
  synthesizeTts,
  saveGeneratedDocument,
  updateGeneratedDocument,
  openGeneratedMedia,
  deleteGeneratedMedia,
  getVideoConfig,
  uploadContentReference,
  deleteContentReference,
  type ContentReference,
  type GenerationHistoryItem,
  type GenerationHistoryType,
  type TtsResult,
  type TtsVoice,
  type VideoModelConfig,
  type VideoStoryboardCharacterLock,
  type VideoStoryboardShot,
} from '@/lib/api'
import {
  getImageGenerationState,
  startImageDraftGeneration,
  subscribeImageGeneration,
  removeGeneratedImageAsset,
  markGeneratedImageAssetAdopted,
  markGeneratedImageAssetUnadopted,
  type GeneratedImageAsset,
} from '@/lib/contentDraftStore'
import { resolveGeneratedAssetUrl } from '@/lib/generatedAssets'
import { translateCurrent, useI18n } from '@/lib/i18n'

type Tab = 'image' | 'video' | 'copy' | 'voice' | 'performance'
type ImageStyle = 'none' | 'realistic' | 'product' | 'xiaohongshu_cover' | 'douyin_cover' | 'anime' | 'oil' | 'watercolor' | 'cyberpunk' | 'minimal'
type ImageSize = '1920x1920' | '2560x1440' | '1440x2560' | '2048x2048' | '2304x1728' | '3072x1296'

const TABS: { key: Tab; label: string; icon: typeof ImageIcon }[] = [
  { key: 'image', get label() { return translateCurrent("图片生成") }, icon: ImageIcon },
  { key: 'video', get label() { return translateCurrent("视频生成") }, icon: VideoIcon },
  { key: 'copy', get label() { return translateCurrent("文案生成") }, icon: TextIcon },
  { key: 'voice', get label() { return translateCurrent("语音合成") }, icon: MicIcon },
  { key: 'performance', get label() { return translateCurrent("内容效果") }, icon: BarChart3 },
]

const IMAGE_STYLES: { key: ImageStyle; label: string }[] = [
  { key: 'none', get label() { return translateCurrent("未定义风格") } },
  { key: 'realistic', get label() { return translateCurrent("写实") } },
  { key: 'product', get label() { return translateCurrent("电商产品图") } },
  { key: 'xiaohongshu_cover', get label() { return translateCurrent("小红书封面") } },
  { key: 'douyin_cover', get label() { return translateCurrent("抖音封面") } },
  { key: 'anime', get label() { return translateCurrent("动漫") } },
  { key: 'oil', get label() { return translateCurrent("油画") } },
  { key: 'watercolor', get label() { return translateCurrent("水彩") } },
  { key: 'cyberpunk', get label() { return translateCurrent("赛博朋克") } },
  { key: 'minimal', get label() { return translateCurrent("极简") } },
]

const IMAGE_SIZES: { key: ImageSize; label: string }[] = [
  { key: '1920x1920', get label() { return translateCurrent("1920 x 1920 方图") } },
  { key: '2560x1440', get label() { return translateCurrent("2560 x 1440 横屏") } },
  { key: '1440x2560', get label() { return translateCurrent("1440 x 2560 竖屏") } },
  { key: '2048x2048', get label() { return translateCurrent("2048 x 2048 高清方图") } },
  { key: '2304x1728', get label() { return translateCurrent("2304 x 1728 横图") } },
  { key: '3072x1296', get label() { return translateCurrent("3072 x 1296 宽屏") } },
]

const HISTORY_TABS: { key: GenerationHistoryType; label: string; icon: typeof ImageIcon }[] = [
  { key: 'image', get label() { return translateCurrent("图片") }, icon: ImageIcon },
  { key: 'video', get label() { return translateCurrent("视频") }, icon: VideoIcon },
  { key: 'audio', get label() { return translateCurrent("语音") }, icon: MicIcon },
  { key: 'text', get label() { return translateCurrent("文案") }, icon: TextIcon },
]

const REFERENCE_LABELS: Record<GenerationHistoryType, string> = {
  get image() { return translateCurrent("图片素材") },
  get video() { return translateCurrent("视频素材") },
  get audio() { return translateCurrent("语音素材") },
  get text() { return translateCurrent("文案素材") },
}

const REFERENCE_STYLES: Record<GenerationHistoryType, string> = {
  image: 'border-[#22C55E]/35 bg-[#22C55E]/10 text-[#BBF7D0]',
  video: 'border-[#6366F1]/35 bg-[#6366F1]/10 text-[#C4B5FD]',
  audio: 'border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#FDE68A]',
  text: 'border-[#38BDF8]/35 bg-[#38BDF8]/10 text-[#BAE6FD]',
}

function AdoptionActionButton({
  adopted,
  onClick,
  disabled = false,
  className = '',
}: {
  adopted?: boolean
  onClick: (event: MouseEvent<HTMLButtonElement>) => void
  disabled?: boolean
  className?: string
}) {
  const { t } = useI18n();

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex min-w-[86px] shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-body-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
        adopted
          ? 'border border-[#334155] bg-[#1E293B] text-[#CBD5E1] hover:bg-[#263449] hover:text-white'
          : 'bg-[#6366F1] text-white hover:bg-[#5558E6]'
      } ${className}`}
    >
      <Check className="h-3.5 w-3.5" />
      {adopted ? t("取消采纳") : t("采纳素材")}
    </button>
  )
}

function adoptionCardClass(adopted?: boolean): string {
  const hoverClass = 'transition-all duration-200 hover:-translate-y-0.5 hover:border-[#6366F1]/45 hover:bg-[#111827] hover:shadow-[0_18px_45px_rgba(15,23,42,0.28)]'
  return adopted
    ? `border-[#10B981]/45 bg-[#10B981]/[0.04] shadow-[0_0_0_1px_rgba(16,185,129,0.08)] ${hoverClass}`
    : `border-[#1E293B] ${hoverClass}`
}

type ReferenceAsset = {
  type: GenerationHistoryType
  title: string
  id?: string
  path?: string
  url?: string
  text?: string
  size?: number
  duration?: number
  source?: 'upload' | 'history'
}

type ReferenceUploadMode = 'image' | 'video'

const REFERENCE_UPLOAD_RULES = {
  image: {
    accept: '.jpg,.jpeg,.png,image/jpeg,image/png',
    get hint() { return translateCurrent("最多 10 张 · JPG/PNG · 单张 ≤15MB · 最大 4096×4096") },
  },
  video: {
    accept: '.jpg,.jpeg,.png,.webp,.mp4,.mov,image/jpeg,image/png,image/webp,video/mp4,video/quicktime',
    get hint() { return translateCurrent("最多 9 张图片 + 3 段视频 · 视频 2–15 秒、单段 ≤50MB") },
  },
} as const

function referenceTypeForFile(file: File): 'image' | 'video' | null {
  const suffix = file.name.split('.').pop()?.toLowerCase() || ''
  if (file.type.startsWith('image/') || ['jpg', 'jpeg', 'png', 'webp'].includes(suffix)) return 'image'
  if (file.type.startsWith('video/') || ['mp4', 'mov'].includes(suffix)) return 'video'
  return null
}

function uploadedReference(item: ContentReference): ReferenceAsset {
  return {
    id: item.id,
    type: item.kind,
    title: item.name,
    path: item.path,
    url: item.url,
    size: item.size,
    duration: item.duration || undefined,
    source: 'upload',
  }
}

function historyTypeForTab(tab: Tab): GenerationHistoryType {
  if (tab === 'voice') return 'audio'
  if (tab === 'copy') return 'text'
  if (tab === 'performance') return 'image'
  return tab
}

function historyKindLabel(type: GenerationHistoryType): string {
  return HISTORY_TABS.find((item) => item.key === type)?.label || translateCurrent("内容")
}

function formatHistoryTime(value: string): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const diffMs = Date.now() - date.getTime()
  if (diffMs < 60 * 1000) return translateCurrent("刚刚")
  const minutes = Math.floor(diffMs / (60 * 1000))
  if (minutes < 60) return translateCurrent("{v0}分钟前", { v0: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return translateCurrent("{v0}小时前", { v0: hours })
  const days = Math.floor(hours / 24)
  if (days < 30) return translateCurrent("{v0}天前", { v0: days })
  return date.toLocaleDateString('zh-CN')
}

function historyUpdatedTime(item: GenerationHistoryItem): string {
  return item.updated_at || item.created_at
}

function notifyGenerationHistoryUpdated(type: GenerationHistoryType) {
  window.dispatchEvent(new CustomEvent('szyg:generation-history-updated', { detail: { type } }))
}

function buildReferenceText(asset: {
  type: GenerationHistoryType
  title?: string
  path?: string
  url?: string
  text?: string
}): string {
  const source = asset.path || asset.url || ''
  if (asset.type === 'image') {
    return `【图片素材】${asset.title || 'AI生成图片'}\n路径：${source}\n用途：画面、主体、风格或构图参考`
  }
  if (asset.type === 'video') {
    return `【视频素材】${asset.title || 'AI生成视频'}\n路径：${source}\n用途：镜头节奏、场景氛围或风格参考`
  }
  if (asset.type === 'audio') {
    return `【语音素材】${asset.title || 'AI生成语音'}\n路径：${source}\n用途：音色、语速、情绪或配音风格参考`
  }
  return `【文案素材】${asset.title || 'AI生成文案'}\n${asset.text || `路径：${source}`}\n用途：内容结构、卖点或表达风格参考`
}

async function copyReference(asset: {
  type: GenerationHistoryType
  title?: string
  path?: string
  url?: string
  text?: string
}) {
  const text = buildReferenceText(asset)
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    window.alert(text)
    return
  }
  window.dispatchEvent(new CustomEvent('szyg-reference-copied', {
    detail: { type: asset.type, title: asset.title || historyKindLabel(asset.type) },
  }))
}

function parseReferenceText(value: string): ReferenceAsset | null {
  const typeMatch = value.match(/【(?:引用)?(图片|视频|语音|文案)素材】([^\n]*)/)
  if (!typeMatch) return null
  const typeMap: Record<string, GenerationHistoryType> = {
    图片: 'image',
    视频: 'video',
    语音: 'audio',
    文案: 'text',
  }
  const type = typeMap[typeMatch[1]]
  const title = typeMatch[2]?.trim() || REFERENCE_LABELS[type]
  const pathMatch = value.match(/(?:路径|本地文件)：([^\n]+)/)
  const path = pathMatch?.[1]?.trim()
  const text = type === 'text'
    ? value
        .replace(/【(?:引用)?文案素材】[^\n]*\n?/, '')
        .replace(/用途：.*$/s, '')
        .trim()
    : ''
  return { type, title, path, text }
}

function compactReferenceToken(ref: ReferenceAsset): string {
  return `[${REFERENCE_LABELS[ref.type]}：${ref.title}]`
}

function referenceContext(references: ReferenceAsset[]): string {
  if (references.length === 0) return ''
  const sourceLabels = { image: '图片素材', video: '视频素材', audio: '语音素材', text: '文案素材' }
  const counters: Record<'image' | 'video' | 'audio' | 'text', number> = {
    image: 0,
    video: 0,
    audio: 0,
    text: 0,
  }
  return [
    '引用素材：',
    ...references.map((ref, index) => {
      counters[ref.type] += 1
      const providerLabel = ref.source === 'upload'
        ? `${ref.type === 'image' ? '图片' : ref.type === 'video' ? '视频' : sourceLabels[ref.type]}${counters[ref.type]}`
        : sourceLabels[ref.type]
      const source = ref.text || (ref.source === 'upload' ? '' : ref.path || '')
      return `${index + 1}. ${providerLabel}：${ref.title}${source ? `\n   ${source}` : ''}`
    }),
  ].join('\n')
}

function promptWithReferences(prompt: string, references: ReferenceAsset[]): string {
  const context = referenceContext(references)
  return [context, prompt.trim()].filter(Boolean).join('\n\n')
}

function ReferenceTextarea({
  value,
  onChange,
  references,
  onReferencesChange,
  allowedTypes,
  uploadMode,
  placeholder,
  className = '',
}: {
  value: string
  onChange: (value: string) => void
  references: ReferenceAsset[]
  onReferencesChange: (value: ReferenceAsset[]) => void
  allowedTypes: GenerationHistoryType[]
  uploadMode?: ReferenceUploadMode
  placeholder: string
  className?: string
}) {
  const { t } = useI18n()
  const [message, setMessage] = useState('')
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)

  const showMessage = useCallback((value: string) => {
    setMessage(value)
    window.setTimeout(() => setMessage(''), 3200)
  }, [])

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    if (!uploadMode || uploading || files.length === 0) return
    setUploading(true)
    let next = [...references]
    try {
      for (const file of Array.from(files)) {
        const type = referenceTypeForFile(file)
        const suffix = file.name.split('.').pop()?.toLowerCase() || ''
        if (!type || !allowedTypes.includes(type)) {
          throw new Error(uploadMode === 'image' ? t("图片生成仅支持 JPG、PNG 参考图") : t("视频生成仅支持 JPG、PNG、WEBP、MP4、MOV 素材"))
        }
        if (uploadMode === 'image' && !['jpg', 'jpeg', 'png'].includes(suffix)) {
          throw new Error(translateCurrent("图片生成仅支持 JPG、PNG 参考图"))
        }
        const uploadedImages = next.filter((item) => item.source === 'upload' && item.type === 'image').length
        const uploadedVideos = next.filter((item) => item.source === 'upload' && item.type === 'video').length
        if (uploadMode === 'image' && uploadedImages >= 10) throw new Error(translateCurrent("图片生成最多添加 10 张参考图"))
        if (uploadMode === 'video' && type === 'image' && uploadedImages >= 9) throw new Error(translateCurrent("视频生成最多添加 9 张参考图"))
        if (uploadMode === 'video' && type === 'video' && uploadedVideos >= 3) throw new Error(translateCurrent("视频生成最多添加 3 段参考视频"))
        if (type === 'image' && file.size > 15 * 1024 * 1024) throw new Error(translateCurrent("单张参考图片不能超过 15MB"))
        if (type === 'video' && file.size > 50 * 1024 * 1024) throw new Error(translateCurrent("单段参考视频不能超过 50MB"))
        const item = await uploadContentReference(file, uploadMode)
        next = [...next, uploadedReference(item)]
        onReferencesChange(next)
      }
    } catch (error) {
      showMessage(getErrorMessage(error, t("参考素材上传失败")))
    } finally {
      setUploading(false)
    }
  }, [allowedTypes, onReferencesChange, references, showMessage, uploadMode, uploading])

  const handlePaste = useCallback((event: ClipboardEvent<HTMLTextAreaElement>) => {
    const pasted = event.clipboardData.getData('text')
    const ref = parseReferenceText(pasted)
    if (!ref) return
    event.preventDefault()
    if (!allowedTypes.includes(ref.type)) {
      setMessage(t("当前输入框不支持{v0}引用", { v0: REFERENCE_LABELS[ref.type] }))
      window.setTimeout(() => setMessage(''), 2200)
      return
    }
    const token = compactReferenceToken(ref)
    if (!references.some((item) => item.type === ref.type && item.title === ref.title && item.path === ref.path)) {
      onReferencesChange([...references, ref])
    }
    const element = event.currentTarget
    const start = element.selectionStart
    const end = element.selectionEnd
    const prefix = value.slice(0, start)
    const suffix = value.slice(end)
    const spacerBefore = prefix && !prefix.endsWith('\n') ? '\n' : ''
    const spacerAfter = suffix && !suffix.startsWith('\n') ? '\n' : ''
    onChange(`${prefix}${spacerBefore}${token}${spacerAfter}${suffix}`)
  }, [allowedTypes, onChange, onReferencesChange, references, value])

  const removeReference = useCallback((ref: ReferenceAsset) => {
    onReferencesChange(references.filter((item) => item !== ref))
    onChange(value.replace(compactReferenceToken(ref), '').replace(/\n{3,}/g, '\n\n').trimStart())
    if (ref.source === 'upload' && ref.id) void deleteContentReference(ref.id).catch(() => undefined)
  }, [onChange, onReferencesChange, references, value])

  const handleDrop = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (!uploadMode) return
    event.preventDefault()
    setDragging(false)
    void handleFiles(event.dataTransfer.files)
  }, [handleFiles, uploadMode])

  return (
    <div
      onDragEnter={(event) => { if (uploadMode) { event.preventDefault(); setDragging(true) } }}
      onDragOver={(event) => { if (uploadMode) event.preventDefault() }}
      onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false) }}
      onDrop={handleDrop}
      className={`relative rounded-lg border bg-[#0B0F1A] transition-colors focus-within:border-[#6366F1] ${dragging ? 'border-[#818CF8] ring-2 ring-[#6366F1]/25' : 'border-[#1E293B]'}`}
    >
      {dragging && (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center rounded-lg bg-[#111827]/95 text-body-sm font-medium text-[#C4B5FD]">

          {t("松开即可添加参考素材")}
        </div>
      )}
      {references.length > 0 && (
        <div className="flex flex-wrap gap-2 border-b border-[#1E293B] px-3 py-2">
          {references.map((ref, index) => (
            <button
              key={`${ref.type}-${ref.title}-${index}`}
              type="button"
              onClick={() => removeReference(ref)}
              className={`inline-flex max-w-full items-center gap-2 rounded-md border px-2.5 py-1 text-[11px] transition-colors hover:border-white/25 ${REFERENCE_STYLES[ref.type]}`}
              title={t("点击移除此引用")}
            >
              <span className="shrink-0 font-medium">{REFERENCE_LABELS[ref.type]}</span>
              <span className="truncate">{ref.title}</span>
              {ref.duration && <span className="shrink-0 opacity-70">{ref.duration.toFixed(1)}s</span>}
              <X className="h-3 w-3 shrink-0 opacity-70" />
            </button>
          ))}
        </div>
      )}
      <div className="flex items-stretch">
        {uploadMode && (
          <label className={`group m-3 mr-0 flex w-[76px] shrink-0 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed text-center transition-colors ${uploading ? 'cursor-wait border-[#6366F1]/40 bg-[#6366F1]/10 text-[#A5B4FC]' : 'border-[#334155] bg-[#111827] text-[#64748B] hover:border-[#6366F1]/70 hover:text-[#C4B5FD]'}`}>
            {uploading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Plus className="h-5 w-5" />}
            <span className="text-[11px]">{uploading ? t("上传中") : t("参考内容")}</span>
            <input
              type="file"
              multiple
              disabled={uploading}
              accept={REFERENCE_UPLOAD_RULES[uploadMode].accept}
              className="hidden"
              onChange={(event) => {
                if (event.target.files) void handleFiles(event.target.files)
                event.target.value = ''
              }}
            />
          </label>
        )}
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onPaste={handlePaste}
          placeholder={placeholder}
          className={`min-w-0 flex-1 resize-none border-0 bg-transparent px-4 py-3 text-body-md text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none ${className}`}
        />
      </div>
      {(message || uploadMode) && (
        <div className={`border-t border-[#1E293B] px-3 py-2 text-body-xs ${message ? 'text-[#FCA5A5]' : 'text-[#64748B]'}`}>
          {message || (uploadMode ? t("{v0}；也可将文件拖到此处", { v0: REFERENCE_UPLOAD_RULES[uploadMode].hint }) : '')}
        </div>
      )}
    </div>
  )
}

async function adoptGeneratedAsset(asset: {
  path?: string
  url?: string
  title?: string
  type?: GenerationHistoryType
}) {
  return adoptMaterial({
    path: asset.path,
    url: asset.url,
    name: asset.title || asset.path?.split(/[\\/]/).pop(),
    tags: ['采纳素材', 'AI生成'],
    source: 'content_generation',
  })
}

export default function ContentProduction() {
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState<Tab>(() => new URLSearchParams(window.location.search).get('view') === 'performance' ? 'performance' : 'image')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [referenceToast, setReferenceToast] = useState('')

  useEffect(() => {
    const onCopied = (event: Event) => {
      const detail = (event as CustomEvent<{ title?: string }>).detail
      setReferenceToast(detail?.title ? t("已复制「{v0}」引用", { v0: detail.title }) : t("已复制素材引用"))
      window.setTimeout(() => setReferenceToast(''), 2600)
    }
    window.addEventListener('szyg-reference-copied', onCopied)
    return () => window.removeEventListener('szyg-reference-copied', onCopied)
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="flex flex-col h-full"
    >
      {/* Tabs */}
      <div className="flex items-center justify-between gap-3 px-6 py-3 border-b border-[#1E293B]">
        <div className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-body-sm transition-all ${
                activeTab === tab.key
                  ? 'bg-[#6366F1]/20 text-[#6366F1] border border-[#6366F1]/30'
                  : 'text-[#94A3B8] hover:bg-[#1E293B] hover:text-[#F1F5F9]'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>
        {activeTab !== 'performance' && <button
          type="button"
          onClick={() => setHistoryOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg border border-[#334155] bg-[#101827] px-4 py-2 text-body-sm text-[#CBD5E1] transition-colors hover:border-[#6366F1]/60 hover:text-white"
        >
          <History className="h-4 w-4" />

          {t("历史记录")}
        </button>}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {activeTab === 'image' && <ImageGeneration />}
        {activeTab === 'video' && <VideoGeneration />}
        {activeTab === 'copy' && <CopyGeneration />}
        {activeTab === 'voice' && <VoiceSynthesis />}
        {activeTab === 'performance' && <ContentAnalytics />}
      </div>
      <GenerationHistoryDrawer
        open={historyOpen}
        initialType={historyTypeForTab(activeTab)}
        onClose={() => setHistoryOpen(false)}
      />
      {referenceToast && (
        <div className="fixed bottom-6 right-6 z-[60] max-w-sm rounded-xl border border-[#6366F1]/40 bg-[#0B1220] px-4 py-3 shadow-2xl shadow-black/40">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-lg bg-[#6366F1]/20 p-1.5 text-[#C4B5FD]">
              <Copy className="h-4 w-4" />
            </div>
            <div>
              <div className="text-body-sm font-medium text-[#F8FAFC]">{referenceToast}</div>
              <div className="mt-1 text-body-xs leading-5 text-[#94A3B8]">

                {t("可在任意描述文本框中按 Ctrl+V 粘贴引用素材。")}
              </div>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  )
}

function GenerationHistoryDrawer({
  open,
  initialType,
  onClose,
}: {
  open: boolean
  initialType: GenerationHistoryType
  onClose: () => void
}) {
  const { t } = useI18n()
  const [activeType, setActiveType] = useState<GenerationHistoryType>(initialType)
  const [items, setItems] = useState<GenerationHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedTextItem, setSelectedTextItem] = useState<GenerationHistoryItem | null>(null)
  const [textOverrides, setTextOverrides] = useState<Record<string, string>>({})
  const [documentVersion, setDocumentVersion] = useState(0)

  useEffect(() => {
    if (open) setActiveType(initialType)
  }, [initialType, open])

  const loadHistory = useCallback(async () => {
    if (!open) return
    setLoading(true)
    setError('')
    try {
      const data = await fetchGenerationHistory(activeType)
      setItems(data.items || [])
    } catch (e) {
      setError(getErrorMessage(e, t("历史记录加载失败")))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [activeType, open])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  useEffect(() => {
    if (!open) return
    const handleDocumentUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ path?: string; url?: string; source?: string }>).detail || {}
      setDocumentVersion((value) => value + 1)
      if (detail.source !== 'history') {
        setTextOverrides((current) => {
          const next = { ...current }
          for (const item of items) {
            if ((detail.path && item.path === detail.path) || (detail.url && item.url === detail.url)) {
              delete next[item.id]
            }
          }
          return next
        })
        setSelectedTextItem((current) => {
          if (!current) return current
          const matched = (detail.path && current.path === detail.path) || (detail.url && current.url === detail.url)
          return matched ? { ...current, updated_at: new Date().toISOString() } : current
        })
      }
      loadHistory()
    }
    const handleHistoryUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ type?: GenerationHistoryType }>).detail || {}
      if (!detail.type || detail.type === activeType) {
        loadHistory()
      }
    }
    window.addEventListener('szyg:document-updated', handleDocumentUpdated)
    window.addEventListener('szyg:generation-history-updated', handleHistoryUpdated)
    return () => {
      window.removeEventListener('szyg:document-updated', handleDocumentUpdated)
      window.removeEventListener('szyg:generation-history-updated', handleHistoryUpdated)
    }
  }, [activeType, items, loadHistory, open])

  const handleAdopt = useCallback(async (item: GenerationHistoryItem) => {
    try {
      const res = await adoptGeneratedAsset(item)
      setItems((prev) => prev.map((current) => (
        current.id === item.id
          ? { ...current, adopted: true, material_id: String(res.material?.id || '') }
          : current
      )))
      setSelectedTextItem((current) => (
        current?.id === item.id ? { ...current, adopted: true, material_id: String(res.material?.id || '') } : current
      ))
      if (item.type === 'image') {
        markGeneratedImageAssetAdopted({ url: item.url, path: item.path }, String(res.material?.id || ''))
      }
    } catch (e) {
      setError(getErrorMessage(e, t("采纳素材失败")))
    }
  }, [])

  const handleUnadopt = useCallback(async (item: GenerationHistoryItem) => {
    try {
      await unadoptMaterial({ path: item.path, url: item.url, material_id: item.material_id })
      setItems((prev) => prev.map((current) => (
        current.id === item.id ? { ...current, adopted: false, material_id: '' } : current
      )))
      setSelectedTextItem((current) => (
        current?.id === item.id ? { ...current, adopted: false, material_id: '' } : current
      ))
      if (item.type === 'image') {
        markGeneratedImageAssetUnadopted({ url: item.url, path: item.path })
      }
    } catch (e) {
      setError(getErrorMessage(e, t("取消采纳失败")))
    }
  }, [])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/45 backdrop-blur-sm">
      <button className="absolute inset-0 cursor-default" onClick={onClose} aria-label={t("关闭历史记录")} />
      <div className="relative flex h-full w-full max-w-5xl flex-col border-l border-[#1E293B] bg-[#020617] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#1E293B] px-6 py-4">
          <div>
            <div className="flex items-center gap-2 text-heading-md text-[#F8FAFC]">
              <History className="h-5 w-5 text-[#A5B4FC]" />

              {t("生成历史")}
            </div>
            <div className="mt-1 text-body-xs text-[#64748B]">

              {t("仅展示本机仍然存在的生成内容。采纳后会进入素材管理，取消采纳不会删除原文件。")}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#334155] bg-[#0B0F1A] p-2 text-[#94A3B8] transition-colors hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex gap-2 border-b border-[#1E293B] px-6 py-3">
          {HISTORY_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveType(tab.key)}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-body-sm transition-colors ${
                activeType === tab.key
                  ? 'border border-[#6366F1]/40 bg-[#6366F1]/15 text-[#C4B5FD]'
                  : 'text-[#94A3B8] hover:bg-[#0F172A] hover:text-white'
              }`}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-6">
          {error && (
            <div className="mb-4 rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-3 text-body-sm text-[#FCA5A5]">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex h-64 items-center justify-center text-[#94A3B8]">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />

              {t("正在读取历史记录")}
            </div>
          ) : items.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-[#334155] bg-[#0B0F1A] text-center">
              <History className="mb-3 h-8 w-8 text-[#475569]" />
              <div className="text-body-sm text-[#CBD5E1]">{t("暂无")}{historyKindLabel(activeType)}{t("历史")}</div>
              <div className="mt-1 text-body-xs text-[#64748B]">{t("生成内容后会自动保存到这里。")}</div>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {items.map((item) => (
                item.type === 'text' ? (
                  <TextHistoryCard
                    key={item.id}
                    item={item}
                    version={documentVersion}
                    textOverride={textOverrides[item.id]}
                    onOpen={() => setSelectedTextItem(item)}
                  />
                ) : (
                  <div key={item.id} className={`relative overflow-hidden rounded-xl border bg-[#0B0F1A] ${adoptionCardClass(item.adopted)}`}>
                    <HistoryPreview item={item} />
                    <div className="space-y-3 p-4">
                      <div>
                        <div className="line-clamp-1 text-body-sm font-medium text-[#F1F5F9]">{item.title || item.filename}</div>
                        <div className="mt-1 text-body-xs text-[#64748B]">{formatHistoryTime(historyUpdatedTime(item))}</div>
                      </div>
                      {item.prompt && <div className="line-clamp-2 text-body-xs leading-5 text-[#94A3B8]">{item.prompt}</div>}
                      <HistoryActions item={item} onAdopt={handleAdopt} onUnadopt={handleUnadopt} />
                    </div>
                  </div>
                )
              ))}
            </div>
          )}
        </div>
      </div>
      {selectedTextItem && (
        <TextHistoryDetailModal
          item={selectedTextItem}
          version={documentVersion}
          textOverride={textOverrides[selectedTextItem.id]}
          onClose={() => setSelectedTextItem(null)}
          onSaved={(text, updatedAt) => {
            setTextOverrides((current) => ({ ...current, [selectedTextItem.id]: text }))
            if (updatedAt) {
              setItems((current) => current
                .map((item) => (item.id === selectedTextItem.id ? { ...item, updated_at: updatedAt } : item))
                .sort((a, b) => new Date(historyUpdatedTime(b)).getTime() - new Date(historyUpdatedTime(a)).getTime()))
              setSelectedTextItem((current) => current?.id === selectedTextItem.id ? { ...current, updated_at: updatedAt } : current)
            }
          }}
          onAdopt={handleAdopt}
          onUnadopt={handleUnadopt}
        />
      )}
    </div>
  )
}

function HistoryActions({
  item,
  onAdopt,
  onUnadopt,
}: {
  item: GenerationHistoryItem
  onAdopt: (item: GenerationHistoryItem) => void
  onUnadopt: (item: GenerationHistoryItem) => void
}) {
  const { t } = useI18n();

  return (
    <div className="flex flex-wrap gap-2">
      <AdoptionActionButton
        adopted={item.adopted}
        onClick={(event) => {
          event.stopPropagation()
          item.adopted ? onUnadopt(item) : onAdopt(item)
        }}
      />
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation()
          copyReference({
            type: item.type,
            path: item.path,
            url: item.url,
            title: item.title || item.filename,
          })
        }}
        className="inline-flex items-center gap-1.5 rounded-md bg-[#1E293B] px-3 py-1.5 text-body-xs text-[#94A3B8] transition-colors hover:bg-[#334155] hover:text-white"
      >
        <Copy className="h-3.5 w-3.5" />

        {t("引用")}
      </button>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation()
          openGeneratedMedia({ path: item.path, url: item.url })
        }}
        className="inline-flex items-center gap-1.5 rounded-md bg-[#1E293B] px-3 py-1.5 text-body-xs text-[#94A3B8] transition-colors hover:bg-[#334155] hover:text-white"
      >
        <ExternalLink className="h-3.5 w-3.5" />

        {t("打开")}
      </button>
    </div>
  )
}

function HistoryPreview({ item }: { item: GenerationHistoryItem }) {
  const url = resolveGeneratedAssetUrl(item.url, item.path)
  if (item.type === 'image') {
    return <img src={url} alt={item.title || item.filename} className="h-52 w-full object-cover" />
  }
  if (item.type === 'video') {
    return <video src={url} controls className="h-52 w-full bg-black object-contain" />
  }
  if (item.type === 'audio') {
    return (
      <div className="flex h-52 flex-col justify-center gap-4 bg-[#111827] p-4">
        <MicIcon className="h-8 w-8 text-[#A5B4FC]" />
        <audio src={url} controls className="w-full" />
      </div>
    )
  }
  return <HistoryTextPreview prompt={item.prompt} />
}

function cleanHistoryTextContent(value: string): string {
  return value
    .split(/\r?\n/)
    .filter((line) => {
      const trimmed = line.trim()
      return trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('需求：')
    })
    .join('\n')
    .trim()
}

function useHistoryTextContent(item: GenerationHistoryItem, version = 0) {
  const [text, setText] = useState('')
  const url = resolveGeneratedAssetUrl(item.url, item.path)
  useEffect(() => {
    let cancelled = false
    const textUrl = `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}-${version}`
    fetch(textUrl, { cache: 'no-store' })
      .then((res) => (res.ok ? res.text() : ''))
      .then((value) => {
        if (!cancelled) setText(cleanHistoryTextContent(value))
      })
      .catch(() => {
        if (!cancelled) setText('')
      })
    return () => {
      cancelled = true
    }
  }, [url, version])
  return [text, setText] as const
}

function TextHistoryCard({
  item,
  version,
  textOverride,
  onOpen,
}: {
  item: GenerationHistoryItem
  version?: number
  textOverride?: string
  onOpen: () => void
}) {
  const { t } = useI18n();

  const [text] = useHistoryTextContent(item, version)
  const displayText = textOverride ?? text
  return (
    <button
      type="button"
      onClick={onOpen}
      className={`group relative min-h-60 rounded-xl border p-6 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-[#6366F1]/45 hover:bg-[#111827] hover:shadow-[0_18px_45px_rgba(15,23,42,0.35)] ${adoptionCardClass(item.adopted)}`}
    >
      <div className="line-clamp-6 whitespace-pre-wrap text-[15px] leading-8 tracking-[0.01em] text-[#F1F5F9] transition-colors group-hover:text-white">
        {displayText || t("文案内容读取中...")}
      </div>
      <div className="mt-6 text-body-xs tracking-[0.01em] text-[#64748B]">{formatHistoryTime(historyUpdatedTime(item))}</div>
    </button>
  )
}

function TextHistoryDetailModal({
  item,
  version,
  textOverride,
  onClose,
  onSaved,
  onAdopt,
  onUnadopt,
}: {
  item: GenerationHistoryItem
  version?: number
  textOverride?: string
  onClose: () => void
  onSaved: (text: string, updatedAt?: string) => void
  onAdopt: (item: GenerationHistoryItem) => void
  onUnadopt: (item: GenerationHistoryItem) => void
}) {
  const { t } = useI18n()
  const [loadedText] = useHistoryTextContent(item, version)
  const [text, setText] = useState(textOverride || '')
  const [savedText, setSavedText] = useState(textOverride || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const next = textOverride ?? loadedText
    setText(next)
    setSavedText(next)
  }, [loadedText, textOverride])

  const dirty = text.trim() !== savedText.trim()

  const saveText = useCallback(async () => {
    if (!text.trim()) return
    setSaving(true)
    setError('')
    try {
      const doc = [`# ${item.title || item.filename}`, '', `需求：${item.prompt || ''}`, '', text.trim()].join('\n')
      const saved = await updateGeneratedDocument({ path: item.path, url: item.url, content: doc })
      setSavedText(text)
      onSaved(text, saved.updated_at)
      window.dispatchEvent(new CustomEvent('szyg:document-updated', { detail: { path: item.path, url: item.url, source: 'history' } }))
    } catch (e) {
      setError(getErrorMessage(e, t("保存文案修改失败")))
    } finally {
      setSaving(false)
    }
  }, [item.filename, item.path, item.prompt, item.title, item.url, onSaved, text])

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/55 px-4 backdrop-blur-sm">
      <button className="absolute inset-0 cursor-default" onClick={onClose} aria-label={t("关闭文案详情")} />
      <div className="relative w-full max-w-3xl rounded-2xl border border-[#1E293B] bg-[#020617] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#1E293B] px-6 py-4">
          <div className="text-body-sm font-medium text-[#F8FAFC]">{t("文案详情")}</div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#334155] bg-[#0B0F1A] p-2 text-[#94A3B8] transition-colors hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[78vh] overflow-auto p-6">
          <div className="space-y-5">
            <div>
              <div className="mb-2 text-[11px] text-[#64748B]">{t("文案内容")}</div>
              <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                className="min-h-60 w-full resize-y rounded-xl border border-[#1E293B] bg-[#0B0F1A] px-4 py-4 text-[15px] leading-8 tracking-[0.01em] text-[#F1F5F9] outline-none transition-colors focus:border-[#6366F1]"
              />
              {dirty && <div className="mt-2 text-[11px] text-[#64748B]">{t("内容已修改，点击下方保存后才会写入文件。")}</div>}
              {error && <div className="mt-2 text-body-xs text-[#FCA5A5]">{error}</div>}
            </div>

            <div className="rounded-xl border border-[#1E293B] bg-[#0B0F1A] p-4">
              <div className="mb-2 text-[11px] text-[#64748B]">{t("生成需求")}</div>
              <div className="whitespace-pre-wrap text-body-xs leading-6 text-[#CBD5E1]">{item.prompt || t("暂无生成需求")}</div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#1E293B] pt-4">
              <span className="text-body-xs text-[#64748B]">
                {(item.title || t("文案素材"))} · {formatHistoryTime(historyUpdatedTime(item))}
              </span>
              <div className="flex flex-wrap gap-2">
                {dirty && (
                  <button
                    type="button"
                    onClick={saveText}
                    disabled={saving || !text.trim()}
                    className="inline-flex items-center gap-1.5 rounded-md bg-[#6366F1] px-3 py-1.5 text-body-xs text-white transition-colors hover:bg-[#5558E6] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}

                    {t("保存")}
                  </button>
                )}
                <HistoryActions item={item} onAdopt={onAdopt} onUnadopt={onUnadopt} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function HistoryTextPreview({ prompt }: { prompt: string }) {
  const { t } = useI18n();

  return (
    <div className="h-52 bg-[#111827] p-4">
      <TextIcon className="mb-3 h-7 w-7 text-[#A5B4FC]" />
      <div className="mb-2 text-[11px] text-[#64748B]">{t("生成需求")}</div>
      <p className="line-clamp-6 whitespace-pre-wrap text-body-xs leading-5 text-[#CBD5E1]">
        {prompt || t("暂无生成需求")}
      </p>
    </div>
  )
}

function ImageGeneration() {
  const { t } = useI18n()
  const initialGeneration = getImageGenerationState()
  const [prompt, setPrompt] = useState(initialGeneration.prompt)
  const [style, setStyle] = useState<ImageStyle>((initialGeneration.style || 'none') as ImageStyle)
  const [size, setSize] = useState<ImageSize>((initialGeneration.size || '1920x1920') as ImageSize)
  const [count, setCount] = useState(initialGeneration.count || 1)
  const [generation, setGeneration] = useState(initialGeneration)
  const [references, setReferences] = useState<ReferenceAsset[]>(() => {
    try {
      const saved = localStorage.getItem('szyg.contentProduction.imageReferences')
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })

  useEffect(() => subscribeImageGeneration(setGeneration), [])

  useEffect(() => {
    localStorage.setItem('szyg.contentProduction.imageReferences', JSON.stringify(references))
  }, [references])

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return
    await startImageDraftGeneration({
      prompt: promptWithReferences(prompt, references),
      style,
      size,
      count,
      referenceIds: references.flatMap((item) => item.id ? [item.id] : []),
    })
  }, [prompt, references, style, size, count])

  const handleOpenAsset = useCallback(async (asset: GeneratedImageAsset) => {
    try {
      await openGeneratedMedia({ path: asset.path, url: asset.url })
    } catch (error) {
      window.alert(getErrorMessage(error, t("打开图片失败")))
    }
  }, [])

  const handleDeleteAsset = useCallback(async (asset: GeneratedImageAsset) => {
    const ok = window.confirm(t("确定删除这张图片吗？如果文件保存在本机媒体目录中，也会同步删除本地文件。"))
    if (!ok) return
    try {
      await deleteGeneratedMedia({ path: asset.path, url: asset.url })
    } catch (error) {
      window.alert(getErrorMessage(error, t("删除本地图片失败")))
      return
    }
    removeGeneratedImageAsset(asset)
  }, [])

  const handleAdoptAsset = useCallback(async (asset: GeneratedImageAsset) => {
    try {
      const result = await adoptGeneratedAsset({ ...asset, type: 'image', title: asset.path ? asset.path.split(/[\\/]/).pop() : t("AI生成图片") })
      markGeneratedImageAssetAdopted(asset, String(result.material?.id || ''))
    } catch (error) {
      window.alert(getErrorMessage(error, t("采纳素材失败")))
    }
  }, [])

  const handleUnadoptAsset = useCallback(async (asset: GeneratedImageAsset) => {
    try {
      await unadoptMaterial({ path: asset.path, url: asset.url, material_id: asset.material_id })
      markGeneratedImageAssetUnadopted(asset)
    } catch (error) {
      window.alert(getErrorMessage(error, t("取消采纳失败")))
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Input */}
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <label className="text-body-sm text-[#94A3B8] mb-2 block">{t("描述图片内容")}</label>
        <ReferenceTextarea
          value={prompt}
          onChange={setPrompt}
          references={references}
          onReferencesChange={setReferences}
          allowedTypes={['image', 'text']}
          uploadMode="image"
          placeholder={t("例如：一只可爱的橘猫坐在窗台上，阳光洒进来，温暖的氛围...")}
          className="h-24"
        />

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("风格")}</span>
            <select
              value={style}
              onChange={(event) => setStyle(event.target.value as ImageStyle)}
              className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {IMAGE_STYLES.map((option) => (
                <option key={option.key} value={option.key}>{option.label}</option>
              ))}
            </select>
          </label>

          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("分辨率")}</span>
            <select
              value={size}
              onChange={(event) => setSize(event.target.value as ImageSize)}
              className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {IMAGE_SIZES.map((option) => (
                <option key={option.key} value={option.key}>{option.label}</option>
              ))}
            </select>
          </label>

          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("生成张数")}</span>
            <select
              value={count}
              onChange={(event) => setCount(Number(event.target.value))}
              className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {[1, 2, 3, 4].map((value) => (
                <option key={value} value={value}>{value}  {t("张")}</option>
              ))}
            </select>
          </label>
        </div>

        <button
          onClick={handleGenerate}
          disabled={generation.loading || !prompt.trim()}
          className="mt-4 flex items-center gap-2 px-6 py-2.5 bg-[#6366F1] hover:bg-[#5558E6] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-body-sm text-white transition-colors"
        >
          {generation.loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}

          {t("生成图片")}
        </button>
      </div>

      {generation.loading && (
        <div className="glass-card rounded-card-lg border border-[#6366F1]/30 bg-[#6366F1]/10 p-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-[#6366F1]" />
            <div>
              <div className="text-body-sm font-medium text-[#F1F5F9]">{t("图片生成中")}</div>
              <div className="mt-1 text-body-xs text-[#94A3B8]">

                {t("生成任务已在后台继续执行，切换到发布中心或其他页面不会中断。")}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {generation.error && (
        <div className="glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm">
          {generation.error}
        </div>
      )}

      {/* Results */}
      {generation.results.length > 0 && (
        <div className="space-y-4">
          <div className="glass-card rounded-card-lg border border-[#10B981]/30 bg-[#10B981]/10 p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-body-sm text-[#F1F5F9] font-medium">{t("已生成图片")}</div>
              <div className="mt-1 text-body-xs text-[#94A3B8]">{t("文件已自动保存。采纳需要使用的图片后，它们会进入素材管理。")}</div>
            </div>
            <Link
              to="/content/assets"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#10B981] px-4 py-2 text-body-sm font-medium text-white transition-colors hover:bg-[#059669]"
            >
              <Send className="h-4 w-4" />

              {t("去素材管理")}
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {generation.results.map((asset, i) => (
            <div key={`${asset.path}-${i}`} className={`glass-card relative overflow-hidden rounded-card-lg border group ${adoptionCardClass(asset.adopted)}`}>
              <img
                src={resolveGeneratedAssetUrl(asset.url, asset.path)}
                alt={`Generated ${i + 1}`}
                className="w-full aspect-square object-cover"
              />
              <div className="p-3 flex flex-wrap justify-end gap-2">
                <AdoptionActionButton
                  adopted={asset.adopted}
                  onClick={() => (asset.adopted ? handleUnadoptAsset(asset) : handleAdoptAsset(asset))}
                />
                <button
                  onClick={() => handleOpenAsset(asset)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />

                  {t("打开")}
                </button>
                <button
                  onClick={() => copyReference({
                    type: 'image',
                    path: asset.path,
                    url: asset.url,
                    title: asset.path ? asset.path.split(/[\\/]/).pop() : t("生成图片 {v0}", { v0: i + 1 }),
                  })}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors"
                >
                  <Copy className="w-3.5 h-3.5" />

                  {t("引用")}
                </button>
                <button
                  onClick={() => handleDeleteAsset(asset)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#7F1D1D] text-[#94A3B8] hover:text-white text-body-xs transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />

                  {t("删除")}
                </button>
              </div>
            </div>
          ))}
          </div>
        </div>
      )}
    </div>
  )
}

type VideoRatio = '16:9' | '1:1' | '9:16'
type VideoModel = 'doubao-seedance-1.5-pro' | 'doubao-seedance-2.0-fast' | 'doubao-seedance-2.0' | 'doubao-seedance-2.5'

const FALLBACK_VIDEO_MODEL_PROFILES: Record<VideoModel, VideoModelConfig> = {
  'doubao-seedance-1.5-pro': {
    id: 'doubao-seedance-1.5-pro',
    provider_model: 'doubao-seedance-1-5-pro-251215',
    get label() { return translateCurrent("基础模式") },
    available: true,
    sizes: ['720p', '1080p'],
    min_duration: 4,
    max_duration: 12,
    native_audio: true,
  },
  'doubao-seedance-2.0-fast': {
    id: 'doubao-seedance-2.0-fast',
    provider_model: 'doubao-seedance-2.0-fast',
    get label() { return translateCurrent("快速模式") },
    available: true,
    sizes: ['720p'],
    min_duration: 4,
    max_duration: 15,
    native_audio: true,
  },
  'doubao-seedance-2.0': {
    id: 'doubao-seedance-2.0',
    provider_model: 'doubao-seedance-2.0',
    get label() { return translateCurrent("高质量模式") },
    available: true,
    sizes: ['720p', '1080p'],
    min_duration: 4,
    max_duration: 15,
    native_audio: true,
  },
  'doubao-seedance-2.5': {
    id: 'doubao-seedance-2.5',
    provider_model: 'doubao-seedance-2.5',
    get label() { return translateCurrent("专业模式") },
    available: false,
    sizes: ['720p', '1080p', '4K'],
    min_duration: 3,
    max_duration: 30,
    native_audio: true,
  },
}

type VideoTaskItem = {
  taskId: string
  status: string
  progress: number
  model?: string
  videoUrl?: string
  downloadUrl?: string
  localPath?: string
  error?: string
  adopted?: boolean
  materialId?: string
  historyRecorded?: boolean
}

const VIDEO_STATE_KEY = 'szyg.contentProduction.videoState'

function normalizeVideoStatus(status: string): string {
  if (status === 'succeed') return 'succeeded'
  return status || 'queued'
}

function readVideoState() {
  try {
    const raw = localStorage.getItem(VIDEO_STATE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function VideoGeneration() {
  const { t } = useI18n()
  const initial = readVideoState()
  const finalPromptTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const [prompt, setPrompt] = useState(initial?.prompt || '')
  const [finalPrompt, setFinalPrompt] = useState(initial?.finalPrompt || '')
  const [negativePrompt, setNegativePrompt] = useState(initial?.negativePrompt || '')
  const [audioPrompt, setAudioPrompt] = useState(initial?.audioPrompt || '')
  const [promptSummary, setPromptSummary] = useState(initial?.promptSummary || '')
  const [duration, setDuration] = useState<number>(initial?.duration || 6)
  const [videoSize, setVideoSize] = useState(initial?.videoSize || '720p')
  const [videoModel, setVideoModel] = useState<VideoModel>(initial?.videoModel || 'doubao-seedance-2.0')
  const [ratio, setRatio] = useState<VideoRatio>(initial?.ratio || '9:16')
  const [count, setCount] = useState<number>(initial?.count || 1)
  const [nativeAudio, setNativeAudio] = useState<boolean>(Boolean(initial?.nativeAudio))
  const [showFinalPrompt, setShowFinalPrompt] = useState<boolean>(Boolean(initial?.finalPrompt))
  const [storyboarding, setStoryboarding] = useState(false)
  const [loading, setLoading] = useState(false)
  const [optimizing, setOptimizing] = useState(false)
  const [tasks, setTasks] = useState<VideoTaskItem[]>(initial?.tasks || [])
  const [error, setError] = useState<string | null>(null)
  const [videoModels, setVideoModels] = useState<VideoModelConfig[]>([])
  const [references, setReferences] = useState<ReferenceAsset[]>(initial?.references || [])

  const hasRunningTasks = tasks.some((task) => !['succeeded', 'failed'].includes(normalizeVideoStatus(task.status)))
  const currentVideoProfile = useMemo(
    () => videoModels.find((model) => model.id === videoModel) || FALLBACK_VIDEO_MODEL_PROFILES[videoModel],
    [videoModels, videoModel],
  )
  const minDuration = currentVideoProfile?.min_duration || 3
  const maxDuration = currentVideoProfile?.max_duration || 15
  const professionalAvailable = (videoModels.find((model) => model.id === 'doubao-seedance-2.5') || FALLBACK_VIDEO_MODEL_PROFILES['doubao-seedance-2.5']).available !== false

  useEffect(() => {
    let cancelled = false
    getVideoConfig()
      .then((config) => {
        if (cancelled) return
        const models = config.models || []
        setVideoModels(models)
        const selected = models.find((model) => model.id === videoModel)
        if (selected?.available === false) {
          const fallback = models.find((model) => model.id === config.default_model && model.available !== false)
            || models.find((model) => model.available !== false)
          if (fallback) {
            setVideoModel(fallback.id as VideoModel)
            if (!fallback.sizes.includes(videoSize)) setVideoSize(config.defaults?.size || fallback.sizes[0] || '720p')
          }
        }
      })
      .catch(() => {
        if (!cancelled) setVideoModels([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    localStorage.setItem(VIDEO_STATE_KEY, JSON.stringify({
      prompt,
      finalPrompt,
      negativePrompt,
      audioPrompt,
      promptSummary,
      duration,
      videoSize,
      videoModel,
      ratio,
      count,
      nativeAudio,
      references,
      tasks,
    }))
  }, [prompt, finalPrompt, negativePrompt, audioPrompt, promptSummary, duration, videoSize, videoModel, ratio, count, nativeAudio, references, tasks])

  useEffect(() => {
    if (!hasRunningTasks) {
      setLoading(false)
      return
    }
    setLoading(true)
    const poll = window.setInterval(async () => {
      const next = await Promise.all(tasks.map(async (task) => {
        const currentStatus = normalizeVideoStatus(task.status)
        if (['succeeded', 'failed'].includes(currentStatus)) return task
        try {
          const status = await pollVideoTask(task.taskId, task.model || videoModel)
          const normalized = normalizeVideoStatus(status.status)
          const nextTask: VideoTaskItem = {
            ...task,
            status: normalized,
            progress: status.progress || (normalized === 'succeeded' ? 100 : task.progress),
            videoUrl: status.video_url || task.videoUrl,
            downloadUrl: status.download_url || task.downloadUrl,
            localPath: status.local_path || task.localPath,
            error: status.error || task.error,
          }
          if (normalized === 'succeeded' && (nextTask.localPath || nextTask.videoUrl) && !task.historyRecorded) {
            try {
              const recorded = await recordGenerationHistory({
                type: 'video',
                path: nextTask.localPath,
                url: nextTask.videoUrl,
                get title() { return translateCurrent("AI生成视频") },
                prompt: finalPrompt || prompt,
                summary: t("{v0}秒 · {v1} · {v2}", { v0: duration, v1: ratio, v2: videoSize }),
                meta: { duration, ratio, size: videoSize, model: videoModel, native_audio: nativeAudio },
              })
              nextTask.historyRecorded = true
              nextTask.adopted = recorded.item.adopted
              nextTask.materialId = recorded.item.material_id || ''
              notifyGenerationHistoryUpdated('video')
            } catch {
              nextTask.historyRecorded = true
            }
          }
          return nextTask
        } catch {
          return task
        }
      }))
      setTasks(next)
      if (next.every((task) => ['succeeded', 'failed'].includes(normalizeVideoStatus(task.status)))) {
        setLoading(false)
        window.clearInterval(poll)
      }
    }, 2500)
    return () => window.clearInterval(poll)
  }, [duration, finalPrompt, hasRunningTasks, nativeAudio, prompt, ratio, tasks, videoModel, videoSize])

  useEffect(() => {
    if (!currentVideoProfile.sizes.includes(videoSize)) {
      setVideoSize(currentVideoProfile.sizes.includes('1080p') ? '1080p' : currentVideoProfile.sizes[0] || '720p')
    }
    if (duration < minDuration) setDuration(minDuration)
    if (duration > maxDuration) setDuration(maxDuration)
    if (nativeAudio && !currentVideoProfile.native_audio) setNativeAudio(false)
  }, [currentVideoProfile, duration, maxDuration, minDuration, nativeAudio, videoSize])

  useEffect(() => {
    const textarea = finalPromptTextareaRef.current
    if (!textarea) return
    const maxHeight = 420
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
  }, [finalPrompt, showFinalPrompt])

  const handleOptimizePrompt = useCallback(async () => {
    if (!prompt.trim()) return
    setOptimizing(true)
    setError(null)
    try {
      const sourcePrompt = promptWithReferences(prompt, references)
      const optimized = await optimizeVideoPrompt({
        prompt: sourcePrompt,
        duration,
        ratio,
        native_audio: nativeAudio,
        model: videoModel,
      })
      setFinalPrompt(optimized.final_prompt || prompt.trim())
      setNegativePrompt(optimized.negative_prompt || '')
      setAudioPrompt(optimized.audio_prompt || '')
      setPromptSummary(optimized.summary || '')
      setShowFinalPrompt(true)
    } catch (e) {
      setError(getErrorMessage(e, t("提示词优化失败")))
    } finally {
      setOptimizing(false)
    }
  }, [prompt, references, duration, ratio, nativeAudio, videoModel])

  const composeStoryboardPrompt = useCallback((shots: VideoStoryboardShot[], locks: VideoStoryboardCharacterLock[] = []) => {
    const activeLocks = locks.filter((lock) => lock.enabled && lock.consistency_prompt)
    return [
      ...(activeLocks.length > 0
        ? [
            '角色一致性要求：',
            ...activeLocks.map((lock) => lock.consistency_prompt),
            '',
          ]
        : []),
      `按照以下 ${shots.length} 个分镜生成一段连贯短视频，画幅 ${ratio}，总时长约 ${shots.reduce((sum, shot) => sum + Number(shot.duration || 0), 0)} 秒。`,
      ...shots.map((shot, index) => (
        `镜头${index + 1}（${shot.duration}秒，${shot.title}）：${shot.scene}；景别：${shot.shot_size}；镜头运动：${shot.camera}；旁白：${shot.narration || '无'}；声音：${shot.audio || '无特殊要求'}；生成提示：${shot.prompt}`
      )),
    ].join('\n')
  }, [ratio])

  const handleCreateStoryboard = useCallback(async () => {
    if (!prompt.trim()) return
    setStoryboarding(true)
    setError(null)
    try {
      const sourcePrompt = promptWithReferences(prompt, references)
      const res = await createVideoStoryboard({
        prompt: sourcePrompt,
        duration,
        ratio,
        native_audio: nativeAudio,
        model: videoModel,
      })
      const locks = res.character_lock || []
      setFinalPrompt(res.final_prompt || composeStoryboardPrompt(res.shots || [], locks))
      setPromptSummary(res.summary || '')
      setShowFinalPrompt(true)
    } catch (e) {
      setError(getErrorMessage(e, t("分镜生成失败")))
    } finally {
      setStoryboarding(false)
    }
  }, [prompt, references, duration, ratio, nativeAudio, videoModel, composeStoryboardPrompt])

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return
    if (videoSize === '4K' && videoModel !== 'doubao-seedance-2.5') {
      setError(t("4K 画质需要切换到专业模式。"))
      return
    }
    if (duration < minDuration || duration > maxDuration) {
      setError(t("{v0} 当前支持 {v1}-{v2} 秒。", { v0: currentVideoProfile.label, v1: minDuration, v2: maxDuration }))
      return
    }
    setLoading(true)
    setError(null)
    setTasks([])

    try {
      const sourcePrompt = promptWithReferences(prompt, references)
      const preparedPrompt = showFinalPrompt && finalPrompt.trim() ? finalPrompt.trim() : sourcePrompt
      const res = await createVideo(sourcePrompt, {
        duration,
        size: videoSize,
        ratio,
        count,
        native_audio: nativeAudio,
        prompt_optimize: false,
        final_prompt: preparedPrompt,
        model: videoModel,
        reference_ids: references.flatMap((item) => item.id ? [item.id] : []),
      })
      const nextTasks = (res.tasks && res.tasks.length > 0 ? res.tasks : [{ task_id: res.task_id, status: res.status }]).map((task) => ({
        taskId: task.task_id,
        status: normalizeVideoStatus(task.status),
        model: 'model' in task ? task.model : videoModel,
        progress: 0,
      }))
      setFinalPrompt(res.final_prompt || preparedPrompt)
      setTasks(nextTasks)
    } catch (e) {
      setError(getErrorMessage(e, t("视频生成失败")))
      setLoading(false)
    }
  }, [prompt, references, showFinalPrompt, finalPrompt, duration, videoSize, videoModel, ratio, count, nativeAudio, minDuration, maxDuration, currentVideoProfile.label])

  const handleOpenVideo = useCallback(async (task: VideoTaskItem) => {
    await openGeneratedMedia({ path: task.localPath, url: task.videoUrl })
  }, [])

  const handleDeleteVideo = useCallback(async (task: VideoTaskItem) => {
    if (!confirm(t("确定删除这个视频？"))) return
    try {
      await deleteGeneratedMedia({ path: task.localPath, url: task.videoUrl })
    } catch {
      /* remove from page even if remote-only */
    }
    setTasks((prev) => prev.filter((item) => item.taskId !== task.taskId))
  }, [])

  const handleAdoptVideo = useCallback(async (task: VideoTaskItem) => {
    try {
      const result = await adoptGeneratedAsset({
        path: task.localPath,
        url: task.videoUrl,
        type: 'video',
        title: t("AI生成视频-{v0}", { v0: task.taskId }),
      })
      setTasks((prev) => prev.map((item) => (
        item.taskId === task.taskId
          ? { ...item, adopted: true, materialId: String(result.material?.id || '') }
          : item
      )))
    } catch (error) {
      setError(getErrorMessage(error, t("采纳视频失败")))
    }
  }, [])

  const handleUnadoptVideo = useCallback(async (task: VideoTaskItem) => {
    try {
      await unadoptMaterial({ path: task.localPath, url: task.videoUrl, material_id: task.materialId })
      setTasks((prev) => prev.map((item) => (
        item.taskId === task.taskId ? { ...item, adopted: false, materialId: '' } : item
      )))
    } catch (error) {
      setError(getErrorMessage(error, t("取消采纳失败")))
    }
  }, [])

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <div className="mb-2 flex items-center justify-between gap-3">
          <label className="text-body-sm text-[#94A3B8]">{t("描述视频内容")}</label>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={handleOptimizePrompt}
              disabled={optimizing || !prompt.trim()}
              className="inline-flex h-9 w-32 items-center justify-center gap-1.5 rounded-lg border border-[#6366F1]/40 bg-[#6366F1]/10 px-3 text-body-xs text-[#C4B5FD] transition-colors hover:bg-[#6366F1]/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {optimizing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Lightbulb className="h-3.5 w-3.5" />}
              <span>{optimizing ? t("优化中") : t("优化提示")}</span>
            </button>
            <button
              type="button"
              onClick={handleCreateStoryboard}
              disabled={storyboarding || !prompt.trim()}
              className="inline-flex h-9 w-28 items-center justify-center gap-1.5 rounded-lg border border-[#6366F1]/40 bg-[#6366F1]/10 px-3 text-body-xs text-[#C4B5FD] transition-colors hover:bg-[#6366F1]/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {storyboarding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}

              {t("拆分镜")}
            </button>
          </div>
        </div>
        <ReferenceTextarea
          value={prompt}
          onChange={setPrompt}
          references={references}
          onReferencesChange={setReferences}
          allowedTypes={['image', 'video', 'text', 'audio']}
          uploadMode="video"
          placeholder={t("例如：一位咖啡店老板在清晨擦拭吧台，窗外阳光照进店里，镜头缓慢推进...")}
          className="h-24"
        />

        <div className="mt-4 grid gap-3 md:grid-cols-3 xl:grid-cols-5">
          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("生成模式")}</span>
            <select
              value={videoModel}
              onChange={(event) => setVideoModel(event.target.value as VideoModel)}
              className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {(videoModels.length ? videoModels : Object.values(FALLBACK_VIDEO_MODEL_PROFILES)).map((model) => (
                <option key={model.id} value={model.id} disabled={model.available === false}>
                  {model.id === 'doubao-seedance-2.0-fast' ? t("社媒快速模式") : model.label}{model.available === false ? t("（暂未开放）") : ''}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("分辨率")}</span>
            <select
              value={videoSize}
              onChange={(event) => {
                const nextSize = event.target.value
                setVideoSize(nextSize)
                if (nextSize === '4K' && professionalAvailable) setVideoModel('doubao-seedance-2.5')
              }}
              className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              <option value="720p">720p</option>
              <option value="1080p">1080p</option>
              <option value="4K" disabled={!professionalAvailable}>4K{professionalAvailable ? '' : t("（暂未开放）")}</option>
            </select>
          </label>

          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("原生声音")}</span>
            <select
              value={nativeAudio ? 'on' : 'off'}
              onChange={(event) => setNativeAudio(event.target.value === 'on')}
              disabled={!currentVideoProfile.native_audio}
              className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 text-body-sm text-[#F1F5F9] outline-none transition-colors focus:border-[#6366F1] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="on">{t("开启")}</option>
              <option value="off">{t("关闭")}</option>
            </select>
          </label>

          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("视频比例")}</span>
            <select
              value={ratio}
              onChange={(event) => setRatio(event.target.value as VideoRatio)}
              className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              <option value="9:16">{t("9:16 竖屏")}</option>
              <option value="16:9">{t("16:9 横屏")}</option>
              <option value="1:1">{t("1:1 方形")}</option>
            </select>
          </label>

          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("生成数量")}</span>
            <select
              value={count}
              onChange={(event) => setCount(Number(event.target.value))}
              className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {[1, 2, 3, 4].map((value) => (
                <option key={value} value={value}>{value}  {t("个")}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4 rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-4 py-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-body-xs text-[#64748B]">{t("视频时长")}</span>
            <span className="text-body-xs text-[#F1F5F9]">{duration}  {t("秒")}</span>
          </div>
          <input
            type="range"
            min={minDuration}
            max={maxDuration}
            step={1}
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value))}
            className="w-full accent-[#6366F1]"
          />
          <div className="mt-1 flex justify-between text-[11px] text-[#64748B]">
            <span>{minDuration}{t("秒")}</span>
            <span>{maxDuration}{t("秒")}</span>
          </div>
        </div>

        {(showFinalPrompt || finalPrompt) && (
          <div className="mt-4 rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <div>
                <p className="text-body-xs text-[#94A3B8]">{t("最终提示词")}</p>
                {promptSummary && <p className="mt-1 text-[11px] text-[#64748B]">{promptSummary}</p>}
              </div>
              <button onClick={() => navigator.clipboard.writeText(finalPrompt)} className="text-body-xs text-[#818CF8] hover:text-white">{t("复制")}</button>
            </div>
            <textarea
              ref={finalPromptTextareaRef}
              value={finalPrompt}
              onChange={(event) => setFinalPrompt(event.target.value)}
              className="w-full min-h-32 max-h-[420px] resize-none rounded-lg border border-[#1E293B] bg-[#111827] px-4 py-3 text-[15px] leading-8 tracking-[0.01em] text-[#F1F5F9] outline-none transition-colors focus:border-[#6366F1]"
            />
            {(negativePrompt || audioPrompt) && (
              <div className="mt-3 grid gap-3 text-body-xs md:grid-cols-2">
                {negativePrompt && <div className="text-[#64748B]">{t("负向约束：")}{negativePrompt}</div>}
                {audioPrompt && <div className="text-[#64748B]">{t("声音提示：")}{audioPrompt}</div>}
              </div>
            )}
          </div>
        )}

        {videoSize === '4K' && (
          <div className="mt-4 rounded-lg border border-[#F59E0B]/30 bg-[#F59E0B]/10 p-3 text-body-xs text-[#FCD34D]">

            {t("4K 画质需要专业生成能力；服务暂未开放时将无法提交。")}
          </div>
        )}

        <button
          onClick={handleGenerate}
          disabled={loading || !prompt.trim() || currentVideoProfile.available === false}
          className="mt-4 flex items-center gap-2 px-6 py-2.5 bg-[#6366F1] hover:bg-[#5558E6] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-body-sm text-white transition-colors"
        >
          {loading || optimizing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {loading ? t("正在生成视频") : t("生成视频")}
        </button>
      </div>

      {loading && (
        <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
          <div className="flex items-center gap-3 mb-3">
            <Loader2 className="w-5 h-5 text-[#6366F1] animate-spin" />
            <span className="text-body-sm text-[#F1F5F9]">{t("正在生成")} {tasks.length || count}  {t("个视频...")}</span>
          </div>
          <div className="space-y-2">
            {(tasks.length ? tasks : Array.from({ length: count }, (_, index) => ({ taskId: `pending-${index}`, progress: 0, status: 'queued' }))).map((task, index) => (
              <div key={task.taskId}>
                <div className="mb-1 flex justify-between text-[11px] text-[#64748B]">
                  <span>{t("视频")} {index + 1}</span>
                  <span>{task.progress || 0}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[#1E293B]">
                  <motion.div className="h-full bg-gradient-to-r from-[#6366F1] to-[#8B5CF6]" animate={{ width: `${task.progress || 0}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm">
          {error}
        </div>
      )}

      {tasks.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {tasks.map((task, index) => {
            const status = normalizeVideoStatus(task.status)
            const ready = status === 'succeeded' && task.videoUrl
            return (
              <div key={task.taskId} className={`glass-card relative overflow-hidden rounded-card-lg border ${adoptionCardClass(task.adopted)}`}>
                <div className="flex items-center justify-between border-b border-[#1E293B] px-4 py-3">
                  <span className="text-body-sm text-[#F1F5F9]">{t("视频")} {index + 1}</span>
                  {status !== 'succeeded' && (
                    <span className={`text-body-xs ${status === 'failed' ? 'text-[#EF4444]' : 'text-[#94A3B8]'}`}>
                      {status === 'failed' ? t("失败") : t("生成中")}
                    </span>
                  )}
                </div>
                {ready ? (
                  <video src={task.videoUrl} controls className="w-full max-h-[360px] bg-black" />
                ) : (
                  <div className="flex h-48 items-center justify-center bg-[#0B0F1A] text-body-sm text-[#64748B]">
                    {status === 'failed' ? (task.error || t("视频生成失败")) : t("等待生成结果...")}
                  </div>
                )}
                <div className="flex flex-wrap gap-2 p-4">
                  <AdoptionActionButton
                    adopted={task.adopted}
                    disabled={!ready}
                    onClick={() => (task.adopted ? handleUnadoptVideo(task) : handleAdoptVideo(task))}
                  />
                  <button disabled={!ready} onClick={() => handleOpenVideo(task)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] disabled:opacity-40 text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors">
                    <ExternalLink className="w-3.5 h-3.5" />

                    {t("打开")}
                  </button>
                  <button disabled={!ready} onClick={() => copyReference({
                    type: 'video',
                    path: task.localPath,
                    url: task.videoUrl,
                    title: t("视频 {v0}", { v0: index + 1 }),
                  })} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] disabled:opacity-40 text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors">
                    <Copy className="w-3.5 h-3.5" />

                    {t("引用")}
                  </button>
                  <button onClick={() => handleDeleteVideo(task)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#7F1D1D] text-[#94A3B8] hover:text-white text-body-xs transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />

                    {t("删除")}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

const COPY_LENGTH_OPTIONS = [
  { key: 'one_liner', get label() { return translateCurrent("一句话") }, get shortLabel() { return translateCurrent("一句话") }, min: 10, max: 30, get description() { return translateCurrent("适合标题、短钩子、评论回复") } },
  { key: 'short', get label() { return translateCurrent("短文案") }, get shortLabel() { return translateCurrent("短文案") }, min: 30, max: 80, get description() { return translateCurrent("适合朋友圈短句、短视频开头") } },
  { key: 'standard', get label() { return translateCurrent("标准文案") }, get shortLabel() { return translateCurrent("标准") }, min: 80, max: 180, get description() { return translateCurrent("适合朋友圈、小红书简介、短视频描述") } },
  { key: 'long', get label() { return translateCurrent("长文案") }, get shortLabel() { return translateCurrent("长文案") }, min: 180, max: 350, get description() { return translateCurrent("适合种草笔记、产品卖点、企业介绍") } },
  { key: 'deep', get label() { return translateCurrent("深度文案") }, get shortLabel() { return translateCurrent("深度") }, min: 350, max: 700, get description() { return translateCurrent("适合产品详情、公众号草稿、转化长文") } },
] as const

type CopyLengthKey = typeof COPY_LENGTH_OPTIONS[number]['key']

function defaultCopyLengthForType(copyType: string): CopyLengthKey {
  if (['抖音标题', '评论区回复'].includes(copyType)) return 'short'
  if (['小红书文案', '企业宣传'].includes(copyType)) return 'long'
  if (['朋友圈文案', '私信话术'].includes(copyType)) return 'standard'
  return 'standard'
}

type CopyResultItem = {
  id: string
  text: string
  savedText: string
  title: string
  path: string
  url: string
  charCount: number
  withinRange: boolean
  adopted: boolean
  materialId?: string
}

function countCopyCharacters(text: string): number {
  return Array.from((text || '').replace(/[\r\n]+/g, '')).length
}

function CopyGeneration() {
  const { t } = useI18n()
  const [prompt, setPrompt] = useState('')
  const [copyType, setCopyType] = useState('未定义类型')
  const [copyCount, setCopyCount] = useState(5)
  const [lengthKey, setLengthKey] = useState<CopyLengthKey>('standard')
  const [loading, setLoading] = useState(false)
  const [copyItems, setCopyItems] = useState<CopyResultItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)
  const [editingCopyId, setEditingCopyId] = useState<string | null>(null)
  const [references, setReferences] = useState<ReferenceAsset[]>([])

  const selectedLength = COPY_LENGTH_OPTIONS.find((item) => item.key === lengthKey) || COPY_LENGTH_OPTIONS[2]

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    setCopyItems([])
    try {
      const sourcePrompt = promptWithReferences(prompt, references)
      const data = await generateCopy({
        prompt: sourcePrompt,
        copy_type: copyType,
        count: copyCount,
        min_words: selectedLength.min,
        max_words: selectedLength.max,
      })
      const nextCopies = data.copies || []
      if (nextCopies.length > 0) {
        const items = await Promise.all(nextCopies.map(async (line: string, index: number): Promise<CopyResultItem> => {
          const text = line.replace(/^\d+[.、)]\s*/, '').trim()
          const charCount = data.char_counts?.[index] ?? countCopyCharacters(text)
          const withinRange = data.within_range?.[index] ?? (selectedLength.min <= charCount && charCount <= selectedLength.max)
          const title = `${copyType} ${index + 1}`
          const doc = [`# ${title}`, '', `需求：${prompt}`, '', text].join('\n')
          const saved = await saveGeneratedDocument(title, doc, 'md')
          let adopted = false
          let materialId = ''
          try {
            const recorded = await recordGenerationHistory({
              type: 'text',
              path: saved.path,
              url: saved.url,
              title,
              prompt: prompt.trim(),
              summary: text.slice(0, 120),
              meta: { copyType, copyIndex: index + 1, count: copyCount, lengthKey: selectedLength.key, minWords: selectedLength.min, maxWords: selectedLength.max },
            })
            adopted = recorded.item.adopted
            materialId = recorded.item.material_id || ''
          } catch {
            /* keep the generated copy visible even if history indexing fails */
          }
          return {
            id: `${Date.now()}-${index}`,
            text,
            savedText: text,
            title,
            path: saved.path,
            url: saved.url,
            charCount,
            withinRange,
            adopted,
            materialId,
          }
        }))
        setCopyItems(items)
        notifyGenerationHistoryUpdated('text')
      }
    } catch (e) {
      setError(getErrorMessage(e, t("文案生成失败")))
    } finally {
      setLoading(false)
    }
  }, [prompt, references, copyType, copyCount, selectedLength])

  const handleCopy = useCallback((text: string, idx: number) => {
    navigator.clipboard.writeText(text)
    setCopiedIdx(idx)
    setTimeout(() => setCopiedIdx(null), 2000)
  }, [])

  const handleEditCopyText = useCallback((itemId: string, text: string) => {
    setCopyItems((current) => current.map((item) => (
      item.id === itemId
        ? {
            ...item,
            text,
            charCount: countCopyCharacters(text),
            withinRange: selectedLength.min <= countCopyCharacters(text) && countCopyCharacters(text) <= selectedLength.max,
          }
        : item
    )))
  }, [selectedLength])

  const handleSaveCopyEdit = useCallback(async (item: CopyResultItem) => {
    setEditingCopyId(null)
    if (!item.path && !item.url) return
    const doc = [`# ${item.title}`, '', `需求：${prompt}`, '', item.text.trim()].join('\n')
    try {
      await updateGeneratedDocument({ path: item.path, url: item.url, content: doc })
      setCopyItems((current) => current.map((copyItem) => (
        copyItem.id === item.id ? { ...copyItem, savedText: item.text } : copyItem
      )))
      window.dispatchEvent(new CustomEvent('szyg:document-updated', { detail: { path: item.path, url: item.url, source: 'history' } }))
      setEditingCopyId(null)
    } catch (e) {
      setError(getErrorMessage(e, t("保存文案修改失败")))
    }
  }, [prompt])

  const handleAdoptCopy = useCallback(async (item: CopyResultItem) => {
    if (!item.path && !item.url) return
    try {
      const result = await adoptGeneratedAsset({ path: item.path, url: item.url, type: 'text', title: item.title })
      setCopyItems((current) => current.map((copyItem) => (
        copyItem.id === item.id ? { ...copyItem, adopted: true, materialId: String(result.material?.id || '') } : copyItem
      )))
    } catch (e) {
      setError(getErrorMessage(e, t("采纳文案失败")))
    }
  }, [])

  const handleUnadoptCopy = useCallback(async (item: CopyResultItem) => {
    if (!item.path && !item.url) return
    try {
      await unadoptMaterial({ path: item.path, url: item.url, material_id: item.materialId })
      setCopyItems((current) => current.map((copyItem) => (
        copyItem.id === item.id ? { ...copyItem, adopted: false, materialId: '' } : copyItem
      )))
    } catch (e) {
      setError(getErrorMessage(e, t("取消采纳失败")))
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Input */}
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <label className="text-body-sm text-[#94A3B8] mb-2 block">{t("输入文案需求")}</label>
        <ReferenceTextarea
          value={prompt}
          onChange={setPrompt}
          references={references}
          onReferencesChange={setReferences}
          allowedTypes={['image', 'video', 'audio', 'text']}
          placeholder={t("例如：为一款新能源汽车写5条朋友圈文案，突出科技感和环保...")}
          className="h-24"
        />
        <div className="mt-4 grid gap-4 md:grid-cols-4">
          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("文案类型")}</span>
            <select
              value={copyType}
              onChange={(event) => {
                const nextType = event.target.value
                setCopyType(nextType)
                setLengthKey(defaultCopyLengthForType(nextType))
              }}
              className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {['未定义类型', '小红书文案', '抖音标题', '朋友圈文案', '企业宣传', '评论区回复', '私信话术'].map((option) => (
                <option key={option} value={option}>{t(option)}</option>
              ))}
            </select>
          </label>
          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">{t("生成数量")}</span>
            <select
              value={copyCount}
              onChange={(event) => setCopyCount(Number(event.target.value))}
              className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>{value}  {t("条")}</option>
              ))}
            </select>
          </label>
          <div className="md:col-span-2">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-body-xs text-[#64748B]">{t("篇幅：")}{selectedLength.label}</span>
              <span className="text-[11px] text-[#94A3B8]">{t("约")} {selectedLength.min}-{selectedLength.max}  {t("字")}</span>
            </div>
            <input
              type="range"
              min={0}
              max={COPY_LENGTH_OPTIONS.length - 1}
              step={1}
              value={COPY_LENGTH_OPTIONS.findIndex((item) => item.key === lengthKey)}
              onChange={(event) => {
                const option = COPY_LENGTH_OPTIONS[Number(event.target.value)] || COPY_LENGTH_OPTIONS[2]
                setLengthKey(option.key)
              }}
              className="w-full accent-[#6366F1]"
            />
            <div className="mt-2 grid grid-cols-5 gap-1 text-center text-[11px] text-[#64748B]">
              {COPY_LENGTH_OPTIONS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setLengthKey(item.key)}
                  className={`rounded-md px-1 py-1 transition-colors ${
                    item.key === lengthKey ? 'bg-[#6366F1]/15 text-[#C4B5FD]' : 'hover:bg-[#1E293B] hover:text-[#CBD5E1]'
                  }`}
                >
                  {item.shortLabel}
                </button>
              ))}
            </div>
            <div className="mt-2 text-[11px] text-[#64748B]">{selectedLength.description}</div>
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading || !prompt.trim()}
          className="mt-4 flex items-center gap-2 px-6 py-2.5 bg-[#6366F1] hover:bg-[#5558E6] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-body-sm text-white transition-colors"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}

          {t("生成文案")}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {copyItems.length > 0 && (
        <div className="space-y-3">
          <div className="glass-card rounded-card-lg border border-[#10B981]/30 bg-[#10B981]/10 p-4">
            <div className="text-body-sm font-medium text-[#D1FAE5]">{t("文案已自动保存")}</div>
            <div className="mt-1 text-body-xs text-[#94A3B8]">

              {t("已生成")} {copyItems.length}  {t("条独立文案。按需采纳后，它们会分别进入素材管理。")}
            </div>
          </div>
          {copyItems.map((item, i) => (
            <div key={item.id} className={`glass-card relative rounded-card-lg border p-4 ${adoptionCardClass(item.adopted)}`}>
              <div className="mb-3 flex items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-body-xs text-[#94A3B8]">{item.title}</div>
                    <span className="rounded-md bg-[#1E293B] px-2 py-0.5 text-[11px] text-[#94A3B8]">

                      {t("约")} {item.charCount}  {t("字 ·")} {selectedLength.label}
                    </span>
                  </div>
                  <div className="mt-1 max-w-3xl truncate text-[11px] text-[#64748B]">{item.path}</div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {item.text.trim() !== item.savedText.trim() && (
                    <button
                      onClick={() => handleSaveCopyEdit(item)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#6366F1] hover:bg-[#5558E6] text-white text-body-xs transition-colors"
                    >
                      <Check className="w-3.5 h-3.5" />

                      {t("保存")}
                    </button>
                  )}
                  <AdoptionActionButton
                    adopted={item.adopted}
                    onClick={() => (item.adopted ? handleUnadoptCopy(item) : handleAdoptCopy(item))}
                  />
                </div>
              </div>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  {editingCopyId === item.id ? (
                    <textarea
                      autoFocus
                      value={item.text}
                      onChange={(event) => handleEditCopyText(item.id, event.target.value)}
                      onKeyDown={(event) => {
                        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                          handleSaveCopyEdit(item)
                        }
                      }}
                      className="min-h-32 w-full resize-y rounded-lg border border-[#6366F1]/40 bg-[#0B0F1A] px-3 py-2 text-body-md leading-7 text-[#F1F5F9] outline-none focus:border-[#818CF8]"
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => setEditingCopyId(item.id)}
                      className="group w-full rounded-lg border border-transparent p-2 text-left transition-colors hover:border-[#334155] hover:bg-[#0B0F1A]"
                    >
                      <p className="whitespace-pre-wrap text-body-md leading-7 text-[#F1F5F9]">{item.text}</p>
                      <div className="mt-2 text-[11px] text-[#475569] opacity-0 transition-opacity group-hover:opacity-100">

                        {t("点击编辑")}
                      </div>
                    </button>
                  )}
                </div>
                <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
                  <button
                    onClick={() => copyReference({
                      type: 'text',
                      path: item.path,
                      url: item.url,
                      title: item.title,
                      text: item.text,
                    })}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors"
                  >
                    <Copy className="w-3.5 h-3.5" />

                    {t("引用")}
                  </button>
                  <button
                    onClick={() => handleCopy(item.text, i)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors"
                  >
                    {copiedIdx === i ? (
                      <><Check className="w-3.5 h-3.5 text-[#10B981]" />  {t("已复制")}</>
                    ) : (
                      <><Copy className="w-3.5 h-3.5" />  {t("复制")}</>
                    )}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const VOICE_STATE_KEY = 'szyg.contentProduction.voiceState'

type VoiceResultItem = TtsResult & {
  id: string
  kind: 'preview' | 'full'
  title: string
  createdAt: string
  adopted?: boolean
  materialId?: string
}

const FALLBACK_TTS_VOICES: TtsVoice[] = [
  {
    id: 'warm_female',
    get name() { return translateCurrent("温柔女声") },
    provider_voice: 'zh_female_xiaoyi',
    gender: 'female',
    tags: ['温柔', '自然', '小红书'],
    get scene() { return translateCurrent("短视频种草、品牌介绍") },
    get description() { return translateCurrent("亲和自然的女声，适合产品介绍和生活方式内容。") },
    get demo_text() { return translateCurrent("您好，我是数字员工，很高兴为您服务。") },
  },
  {
    id: 'pro_male',
    get name() { return translateCurrent("专业男声") },
    provider_voice: 'zh_male_yuanfeng',
    gender: 'male',
    tags: ['专业', '清晰', '商务'],
    get scene() { return translateCurrent("企业宣传、知识讲解") },
    get description() { return translateCurrent("清晰稳重的男声，适合企业宣传和专业讲解。") },
    get demo_text() { return translateCurrent("您好，我是数字员工，很高兴为您服务。") },
  },
]

const VOICE_SCENES = [
  { value: 'short_video', get label() { return translateCurrent("短视频配音") } },
  { value: 'customer_service', get label() { return translateCurrent("客服话术") } },
  { value: 'brand_intro', get label() { return translateCurrent("企业宣传") } },
  { value: 'livestream', get label() { return translateCurrent("直播口播") } },
  { value: 'knowledge', get label() { return translateCurrent("知识讲解") } },
  { value: 'ad', get label() { return translateCurrent("广告旁白") } },
]

const VOICE_EMOTIONS = [
  { value: 'neutral', get label() { return translateCurrent("自然") } },
  { value: 'happy', get label() { return translateCurrent("热情") } },
  { value: 'calm', get label() { return translateCurrent("沉稳") } },
  { value: 'excited', get label() { return translateCurrent("兴奋") } },
  { value: 'sad', get label() { return translateCurrent("克制") } },
]

function readVoiceState() {
  try {
    const raw = localStorage.getItem(VOICE_STATE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function VoiceSynthesis() {
  const { t } = useI18n()
  const initial = readVoiceState()
  const [text, setText] = useState(initial?.text || '')
  const [voicePrompt, setVoicePrompt] = useState(initial?.voicePrompt || '')
  const [scene, setScene] = useState(initial?.scene || 'short_video')
  const [voice, setVoice] = useState(initial?.voice || 'warm_female')
  const [emotion, setEmotion] = useState(initial?.emotion || 'neutral')
  const [speed, setSpeed] = useState<number>(initial?.speed || 1.0)
  const [pitch, setPitch] = useState<number>(initial?.pitch || 0)
  const [voices, setVoices] = useState<TtsVoice[]>(FALLBACK_TTS_VOICES)
  const [results, setResults] = useState<VoiceResultItem[]>(initial?.results || [])
  const [previewLoading, setPreviewLoading] = useState<'voice' | 'text' | null>(null)
  const [generating, setGenerating] = useState(false)
  const [interpreting, setInterpreting] = useState(false)
  const [summary, setSummary] = useState(initial?.summary || '')
  const [error, setError] = useState<string | null>(null)
  const [references, setReferences] = useState<ReferenceAsset[]>(initial?.references || [])

  const selectedVoice = voices.find((item) => item.id === voice) || voices[0]
  const estimatedDuration = Math.max(1, Math.round((text.trim().length / (4.2 * Math.max(speed, 0.5))) * 10) / 10)

  useEffect(() => {
    let cancelled = false
    fetchTtsVoices()
      .then((data) => {
        if (!cancelled && data.voices?.length) {
          setVoices(data.voices)
          if (!data.voices.some((item) => item.id === voice)) {
            setVoice(data.voices[0].id)
          }
        }
      })
      .catch(() => {
        if (!cancelled) setVoices(FALLBACK_TTS_VOICES)
      })
    return () => {
      cancelled = true
    }
  }, [voice])

  useEffect(() => {
    localStorage.setItem(VOICE_STATE_KEY, JSON.stringify({
      text,
      voicePrompt,
      scene,
      voice,
      emotion,
      speed,
      pitch,
      summary,
      references,
      results,
    }))
  }, [text, voicePrompt, scene, voice, emotion, speed, pitch, summary, references, results])

  const buildPayload = useCallback((sourceText: string, preview: boolean) => ({
    text: sourceText,
    voice,
    voice_prompt: voicePrompt,
    scene,
    emotion,
    speed,
    pitch,
    format: 'mp3' as const,
    preview,
  }), [voice, voicePrompt, scene, emotion, speed, pitch])

  const addResult = useCallback(async (result: TtsResult, kind: 'preview' | 'full', title: string) => {
    const item: VoiceResultItem = {
      ...result,
      id: `${kind}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      kind,
      title,
      createdAt: new Date().toLocaleString(),
    }
    try {
      const recorded = await recordGenerationHistory({
        type: 'audio',
        path: result.path,
        url: result.url,
        title,
        prompt: text.trim() || selectedVoice?.demo_text || '',
        summary: `${selectedVoice?.name || t("语音")} · ${kind === 'preview' ? t("试听") : t("完整生成")}`,
        meta: { voice, emotion, speed, pitch, scene, preview: kind === 'preview' },
      })
      item.adopted = recorded.item.adopted
      item.materialId = recorded.item.material_id || ''
    } catch {
      /* keep the generated audio visible even if history indexing fails */
    }
    notifyGenerationHistoryUpdated('audio')
    setResults((prev) => [item, ...prev].slice(0, 20))
  }, [emotion, pitch, scene, selectedVoice?.demo_text, selectedVoice?.name, speed, text, voice])

  const handleInterpret = useCallback(async () => {
    if (!voicePrompt.trim()) return
    setInterpreting(true)
    setError(null)
    try {
      const interpreted = await interpretVoicePrompt({
        voice_prompt: voicePrompt.trim(),
        voice,
        scene,
        emotion,
        speed,
        pitch,
      })
      setVoice(interpreted.voice)
      setEmotion(interpreted.emotion)
      setSpeed(interpreted.speed)
      setPitch(interpreted.pitch)
      setSummary(interpreted.summary)
    } catch (e) {
      setError(getErrorMessage(e, t("声音描述解析失败")))
    } finally {
      setInterpreting(false)
    }
  }, [voicePrompt, voice, scene, emotion, speed, pitch])

  const handlePreviewVoice = useCallback(async () => {
    if (!selectedVoice) return
    setPreviewLoading('voice')
    setError(null)
    try {
      const result = await previewTts(buildPayload(selectedVoice.demo_text, true))
      await addResult(result, 'preview', t("{v0}试听", { v0: selectedVoice.name }))
    } catch (e) {
      setError(getErrorMessage(e, t("声音试听失败")))
    } finally {
      setPreviewLoading(null)
    }
  }, [selectedVoice, buildPayload, addResult])

  const handlePreviewText = useCallback(async () => {
    const source = text.trim()
    if (!source) return
    setPreviewLoading('text')
    setError(null)
    try {
      const result = await previewTts(buildPayload(source.slice(0, 120), true))
      await addResult(result, 'preview', t("当前文案试听"))
    } catch (e) {
      setError(getErrorMessage(e, t("文案试听失败")))
    } finally {
      setPreviewLoading(null)
    }
  }, [text, buildPayload, addResult])

  const handleGenerate = useCallback(async () => {
    const source = text.trim()
    if (!source) return
    setGenerating(true)
    setError(null)
    try {
      const result = await synthesizeTts(buildPayload(source, false))
      await addResult(result, 'full', t("完整语音"))
    } catch (e) {
      setError(getErrorMessage(e, t("语音合成失败")))
    } finally {
      setGenerating(false)
    }
  }, [text, buildPayload, addResult])

  const handleOpen = useCallback(async (item: VoiceResultItem) => {
    try {
      await openGeneratedMedia({ path: item.path, url: item.url })
    } catch (e) {
      setError(getErrorMessage(e, t("打开音频失败")))
    }
  }, [])

  const handleDelete = useCallback(async (item: VoiceResultItem) => {
    try {
      await deleteGeneratedMedia({ path: item.path, url: item.url })
      setResults((prev) => prev.filter((current) => current.id !== item.id))
    } catch (e) {
      setError(getErrorMessage(e, t("删除音频失败")))
    }
  }, [])

  const handleAdoptVoice = useCallback(async (item: VoiceResultItem) => {
    try {
      const result = await adoptGeneratedAsset({ path: item.path, url: item.url, type: 'audio', title: item.title })
      setResults((prev) => prev.map((current) => (
        current.id === item.id ? { ...current, adopted: true, materialId: String(result.material?.id || '') } : current
      )))
    } catch (e) {
      setError(getErrorMessage(e, t("采纳语音失败")))
    }
  }, [])

  const handleUnadoptVoice = useCallback(async (item: VoiceResultItem) => {
    try {
      await unadoptMaterial({ path: item.path, url: item.url, material_id: item.materialId })
      setResults((prev) => prev.map((current) => (
        current.id === item.id ? { ...current, adopted: false, materialId: '' } : current
      )))
    } catch (e) {
      setError(getErrorMessage(e, t("取消采纳失败")))
    }
  }, [])

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <div className="mb-2 flex items-center justify-between gap-3">
          <label className="text-body-sm text-[#94A3B8]">{t("配音文案")}</label>
          <span className="text-body-xs text-[#64748B]">{text.trim().length}  {t("字 · 预计")} {estimatedDuration}  {t("秒")}</span>
        </div>
        <ReferenceTextarea
          value={text}
          onChange={setText}
          references={references}
          onReferencesChange={setReferences}
          allowedTypes={['text']}
          placeholder={t("请输入需要合成语音的文案，例如：今天给大家介绍一款适合中小企业的智能获客工具...")}
          className="h-32"
        />

        <div className="mt-4 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <label className="mb-2 block text-body-sm text-[#94A3B8]">{t("声音描述")}</label>
            <div className="flex gap-2">
              <input
                value={voicePrompt}
                onChange={(event) => setVoicePrompt(event.target.value)}
                placeholder={t("例如：年轻女性，温柔自然，适合小红书种草，语速稍慢")}
                className="h-10 min-w-0 flex-1 rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
              />
              <button
                type="button"
                onClick={handleInterpret}
                disabled={interpreting || !voicePrompt.trim()}
                className="inline-flex h-10 shrink-0 items-center gap-2 rounded-lg border border-[#6366F1]/40 bg-[#6366F1]/10 px-3 text-body-sm text-[#C4B5FD] transition-colors hover:bg-[#6366F1]/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {interpreting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}

                {t("解析声音")}
              </button>
            </div>
            {summary && <div className="mt-2 text-body-xs text-[#64748B]">{summary}</div>}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label>
              <span className="mb-1 block text-body-xs text-[#64748B]">{t("用途")}</span>
              <select
                value={scene}
                onChange={(event) => setScene(event.target.value)}
                className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
              >
                {VOICE_SCENES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label>
              <span className="mb-1 block text-body-xs text-[#64748B]">{t("情绪")}</span>
              <select
                value={emotion}
                onChange={(event) => setEmotion(event.target.value)}
                className="h-10 w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
              >
                {VOICE_EMOTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
          </div>
        </div>

        <div className="mt-5">
          <div className="mb-3 text-body-sm text-[#94A3B8]">{t("选择声音风格")}</div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {voices.map((item) => {
              const selected = voice === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setVoice(item.id)}
                  className={`rounded-lg border p-4 text-left transition-all ${
                    selected
                      ? 'border-[#6366F1]/70 bg-[#6366F1]/15 shadow-[0_0_0_1px_rgba(99,102,241,0.2)]'
                      : 'border-[#1E293B] bg-[#0B0F1A] hover:border-[#475569] hover:bg-[#111827]'
                  }`}
                >
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <div>
                      <div className="text-body-sm font-medium text-[#F1F5F9]">{item.name}</div>
                      <div className="mt-1 text-[11px] text-[#64748B]">{item.scene}</div>
                    </div>
                    {selected && <Check className="h-4 w-4 text-[#A5B4FC]" />}
                  </div>
                  <div className="mb-3 line-clamp-2 text-body-xs text-[#94A3B8]">{item.description}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {item.tags.map((tag) => (
                      <span key={tag} className="rounded-md bg-[#1E293B] px-2 py-0.5 text-[11px] text-[#94A3B8]">{t(tag)}</span>
                    ))}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-body-xs text-[#64748B]">{t("语速")}</span>
              <span className="text-body-xs text-[#F1F5F9]">{speed.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={speed}
              onChange={(e) => setSpeed(parseFloat(e.target.value))}
              className="w-full accent-[#6366F1]"
            />
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-body-xs text-[#64748B]">{t("音调")}</span>
              <span className="text-body-xs text-[#F1F5F9]">{pitch > 0 ? `+${pitch}` : pitch}</span>
            </div>
            <input
              type="range"
              min="-100"
              max="100"
              step="10"
              value={pitch}
              onChange={(e) => setPitch(Number(e.target.value))}
              className="w-full accent-[#6366F1]"
            />
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handlePreviewVoice}
            disabled={previewLoading !== null || generating || !selectedVoice}
            className="inline-flex items-center gap-2 rounded-lg border border-[#334155] bg-[#1E293B] px-4 py-2.5 text-body-sm text-[#CBD5E1] transition-colors hover:border-[#6366F1] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {previewLoading === 'voice' ? <Loader2 className="h-4 w-4 animate-spin" /> : <MicIcon className="h-4 w-4" />}

            {t("试听声音")}
          </button>
          <button
            type="button"
            onClick={handlePreviewText}
            disabled={previewLoading !== null || generating || !text.trim()}
            className="inline-flex items-center gap-2 rounded-lg border border-[#334155] bg-[#1E293B] px-4 py-2.5 text-body-sm text-[#CBD5E1] transition-colors hover:border-[#6366F1] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {previewLoading === 'text' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}

            {t("试听当前文案")}
          </button>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating || previewLoading !== null || !text.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-[#6366F1] px-5 py-2.5 text-body-sm text-white transition-colors hover:bg-[#5558E6] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}

            {t("生成完整语音")}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm">
          {error}
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          {results.map((item) => (
            <div key={item.id} className={`glass-card relative rounded-card-lg border p-4 ${adoptionCardClass(item.adopted)}`}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-md px-2 py-0.5 text-[11px] ${item.kind === 'preview' ? 'bg-[#334155] text-[#CBD5E1]' : 'bg-[#6366F1]/20 text-[#C4B5FD]'}`}>
                      {item.kind === 'preview' ? t("试听") : t("完整生成")}
                    </span>
                    <span className="text-body-sm font-medium text-[#F1F5F9]">{item.title}</span>
                  </div>
                  <div className="mt-1 text-body-xs text-[#64748B]">
                    {item.createdAt} · {item.filename}  {t("· 约")} {item.estimated_duration}  {t("秒")}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <AdoptionActionButton
                    adopted={item.adopted}
                    onClick={() => (item.adopted ? handleUnadoptVoice(item) : handleAdoptVoice(item))}
                  />
                  <button onClick={() => handleOpen(item)} className="inline-flex items-center gap-1.5 rounded-md bg-[#1E293B] px-3 py-1.5 text-body-xs text-[#94A3B8] transition-colors hover:bg-[#334155] hover:text-[#F1F5F9]">
                    <ExternalLink className="h-3.5 w-3.5" />

                    {t("打开")}
                  </button>
                  <button onClick={() => copyReference({
                    type: 'audio',
                    path: item.path,
                    url: item.url,
                    title: item.title,
                  })} className="inline-flex items-center gap-1.5 rounded-md bg-[#1E293B] px-3 py-1.5 text-body-xs text-[#94A3B8] transition-colors hover:bg-[#334155] hover:text-[#F1F5F9]">
                    <Copy className="h-3.5 w-3.5" />

                    {t("引用")}
                  </button>
                  <button onClick={() => handleDelete(item)} className="inline-flex items-center gap-1.5 rounded-md bg-[#1E293B] px-3 py-1.5 text-body-xs text-[#94A3B8] transition-colors hover:bg-[#7F1D1D] hover:text-white">
                    <Trash2 className="h-3.5 w-3.5" />

                    {t("删除")}
                  </button>
                </div>
              </div>
              <audio src={resolveGeneratedAssetUrl(item.url, item.path)} controls className="w-full" />
              <div className="mt-2 truncate text-body-xs text-[#64748B]">{t("保存到：")}{item.path}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
