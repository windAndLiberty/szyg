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
  GraduationCap,
  SlidersHorizontal,
  Palette,
  UsersRound,
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
    label: 'AI员工',
    icon: Bot,
    basePath: '/ai-staff',
    defaultChild: '/',
    children: [
      { path: '/', label: '超级员工', icon: BrainCircuit, module: 'hermes', implemented: true },
      { path: '/ai-staff/market', label: 'AI人才市场', icon: Bot, module: 'agents' },
      { path: '/ai-staff/tools', label: 'AI工具导航', icon: Compass, module: 'external-tools', implemented: true },
    ],
  },
  {
    id: 'content-publish',
    label: '内容发布',
    icon: Package,
    basePath: '/content',
    defaultChild: '/content/production',
    children: [
      { path: '/content/production', label: '内容生成', icon: PenLine, module: 'content-generation', implemented: true },
      { path: '/content/digital-human', label: '数字人创作', icon: UserRound, module: 'digital-human', implemented: true },
      { path: '/content/assets', label: '素材管理与发布', icon: ImageIcon, module: 'materials' },
      { path: '/publish/accounts', label: '渠道账号', icon: KeyRound, module: 'platforms' },
      { path: '/publish/center', label: '发布看板', icon: Send, module: 'publisher' },
    ],
  },
  {
    id: 'marketing',
    label: 'AI营销获客',
    icon: Target,
    basePath: '/marketing',
    defaultChild: '/marketing/workbench',
    children: [
      { path: '/marketing/workbench', label: '获客工作台', icon: TrendingUp, module: 'marketing-workbench', implemented: true },
      { path: '/marketing/opportunities', label: '客户机会', icon: SearchCheck, module: 'marketing-opportunities', implemented: true },
      { path: '/marketing/customers', label: '客户中心', icon: ContactRound, module: 'customers', implemented: true },
    ],
  },
  {
    id: 'geo',
    label: 'GEO品牌增长',
    icon: Globe2,
    basePath: '/geo',
    defaultChild: '/geo/workbench',
    children: [
      { path: '/geo/workbench', label: 'GEO工作台', icon: TrendingUp, module: 'geo-workbench', implemented: true },
      { path: '/geo/monitoring', label: 'AI推荐监测', icon: Quote, module: 'geo-monitoring', implemented: true },
      { path: '/geo/optimization', label: '优化中心', icon: Sparkles, module: 'geo-optimization', implemented: true },
    ],
  },
  {
    id: 'automation',
    label: 'AI自动执行',
    icon: Workflow,
    basePath: '/automation',
    defaultChild: '/automation/tasks',
    children: [
      { path: '/automation/tasks', label: '自动任务', icon: ListChecks, module: 'automation-tasks', implemented: true },
      { path: '/automation/approvals', label: '待我确认', icon: ShieldCheck, module: 'automation-approvals', implemented: true },
      { path: '/automation/runs', label: '执行记录', icon: Clock, module: 'automation-runs', implemented: true },
    ],
  },
  {
    id: 'knowledge',
    label: '知识库',
    icon: BookOpen,
    basePath: '/knowledge',
    defaultChild: '/knowledge/base',
    children: [
      { path: '/knowledge/base', label: '知识管理', icon: Database, module: 'knowledge' },
      { path: '/knowledge/skills', label: '技能市场', icon: Cpu, module: 'skills' },
      { path: '/knowledge/academy', label: '商学院', icon: GraduationCap, module: 'academy' },
    ],
  },
  {
    id: 'settings',
    label: '系统设置',
    icon: SlidersHorizontal,
    basePath: '/settings',
    defaultChild: '/settings',
    children: [
      { path: '/settings', label: '系统配置', icon: SlidersHorizontal, module: 'config', implemented: true },
      { path: '/settings/brand', label: '品牌配置', icon: Palette, module: 'oem' },
      { path: '/settings/team', label: '团队管理', icon: UsersRound, module: 'team' },
      { path: '/settings/billing', label: '计费管理', icon: CreditCard, module: 'billing' },
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
  { from: '/admin', to: '/settings/team' },
  { from: '/oem', to: '/settings/brand' },
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
  { from: '/team', to: '/settings/team' },
  { from: '/billing', to: '/settings/billing' },
  { from: '/brand', to: '/settings/brand' },
  { from: '/config', to: '/settings' },
  { from: '/settings/system', to: '/settings' },
  { from: '/staff', to: '/publish/center' },
  { from: '/tasks', to: '/publish/center' },
  { from: '/market', to: '/ai-staff/market' },
  { from: '/calendar', to: '/publish/center' },
  { from: '/publish/calendar', to: '/publish/center' },
  { from: '/accounts', to: '/publish/accounts' },
  { from: '/academy', to: '/knowledge/academy' },
]
