import { useEffect, useState, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { useLocation } from 'react-router'

export const panelClass = 'rounded-xl bg-[#111827]/80 shadow-[0_1px_0_rgba(255,255,255,0.025)]'
export const inputClass = 'w-full rounded-lg border border-[#273449] bg-[#0B0F1A] px-3 py-2.5 text-sm text-[#F1F5F9] outline-none placeholder:text-[#475569] focus:border-[#6366F1]'
export const primaryButton = 'inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-[#6366F1] px-4 text-sm font-medium text-white hover:bg-[#5558E6] disabled:cursor-not-allowed disabled:opacity-45'
export const secondaryButton = 'inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-[#334155] bg-[#0B0F1A] px-3 text-sm font-medium text-[#CBD5E1] hover:border-[#6366F1] hover:text-white disabled:opacity-45'

export function GeoPage({ subtitle, children }: { subtitle: string; children: ReactNode }) {
  return <div className="flex h-full min-w-0 flex-1 flex-col overflow-auto bg-[#0B0F1A]"><div className="px-6 pb-2 pt-5 text-sm text-[#94A3B8]">{subtitle}</div><div className="space-y-5 p-6 pt-3">{children}</div></div>
}

/**
 * App.tsx keeps recently visited routes mounted. Native Electron WebContentsView
 * surfaces are not affected by CSS display:none, so every GEO page that owns the
 * browser work view must explicitly hide it when its keep-alive slot is inactive.
 */
export function useKeepAlivePageActive() {
  const location = useLocation()
  const pagePath = location.pathname + location.search
  const [active, setActive] = useState(() => {
    if (typeof window === 'undefined') return true
    return window.location.pathname + window.location.search === pagePath
  })

  useEffect(() => {
    const update = (event?: Event) => {
      const path = (event as CustomEvent<{ path?: string }> | undefined)?.detail?.path
      setActive((path || window.location.pathname + window.location.search) === pagePath)
    }
    update()
    window.addEventListener('szyg:keep-alive-active-changed', update)
    return () => window.removeEventListener('szyg:keep-alive-active-changed', update)
  }, [pagePath])

  return active
}

export function GeoMetric({ label, value, icon: Icon, hint, tone = 'indigo' }: { label: string; value: string | number; icon: LucideIcon; hint?: string; tone?: 'indigo' | 'green' | 'amber' | 'red' }) {
  const colors = { indigo: 'bg-[#6366F1]/12 text-[#A5B4FC]', green: 'bg-[#10B981]/12 text-[#34D399]', amber: 'bg-[#F59E0B]/12 text-[#FBBF24]', red: 'bg-[#EF4444]/12 text-[#F87171]' }
  return <div className={`${panelClass} p-4`}><div className="flex items-start justify-between"><div><p className="text-xs text-[#64748B]">{label}</p><p className="mt-2 text-2xl font-semibold text-[#F1F5F9]">{value}</p></div><div className={`flex h-9 w-9 items-center justify-center rounded-lg ${colors[tone]}`}><Icon className="h-4 w-4" /></div></div>{hint && <p className="mt-3 text-xs text-[#64748B]">{hint}</p>}</div>
}

export function GeoSection({ title, description, action, children }: { title: string; description?: string; action?: ReactNode; children: ReactNode }) {
  return <section className={panelClass}><div className="flex items-start justify-between gap-4 px-5 pb-2 pt-5"><div><h2 className="text-sm font-semibold text-[#F1F5F9]">{title}</h2>{description && <p className="mt-1 text-xs text-[#64748B]">{description}</p>}</div>{action}</div><div className="p-5 pt-3">{children}</div></section>
}

export function EmptyGeo({ title, description }: { title: string; description: string }) {
  return <div className="flex min-h-40 flex-col items-center justify-center rounded-lg bg-[#0B0F1A]/60 px-6 py-10 text-center"><p className="text-sm font-medium text-[#CBD5E1]">{title}</p><p className="mt-2 max-w-md text-xs leading-5 text-[#64748B]">{description}</p></div>
}

export function handoffToSuperAgent(prompt: string, recommendationId?: string) {
  const context = recommendationId ? `${prompt}\n\n请先调用 geo.recommendation.get 读取建议 ${recommendationId} 的完整证据，再制定方案。` : prompt
  sessionStorage.setItem('szyg:super-agent-prefill', context)
  window.location.href = '/'
}
