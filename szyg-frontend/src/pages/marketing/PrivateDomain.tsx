import { useEffect, useMemo, useState } from 'react'
import {
  Bot,
  CheckCircle2,
  Clock,
  Loader2,
  MessageCircle,
  MousePointerClick,
  RefreshCw,
  Send,
  Sparkles,
  UserCheck,
  Users,
} from 'lucide-react'
import {
  acquisitionGenerateReply,
  openWechatDesktop,
  captureWechatInputClick,
  privateDomainCreateFollowup,
  privateDomainCreateWechatDraft,
  privateDomainOverview,
  privateDomainQueue,
  type LeadItem,
  type PrivateDomainOverview,
} from '@/lib/api'
import {
  EmptyState,
  FieldLabel,
  MetricCard,
  PageShell,
  Panel,
  StatusPill,
  buttonPrimary,
  buttonSecondary,
  formatDateTime,
  inputClass,
  platformLabel,
  scoreTone,
} from './MarketingShared'

function leadId(item?: LeadItem | null): string {
  return String(item?.lead_id || item?.id || '')
}

function leadName(item?: LeadItem | null): string {
  return String(item?.user_name || item?.author_name || '潜在线索')
}

function leadText(item?: LeadItem | null): string {
  return String(item?.comment_text || item?.content || item?.notes || '')
}

function isHighIntent(item?: LeadItem | null): boolean {
  const grade = String(item?.grade || '').toLowerCase()
  const score = Number(item?.lead_score || item?.score || 0)
  return ['a', 's', '高', 'high'].includes(grade) || score >= 70
}

function wechatTone(state?: string): string {
  if (state === 'calibrated') return 'border-[#10B981]/30 bg-[#10B981]/10 text-[#A7F3D0]'
  if (state === 'connected') return 'border-[#38BDF8]/30 bg-[#38BDF8]/10 text-[#BAE6FD]'
  return 'border-[#F59E0B]/30 bg-[#F59E0B]/10 text-[#FCD34D]'
}

export default function PrivateDomain() {
  const [overview, setOverview] = useState<PrivateDomainOverview | null>(null)
  const [items, setItems] = useState<LeadItem[]>([])
  const [selected, setSelected] = useState<LeadItem | null>(null)
  const [reply, setReply] = useState('')
  const [replyGrade, setReplyGrade] = useState('')
  const [nextReminder, setNextReminder] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')

  const selectedText = useMemo(() => leadText(selected), [selected])

  const load = async () => {
    setError('')
    try {
      const [overviewData, queueData] = await Promise.all([
        privateDomainOverview(),
        privateDomainQueue(80),
      ])
      setOverview(overviewData)
      const queue = queueData.items || []
      setItems(queue)
      setSelected((prev) => prev || queue[0] || null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '私域营销数据加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const showToast = (message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 3000)
  }

  const generateReply = async () => {
    const text = selectedText.trim()
    if (!selected || !text) {
      setError('请选择一条有上下文的线索')
      return
    }
    setWorking('reply')
    setError('')
    try {
      const data = await acquisitionGenerateReply({
        comment_text: text,
        author_name: leadName(selected),
        platform: selected.platform || 'douyin',
      })
      setReply(data.reply)
      setReplyGrade(`${data.grade} · ${data.lead_score}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : '回复生成失败')
    } finally {
      setWorking('')
    }
  }

  const openWechat = async () => {
    setWorking('open')
    setError('')
    try {
      await openWechatDesktop()
      showToast('微信已打开到前台')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '打开微信失败')
    } finally {
      setWorking('')
    }
  }

  const captureInput = async () => {
    setWorking('capture')
    setError('')
    try {
      await captureWechatInputClick(30)
      showToast('微信输入区已识别')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '识别输入区失败')
    } finally {
      setWorking('')
    }
  }

  const createDraft = async () => {
    const text = reply.trim()
    if (!selected || !text) {
      setError('请先生成或填写回复话术')
      return
    }
    if (!overview?.wechat.calibrated) {
      setError('请先识别微信输入区')
      return
    }
    if (!window.confirm('将这段话术记录为微信草稿，发送前仍需要你人工确认。')) return
    setWorking('draft')
    setError('')
    try {
      await privateDomainCreateWechatDraft({
        lead_id: leadId(selected),
        customer_name: leadName(selected),
        message: text,
      })
      showToast('已生成微信草稿记录')
    } catch (e) {
      setError(e instanceof Error ? e.message : '写入草稿失败')
    } finally {
      setWorking('')
    }
  }

  const markFollowed = async () => {
    if (!selected) return
    setWorking('follow')
    setError('')
    try {
      await privateDomainCreateFollowup({
        lead_id: leadId(selected),
        customer_name: leadName(selected),
        platform: selected.platform,
        reply_text: reply,
        next_reminder_at: nextReminder,
        notes,
      })
      showToast('已记录跟进')
      setItems((prev) => prev.map((item) => leadId(item) === leadId(selected) ? { ...item, private_status: 'followed', status: 'followed' } : item))
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '记录跟进失败')
    } finally {
      setWorking('')
    }
  }

  const metrics = overview?.metrics || { pending: 0, high_intent: 0, followed_today: 0, overdue: 0 }
  const wechat = overview?.wechat

  return (
    <PageShell title="私域营销" subtitle="AI 销售员工会从线索里判断需求，生成跟进话术，并辅助你在微信里安全承接客户。" icon={MessageCircle}>
      {toast && <div className="fixed right-6 top-20 z-50 rounded-lg border border-[#10B981]/30 bg-[#064E3B] px-4 py-3 text-sm text-[#D1FAE5] shadow-xl">{toast}</div>}
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="待跟进" value={metrics.pending} icon={UserCheck} />
        <MetricCard label="高意向" value={metrics.high_intent} icon={Sparkles} tone="green" />
        <MetricCard label="已跟进" value={metrics.followed_today} icon={CheckCircle2} tone="blue" />
        <MetricCard label="超时提醒" value={metrics.overdue} icon={Clock} tone="amber" />
        <div className={`rounded-lg border p-4 ${wechatTone(wechat?.state)}`}>
          <p className="text-xs opacity-80">当前电脑微信</p>
          <p className="mt-2 text-lg font-semibold">{wechat?.label || '未连接'}</p>
          <p className="mt-3 text-xs opacity-75">只辅助草稿和跟进，发送前仍需确认。</p>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)_390px]">
        <Panel title="待跟进队列" description="来自智能截流和机会监听的潜在线索。">
          {loading ? (
            <div className="flex h-56 items-center justify-center text-[#64748B]"><Loader2 className="h-6 w-6 animate-spin" /></div>
          ) : items.length === 0 ? (
            <EmptyState title="暂无线索" description="智能截流或机会监听识别到客户后，会进入这里。" />
          ) : (
            <div className="space-y-3">
              {items.map((item, index) => {
                const active = leadId(item) === leadId(selected)
                return (
                  <button
                    key={leadId(item) || index}
                    onClick={() => {
                      setSelected(item)
                      setReply('')
                      setReplyGrade('')
                      setNotes('')
                    }}
                    className={`w-full rounded-lg border p-4 text-left transition-colors ${
                      active ? 'border-[#6366F1] bg-[#6366F1]/10' : 'border-[#1E293B] bg-[#0B0F1A] hover:border-[#334155]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-[#F1F5F9]">{leadName(item)}</p>
                        <p className="mt-1 text-xs text-[#64748B]">{platformLabel(item.platform)} · {item.grade || '未评级'}</p>
                      </div>
                      <StatusPill status={String(item.private_status || item.status || 'pending')} />
                    </div>
                    <p className="mt-3 line-clamp-3 text-sm leading-6 text-[#CBD5E1]">{leadText(item) || '暂无客户上下文'}</p>
                  </button>
                )
              })}
            </div>
          )}
        </Panel>

        <Panel title="客户需求判断" description="先判断客户想要什么，再决定是否进入微信跟进。">
          {!selected ? (
            <EmptyState title="请选择线索" description="选择一条线索后查看来源、意向和推荐动作。" />
          ) : (
            <div className="space-y-5">
              <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-lg font-semibold text-[#F8FAFC]">{leadName(selected)}</p>
                    <p className="mt-1 text-sm text-[#64748B]">{platformLabel(selected.platform)} · {selected.source_title || '来源内容待补充'}</p>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs ${scoreTone(Number(selected.lead_score || selected.score || 0))}`}>
                    {isHighIntent(selected) ? '高意向' : '待确认'} · {selected.grade || selected.lead_score || selected.score || '未评分'}
                  </span>
                </div>
                <div className="mt-5 rounded-lg border border-[#334155] bg-[#020617] p-4">
                  <p className="text-xs text-[#64748B]">客户原始表达</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[#E2E8F0]">{selectedText || '暂无上下文'}</p>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                  <p className="text-xs text-[#64748B]">判断</p>
                  <p className="mt-2 text-sm leading-6 text-[#CBD5E1]">{isHighIntent(selected) ? '建议优先进入微信私域承接' : '先确认需求，再决定是否跟进'}</p>
                </div>
                <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                  <p className="text-xs text-[#64748B]">下一步</p>
                  <p className="mt-2 text-sm leading-6 text-[#CBD5E1]">{String(selected.recommended_action || '生成回复并人工确认')}</p>
                </div>
                <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                  <p className="text-xs text-[#64748B]">最近更新</p>
                  <p className="mt-2 text-sm leading-6 text-[#CBD5E1]">{formatDateTime(selected.updated_at || selected.created_at)}</p>
                </div>
              </div>

              <div>
                <FieldLabel>跟进备注</FieldLabel>
                <textarea
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  rows={4}
                  className={inputClass}
                  placeholder="记录客户需求、预算、顾虑或下一步动作"
                />
              </div>
            </div>
          )}
        </Panel>

        <Panel title="微信跟进" description="生成话术、打开微信、写入草稿，发送前由你确认。">
          <div className="space-y-4">
            <div className={`rounded-lg border p-4 ${wechatTone(wechat?.state)}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">当前电脑微信</p>
                  <p className="mt-1 text-xs opacity-75">{wechat?.label || '未连接'}</p>
                </div>
                <MessageCircle className="h-5 w-5" />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button onClick={openWechat} disabled={working === 'open'} className={buttonSecondary}>
                  {working === 'open' ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
                  打开微信
                </button>
                <button onClick={captureInput} disabled={working === 'capture'} className={buttonSecondary}>
                  {working === 'capture' ? <Loader2 className="h-4 w-4 animate-spin" /> : <MousePointerClick className="h-4 w-4" />}
                  识别输入区
                </button>
              </div>
            </div>

            <button onClick={generateReply} disabled={!selected || working === 'reply'} className={`${buttonPrimary} w-full`}>
              {working === 'reply' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
              生成回复
            </button>

            <div>
              <FieldLabel>AI 建议话术 {replyGrade && <span className="text-[#64748B]">· {replyGrade}</span>}</FieldLabel>
              <textarea
                value={reply}
                onChange={(event) => setReply(event.target.value)}
                rows={8}
                className={inputClass}
                placeholder="生成后可以在这里微调，再写入微信草稿"
              />
            </div>

            <div>
              <FieldLabel>下次提醒</FieldLabel>
              <input value={nextReminder} onChange={(event) => setNextReminder(event.target.value)} type="datetime-local" className={inputClass} />
            </div>

            <div className="grid gap-2">
              <button onClick={createDraft} disabled={!reply.trim() || working === 'draft'} className={buttonSecondary}>
                {working === 'draft' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                写入草稿
              </button>
              <button onClick={markFollowed} disabled={!selected || working === 'follow'} className={buttonSecondary}>
                {working === 'follow' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                标记已跟进
              </button>
            </div>
          </div>
        </Panel>
      </div>
    </PageShell>
  )
}
