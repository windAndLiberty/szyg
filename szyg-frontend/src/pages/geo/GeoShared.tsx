import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { translateCurrent } from '@/lib/i18n'

export const panelClass = 'rounded-xl bg-card/80 shadow-[0_1px_0_rgba(255,255,255,0.025)]'
export const inputClass = 'w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-[#6366F1]'
export const primaryButton = 'inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:brightness-90 disabled:cursor-not-allowed disabled:opacity-45'
export const secondaryButton = 'inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-medium text-foreground hover:border-[#6366F1] hover:text-foreground disabled:opacity-45'

export function GeoPage({ subtitle, children }: { subtitle: string; children: ReactNode }) {
  return <div className="flex h-full min-w-0 flex-1 flex-col overflow-auto bg-background"><div className="px-6 pb-2 pt-5 text-sm text-muted-foreground">{subtitle}</div><div className="space-y-5 p-6 pt-3">{children}</div></div>
}

export { useKeepAlivePageActive } from '@/lib/hooks'

export function GeoMetric({ label, value, icon: Icon, hint, tone = 'indigo' }: { label: string; value: string | number; icon: LucideIcon; hint?: string; tone?: 'indigo' | 'green' | 'amber' | 'red' }) {
  const colors = { indigo: 'bg-[#6366F1]/12 text-accent-ink', green: 'bg-[#10B981]/12 text-success-ink', amber: 'bg-[#F59E0B]/12 text-warning-ink', red: 'bg-[#EF4444]/12 text-danger-ink' }
  return <div className={`${panelClass} p-4`}><div className="flex items-start justify-between"><div><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold text-foreground">{value}</p></div><div className={`flex h-9 w-9 items-center justify-center rounded-lg ${colors[tone]}`}><Icon className="h-4 w-4" /></div></div>{hint && <p className="mt-3 text-xs text-muted-foreground">{hint}</p>}</div>
}

export function GeoSection({ title, description, action, children }: { title: string; description?: string; action?: ReactNode; children: ReactNode }) {
  return <section className={panelClass}><div className="flex items-start justify-between gap-4 px-5 pb-2 pt-5"><div><h2 className="text-sm font-semibold text-foreground">{title}</h2>{description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}</div>{action}</div><div className="p-5 pt-3">{children}</div></section>
}

export function EmptyGeo({ title, description }: { title: string; description: string }) {
  return <div className="flex min-h-40 flex-col items-center justify-center rounded-lg bg-background/60 px-6 py-10 text-center"><p className="text-sm font-medium text-foreground">{title}</p><p className="mt-2 max-w-md text-xs leading-5 text-muted-foreground">{description}</p></div>
}

export function handoffToSuperAgent(prompt: string, recommendationId?: string) {
  const context = recommendationId ? translateCurrent("{v0} 请先调用 geo.recommendation.get 读取建议 {v1} 的完整证据，再制定方案。", { v0: prompt, v1: recommendationId }) : prompt
  sessionStorage.setItem('szyg:super-agent-prefill', context)
  window.location.href = '/'
}
