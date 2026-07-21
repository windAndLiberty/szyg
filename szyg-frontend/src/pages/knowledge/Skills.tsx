import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  BarChart3,
  BriefcaseBusiness,
  FileText,
  Loader2,
  Megaphone,
  Search,
  Sparkles,
} from 'lucide-react'
import { apiDel, apiGet, apiPost, getErrorMessage } from '@/lib/api'

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
  const [view, setView] = useState<'market' | 'installed'>('market')
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

  const loadMarket = useCallback(async (categoryId: string, text = '') => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ category: categoryId, page_size: '24' })
      if (text.trim()) params.set('q', text.trim())
      const data = await apiGet<MarketResponse>(`/api/skills/market?${params.toString()}`)
      setMarket(data.items || [])
      setCategories(data.categories || [])
    } catch (err) {
      setError(getErrorMessage(err, '能力市场暂时无法连接'))
      setMarket([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    Promise.all([loadInstalled(), loadMarket('recommended')]).catch((err) => {
      setError(getErrorMessage(err))
      setLoading(false)
    })
  }, [loadInstalled, loadMarket])

  const changeCategory = (nextCategory: string) => {
    setCategory(nextCategory)
    setQuery('')
    setSubmittedQuery('')
    loadMarket(nextCategory)
  }

  const submitSearch = () => {
    const next = query.trim()
    setSubmittedQuery(next)
    loadMarket(category, next)
  }

  const install = async (item: MarketSkill) => {
    setWorking(item.identifier)
    setError('')
    setNotice('')
    try {
      await apiPost('/api/skills/install', { identifier: item.identifier })
      await loadInstalled()
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
      setNotice('已移除。')
    } catch (err) {
      setError(getErrorMessage(err, '移除失败，请稍后重试'))
    } finally {
      setWorking('')
    }
  }

  return (
    <div className="min-h-full bg-[#080C14] text-[#E5E7EB]">
      <div className="border-b border-[#1E293B] px-6 py-4 text-sm text-[#94A3B8]">
        按需为超级员工添加新的工作能力，让日常经营少一些重复操作。
      </div>

      <div className="flex flex-col gap-4 border-b border-[#1E293B] px-6 py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex rounded-md border border-[#273449] bg-[#0B0F1A] p-1">
            <button
              className={`h-8 rounded px-4 text-sm transition ${view === 'market' ? 'bg-[#273449] text-white' : 'text-[#94A3B8] hover:text-white'}`}
              onClick={() => setView('market')}
            >
              推荐能力
            </button>
            <button
              className={`h-8 rounded px-4 text-sm transition ${view === 'installed' ? 'bg-[#273449] text-white' : 'text-[#94A3B8] hover:text-white'}`}
              onClick={() => setView('installed')}
            >
              我的能力{installed.length > 0 ? ` ${installed.length}` : ''}
            </button>
          </div>

          {view === 'market' && (
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

        {view === 'market' && !submittedQuery && (
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
      {notice && <div className="mx-6 mt-4 rounded-md border border-[#14532D] bg-[#052E16]/30 px-4 py-3 text-sm text-[#86EFAC]">{notice}</div>}

      <div className="px-6 py-5">
        {view === 'market' ? (
          loading ? (
            <div className="flex h-56 items-center justify-center text-sm text-[#94A3B8]"><Loader2 className="mr-2 h-5 w-5 animate-spin" />正在寻找实用能力</div>
          ) : market.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              {market.map((item) => {
                const added = installedIds.has(item.identifier)
                return (
                  <div key={item.identifier} className="flex min-h-[132px] items-center gap-4 rounded-md border border-[#1E293B] bg-[#0D131F] px-5 py-4 transition hover:-translate-y-0.5 hover:border-[#46536A] hover:bg-[#111A29]">
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium text-[#E2E8F0]">{item.name}</div>
                      <p className="mt-1.5 line-clamp-2 text-sm leading-6 text-[#94A3B8]">{item.description}</p>
                      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[#64748B]">
                        <span>{item.category_label}</span>
                        <span>{formatCount(item.downloads)}</span>
                        <span className="text-[#86EFAC]">{item.availability_label}</span>
                      </div>
                    </div>
                    <button className={itemActionButton} onClick={() => !added && install(item)} disabled={added || working === item.identifier}>
                      {working === item.identifier ? <Loader2 className="h-4 w-4 animate-spin" /> : added ? '已添加' : '添加'}
                    </button>
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
            <button className={`${primaryButton} mt-4`} onClick={() => setView('market')}>去看看推荐能力</button>
          </div>
        )}
      </div>
    </div>
  )
}
