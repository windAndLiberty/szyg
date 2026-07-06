import { Outlet } from 'react-router'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Footer from './Footer'
import { useLayout } from '@/lib/layout'

export default function Layout() {
  const { sidebarWidth } = useLayout()
  return (
    <div className="min-h-[100dvh] bg-[#0B0F1A]">
      <Sidebar />
      <TopBar />
      <main className="pt-16 min-h-[100dvh] flex flex-col" style={{ marginLeft: sidebarWidth }}>
        <div className="flex-1 p-8 flex flex-col min-h-0">
          <Outlet />
        </div>
        <Footer />
      </main>
    </div>
  )
}
