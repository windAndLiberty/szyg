import { Outlet } from 'react-router'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Footer from './Footer'

export default function Layout() {
  return (
    <div className="min-h-[100dvh] bg-[#0B0F1A]">
      <Sidebar />
      <TopBar />
      <main className="ml-[260px] pt-16 min-h-[100dvh] flex flex-col">
        <div className="flex-1 p-8">
          <Outlet />
        </div>
        <Footer />
      </main>
    </div>
  )
}
