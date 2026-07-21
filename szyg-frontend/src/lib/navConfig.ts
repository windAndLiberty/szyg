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
  MessageCircle,
  Fish,
  Radar,
  Repeat2,
  Users,
  Send,
  MonitorCog,
  KeyRound,
  Workflow,
  GitBranch,
  Clock,
  ClipboardList,
  BarChart3,
  LineChart,
  TrendingUp,
  BookOpen,
  Database,
  Cpu,
  GraduationCap,
  SlidersHorizontal,
  Palette,
  UsersRound,
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
      { path: '/ai-staff/computer-use', label: '电脑使用', icon: MonitorCog, module: 'computer-use', implemented: true },
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
      { path: '/content/assets', label: '素材管理与发布', icon: ImageIcon, module: 'materials' },
      { path: '/publish/accounts', label: '渠道账号', icon: KeyRound, module: 'platforms' },
      { path: '/publish/center', label: '发布看板', icon: Send, module: 'publisher' },
    ],
  },
  {
    id: 'marketing',
    label: '营销获客',
    icon: Target,
    basePath: '/marketing',
    defaultChild: '/marketing/private-domain',
    children: [
      { path: '/marketing/private-domain', label: '私域营销', icon: MessageCircle, module: 'private-domain' },
      { path: '/marketing/intelligence', label: '市场情报', icon: LineChart, module: 'intelligence' },
      { path: '/marketing/intercept', label: '智能截流', icon: Fish, module: 'acquisition' },
      { path: '/marketing/listen', label: '舆情监听', icon: Radar, module: 'listen' },
      { path: '/marketing/conversion', label: '客户转化', icon: Repeat2, module: 'convert' },
      { path: '/marketing/customers', label: '客户资产', icon: Users, module: 'customers' },
    ],
  },
  {
    id: 'automation',
    label: '工作流',
    icon: Workflow,
    basePath: '/automation',
    defaultChild: '/automation/plans',
    children: [
      { path: '/automation/plans', label: '工作流方案', icon: GitBranch, module: 'automation-plans' },
      { path: '/automation/runs', label: '运行计划', icon: Clock, module: 'automation-runs' },
    ],
  },
  {
    id: 'insights',
    label: '数据洞察',
    icon: BarChart3,
    basePath: '/insights',
    defaultChild: '/insights/dashboard',
    children: [
      { path: '/insights/dashboard', label: '全局洞察', icon: BarChart3, module: 'dashboard', implemented: true },
      { path: '/insights/content-analytics', label: '内容洞察', icon: LineChart, module: 'content-analytics' },
      { path: '/insights/acquisition-analytics', label: '获客洞察', icon: TrendingUp, module: 'acquisition-analytics' },
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
  { from: '/dashboard', to: '/insights/dashboard' },
  { from: '/digital-human', to: '/' },
  { from: '/content/digital-human', to: '/' },
  { from: '/agents', to: '/ai-staff/market' },
  { from: '/video', to: '/content/production' },
  { from: '/image', to: '/content/production' },
  { from: '/publisher', to: '/publish/center' },
  { from: '/publish', to: '/publish/center' },
  { from: '/scheduler', to: '/automation/runs' },
  { from: '/sop', to: '/automation/plans?view=standards' },
  { from: '/pipeline', to: '/automation/plans' },
  { from: '/tools', to: '/knowledge/skills' },
  { from: '/hub', to: '/knowledge/skills' },
  { from: '/skills', to: '/knowledge/skills' },
  { from: '/memory', to: '/knowledge/base' },
  { from: '/knowledge', to: '/knowledge/base' },
  { from: '/admin', to: '/settings/team' },
  { from: '/oem', to: '/settings/brand' },
  { from: '/acquisition', to: '/marketing/intercept' },
  { from: '/intercept', to: '/marketing/intercept' },
  { from: '/listen', to: '/marketing/listen' },
  { from: '/convert', to: '/marketing/conversion' },
  { from: '/customers', to: '/marketing/customers' },
  { from: '/content', to: '/content/production' },
  { from: '/assets', to: '/content/assets' },
  { from: '/marketing', to: '/marketing/private-domain' },
  { from: '/workflow', to: '/automation/plans' },
  { from: '/automation', to: '/automation/plans' },
  { from: '/insights', to: '/insights/dashboard' },
  { from: '/analytics', to: '/insights/dashboard' },
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
