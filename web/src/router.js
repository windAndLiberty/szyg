import { createRouter, createWebHistory } from 'vue-router'
// Static imports: login + layout (always needed on first load)
import Login from './pages/Login.vue'
import AppLayout from './components/AppLayout.vue'

// ═══════════════════════════════════════════════════════════════
// Lazy imports: every page split into its own chunk
// ═══════════════════════════════════════════════════════════════

// ── Section Shells ──
const AiStaffShell      = () => import('./pages/AiStaff.vue')
const ContentShell      = () => import('./pages/ContentShell.vue')
const MarketingShell    = () => import('./pages/MarketingShell.vue')
const WorkflowShell     = () => import('./pages/WorkflowShell.vue')
const InsightsShell     = () => import('./pages/InsightsShell.vue')
const KnowledgeShell    = () => import('./pages/KnowledgeShell.vue')
const Settings          = () => import('./pages/Settings.vue')

// ── Existing Pages ──
const Dashboard           = () => import('./pages/Dashboard.vue')
const StaffOverview       = () => import('./pages/StaffOverview.vue')
const TaskBoard           = () => import('./pages/TaskBoard.vue')
const AgentProfiles       = () => import('./pages/AgentProfiles.vue')
const ContentStudio       = () => import('./pages/ContentStudio.vue')
const ContentAssets       = () => import('./pages/ContentAssets.vue')
const AcquisitionStudio   = () => import('./pages/AcquisitionStudio.vue')
const ConversionStudio    = () => import('./pages/ConversionStudio.vue')
const CustomerAssets      = () => import('./pages/CustomerAssets.vue')
const SettingsPlatforms   = () => import('./pages/SettingsPlatforms.vue')
const SettingsSkills      = () => import('./pages/SettingsSkills.vue')
const SettingsTools       = () => import('./pages/SettingsTools.vue')
const SettingsSystem      = () => import('./pages/SettingsSystem.vue')
const SettingsBrand       = () => import('./pages/SettingsBrand.vue')
const SettingsTeam        = () => import('./pages/SettingsTeam.vue')

// ── New Pages ──
const SuperAgent             = () => import('./pages/SuperAgent.vue')
const VideoEditor            = () => import('./pages/VideoEditor.vue')
const DigitalHuman           = () => import('./pages/DigitalHuman.vue')
const PublishCenter          = () => import('./pages/PublishCenter.vue')
const ListenCenter           = () => import('./pages/ListenCenter.vue')
const ABTestCenter           = () => import('./pages/ABTestCenter.vue')
const EnterpriseAcquisition  = () => import('./pages/EnterpriseAcquisition.vue')
const NfcMarketing           = () => import('./pages/NfcMarketing.vue')
const PipelineDesigner       = () => import('./pages/PipelineDesigner.vue')
const SchedulerEngine        = () => import('./pages/SchedulerEngine.vue')
const SOPManager             = () => import('./pages/SOPManager.vue')
const ContentAnalytics       = () => import('./pages/ContentAnalytics.vue')
const AcquisitionAnalytics   = () => import('./pages/AcquisitionAnalytics.vue')
const ConversionAnalytics    = () => import('./pages/ConversionAnalytics.vue')
const KnowledgeBase          = () => import('./pages/KnowledgeBase.vue')
const MemoryCenter           = () => import('./pages/MemoryCenter.vue')
const Academy                = () => import('./pages/Academy.vue')
const SettingsRiskControl    = () => import('./pages/SettingsRiskControl.vue')
const SettingsBilling        = () => import('./pages/SettingsBilling.vue')

// ═══════════════════════════════════════════════════════════════
// Route tree — 7 Sections + Backward-Compatible Redirects
// ═══════════════════════════════════════════════════════════════
const routes = [
  { path: '/login', component: Login },
  {
    path: '/',
    component: AppLayout,
    children: [
      // Default → Dashboard
      { path: '', redirect: '/insights/dashboard' },

      // ══════════════════════════════════════════════════════════
      // 🤖 AI员工
      // ══════════════════════════════════════════════════════════
      {
        path: 'ai-staff',
        component: AiStaffShell,
        redirect: '/ai-staff/super-agent',
        meta: { requiresAuth: true, section: 'ai-staff', title: 'AI员工' },
        children: [
          { path: 'super-agent',  component: SuperAgent,     meta: { requiresAuth: true, section: 'ai-staff', title: '超级员工' } },
          { path: 'overview',     component: StaffOverview,  meta: { requiresAuth: true, section: 'ai-staff', title: '员工概览' } },
          { path: 'tasks',        component: TaskBoard,      meta: { requiresAuth: true, section: 'ai-staff', title: '任务看板' } },
          { path: 'profiles',     component: AgentProfiles,  meta: { requiresAuth: true, section: 'ai-staff', title: '员工配置' } },
        ],
      },

      // ══════════════════════════════════════════════════════════
      // 📦 内容工厂
      // ══════════════════════════════════════════════════════════
      {
        path: 'content',
        component: ContentShell,
        redirect: '/content/production',
        meta: { requiresAuth: true, section: 'content', title: '内容工厂' },
        children: [
          { path: 'production',    component: ContentStudio,  meta: { requiresAuth: true, section: 'content', title: '内容生产' } },
          { path: 'video-editor',  component: VideoEditor,    meta: { requiresAuth: true, section: 'content', title: '视频剪辑' } },
          { path: 'digital-human', component: DigitalHuman,   meta: { requiresAuth: true, section: 'content', title: '数字人' } },
          { path: 'assets',        component: ContentAssets,   meta: { requiresAuth: true, section: 'content', title: '内容资产' } },
          { path: 'publish',       component: PublishCenter,   meta: { requiresAuth: true, section: 'content', title: '多平台发布' } },
        ],
      },

      // ══════════════════════════════════════════════════════════
      // 🎯 营销拓客
      // ══════════════════════════════════════════════════════════
      {
        path: 'marketing',
        component: MarketingShell,
        redirect: '/marketing/intercept',
        meta: { requiresAuth: true, section: 'marketing', title: '营销拓客' },
        children: [
          { path: 'intercept',   component: AcquisitionStudio,      meta: { requiresAuth: true, section: 'marketing', title: '智能截流' } },
          { path: 'listen',      component: ListenCenter,           meta: { requiresAuth: true, section: 'marketing', title: '舆情监听' } },
          { path: 'conversion',  component: ConversionStudio,       meta: { requiresAuth: true, section: 'marketing', title: '客户转化' } },
          { path: 'ab-test',     component: ABTestCenter,           meta: { requiresAuth: true, section: 'marketing', title: 'A/B测试' } },
          { path: 'customers',   component: CustomerAssets,         meta: { requiresAuth: true, section: 'marketing', title: '客户资产' } },
          { path: 'enterprise',  component: EnterpriseAcquisition,  meta: { requiresAuth: true, section: 'marketing', title: '企业获客' } },
          { path: 'nfc',         component: NfcMarketing,           meta: { requiresAuth: true, section: 'marketing', title: '到店引流' } },
        ],
      },

      // ══════════════════════════════════════════════════════════
      // ⚙️ 工作流编排
      // ══════════════════════════════════════════════════════════
      {
        path: 'workflow',
        component: WorkflowShell,
        redirect: '/workflow/pipeline',
        meta: { requiresAuth: true, section: 'workflow', title: '工作流编排' },
        children: [
          { path: 'pipeline',   component: PipelineDesigner,  meta: { requiresAuth: true, section: 'workflow', title: '流水线编排' } },
          { path: 'scheduler',  component: SchedulerEngine,   meta: { requiresAuth: true, section: 'workflow', title: '调度引擎' } },
          { path: 'sop',        component: SOPManager,         meta: { requiresAuth: true, section: 'workflow', title: 'SOP管理' } },
        ],
      },

      // ══════════════════════════════════════════════════════════
      // � 数据洞察
      // ══════════════════════════════════════════════════════════
      {
        path: 'insights',
        component: InsightsShell,
        redirect: '/insights/dashboard',
        meta: { requiresAuth: true, section: 'insights', title: '数据洞察' },
        children: [
          { path: 'dashboard',             component: Dashboard,             meta: { requiresAuth: true, section: 'insights', title: '运营仪表盘' } },
          { path: 'content-analytics',     component: ContentAnalytics,      meta: { requiresAuth: true, section: 'insights', title: '内容分析' } },
          { path: 'acquisition-analytics', component: AcquisitionAnalytics,  meta: { requiresAuth: true, section: 'insights', title: '截流效果' } },
          { path: 'conversion-analytics',  component: ConversionAnalytics,   meta: { requiresAuth: true, section: 'insights', title: '转化分析' } },
        ],
      },

      // ══════════════════════════════════════════════════════════
      // � 知识库
      // ══════════════════════════════════════════════════════════
      {
        path: 'knowledge',
        component: KnowledgeShell,
        redirect: '/knowledge/base',
        meta: { requiresAuth: true, section: 'knowledge', title: '知识库' },
        children: [
          { path: 'base',    component: KnowledgeBase,    meta: { requiresAuth: true, section: 'knowledge', title: '知识管理' } },
          { path: 'memory',  component: MemoryCenter,     meta: { requiresAuth: true, section: 'knowledge', title: '长期记忆' } },
          { path: 'skills',  component: SettingsSkills,   meta: { requiresAuth: true, section: 'knowledge', title: '技能市场' } },
          { path: 'academy', component: Academy,          meta: { requiresAuth: true, section: 'knowledge', title: '商学院' } },
        ],
      },

      // ══════════════════════════════════════════════════════════
      // ⚙️ 系统设置
      // ══════════════════════════════════════════════════════════
      {
        path: 'settings',
        component: Settings,
        redirect: '/settings/platforms',
        meta: { requiresAuth: true, section: 'settings', title: '系统设置' },
        children: [
          { path: 'platforms',     component: SettingsPlatforms,   meta: { requiresAuth: true, section: 'settings', title: '平台账号' } },
          { path: 'risk-control',  component: SettingsRiskControl, meta: { requiresAuth: true, section: 'settings', title: '风控策略' } },
          { path: 'tools',         component: SettingsTools,       meta: { requiresAuth: true, section: 'settings', title: '工具管理' } },
          { path: 'system',        component: SettingsSystem,      meta: { requiresAuth: true, section: 'settings', title: '系统配置' } },
          { path: 'brand',         component: SettingsBrand,       meta: { requiresAuth: true, requiresAdmin: true, section: 'settings', title: '品牌配置' } },
          { path: 'team',          component: SettingsTeam,        meta: { requiresAuth: true, requiresAdmin: true, section: 'settings', title: '团队管理' } },
          { path: 'billing',       component: SettingsBilling,     meta: { requiresAuth: true, requiresAdmin: true, section: 'settings', title: '计费管理' } },
        ],
      },

      // ══════════════════════════════════════════════════════════
      // Backward-Compatible Redirects: old paths → new routes
      // ══════════════════════════════════════════════════════════

      // Old dashboard
      { path: 'dashboard',  redirect: '/insights/dashboard' },

      // Gen 1: old standalone routes → new section paths
      { path: 'chat',            redirect: { path: '/', query: { panel: 'open' } } },
      { path: 'chat-legacy',     redirect: { path: '/', query: { panel: 'open' } } },
      { path: 'image',           redirect: '/content/production' },
      { path: 'video',           redirect: '/content/production' },
      { path: 'agents',          redirect: '/ai-staff/overview' },
      { path: 'agents/:id',      redirect: '/ai-staff/profiles' },
      { path: 'skills',          redirect: '/knowledge/skills' },
      { path: 'hub',             redirect: '/content/production' },
      { path: 'publisher',       redirect: '/content/publish' },
      { path: 'publish',         redirect: '/content/publish' },
      { path: 'calendar',        redirect: '/workflow/scheduler' },
      { path: 'scheduler',       redirect: '/workflow/scheduler' },
      { path: 'video-edit',      redirect: '/content/video-editor' },
      { path: 'documents',       redirect: '/content/production' },
      { path: 'intercept',       redirect: '/marketing/intercept' },
      { path: 'search',          redirect: '/marketing/intercept' },
      { path: 'comments',        redirect: '/marketing/intercept' },
      { path: 'monitor',         redirect: '/marketing/listen' },
      { path: 'ab-test',         redirect: '/marketing/ab-test' },
      { path: 'auto-reply',      redirect: '/marketing/conversion' },
      { path: 'dm',              redirect: '/marketing/conversion' },
      { path: 'leads',           redirect: '/marketing/customers' },
      { path: 'wechat',          redirect: '/marketing/conversion' },
      { path: 'knowledge',       redirect: '/knowledge/base' },
      { path: 'sop',             redirect: '/workflow/sop' },
      { path: 'history',         redirect: '/workflow/scheduler' },
      { path: 'strategy',        redirect: '/marketing/ab-test' },
      { path: 'ab-results',      redirect: '/marketing/ab-test' },
      { path: 'platforms/:platform?', redirect: '/settings/platforms' },
      { path: 'platforms-admin', redirect: '/settings/platforms' },
      { path: 'tools',           redirect: '/settings/tools' },
      { path: 'tools/:category', redirect: '/settings/tools' },
      { path: 'oem',             redirect: '/settings/brand' },
      { path: 'admin',           redirect: '/settings/team' },
      { path: 'acquisition',            redirect: '/marketing/intercept' },
      { path: 'acquisition/search',     redirect: '/marketing/intercept' },
      { path: 'acquisition/comments',   redirect: '/marketing/intercept' },

      // Gen 2: old /assets and /crm → new paths
      { path: 'assets',          redirect: '/content/assets' },
      { path: 'crm',             redirect: '/marketing/customers' },

      // Gen 3: interim 5-department paths
      { path: 'creative-studio',            redirect: '/content/production' },
      { path: 'creative-studio/:path(.*)',  redirect: '/content/production' },
      { path: 'growth-engine',              redirect: '/marketing/intercept' },
      { path: 'growth-engine/:path(.*)',    redirect: '/marketing/intercept' },

      // Gen 4: old /infra/* paths
      { path: 'infra',              redirect: '/settings/platforms' },
      { path: 'infra/:path(.*)',    redirect: '/settings/platforms' },

      // Gen 5: old ai-staff sub-routes → new paths
      { path: 'ai-staff/content-studio',     redirect: '/content/production' },
      { path: 'ai-staff/acquisition-studio', redirect: '/marketing/intercept' },
      { path: 'ai-staff/conversion-studio',  redirect: '/marketing/conversion' },
      { path: 'ai-staff/ops-studio',         redirect: '/workflow/scheduler' },

      // Wildcard: catch any unmatched old section paths → new routes
      { path: 'pipeline/:path(.*)',        redirect: '/workflow/pipeline' },
      { path: 'capture/:path(.*)',         redirect: '/marketing/intercept' },
      { path: 'conversion/:path(.*)',      redirect: '/marketing/conversion' },
      { path: 'security-matrix/:path(.*)', redirect: '/settings/platforms' },
      { path: 'acquisition/:path(.*)',     redirect: '/marketing/intercept' },
    ],
  },
]

// ═══════════════════════════════════════════════════════════════
// Router factory
// ═══════════════════════════════════════════════════════════════
const router = createRouter({ history: createWebHistory(), routes })

// ═══════════════════════════════════════════════════════════════
// JWT Auth Guard (unchanged)
// ═══════════════════════════════════════════════════════════════
router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || 'null')

  if (to.meta.requiresAuth && !token) {
    return next('/login')
  }
  if (to.meta.requiresAdmin && user?.role !== 'admin') {
    return next('/dashboard')
  }
  next()
})

export default router
