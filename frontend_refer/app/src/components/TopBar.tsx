import { useState } from 'react'
import { useLocation } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  Bell,
  ChevronDown,
  LogOut,
  User,
} from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/input': '快速录入',
  '/processing': 'AI 处理',
  '/reports': '报告',
  '/pipeline': 'Pipeline',
  '/customers': '客户',
  '/settings': '设置',
}

export default function TopBar() {
  const location = useLocation()
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')

  const pageTitle = pageTitles[location.pathname] || 'DealFlow'

  return (
    <header className="fixed top-0 right-0 left-0 h-16 bg-[#111827]/95 backdrop-blur-md border-b border-[#1E293B] z-30">
      <div className="h-full flex items-center justify-between px-6 ml-[260px]">
        {/* Left: Page Title */}
        <motion.h1
          key={pageTitle}
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
          className="text-heading-sm text-[#F1F5F9]"
        >
          {pageTitle}
        </motion.h1>

        {/* Center: Search */}
        <div className="flex-1 max-w-md mx-8">
          <AnimatePresence>
            {searchOpen ? (
              <motion.div
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
                  placeholder="Search deals, customers, reports..."
                  className="w-full h-10 pl-10 pr-4 rounded-input bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] placeholder-[#64748B] focus:outline-none focus:border-[#334155] transition-colors"
                />
              </motion.div>
            ) : (
              <motion.button
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                onClick={() => setSearchOpen(true)}
                className="flex items-center gap-2 h-10 px-3 rounded-input bg-[#0D1321] border border-[#1E293B] text-[#64748B] hover:text-[#94A3B8] hover:border-[#334155] transition-colors"
              >
                <Search className="w-4 h-4" />
                <span className="text-sm">Search...</span>
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
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors">
                <Avatar className="w-8 h-8">
                  <AvatarFallback className="bg-[#6366F1] text-white text-xs font-medium">
                    ZW
                  </AvatarFallback>
                </Avatar>
                <ChevronDown className="w-4 h-4 text-[#64748B]" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-48 bg-[#1A2235] border-[#1E293B] text-[#F1F5F9]"
            >
              <div className="px-3 py-2 border-b border-[#1E293B]">
                <p className="text-sm font-medium">Zhang Wei</p>
                <p className="text-xs text-[#64748B]">zhang.wei@dealflow.com</p>
              </div>
              <DropdownMenuItem className="text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)] cursor-pointer">
                <User className="w-4 h-4 mr-2" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-[#1E293B]" />
              <DropdownMenuItem className="text-[#EF4444] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.05)] cursor-pointer">
                <LogOut className="w-4 h-4 mr-2" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
