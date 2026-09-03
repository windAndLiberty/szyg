import { useState } from 'react'
import { Link, useLocation } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  FileInput,
  Cpu,
  FileText,
  Kanban,
  Users,
  Settings,
  ChevronLeft,
  ChevronRight,
  Workflow,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/input', label: '快速录入', icon: FileInput },
  { path: '/processing', label: 'AI 处理', icon: Cpu },
  { path: '/reports', label: '报告', icon: FileText },
  { path: '/pipeline', label: 'Pipeline', icon: Kanban },
  { path: '/customers', label: '客户', icon: Users },
  { path: '/settings', label: '设置', icon: Settings },
]

const sidebarVariants = {
  expanded: { width: 260 },
  collapsed: { width: 72 },
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  return (
    <motion.aside
      initial={false}
      animate={collapsed ? 'collapsed' : 'expanded'}
      variants={sidebarVariants}
      transition={{ duration: 0.4, ease: [0.45, 0.05, 0.55, 0.95] as [number, number, number, number] }}
      className="fixed left-0 top-0 h-screen bg-[#111827] border-r border-[#1E293B] z-40 flex flex-col overflow-hidden"
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-[#1E293B] shrink-0">
        <Link to="/" className="flex items-center gap-3 min-w-0">
          <Workflow className="w-7 h-7 text-[#6366F1] shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                className="font-display text-xl font-bold text-[#F1F5F9] whitespace-nowrap"
              >
                DealFlow
              </motion.span>
            )}
          </AnimatePresence>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto overflow-x-hidden">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path ||
            (item.path === '/reports' && location.pathname.startsWith('/report'))
          const Icon = item.icon

          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-100 relative group',
                isActive
                  ? 'bg-[rgba(99,102,241,0.08)] text-[#6366F1]'
                  : 'text-[#94A3B8] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#F1F5F9]'
              )}
            >
              {/* Active indicator */}
              {isActive && (
                <motion.div
                  layoutId="activeNavIndicator"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 bg-[#6366F1] rounded-r-full"
                  transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
                />
              )}

              <Icon className="w-5 h-5 shrink-0" />

              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: 'auto' }}
                    exit={{ opacity: 0, width: 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-sm font-medium whitespace-nowrap overflow-hidden"
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </Link>
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
              <span className="text-sm">Collapse</span>
            </div>
          )}
        </button>
      </div>
    </motion.aside>
  )
}
