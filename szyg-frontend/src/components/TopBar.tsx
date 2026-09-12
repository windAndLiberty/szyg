import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  Bell,
  ChevronDown,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  User,
} from 'lucide-react'
import UserAvatar from '@/components/ui/UserAvatar'
import AvatarSettingsDialog from '@/components/ui/AvatarSettingsDialog'
import { cn } from '@/lib/utils'
import { allNavChildren, pageTitleMap } from '@/lib/navConfig'
import { useLayout } from '@/lib/layout'
import { useI18n } from '@/lib/i18n'
import { getCurrentUser } from '@/lib/api'

export default function TopBar() {
  const location = useLocation()
  const { sidebarWidth } = useLayout()
  const { t } = useI18n()
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [avatarSettingsOpen, setAvatarSettingsOpen] = useState(false)
  const [superAgentHistoryCollapsed, setSuperAgentHistoryCollapsed] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)
  const currentUser = getCurrentUser()
  const displayName = currentUser?.username ?? 'Admin'
  const displayEmail = `${displayName}@szyg.local`

  // 从 navConfig 派生标题（支持全部路由）
  const pageTitle = t(pageTitleMap[location.pathname] || '数字员工')
  const pageNavItem = allNavChildren.find((item) => item.path === location.pathname)
  const PageIcon = pageNavItem?.icon
  const isSuperAgent = location.pathname === '/'

  const toggleSuperAgentHistory = () => {
    const next = !superAgentHistoryCollapsed
    setSuperAgentHistoryCollapsed(next)
    window.dispatchEvent(new CustomEvent('szyg:toggle-super-agent-history', { detail: { collapsed: next } }))
  }

  // Close user menu on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <header className="fixed top-0 right-0 left-0 h-16 bg-[#111827]/95 backdrop-blur-md border-b border-[#1E293B] z-30 transition-[padding-left] duration-150 ease-out" style={{ paddingLeft: sidebarWidth }}>
      <div className="h-full flex items-center justify-between px-6">
        {/* Left: Page Title / Super Agent history toggle */}
        {isSuperAgent ? (
          <motion.div
            key="super-agent-history-toggle"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="flex items-center gap-2"
          >
            <h1 className="text-lg font-semibold text-[#F1F5F9]">{t('超级员工')}</h1>
            <button
              type="button"
              onClick={toggleSuperAgentHistory}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#1E293B] bg-[#0B0F1A] text-[#94A3B8] transition-colors hover:border-[#6366F1]/50 hover:text-[#F1F5F9]"
              aria-label={t(superAgentHistoryCollapsed ? '展开' : '折叠')}
              title={t(superAgentHistoryCollapsed ? '展开' : '折叠')}
            >
              {superAgentHistoryCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </button>
          </motion.div>
        ) : (
          <motion.div
            key={pageTitle}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="flex items-center gap-2"
          >
            {PageIcon && (
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[#6366F1]/15 text-[#A5B4FC]">
                <PageIcon className="h-4 w-4" />
              </span>
            )}
            <h1 className="text-lg font-semibold text-[#F1F5F9]">{pageTitle}</h1>
          </motion.div>
        )}

        {/* Center: Search */}
        <div className="flex-1 max-w-md mx-8">
          <AnimatePresence mode="wait">
            {searchOpen ? (
              <motion.div
                key="search-input"
                initial={{ width: 40, opacity: 0 }}
                animate={{ width: '100%', opacity: 1 }}
                exit={{ width: 40, opacity: 0 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
                className="relative"
              >
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
                <input
                  type="text"
                  autoFocus
                  value={searchValue}
                  onChange={(e) => setSearchValue(e.target.value)}
                  onBlur={() => {
                    if (!searchValue) setSearchOpen(false)
                  }}
                  placeholder={t('搜索...')}
                  className="w-full h-10 pl-10 pr-4 rounded-lg bg-[#0B0F1A] border border-[#1E293B] text-sm text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155] transition-colors"
                />
              </motion.div>
            ) : (
              <motion.button
                key="search-button"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setSearchOpen(true)}
                className="flex items-center gap-2 h-10 px-3 rounded-lg bg-[#0B0F1A] border border-[#1E293B] text-[#64748B] hover:text-[#94A3B8] hover:border-[#334155] transition-colors"
              >
                <Search className="w-4 h-4" />
                <span className="text-sm">{t('搜索...')}</span>
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        {/* Right: Notifications + User */}
        <div className="flex items-center gap-3">
          {/* Notifications */}
          <button className="relative p-2 rounded-lg text-[#94A3B8] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#F1F5F9] transition-colors">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#EF4444] rounded-full" />
          </button>

          {/* User Dropdown */}
          <div className="relative" ref={userMenuRef}>
            <div className="flex items-center gap-0.5">
              <button
                onClick={() => {
                  setUserMenuOpen(false)
                  setAvatarSettingsOpen(true)
                }}
                className="p-1.5 rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors"
                aria-label={t('点击设置头像')}
                title={t('点击设置头像')}
              >
                <UserAvatar className="h-8 w-8" alt={displayName} />
              </button>
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="p-1.5 rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors"
                aria-label={t('个人菜单')}
              >
                <ChevronDown className={cn('w-4 h-4 text-[#64748B] transition-transform', userMenuOpen && 'rotate-180')} />
              </button>
            </div>

            <AnimatePresence>
              {userMenuOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.96 }}
                  transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
                  className="absolute right-0 top-full mt-1 w-48 bg-[#1A2235] border border-[#1E293B] rounded-lg shadow-lg overflow-hidden z-50"
                >
                  <div className="px-3 py-2.5 border-b border-[#1E293B]">
                    <p className="text-sm font-medium text-[#F1F5F9]">{displayName}</p>
                    <p className="text-xs text-[#64748B]">{displayEmail}</p>
                  </div>
                  <button
                    onClick={() => {
                      setUserMenuOpen(false)
                      setAvatarSettingsOpen(true)
                    }}
                    className="flex items-center w-full px-3 py-2 text-sm text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)] transition-colors"
                  >
                    <User className="w-4 h-4 mr-2 shrink-0" />
                    {t('更换头像')}
                  </button>
                  <button className="flex items-center w-full px-3 py-2 text-sm text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)] transition-colors">
                    <User className="w-4 h-4 mr-2 shrink-0" />
                    {t('个人资料')}
                  </button>
                  <div className="border-t border-[#1E293B]" />
                  <button className="flex items-center w-full px-3 py-2 text-sm text-[#EF4444] hover:bg-[rgba(239,68,68,0.05)] transition-colors">
                    <LogOut className="w-4 h-4 mr-2 shrink-0" />
                    {t('退出登录')}
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      <AvatarSettingsDialog open={avatarSettingsOpen} onClose={() => setAvatarSettingsOpen(false)} />
    </header>
  )
}
