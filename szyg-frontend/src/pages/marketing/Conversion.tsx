import { useEffect, useMemo, useState } from 'react'
import { Bot, Funnel, Loader2, MessageCircle, Repeat2, Send, Sparkles, UserCheck } from 'lucide-react'
import {
  acquisitionFunnel,
  acquisitionGenerateReply,
  acquisitionLeads,
  type LeadItem,
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
  inputClass,
  parseFunnelStages,
  platformLabel,
} from './MarketingShared'
import { useI18n } from '@/lib/i18n'

export default function Conversion() {
  const { t } = useI18n()
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [funnel, setFunnel] = useState<Record<string, unknown>>({})
  const [selected, setSelected] = useState<LeadItem | null>(null)
  const [replyInput, setReplyInput] = useState('')
  const [reply, setReply] = useState('')
  const [replyGrade, setReplyGrade] = useState('')
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  const pending = useMemo(() => leads.filter((item) => !['converted', 'invalid'].includes(String(item.status || '').toLowerCase())).length, [leads])
  const highIntent = useMemo(() => leads.filter((item) => ['a', 's', '高', 'high'].includes(String(item.grade || '').toLowerCase())).length, [leads])

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [leadData, funnelData] = await Promise.all([
        acquisitionLeads({ limit: 50 }),
        acquisitionFunnel(),
      ])
      setLeads(leadData.leads || [])
      setFunnel(funnelData || {})
      setSelected((leadData.leads || [])[0] || null)
      setReplyInput((leadData.leads || [])[0]?.comment_text || '')
    } catch (e) {
      setError(e instanceof Error ? e.message : t("客户转化数据加载失败"))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const generateReply = async () => {
    const text = replyInput.trim() || selected?.comment_text || selected?.content || ''
    if (!text) {
      setError(t("请输入客户评论或上下文"))
      return
    }
    setGenerating(true)
    setError('')
    try {
      const data = await acquisitionGenerateReply({
        comment_text: text,
        author_name: selected?.user_name || selected?.author_name || '',
        platform: selected?.platform || 'douyin',
      })
      setReply(data.reply)
      setReplyGrade(`${data.grade} · ${data.lead_score}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("回复生成失败"))
    } finally {
      setGenerating(false)
    }
  }

  const confirmDm = () => {
    if (confirm(t("这是私信发送的预览确认入口。请确保话术、账号状态和平台规则已经人工检查。"))) {
      alert(t("v1 保留确认入口。真实私信发送将接入队列和执行观测。"))
    }
  }

  const funnelStages = parseFunnelStages(funnel)

  return (
    <PageShell title={t("客户转化工作台")} subtitle={t("把识别出的线索推进到回复、私信、确认和成交阶段。")} icon={Repeat2}>
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label={t("线索总数")} value={leads.length} icon={UserCheck} />
        <MetricCard label={t("待跟进")} value={pending} icon={MessageCircle} tone="amber" />
        <MetricCard label={t("高意向")} value={highIntent} icon={Sparkles} tone="green" />
        <MetricCard label={t("漏斗阶段")} value={funnelStages.length || '-'} icon={Funnel} tone="blue" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
        <Panel title={t("待跟进线索")} description={t("按最新状态处理线索，优先跟进高意向用户。")}>
          {loading ? (
            <div className="flex h-40 items-center justify-center text-[#64748B]"><Loader2 className="h-6 w-6 animate-spin" /></div>
          ) : leads.length === 0 ? (
            <EmptyState title={t("暂无线索")} description={t("智能截流和机会监听识别到线索后，会进入这里。")} />
          ) : (
            <div className="space-y-3">
              {leads.map((item, index) => (
                <button
                  key={item.id || item.lead_id || index}
                  onClick={() => {
                    setSelected(item)
                    setReplyInput(item.comment_text || item.content || '')
                    setReply('')
                  }}
                  className={`w-full rounded-lg border p-4 text-left transition-colors ${
                    selected === item ? 'border-[#6366F1] bg-[#6366F1]/10' : 'border-[#1E293B] bg-[#0B0F1A] hover:border-[#334155]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-[#F1F5F9]">{item.user_name || item.author_name || t("潜在线索")}</p>
                      <p className="mt-1 text-xs text-[#64748B]">{platformLabel(item.platform)} · {item.grade || t("未评级")}</p>
                    </div>
                    <StatusPill status={item.status || 'pending'} />
                  </div>
                  <p className="mt-3 line-clamp-2 text-sm text-[#CBD5E1]">{item.comment_text || item.content || t("暂无上下文")}</p>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel title={t("回复生成器")} description={t("先生成和预览话术，再由人工确认外发。")}>
          <div className="space-y-4">
            <div>
              <FieldLabel>{t("评论/上下文")}</FieldLabel>
              <textarea value={replyInput} onChange={(e) => setReplyInput(e.target.value)} rows={5} className={inputClass} placeholder={t("粘贴客户评论或私信上下文")} />
            </div>
            <button onClick={generateReply} disabled={generating} className={`${buttonPrimary} w-full`}>
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}

              {t("生成回复")}
            </button>
            {reply && (
              <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                <p className="text-xs text-[#64748B]">{t("AI 建议回复")} {replyGrade && `· ${replyGrade}`}</p>
                <p className="mt-2 text-sm leading-6 text-[#F1F5F9]">{reply}</p>
                <div className="mt-4 flex gap-2">
                  <button onClick={confirmDm} className={buttonSecondary}><Send className="h-4 w-4" />{t("预览私信确认")}</button>
                  <button className={buttonSecondary}>{t("预览跟进入口")}</button>
                </div>
              </div>
            )}
          </div>
        </Panel>
      </div>

      <Panel title={t("转化漏斗")} description={t("用于老板和运营判断线索在哪个阶段流失。")}>
        {funnelStages.length === 0 ? (
          <EmptyState title={t("暂无漏斗数据")} description={t("线索状态更新后，这里会展示从发现到成交的阶段分布。")} />
        ) : (
          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
            {funnelStages.map((item) => (
              <div key={item.stage} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                <p className="text-xs text-[#64748B]">{item.label}</p>
                <p className="mt-2 text-2xl font-semibold text-[#F1F5F9]">{item.count}</p>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </PageShell>
  )
}
