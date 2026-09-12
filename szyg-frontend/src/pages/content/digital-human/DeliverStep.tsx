import { Check, CircleAlert, Loader2, RefreshCw, Send, WandSparkles } from 'lucide-react'
import type { DigitalHumanConfig, DigitalHumanProject, DigitalHumanRender, DigitalHumanProfile } from '@/lib/api'

interface DeliverStepProps {
  project: DigitalHumanProject
  config: DigitalHumanConfig | null
  render: DigitalHumanRender | null
  selectedProfile: DigitalHumanProfile | null | undefined
  totalDuration: number
  canGenerate: boolean
  busyKey: string
  onPatch: (patch: Partial<DigitalHumanProject>) => void
  onStartRender: () => void
  onRetrySegment: (segmentId: string) => void
  onOpenPublish: () => void
}

export default function DeliverStep({
  project,
  config,
  render,
  selectedProfile,
  totalDuration,
  canGenerate,
  busyKey,
  onPatch,
  onStartRender,
  onRetrySegment,
  onOpenPublish,
}: DeliverStepProps) {
  const durationOver = totalDuration > 60
  return (
    <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
      <section>
        <h2 className="text-base font-semibold">成片设置</h2>
        <div className="mt-4 space-y-4">
          <label className="block">
            <span className="text-xs text-[#7F8DA5]">作品名称</span>
            <input
              value={project.name}
              onChange={(event) => onPatch({ name: event.target.value })}
              className="mt-1 h-10 w-full border border-[#2A3548] bg-[#0D1320] px-3 text-sm outline-none"
            />
          </label>
          <label className="block">
            <span className="text-xs text-[#7F8DA5]">视觉风格</span>
            <textarea
              value={project.visual_style}
              onChange={(event) => onPatch({ visual_style: event.target.value })}
              rows={3}
              className="mt-1 w-full border border-[#2A3548] bg-[#0D1320] p-3 text-sm leading-6 outline-none"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label>
              <span className="text-xs text-[#7F8DA5]">视频比例</span>
              <select
                value={project.ratio}
                onChange={(event) => onPatch({ ratio: event.target.value as DigitalHumanProject['ratio'] })}
                className="mt-1 h-10 w-full border border-[#2A3548] bg-[#0D1320] px-2 text-sm"
              >
                {config?.ratios.map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="text-xs text-[#7F8DA5]">清晰度</span>
              <select
                value={project.size}
                onChange={(event) => onPatch({ size: event.target.value as DigitalHumanProject['size'] })}
                className="mt-1 h-10 w-full border border-[#2A3548] bg-[#0D1320] px-2 text-sm"
              >
                <option value="480p">流畅</option>
                <option value="720p">高清</option>
              </select>
            </label>
          </div>
          <div className="border-y border-[#223047] py-4">
            <div className="flex justify-between text-sm">
              <span className="text-[#8D9AAF]">总时长</span>
              <strong className={durationOver ? 'text-[#FF8FA3]' : 'text-white'}>{totalDuration} 秒</strong>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden bg-[#1B2535]">
              <div
                className={`h-full ${durationOver ? 'bg-[#EF6078]' : 'bg-[#6671F0]'}`}
                style={{ width: `${Math.min(100, (totalDuration / 60) * 100)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-[#718098]">系统会自动分段生成并在本机合成为一个视频。</p>
          </div>
          {selectedProfile?.profile_type === 'real' && (
            <p className="flex gap-2 border border-[#65404A] bg-[#27151B] p-3 text-xs leading-5 text-[#F5AAB7]">
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              当前版本暂不能使用真人形象生成，请选择虚拟人物。
            </p>
          )}
          {selectedProfile && !selectedProfile.voice_asset_id && (
            <p className="flex gap-2 border border-[#65543A] bg-[#251E12] p-3 text-xs text-[#EDC67D]">
              <CircleAlert className="h-4 w-4" />
              该形象尚未绑定声音。
            </p>
          )}
          <button
            type="button"
            onClick={onStartRender}
            disabled={!canGenerate || busyKey === 'render' || !config?.configured}
            className="flex h-11 w-full items-center justify-center gap-2 bg-[#5965E8] text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busyKey === 'render' ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
            生成视频
          </button>
        </div>
      </section>
      <section>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">生成进度</h2>
            <p className="mt-1 text-xs text-[#7F8DA5]">每个片段独立生成，失败时只需重试对应片段。</p>
          </div>
          {render?.status === 'succeeded' && (
            <button
              type="button"
              onClick={onOpenPublish}
              className="inline-flex h-9 items-center gap-2 bg-[#20A887] px-4 text-sm"
            >
              <Send className="h-4 w-4" />
              发布成片
            </button>
          )}
        </div>
        {!render ? (
          <div className="flex min-h-[200px] flex-col items-center justify-center border border-dashed border-[#2B3850] bg-[#0B101B]/40 px-6 text-center">
            <WandSparkles className="mb-3 h-7 w-7 text-[#7184A3]" />
            <p className="text-sm font-medium text-[#E7ECF5]">准备生成你的数字人口播</p>
            <p className="mt-1 max-w-sm text-xs leading-5 text-[#7F8DA5]">确认形象、声音、场景和总时长后开始生成。</p>
          </div>
        ) : (
          <RenderProgress render={render} onRetrySegment={onRetrySegment} />
        )}
      </section>
    </div>
  )
}

function RenderProgress({
  render,
  onRetrySegment,
}: {
  render: DigitalHumanRender
  onRetrySegment: (segmentId: string) => void
}) {
  return (
    <div>
      <div className="border border-[#263247] bg-[#0C111D] p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">
            {render.status === 'succeeded' ? '成片已完成' : render.status === 'failed' ? '部分片段需要处理' : '正在生成'}
          </span>
          <span className="text-sm text-[#AAB5C6]">{render.progress}%</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden bg-[#1A2332]">
          <div
            className={`h-full transition-all ${
              render.status === 'failed'
                ? 'bg-[#ED667D]'
                : render.status === 'succeeded'
                ? 'bg-[#2BC6A2]'
                : 'bg-[#6873EE]'
            }`}
            style={{ width: `${render.progress}%` }}
          />
        </div>
      </div>
      <div className="mt-3 space-y-2">
        {render.segments.map((segment) => {
          const isDone = segment.status === 'succeeded'
          const isFailed = segment.status === 'failed'
          const isWorking = segment.status === 'processing' || segment.status === 'queued'
          return (
            <div key={segment.id} className="flex items-center gap-3 border border-[#222D40] bg-[#0B101A] px-4 py-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#1C2638] text-xs">
                {segment.index}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm">片段 {segment.index} · {segment.duration} 秒</p>
                <p className={`mt-0.5 text-xs ${isFailed ? 'text-[#F28A9C]' : 'text-[#78879E]'}`}>
                  {isDone ? '已完成' : isFailed ? (segment.error || '生成失败') : '生成中'}
                </p>
              </div>
              {isWorking ? (
                <Loader2 className="h-4 w-4 animate-spin text-[#7B85FF]" />
              ) : isDone ? (
                <Check className="h-4 w-4 text-[#4DD7B5]" />
              ) : (
                <button
                  type="button"
                  onClick={() => onRetrySegment(segment.id)}
                  className="inline-flex h-8 items-center gap-1 border border-[#704052] px-2 text-xs text-[#F0A0AD]"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  重试
                </button>
              )}
            </div>
          )
        })}
      </div>
      {render.status === 'succeeded' && render.output_url && (
        <video src={render.output_url} controls className="mt-4 max-h-[560px] w-full bg-black" />
      )}
    </div>
  )
}
