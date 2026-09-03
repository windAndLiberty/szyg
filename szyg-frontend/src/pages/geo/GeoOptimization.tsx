import { useEffect, useState } from 'react'
import { Bot, CalendarClock, CheckCircle2, Globe2, Loader2, MoreHorizontal, RefreshCw } from 'lucide-react'
import {
  geoRecommendations, reviewGeoSite, updateGeoRecommendation, verifyGeoRecommendation,
  type GeoRecommendation,
} from '@/lib/api'
import { createWorkflowInstance, workflowInstances } from '../workflow/workflowApi'
import { EmptyGeo, GeoPage, GeoSection, handoffToSuperAgent, primaryButton, secondaryButton } from './GeoShared'

const categoryLabels: Record<string, string> = {
  not_understood: 'AI不了解企业', not_recommended: '知道但未推荐', competitor_ahead: '竞品表现领先',
  citation_gap: '权威引用不足', owned_site_gap: '官网未被引用', factual_error: '品牌信息错误', site_gap: '官网内容缺口',
}
const statusLabels: Record<string, string> = { open: '待处理', in_progress: '处理中', done: '已完成', dismissed: '已忽略', verifying: '验证中', verified: '已验证' }

export default function GeoOptimization() {
  const [items, setItems] = useState<GeoRecommendation[]>([])
  const [working, setWorking] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [menu, setMenu] = useState('')
  const [siteResult, setSiteResult] = useState<{ checks: Array<{ id: string; label: string; passed: boolean; detail: string }>; passed?: number; total?: number } | null>(null)

  const load = async () => {
    try { const data = await geoRecommendations(200); setItems(data.items || []) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'GEO优化建议加载失败') }
  }
  useEffect(() => { load() }, [])

  const enableWeekly = async () => {
    setWorking('weekly'); setError(''); setNotice('')
    try {
      const current = await workflowInstances()
      if ((current.items || []).some((item) => item.template_id === 'geo_weekly_audit')) { setNotice('每周GEO品牌检查已经启用。'); return }
      await createWorkflowInstance({ template_id: 'geo_weekly_audit', name: '每周检查AI是否推荐我的企业', schedule: { type: 'weekly', time: '09:00' }, config: {}, human_policy: 'pause_on_risk' })
      setNotice('已创建每周GEO品牌检查。系统会按时准备任务，你打开品牌体检后在右侧真实AI界面中执行。')
    } catch (cause) { setError(cause instanceof Error ? cause.message : '自动复查创建失败') }
    finally { setWorking('') }
  }

  const changeStatus = async (item: GeoRecommendation, status: 'open' | 'in_progress' | 'done' | 'dismissed') => {
    setWorking(item.id); setMenu('')
    try { await updateGeoRecommendation(item.id, status); await load() }
    catch (cause) { setError(cause instanceof Error ? cause.message : '建议状态更新失败') }
    finally { setWorking('') }
  }

  const verify = async (item: GeoRecommendation) => {
    setWorking(item.id); setMenu(''); setError('')
    try { await verifyGeoRecommendation(item.id); window.location.href = '/geo/workbench' }
    catch (cause) { setError(cause instanceof Error ? cause.message : '定向复查启动失败') }
    finally { setWorking('') }
  }

  const reviewSite = async () => {
    setWorking('site'); setError('')
    try { const result = await reviewGeoSite(); setSiteResult(result) }
    catch (cause) { setError(cause instanceof Error ? cause.message : '官网检查失败') }
    finally { setWorking('') }
  }

  const visible = items.filter((item) => item.status !== 'dismissed')

  return <GeoPage subtitle="把AI品牌问题变成今天能完成的工作，并在完成后验证是否真的改善。">
    {error && <div className="rounded-lg bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
    {notice && <div className="rounded-lg bg-[#10B981]/10 px-4 py-3 text-sm text-[#A7F3D0]">{notice}</div>}

    <section className="flex flex-col gap-4 rounded-2xl bg-gradient-to-br from-[#171B34] to-[#111827] p-6 shadow-[0_18px_50px_rgba(0,0,0,.18)] lg:flex-row lg:items-center">
      <div className="flex-1"><p className="text-xs font-medium text-[#A5B4FC]">持续验证，不做一次性改写</p><h1 className="mt-2 text-xl font-semibold text-[#F1F5F9]">每周检查AI是否开始理解、引用和推荐你的企业</h1><p className="mt-2 text-sm text-[#94A3B8]">系统按时准备任务；你打开品牌体检后，超级员工会在右侧真实AI界面中执行。内容发布和外部联系仍然等待确认。</p></div>
      <button onClick={enableWeekly} disabled={working === 'weekly'} className={primaryButton}>{working === 'weekly' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarClock className="h-4 w-4" />}设置每周自动复查</button>
    </section>

    <GeoSection title="改进并验证" description="优先级来自受影响问题的重要度、出现频率和平台数量，不使用含义不明的综合分。">
      {visible.length === 0 ? <EmptyGeo title="暂无改进任务" description="完成AI品牌体检后，系统会把未提及、未推荐、竞品领先、引用和事实问题转成任务。" /> : <div className="grid gap-4 lg:grid-cols-2">{visible.map((item) => <article key={item.id} className="relative rounded-xl bg-[#0B0F1A]/75 p-5">
        <div className="flex items-start justify-between gap-3"><div className="flex flex-wrap gap-2"><span className="rounded-full bg-[#6366F1]/10 px-2 py-1 text-xs text-[#A5B4FC]">{categoryLabels[item.category] || 'GEO改进'}</span><span className="rounded-full bg-[#64748B]/10 px-2 py-1 text-xs text-[#94A3B8]">{statusLabels[item.status] || item.status}</span></div><button onClick={() => setMenu(menu === item.id ? '' : item.id)} className="rounded-lg p-1.5 text-[#64748B] hover:bg-[#1E293B] hover:text-white"><MoreHorizontal className="h-4 w-4" /></button></div>
        <h2 className="mt-4 font-semibold text-[#F1F5F9]">{item.title}</h2><p className="mt-2 text-sm leading-6 text-[#94A3B8]">{item.description}</p>
        <div className="mt-4 rounded-lg bg-[#111827]/70 p-3"><p className="text-xs text-[#CBD5E1]">为什么现在做</p><p className="mt-1 text-xs leading-5 text-[#64748B]">{item.rationale || `共有 ${item.evidence_count} 条回答证据。`}</p></div>
        {item.verification_result?.after && <div className="mt-3 rounded-lg bg-[#10B981]/8 p-3"><p className="text-xs font-medium text-[#6EE7B7]">完成后复查结果</p><div className="mt-2 grid grid-cols-3 gap-2 text-xs"><div><p className="text-[#64748B]">提及率</p><p className="mt-1 text-[#D1FAE5]">{item.verification_result.before?.mention_rate || 0}% → {item.verification_result.after.mention_rate || 0}%</p></div><div><p className="text-[#64748B]">推荐率</p><p className="mt-1 text-[#D1FAE5]">{item.verification_result.before?.recommendation_rate || 0}% → {item.verification_result.after.recommendation_rate || 0}%</p></div><div><p className="text-[#64748B]">官网引用率</p><p className="mt-1 text-[#D1FAE5]">{item.verification_result.before?.owned_citation_rate || 0}% → {item.verification_result.after.owned_citation_rate || 0}%</p></div></div></div>}
        <div className="mt-5 flex items-center justify-between gap-3"><span className={`text-xs ${item.priority === 'high' ? 'text-[#FBBF24]' : 'text-[#94A3B8]'}`}>{item.evidence_count} 条依据 · {item.provider_ids?.length || 0} 个平台</span><button onClick={() => handoffToSuperAgent(`请处理这条GEO品牌改进任务：${item.title}。先读取证据，说明准备修改什么；涉及发布或外部联系时等待我确认。`, item.id)} className={primaryButton}><Bot className="h-4 w-4" />交给超级员工</button></div>
        {menu === item.id && <div className="absolute right-4 top-12 z-10 w-48 rounded-xl bg-[#1B2435] p-2 shadow-2xl">{item.status !== 'in_progress' && <button onClick={() => changeStatus(item, 'in_progress')} className="w-full rounded-lg px-3 py-2 text-left text-sm text-[#CBD5E1] hover:bg-[#273449]">标记处理中</button>}{item.status !== 'done' && <button onClick={() => changeStatus(item, 'done')} className="w-full rounded-lg px-3 py-2 text-left text-sm text-[#CBD5E1] hover:bg-[#273449]">标记已完成</button>}<button onClick={() => handoffToSuperAgent(`请基于企业知识库和这条GEO建议生成可引用的内容草稿：${item.title}`, item.id)} className="w-full rounded-lg px-3 py-2 text-left text-sm text-[#CBD5E1] hover:bg-[#273449]">生成内容草稿</button><button onClick={() => verify(item)} className="w-full rounded-lg px-3 py-2 text-left text-sm text-[#CBD5E1] hover:bg-[#273449]">重新验证（三次）</button><button onClick={() => changeStatus(item, 'dismissed')} className="w-full rounded-lg px-3 py-2 text-left text-sm text-[#FCA5A5] hover:bg-[#273449]">忽略建议</button></div>}
      </article>)}</div>}
    </GeoSection>

    <GeoSection title="官网是否容易被AI发现" description="检查公开访问、页面标题、结构化数据、robots.txt和网站地图，不会修改官网。" action={<button onClick={reviewSite} disabled={working === 'site'} className={secondaryButton}>{working === 'site' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Globe2 className="h-4 w-4" />}检查官网</button>}>
      {siteResult ? <div><div className="mb-4 flex items-center gap-2"><span className="text-2xl font-semibold text-white">{siteResult.passed || 0}/{siteResult.total || siteResult.checks.length}</span><span className="text-sm text-[#64748B]">项准备完成</span></div><div className="grid gap-3 md:grid-cols-2">{siteResult.checks.map((check) => <div key={check.id} className="flex gap-3 rounded-xl bg-[#0B0F1A]/75 p-4">{check.passed ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#34D399]" /> : <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 text-[#FBBF24]" />}<div><p className="text-sm text-[#E2E8F0]">{check.label}</p><p className="mt-1 text-xs leading-5 text-[#64748B]">{check.detail}</p></div></div>)}</div></div> : <p className="py-6 text-center text-sm text-[#64748B]">点击“检查官网”，获得一份普通用户也能理解的AI可发现性检查。</p>}
    </GeoSection>

    <GeoSection title="安全边界" description="GEO不会绕过现有审批机制。"><div className="grid gap-3 md:grid-cols-3">{['回答、推荐判断和引用均保留原始证据', '只有侧边栏自动采集的真实回答计入核心指标', '发布、发送和外部联系继续等待确认'].map((text) => <div key={text} className="flex items-start gap-3 rounded-xl bg-[#0B0F1A]/75 p-4"><CheckCircle2 className="mt-0.5 h-4 w-4 text-[#34D399]" /><p className="text-sm text-[#CBD5E1]">{text}</p></div>)}</div></GeoSection>
  </GeoPage>
}
