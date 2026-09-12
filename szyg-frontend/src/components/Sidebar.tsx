import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { navGroups } from '@/lib/navConfig'
import { SIDEBAR_WIDTH_COLLAPSED, SIDEBAR_WIDTH_EXPANDED, useLayout } from '@/lib/layout'
import { cn } from '@/lib/utils'
import { useI18n } from '@/lib/i18n'
import { WORK_DONE_CHANGE_EVENT, clearWorkDone, getWorkDoneNotices } from '@/lib/workNotifications'

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
  const navigate = useNavigate()
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

  const toggleGroup = (id: string, defaultChild: string) => {
    if (collapsed) {
      navigate(defaultChild)
      return
    }
    setExpandedGroups((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      saveExpandedGroups(next)
      return next
    })
  }

  return <aside
    className="fixed inset-y-0 left-0 z-40 flex flex-col overflow-hidden border-r border-[#1E293B] bg-[#111827] transition-[width] duration-150 ease-out [contain:layout_paint]"
    style={{ width: collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED }}
  >
    <div className={cn('flex h-16 shrink-0 items-center border-b border-[#1E293B]', collapsed ? 'justify-center px-2' : 'px-4')}>
      <Link to="/" className="flex min-w-0 items-center gap-3" title={collapsed ? t('数字员工') : undefined}>
        <img src="/logo1.png" alt="数字员工" className="h-8 w-8 shrink-0 object-contain" />
        {!collapsed && <div className="min-w-0"><p className="whitespace-nowrap font-display text-xl font-bold text-[#F1F5F9]">{t('数字员工')}</p><p className="-mt-0.5 whitespace-nowrap text-[10px] text-[#64748B]">{t('超级数字员工')}</p></div>}
      </Link>
    </div>

    <nav className={cn('min-h-0 flex-1 overflow-y-auto overflow-x-hidden py-3', collapsed ? 'px-2' : 'px-3')} aria-label={t('主导航')}>
      <div className="space-y-2">
        {navGroups.map((group) => {
          const isExpanded = expandedGroups.has(group.id) && !collapsed
          const isGroupActive = activeGroup?.id === group.id
          const GroupIcon = group.icon
          return <section key={group.id} className={cn('overflow-hidden rounded-lg', isGroupActive ? 'bg-[#6366F1]/[0.06]' : 'bg-transparent')}>
            <button
              type="button"
              onClick={() => toggleGroup(group.id, group.defaultChild)}
              className={cn('flex h-11 w-full items-center text-left outline-none transition-colors duration-100 hover:bg-white/[0.035] focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[#6366F1]', collapsed ? 'justify-center px-2' : 'gap-3 px-3')}
              aria-expanded={isExpanded}
              aria-controls={`sidebar-group-${group.id}`}
              title={collapsed ? t(group.label) : undefined}
            >
              <GroupIcon className={cn('h-5 w-5 shrink-0', isGroupActive ? 'text-[#818CF8]' : 'text-[#94A3B8]')} />
              {!collapsed && <><span className={cn('min-w-0 flex-1 truncate text-sm font-medium', isGroupActive ? 'text-[#F1F5F9]' : 'text-[#CBD5E1]')}>{t(group.label)}</span><ChevronDown className={cn('h-4 w-4 shrink-0 text-[#64748B] transition-transform duration-150', !isExpanded && '-rotate-90')} /></>}
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
                      tabIndex={isExpanded ? 0 : -1}
                      className={cn('relative flex h-9 items-center gap-2.5 rounded-md px-3 text-[13px] transition-colors duration-100', isActive ? 'bg-[#6366F1]/10 text-[#A5B4FC]' : 'text-[#94A3B8] hover:bg-white/[0.035] hover:text-[#F1F5F9]')}
                    >
                      {isActive && <span className="absolute bottom-2 left-0 top-2 w-[3px] rounded-r-full bg-[#6366F1]" />}
                      <ChildIcon className="h-4 w-4 shrink-0" />
                      <span className="min-w-0 flex-1 truncate">{t(child.label)}</span>
                      {workDone.has(child.path) && <span title={t('有已完成的工作,点击查看')} className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#10B981] shadow-[0_0_6px_rgba(16,185,129,0.8)]" />}
                    </Link>
                  })}
                </div>
              </div>
            </div>
          </section>
        })}
      </div>
    </nav>

    <div className="shrink-0 border-t border-[#1E293B] p-3">
      <button type="button" onClick={() => setCollapsed(!collapsed)} className="flex h-10 w-full items-center justify-center rounded-lg text-[#64748B] outline-none transition-colors duration-100 hover:bg-white/[0.035] hover:text-[#CBD5E1] focus-visible:ring-1 focus-visible:ring-[#6366F1]" aria-label={t(collapsed ? '展开侧边栏' : '收起侧边栏')}>
        {collapsed ? <ChevronRight className="h-5 w-5" /> : <span className="flex items-center gap-2 text-sm"><ChevronLeft className="h-5 w-5" />{t('收起')}</span>}
      </button>
    </div>
  </aside>
}
