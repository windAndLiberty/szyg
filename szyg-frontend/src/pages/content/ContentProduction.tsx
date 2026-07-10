import { useState, useCallback, useEffect } from 'react'
import { Link } from 'react-router'
import { motion } from 'framer-motion'
import {
  PenLine as ContentProductionIcon,
  Image as ImageIcon,
  Video as VideoIcon,
  FileText as TextIcon,
  Mic as MicIcon,
  Download,
  ExternalLink,
  Copy,
  Check,
  Loader2,
  Send,
  Sparkles,
  FolderOpen,
  Save,
  Trash2,
} from 'lucide-react'
import {
  createVideo,
  pollVideoTask,
  getErrorMessage,
  fetchMediaStorage,
  updateMediaStorage,
  saveGeneratedDocument,
  openGeneratedMedia,
  deleteGeneratedMedia,
  type MediaStorageConfig,
} from '@/lib/api'
import {
  getImageGenerationState,
  startImageDraftGeneration,
  subscribeImageGeneration,
  removeGeneratedImageAsset,
  type GeneratedImageAsset,
} from '@/lib/contentDraftStore'
import { downloadGeneratedAsset, resolveGeneratedAssetUrl } from '@/lib/generatedAssets'

type Tab = 'image' | 'video' | 'copy' | 'voice'
type ImageStyle = 'none' | 'realistic' | 'product' | 'xiaohongshu_cover' | 'douyin_cover' | 'anime' | 'oil' | 'watercolor' | 'cyberpunk' | 'minimal'
type ImageSize = '1920x1920' | '2560x1440' | '1440x2560' | '2048x2048' | '2304x1728' | '3072x1296'
type VoiceType = 'male' | 'female' | 'child'

const TABS: { key: Tab; label: string; icon: typeof ImageIcon }[] = [
  { key: 'image', label: '文生图', icon: ImageIcon },
  { key: 'video', label: '文生视频', icon: VideoIcon },
  { key: 'copy', label: '文案生成', icon: TextIcon },
  { key: 'voice', label: '语音合成', icon: MicIcon },
]

const IMAGE_STYLES: { key: ImageStyle; label: string }[] = [
  { key: 'none', label: '未定义风格' },
  { key: 'realistic', label: '写实' },
  { key: 'product', label: '电商产品图' },
  { key: 'xiaohongshu_cover', label: '小红书封面' },
  { key: 'douyin_cover', label: '抖音封面' },
  { key: 'anime', label: '动漫' },
  { key: 'oil', label: '油画' },
  { key: 'watercolor', label: '水彩' },
  { key: 'cyberpunk', label: '赛博朋克' },
  { key: 'minimal', label: '极简' },
]

const IMAGE_SIZES: { key: ImageSize; label: string }[] = [
  { key: '1920x1920', label: '1920 x 1920 方图' },
  { key: '2560x1440', label: '2560 x 1440 横屏' },
  { key: '1440x2560', label: '1440 x 2560 竖屏' },
  { key: '2048x2048', label: '2048 x 2048 高清方图' },
  { key: '2304x1728', label: '2304 x 1728 横图' },
  { key: '3072x1296', label: '3072 x 1296 宽屏' },
]

const VOICE_TYPES: { key: VoiceType; label: string }[] = [
  { key: 'male', label: '男声' },
  { key: 'female', label: '女声' },
  { key: 'child', label: '童声' },
]

export default function ContentProduction() {
  const [activeTab, setActiveTab] = useState<Tab>('image')

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="flex flex-col h-full"
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#1E293B]">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center">
          <ContentProductionIcon className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-display-sm text-[#F1F5F9]">内容生产</h1>
          <p className="text-body-sm text-[#64748B]">AI驱动的内容创作工作台</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 px-6 py-3 border-b border-[#1E293B]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
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

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {activeTab === 'image' && <ImageGeneration />}
        {activeTab === 'video' && <VideoGeneration />}
        {activeTab === 'copy' && <CopyGeneration />}
        {activeTab === 'voice' && <VoiceSynthesis />}
      </div>
    </motion.div>
  )
}

function AutoSaveControl({ activeTab, onEnabledChange }: { activeTab: Tab; onEnabledChange?: (enabled: boolean) => void }) {
  const storageKey = `szyg.contentProduction.autoSave.${activeTab}`
  const [config, setConfig] = useState<MediaStorageConfig | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [enabled, setEnabled] = useState(() => localStorage.getItem(storageKey) === 'true')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    localStorage.setItem(storageKey, enabled ? 'true' : 'false')
    onEnabledChange?.(enabled)
  }, [enabled, onEnabledChange, storageKey])

  useEffect(() => {
    let cancelled = false
    fetchMediaStorage()
      .then((data) => {
        if (cancelled) return
        setConfig(data)
        setDraft({
          image_dir: data.image_dir,
          video_dir: data.video_dir,
          audio_dir: data.audio_dir,
          document_dir: data.document_dir,
        })
      })
      .catch((error) => {
        if (!cancelled) setMessage(getErrorMessage(error, '存储位置读取失败'))
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setMessage('')
    try {
      const next = await updateMediaStorage(draft)
      setConfig(next)
      setDraft({
        image_dir: next.image_dir,
        video_dir: next.video_dir,
        audio_dir: next.audio_dir,
        document_dir: next.document_dir,
      })
      setEditing(false)
      setMessage('路径已更新')
      window.setTimeout(() => setMessage(''), 1500)
    } catch (error) {
      setMessage(getErrorMessage(error, '存储位置保存失败'))
    } finally {
      setSaving(false)
    }
  }, [draft])

  const activeStorage = {
    image: { key: 'image_dir', label: '图片' },
    video: { key: 'video_dir', label: '视频' },
    copy: { key: 'document_dir', label: '文案' },
    voice: { key: 'audio_dir', label: '语音' },
  }[activeTab]
  const activePath = (draft[activeStorage.key] || config?.[activeStorage.key as keyof MediaStorageConfig] || '') as string

  const handleEdit = useCallback(() => {
    setMessage('')
    setDraft((value) => ({ ...value, [activeStorage.key]: activePath }))
    setEditing(true)
  }, [activeStorage.key, activePath])

  const handleCancel = useCallback(() => {
    setMessage('')
    const original = config?.[activeStorage.key as keyof MediaStorageConfig]
    setDraft((value) => ({ ...value, [activeStorage.key]: typeof original === 'string' ? original : activePath }))
    setEditing(false)
  }, [activeStorage.key, activePath, config])

  return (
    <div className="mb-4 rounded-lg border border-[#1E293B] bg-[#0B0F1A]/80 p-3">
      <div className="flex min-h-[44px] flex-col gap-3 xl:flex-row xl:items-center">
        <button
          type="button"
          onClick={() => setEnabled((value) => !value)}
          aria-pressed={enabled}
          className={`inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg border px-4 text-body-sm font-medium shadow-sm transition-all ${
            enabled
              ? 'border-[#6366F1]/70 bg-[#6366F1] text-white hover:bg-[#5558E6]'
              : 'border-[#334155] bg-[#1E293B] text-[#CBD5E1] hover:border-[#475569] hover:bg-[#334155]'
          }`}
        >
          {enabled ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
          {enabled ? '自动保存' : '自动保存'}
        </button>

        {enabled && (
          <div className="flex min-h-10 min-w-0 flex-1 flex-col gap-2 rounded-lg border border-[#6366F1]/25 bg-[#6366F1]/10 px-3 py-1.5 md:flex-row md:items-center">
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <FolderOpen className="h-4 w-4 shrink-0 text-[#A5B4FC]" />
              <span className="shrink-0 text-body-xs font-medium text-[#C7D2FE]">{activeStorage.label}保存到：</span>
              {editing ? (
                <input
                  value={draft[activeStorage.key] || activePath || ''}
                  onChange={(event) => setDraft((value) => ({ ...value, [activeStorage.key]: event.target.value }))}
                  className="h-7 min-w-0 flex-1 rounded-md border border-[#6366F1]/45 bg-[#020617] px-2 text-body-xs text-[#E2E8F0] outline-none transition-colors focus:border-[#818CF8]"
                />
              ) : (
                <span className="min-w-0 flex-1 truncate text-body-xs text-[#C7D2FE]">
                  {activePath || '正在读取...'}
                </span>
              )}
            </div>
            {message && <span className="text-body-xs text-[#94A3B8]">{message}</span>}
            {editing ? (
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="inline-flex h-7 shrink-0 items-center justify-center gap-2 rounded-md bg-[#6366F1] px-3 text-body-xs font-medium text-white transition-colors hover:bg-[#5558E6] disabled:opacity-50"
              >
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                应用路径
              </button>
            ) : (
              <button
                type="button"
                onClick={handleEdit}
                className="h-7 shrink-0 rounded-md border border-[#6366F1]/35 px-3 text-body-xs font-medium text-[#C7D2FE] transition-colors hover:bg-[#6366F1]/15"
              >
                更改
              </button>
            )}
            {editing && (
              <button
                type="button"
                onClick={handleCancel}
                disabled={saving}
                className="h-7 shrink-0 rounded-md border border-[#334155] px-3 text-body-xs font-medium text-[#CBD5E1] transition-colors hover:bg-[#1E293B] disabled:opacity-50"
              >
                取消
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ImageGeneration() {
  const initialGeneration = getImageGenerationState()
  const [prompt, setPrompt] = useState(initialGeneration.prompt)
  const [style, setStyle] = useState<ImageStyle>((initialGeneration.style || 'none') as ImageStyle)
  const [size, setSize] = useState<ImageSize>((initialGeneration.size || '1920x1920') as ImageSize)
  const [count, setCount] = useState(initialGeneration.count || 1)
  const [generation, setGeneration] = useState(initialGeneration)

  useEffect(() => subscribeImageGeneration(setGeneration), [])

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return
    await startImageDraftGeneration({ prompt, style, size, count })
  }, [prompt, style, size, count])

  const handleDownload = useCallback(async (asset: GeneratedImageAsset) => {
    try {
      await downloadGeneratedAsset(asset, `generated-${Date.now()}.jpg`)
    } catch {
      // downloadGeneratedAsset already provides a user-visible fallback.
    }
  }, [])

  const handleCopyPath = useCallback(async (asset: GeneratedImageAsset) => {
    const value = asset.path || resolveGeneratedAssetUrl(asset.url, asset.path)
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      window.alert(value)
    }
  }, [])

  const handleOpenAsset = useCallback(async (asset: GeneratedImageAsset) => {
    try {
      await openGeneratedMedia({ path: asset.path, url: asset.url })
    } catch (error) {
      window.alert(getErrorMessage(error, '打开图片失败'))
    }
  }, [])

  const handleDeleteAsset = useCallback(async (asset: GeneratedImageAsset) => {
    const ok = window.confirm('确定删除这张图片吗？如果文件保存在本机媒体目录中，也会同步删除本地文件。')
    if (!ok) return
    try {
      await deleteGeneratedMedia({ path: asset.path, url: asset.url })
    } catch (error) {
      window.alert(getErrorMessage(error, '删除本地图片失败'))
      return
    }
    removeGeneratedImageAsset(asset)
  }, [])

  return (
    <div className="space-y-6">
      {/* Input */}
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <AutoSaveControl activeTab="image" />

        <label className="text-body-sm text-[#94A3B8] mb-2 block">描述图片内容</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="例如：一只可爱的橘猫坐在窗台上，阳光洒进来，温暖的氛围..."
          className="w-full h-24 bg-[#0B0F1A] border border-[#1E293B] rounded-lg px-4 py-3 text-body-md text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#6366F1] resize-none"
        />

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">风格</span>
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
            <span className="text-body-xs text-[#64748B] mb-1 block">分辨率</span>
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
            <span className="text-body-xs text-[#64748B] mb-1 block">生成张数</span>
            <select
              value={count}
              onChange={(event) => setCount(Number(event.target.value))}
              className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {[1, 2, 3, 4].map((value) => (
                <option key={value} value={value}>{value} 张</option>
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
          生成图片
        </button>
      </div>

      {generation.loading && (
        <div className="glass-card rounded-card-lg border border-[#6366F1]/30 bg-[#6366F1]/10 p-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-[#6366F1]" />
            <div>
              <div className="text-body-sm font-medium text-[#F1F5F9]">图片生成中</div>
              <div className="mt-1 text-body-xs text-[#94A3B8]">
                生成任务已在后台继续执行，切换到发布中心或其他页面不会中断。
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
              <div className="text-body-sm text-[#F1F5F9] font-medium">已生成内容草稿</div>
              <div className="mt-1 text-body-xs text-[#94A3B8]">发布中心会自动读取这批素材，保持生产到发布的连续操作流。</div>
            </div>
            <Link
              to="/publish/center"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#10B981] px-4 py-2 text-body-sm font-medium text-white transition-colors hover:bg-[#059669]"
            >
              <Send className="h-4 w-4" />
              去发布
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {generation.results.map((asset, i) => (
            <div key={`${asset.path}-${i}`} className="glass-card rounded-card-lg border border-[#1E293B] overflow-hidden group">
              <img
                src={resolveGeneratedAssetUrl(asset.url, asset.path)}
                alt={`Generated ${i + 1}`}
                className="w-full aspect-square object-cover"
              />
              <div className="p-3 flex flex-wrap justify-end gap-2">
                <button
                  onClick={() => handleOpenAsset(asset)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  打开
                </button>
                <button
                  onClick={() => handleCopyPath(asset)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors"
                >
                  <Copy className="w-3.5 h-3.5" />
                  复制路径
                </button>
                <button
                  onClick={() => handleDownload(asset)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  下载
                </button>
                <button
                  onClick={() => handleDeleteAsset(asset)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#7F1D1D] text-[#94A3B8] hover:text-white text-body-xs transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  删除
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

function VideoGeneration() {
  const [prompt, setPrompt] = useState('')
  const [duration, setDuration] = useState(5)
  const [videoSize, setVideoSize] = useState('720p')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    setProgress(0)
    setVideoUrl(null)

    try {
      const res = await createVideo(prompt, { duration, size: videoSize })
      if (res.ok) {
        // Poll for status
        const poll = setInterval(async () => {
          try {
            const status = await pollVideoTask(res.task_id)
            setProgress(status.progress || 0)
            if (status.status === 'succeed' && status.video_url) {
              clearInterval(poll)
              setVideoUrl(status.video_url)
              setLoading(false)
            } else if (status.status === 'failed') {
              clearInterval(poll)
              setError(status.error || '视频生成失败')
              setLoading(false)
            }
          } catch {
            // Continue polling
          }
        }, 2000)
      }
    } catch (e) {
      setError(getErrorMessage(e, '视频生成失败'))
      setLoading(false)
    }
  }, [prompt, duration, videoSize])

  return (
    <div className="space-y-6">
      {/* Input */}
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <AutoSaveControl activeTab="video" />

        <label className="text-body-sm text-[#94A3B8] mb-2 block">描述视频内容</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="例如：日出时分的海边，海浪轻轻拍打沙滩，金色的阳光洒在海面上..."
          className="w-full h-24 bg-[#0B0F1A] border border-[#1E293B] rounded-lg px-4 py-3 text-body-md text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#6366F1] resize-none"
        />

        <div className="grid gap-4 mt-4 md:grid-cols-2">
          <div>
            <label className="text-body-xs text-[#64748B] mb-1 block">时长</label>
            <div className="flex gap-1">
              {[5, 10].map((d) => (
                <button
                  key={d}
                  onClick={() => setDuration(d)}
                  className={`px-3 py-1.5 rounded-md text-body-xs transition-all ${
                    duration === d
                      ? 'bg-[#6366F1] text-white'
                      : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
                  }`}
                >
                  {d}秒
                </button>
              ))}
            </div>
          </div>
          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">分辨率</span>
            <select
              value={videoSize}
              onChange={(event) => setVideoSize(event.target.value)}
              className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              <option value="720p">720p</option>
              <option value="1080p">1080p</option>
            </select>
          </label>
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
          生成视频
        </button>
      </div>

      {/* Progress */}
      {loading && (
        <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
          <div className="flex items-center gap-3 mb-3">
            <Loader2 className="w-5 h-5 text-[#6366F1] animate-spin" />
            <span className="text-body-sm text-[#F1F5F9]">正在生成视频...</span>
            <span className="text-body-xs text-[#64748B]">{progress}%</span>
          </div>
          <div className="w-full h-2 bg-[#1E293B] rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-[#6366F1] to-[#8B5CF6]"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm">
          {error}
        </div>
      )}

      {/* Result */}
      {videoUrl && (
        <div className="glass-card rounded-card-lg border border-[#1E293B] overflow-hidden">
          <video src={videoUrl} controls className="w-full max-h-[400px] bg-black" />
        </div>
      )}
    </div>
  )
}

function CopyGeneration() {
  const [prompt, setPrompt] = useState('')
  const [copyType, setCopyType] = useState('未定义类型')
  const [copyCount, setCopyCount] = useState(5)
  const [autoSave, setAutoSave] = useState(false)
  const [loading, setLoading] = useState(false)
  const [copies, setCopies] = useState<string[]>([])
  const [savedPath, setSavedPath] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    setSavedPath('')
    try {
      const res = await fetch('/api/hermes/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'doubao-seed-2-0-pro-260215',
          messages: [
            { role: 'system', content: `你是一个专业的文案撰写专家。请根据用户需求生成${copyCount}条不同的营销文案。文案类型：${copyType}。每条文案独立一行，以数字开头。` },
            { role: 'user', content: prompt },
          ],
          stream: false,
        }),
      })
      const data = await res.json()
      const content = data.choices?.[0]?.message?.content || ''
      const lines = content.split('\n').filter((l: string) => l.trim())
      const nextCopies = lines.slice(0, copyCount)
      setCopies(nextCopies)
      if (autoSave && nextCopies.length > 0) {
        const doc = [`# ${copyType}`, '', `需求：${prompt}`, '', ...nextCopies.map((line: string, index: number) => `${index + 1}. ${line.replace(/^\d+[.、)]\s*/, '')}`)].join('\n')
        const saved = await saveGeneratedDocument(copyType, doc, 'md')
        setSavedPath(saved.path)
      }
    } catch (e) {
      setError(getErrorMessage(e, '文案生成失败'))
    } finally {
      setLoading(false)
    }
  }, [prompt, copyType, copyCount, autoSave])

  const handleCopy = useCallback((text: string, idx: number) => {
    navigator.clipboard.writeText(text)
    setCopiedIdx(idx)
    setTimeout(() => setCopiedIdx(null), 2000)
  }, [])

  return (
    <div className="space-y-6">
      {/* Input */}
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <AutoSaveControl activeTab="copy" onEnabledChange={setAutoSave} />

        <label className="text-body-sm text-[#94A3B8] mb-2 block">输入文案需求</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="例如：为一款新能源汽车写5条朋友圈文案，突出科技感和环保..."
          className="w-full h-24 bg-[#0B0F1A] border border-[#1E293B] rounded-lg px-4 py-3 text-body-md text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#6366F1] resize-none"
        />
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">文案类型</span>
            <select
              value={copyType}
              onChange={(event) => setCopyType(event.target.value)}
              className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {['未定义类型', '小红书文案', '抖音标题', '朋友圈文案', '企业宣传', '评论区回复', '私信话术'].map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <label>
            <span className="text-body-xs text-[#64748B] mb-1 block">生成数量</span>
            <select
              value={copyCount}
              onChange={(event) => setCopyCount(Number(event.target.value))}
              className="w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2 text-body-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>{value} 条</option>
              ))}
            </select>
          </label>
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
          生成文案
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {copies.length > 0 && (
        <div className="space-y-3">
          {savedPath && (
            <div className="glass-card rounded-card-lg border border-[#10B981]/30 bg-[#10B981]/10 p-4 text-body-sm text-[#D1FAE5]">
              已保存到：{savedPath}
            </div>
          )}
          {copies.map((copy, i) => (
            <div key={i} className="glass-card rounded-card-lg border border-[#1E293B] p-4 flex items-start justify-between gap-4">
              <p className="text-body-md text-[#F1F5F9] flex-1">{copy}</p>
              <button
                onClick={() => handleCopy(copy, i)}
                className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors"
              >
                {copiedIdx === i ? (
                  <><Check className="w-3.5 h-3.5 text-[#10B981]" /> 已复制</>
                ) : (
                  <><Copy className="w-3.5 h-3.5" /> 复制</>
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function VoiceSynthesis() {
  const [text, setText] = useState('')
  const [voice, setVoice] = useState<VoiceType>('female')
  const [speed, setSpeed] = useState(1.0)
  const [loading, setLoading] = useState(false)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = useCallback(async () => {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/tts/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice, speed }),
      })
      if (!res.ok) throw new Error('语音合成失败')
      const blob = await res.blob()
      setAudioUrl(URL.createObjectURL(blob))
    } catch (e) {
      setError(getErrorMessage(e, '语音合成失败'))
    } finally {
      setLoading(false)
    }
  }, [text, voice, speed])

  return (
    <div className="space-y-6">
      {/* Input */}
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <AutoSaveControl activeTab="voice" />

        <label className="text-body-sm text-[#94A3B8] mb-2 block">输入文本</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="请输入需要合成语音的文本内容..."
          className="w-full h-32 bg-[#0B0F1A] border border-[#1E293B] rounded-lg px-4 py-3 text-body-md text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#6366F1] resize-none"
        />

        <div className="flex flex-wrap gap-4 mt-4">
          {/* Voice */}
          <div>
            <label className="text-body-xs text-[#64748B] mb-1 block">声音</label>
            <div className="flex gap-1">
              {VOICE_TYPES.map((v) => (
                <button
                  key={v.key}
                  onClick={() => setVoice(v.key)}
                  className={`px-3 py-1.5 rounded-md text-body-xs transition-all ${
                    voice === v.key
                      ? 'bg-[#6366F1] text-white'
                      : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
                  }`}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </div>

          {/* Speed */}
          <div className="flex-1 min-w-[200px]">
            <label className="text-body-xs text-[#64748B] mb-1 block">语速: {speed.toFixed(1)}x</label>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={speed}
              onChange={(e) => setSpeed(parseFloat(e.target.value))}
              className="w-full h-2 bg-[#1E293B] rounded-full appearance-none cursor-pointer accent-[#6366F1]"
            />
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading || !text.trim()}
          className="mt-4 flex items-center gap-2 px-6 py-2.5 bg-[#6366F1] hover:bg-[#5558E6] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-body-sm text-white transition-colors"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <MicIcon className="w-4 h-4" />
          )}
          生成语音
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm">
          {error}
        </div>
      )}

      {/* Result */}
      {audioUrl && (
        <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
          <audio src={audioUrl} controls className="w-full" />
        </div>
      )}
    </div>
  )
}
