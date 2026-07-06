import type { ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router'
import Layout from './components/Layout'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import { legacyRedirects } from './lib/navConfig'
import { useLayout } from './lib/layout'

// 已实现的真实页面
import SuperAgent from './pages/SuperAgent'
import Dashboard from './pages/Dashboard'
import DigitalHuman from './pages/DigitalHuman'
import Settings from './pages/Settings'

// 占位页面 — AI员工
import AIVideo from './pages/ai-staff/AIVideo'
import AIMarket from './pages/ai-staff/AIMarket'
import TaskBoard from './pages/ai-staff/TaskBoard'
// 占位页面 — 内容创作
import ContentProduction from './pages/content/ContentProduction'
import AssetManagement from './pages/content/AssetManagement'
// 占位页面 — 营销获客
import Intercept from './pages/marketing/Intercept'
import Listen from './pages/marketing/Listen'
import Conversion from './pages/marketing/Conversion'
import Customers from './pages/marketing/Customers'
// 占位页面 — 发布管理
import PublishCenter from './pages/publish/PublishCenter'
import Accounts from './pages/publish/Accounts'
import ContentCalendar from './pages/publish/ContentCalendar'
// 占位页面 — 工作流
import Pipeline from './pages/workflow/Pipeline'
import Scheduler from './pages/workflow/Scheduler'
import Sop from './pages/workflow/Sop'
// 占位页面 — 数据洞察
import ContentAnalytics from './pages/insights/ContentAnalytics'
import AcquisitionAnalytics from './pages/insights/AcquisitionAnalytics'
// 占位页面 — 知识库
import KnowledgeBase from './pages/knowledge/KnowledgeBase'
import Memory from './pages/knowledge/Memory'
import Skills from './pages/knowledge/Skills'
import Academy from './pages/knowledge/Academy'
// 占位页面 — 系统设置
import RiskControl from './pages/settings/RiskControl'
import Tools from './pages/settings/Tools'
import Brand from './pages/settings/Brand'
import Team from './pages/settings/Team'
import Billing from './pages/settings/Billing'

// === LAYOUT WRAPPERS ===

// Full-bleed layout for Super Agent chat (no content padding / footer)
function FullBleedLayout({ children }: { children: ReactNode }) {
  const { sidebarWidth } = useLayout()
  return (
    <div className="min-h-[100dvh] bg-[#0B0F1A]">
      <Sidebar />
      <TopBar />
      <main className="pt-16 min-h-[100dvh]" style={{ marginLeft: sidebarWidth }}>{children}</main>
    </div>
  )
}

// 404 页面 — 未匹配路由的兜底
function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6">
      <div className="text-display-xl text-[#1E293B] font-bold mb-4">404</div>
      <h1 className="text-heading-lg text-[#F1F5F9] mb-2">页面未找到</h1>
      <p className="text-body-md text-[#64748B] mb-6">您访问的页面不存在或已被移动</p>
      <a
        href="/"
        className="px-4 py-2 rounded-button bg-[#6366F1] text-white text-sm font-medium hover:bg-[#818CF8] transition-colors"
      >
        返回超级员工
      </a>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      {/* ── 超级员工：full-bleed 布局（系统默认首页）── */}
      <Route
        path="/"
        element={
          <FullBleedLayout>
            <SuperAgent />
          </FullBleedLayout>
        }
      />

      {/* ── 标准 Layout 路由（Sidebar + TopBar + Content + Footer）── */}
      <Route element={<Layout />}>
        {/* AI员工 */}
        <Route path="/ai-staff/video" element={<AIVideo />} />
        <Route path="/ai-staff/market" element={<AIMarket />} />
        <Route path="/ai-staff/tasks" element={<TaskBoard />} />

        {/* 内容创作 */}
        <Route path="/content/production" element={<ContentProduction />} />
        <Route path="/content/assets" element={<AssetManagement />} />
        <Route path="/content/digital-human" element={<DigitalHuman />} />

        {/* 营销获客 */}
        <Route path="/marketing/intercept" element={<Intercept />} />
        <Route path="/marketing/listen" element={<Listen />} />
        <Route path="/marketing/conversion" element={<Conversion />} />
        <Route path="/marketing/customers" element={<Customers />} />

        {/* 发布管理 */}
        <Route path="/publish/center" element={<PublishCenter />} />
        <Route path="/publish/accounts" element={<Accounts />} />
        <Route path="/publish/calendar" element={<ContentCalendar />} />

        {/* 工作流 */}
        <Route path="/workflow/pipeline" element={<Pipeline />} />
        <Route path="/workflow/scheduler" element={<Scheduler />} />
        <Route path="/workflow/sop" element={<Sop />} />

        {/* 数据洞察 */}
        <Route path="/insights/dashboard" element={<Dashboard />} />
        <Route path="/insights/content-analytics" element={<ContentAnalytics />} />
        <Route path="/insights/acquisition-analytics" element={<AcquisitionAnalytics />} />

        {/* 知识库 */}
        <Route path="/knowledge/base" element={<KnowledgeBase />} />
        <Route path="/knowledge/memory" element={<Memory />} />
        <Route path="/knowledge/skills" element={<Skills />} />
        <Route path="/knowledge/academy" element={<Academy />} />

        {/* 系统设置 */}
        <Route path="/settings" element={<Settings />} />
        <Route path="/settings/risk-control" element={<RiskControl />} />
        <Route path="/settings/tools" element={<Tools />} />
        <Route path="/settings/brand" element={<Brand />} />
        <Route path="/settings/team" element={<Team />} />
        <Route path="/settings/billing" element={<Billing />} />

        {/* 404 兜底 */}
        <Route path="*" element={<NotFound />} />
      </Route>

      {/* ── 向后兼容重定向（45条）── */}
      {legacyRedirects.map((r) => (
        <Route key={r.from} path={r.from} element={<Navigate to={r.to} replace />} />
      ))}
    </Routes>
  )
}

