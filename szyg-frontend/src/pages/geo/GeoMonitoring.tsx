import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, ExternalLink, Globe2, Loader2, Quote, Search, XCircle } from 'lucide-react'
import {
  cancelGeoAudit, createGeoAudit, geoAudit, geoObservations, geoOverview, geoQuestions, geoSources,
  type GeoAudit, type GeoObservation, type GeoProviderStatus, type GeoQuestion, type GeoSource,
} from '@/lib/api'
import BrowserWorkView, { type BrowserWorkEvent, type BrowserWorkPhase } from '@/components/superagent/BrowserWorkView'
import { EmptyGeo, GeoPage, GeoSection, inputClass, secondaryButton, useKeepAlivePageActive } from './GeoShared'

export default function GeoMonitoring() {
  const [items, setItems] = useState<GeoObservation[]>([])
  const [questions, setQuestions] = useState<GeoQuestion[]>([])
  const [providers, setProviders] = useState<GeoProviderStatus[]>([])
  const [sources, setSources] = useState<GeoSource[]>([])
  const [provider, setProvider] = useState('')
  const [status, setStatus] = useState('all')
  const [search, setSearch] = useState('')
  const [selectedQuestion, setSelectedQuestion] = useState('')
  const [selected, setSelected] = useState<GeoObservation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [audit, setAudit] = useState<GeoAudit | null>(null)
  const [auditWorking, setAuditWorking] = useState(false)
  const [browserOpen, setBrowserOpen] = useState(false)
  const [browserPaused, setBrowserPaused] = useState(false)
  const userStoppedAuditRef = useRef('')
  const pageActive = useKeepAlivePageActive()

  const load = async () => {
    try {
      const [data, overview, questionData, sourceData] = await Promise.all([geoObservations({ limit: 1000 }), geoOverview(30), geoQuestions(), geoSources(20)])
      setItems(data.items || []); setProviders(overview.providers || []); setQuestions(questionData.details || []); setSources(sourceData.items || [])
      const first = data.items?.[0] || null; setSelected(first); setSelectedQuestion(first?.question_id || questionData.details?.[0]?.id || '')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'AI回答记录加载失败') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const visible = useMemo(() => items.filter((item) =>
    (!provider || item.provider_id === provider) &&
    (status === 'all' || (status === 'recommended' ? item.recommended : status === 'mentioned' ? item.mentioned : status === 'failed' ? item.status === 'failed' : !item.mentioned)) &&
    (!search || item.question.toLowerCase().includes(search.toLowerCase())),
  ), [items, provider, status, search])

  const grouped = useMemo(() => {
    const map = new Map<string, GeoObservation[]>()
    visible.forEach((item) => map.set(item.question_id, [...(map.get(item.question_id) || []), item]))
    return [...map.entries()].map(([questionId, observations]) => ({ questionId, question: observations[0]?.question || '', observations }))
  }, [visible])

  const startSurfaceCheck = async () => {
    const question = questions.find((item) => item.id === selectedQuestion) || questions[0]
    if (!question) { setError('请先在品牌体检中确认客户问题'); return }
    const available = providers.filter((item) => item.configured && item.mode === 'consumer_surface')
    const selectedProvider = available.find((item) => item.id === provider) || available.find((item) => item.id === 'deepseek') || available[0]
    if (!selectedProvider) { setError('请使用领鹿开发桌面版进行真实AI界面检测'); return }
    setAuditWorking(true); setError(''); setNotice('')
    try {
      let next = await createGeoAudit({ provider_ids: [selectedProvider.id], question_ids: [question.id], sample_count: 1, mode: 'diagnostic' })
      userStoppedAuditRef.current = ''
      setAudit(next); setBrowserOpen(true); setBrowserPaused(false)
      setNotice(`超级员工正在${selectedProvider.label}真实界面中自动提问并读取回答。`)
      while (['queued', 'running'].includes(next.status)) {
        await new Promise((resolve) => setTimeout(resolve, 1500)); next = await geoAudit(next.id); setAudit(next)
      }
      if (next.status === 'failed' && userStoppedAuditRef.current === next.id) { setError(''); setNotice('本次复查已停止，已经采集的回答仍会保留。') }
      else if (next.status === 'failed') setError(next.error || '真实AI界面复查没有获得回答')
      else setNotice(next.status === 'partial' ? '复查已完成，部分证据暂未读取成功。' : '真实AI界面复查已完成，回答和引用已自动保存。')
      await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : '真实AI界面复查启动失败') }
    finally { setAuditWorking(false) }
  }

  const stopAudit = async () => {
    if (!audit || !['queued', 'running'].includes(audit.status)) return
    try {
      userStoppedAuditRef.current = audit.id
      const cancelled = await cancelGeoAudit(audit.id)
      setAudit(cancelled); setBrowserPaused(false); setNotice('本次复查已停止，已经采集的回答仍会保留。')
    } catch (cause) { setError(cause instanceof Error ? cause.message : '停止复查失败') }
  }

  const auditRunning = Boolean(audit && ['queued', 'running'].includes(audit.status))
  const auditWasStopped = Boolean(audit && userStoppedAuditRef.current === audit.id && ['failed', 'cancelled'].includes(audit.status))
  const browserPhase: BrowserWorkPhase = browserPaused ? 'paused' : auditWasStopped || audit?.status === 'cancelled' ? 'cancelled' : audit?.status === 'failed' ? 'failed' : audit?.status === 'completed' || audit?.status === 'partial' ? 'completed' : auditRunning ? 'running' : 'idle'
  const browserEvents: BrowserWorkEvent[] = audit ? [
    { id: 'question', type: 'type', title: '已自动向AI提出客户问题', state: auditRunning ? 'running' : 'success' },
    { id: 'capture', type: 'read', title: audit.completed ? '已自动读取并保存回答' : auditWasStopped ? '用户已停止复查' : '正在等待AI完整回答', detail: '回答正文与引用链接会直接保存，无需手工粘贴', state: auditWasStopped ? 'warning' : audit.status === 'failed' ? 'error' : audit.completed ? 'success' : 'running' },
  ] : []

  return <div className="flex h-[calc(100vh-4rem)] min-w-0 overflow-hidden bg-[#0B0F1A]">
  <GeoPage subtitle="按客户真实问题查看AI怎么说，并保留回答、推荐依据和引用来源。">
    {error && <div className="rounded-lg bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
    {notice && <div className="rounded-lg bg-[#10B981]/10 px-4 py-3 text-sm text-[#A7F3D0]">{notice}</div>}
    <GeoSection title="AI怎么说" description="同一个问题的不同平台和重复采样会放在一起，避免把一次回答误认为固定排名。" action={<div className="flex gap-2">{audit && !browserOpen && <button onClick={() => setBrowserOpen(true)} className={secondaryButton}><Globe2 className="h-4 w-4" />查看现场</button>}<button onClick={startSurfaceCheck} disabled={auditWorking} className={secondaryButton}>{auditWorking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Globe2 className="h-4 w-4" />}用真实AI界面复查</button></div>}>
      <div className="mb-4 grid gap-3 lg:grid-cols-4">
        <div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-[#64748B]" /><input value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputClass} pl-9`} placeholder="搜索客户问题" /></div>
        <select value={provider} onChange={(e) => setProvider(e.target.value)} className={inputClass}><option value="">全部AI平台</option>{providers.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={inputClass}><option value="all">全部表现</option><option value="recommended">被推荐</option><option value="mentioned">被提及</option><option value="missing">未提及</option><option value="failed">检测失败</option></select>
        <select value={selectedQuestion} onChange={(e) => setSelectedQuestion(e.target.value)} className={inputClass}><option value="">选择复查问题</option>{questions.map((item) => <option key={item.id} value={item.id}>{item.text}</option>)}</select>
      </div>
      {loading ? <div className="flex h-52 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-[#818CF8]" /></div> : grouped.length === 0 ? <EmptyGeo title="暂无可信回答记录" description="先在GEO品牌体检中启动真实AI界面检测；超级员工会自动提问并采集回答。" /> : <div className="grid gap-4 xl:grid-cols-[.9fr_1.1fr]">
        <div className="max-h-[660px] space-y-2 overflow-auto pr-1">{grouped.map((group) => {
          const recommended = group.observations.filter((item) => item.recommended).length
          const valid = group.observations.filter((item) => item.status === 'completed').length
          return <button key={group.questionId} onClick={() => setSelected(group.observations.find((item) => item.status === 'completed') || group.observations[0])} className={`w-full rounded-xl p-4 text-left ${selected?.question_id === group.questionId ? 'bg-[#1A2040]' : 'bg-[#0B0F1A]/75 hover:bg-[#131B2C]'}`}>
            <p className="text-sm font-medium leading-6 text-[#F1F5F9]">{group.question}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-[#6366F1]/10 px-2 py-1 text-[#A5B4FC]">{group.observations.length} 次检测</span><span className="rounded-full bg-[#10B981]/10 px-2 py-1 text-[#34D399]">{recommended}/{valid} 次推荐</span><span className="rounded-full bg-[#64748B]/10 px-2 py-1 text-[#94A3B8]">{new Set(group.observations.map((item) => item.provider_id)).size} 个平台</span></div>
          </button>
        })}</div>
        <div className="rounded-xl bg-[#0B0F1A]/75 p-5">{selected ? <>
          <div className="flex flex-wrap items-center gap-2 text-xs"><span className="text-[#818CF8]">{selected.provider_label}</span><span className="text-[#64748B]">第 {selected.sample_index} 次采样</span><span className="rounded-full bg-[#64748B]/10 px-2 py-1 text-[#94A3B8]">{selected.fidelity === 'consumer_surface' ? '真实AI界面' : selected.fidelity === 'official_search_api' ? '历史接口样本' : '历史普通模型'}</span></div>
          <h2 className="mt-3 text-base font-semibold leading-7 text-[#F1F5F9]">{selected.question}</h2>
          {selected.status === 'failed' ? <p className="mt-4 rounded-lg bg-[#EF4444]/8 p-4 text-sm text-[#FCA5A5]">{selected.error || '平台暂时没有返回可用回答'}</p> : <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-[#CBD5E1]">{selected.answer}</p>}
          {selected.recommendation_evidence && <div className="mt-5 rounded-lg bg-[#10B981]/8 p-4"><p className="text-xs font-medium text-[#34D399]">推荐依据</p><p className="mt-2 text-sm leading-6 text-[#CBD5E1]">{selected.recommendation_evidence}</p></div>}
          {!!selected.competitor_mentions?.length && <div className="mt-5"><p className="text-xs font-medium text-[#94A3B8]">回答中的竞品</p><div className="mt-2 flex flex-wrap gap-2">{selected.competitor_mentions.map((item, index) => <span key={`${item.name}-${index}`} className="rounded-full bg-[#F59E0B]/10 px-2 py-1 text-xs text-[#FBBF24]">{item.name}{item.recommended ? ' · 被推荐' : ''}</span>)}</div></div>}
          <div className="mt-5 bg-[#111827]/60 p-4"><p className="flex items-center gap-2 text-xs font-medium text-[#94A3B8]"><Quote className="h-3.5 w-3.5" />引用来源</p>{selected.citations.length ? <div className="mt-3 space-y-2">{selected.citations.map((citation) => <a key={citation.normalized_url || citation.url} href={citation.url} target="_blank" rel="noreferrer" className="flex items-start gap-2 text-xs text-[#818CF8]"><ExternalLink className="mt-0.5 h-3 w-3 shrink-0" /><span><span className="block text-[#CBD5E1]">{citation.title || citation.domain || citation.url}</span><span className="mt-0.5 block text-[#64748B]">{citation.domain}{citation.is_owned_domain ? ' · 企业官网' : ''}</span></span></a>)}</div> : <p className="mt-2 text-xs text-[#64748B]">本次回答没有返回可验证的引用链接。</p>}</div>
          <div className="mt-4 flex gap-2">{items.filter((item) => item.question_id === selected.question_id).map((item) => <button key={item.id} onClick={() => setSelected(item)} title={`${item.provider_label} 第${item.sample_index}次`} className={`flex h-8 w-8 items-center justify-center rounded-full ${item.status === 'failed' ? 'bg-[#EF4444]/10 text-[#F87171]' : item.recommended ? 'bg-[#10B981]/10 text-[#34D399]' : 'bg-[#64748B]/10 text-[#94A3B8]'}`}>{item.status === 'failed' ? <XCircle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}</button>)}</div>
        </> : <EmptyGeo title="请选择一个客户问题" description="查看不同AI平台的实际回答和引用来源。" />}</div>
      </div>}
    </GeoSection>

    <GeoSection title="AI常引用哪些来源" description="优先关注支持竞品、却还没有支持你品牌的第三方来源。">
      {sources.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{sources.slice(0, 9).map((item) => <a key={item.domain} href={item.sample_url} target="_blank" rel="noreferrer" className="rounded-xl bg-[#0B0F1A]/75 p-4 hover:bg-[#131B2C]"><div className="flex items-start justify-between gap-2"><p className="text-sm font-medium text-[#E2E8F0]">{item.domain}</p>{item.is_owned && <span className="rounded-full bg-[#10B981]/10 px-2 py-1 text-[10px] text-[#34D399]">企业官网</span>}</div><p className="mt-2 text-xs text-[#64748B]">{item.citation_count} 次引用 · {item.question_count} 个问题 · {item.provider_count} 个平台</p>{item.competitor_gap_count > 0 && <p className="mt-2 text-xs text-[#FBBF24]">{item.competitor_gap_count} 次出现在竞品领先回答中</p>}</a>)}</div> : <EmptyGeo title="暂无来源数据" description="从真实AI界面获得带引用的回答后，这里会自动形成来源机会。" />}
    </GeoSection>
  </GeoPage>
  <BrowserWorkView
    open={browserOpen}
    pageActive={pageActive}
    taskTitle="复查一个客户问题"
    result={audit?.completed ? '真实回答与引用已保存' : ''}
    status={audit ? `正在采集 ${audit.completed} / ${audit.total}` : '等待开始复查'}
    phase={browserPhase}
    events={browserEvents}
    approval={null}
    paused={browserPaused}
    busy={auditRunning}
    onClose={() => setBrowserOpen(false)}
    onTakeover={() => { setBrowserPaused(true); setNotice('你正在操作AI页面；点击“继续”后，超级员工会接着读取回答。') }}
    onResume={() => { setBrowserPaused(false); setNotice('超级员工已继续自动复查。') }}
    onStop={() => { void stopAudit() }}
    onApproval={() => undefined}
  />
  </div>
}
