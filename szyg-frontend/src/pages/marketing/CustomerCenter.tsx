import { useEffect, useMemo, useState } from 'react'
import { ClipboardCheck, Copy, Loader2, MessageCircle, Search, Sparkles, UserRound, Users } from 'lucide-react'
import {
  acquisitionCustomers,
  acquisitionGenerateReply,
  acquisitionLeads,
  acquisitionMessages,
  privateDomainCreateFollowup,
  privateDomainCreateWechatDraft,
  type CustomerItem,
  type LeadItem,
  type MessageItem,
} from '@/lib/api'
import { EmptyState, MetricCard, PageShell, Panel, StatusPill, buttonPrimary, buttonSecondary, formatDateTime, inputClass, platformLabel } from './MarketingShared'

const stages = [
  ['all', '全部'], ['new', '新发现'], ['contact', '待联系'], ['communicating', '沟通中'],
  ['followup', '待跟进'], ['converted', '已成交'], ['closed', '已结束'],
] as const

export default function CustomerCenter() {
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [customers, setCustomers] = useState<CustomerItem[]>([])
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [selected, setSelected] = useState<LeadItem | CustomerItem | null>(null)
  const [stage, setStage] = useState(() => new URLSearchParams(window.location.search).get('stage') || 'all')
  const [search, setSearch] = useState('')
  const [reply, setReply] = useState('')
  const [working, setWorking] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    try {
      const [leadData, customerData] = await Promise.all([acquisitionLeads({ limit: 100 }), acquisitionCustomers(search, 100)])
      setLeads(leadData.leads || []); setCustomers(customerData.customers || [])
      setSelected((current) => current || leadData.leads?.[0] || customerData.customers?.[0] || null)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '客户数据加载失败') }
  }
  useEffect(() => { load() }, [])
  useEffect(() => {
    const id = selected && 'id' in selected ? selected.id : undefined
    if (!id) { setMessages([]); return }
    acquisitionMessages(String(id)).then((data) => setMessages(data.messages || [])).catch(() => setMessages([]))
  }, [selected])

  const unified = useMemo(() => {
    const rows: Array<LeadItem | CustomerItem> = [...leads, ...customers]
    const seen = new Set<string>()
    return rows.filter((item) => {
      const key = String(item.id || ('lead_id' in item ? item.lead_id : '') || `${'author_name' in item ? item.author_name : item.name}-${item.platform}`)
      if (seen.has(key)) return false
      seen.add(key)
      const status = String(item.status || 'new').toLowerCase()
      const name = String(('name' in item ? item.name : item.author_name) || ('user_name' in item ? item.user_name : '') || '')
      const matchesSearch = !search || name.toLowerCase().includes(search.toLowerCase())
      const isHigh = 'grade' in item && ['a', 's', 'high', '高'].includes(String(item.grade || '').toLowerCase())
      const matchesStage = stage === 'all' || (stage === 'high' ? isHigh : stage === 'contact' ? ['new', 'pending'].includes(status) : stage === 'followup' ? ['contacted', 'replied', 'qualified'].includes(status) : status === stage)
      return matchesSearch && matchesStage
    })
  }, [leads, customers, search, stage])

  const high = leads.filter((item) => ['a', 's', 'high', '高'].includes(String(item.grade || '').toLowerCase())).length
  const displayName = selected ? String(('name' in selected ? selected.name : selected.author_name) || ('user_name' in selected ? selected.user_name : '') || '未命名客户') : ''
  const sourceText = selected && 'comment_text' in selected ? String(selected.comment_text || selected.content || '') : String(selected && 'lastMessage' in selected ? selected.lastMessage || '' : '')

  const generateReply = async () => {
    if (!selected) return
    setWorking(true); setError(''); setNotice('')
    try {
      const result = await acquisitionGenerateReply({ comment_text: sourceText || `请联系客户${displayName}并确认需求`, author_name: displayName, platform: selected.platform })
      setReply(result.reply)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '回复建议生成失败') }
    finally { setWorking(false) }
  }

  const saveDraft = async () => {
    if (!selected || !reply.trim()) return
    setWorking(true); setError('')
    try {
      const leadId = 'lead_id' in selected && selected.lead_id ? String(selected.lead_id) : undefined
      const customerId = 'id' in selected && selected.id ? String(selected.id) : undefined
      const result = await privateDomainCreateWechatDraft({ lead_id: leadId, customer_id: customerId, customer_name: displayName, message: reply.trim(), source: 'customer_center' })
      setNotice(result.wechat?.connected ? '已创建微信发送草稿，请在发送前确认。' : '当前未连接微信，已保存草稿，可复制后人工发送。')
    } catch (cause) { setError(cause instanceof Error ? cause.message : '保存草稿失败') }
    finally { setWorking(false) }
  }

  const recordFollowup = async () => {
    if (!selected) return
    setWorking(true); setError('')
    try {
      await privateDomainCreateFollowup({ lead_id: 'lead_id' in selected && selected.lead_id ? String(selected.lead_id) : undefined, customer_id: 'id' in selected && selected.id ? String(selected.id) : undefined, customer_name: displayName, platform: selected.platform, action: 'followup', reply_text: reply })
      setNotice('已记录本次跟进，客户会继续保留在统一客户中心。')
    } catch (cause) { setError(cause instanceof Error ? cause.message : '记录跟进失败') }
    finally { setWorking(false) }
  }

  return <PageShell title="客户中心" subtitle="从发现、联系到成交，在一个页面持续推进同一位客户。" icon={Users}>
    {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
    {notice && <div className="rounded-lg border border-[#10B981]/30 bg-[#10B981]/10 px-4 py-3 text-sm text-[#A7F3D0]">{notice}</div>}
    <div className="grid gap-4 md:grid-cols-3">
      <MetricCard label="客户与线索" value={unified.length} icon={Users} />
      <MetricCard label="高意向客户" value={high} icon={UserRound} tone="green" />
      <MetricCard label="需要继续跟进" value={unified.filter((item) => !['converted', 'closed', 'done', 'invalid'].includes(String(item.status || '').toLowerCase())).length} icon={MessageCircle} tone="amber" />
    </div>
    <div className="flex flex-wrap gap-2">{stages.map(([value, label]) => <button key={value} onClick={() => setStage(value)} className={`rounded-full border px-3 py-1.5 text-xs ${stage === value ? 'border-[#6366F1] bg-[#6366F1]/15 text-[#C7D2FE]' : 'border-[#334155] text-[#94A3B8]'}`}>{label}</button>)}</div>
    <div className="grid gap-5 xl:grid-cols-[1fr_430px]">
      <Panel title="客户列表" description="线索和已沉淀客户统一展示，不再分散在多个页面。" action={<div className="flex gap-2"><input value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputClass} h-9 w-48`} placeholder="搜索客户" /><button onClick={load} className={buttonSecondary}><Search className="h-4 w-4" /></button></div>}>
        {unified.length === 0 ? <EmptyState title="当前没有匹配客户" description="前往客户机会描述目标客户，AI发现的线索会进入这里。" /> : <div className="space-y-2">{unified.map((item, index) => { const name = String(('name' in item ? item.name : item.author_name) || ('user_name' in item ? item.user_name : '') || '未命名客户'); return <button key={String(item.id || ('lead_id' in item ? item.lead_id : '') || index)} onClick={() => { setSelected(item); setReply(''); setNotice('') }} className={`flex w-full items-center gap-3 rounded-lg border p-4 text-left ${selected === item ? 'border-[#6366F1] bg-[#6366F1]/8' : 'border-[#1E293B] bg-[#0B0F1A]'}`}><div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#6366F1]/12 text-[#A5B4FC]"><UserRound className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-[#F1F5F9]">{name}</p><p className="mt-1 truncate text-xs text-[#64748B]">{platformLabel(item.platform)} · {String(('comment_text' in item ? item.comment_text : item.lastMessage) || '等待进一步了解需求')}</p></div><StatusPill status={item.status || 'new'} /></button> })}</div>}
      </Panel>
      <Panel title="客户详情与下一步" description="AI建议只作为草稿，真实发送取决于已连接的渠道能力。">
        {!selected ? <EmptyState title="请选择客户" description="选择后查看来源、沟通记录并生成跟进建议。" /> : <div className="space-y-4">
          <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4"><p className="font-medium text-[#F1F5F9]">{displayName}</p><p className="mt-1 text-xs text-[#64748B]">{platformLabel(selected.platform)} · 最近状态 {String(selected.status || '新发现')}</p>{sourceText && <p className="mt-3 text-sm leading-6 text-[#CBD5E1]">{sourceText}</p>}</div>
          {messages.length > 0 && <div className="max-h-44 space-y-2 overflow-auto">{messages.slice(-5).map((item, index) => <div key={item.id || index} className="rounded-lg bg-[#0B0F1A] p-3"><p className="text-xs text-[#64748B]">{item.sender || '记录'} · {item.time || formatDateTime(item.created_at)}</p><p className="mt-1 text-sm text-[#CBD5E1]">{item.text}</p></div>)}</div>}
          <button onClick={generateReply} disabled={working} className={`${buttonPrimary} w-full`}>{working ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}生成跟进建议</button>
          {reply && <><textarea value={reply} onChange={(e) => setReply(e.target.value)} className={`${inputClass} min-h-28 resize-none`} /><div className="grid grid-cols-3 gap-2"><button onClick={() => navigator.clipboard.writeText(reply).then(() => setNotice('已复制，可在暂未连接的渠道中人工发送。'))} className={buttonSecondary}><Copy className="h-4 w-4" />复制</button><button onClick={saveDraft} disabled={working} className={buttonSecondary}><MessageCircle className="h-4 w-4" />保存草稿</button><button onClick={recordFollowup} disabled={working} className={buttonSecondary}><ClipboardCheck className="h-4 w-4" />记录跟进</button></div></>}
        </div>}
      </Panel>
    </div>
  </PageShell>
}
