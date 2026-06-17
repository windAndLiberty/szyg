'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Monitor, Settings, User, LogOut, Paintbrush, ChevronLeft, ChevronRight,
  MessageSquarePlus, Send, Clapperboard, FileImage, FileText, Bot,
  Sparkles, Globe, MessageCircleHeart, BarChart3, Wrench,
  Copy, TrendingUp, Tags, Camera, Users, UserCheck,
  Stethoscope, Eye, LayoutDashboard, Newspaper,
  Pencil, ImagePlus, ArrowLeftRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth, useBrand } from '@/lib/hooks'
import Particles from './Particles'
import FeatureNav from './FeatureNav'
import TitleBar from './TitleBar'

const themes = [
  { value: 'default', label: '🔵 经典蓝' },
  { value: 'dark', label: '🌙 暗夜黑' },
  { value: 'green', label: '🌿 自然绿' },
  { value: 'sunset', label: '🌅 日落橙' },
  { value: 'starry', label: '⭐ 星空紫' },
]

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { user, isAdmin, token, loading, logout: doLogout } = useAuth()
  const { brand, setTheme } = useBrand()
  const [isElectron, setIsElectron] = useState(false)
  const [themeOpen, setThemeOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [disclaimer, setDisclaimer] = useState(false)

  useEffect(() => {
    setIsElectron(!!window.electronAPI)
  }, [])

  useEffect(() => {
    if (!loading && !token && pathname !== '/login') {
      router.push('/login')
    }
    if (pathname?.startsWith('/admin') && !isAdmin && !loading && user?.role) {
      router.push('/dashboard')
    }
  }, [pathname, isAdmin, user, router, token, loading])

  const switchTheme = (t: string) => {
    setTheme(t)
    setThemeOpen(false)
  }

  const logout = () => {
    doLogout()
    router.push('/login')
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden" data-theme={brand.theme || 'default'}>
      <TitleBar />
      <Particles />

      {/* Mobile overlay */}
      <AnimatePresence>
        {mobileSidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            onClick={() => setMobileSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Sidebar */}
        <aside
          className={cn(
            'fixed lg:sticky top-0 left-0 z-50 h-screen flex-shrink-0 border-r border-white/5 backdrop-blur-2xl bg-[var(--header-bg)]/90 transition-all duration-300',
            isElectron && 'pt-8',
            sidebarCollapsed ? 'w-16' : 'w-64',
            mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          )}
        >
          {/* Brand */}
          <div className="flex items-center gap-3 px-4 h-14 border-b border-white/5">
            <Link href="/dashboard" className="flex items-center gap-2 flex-1 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent-light flex items-center justify-center flex-shrink-0">
                <Monitor className="w-4 h-4 text-white" />
              </div>
              {!sidebarCollapsed && (
                <span className="text-sm font-bold text-white tracking-tight truncate">
                  {brand.name}
                </span>
              )}
            </Link>
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="hidden lg:flex p-1 rounded-md text-white/30 hover:text-white/60 hover:bg-white/5 transition-all"
            >
              {sidebarCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
            </button>
          </div>

          {/* Navigation */}
          <div className="py-3 px-2 overflow-y-auto h-[calc(100vh-3.5rem-3rem)]">
            {sidebarCollapsed ? (
              <CollapsedNav pathname={pathname || ''} />
            ) : (
              <FeatureNav onNavigate={() => setMobileSidebarOpen(false)} />
            )}
          </div>

          {/* Sidebar footer */}
          <div className="absolute bottom-0 left-0 right-0 border-t border-white/5 px-3 py-2">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setThemeOpen(!themeOpen)}
                className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/5 transition-all"
              >
                <Paintbrush className="w-4 h-4" />
              </button>
              {!sidebarCollapsed && (
                <span className="text-xs text-white/30 truncate flex-1">{user?.username || '未登录'}</span>
              )}
              <div className="relative">
                <button
                  onClick={() => setProfileOpen(!profileOpen)}
                  className="w-7 h-7 rounded-full bg-gradient-to-br from-accent to-accent-light flex items-center justify-center text-white text-xs hover:shadow-lg hover:shadow-accent/30 transition-all"
                >
                  <User className="w-3.5 h-3.5" />
                </button>
                <AnimatePresence>
                  {profileOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 8, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 8, scale: 0.95 }}
                      className={cn(
                        'absolute bottom-full mb-2 w-36 rounded-xl border border-white/10 bg-[var(--header-bg)]/95 backdrop-blur-xl shadow-2xl overflow-hidden',
                        sidebarCollapsed ? 'left-0' : 'right-0'
                      )}
                    >
                      <button
                        onClick={() => { setProfileOpen(false); router.push('/oem') }}
                        className="w-full px-4 py-2.5 text-left text-sm text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                      >
                        品牌设置
                      </button>
                      {isAdmin && (
                        <button
                          onClick={() => { setProfileOpen(false); router.push('/admin') }}
                          className="w-full px-4 py-2.5 text-left text-sm text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                        >
                          系统管理
                        </button>
                      )}
                      <div className="border-t border-white/5" />
                      <button
                        onClick={logout}
                        className="w-full px-4 py-2.5 text-left text-sm text-red-400 hover:text-red-300 hover:bg-white/5 transition-colors flex items-center gap-2"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        退出
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Theme picker */}
            <AnimatePresence>
              {themeOpen && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="pt-2 space-y-1">
                    {themes.map((t) => (
                      <button
                        key={t.value}
                        onClick={() => switchTheme(t.value)}
                        className="w-full px-3 py-1.5 text-left text-xs text-white/60 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </aside>

        <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
          {/* Mobile header */}
          <header className={cn('lg:hidden flex items-center justify-between px-4 h-14 border-b border-white/5 backdrop-blur-xl bg-[var(--header-bg)]/80 z-30', isElectron && 'mt-8')}>
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="p-2 rounded-lg text-white/50 hover:text-white hover:bg-white/5"
            >
              <Sparkles className="w-5 h-5" />
            </button>
            <span className="text-sm font-bold text-white">{brand.name}</span>
            <div className="w-8" />
          </header>

          <main className="flex-1 page-content overflow-y-auto min-h-0">
            <motion.div
              key={pathname}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
              className="h-full"
            >
              {children}
            </motion.div>
          </main>

          <footer className="border-t border-white/5 backdrop-blur-xl bg-white/[0.02] py-2 px-4 text-center flex-shrink-0">
            <span className="text-xs text-white/30">
              {brand.copyright || '© 2024 szyg'}
            </span>
            {brand.disclaimer && (
              <>
                <span className="text-white/20 mx-1">|</span>
                <button
                  onClick={() => setDisclaimer(true)}
                  className="text-xs text-accent/60 hover:text-accent transition-colors"
                >
                  免责声明
                </button>
              </>
            )}
          </footer>
        </div>
      </div>

      {/* Disclaimer modal */}
      <AnimatePresence>
        {disclaimer && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => setDisclaimer(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-xl rounded-2xl border border-white/10 bg-[var(--header-bg)]/95 backdrop-blur-xl p-6 shadow-2xl"
            >
              <h3 className="text-lg font-semibold text-white mb-4">免责声明</h3>
              <div className="text-sm text-white/60 leading-relaxed whitespace-pre-wrap max-h-[50vh] overflow-y-auto">
                {brand.disclaimer}
              </div>
              <div className="mt-4 flex justify-end">
                <button
                  onClick={() => setDisclaimer(false)}
                  className="px-4 py-2 rounded-lg bg-accent text-white text-sm hover:bg-accent-dark transition-colors"
                >
                  知道了
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/** 折叠状态下的简化导航（只显示图标） */
function CollapsedNav({ pathname }: { pathname: string }) {
  const iconClass = "w-5 h-5"
  const items = [
    { icon: <Sparkles className={iconClass} />, path: '/studio/super-agent', label: 'AI工作室' },
    { icon: <Globe className={iconClass} />, path: '/public/smart-comment', label: '公域获客' },
    { icon: <MessageCircleHeart className={iconClass} />, path: '/private/lead-manager', label: '私域营销' },
    { icon: <BarChart3 className={iconClass} />, path: '/insight/asset-dashboard', label: '数据洞察' },
    { icon: <Wrench className={iconClass} />, path: '/tools/copy-gen', label: '工具箱' },
  ]

  return (
    <div className="space-y-1">
      {items.map((item) => (
        <Link
          key={item.path}
          href={item.path}
          title={item.label}
          className={cn(
            'flex items-center justify-center p-2.5 rounded-xl transition-all duration-200',
            pathname.startsWith(item.path.split('/')[1])
              ? 'bg-white/10 text-accent'
              : 'text-white/40 hover:text-white/70 hover:bg-white/5'
          )}
        >
          {item.icon}
        </Link>
      ))}
    </div>
  )
}
