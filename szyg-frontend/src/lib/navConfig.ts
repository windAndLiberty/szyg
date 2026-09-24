/**
 * 域灵系统导航配置 — 单一真理源 (Single Source of Truth)
 *
 * 供 Sidebar、TopBar、App 路由共用。结构对齐 module-tree.md 的 9 大一级模块。
 * 图标使用 lucide-react，按 DESIGN_SYSTEM.md 规范（导航图标 20px）。
 */
import {
  Bot,
  BrainCircuit,
  Compass,
  Package,
  PenLine,
  Image as ImageIcon,
  Target,
  SearchCheck,
  ContactRound,
  Users,
  Send,
  KeyRound,
  Workflow,
  ListChecks,
  ShieldCheck,
  Clock,
  TrendingUp,
  Globe2,
  Quote,
  Sparkles,
  BookOpen,
  Database,
  Cpu,
  SlidersHorizontal,
  UserRound,
  CreditCard,
  type LucideIcon,
} from 'lucide-react'

export interface NavChild {
  path: string
  label: string
  icon: LucideIcon
  /** 对应的后端模块标识，便于后续填充时定位 API */
  module?: string
  /** 是否已实现（非占位） */
  implemented?: boolean
}

export interface NavGroup {
  id: string
  label: string
  icon: LucideIcon
  /** 一级路由前缀 */
  basePath: string
  /** 默认子路由（点击一级标题时跳转） */
  defaultChild: string
  children: NavChild[]
}

export const navGroups: NavGroup[] = [
  {
    id: 'ai-staff',
    label: 'nav.aiStaff',
    icon: Bot,
    basePath: '/ai-staff',
    defaultChild: '/',
    children: [
      { path: '/', label: 'nav.superAgent', icon: BrainCircuit, module: 'hermes', implemented: true },
      { path: '/ai-staff/market', label: 'nav.aiTalent', icon: Bot, module: 'agents' },
      { path: '/ai-staff/tools', label: 'nav.aiTools', icon: Compass, module: 'external-tools', implemented: true },
    ],
  },
  {
    id: 'content-publish',
    label: 'nav.content',
    icon: Package,
    basePath: '/content',
    defaultChild: '/content/production',
    children: [
      { path: '/content/production', label: 'nav.contentStudio', icon: PenLine, module: 'content-generation', implemented: true },
      { path: '/content/digital-human', label: 'nav.digitalHuman', icon: UserRound, module: 'digital-human', implemented: true },
      { path: '/content/assets', label: 'nav.assets', icon: ImageIcon, module: 'materials' },
      { path: '/publish/accounts', label: 'nav.channelAccounts', icon: KeyRound, module: 'platforms' },
      { path: '/publish/center', label: 'nav.publishBoard', icon: Send, module: 'publisher' },
    ],
  },
  {
    id: 'marketing',
    label: 'nav.marketing',
    icon: Target,
    basePath: '/marketing',
    defaultChild: '/marketing/workbench',
    children: [
      { path: '/marketing/workbench', label: 'nav.marketingWorkbench', icon: TrendingUp, module: 'marketing-workbench', implemented: true },
      { path: '/marketing/opportunities', label: 'nav.opportunities', icon: SearchCheck, module: 'marketing-opportunities', implemented: true },
      { path: '/marketing/customers', label: 'nav.customers', icon: ContactRound, module: 'customers', implemented: true },
    ],
  },
  {
    id: 'geo',
    label: 'nav.geo',
    icon: Globe2,
    basePath: '/geo',
    defaultChild: '/geo/workbench',
    children: [
      { path: '/geo/workbench', label: 'nav.geoWorkbench', icon: TrendingUp, module: 'geo-workbench', implemented: true },
      { path: '/geo/monitoring', label: 'nav.geoMonitoring', icon: Quote, module: 'geo-monitoring', implemented: true },
      { path: '/geo/optimization', label: 'nav.geoOptimization', icon: Sparkles, module: 'geo-optimization', implemented: true },
    ],
  },
  {
    id: 'automation',
    label: 'nav.automation',
    icon: Workflow,
    basePath: '/automation',
    defaultChild: '/automation/tasks',
    children: [
      { path: '/automation/tasks', label: 'nav.automationTasks', icon: ListChecks, module: 'automation-tasks', implemented: true },
      { path: '/automation/approvals', label: 'nav.approvals', icon: ShieldCheck, module: 'automation-approvals', implemented: true },
      { path: '/automation/runs', label: 'nav.runs', icon: Clock, module: 'automation-runs', implemented: true },
    ],
  },
  {
    id: 'knowledge',
    label: 'nav.knowledge',
    icon: BookOpen,
    basePath: '/knowledge',
    defaultChild: '/knowledge/base',
    children: [
      { path: '/knowledge/base', label: 'nav.knowledgeManagement', icon: Database, module: 'knowledge' },
      { path: '/knowledge/skills', label: 'nav.skills', icon: Cpu, module: 'skills' },
    ],
  },
  {
    id: 'settings',
    label: 'nav.settings',
    icon: SlidersHorizontal,
    basePath: '/settings',
    defaultChild: '/settings',
    children: [
      { path: '/settings', label: 'nav.systemSettings', icon: SlidersHorizontal, module: 'config', implemented: true },
      { path: '/settings/billing', label: 'nav.billing', icon: CreditCard, module: 'billing' },
    ],
  },
]

/** 扁平化所有子项，便于 TopBar 标题查找与路由生成 */
export const allNavChildren: NavChild[] = navGroups.flatMap((g) => g.children)

/** 路由路径 → 页面标题 映射（TopBar 使用） */
export const pageTitleMap: Record<string, string> = Object.fromEntries(
  allNavChildren.map((c) => [c.path, c.label]),
)

/** 按路径查找所属一级分组 */
export function findGroupByPath(path: string): NavGroup | undefined {
  return navGroups.find((g) => g.children.some((c) => c.path === path))
}

/**
 * 向后兼容重定向表（40+条）— 旧路由 → 新路由。
 * 确保旧书签/旧链接不 404。
 */
export const legacyRedirects: { from: string; to: string }[] = [
  { from: '/super-agent', to: '/' },
  { from: '/chat', to: '/' },
  { from: '/ai-staff', to: '/' },
  { from: '/ai-staff/chat', to: '/' },
  { from: '/ai-staff/computer-use', to: '/' },
  { from: '/dashboard', to: '/marketing/workbench' },
  { from: '/digital-human', to: '/content/digital-human' },
  { from: '/agents', to: '/ai-staff/market' },
  { from: '/video', to: '/content/production' },
  { from: '/image', to: '/content/production' },
  { from: '/publisher', to: '/publish/center' },
  { from: '/publish', to: '/publish/center' },
  { from: '/scheduler', to: '/automation/runs' },
  { from: '/sop', to: '/automation/tasks' },
  { from: '/pipeline', to: '/automation/tasks' },
  { from: '/tools', to: '/knowledge/skills' },
  { from: '/hub', to: '/knowledge/skills' },
  { from: '/skills', to: '/knowledge/skills' },
  { from: '/memory', to: '/knowledge/base' },
  { from: '/knowledge', to: '/knowledge/base' },
  { from: '/admin', to: '/settings' },
  { from: '/oem', to: '/settings' },
  { from: '/acquisition', to: '/marketing/opportunities' },
  { from: '/intercept', to: '/marketing/opportunities' },
  { from: '/listen', to: '/marketing/opportunities?view=monitoring' },
  { from: '/convert', to: '/marketing/customers' },
  { from: '/customers', to: '/marketing/customers' },
  { from: '/content', to: '/content/production' },
  { from: '/assets', to: '/content/assets' },
  { from: '/marketing', to: '/marketing/workbench' },
  { from: '/geo', to: '/geo/workbench' },
  { from: '/workflow', to: '/automation/tasks' },
  { from: '/automation', to: '/automation/tasks' },
  { from: '/insights', to: '/marketing/workbench' },
  { from: '/analytics', to: '/marketing/workbench' },
  { from: '/risk-control', to: '/settings' },
  { from: '/risk', to: '/settings' },
  { from: '/team', to: '/settings' },
  { from: '/billing', to: '/settings/billing' },
  { from: '/brand', to: '/settings' },
  { from: '/config', to: '/settings' },
  { from: '/settings/system', to: '/settings' },
  { from: '/staff', to: '/publish/center' },
  { from: '/tasks', to: '/publish/center' },
  { from: '/market', to: '/ai-staff/market' },
  { from: '/calendar', to: '/publish/center' },
  { from: '/publish/calendar', to: '/publish/center' },
  { from: '/accounts', to: '/publish/accounts' },
  { from: '/academy', to: '/knowledge/base' },
]
