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
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'

// 占位页面 — AI员工
import AIMarket from './pages/ai-staff/AIMarket'
import AITools from './pages/ai-staff/AITools'
import ComputerUse from './pages/ai-staff/ComputerUse'
// 占位页面 — 内容创作
import ContentProduction from './pages/content/ContentProduction'
import AssetManagement from './pages/content/AssetManagement'
// 占位页面 — 营销获客
import PrivateDomain from './pages/marketing/PrivateDomain'
import Intelligence from './pages/marketing/Intelligence'
import Intercept from './pages/marketing/Intercept'
import Listen from './pages/marketing/Listen'
import Conversion from './pages/marketing/Conversion'
import Customers from './pages/marketing/Customers'
// 占位页面 — 发布管理
import PublishCenter from './pages/publish/PublishCenter'
import Accounts from './pages/publish/Accounts'
import PlatformWorkspace from './pages/publish/PlatformWorkspace'
// 工作流
import AutomationPlans from './pages/workflow/AutomationPlans'
import AutomationRuns from './pages/workflow/AutomationRuns'
// 占位页面 — 数据洞察
import ContentAnalytics from './pages/insights/ContentAnalytics'
import AcquisitionAnalytics from './pages/insights/AcquisitionAnalytics'
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
      <Sidebar />
      <TopBar />
      <main className="pt-16 min-h-[100dvh]" style={{ marginLeft: sidebarWidth }}>{children}</main>
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

      {/* ── 标准 Layout 路由（Sidebar + TopBar + Content + Footer）── */}
      <Route element={<Layout />}>
        {/* AI员工 */}
        <Route path="/ai-staff/market" element={<AIMarket />} />
        <Route path="/ai-staff/tools" element={<AITools />} />
        <Route path="/ai-staff/computer-use" element={<ComputerUse />} />
        <Route path="/ai-staff/tasks" element={<Navigate to="/publish/center" replace />} />

        {/* 内容创作 */}
        <Route path="/content/production" element={<ContentProduction />} />
        <Route path="/content/assets" element={<AssetManagement />} />

        {/* 营销获客 */}
        <Route path="/marketing/private-domain" element={<PrivateDomain />} />
        <Route path="/marketing/intelligence" element={<Intelligence />} />
        <Route path="/marketing/intercept" element={<Intercept />} />
        <Route path="/marketing/listen" element={<Listen />} />
        <Route path="/marketing/conversion" element={<Conversion />} />
        <Route path="/marketing/customers" element={<Customers />} />

        {/* 发布管理 */}
        <Route path="/publish/center" element={<PublishCenter />} />
        <Route path="/publish/accounts" element={<Accounts />} />
        <Route path="/publish/calendar" element={<Navigate to="/publish/center" replace />} />
        <Route path="/publish/workspace" element={<PlatformWorkspace />} />

        {/* 工作流 */}
        <Route path="/automation/plans" element={<AutomationPlans />} />
        <Route path="/automation/runs" element={<AutomationRuns />} />
        <Route path="/workflow/pipeline" element={<Navigate to="/automation/plans" replace />} />
        <Route path="/workflow/scheduler" element={<Navigate to="/automation/runs" replace />} />
        <Route path="/workflow/sop" element={<Navigate to="/automation/plans?view=standards" replace />} />

        {/* 数据洞察 */}
        <Route path="/insights/dashboard" element={<Dashboard />} />
        <Route path="/insights/content-analytics" element={<ContentAnalytics />} />
        <Route path="/insights/acquisition-analytics" element={<AcquisitionAnalytics />} />

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
      {[...slots.entries()].map(([key, slotLocation]) => {
        const active = key === slotKey
        return (
          <div
            key={key}
            // 页面保活：隐藏页面保持挂载，但必须彻底不可见且不拦截事件，
            // 否则其内部的 fixed 元素（TopBar/Sidebar/头像弹窗 portal）会遮挡当前页面，
            // 导致点击头像后弹窗看不到/点不到。
            style={{
              display: active ? undefined : 'none',
              visibility: active ? undefined : 'hidden',
              pointerEvents: active ? undefined : 'none',
            }}
            aria-hidden={!active}
          >
            <AppRoutes location={slotLocation} />
          </div>
        )
      })}
    </CloudAuthGate>
  )
}
