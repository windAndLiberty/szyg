import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  BarChart3,
  BriefcaseBusiness,
  FileText,
  Loader2,
  Megaphone,
  Search,
  Sparkles,
} from 'lucide-react'
import { apiDel, apiGet, apiPost, getErrorMessage } from '@/lib/api'
import { useNavigate } from 'react-router'

type MarketCategory = {
  id: string
  label: string
}

type MarketSkill = {
  name: string
  description: string
  identifier: string
  category: string
  category_label: string
  downloads: number
  installs: number
  stars: number
  ready_to_use: boolean
  availability_label: string
  source: 'builtin' | 'external'
  builtin: boolean
  emoji: string
}

type InstalledSkill = {
  name: string
  skill_name?: string
  identifier: string
  installed_at?: string
  version?: string
  description: string
}

type MarketResponse = {
  items: MarketSkill[]
  total: number
  categories: MarketCategory[]
}

const categoryIcons = {
  recommended: Sparkles,
  office: BriefcaseBusiness,
  marketing: Megaphone,
  research: Search,
  data: BarChart3,
  content: FileText,
}

const builtinCategoryLabels: Record<string, string> = {
  office: '办公提效',
  marketing: '营销获客',
  research: '市场调研',
  data: '数据分析',
  content: '内容创作',
}

const BUILTIN_SKILL_DEFINITIONS = [
  ['content-planning', '内容策划与文案', '结合企业资料策划选题、营销文案和多平台内容方案。', 'content', '✍️'],
  ['image-creation', '图片创作', '根据业务目标生成海报、配图和营销视觉素材。', 'content', '🎨'],
  ['video-creation', '视频创作', '完成视频选题、脚本、画面规划和视频生成任务。', 'content', '🎬'],
  ['public-lead-discovery', '公域客户发现', '从公开内容和平台信号中发现高相关潜在客户机会。', 'marketing', '🎯'],
  ['customer-conversion', '客户转化跟进', '判断客户意向，准备个性化沟通内容和下一步行动。', 'marketing', '🤝'],
  ['content-publishing', '内容发布协作', '整理发布素材、检查内容并协助完成多平台发布。', 'marketing', '📣'],
  ['knowledge-assistant', '企业知识助手', '检索企业知识库，从内部资料中提取可靠信息和来源。', 'office', '📚'],
  ['document-analysis', '文档与附件分析', '阅读文档、表格、图片和音视频资料并整理重点。', 'office', '📄'],
  ['workflow-automation', '工作流自动化', '把重复经营任务整理为可复用、可跟踪的自动化流程。', 'office', '⚙️'],
  ['browser-assistant', '网页代办', '根据你的要求查找信息、填写内容并协助完成网页任务。', 'office', '🌐'],
  ['market-research', '市场调研', '综合公开资料研究市场、人群、竞争格局和真实需求。', 'research', '🔍'],
  ['competitive-intelligence', '竞品与市场情报', '跟踪竞品内容与市场变化，形成有依据的行动建议。', 'research', '🧭'],
  ['operations-insights', '运营数据洞察', '汇总内容、获客和转化表现，识别问题与增长机会。', 'data', '📊'],
  ['materials-management', '经营素材整理', '整理企业图片、视频和内容素材，便于后续创作与发布。', 'content', '🗂️'],
] as const

const BUILTIN_MARKET_SKILLS: MarketSkill[] = BUILTIN_SKILL_DEFINITIONS.map(([
  identifier,
  name,
  description,
  category,
  emoji,
]) => ({
  identifier: `szyg:${identifier}`,
  name,
  description,
  category,
  category_label: builtinCategoryLabels[category],
  downloads: 0,
  installs: 0,
  stars: 0,
  ready_to_use: true,
  availability_label: '系统内置',
  source: 'builtin',
  builtin: true,
  emoji,
}))

const primaryButton = 'inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md bg-[#6366F1] px-4 text-sm font-medium text-white transition hover:bg-[#5558E8] disabled:cursor-not-allowed disabled:opacity-45'
const secondaryButton = 'inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md border border-[#2A3547] bg-[#111827] px-3 text-sm text-[#CBD5E1] transition hover:border-[#46536A] hover:bg-[#172033] disabled:cursor-not-allowed disabled:opacity-45'
const itemActionButton = 'inline-flex h-9 shrink-0 items-center justify-center text-sm font-medium text-[#A5B4FC] underline decoration-[#6366F1]/65 underline-offset-4 transition hover:text-white hover:decoration-[#A5B4FC] disabled:cursor-not-allowed disabled:text-[#64748B] disabled:decoration-[#475569]'
const itemRemoveButton = 'inline-flex h-9 shrink-0 items-center justify-center text-sm text-[#94A3B8] underline decoration-[#475569] underline-offset-4 transition hover:text-[#FCA5A5] hover:decoration-[#EF4444]/70 disabled:cursor-not-allowed disabled:opacity-45'

function formatCount(value: number) {
  if (value >= 10000) return `${Math.floor(value / 1000) / 10}万次使用`
  if (value >= 1000) return `${Math.floor(value / 100) / 10}千次使用`
  if (value > 0) return `${value}次使用`
  return '新上架'
}

function friendlyName(value: string) {
  return value
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export default function Skills() {
  const navigate = useNavigate()
  const [view, setView] = useState<'all' | 'builtin' | 'external' | 'installed'>('all')
  const [category, setCategory] = useState('recommended')
  const [categories, setCategories] = useState<MarketCategory[]>([])
  const [market, setMarket] = useState<MarketSkill[]>([])
  const [installed, setInstalled] = useState<InstalledSkill[]>([])
  const [query, setQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const installedIds = useMemo(
    () => new Set(installed.map((item) => item.identifier || item.name)),
    [installed],
  )

  const loadInstalled = useCallback(async () => {
    const data = await apiGet<{ items: InstalledSkill[] }>('/api/skills/installed')
    setInstalled(data.items || [])
  }, [])

  const loadMarket = useCallback(async (
    categoryId: string,
    text = '',
    source: 'all' | 'builtin' | 'external' = 'all',
  ) => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ category: categoryId, source, page_size: '40' })
      if (text.trim()) params.set('q', text.trim())
      const data = await apiGet<MarketResponse>(`/api/skills/market?${params.toString()}`)
      const normalized = (data.items || []).map((item) => ({
        ...item,
        source: item.source || (item.identifier.startsWith('szyg:') ? 'builtin' : 'external'),
        builtin: item.builtin ?? item.identifier.startsWith('szyg:'),
        emoji: item.emoji || (item.identifier.startsWith('szyg:') ? '✨' : '🧩'),
      }))
      const backendBuiltin = normalized.filter((item) => item.builtin)
      const external = normalized.filter((item) => !item.builtin)
      const normalizedQuery = text.trim().toLowerCase()
      const localBuiltin = BUILTIN_MARKET_SKILLS.filter((item) => {
        if (categoryId !== 'recommended' && item.category !== categoryId) return false
        if (!normalizedQuery) return true
        return `${item.name} ${item.description}`.toLowerCase().includes(normalizedQuery)
      })
      const builtin = backendBuiltin.length > 0 ? backendBuiltin : localBuiltin
      const combined = source === 'builtin'
        ? builtin
        : source === 'external'
          ? external
          : [...builtin, ...external]
      setMarket(Array.from(new Map(combined.map((item) => [item.identifier, item])).values()))
      setCategories(data.categories || [])
    } catch (err) {
      setError(getErrorMessage(err, '能力市场暂时无法连接'))
      setMarket([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    Promise.all([loadInstalled(), loadMarket('recommended', '', 'all')]).catch((err) => {
      setError(getErrorMessage(err))
      setLoading(false)
    })
  }, [loadInstalled, loadMarket])

  const changeCategory = (nextCategory: string) => {
    setCategory(nextCategory)
    setQuery('')
    setSubmittedQuery('')
    loadMarket(nextCategory, '', view === 'installed' ? 'all' : view)
  }

  const changeView = (nextView: 'all' | 'builtin' | 'external' | 'installed') => {
    setView(nextView)
    setQuery('')
    setSubmittedQuery('')
    if (nextView !== 'installed') loadMarket(category, '', nextView)
  }

  const submitSearch = () => {
    const next = query.trim()
    setSubmittedQuery(next)
    loadMarket(category, next, view === 'installed' ? 'all' : view)
  }

  const install = async (item: MarketSkill) => {
    setWorking(item.identifier)
    setError('')
    setNotice('')
    try {
      await apiPost('/api/skills/install', { identifier: item.identifier })
      await loadInstalled()
      window.dispatchEvent(new Event('szyg:skills-changed'))
      setNotice(`“${item.name}”已添加，超级员工现在可以使用这项能力。`)
    } catch (err) {
      setError(getErrorMessage(err, '添加失败，请稍后重试'))
    } finally {
      setWorking('')
    }
  }

  const remove = async (item: InstalledSkill) => {
    if (!window.confirm(`从超级员工中移除“${friendlyName(item.name)}”？`)) return
    const skillName = item.skill_name || item.name
    setWorking(skillName)
    setError('')
    setNotice('')
    try {
      await apiDel(`/api/skills/installed/${encodeURIComponent(skillName)}`)
      await loadInstalled()
      window.dispatchEvent(new Event('szyg:skills-changed'))
      setNotice('已移除。')
    } catch (err) {
      setError(getErrorMessage(err, '移除失败，请稍后重试'))
    } finally {
      setWorking('')
    }
  }

  return (
    <div className="min-h-full bg-[#080C14] text-[#E5E7EB]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1E293B] px-6 py-4">
        <div>
          <div className="font-medium text-[#E2E8F0]">技能市场</div>
          <div className="mt-1 text-sm text-[#94A3B8]">查看系统内置技能，或为超级员工添加需要的外部技能。</div>
        </div>
        <button className={secondaryButton} onClick={() => navigate('/')}>
          <ArrowLeft className="h-4 w-4" />返回超级员工
        </button>
      </div>

      <div className="flex flex-col gap-4 border-b border-[#1E293B] px-6 py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap rounded-md border border-[#273449] bg-[#0B0F1A] p-1">
            {([
              ['all', '全部'],
              ['builtin', 'SZYG 内置'],
              ['external', '外部技能'],
              ['installed', `已添加${installed.length > 0 ? ` ${installed.length}` : ''}`],
            ] as const).map(([id, label]) => (
              <button
                key={id}
                className={`h-8 rounded px-4 text-sm transition ${view === id ? 'bg-[#273449] text-white' : 'text-[#94A3B8] hover:text-white'}`}
                onClick={() => changeView(id)}
              >
                {label}
              </button>
            ))}
          </div>

          {view !== 'installed' && (
            <div className="flex w-full max-w-md items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-[#64748B]" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => { if (event.key === 'Enter') submitSearch() }}
                  placeholder="搜索想让超级员工完成的工作"
                  className="h-9 w-full rounded-md border border-[#273449] bg-[#0B0F1A] pl-9 pr-3 text-sm outline-none transition focus:border-[#6366F1]"
                />
              </div>
              <button className={secondaryButton} onClick={submitSearch}>搜索</button>
            </div>
          )}
        </div>

        {view !== 'installed' && !submittedQuery && (
          <div className="flex flex-wrap gap-2">
            {categories.map((item) => {
              const Icon = categoryIcons[item.id as keyof typeof categoryIcons] || Sparkles
              return (
                <button
                  key={item.id}
                  onClick={() => changeCategory(item.id)}
                  className={`inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm transition ${category === item.id ? 'border-[#6366F1]/60 bg-[#6366F1]/12 text-[#C7D2FE]' : 'border-[#273449] bg-[#0D131F] text-[#94A3B8] hover:border-[#46536A] hover:text-white'}`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {error && <div className="mx-6 mt-4 rounded-md border border-[#7F1D1D] bg-[#450A0A]/30 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}
      {notice && (
        <div className="mx-6 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#14532D] bg-[#052E16]/30 px-4 py-3 text-sm text-[#86EFAC]">
          <span>{notice}</span>
          <button className="font-medium text-[#BBF7D0] underline underline-offset-4 hover:text-white" onClick={() => navigate('/')}>返回超级员工</button>
        </div>
      )}

      <div className="px-6 py-5">
        {view !== 'installed' ? (
          loading ? (
            <div className="flex h-56 items-center justify-center text-sm text-[#94A3B8]"><Loader2 className="mr-2 h-5 w-5 animate-spin" />正在寻找实用能力</div>
          ) : market.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              {market.map((item) => {
                const added = item.builtin || installedIds.has(item.identifier)
                return (
                  <div key={item.identifier} className="flex min-h-[132px] items-center gap-4 rounded-md border border-[#1E293B] bg-[#0D131F] px-5 py-4 transition hover:-translate-y-0.5 hover:border-[#46536A] hover:bg-[#111A29]">
                    <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-[#273449] bg-[#111827] text-xl" aria-hidden="true">{item.emoji || (item.builtin ? '✨' : '🧩')}</div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium text-[#E2E8F0]">{item.name}</div>
                      <p className="mt-1.5 line-clamp-2 text-sm leading-6 text-[#94A3B8]">{item.description}</p>
                      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[#64748B]">
                        <span>{item.category_label}</span>
                        {!item.builtin && <span>{formatCount(item.downloads)}</span>}
                        {!item.builtin && <span className="text-[#86EFAC]">{item.availability_label}</span>}
                      </div>
                    </div>
                    {item.builtin ? (
                      <span className="shrink-0 rounded-full border border-[#334155] bg-[#111827] px-3 py-1.5 text-xs text-[#94A3B8]">系统内置</span>
                    ) : (
                      <button className={itemActionButton} onClick={() => !added && install(item)} disabled={added || working === item.identifier}>
                        {working === item.identifier ? <Loader2 className="h-4 w-4 animate-spin" /> : added ? '已添加' : '添加'}
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="py-24 text-center">
              <Search className="mx-auto h-8 w-8 text-[#475569]" />
              <div className="mt-4 text-sm text-[#CBD5E1]">没有找到合适的能力</div>
              <div className="mt-1 text-xs text-[#64748B]">换一个更简单的工作描述试试</div>
            </div>
          )
        ) : installed.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {installed.map((item) => (
              <div key={item.name} className="flex min-h-[112px] items-center gap-4 rounded-md border border-[#1E293B] bg-[#0D131F] px-5 py-4">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-[#273449] bg-[#111827] text-xl" aria-hidden="true">🧩</div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-[#E2E8F0]">{friendlyName(item.name)}</div>
                  <p className="mt-1.5 text-sm leading-6 text-[#94A3B8]">{item.description}</p>
                </div>
                <button className={itemRemoveButton} title="移除能力" onClick={() => remove(item)} disabled={working === (item.skill_name || item.name)}>
                  {working === (item.skill_name || item.name) ? <Loader2 className="h-4 w-4 animate-spin" /> : '移除'}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-24 text-center">
            <Sparkles className="mx-auto h-8 w-8 text-[#475569]" />
            <div className="mt-4 text-sm text-[#CBD5E1]">还没有添加新的能力</div>
            <button className={`${primaryButton} mt-4`} onClick={() => changeView('external')}>去看看外部技能</button>
          </div>
        )}
      </div>
    </div>
  )
}
