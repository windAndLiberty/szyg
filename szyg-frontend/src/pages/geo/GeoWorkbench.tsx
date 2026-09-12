import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, ChevronRight, Globe2, Loader2, Play, RefreshCw, Save, Sparkles, Target } from 'lucide-react'
import {
  cancelGeoAudit, createGeoAudit, geoAudit, geoOverview, geoProfile, geoQuestions, suggestGeoQuestions,
  updateGeoProfile, updateGeoQuestions, type GeoAudit, type GeoOverview, type GeoProfile, type GeoQuestion,
} from '@/lib/api'
import BrowserWorkView, { type BrowserWorkEvent, type BrowserWorkPhase } from '@/components/superagent/BrowserWorkView'
import { EmptyGeo, GeoMetric, GeoPage, GeoSection, inputClass, primaryButton, secondaryButton, useKeepAlivePageActive } from './GeoShared'

const emptyProfile: GeoProfile = { id: 'default', product_name: '', website: '', industry: '', audience: '', region: '', brand_aliases: [], products: [], competitors: [], languages: ['zh-CN'], target_questions: [], geo_providers: [] }
const sourceLabels: Record<string, string> = { ai_suggestion: '企业资料', marketing_intelligence: '营销情报', existing: '已在使用', manual: '手动添加', legacy: '历史问题' }

export default function GeoWorkbench() {
  const [overview, setOverview] = useState<GeoOverview | null>(null)
  const [profile, setProfile] = useState<GeoProfile>(emptyProfile)
  const [questions, setQuestions] = useState<GeoQuestion[]>([])
  const [editing, setEditing] = useState(false)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [browserOpen, setBrowserOpen] = useState(false)
  const [activeAudit, setActiveAudit] = useState<GeoAudit | null>(null)
  const [browserPaused, setBrowserPaused] = useState(false)
  const userStoppedAuditRef = useRef('')
  const monitoringAuditRef = useRef('')
  const pageActive = useKeepAlivePageActive()

  const load = async () => {
    try {
      const [overviewData, profileData, questionData] = await Promise.all([geoOverview(30), geoProfile(), geoQuestions()])
      setOverview(overviewData); setProfile({ ...emptyProfile, ...profileData }); setQuestions(questionData.details || [])
      if (!profileData.product_name || !(questionData.details || []).length) setEditing(true)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'GEO数据加载失败') }
  }
  useEffect(() => { load() }, [])

  const consumerProviders = overview?.providers.filter((item) => item.configured && item.mode === 'consumer_surface') || []
  const selectedProviders = profile.geo_providers.filter((id) => consumerProviders.some((item) => item.id === id))
  // One visible browser surface is sampled serially. Defaulting to DeepSeek
  // avoids triggering several platform login flows for a first-time user.
  const defaultProvider = consumerProviders.find((item) => item.id === 'deepseek') || consumerProviders[0]
  const providerIds = selectedProviders.length ? selectedProviders.slice(0, 1) : defaultProvider ? [defaultProvider.id] : []
  const selectedQuestions = useMemo(() => questions.filter((item) => item.selected !== false), [questions])

  const discoverQuestions = async () => {
    if (!profile.product_name.trim()) { setError('请先填写企业或品牌名称'); return }
    setWorking('suggest'); setError(''); setNotice('')
    try {
      await updateGeoProfile({
        product_name: profile.product_name, website: profile.website, industry: profile.industry,
        audience: profile.audience, region: profile.region, brand_aliases: profile.brand_aliases,
        products: profile.products, competitors: profile.competitors, languages: profile.languages,
        geo_providers: providerIds,
      })
      const data = await suggestGeoQuestions(20)
      setQuestions(data.items.map((item) => ({ ...item, selected: item.selected !== false })))
      setNotice('已根据企业资料和营销情报整理客户问题，请确认后开始体检。')
    } catch (cause) { setError(cause instanceof Error ? cause.message : '客户问题生成失败') }
    finally { setWorking('') }
  }

  const save = async () => {
    setWorking('save'); setError(''); setNotice('')
    try {
      await updateGeoProfile({
        product_name: profile.product_name, website: profile.website, industry: profile.industry,
        audience: profile.audience, region: profile.region, brand_aliases: profile.brand_aliases,
        products: profile.products, competitors: profile.competitors, languages: profile.languages,
        geo_providers: providerIds,
      })
      if (!selectedQuestions.length) throw new Error('请至少保留一个客户问题')
      await updateGeoQuestions(selectedQuestions.map(({ selected: _selected, ...item }) => item))
      setEditing(false); setNotice('企业资料和客户问题已保存。'); await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'GEO资料保存失败') }
    finally { setWorking('') }
  }

  const monitorAudit = async (initial: GeoAudit) => {
    if (monitoringAuditRef.current === initial.id) return
    monitoringAuditRef.current = initial.id
    let audit = initial
    try {
      while (['queued', 'running'].includes(audit.status)) {
        await new Promise((resolve) => setTimeout(resolve, 1500)); audit = await geoAudit(audit.id); setActiveAudit(audit)
      }
      if (audit.status === 'failed' && userStoppedAuditRef.current === audit.id) { setError(''); setNotice('本次检测已停止，已经采集的回答仍会保留。') }
      else if (audit.status === 'failed') setError(audit.error || '本次真实界面检测没有获得可用结果')
      else setNotice(audit.status === 'partial' ? '检测已完成，部分问题暂时没有获得回答，其他真实结果已保留。' : '真实AI界面检测已完成。')
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'AI品牌体检进度读取失败')
    } finally {
      if (monitoringAuditRef.current === initial.id) monitoringAuditRef.current = ''
    }
  }

  useEffect(() => {
    const pending = overview?.latest_audit
    if (!pending || !['queued', 'running'].includes(pending.status) || monitoringAuditRef.current === pending.id) return
    setActiveAudit(pending); setBrowserOpen(true); setBrowserPaused(false)
    setNotice(pending.mode === 'scheduled' ? '本周检测已准备好，正在右侧真实AI界面中执行。' : '正在恢复尚未完成的真实AI界面检测。')
    void monitorAudit(pending)
  }, [overview?.latest_audit?.id, overview?.latest_audit?.status])

  const startAudit = async () => {
    setWorking('audit'); setError(''); setNotice('')
    try {
      if (editing) throw new Error('请先保存体检范围，再开始AI品牌体检')
      let audit = await createGeoAudit({ provider_ids: providerIds, question_ids: selectedQuestions.map((item) => item.id), sample_count: 1, mode: 'diagnostic' })
      userStoppedAuditRef.current = ''
      setActiveAudit(audit); setBrowserOpen(true); setBrowserPaused(false)
      setNotice(`真实AI界面检测已开始。超级员工会在右侧工作现场自动提出 ${audit.total} 个问题并读取回答，无需复制粘贴。`)
      await monitorAudit(audit)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'AI品牌体检启动失败') }
    finally { setWorking('') }
  }

  const stopAudit = async () => {
    if (!activeAudit || !['queued', 'running'].includes(activeAudit.status)) return
    try {
      userStoppedAuditRef.current = activeAudit.id
      const cancelled = await cancelGeoAudit(activeAudit.id)
      setActiveAudit(cancelled); setBrowserPaused(false)
      setNotice('本次检测已停止，已经采集的回答仍会保留。')
    } catch (cause) { setError(cause instanceof Error ? cause.message : '停止检测失败') }
  }

  const summary = !overview?.valid_sample_count
    ? '还没有形成可参考的AI品牌结论。完成企业资料和客户问题后，系统会检查AI是否认识、推荐并准确介绍你的企业。'
    : `过去30天从真实AI界面获得 ${overview.valid_sample_count} 条有效回答。${overview.mention_rate >= 60 ? '多数回答已经认识你的品牌' : 'AI对品牌的认知仍需补齐'}，${overview.recommendation_rate >= 40 ? '并开始在部分问题中主动推荐' : '但主动推荐仍然不足'}。当前数据可信度：${overview.confidence_label}。`

  const auditRunning = Boolean(activeAudit && ['queued', 'running'].includes(activeAudit.status))
  const auditWasStopped = Boolean(activeAudit && userStoppedAuditRef.current === activeAudit.id && ['failed', 'cancelled'].includes(activeAudit.status))
  const browserPhase: BrowserWorkPhase = browserPaused ? 'paused' : auditWasStopped || activeAudit?.status === 'cancelled' ? 'cancelled' : activeAudit?.status === 'failed' ? 'failed' : activeAudit?.status === 'completed' || activeAudit?.status === 'partial' ? 'completed' : auditRunning ? 'running' : 'idle'
  const browserEvents: BrowserWorkEvent[] = activeAudit ? [
    { id: 'started', type: 'navigate', title: `已开始在${consumerProviders.find((item) => item.id === activeAudit.provider_ids[0])?.label || '真实AI界面'}检测`, state: auditRunning ? 'running' : 'success' },
    { id: 'progress', type: 'observe', title: `已采集 ${activeAudit.completed} / ${activeAudit.total} 条回答`, detail: auditWasStopped ? '用户已停止本次检测' : activeAudit.failed ? `${activeAudit.failed} 条暂未获得结果` : '回答与引用会自动保存到本地', state: auditWasStopped ? 'warning' : activeAudit.status === 'failed' ? 'error' : auditRunning ? 'running' : 'success' },
  ] : []

  return <div className="flex h-[calc(100vh-4rem)] min-w-0 overflow-hidden bg-[#0B0F1A]">
  <GeoPage subtitle="持续检查客户向AI咨询时，是否能看到、理解并信任你的品牌。">
    {error && <div className="rounded-lg bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
    {notice && <div className="rounded-lg bg-[#10B981]/10 px-4 py-3 text-sm text-[#A7F3D0]">{notice}</div>}

    <section className="rounded-2xl bg-gradient-to-br from-[#171B34] to-[#111827] p-6 shadow-[0_18px_50px_rgba(0,0,0,.18)]">
      <p className="text-xs font-medium text-[#A5B4FC]">AI品牌结论</p>
      <h1 className="mt-3 max-w-4xl text-xl font-semibold leading-8 text-[#F1F5F9]">{summary}</h1>
      <div className="mt-5 flex flex-wrap gap-3">
        <button onClick={startAudit} disabled={working === 'audit' || auditRunning || editing || !profile.product_name || !selectedQuestions.length || !consumerProviders.length} className={primaryButton}>{working === 'audit' || auditRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}开始真实AI界面检测</button>
        {activeAudit && !browserOpen && <button onClick={() => setBrowserOpen(true)} className={secondaryButton}><Globe2 className="h-4 w-4" />查看检测现场</button>}
        <button onClick={() => setEditing((value) => !value)} className={secondaryButton}>{editing ? '收起设置' : '检查体检范围'}</button>
      </div>
      <p className="mt-3 text-xs leading-5 text-[#64748B]">本次默认检测 1 个平台 × {selectedQuestions.length} 个已选问题。不会消耗数字员工或 Dolphin 的模型推理 Token；但会像你正常提问一样，占用所选 AI 平台账号的对话次数或使用配额。</p>
      {!consumerProviders.length && <p className="mt-3 text-xs text-[#FBBF24]">当前无法使用真实AI界面检测。请从开发桌面版启动数字员工，并确认右侧工作现场可用。</p>}
    </section>

    <div className="grid gap-4 md:grid-cols-3">
      <GeoMetric label="AI认识我吗" value={`${overview?.mention_rate || 0}%`} icon={Globe2} hint={`${overview?.valid_sample_count || 0} 条有效样本`} />
      <GeoMetric label="AI会推荐我吗" value={`${overview?.recommendation_rate || 0}%`} icon={Target} tone="green" hint={`首选率 ${overview?.first_choice_rate || 0}%`} />
      <GeoMetric
        label="信息准确吗"
        value={overview?.fact_checked_sample_count ? `${overview.accuracy_rate || 0}%` : '待核验'}
        icon={overview?.factual_issue_count ? AlertTriangle : CheckCircle2}
        tone={overview?.factual_issue_count ? 'red' : overview?.fact_checked_sample_count ? 'green' : 'amber'}
        hint={overview?.fact_checked_sample_count ? `${overview.factual_issue_count || 0} 条错误信息` : '当前仅保存原文，避免用规则猜测事实对错'}
      />
    </div>

    {editing && <GeoSection title="三步完成体检设置" description="只填写业务信息；超级员工会复用桌面版中的AI平台登录状态，不需要配置API密钥。">
      <div className="grid gap-5 xl:grid-cols-[.85fr_1.15fr]">
        <div className="space-y-4 rounded-xl bg-[#0B0F1A]/70 p-5">
          <div><p className="text-xs font-medium text-[#818CF8]">1 · 确认企业</p></div>
          <div><label className="mb-2 block text-xs text-[#94A3B8]">企业或品牌名称</label><input value={profile.product_name} onChange={(e) => setProfile({ ...profile, product_name: e.target.value })} className={inputClass} /></div>
          <div><label className="mb-2 block text-xs text-[#94A3B8]">官网</label><input value={profile.website} onChange={(e) => setProfile({ ...profile, website: e.target.value })} className={inputClass} placeholder="https://" /></div>
          <div><label className="mb-2 block text-xs text-[#94A3B8]">主要产品（逗号分隔）</label><input value={profile.products.join('，')} onChange={(e) => setProfile({ ...profile, products: e.target.value.split(/[，,]/).map((v) => v.trim()).filter(Boolean) })} className={inputClass} /></div>
          <div><label className="mb-2 block text-xs text-[#94A3B8]">目标客户</label><input value={profile.audience || ''} onChange={(e) => setProfile({ ...profile, audience: e.target.value })} className={inputClass} /></div>
          <div><label className="mb-2 block text-xs text-[#94A3B8]">主要竞品（逗号分隔）</label><input value={profile.competitors.join('，')} onChange={(e) => setProfile({ ...profile, competitors: e.target.value.split(/[，,]/).map((v) => v.trim()).filter(Boolean) })} className={inputClass} /></div>
          <div>
            <label className="mb-2 block text-xs text-[#94A3B8]">本次用哪个AI检测</label>
            <div className="grid gap-2 sm:grid-cols-2">
              {consumerProviders.map((item) => <label key={item.id} className={`flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2.5 text-sm ${providerIds[0] === item.id ? 'bg-[#6366F1]/15 text-[#C7D2FE]' : 'bg-[#111827] text-[#94A3B8] hover:bg-[#172033]'}`}><input type="radio" name="geo-provider" checked={providerIds[0] === item.id} onChange={() => setProfile({ ...profile, geo_providers: [item.id] })} className="accent-[#6366F1]" />{item.label}</label>)}
            </div>
            <p className="mt-2 text-xs leading-5 text-[#64748B]">一次只检测一个平台，超级员工会在右侧真实界面中逐个提问。默认使用 DeepSeek。</p>
          </div>
          <button onClick={discoverQuestions} disabled={working === 'suggest'} className={secondaryButton}>{working === 'suggest' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}发现客户会问什么</button>
        </div>
        <div className="rounded-xl bg-[#0B0F1A]/70 p-5">
          <div className="flex items-center justify-between"><p className="text-xs font-medium text-[#818CF8]">2 · 确认客户问题</p><span className="text-xs text-[#64748B]">已选 {selectedQuestions.length} / {questions.length}</span></div>
          {questions.length ? <div className="mt-4 max-h-[440px] space-y-2 overflow-auto pr-1">{questions.map((item, index) => <label key={item.id || index} className="flex cursor-pointer gap-3 rounded-lg bg-[#111827] p-3 hover:bg-[#172033]"><input type="checkbox" checked={item.selected !== false} onChange={(e) => setQuestions((rows) => rows.map((row, i) => i === index ? { ...row, selected: e.target.checked } : row))} className="mt-1 accent-[#6366F1]" /><div><p className="text-sm text-[#E2E8F0]">{item.text}</p><p className="mt-1 text-xs text-[#64748B]">{item.topic || '客户问题'} · {sourceLabels[item.source] || '智能建议'}</p></div></label>)}</div> : <EmptyGeo title="尚未生成客户问题" description="填写企业信息后，点击“发现客户会问什么”，系统会从企业资料和营销情报中生成建议。" />}
          <div className="mt-4 flex items-center justify-between"><p className="text-xs text-[#64748B]">3 · 保存后即可开始体检</p><button onClick={save} disabled={working === 'save'} className={primaryButton}>{working === 'save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}保存体检范围</button></div>
        </div>
      </div>
    </GeoSection>}

    <div className="grid gap-5 xl:grid-cols-[1.2fr_.8fr]">
      <GeoSection title="今天最值得做的事" description="建议来自真实回答、竞品和引用差距。">
        {overview?.recommendations.length ? <div className="space-y-2">{overview.recommendations.slice(0, 3).map((item) => <a key={item.id} href="/geo/optimization" className="flex items-center gap-3 rounded-xl bg-[#0B0F1A]/75 p-4 hover:bg-[#131B2C]"><Sparkles className="h-4 w-4 text-[#A5B4FC]" /><div className="flex-1"><p className="text-sm font-medium text-[#F1F5F9]">{item.title}</p><p className="mt-1 text-xs text-[#64748B]">{item.rationale || item.description}</p></div><ChevronRight className="h-4 w-4 text-[#64748B]" /></a>)}</div> : <EmptyGeo title="暂无改进建议" description="完成一次真实AI品牌体检后，这里会优先展示最值得处理的三项工作。" />}
      </GeoSection>
      <GeoSection title="体检覆盖" description="所有核心结果都来自用户实际使用的AI产品界面。">
        {!!overview?.valid_sample_count && <p className="mb-3 text-xs text-[#64748B]">真实界面回答 {overview.consumer_sample_count || 0} 条 · 暂未获得结果的平台 {overview.failed_provider_count || 0} 个</p>}
        <div className="space-y-2">{(overview?.providers || []).map((item) => <div key={item.id} className="flex items-center justify-between rounded-xl bg-[#0B0F1A]/75 px-4 py-3"><div><p className="text-sm text-[#E2E8F0]">{item.label}</p><p className="mt-1 text-xs text-[#64748B]">侧边栏真实AI界面 · 复用本地登录状态</p></div><span className={`rounded-full px-2 py-1 text-xs ${item.configured ? 'bg-[#10B981]/10 text-[#34D399]' : 'bg-[#64748B]/10 text-[#94A3B8]'}`}>{item.configured ? '可检测' : '需要桌面版'}</span></div>)}</div>
        <button onClick={load} className="mt-4 inline-flex items-center gap-2 text-xs text-[#818CF8]"><RefreshCw className="h-3.5 w-3.5" />刷新覆盖状态</button>
      </GeoSection>
    </div>
  </GeoPage>
  <BrowserWorkView
    open={browserOpen}
    pageActive={pageActive}
    taskTitle="GEO真实AI界面检测"
    result={activeAudit ? `已保存 ${activeAudit.completed} 条真实回答` : ''}
    status={activeAudit ? `正在采集 ${activeAudit.completed} / ${activeAudit.total}` : '等待开始检测'}
    phase={browserPhase}
    events={browserEvents}
    approval={null}
    paused={browserPaused}
    busy={auditRunning}
    onClose={() => setBrowserOpen(false)}
    onTakeover={() => { setBrowserPaused(true); setNotice('你正在操作AI页面；点击“继续”后，超级员工会从当前位置接着检测。') }}
    onResume={() => { setBrowserPaused(false); setNotice('超级员工已继续自动检测。') }}
    onStop={() => { void stopAudit() }}
    onApproval={() => undefined}
  />
  </div>
}
