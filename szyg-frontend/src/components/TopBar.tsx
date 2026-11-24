import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bell,
  ChevronDown,
  LogOut,
  User,
} from 'lucide-react'
import UserAvatar from '@/components/ui/UserAvatar'
import AvatarSettingsDialog from '@/components/ui/AvatarSettingsDialog'
import { cn } from '@/lib/utils'
import { allNavChildren, pageTitleMap } from '@/lib/navConfig'
import { useLayout } from '@/lib/layout'
import { useI18n } from '@/lib/i18n'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import PageSearch from '@/components/PageSearch'
import { fetchCloudSession, type CloudSession } from '@/lib/api'
import { logoutCloudSession } from '@/lib/cloudSession'

export default function TopBar() {
  const location = useLocation()
  const { sidebarWidth } = useLayout()
  const { t } = useI18n()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [avatarSettingsOpen, setAvatarSettingsOpen] = useState(false)
  const [cloudSession, setCloudSession] = useState<CloudSession | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)
  const displayName = cloudSession?.user?.display_name || t('账户管理')
  const displayEmail = cloudSession?.user?.email || ''

  // 从 navConfig 派生标题（支持全部路由）
  const pageTitle = t(pageTitleMap[location.pathname] || t("数字员工"))
  const pageNavItem = allNavChildren.find((item) => item.path === location.pathname)
  const PageIcon = pageNavItem?.icon
  const isSuperAgent = location.pathname === '/'

  // Close user menu on outside click
  useEffect(() => {
    let active = true
    void fetchCloudSession()
      .then((next) => { if (active) setCloudSession(next) })
      .catch(() => { if (active) setCloudSession(null) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLogout = async () => {
    if (loggingOut) return
    setLoggingOut(true)
    try {
      await logoutCloudSession()
    } finally {
      setUserMenuOpen(false)
      setLoggingOut(false)
    }
  }

  return (
    <header className="fixed top-0 right-0 left-0 h-16 bg-background/95 backdrop-blur-md border-b z-30 transition-[padding-left] duration-150 ease-out" style={{ paddingLeft: sidebarWidth }}>
      <div className="h-full flex items-center justify-between px-6">
        {/* Page title */}
        {isSuperAgent ? (
          <motion.div
            key="super-agent-title"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="flex items-center gap-2"
          >
            <h1 className="text-base font-semibold text-foreground">{t('navigation.superAgent')}</h1>
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
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <PageIcon className="h-4 w-4" />
              </span>
            )}
            <h1 className="text-base font-semibold text-foreground">{pageTitle}</h1>
          </motion.div>
        )}

        <PageSearch />

        {/* Right: Notifications + User */}
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          {/* Notifications */}
          <button className="relative p-2 rounded-lg text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors">
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
                className="p-1.5 rounded-lg hover:bg-muted/50 transition-colors"
                aria-label={t('common.changeAvatarHint')}
                title={t('common.changeAvatarHint')}
              >
                <UserAvatar className="h-8 w-8" alt={displayName} />
              </button>
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="p-1.5 rounded-lg hover:bg-muted/50 transition-colors"
                aria-label={t('common.accountMenu')}
              >
                <ChevronDown className={cn('w-4 h-4 text-muted-foreground transition-transform', userMenuOpen && 'rotate-180')} />
              </button>
            </div>

            <AnimatePresence>
              {userMenuOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.96 }}
                  transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
                  className="absolute right-0 top-full mt-1 w-48 bg-muted border border-border rounded-lg shadow-lg overflow-hidden z-50"
                >
                  <div className="px-3 py-2.5 border-b border-border">
                    <p className="text-sm font-medium text-foreground">{displayName}</p>
                    <p className="text-xs text-muted-foreground">{displayEmail}</p>
                  </div>
                  <button
                    onClick={() => {
                      setUserMenuOpen(false)
                      setAvatarSettingsOpen(true)
                    }}
                    className="flex items-center w-full px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                  >
                    <User className="w-4 h-4 mr-2 shrink-0" />
                    {t('common.changeAvatar')}
                  </button>
                  <button className="flex items-center w-full px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
                    <User className="w-4 h-4 mr-2 shrink-0" />
                    {t('common.profile')}
                  </button>
                  <div className="border-t border-border" />
                  <button
                    type="button"
                    onClick={() => void handleLogout()}
                    disabled={loggingOut}
                    className="flex items-center w-full px-3 py-2 text-sm text-danger-ink hover:bg-[rgba(239,68,68,0.05)] transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <LogOut className="w-4 h-4 mr-2 shrink-0" />
                    {loggingOut ? t('正在退出…') : t('common.signOut')}
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
