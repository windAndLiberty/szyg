import { Outlet } from 'react-router'
import Footer from './Footer'
import { useLayout } from '@/lib/layout'

export default function Layout() {
  const { sidebarWidth } = useLayout()
  return (
    <div className="min-h-[100dvh] bg-[#0B0F1A]">
      <main className="pt-16 min-h-[100dvh] flex flex-col transition-[margin-left] duration-150 ease-out" style={{ marginLeft: sidebarWidth }}>
        <div className="flex-1 p-8 flex flex-col min-h-0">
          <Outlet />
        </div>
        <Footer />
      </main>
    </div>
  )
}
