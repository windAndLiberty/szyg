import { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  PenLine as ContentProductionIcon,
  Image as ImageIcon,
  Video as VideoIcon,
  FileText as TextIcon,
  Mic as MicIcon,
  Download,
  Copy,
  Check,
  Loader2,
  Sparkles,
} from 'lucide-react'
import { generateImage, createVideo, pollVideoTask, getErrorMessage } from '@/lib/api'

type Tab = 'image' | 'video' | 'copy' | 'voice'
type ImageStyle = 'realistic' | 'anime' | 'oil' | 'watercolor' | 'cyberpunk'
type ImageSize = '1024x1024' | '1920x1920' | '2560x1440'
type VoiceType = 'male' | 'female' | 'child'

const TABS: { key: Tab; label: string; icon: typeof ImageIcon }[] = [
  { key: 'image', label: '文生图', icon: ImageIcon },
  { key: 'video', label: '文生视频', icon: VideoIcon },
  { key: 'copy', label: '文案生成', icon: TextIcon },
  { key: 'voice', label: '语音合成', icon: MicIcon },
]

const IMAGE_STYLES: { key: ImageStyle; label: string }[] = [
  { key: 'realistic', label: '写实' },
  { key: 'anime', label: '动漫' },
  { key: 'oil', label: '油画' },
  { key: 'watercolor', label: '水彩' },
  { key: 'cyberpunk', label: '赛博朋克' },
]

const IMAGE_SIZES: { key: ImageSize; label: string }[] = [
  { key: '1024x1024', label: '1024×1024' },
  { key: '1920x1920', label: '1920×1920' },
  { key: '2560x1440', label: '2560×1440' },
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

function ImageGeneration() {
  const [prompt, setPrompt] = useState('')
  const [style, setStyle] = useState<ImageStyle>('realistic')
  const [size, setSize] = useState<ImageSize>('1920x1920')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await generateImage(`${prompt}, ${style} style`, size)
      setResults(res.images || [])
    } catch (e) {
      setError(getErrorMessage(e, '图片生成失败'))
    } finally {
      setLoading(false)
    }
  }, [prompt, style, size])

  const handleDownload = useCallback((url: string) => {
    const a = document.createElement('a')
    a.href = url
    a.download = `generated-${Date.now()}.png`
    a.click()
  }, [])

  return (
    <div className="space-y-6">
      {/* Input */}
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <label className="text-body-sm text-[#94A3B8] mb-2 block">描述图片内容</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="例如：一只可爱的橘猫坐在窗台上，阳光洒进来，温暖的氛围..."
          className="w-full h-24 bg-[#0B0F1A] border border-[#1E293B] rounded-lg px-4 py-3 text-body-md text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#6366F1] resize-none"
        />

        <div className="flex flex-wrap gap-4 mt-4">
          {/* Style */}
          <div>
            <label className="text-body-xs text-[#64748B] mb-1 block">风格</label>
            <div className="flex gap-1">
              {IMAGE_STYLES.map((s) => (
                <button
                  key={s.key}
                  onClick={() => setStyle(s.key)}
                  className={`px-3 py-1.5 rounded-md text-body-xs transition-all ${
                    style === s.key
                      ? 'bg-[#6366F1] text-white'
                      : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Size */}
          <div>
            <label className="text-body-xs text-[#64748B] mb-1 block">分辨率</label>
            <div className="flex gap-1">
              {IMAGE_SIZES.map((s) => (
                <button
                  key={s.key}
                  onClick={() => setSize(s.key)}
                  className={`px-3 py-1.5 rounded-md text-body-xs transition-all ${
                    size === s.key
                      ? 'bg-[#6366F1] text-white'
                      : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
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
          生成
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {results.map((url, i) => (
            <div key={i} className="glass-card rounded-card-lg border border-[#1E293B] overflow-hidden group">
              <img src={url} alt={`Generated ${i + 1}`} className="w-full aspect-square object-cover" />
              <div className="p-3 flex justify-end gap-2">
                <button
                  onClick={() => handleDownload(url)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-[#F1F5F9] text-body-xs transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  下载
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function VideoGeneration() {
  const [prompt, setPrompt] = useState('')
  const [duration, setDuration] = useState(5)
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
      const res = await createVideo(prompt, { duration })
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
  }, [prompt, duration])

  return (
    <div className="space-y-6">
      {/* Input */}
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <label className="text-body-sm text-[#94A3B8] mb-2 block">描述视频内容</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="例如：日出时分的海边，海浪轻轻拍打沙滩，金色的阳光洒在海面上..."
          className="w-full h-24 bg-[#0B0F1A] border border-[#1E293B] rounded-lg px-4 py-3 text-body-md text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#6366F1] resize-none"
        />

        <div className="flex items-center gap-4 mt-4">
          <div>
            <label className="text-body-xs text-[#64748B] mb-1 block">时长</label>
            <div className="flex gap-1">
              {[5, 10, 15].map((d) => (
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
  const [loading, setLoading] = useState(false)
  const [copies, setCopies] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    try {
      // Generate 5 copies using AI
      const res = await fetch('/api/hermes/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'doubao-seed-2-0-pro-260215',
          messages: [
            { role: 'system', content: '你是一个专业的文案撰写专家。请根据用户需求生成5条不同的营销文案。每条文案独立一行，以数字开头。' },
            { role: 'user', content: prompt },
          ],
          stream: false,
        }),
      })
      const data = await res.json()
      const content = data.choices?.[0]?.message?.content || ''
      const lines = content.split('\n').filter((l: string) => l.trim())
      setCopies(lines.slice(0, 5))
    } catch (e) {
      setError(getErrorMessage(e, '文案生成失败'))
    } finally {
      setLoading(false)
    }
  }, [prompt])

  const handleCopy = useCallback((text: string, idx: number) => {
    navigator.clipboard.writeText(text)
    setCopiedIdx(idx)
    setTimeout(() => setCopiedIdx(null), 2000)
  }, [])

  return (
    <div className="space-y-6">
      {/* Input */}
      <div className="glass-card rounded-card-lg border border-[#1E293B] p-6">
        <label className="text-body-sm text-[#94A3B8] mb-2 block">输入文案需求</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="例如：为一款新能源汽车写5条朋友圈文案，突出科技感和环保..."
          className="w-full h-24 bg-[#0B0F1A] border border-[#1E293B] rounded-lg px-4 py-3 text-body-md text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#6366F1] resize-none"
        />
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
          生成5条文案
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
