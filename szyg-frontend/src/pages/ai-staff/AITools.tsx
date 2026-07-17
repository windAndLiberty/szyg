import { useMemo, useState } from 'react'
import {
  BadgeCheck,
  BriefcaseBusiness,
  Flame,
  Search,
  Sparkles,
  Star,
} from 'lucide-react'
import { AI_TOOL_CATEGORIES, AI_TOOLS_CATALOG, type AIToolCategory, type AIToolItem } from '@/lib/aiToolsCatalog'

type QuickFilter = 'all' | 'hot' | 'latest' | 'business'

const quickFilters: Array<{ key: QuickFilter; label: string; icon: typeof Sparkles }> = [
  { key: 'all', label: '全部工具', icon: Sparkles },
  { key: 'hot', label: '热门工具', icon: Flame },
  { key: 'latest', label: '最新收录', icon: BadgeCheck },
  { key: 'business', label: '企业常用', icon: BriefcaseBusiness },
]

function normalize(text: string) {
  return text.trim().toLowerCase()
}

function toolMatchesSearch(tool: AIToolItem, query: string) {
  const q = normalize(query)
  if (!q) return true
  return [
    tool.name,
    tool.description,
    tool.category,
    tool.scenario,
    tool.pricing,
    ...tool.tags,
  ].some((value) => normalize(value).includes(q))
}

function openTool(tool: AIToolItem) {
  window.open(tool.url, '_blank', 'noopener,noreferrer')
}

export default function AITools() {
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<'全部' | AIToolCategory>('全部')
  const [quickFilter, setQuickFilter] = useState<QuickFilter>('all')

  const filteredTools = useMemo(() => {
    return AI_TOOLS_CATALOG
      .filter((tool) => category === '全部' || tool.category === category)
      .filter((tool) => {
        if (quickFilter === 'hot') return Boolean(tool.hot)
        if (quickFilter === 'latest') return Boolean(tool.latest)
        if (quickFilter === 'business') return Boolean(tool.business)
        return true
      })
      .filter((tool) => toolMatchesSearch(tool, search))
      .sort((a, b) => {
        if (a.chinaReady !== b.chinaReady) return a.chinaReady ? -1 : 1
        if (Boolean(a.hot) !== Boolean(b.hot)) return a.hot ? -1 : 1
        if (Boolean(a.business) !== Boolean(b.business)) return a.business ? -1 : 1
        return b.rating - a.rating
      })
  }, [category, quickFilter, search])

  const stats = useMemo(() => {
    return {
      total: AI_TOOLS_CATALOG.length,
      hot: AI_TOOLS_CATALOG.filter((tool) => tool.hot).length,
      chinaReady: AI_TOOLS_CATALOG.filter((tool) => tool.chinaReady).length,
      business: AI_TOOLS_CATALOG.filter((tool) => tool.business).length,
    }
  }, [])

  return (
    <div className="min-h-full bg-[#0B0F1A] px-6 py-6">
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="mt-1 max-w-2xl text-body-sm text-[#94A3B8]">
              为老板和运营员工整理常用外部 AI 工具，快速找到写作、图片、视频、办公、搜索、编程和智能体平台。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="精选工具" value={stats.total} />
            <Metric label="热门" value={stats.hot} />
            <Metric label="国内可用" value={stats.chinaReady} />
            <Metric label="企业常用" value={stats.business} />
          </div>
        </header>

        <section className="rounded-card-lg border border-[#1E293B] bg-[#111827] p-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-center">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#64748B]" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="搜索工具名称、分类、标签或使用场景..."
                className="h-11 w-full rounded-lg border border-[#1E293B] bg-[#0B0F1A] pl-10 pr-4 text-body-sm text-[#F1F5F9] placeholder:text-[#64748B] outline-none transition-colors focus:border-[#6366F1]"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {quickFilters.map((item) => {
                const Icon = item.icon
                const active = quickFilter === item.key
                return (
                  <button
                    key={item.key}
                    onClick={() => setQuickFilter(item.key)}
                    className={`inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-body-xs transition-colors ${
                      active
                        ? 'border-[#6366F1]/50 bg-[#6366F1]/10 text-[#C4B5FD]'
                        : 'border-[#1E293B] bg-[#0B0F1A] text-[#94A3B8] hover:border-[#334155] hover:text-[#F1F5F9]'
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {item.label}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {AI_TOOL_CATEGORIES.map((item) => {
              const active = category === item
              return (
                <button
                  key={item}
                  onClick={() => setCategory(item)}
                  className={`h-8 rounded-lg border px-3 text-body-xs transition-colors ${
                    active
                      ? 'border-[#10B981]/40 bg-[#10B981]/10 text-[#86EFAC]'
                      : 'border-[#1E293B] bg-[#0B0F1A] text-[#94A3B8] hover:border-[#334155] hover:text-[#F1F5F9]'
                  }`}
                >
                  {item}
                </button>
              )
            })}
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredTools.map((tool) => (
            <ToolCard key={tool.id} tool={tool} />
          ))}
        </section>

        {filteredTools.length === 0 && (
          <div className="rounded-card-lg border border-[#1E293B] bg-[#111827] px-6 py-12 text-center">
            <Search className="mx-auto h-8 w-8 text-[#334155]" />
            <h2 className="mt-3 text-heading-sm text-[#F1F5F9]">没有找到匹配工具</h2>
            <p className="mt-1 text-body-sm text-[#64748B]">换一个关键词、分类或快捷筛选试试。</p>
          </div>
        )}
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-24 rounded-lg border border-[#1E293B] bg-[#111827] px-3 py-2">
      <div className="text-heading-sm text-[#F1F5F9]">{value}</div>
      <div className="mt-0.5 text-[11px] text-[#64748B]">{label}</div>
    </div>
  )
}

function ToolCard({ tool }: { tool: AIToolItem }) {
  return (
    <article
      onClick={() => openTool(tool)}
      role="link"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          openTool(tool)
        }
      }}
      className="group relative flex min-h-[220px] cursor-pointer flex-col overflow-hidden rounded-card-lg border border-[#1E293B] bg-[#111827] p-4 transition-all duration-200 hover:-translate-y-1.5 hover:border-[#6366F1]/70 hover:bg-[#151F33] hover:shadow-[0_18px_40px_rgba(15,23,42,0.55),0_0_0_1px_rgba(99,102,241,0.18)] focus:outline-none focus:ring-1 focus:ring-[#6366F1]/50"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="truncate text-heading-sm text-[#F1F5F9]">{tool.name}</h2>
            {tool.hot && <Flame className="h-4 w-4 shrink-0 text-[#F97316]" />}
            {tool.latest && <BadgeCheck className="h-4 w-4 shrink-0 text-[#22C55E]" />}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-[#6366F1]/10 px-2 py-0.5 text-[11px] text-[#C4B5FD]">{tool.category}</span>
            <span className="rounded-md bg-[#0B0F1A] px-2 py-0.5 text-[11px] text-[#94A3B8]">{tool.pricing}</span>
            {tool.chinaReady && <span className="rounded-md bg-[#10B981]/10 px-2 py-0.5 text-[11px] text-[#86EFAC]">国内可用</span>}
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-2 py-1 text-[12px] text-[#F8FAFC]">
          <Star className="h-3.5 w-3.5 fill-[#FACC15] text-[#FACC15]" />
          {tool.rating}
        </div>
      </div>

      <p className="mt-3 line-clamp-2 text-body-sm leading-6 text-[#CBD5E1]">{tool.description}</p>
      <div className="mt-3 rounded-lg border border-[#1E293B] bg-[#0B0F1A] px-3 py-2">
        <div className="text-[11px] text-[#64748B]">适合场景</div>
        <div className="mt-1 line-clamp-2 text-body-xs text-[#94A3B8]">{tool.scenario}</div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {tool.tags.slice(0, 4).map((tag) => (
          <span key={tag} className="rounded-md border border-[#1E293B] px-2 py-0.5 text-[11px] text-[#64748B]">
            {tag}
          </span>
        ))}
      </div>

    </article>
  )
}
