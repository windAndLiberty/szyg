import { motion } from 'framer-motion'
import {
  Activity,
  ArrowDownRight,
  Clock3,
  Coins,
  CreditCard,
  Image as ImageIcon,
  MessageSquareText,
  Mic2,
  Search,
  Sparkles,
  Video,
} from 'lucide-react'
import { fetchCloudBilling, type CloudBilling } from '@/lib/api'
import { useAsync } from '@/lib/hooks'

const capabilityMeta: Record<string, { label: string; icon: typeof Sparkles; color: string }> = {
  'text.fast': { label: '文字处理', icon: MessageSquareText, color: '#818CF8' },
  'text.reasoning': { label: '深度分析', icon: Sparkles, color: '#A78BFA' },
  'text.vision': { label: '视觉理解', icon: Search, color: '#38BDF8' },
  'image.standard': { label: '图片生成', icon: ImageIcon, color: '#F472B6' },
  'video.standard': { label: '视频生成', icon: Video, color: '#FB923C' },
  'speech.tts': { label: '语音合成', icon: Mic2, color: '#34D399' },
  'embedding.standard': { label: '知识检索', icon: Search, color: '#22D3EE' },
}

function formatCredits(value: number) {
  const digits = Math.abs(value) < 1 ? 4 : 2
  return Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function formatTime(value: string) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function LoadingState() {
  return (
    <div className="space-y-5 animate-pulse">
      <div className="h-5 w-64 rounded bg-[#1E293B]" />
      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((item) => <div key={item} className="h-32 rounded-lg bg-[#111827] border border-[#1E293B]" />)}
      </div>
      <div className="h-72 rounded-lg bg-[#111827] border border-[#1E293B]" />
    </div>
  )
}

export default function Billing() {
  const { data, loading, error } = useAsync<CloudBilling>(fetchCloudBilling)

  if (loading) return <LoadingState />

  if (error || !data) {
    return (
      <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-5 py-4 text-sm text-[#FCA5A5]">
        {error || '费用信息暂时无法加载'}
      </div>
    )
  }

  const maxBreakdown = Math.max(...data.breakdown.map((item) => item.credits), 0.000001)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-6"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="text-sm text-[#94A3B8]">清楚了解 Credits 余额、充值记录与智能服务消耗。</p>
        <p className="text-xs text-[#64748B]">更新于 {formatTime(data.as_of)}</p>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="relative overflow-hidden rounded-lg border border-[#6366F1]/35 bg-[#111827] p-5">
          <div className="absolute inset-y-0 left-0 w-1 bg-[#6366F1]" />
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-[#94A3B8]">可用 Credits</p>
              <p className={`mt-3 text-3xl font-semibold ${data.balance_credits < 0 ? 'text-[#FCA5A5]' : 'text-[#F1F5F9]'}`}>
                {formatCredits(data.balance_credits)}
              </p>
            </div>
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-[#6366F1]/15 text-[#A5B4FC]">
              <Coins className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-4 text-xs text-[#64748B]">由管理员统一开通与调整</p>
        </div>

        <div className="rounded-lg border border-[#1E293B] bg-[#111827] p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-[#94A3B8]">本日消耗</p>
              <p className="mt-3 text-3xl font-semibold text-[#F1F5F9]">{formatCredits(data.today_credits)}</p>
            </div>
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-[#F59E0B]/12 text-[#FBBF24]">
              <Activity className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-4 text-xs text-[#64748B]">仅统计成功完成的智能任务</p>
        </div>

        <div className="rounded-lg border border-[#1E293B] bg-[#111827] p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-[#94A3B8]">近 30 日消耗</p>
              <p className="mt-3 text-3xl font-semibold text-[#F1F5F9]">{formatCredits(data.thirty_day_credits)}</p>
            </div>
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-[#10B981]/12 text-[#6EE7B7]">
              <Clock3 className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-4 text-xs text-[#64748B]">累计消耗 {formatCredits(data.spent_credits)} Credits</p>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
        <div className="rounded-lg border border-[#1E293B] bg-[#111827] p-5">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-[#F1F5F9]">用量构成</h2>
              <p className="mt-1 text-xs text-[#64748B]">最近 30 日各类智能任务的 Credits 消耗</p>
            </div>
            <span className="text-xs text-[#64748B]">共 {data.breakdown.reduce((sum, item) => sum + item.requests, 0)} 次</span>
          </div>

          {data.breakdown.length === 0 ? (
            <div className="grid min-h-48 place-items-center text-sm text-[#64748B]">暂无消耗记录</div>
          ) : (
            <div className="space-y-5">
              {data.breakdown.map((item) => {
                const meta = capabilityMeta[item.capability] || { label: '智能任务', icon: Sparkles, color: '#94A3B8' }
                const Icon = meta.icon
                return (
                  <div key={item.capability}>
                    <div className="mb-2 flex items-center justify-between gap-4">
                      <div className="flex min-w-0 items-center gap-2.5">
                        <Icon className="h-4 w-4 shrink-0" style={{ color: meta.color }} />
                        <span className="text-sm text-[#CBD5E1]">{meta.label}</span>
                        <span className="text-xs text-[#64748B]">{item.requests} 次</span>
                      </div>
                      <span className="text-sm font-medium tabular-nums text-[#E2E8F0]">{formatCredits(item.credits)}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-[#1A2235]">
                      <div
                        className="h-full rounded-full transition-[width] duration-500"
                        style={{ width: `${Math.max(3, item.credits / maxBreakdown * 100)}%`, backgroundColor: meta.color }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-[#1E293B] bg-[#111827] p-5">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-[#F1F5F9]">充值记录</h2>
              <p className="mt-1 text-xs text-[#64748B]">累计获得 {formatCredits(data.credited_credits)} Credits</p>
            </div>
            <CreditCard className="h-5 w-5 text-[#64748B]" />
          </div>

          {data.recharges.length === 0 ? (
            <div className="grid min-h-48 place-items-center text-center">
              <div>
                <Coins className="mx-auto h-6 w-6 text-[#475569]" />
                <p className="mt-3 text-sm text-[#94A3B8]">暂无充值记录</p>
                <p className="mt-1 text-xs text-[#64748B]">内测额度由管理员统一开通</p>
              </div>
            </div>
          ) : (
            <div className="divide-y divide-[#1E293B]">
              {data.recharges.slice(0, 8).map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-[#CBD5E1]">{item.note || (item.kind === 'recharge' ? '管理员充值' : '额度调整')}</p>
                    <p className="mt-1 text-xs text-[#64748B]">{formatTime(item.created_at)}</p>
                  </div>
                  <div className="text-right">
                    <p className={`text-sm font-medium tabular-nums ${item.credits >= 0 ? 'text-[#6EE7B7]' : 'text-[#FCA5A5]'}`}>
                      {item.credits >= 0 ? '+' : ''}{formatCredits(item.credits)}
                    </p>
                    {item.payment_amount_cny > 0 && <p className="mt-1 text-xs text-[#64748B]">¥{item.payment_amount_cny.toFixed(2)}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-[#1E293B] bg-[#111827]">
        <div className="flex items-center justify-between gap-3 border-b border-[#1E293B] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-[#F1F5F9]">最近消耗</h2>
            <p className="mt-1 text-xs text-[#64748B]">失败或取消的任务不会扣除 Credits</p>
          </div>
          <ArrowDownRight className="h-5 w-5 text-[#64748B]" />
        </div>
        {data.recent_usage.length === 0 ? (
          <div className="grid min-h-32 place-items-center text-sm text-[#64748B]">暂无消耗记录</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left">
              <thead className="bg-[#0D1321] text-xs text-[#64748B]">
                <tr>
                  <th className="px-5 py-3 font-medium">服务类型</th>
                  <th className="px-5 py-3 font-medium">时间</th>
                  <th className="px-5 py-3 text-right font-medium">消耗 Credits</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E293B]">
                {data.recent_usage.slice(0, 10).map((item) => {
                  const meta = capabilityMeta[item.capability] || { label: '智能任务', icon: Sparkles, color: '#94A3B8' }
                  const Icon = meta.icon
                  return (
                    <tr key={item.id} className="transition-colors hover:bg-white/[0.02]">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2.5 text-sm text-[#CBD5E1]">
                          <Icon className="h-4 w-4" style={{ color: meta.color }} />
                          {meta.label}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-sm text-[#64748B]">{formatTime(item.created_at)}</td>
                      <td className="px-5 py-3.5 text-right text-sm font-medium tabular-nums text-[#E2E8F0]">-{formatCredits(item.credits)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </motion.div>
  )
}
