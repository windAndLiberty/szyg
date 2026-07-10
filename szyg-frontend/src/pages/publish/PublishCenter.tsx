import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Clock3,
  ImagePlus,
  Loader2,
  Music2,
  Play,
  Send,
  ShieldCheck,
  Sparkles,
  Video,
  Workflow,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  createSauNoteTask,
  createSauVideoTask,
  generateImage,
  getErrorMessage,
  type SauCreateResponse,
} from '@/lib/api'
import {
  CONTENT_DRAFT_KEY,
  subscribeImageGeneration,
  type ContentDraft,
} from '@/lib/contentDraftStore'
import { resolveGeneratedAssetUrl } from '@/lib/generatedAssets'

type PublishMode = 'video' | 'note'

const PLATFORMS = [
  { id: 'douyin', label: '抖音', icon: Music2, tone: 'cyan' },
  { id: 'xhs', label: '小红书', icon: BookOpen, tone: 'rose' },
]

const metrics = [
  { label: '今日任务', value: '12', hint: '3 个执行中', color: 'text-[#38BDF8]' },
  { label: '需人工', value: '2', hint: '验证码/登录态', color: 'text-[#F59E0B]' },
  { label: '素材生成', value: '7', hint: '火山引擎可用', color: 'text-[#10B981]' },
  { label: '平均耗时', value: '03:42', hint: '近 20 次', color: 'text-[#22D3EE]' },
]

function splitTags(raw: string): string[] {
  return raw
    .split(/[,，#\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function splitLines(raw: string): string[] {
  return raw
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function appendUniquePath(current: string, nextPath: string): string {
  const next = nextPath.trim()
  if (!next) return current
  const paths = splitLines(current)
  if (paths.includes(next)) return paths.join('\n')
  return [...paths, next].join('\n')
}

function TextArea({
  value,
  onChange,
  rows,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  rows: number
  placeholder?: string
}) {
  return (
    <textarea
      value={value}
      onChange={(event) => onChange(event.target.value)}
      rows={rows}
      placeholder={placeholder}
      className="w-full resize-none rounded-md border border-[#223049] bg-[#080D16] px-3 py-2.5 text-sm text-[#F1F5F9] placeholder:text-[#64748B] focus:border-[#38BDF8]/50 focus:outline-none focus:ring-1 focus:ring-[#38BDF8]/20"
    />
  )
}

function FieldLabel({ children }: { children: string }) {
  return <span className="text-xs font-medium uppercase tracking-[0.08em] text-[#94A3B8]">{children}</span>
}

function StatusPanel({ result, error }: { result: SauCreateResponse | null; error: string }) {
  if (!result && !error) return null

  return (
    <section className="rounded-md border border-[#223049] bg-[#080D16] p-4">
      {error ? (
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-[#EF4444]" />
          <div>
            <div className="text-sm font-medium text-[#F1F5F9]">创建失败</div>
            <div className="mt-1 text-sm text-[#94A3B8]">{error}</div>
          </div>
        </div>
      ) : result ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-[#10B981]" />
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-[#F1F5F9]">ExecutionRun 已创建</span>
                <Badge variant="info">{result.run.status}</Badge>
              </div>
              <div className="mt-1 break-all text-xs text-[#94A3B8]">{result.execution_id}</div>
            </div>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link to="/ai-staff/tasks">任务看板</Link>
          </Button>
        </div>
      ) : null}
    </section>
  )
}

export default function PublishCenter() {
  const [mode, setMode] = useState<PublishMode>('note')
  const [platform, setPlatform] = useState('douyin')
  const [headless, setHeadless] = useState(false)

  const [videoPath, setVideoPath] = useState('')
  const [videoTitle, setVideoTitle] = useState('SZYG 抖音自动发布测试')
  const [videoDesc, setVideoDesc] = useState('由 SZYG Execution Kernel 创建的发布任务')
  const [videoTags, setVideoTags] = useState('szygtest 自动化')

  const [noteImages, setNoteImages] = useState('')
  const [noteTitle, setNoteTitle] = useState('SZYG 图文自动发布测试')
  const [noteText, setNoteText] = useState('这是一条用于验证图文发布链路的测试内容。')
  const [noteTags, setNoteTags] = useState('szygtest 图文测试')
  const [imagePrompt, setImagePrompt] = useState(
    '真实产品营销图：办公桌上的笔记本电脑展示抽象运营看板，社媒发布图标、流程卡片、增长图表，蓝绿色点缀，无可读文字'
  )
  const [generatedPreview, setGeneratedPreview] = useState('')
  const [contentDraft, setContentDraft] = useState<ContentDraft | null>(null)
  const [productionGenerating, setProductionGenerating] = useState(false)

  const [submitting, setSubmitting] = useState(false)
  const [generating, setGenerating] = useState(false)
  const generatingRef = useRef(false)
  const [result, setResult] = useState<SauCreateResponse | null>(null)
  const [error, setError] = useState('')

  const selectedPlatform = useMemo(
    () => PLATFORMS.find((item) => item.id === platform) || PLATFORMS[0],
    [platform]
  )

  const loadContentDraft = useCallback(() => {
    try {
      const raw = sessionStorage.getItem(CONTENT_DRAFT_KEY) || localStorage.getItem(CONTENT_DRAFT_KEY)
      if (!raw) return null
      const draft = JSON.parse(raw) as ContentDraft
      if (!Array.isArray(draft.assets) || draft.assets.length === 0) return null
      setContentDraft(draft)
      setMode('note')
      setNoteTitle((current) => current || draft.title || 'AI生成图文草稿')
      setNoteText((current) => current || draft.note || draft.prompt || '')
      setNoteTags((current) => current || (draft.tags || []).join(' '))
      setGeneratedPreview(resolveGeneratedAssetUrl(draft.assets[0]?.url || '', draft.assets[0]?.path || ''))
      return draft
    } catch {
      sessionStorage.removeItem(CONTENT_DRAFT_KEY)
      localStorage.removeItem(CONTENT_DRAFT_KEY)
      return null
    }
  }, [])

  useEffect(() => {
    loadContentDraft()
    return subscribeImageGeneration((state) => {
      setProductionGenerating(state.loading)
      if (!state.loading && state.results.length > 0) {
        loadContentDraft()
      }
    })
  }, [loadContentDraft])

  function applyContentDraft() {
    if (!contentDraft) return
    setMode('note')
    setNoteTitle(contentDraft.title || 'AI生成图文草稿')
    setNoteText(contentDraft.note || contentDraft.prompt || '')
    setNoteTags((contentDraft.tags || []).join(' '))
    setNoteImages((current) =>
      contentDraft.assets.reduce((next, asset) => appendUniquePath(next, asset.path || asset.url), current),
    )
    setGeneratedPreview(resolveGeneratedAssetUrl(contentDraft.assets[0]?.url || '', contentDraft.assets[0]?.path || ''))
  }

  async function handleGenerateImage() {
    if (generatingRef.current || !imagePrompt.trim()) return
    generatingRef.current = true
    setGenerating(true)
    setError('')
    setMode('note')
    try {
      const data = await generateImage(imagePrompt, '1920x1920')
      const path = (data.paths?.[0] || data.images[0] || '').trim()
      if (!path) throw new Error('图片生成完成，但没有返回素材路径')
      setNoteImages((current) => appendUniquePath(current, path))
      setGeneratedPreview(resolveGeneratedAssetUrl(data.images[0] || '', path))
    } catch (err) {
      setError(getErrorMessage(err, '图片生成失败'))
    } finally {
      generatingRef.current = false
      setGenerating(false)
    }
  }

  async function handleSubmit() {
    setSubmitting(true)
    setError('')
    setResult(null)
    try {
      const payload =
        mode === 'video'
          ? await createSauVideoTask({
              platform,
              file_path: videoPath.trim(),
              title: videoTitle.trim(),
              desc: videoDesc.trim(),
              tags: splitTags(videoTags),
              headless,
            })
          : await createSauNoteTask({
              platform,
              image_paths: splitLines(noteImages),
              title: noteTitle.trim(),
              note: noteText.trim(),
              tags: splitTags(noteTags),
              headless,
            })
      setResult(payload)
    } catch (err) {
      setError(getErrorMessage(err, '发布任务创建失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const Icon = selectedPlatform.icon
  const canSubmit =
    mode === 'video'
      ? Boolean(videoPath.trim() && videoTitle.trim())
      : Boolean(splitLines(noteImages).length > 0 && noteTitle.trim())

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#080D16] px-4 py-5 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1480px] flex-col gap-5">
        <header className="flex flex-col gap-4 rounded-md border border-[#1C2940] bg-[#0D1422] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md border border-[#1E3A5F] bg-[#0B1A2D]">
              <Send className="h-5 w-5 text-[#38BDF8]" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-normal text-[#F8FAFC]">发布中心</h1>
                <Badge variant="info">Execution Kernel</Badge>
              </div>
              <p className="mt-1 text-sm text-[#94A3B8]">
                内容、素材生成、平台发布和执行观测在一个工作台完成。
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/publish/workspace">执行观测</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/ai-staff/tasks">任务看板</Link>
            </Button>
          </div>
        </header>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-md border border-[#1C2940] bg-[#0D1422] px-4 py-3">
              <div className="text-xs text-[#64748B]">{metric.label}</div>
              <div className="mt-1 flex items-end gap-3">
                <span className={`text-2xl font-semibold ${metric.color}`}>{metric.value}</span>
                <span className="pb-1 text-xs text-[#94A3B8]">{metric.hint}</span>
              </div>
            </div>
          ))}
        </section>

        <section className="rounded-md border border-[#1C2940] bg-[#0D1422]">
          <div className="grid gap-4 p-4 lg:grid-cols-[1fr_auto] lg:items-end">
            <label className="grid gap-2">
              <FieldLabel>AI 图片生成</FieldLabel>
              <Input value={imagePrompt} onChange={(event) => setImagePrompt(event.target.value)} />
            </label>
            <Button
              type="button"
              onClick={handleGenerateImage}
              disabled={generating || !imagePrompt.trim()}
              className="h-10"
            >
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              生成图片
            </Button>
          </div>
          <div className="border-t border-[#1C2940] px-4 py-2 text-xs text-[#64748B]">
            生成后自动切换到图文任务，并写入图片文件路径。此入口始终首屏可见。
          </div>
        </section>

        {(contentDraft || productionGenerating) && (
          <section className="rounded-md border border-[#1E3A5F] bg-[#0B1A2D] p-4">
            <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-[#1E3A5F] bg-[#080D16]">
                  {productionGenerating ? (
                    <Loader2 className="h-5 w-5 animate-spin text-[#38BDF8]" />
                  ) : (
                    <ImagePlus className="h-5 w-5 text-[#38BDF8]" />
                  )}
                </div>
                <div>
                  <div className="text-sm font-medium text-[#F1F5F9]">
                    {productionGenerating ? '内容生产正在生成' : '检测到内容生产草稿'}
                  </div>
                  <div className="mt-1 text-xs leading-5 text-[#94A3B8]">
                    {productionGenerating
                      ? '可以停留在发布中心，生成完成后草稿会自动出现在这里。'
                      : `${contentDraft?.assets.length || 0} 张素材 · ${contentDraft?.prompt || contentDraft?.title || ''}`}
                  </div>
                </div>
              </div>
              <Button type="button" onClick={applyContentDraft} disabled={!contentDraft || productionGenerating}>
                <Send className="h-4 w-4" />
                加入发布内容
              </Button>
            </div>
          </section>
        )}

        <section className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)] 2xl:grid-cols-[300px_minmax(0,1fr)_340px]">
          <aside className="rounded-md border border-[#1C2940] bg-[#0D1422]">
            <div className="border-b border-[#1C2940] px-4 py-4">
              <div className="flex items-center gap-2 text-sm font-medium text-[#F1F5F9]">
                <Workflow className="h-4 w-4 text-[#38BDF8]" />
                任务配置
              </div>
              <div className="mt-1 text-xs text-[#64748B]">选择内容形态、平台和执行方式。</div>
            </div>

            <div className="grid gap-5 p-4">
              <div className="grid gap-2">
                <FieldLabel>内容类型</FieldLabel>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    type="button"
                    variant={mode === 'note' ? 'default' : 'outline'}
                    className="justify-start"
                    onClick={() => setMode('note')}
                  >
                    <ImagePlus className="h-4 w-4" />
                    图文
                  </Button>
                  <Button
                    type="button"
                    variant={mode === 'video' ? 'default' : 'outline'}
                    className="justify-start"
                    onClick={() => setMode('video')}
                  >
                    <Video className="h-4 w-4" />
                    视频
                  </Button>
                </div>
              </div>

              <div className="grid gap-2">
                <FieldLabel>平台</FieldLabel>
                <div className="grid gap-2">
                  {PLATFORMS.map((item) => {
                    const PlatformIcon = item.icon
                    return (
                      <Button
                        key={item.id}
                        type="button"
                        variant={platform === item.id ? 'secondary' : 'outline'}
                        className="justify-start"
                        onClick={() => setPlatform(item.id)}
                      >
                        <PlatformIcon className="h-4 w-4" />
                        {item.label}
                      </Button>
                    )
                  })}
                </div>
              </div>

              <div className="grid gap-2">
                <FieldLabel>执行方式</FieldLabel>
                <label className="flex items-center justify-between gap-3 rounded-md border border-[#223049] bg-[#080D16] px-3 py-3">
                  <span>
                    <span className="block text-sm text-[#F1F5F9]">{headless ? '后台执行' : '可视化浏览器'}</span>
                    <span className="text-xs text-[#64748B]">{headless ? '适合稳定链路' : '适合登录/验收/人工接管'}</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={headless}
                    onChange={(event) => setHeadless(event.target.checked)}
                    className="h-4 w-4 accent-[#38BDF8]"
                  />
                </label>
              </div>

              <div className="rounded-md border border-[#24324B] bg-[#080D16] p-3">
                <div className="flex items-center gap-2 text-sm font-medium text-[#F1F5F9]">
                  <ShieldCheck className="h-4 w-4 text-[#10B981]" />
                  风控策略
                </div>
                <p className="mt-2 text-xs leading-5 text-[#94A3B8]">
                  登录失效、验证码、账号异常、未知弹窗会进入需人工状态，不继续盲点发布。
                </p>
              </div>
            </div>
          </aside>

          <main className="rounded-md border border-[#1C2940] bg-[#0D1422]">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1C2940] px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md border border-[#1E3A5F] bg-[#0B1A2D]">
                  <Icon className="h-5 w-5 text-[#38BDF8]" />
                </div>
                <div>
                  <div className="text-sm font-medium text-[#F1F5F9]">
                    {selectedPlatform.label} · {mode === 'video' ? '视频发布' : '图文发布'}
                  </div>
                  <div className="mt-1 text-xs text-[#64748B]">提交后立即创建可追踪的 ExecutionRun。</div>
                </div>
              </div>
              <Badge variant={headless ? 'muted' : 'warning'}>{headless ? 'headless' : 'headed'}</Badge>
            </div>

            <div className="grid gap-5 p-5">
              {mode === 'video' ? (
                <>
                  <label className="grid gap-2">
                    <FieldLabel>视频文件路径</FieldLabel>
                    <Input
                      value={videoPath}
                      onChange={(event) => setVideoPath(event.target.value)}
                      placeholder="D:\szyg\data\materials\demo.mp4"
                    />
                  </label>
                  <label className="grid gap-2">
                    <FieldLabel>标题</FieldLabel>
                    <Input value={videoTitle} onChange={(event) => setVideoTitle(event.target.value)} />
                  </label>
                  <label className="grid gap-2">
                    <FieldLabel>描述</FieldLabel>
                    <TextArea value={videoDesc} onChange={setVideoDesc} rows={5} />
                  </label>
                  <label className="grid gap-2">
                    <FieldLabel>标签</FieldLabel>
                    <Input value={videoTags} onChange={(event) => setVideoTags(event.target.value)} />
                  </label>
                </>
              ) : (
                <>
                  <label className="grid gap-2">
                    <FieldLabel>标题</FieldLabel>
                    <Input value={noteTitle} onChange={(event) => setNoteTitle(event.target.value)} />
                  </label>
                  <label className="grid gap-2">
                    <FieldLabel>正文</FieldLabel>
                    <TextArea value={noteText} onChange={setNoteText} rows={6} />
                  </label>
                  <label className="grid gap-2">
                    <FieldLabel>图片文件路径</FieldLabel>
                    <TextArea
                      value={noteImages}
                      onChange={setNoteImages}
                      rows={5}
                      placeholder="D:\szyg\data\volcengine_output\image.jpg"
                    />
                  </label>
                  <label className="grid gap-2">
                    <FieldLabel>标签</FieldLabel>
                    <Input value={noteTags} onChange={(event) => setNoteTags(event.target.value)} />
                  </label>
                </>
              )}

              <div className="rounded-md border border-[#223049] bg-[#080D16] p-4">
                <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-center">
                  <div className="flex items-start gap-3">
                    <Clock3 className="mt-0.5 h-4 w-4 text-[#38BDF8]" />
                    <div>
                      <div className="text-sm font-medium text-[#F1F5F9]">执行闭环</div>
                      <div className="mt-1 text-xs leading-5 text-[#94A3B8]">
                        预检、上传、填写、发布、校验都会记录 Step 和 AuditEvent。
                      </div>
                    </div>
                  </div>
                  <Button type="button" onClick={handleSubmit} disabled={submitting || !canSubmit}>
                    {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    创建发布任务
                  </Button>
                </div>
              </div>

              <StatusPanel result={result} error={error} />
            </div>
          </main>

          <aside className="rounded-md border border-[#1C2940] bg-[#0D1422]">
            <div className="border-b border-[#1C2940] px-4 py-4">
              <div className="flex items-center gap-2 text-sm font-medium text-[#F1F5F9]">
                <Sparkles className="h-4 w-4 text-[#10B981]" />
                AI 素材生成
              </div>
              <div className="mt-1 text-xs text-[#64748B]">常驻入口，生成后自动写入图文图片路径。</div>
            </div>

            <div className="grid gap-4 p-4">
              <label className="grid gap-2">
                <FieldLabel>图片提示词</FieldLabel>
                <TextArea value={imagePrompt} onChange={setImagePrompt} rows={6} />
              </label>

              <Button type="button" onClick={handleGenerateImage} disabled={generating || !imagePrompt.trim()}>
                {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                生成图片
              </Button>

              <div className="overflow-hidden rounded-md border border-[#223049] bg-[#080D16]">
                {generatedPreview ? (
                  <img src={generatedPreview} alt="generated publish asset" className="h-44 w-full object-cover" />
                ) : (
                  <div className="flex h-44 flex-col items-center justify-center gap-2 text-[#64748B]">
                    <ImagePlus className="h-7 w-7" />
                    <span className="text-sm">等待生成预览</span>
                  </div>
                )}
              </div>

              <div className="rounded-md border border-[#223049] bg-[#080D16] p-3">
                <div className="flex items-center gap-2 text-sm font-medium text-[#F1F5F9]">
                  <Play className="h-4 w-4 text-[#38BDF8]" />
                  最近动作
                </div>
                <div className="mt-3 grid gap-2 text-xs text-[#94A3B8]">
                  <div className="flex justify-between gap-2">
                    <span>生成素材</span>
                    <span className={generatedPreview ? 'text-[#10B981]' : 'text-[#64748B]'}>
                      {generatedPreview ? 'ready' : 'waiting'}
                    </span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span>图文路径</span>
                    <span className={noteImages.trim() ? 'text-[#10B981]' : 'text-[#64748B]'}>
                      {splitLines(noteImages).length} 张
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </aside>
        </section>
      </div>
    </div>
  )
}
