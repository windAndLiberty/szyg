import { useEffect, useRef, type ReactNode } from 'react'
import { Routes, Route, Navigate, useLocation, type Location } from 'react-router'
import Layout from './components/Layout'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import { legacyRedirects } from './lib/navConfig'
import { useLayout } from './lib/layout'
import { useI18n } from './lib/i18n'
import CloudAuthGate from './components/CloudAuthGate'

// 已实现的真实页面
import SuperAgent from './pages/SuperAgent'
import Settings from './pages/Settings'

// 占位页面 — AI员工
import AIMarket from './pages/ai-staff/AIMarket'
import AITools from './pages/ai-staff/AITools'
// 占位页面 — 内容创作
import ContentProduction from './pages/content/ContentProduction'
import AssetManagement from './pages/content/AssetManagement'
import DigitalHumanStudio from './pages/content/DigitalHumanStudio'
// 占位页面 — 营销获客
import MarketingWorkbench from './pages/marketing/MarketingWorkbench'
import Opportunities from './pages/marketing/Opportunities'
import CustomerCenter from './pages/marketing/CustomerCenter'
import GeoWorkbench from './pages/geo/GeoWorkbench'
import GeoMonitoring from './pages/geo/GeoMonitoring'
import GeoOptimization from './pages/geo/GeoOptimization'
// 占位页面 — 发布管理
import PublishCenter from './pages/publish/PublishCenter'
import Accounts from './pages/publish/Accounts'
import PlatformWorkspace from './pages/publish/PlatformWorkspace'
// 工作流
import AutomationTasks from './pages/workflow/AutomationTasks'
import AutomationApprovals from './pages/workflow/AutomationApprovals'
import AutomationHistory from './pages/workflow/AutomationHistory'
// 占位页面 — 数据洞察
// 占位页面 — 知识库
import KnowledgeBase from './pages/knowledge/KnowledgeBase'
import Skills from './pages/knowledge/Skills'
import Academy from './pages/knowledge/Academy'
// 占位页面 — 系统设置
import Brand from './pages/settings/Brand'
import Team from './pages/settings/Team'
import Billing from './pages/settings/Billing'

// === LAYOUT WRAPPERS ===

// Full-bleed layout for Super Agent chat (no content padding / footer)
function FullBleedLayout({ children }: { children: ReactNode }) {
  const { sidebarWidth } = useLayout()
  return (
    <div className="min-h-[100dvh] bg-[#0B0F1A]">
      <main className="pt-16 min-h-[100dvh] transition-[margin-left] duration-150 ease-out" style={{ marginLeft: sidebarWidth }}>{children}</main>
    </div>
  )
}

// 404 页面 — 未匹配路由的兜底
function NotFound() {
  const { t } = useI18n()
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6">
      <div className="text-display-xl text-[#1E293B] font-bold mb-4">404</div>
      <h1 className="text-heading-lg text-[#F1F5F9] mb-2">{t('页面未找到')}</h1>
      <p className="text-body-md text-[#64748B] mb-6">{t('您访问的页面不存在或已被移动')}</p>
      <a
        href="/"
        className="px-4 py-2 rounded-button bg-[#6366F1] text-white text-sm font-medium hover:bg-[#818CF8] transition-colors"
      >
        {t('返回超级员工')}
      </a>
    </div>
  )
}

// 页面保活:已访问页面保持挂载(隐藏而非卸载),返回时原样恢复工作现场
// (聊天消息、浏览器工作台、表单输入、滚动位置等)。仅保留最近 MAX 个页面。
const MAX_KEEP_ALIVE_PAGES = 20

function AppRoutes({ location }: { location: Location }) {
  return (
    <Routes location={location}>
      {/* ── 超级员工：full-bleed 布局（系统默认首页）── */}
      <Route
        path="/"
        element={
          <FullBleedLayout>
            <SuperAgent />
          </FullBleedLayout>
        }
      />

      {/* ── 标准内容路由（全局 Sidebar/TopBar 在保活容器之外，仅挂载一次）── */}
      <Route element={<Layout />}>
        {/* AI员工 */}
        <Route path="/ai-staff/market" element={<AIMarket />} />
        <Route path="/ai-staff/tools" element={<AITools />} />
        <Route path="/ai-staff/tasks" element={<Navigate to="/publish/center" replace />} />

        {/* 内容创作 */}
        <Route path="/content/production" element={<ContentProduction />} />
        <Route path="/content/digital-human" element={<DigitalHumanStudio />} />
        <Route path="/content/assets" element={<AssetManagement />} />

        {/* 营销获客 */}
        <Route path="/marketing/workbench" element={<MarketingWorkbench />} />
        <Route path="/marketing/opportunities" element={<Opportunities />} />
        <Route path="/marketing/customers" element={<CustomerCenter />} />
        <Route path="/marketing/private-domain" element={<Navigate to="/marketing/customers?stage=followup" replace />} />
        <Route path="/marketing/intelligence" element={<Navigate to="/marketing/opportunities" replace />} />
        <Route path="/marketing/intercept" element={<Navigate to="/marketing/opportunities" replace />} />
        <Route path="/marketing/listen" element={<Navigate to="/marketing/opportunities?view=monitoring" replace />} />
        <Route path="/marketing/conversion" element={<Navigate to="/marketing/customers" replace />} />

        {/* GEO品牌增长 */}
        <Route path="/geo/workbench" element={<GeoWorkbench />} />
        <Route path="/geo/monitoring" element={<GeoMonitoring />} />
        <Route path="/geo/optimization" element={<GeoOptimization />} />

        {/* 发布管理 */}
        <Route path="/publish/center" element={<PublishCenter />} />
        <Route path="/publish/accounts" element={<Accounts />} />
        <Route path="/publish/calendar" element={<Navigate to="/publish/center" replace />} />
        <Route path="/publish/workspace" element={<PlatformWorkspace />} />

        {/* 工作流 */}
        <Route path="/automation/tasks" element={<AutomationTasks />} />
        <Route path="/automation/approvals" element={<AutomationApprovals />} />
        <Route path="/automation/runs" element={<AutomationHistory />} />
        <Route path="/automation/plans" element={<Navigate to="/automation/tasks" replace />} />
        <Route path="/workflow/pipeline" element={<Navigate to="/automation/tasks" replace />} />
        <Route path="/workflow/scheduler" element={<Navigate to="/automation/runs" replace />} />
        <Route path="/workflow/sop" element={<Navigate to="/automation/tasks" replace />} />

        {/* 数据洞察 */}
        <Route path="/insights/dashboard" element={<Navigate to="/marketing/workbench" replace />} />
        <Route path="/insights/content-analytics" element={<Navigate to="/content/production?view=performance" replace />} />
        <Route path="/insights/acquisition-analytics" element={<Navigate to="/marketing/workbench" replace />} />

        {/* 知识库 */}
        <Route path="/knowledge/base" element={<KnowledgeBase />} />
        <Route path="/knowledge/skills" element={<Skills />} />
        <Route path="/knowledge/academy" element={<Academy />} />

        {/* 系统设置 */}
        <Route path="/settings" element={<Settings />} />
        <Route path="/settings/risk-control" element={<Navigate to="/settings" replace />} />
        <Route path="/settings/tools" element={<Navigate to="/knowledge/skills" replace />} />
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

export default function App() {
  const location = useLocation()
  const slotsRef = useRef<Map<string, Location>>(new Map())
  const slotKey = location.pathname + location.search
  const slots = slotsRef.current
  slots.set(slotKey, location)
  if (slots.size > MAX_KEEP_ALIVE_PAGES) {
    let excess = slots.size - MAX_KEEP_ALIVE_PAGES
    for (const key of slots.keys()) {
      if (key === slotKey) continue
      slots.delete(key)
      excess -= 1
      if (excess <= 0) break
    }
  }

  // 通知隐藏中的页面(如超级员工浏览器工作台)让出原生窗口,避免遮挡/黑屏
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('szyg:keep-alive-active-changed', { detail: { path: slotKey } }))
  }, [slotKey])

  return (
    <CloudAuthGate>
      <Sidebar />
      <TopBar />
      {[...slots.entries()].map(([key, slotLocation]) => {
        const active = key === slotKey
        return <div key={key} style={{ display: active ? undefined : 'none' }} aria-hidden={!active}><AppRoutes location={slotLocation} /></div>
      })}
    </CloudAuthGate>
  )
}
