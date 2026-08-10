import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronLeft, ChevronRight, ChevronDown, Workflow } from 'lucide-react'
import { navGroups } from '@/lib/navConfig'
import { useLayout, SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED } from '@/lib/layout'
import { cn } from '@/lib/utils'
import { useI18n } from '@/lib/i18n'
import {
  getWorkDoneNotices,
  clearWorkDone,
  WORK_DONE_CHANGE_EVENT,
} from '@/lib/workNotifications'

const sidebarVariants = {
  expanded: { width: SIDEBAR_WIDTH_EXPANDED },
  collapsed: { width: SIDEBAR_WIDTH_COLLAPSED },
}

export default function Sidebar() {
  const { collapsed, setCollapsed } = useLayout()
  const { t } = useI18n()
  const location = useLocation()

  // 自动展开当前路由所属分组
  const activeGroup = navGroups.find((g) =>
    g.children.some((c) => location.pathname === c.path),
  )
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(activeGroup ? [activeGroup.id] : []),
  )

  // 路由变化时自动展开当前分组
  useEffect(() => {
    if (activeGroup && !expandedGroups.has(activeGroup.id)) {
      setExpandedGroups((prev) => new Set(prev).add(activeGroup.id))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  // 工作现场任务完成提示(绿点):仅在工作任务完成后显示
  const [workDone, setWorkDone] = useState<Set<string>>(
    () => new Set(Object.keys(getWorkDoneNotices())),
  )

  useEffect(() => {
    const sync = () => setWorkDone(new Set(Object.keys(getWorkDoneNotices())))
    window.addEventListener(WORK_DONE_CHANGE_EVENT, sync)
    return () => window.removeEventListener(WORK_DONE_CHANGE_EVENT, sync)
  }, [])

  // 进入对应页面即视为已读,绿点消失
  useEffect(() => {
    if (workDone.has(location.pathname)) {
      clearWorkDone(location.pathname)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  const toggleGroup = (id: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <motion.aside
      initial={false}
      animate={collapsed ? 'collapsed' : 'expanded'}
      variants={sidebarVariants}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="fixed left-0 top-0 h-screen bg-[#111827] border-r border-[#1E293B] z-40 flex flex-col overflow-hidden"
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-[#1E293B] shrink-0">
        <Link to="/" className="flex items-center gap-3 min-w-0">
          <Workflow className="w-7 h-7 text-[#6366F1] shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                className="flex flex-col min-w-0"
              >
                <span className="font-display text-xl font-bold text-[#F1F5F9] whitespace-nowrap">
                  {t('领鹿员工')}
                </span>
                <span className="text-[10px] text-[#64748B] whitespace-nowrap -mt-0.5">
                  {t('超级数字员工')}
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </Link>
      </div>
      {/* === NAV RENDER MARKER === */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto overflow-x-hidden">
        {navGroups.map((group) => {
          const isExpanded = expandedGroups.has(group.id)
          const isGroupActive = activeGroup?.id === group.id
          const GroupIcon = group.icon

          return (
            <div key={group.id} className="mb-1">
              <div className="flex items-center">
                <Link
                  to={group.defaultChild}
                  onClick={() => toggleGroup(group.id)}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-lg transition-colors flex-1 min-w-0',
                    isGroupActive
                      ? 'text-[#F1F5F9]'
                      : 'text-[#94A3B8] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#F1F5F9]',
                  )}
                >
                  <GroupIcon className={cn('w-5 h-5 shrink-0', isGroupActive && 'text-[#6366F1]')} />
                  <AnimatePresence>
                    {!collapsed && (
                      <motion.span
                        initial={{ opacity: 0, width: 0 }}
                        animate={{ opacity: 1, width: 'auto' }}
                        exit={{ opacity: 0, width: 0 }}
                        transition={{ duration: 0.2 }}
                        className="text-sm font-medium whitespace-nowrap overflow-hidden"
                      >
                        {t(group.label)}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </Link>
                {!collapsed && group.children.length > 1 && (
                  <button
                    onClick={() => toggleGroup(group.id)}
                    className="p-1 mr-1 rounded text-[#64748B] hover:text-[#94A3B8] hover:bg-[rgba(255,255,255,0.03)] transition-colors shrink-0"
                    aria-label={t(isExpanded ? '折叠' : '展开')}
                  >
                    <motion.div animate={{ rotate: isExpanded ? 0 : -90 }} transition={{ duration: 0.2 }}>
                      <ChevronDown className="w-3.5 h-3.5" />
                    </motion.div>
                  </button>
                )}
              </div>

              <AnimatePresence initial={false}>
                {isExpanded && !collapsed && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                    className="overflow-hidden"
                  >
                    <div className="ml-3 pl-3 border-l border-[#1E293B] mt-0.5 space-y-0.5">
                      {group.children.map((child) => {
                        const isActive = location.pathname === child.path
                        const ChildIcon = child.icon
                        return (
                          <Link
                            key={child.path}
                            to={child.path}
                            className={cn(
                              'flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors relative',
                              isActive
                                ? 'bg-[rgba(99,102,241,0.08)] text-[#6366F1]'
                                : 'text-[#94A3B8] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#F1F5F9]',
                            )}
                          >
                            {isActive && (
                              <motion.div
                                layoutId={`active-${group.id}`}
                                className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[#6366F1] rounded-r-full"
                              />
                            )}
                            <ChildIcon className="w-4 h-4 shrink-0" />
                            <span className="text-[13px] whitespace-nowrap truncate">{t(child.label)}</span>
                            {workDone.has(child.path) && (
                              <span
                                title={t('有已完成的工作,点击查看')}
                                className="ml-auto w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_rgba(16,185,129,0.8)] shrink-0"
                              />
                            )}
                          </Link>
                        )
                      })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="px-3 py-3 border-t border-[#1E293B] shrink-0">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center w-full px-3 py-2 rounded-lg text-[#64748B] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#94A3B8] transition-colors duration-100"
        >
          {collapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <div className="flex items-center gap-2">
              <ChevronLeft className="w-5 h-5" />
              <span className="text-sm">{t('收起')}</span>
            </div>
          )}
        </button>
      </div>
    </motion.aside>
  )
}
