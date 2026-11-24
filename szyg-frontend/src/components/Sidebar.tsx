import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router'
import { ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { navGroups } from '@/lib/navConfig'
import { SIDEBAR_WIDTH_COLLAPSED, SIDEBAR_WIDTH_EXPANDED, useLayout } from '@/lib/layout'
import { cn } from '@/lib/utils'
import { useI18n } from '@/lib/i18n'
import { WORK_DONE_CHANGE_EVENT, clearWorkDone, getWorkDoneNotices } from '@/lib/workNotifications'
import { product } from '@/lib/product'

const EXPANDED_GROUPS_KEY = 'szyg:sidebar-expanded-groups'

function loadExpandedGroups(activeGroupId = ''): Set<string> {
  try {
    const raw = JSON.parse(window.localStorage.getItem(EXPANDED_GROUPS_KEY) || '[]')
    const ids = Array.isArray(raw) ? raw.filter((item): item is string => typeof item === 'string') : []
    if (activeGroupId) ids.push(activeGroupId)
    return new Set(ids)
  } catch {
    return new Set(activeGroupId ? [activeGroupId] : [])
  }
}

function saveExpandedGroups(groups: Set<string>) {
  try { window.localStorage.setItem(EXPANDED_GROUPS_KEY, JSON.stringify([...groups])) } catch { /* localStorage may be disabled */ }
}

export default function Sidebar() {
  const { collapsed, setCollapsed } = useLayout()
  const { t } = useI18n()
  const location = useLocation()
  const activeGroup = navGroups.find((group) => group.children.some((child) => location.pathname === child.path))
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => loadExpandedGroups(activeGroup?.id))
  const [workDone, setWorkDone] = useState<Set<string>>(() => new Set(Object.keys(getWorkDoneNotices())))

  useEffect(() => {
    if (!activeGroup) return
    setExpandedGroups((current) => {
      if (current.has(activeGroup.id)) return current
      const next = new Set(current).add(activeGroup.id)
      saveExpandedGroups(next)
      return next
    })
  }, [activeGroup?.id, location.pathname])

  useEffect(() => {
    const sync = () => setWorkDone(new Set(Object.keys(getWorkDoneNotices())))
    window.addEventListener(WORK_DONE_CHANGE_EVENT, sync)
    return () => window.removeEventListener(WORK_DONE_CHANGE_EVENT, sync)
  }, [])

  useEffect(() => {
    if (workDone.has(location.pathname)) clearWorkDone(location.pathname)
  }, [location.pathname, workDone])

  const toggleGroup = (id: string) => {
    if (collapsed) setCollapsed(false)
    setExpandedGroups((current) => {
      const next = new Set(current)
      if (!collapsed && next.has(id)) next.delete(id)
      else next.add(id)
      saveExpandedGroups(next)
      return next
    })
  }

  return <aside
    className="fixed inset-y-0 left-0 z-40 flex flex-col overflow-hidden border-r bg-card transition-[width] duration-150 ease-out [contain:layout_paint]"
    style={{ width: collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED }}
  >
    <div className={cn('flex h-16 shrink-0 items-center', collapsed ? 'justify-center px-2' : 'px-4')}>
      <Link to="/" className="flex min-w-0 items-center gap-3" title={collapsed ? t(product.name) : undefined}>
        <img src={product.logoUrl} alt={t(product.name)} className="h-8 w-8 shrink-0 rounded-md object-cover" />
        {!collapsed && <p className="truncate font-display text-xl font-bold text-foreground">{t(product.name)}</p>}
      </Link>
    </div>

    <nav className={cn('min-h-0 flex-1 overflow-y-auto overflow-x-hidden py-3', collapsed ? 'px-2' : 'px-3')} aria-label={t('navigation.main')}>
      <div className="space-y-1">
        {navGroups.map((group) => {
          const isExpanded = expandedGroups.has(group.id) && !collapsed
          const isGroupActive = activeGroup?.id === group.id
          const GroupIcon = group.icon
          return <section key={group.id} className={cn('overflow-hidden rounded-lg', isGroupActive ? 'bg-muted/50' : 'bg-transparent')}>
            <button
              type="button"
              onClick={() => toggleGroup(group.id)}
              className={cn('flex h-11 w-full items-center text-left outline-none transition-colors duration-100 hover:bg-muted focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[#6366F1]', collapsed ? 'justify-center px-2' : 'gap-3 px-3')}
              aria-label={t(group.label)}
              aria-expanded={isExpanded}
              aria-controls={`sidebar-group-${group.id}`}
              title={collapsed ? t(group.label) : undefined}
            >
              <GroupIcon className={cn('h-5 w-5 shrink-0', isGroupActive ? 'text-foreground' : 'text-muted-foreground')} />
              {!collapsed && <><span className={cn('min-w-0 flex-1 truncate text-sm font-medium', isGroupActive ? 'text-foreground' : 'text-foreground')}>{t(group.label)}</span><ChevronDown className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-150', !isExpanded && '-rotate-90')} /></>}
            </button>

            <div id={`sidebar-group-${group.id}`} className={cn('grid transition-[grid-template-rows,opacity] duration-150 ease-out', isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')} aria-hidden={!isExpanded}>
              <div className="min-h-0 overflow-hidden">
                <div className="mx-2 mb-2 pt-1">
                  {group.children.map((child) => {
                    const isActive = location.pathname === child.path
                    const ChildIcon = child.icon
                    return <Link
                      key={child.path}
                      to={child.path}
                      aria-current={isActive ? 'page' : undefined}
                      onClick={() => { if (window.matchMedia('(max-width: 760px)').matches) setCollapsed(true) }}
                      tabIndex={isExpanded ? 0 : -1}
                      className={cn('relative flex h-9 items-center gap-2.5 rounded-md px-3 text-[13px] transition-colors duration-100', isActive ? 'bg-muted text-foreground font-semibold' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}
                    >
                      <ChildIcon className="h-4 w-4 shrink-0" />
                      <span className="min-w-0 flex-1 truncate">{t(child.label)}</span>
                      {workDone.has(child.path) && <span title={t('navigation.completedWork')} className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#10B981] shadow-[0_0_6px_rgba(16,185,129,0.8)]" />}
                    </Link>
                  })}
                </div>
              </div>
            </div>
          </section>
        })}
      </div>
    </nav>

    <div className="shrink-0 border-t border-border p-3">
      <button type="button" onClick={() => setCollapsed(!collapsed)} className="flex h-10 w-full items-center justify-center rounded-lg text-muted-foreground outline-none transition-colors duration-100 hover:bg-muted hover:text-foreground focus-visible:ring-1 focus-visible:ring-[#6366F1]" aria-label={t(collapsed ? 'navigation.expandSidebar' : 'navigation.collapseSidebar')}>
        {collapsed ? <ChevronRight className="h-5 w-5" /> : <span className="flex items-center gap-2 text-sm"><ChevronLeft className="h-5 w-5" />{t('common.collapse')}</span>}
      </button>
    </div>
  </aside>
}
