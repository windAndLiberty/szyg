/**
 * 域灵系统导航配置 — 单一真理源 (Single Source of Truth)
 *
 * 供 Sidebar、TopBar、App 路由共用。结构对齐 module-tree.md 的 9 大一级模块。
 * 图标使用 lucide-react，按 DESIGN_SYSTEM.md 规范（导航图标 20px）。
 */
import {
  Bot,
  Video,
  BrainCircuit,
  ListChecks,
  Package,
  PenLine,
  Image as ImageIcon,
  PersonStanding,
  Target,
  Fish,
  Radar,
  Repeat2,
  Users,
  Send,
  KeyRound,
  CalendarDays,
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
  ShieldCheck,
  Wrench,
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
      { path: '/ai-staff/video', label: 'AI视频', icon: Video, module: 'video' },
      { path: '/ai-staff/market', label: 'AI人才市场', icon: Bot, module: 'agents' },
      { path: '/ai-staff/tasks', label: '任务看板', icon: ListChecks, module: 'staff' },
    ],
  },
  {
    id: 'content',
    label: '内容创作',
    icon: Package,
    basePath: '/content',
    defaultChild: '/content/production',
    children: [
      { path: '/content/production', label: '内容生产', icon: PenLine, module: 'image' },
      { path: '/content/assets', label: '素材管理', icon: ImageIcon, module: 'materials' },
      { path: '/content/digital-human', label: '数字人', icon: PersonStanding, module: 'digital-human', implemented: true },
    ],
  },
  {
    id: 'marketing',
    label: '营销获客',
    icon: Target,
    basePath: '/marketing',
    defaultChild: '/marketing/intercept',
    children: [
      { path: '/marketing/intercept', label: '智能截流', icon: Fish, module: 'acquisition' },
      { path: '/marketing/listen', label: '舆情监听', icon: Radar, module: 'listen' },
      { path: '/marketing/conversion', label: '客户转化', icon: Repeat2, module: 'convert' },
      { path: '/marketing/customers', label: '客户资产', icon: Users, module: 'customers' },
    ],
  },
  {
    id: 'publish',
    label: '发布管理',
    icon: Send,
    basePath: '/publish',
    defaultChild: '/publish/center',
    children: [
      { path: '/publish/center', label: '发布中心', icon: Send, module: 'publisher' },
      { path: '/publish/accounts', label: '账号管理', icon: KeyRound, module: 'platforms' },
      { path: '/publish/calendar', label: '内容日历', icon: CalendarDays, module: 'scheduler' },
    ],
  },
  {
    id: 'workflow',
    label: '工作流',
    icon: Workflow,
    basePath: '/workflow',
    defaultChild: '/workflow/pipeline',
    children: [
      { path: '/workflow/pipeline', label: '流水线编排', icon: GitBranch, module: 'pipeline' },
      { path: '/workflow/scheduler', label: '调度引擎', icon: Clock, module: 'scheduler' },
      { path: '/workflow/sop', label: 'SOP管理', icon: ClipboardList, module: 'sop' },
    ],
  },
  {
    id: 'insights',
    label: '数据洞察',
    icon: BarChart3,
    basePath: '/insights',
    defaultChild: '/insights/dashboard',
    children: [
      { path: '/insights/dashboard', label: '运营仪表盘', icon: BarChart3, module: 'dashboard', implemented: true },
      { path: '/insights/content-analytics', label: '内容分析', icon: LineChart, module: 'content-analytics' },
      { path: '/insights/acquisition-analytics', label: '获客分析', icon: TrendingUp, module: 'acquisition-analytics' },
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
      { path: '/knowledge/memory', label: '长期记忆', icon: BrainCircuit, module: 'memory' },
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
      { path: '/settings/risk-control', label: '风控策略', icon: ShieldCheck, module: 'risk' },
      { path: '/settings/tools', label: '工具管理', icon: Wrench, module: 'tools' },
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
  { from: '/digital-human', to: '/content/digital-human' },
  { from: '/agents', to: '/ai-staff/market' },
  { from: '/video', to: '/ai-staff/video' },
  { from: '/image', to: '/content/production' },
  { from: '/publisher', to: '/publish/center' },
  { from: '/publish', to: '/publish/center' },
  { from: '/scheduler', to: '/workflow/scheduler' },
  { from: '/sop', to: '/workflow/sop' },
  { from: '/pipeline', to: '/workflow/pipeline' },
  { from: '/tools', to: '/settings/tools' },
  { from: '/hub', to: '/knowledge/skills' },
  { from: '/skills', to: '/knowledge/skills' },
  { from: '/memory', to: '/knowledge/memory' },
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
  { from: '/marketing', to: '/marketing/intercept' },
  { from: '/workflow', to: '/workflow/pipeline' },
  { from: '/insights', to: '/insights/dashboard' },
  { from: '/analytics', to: '/insights/dashboard' },
  { from: '/risk-control', to: '/settings/risk-control' },
  { from: '/risk', to: '/settings/risk-control' },
  { from: '/team', to: '/settings/team' },
  { from: '/billing', to: '/settings/billing' },
  { from: '/brand', to: '/settings/brand' },
  { from: '/config', to: '/settings' },
  { from: '/settings/system', to: '/settings' },
  { from: '/staff', to: '/ai-staff/tasks' },
  { from: '/tasks', to: '/ai-staff/tasks' },
  { from: '/market', to: '/ai-staff/market' },
  { from: '/calendar', to: '/publish/calendar' },
  { from: '/accounts', to: '/publish/accounts' },
  { from: '/academy', to: '/knowledge/academy' },
]

