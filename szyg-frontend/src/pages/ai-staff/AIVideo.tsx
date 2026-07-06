import { useState, useCallback, useRef, useEffect } from 'react'
import { streamHermesChat, getErrorMessage, apiGet, apiPost } from '@/lib/api'
import type { HermesEvent } from '@/lib/api'
import VideoToolbox from './video/VideoToolbox'
import CreateDialog from './video/CreateDialog'
import VideoPreview from './video/VideoPreview'
import type { PreviewMessage } from './video/VideoPreview'
import VideoLibrary from './video/VideoLibrary'
import PublishPanel from './video/PublishPanel'
import type { PageStatus, VideoItem, EditStep, VideoGenParams, PublishTarget } from './video/types'

const DEFAULT_MODEL = 'doubao-seed-2-0-pro-260215'

export default function AIVideo() {
  // ── Page state ──
  const [status, setStatus] = useState<PageStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  // ── Video state ──
  const [currentVideo, setCurrentVideo] = useState<VideoItem | null>(null)
  const [library, setLibrary] = useState<VideoItem[]>([])
  const [progress, setProgress] = useState(0)
  const [progressPrompt, setProgressPrompt] = useState('')

  // ── Toolbox state ──
  const [editChain, setEditChain] = useState<EditStep[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [showPublish, setShowPublish] = useState(false)
  const [generating, setGenerating] = useState(false)

  // ── Chat state ──
  const [messages, setMessages] = useState<PreviewMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const streamBufRef = useRef('')
  const streamIdRef = useRef<string | null>(null)

  // ── Load library on mount ──
  useEffect(() => {
    apiGet<VideoItem[]>('/api/video/library')
      .then(setLibrary)
      .catch(() => setLibrary([]))
  }, [])

  // ── Tool handlers ──
  const handleToolClick = useCallback((tool: string) => {
    const labels: Record<string, string> = {
      cut: '✂️ 裁剪', concat: '🔗 拼接', speed: '⏱ 变速',
      title: 'T 叠加标题', mix_audio: '🎵 混音', extract_frame: '🖼 提取封面',
    }
    setEditChain((prev) => [...prev, { tool, label: labels[tool] || tool, params: {} }])
    setStatus('editing')
  }, [])

  const handleRemoveStep = useCallback((idx: number) => {
    setEditChain((prev) => prev.filter((_, i) => i !== idx))
  }, [])

  const handleApplyChain = useCallback(async () => {
    if (!currentVideo || editChain.length === 0) return
    setError(null)
    // Send as a chat command for the AI to execute the chain
    const steps = editChain.map((s) => s.label).join(' → ')
    const text = `对当前视频依次执行：${steps}`
    setInputText(text)
  }, [currentVideo, editChain])

  const handleClearChain = useCallback(() => setEditChain([]), [])

  // ── AI Generation ──
  const handleCreateSubmit = useCallback(async (params: VideoGenParams) => {
    setShowCreate(false)
    setGenerating(true)
    setStatus('generating')
    setProgress(0)
    setProgressPrompt(params.prompt)
    setError(null)

    try {
      const res = await apiPost<{ ok: boolean; task_id: string }>('/api/video/create', {
        prompt: params.prompt,
        duration: params.duration,
        size: '720p',
        model: params.model,
      })

      if (res.ok) {
        // Poll for status
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await apiGet<{ status: string; progress: number; video_url?: string }>(
              `/api/video/status/${res.task_id}?model=${params.model}`,
            )
            setProgress(statusRes.progress || 0)

            if (statusRes.status === 'succeed' && statusRes.video_url) {
              clearInterval(pollInterval)
              const newVideo: VideoItem = {
                id: res.task_id,
                title: params.prompt.slice(0, 40),
                url: statusRes.video_url,
                duration: params.duration,
                size_mb: 0,
                resolution: '1920×1080',
                status: 'ready',
                progress: 100,
                created_at: new Date().toISOString(),
                source: 'ai',
              }
              setCurrentVideo(newVideo)
              setLibrary((prev) => [newVideo, ...prev])
              setStatus('previewing')
              setGenerating(false)
              setMessages((prev) => [...prev, {
                role: 'assistant',
                content: `✅ 视频生成完成！「${params.prompt.slice(0, 40)}」`,
              }])
            } else if (statusRes.status === 'failed') {
              clearInterval(pollInterval)
              setStatus('error')
              setError('视频生成失败，请重试')
              setGenerating(false)
            }
          } catch {
            // polling continues
          }
        }, 2000)
      }
    } catch (e) {
      setStatus('error')
      setError(getErrorMessage(e, '视频生成失败'))
      setGenerating(false)
    }
  }, [])

  // ── Chat / Send ──
  const handleSend = useCallback(async () => {
    if (!inputText.trim() || streaming) return
    const text = inputText.trim()
    setInputText('')

    const userMsg: PreviewMessage = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])

    setStreaming(true)
    streamBufRef.current = ''
    const streamId = `stream-${Date.now()}`
    streamIdRef.current = streamId

    setMessages((prev) => [...prev, { role: 'assistant', content: '', isStreaming: true }])

    try {
      await streamHermesChat({
        model: DEFAULT_MODEL,
        messages: [...messages, userMsg].map((m) => ({ role: m.role, content: m.content })),
        onEvent: (ev: HermesEvent) => {
          if (streamIdRef.current !== streamId) return

          if (ev.type === 'text' && ev.content) {
            streamBufRef.current += ev.content
            setMessages((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              if (last?.isStreaming) {
                next[next.length - 1] = { ...last, content: streamBufRef.current }
              }
              return next
            })
          } else if (ev.type === 'tool_result') {
            // Extract video URL from tool results if present
            try {
              const result = JSON.parse(ev.result || '{}')
              if (result.video_url || result.output_path) {
                const url = result.video_url || result.output_path || ''
                setCurrentVideo((prev) => prev ? { ...prev, url } : null)
              }
              if (result.status === 'succeed' && result.url) {
                const newVid: VideoItem = {
                  id: ev.id || `vid-${Date.now()}`,
                  title: text.slice(0, 40),
                  url: result.url,
                  duration: 0,
                  size_mb: 0,
                  resolution: '1920×1080',
                  status: 'ready',
                  progress: 100,
                  created_at: new Date().toISOString(),
                  source: 'ai',
                }
                setCurrentVideo(newVid)
                setLibrary((prev) => [newVid, ...prev])
                setStatus('previewing')
              }
            } catch { /* raw result */ }
          } else if (ev.type === 'video_status' || ev.type === 'video_task') {
            setProgress(typeof ev.progress === 'number' ? ev.progress : 0)
          }
        },
      })
    } catch (e) {
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last?.isStreaming) {
          next[next.length - 1] = { role: 'assistant', content: `⚠️ ${getErrorMessage(e)}` }
        }
        return next
      })
    } finally {
      setStreaming(false)
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last?.isStreaming) next[next.length - 1] = { ...last, isStreaming: false }
        return next
      })
    }
  }, [inputText, streaming, messages])

  // ── Library handlers ──
  const handleSelectVideo = useCallback((video: VideoItem) => {
    setCurrentVideo(video)
    if (video.status === 'ready') setStatus('previewing')
  }, [])

  const handleDeleteVideo = useCallback((id: string) => {
    setLibrary((prev) => prev.filter((v) => v.id !== id))
    if (currentVideo?.id === id) {
      setCurrentVideo(null)
      setStatus('idle')
    }
    apiGet(`/api/video/${id}`).catch(() => {}) // TODO: switch to apiDel when backend ready
  }, [currentVideo])

  // ── Publish ──
  const handlePublish = useCallback(async (target: PublishTarget) => {
    setShowPublish(false)
    try {
      await apiPost('/api/publisher/publish', {
        platform: target.platform,
        title: target.title,
        tags: target.tags,
        description: target.description,
        video_url: currentVideo?.url || '',
      })
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: `✅ 已成功发布到${target.platform}：${target.title}`,
      }])
    } catch (e) {
      setError(getErrorMessage(e, '发布失败'))
    }
  }, [currentVideo])

  // ── Disabled state ──
  const disabled = streaming || generating || status === 'generating'

  return (
    <div className="flex flex-1 min-h-0 gap-0">
      {/* ── 左栏：工具箱 ── */}
      <VideoToolbox
        onCreateClick={() => setShowCreate(true)}
        onUploadClick={() => {
          // Trigger file input via ref
          const input = document.createElement('input')
          input.type = 'file'
          input.accept = '.mp4,.mov,.avi,.mkv'
          input.onchange = async (e) => {
            const file = (e.target as HTMLInputElement).files?.[0]
            if (!file) return
            // Simple upload — in production use FormData
            const fakeVid: VideoItem = {
              id: `upload-${Date.now()}`,
              title: file.name,
              url: URL.createObjectURL(file),
              duration: 0,
              size_mb: Math.round(file.size / 1024 / 1024),
              resolution: '—',
              status: 'ready',
              progress: 100,
              created_at: new Date().toISOString(),
              source: 'upload',
            }
            setCurrentVideo(fakeVid)
            setLibrary((prev) => [fakeVid, ...prev])
            setStatus('previewing')
          }
          input.click()
        }}
        onPublishClick={() => setShowPublish(true)}
        editChain={editChain}
        onRemoveStep={handleRemoveStep}
        onApplyChain={handleApplyChain}
        onClearChain={handleClearChain}
        onToolClick={handleToolClick}
        disabled={disabled}
      />

      {/* ── 中栏：预览区 + 对话区 ── */}
      <VideoPreview
        video={currentVideo}
        status={status}
        progress={progress}
        progressPrompt={progressPrompt}
        inputText={inputText}
        setInputText={setInputText}
        onSend={handleSend}
        streaming={streaming}
        messages={messages}
        error={error}
      />

      {/* ── 右栏：视频库 ── */}
      <VideoLibrary
        videos={library}
        onSelect={handleSelectVideo}
        onDelete={handleDeleteVideo}
        selectedId={currentVideo?.id}
      />

      {/* ── Dialogs ── */}
      <CreateDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreateSubmit}
        generating={generating}
      />

      <PublishPanel
        open={showPublish}
        onClose={() => setShowPublish(false)}
        onPublish={handlePublish}
      />
    </div>
  )
}
