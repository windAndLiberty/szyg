import { useEffect, useState } from 'react'
import { History, Loader2, MessageCircle, Search, Tags, UserRound, Users } from 'lucide-react'
import {
  acquisitionCustomers,
  acquisitionMessages,
  type CustomerItem,
  type MessageItem,
} from '@/lib/api'
import {
  EmptyState,
  FieldLabel,
  MetricCard,
  PageShell,
  Panel,
  StatusPill,
  buttonSecondary,
  formatDateTime,
  inputClass,
  platformLabel,
} from './MarketingShared'

export default function Customers() {
  const [customers, setCustomers] = useState<CustomerItem[]>([])
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [selected, setSelected] = useState<CustomerItem | null>(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [error, setError] = useState('')

  const loadCustomers = async (query = search) => {
    setLoading(true)
    setError('')
    try {
      const data = await acquisitionCustomers(query, 80)
      const items = data.customers || []
      setCustomers(items)
      setSelected((prev) => prev || items[0] || null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '客户资产加载失败')
    } finally {
      setLoading(false)
    }
  }

  const loadMessages = async (customer?: CustomerItem | null) => {
    if (!customer?.id) {
      setMessages([])
      return
    }
    setLoadingMessages(true)
    try {
      const data = await acquisitionMessages(customer.id)
      setMessages(data.messages || [])
    } catch {
      setMessages([])
    } finally {
      setLoadingMessages(false)
    }
  }

  useEffect(() => {
    loadCustomers('')
  }, [])

  useEffect(() => {
    loadMessages(selected)
  }, [selected])

  return (
    <PageShell title="客户资产池" subtitle="把线索沉淀为客户资产，保留来源、互动记录和下一步动作。" icon={Users}>
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="客户总数" value={customers.length} icon={Users} />
        <MetricCard label="高意向客户" value={customers.filter((item) => ['a', 's', '高', 'high'].includes(String(item.grade || '').toLowerCase())).length} icon={UserRound} tone="green" />
        <MetricCard label="待跟进" value={customers.filter((item) => !['done', 'converted', 'invalid'].includes(String(item.status || '').toLowerCase())).length} icon={MessageCircle} tone="amber" />
        <MetricCard label="标签数量" value={new Set(customers.flatMap((item) => item.tags || [])).size} icon={Tags} tone="blue" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
        <Panel
          title="客户列表"
          description="按客户昵称、最近消息或标签检索客户资产。"
          action={
            <div className="flex items-center gap-2">
              <input value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputClass} h-9 w-52`} placeholder="搜索客户" />
              <button onClick={() => loadCustomers(search)} className={buttonSecondary}><Search className="h-4 w-4" />搜索</button>
            </div>
          }
        >
          {loading ? (
            <div className="flex h-40 items-center justify-center text-[#64748B]"><Loader2 className="h-6 w-6 animate-spin" /></div>
          ) : customers.length === 0 ? (
            <EmptyState title="暂无客户资产" description="客户会从线索跟进中沉淀，也可以后续从微信、企微、私信渠道同步。" />
          ) : (
            <div className="overflow-hidden rounded-lg border border-[#1E293B]">
              <table className="w-full text-left text-sm">
                <thead className="bg-[#0B0F1A] text-xs text-[#64748B]">
                  <tr>
                    <th className="px-3 py-3">客户</th>
                    <th className="px-3 py-3">来源</th>
                    <th className="px-3 py-3">意向</th>
                    <th className="px-3 py-3">状态</th>
                    <th className="px-3 py-3">下一步</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1E293B]">
                  {customers.map((item, index) => (
                    <tr key={item.id || index} onClick={() => setSelected(item)} className={`cursor-pointer ${selected === item ? 'bg-[#6366F1]/10' : 'hover:bg-[#0B0F1A]/60'}`}>
                      <td className="px-3 py-3">
                        <p className="font-medium text-[#F1F5F9]">{item.name || '未命名客户'}</p>
                        <p className="mt-1 truncate text-xs text-[#64748B]">{item.lastMessage || item.source || '暂无最近互动'}</p>
                      </td>
                      <td className="px-3 py-3 text-[#94A3B8]">{platformLabel(item.platform)}</td>
                      <td className="px-3 py-3 text-[#CBD5E1]">{item.grade || '-'}</td>
                      <td className="px-3 py-3"><StatusPill status={item.status || 'pending'} /></td>
                      <td className="px-3 py-3 text-[#94A3B8]">{item.next_action || '继续跟进'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="客户详情" description="查看来源链路、AI 总结和互动时间线。">
          {!selected ? (
            <EmptyState title="请选择客户" description="选择客户后查看消息记录、标签和推荐动作。" />
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                <p className="text-base font-semibold text-[#F1F5F9]">{selected.name || '未命名客户'}</p>
                <p className="mt-1 text-xs text-[#64748B]">{platformLabel(selected.platform)} · 负责人 {selected.owner || '未分配'}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(selected.tags || []).map((tag) => (
                    <span key={tag} className="rounded-full border border-[#334155] px-2 py-1 text-xs text-[#94A3B8]">{tag}</span>
                  ))}
                </div>
              </div>
              <div className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium text-[#F1F5F9]">
                  <History className="h-4 w-4 text-[#818CF8]" />
                  互动时间线
                </div>
                {loadingMessages ? (
                  <Loader2 className="h-5 w-5 animate-spin text-[#64748B]" />
                ) : messages.length === 0 ? (
                  <p className="text-xs text-[#64748B]">暂无消息记录</p>
                ) : (
                  <div className="space-y-3">
                    {messages.map((item, index) => (
                      <div key={item.id || index} className="rounded-lg bg-[#111827] p-3">
                        <p className="text-xs text-[#64748B]">{item.sender || 'assistant'} · {item.time || formatDateTime(item.created_at)}</p>
                        <p className="mt-1 text-sm text-[#CBD5E1]">{item.text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <FieldLabel>推荐下一步</FieldLabel>
                <div className="rounded-lg border border-[#334155] bg-[#0B0F1A] p-3 text-sm leading-6 text-[#CBD5E1]">
                  {selected.next_action || '基于客户最近互动，建议先确认需求和预算，再进入私信跟进。'}
                </div>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </PageShell>
  )
}
