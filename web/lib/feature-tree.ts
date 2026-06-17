/**
 * 需求驱动的功能树配置
 * L1: 五大业务板块 | L2: 功能模块 | L3: 模板/入口（页面级）
 */

export interface FeatureNode {
  id: string
  label: string
  icon: string
  description?: string
  path?: string
  /** Old flat route this feature supersedes (for migration) */
  legacyPath?: string
  children?: FeatureNode[]
  badge?: 'new' | 'beta' | 'hot'
  automationLevel?: 'full' | 'semi' | 'assist'
  /** 流水线 / 状态机 / 纯工具 */
  engine?: 'pipeline' | 'state-machine' | 'tool'
}

export const featureTree: FeatureNode[] = [
  {
    id: 'ai-studio',
    label: 'AI工作室',
    icon: 'Sparkles',
    description: '管理/训练你的数字员工团队',
    children: [
      {
        id: 'super-agent',
        label: '超级员工',
        icon: 'Bot',
        description: '创建、训练和管理全能AI助手，串联多项技能',
        path: '/studio/super-agent',
        legacyPath: '/chat',
        engine: 'state-machine',
      },
      {
        id: 'ai-video',
        label: 'AI视频',
        icon: 'Clapperboard',
        description: '脚本变视频，含配音、素材混剪，一键生成',
        path: '/studio/ai-video',
        legacyPath: '/video',
        engine: 'pipeline',
        badge: 'hot',
      },
      {
        id: 'ai-graphic',
        label: 'AI图文',
        icon: 'FileImage',
        description: '输入卖点/链接，自动生成笔记、海报、长文',
        path: '/studio/ai-graphic',
        legacyPath: '/image',
        engine: 'pipeline',
      },
      {
        id: 'ai-agents',
        label: 'AI智能体',
        icon: 'Bot',
        description: '一批开箱即用的小型AI专家，处理写作、办公、营销与业务咨询任务',
        path: '/studio/ai-agents',
        engine: 'tool',
        badge: 'new',
      },
      {
        id: 'ai-navigation',
        label: 'AI导航',
        icon: 'Compass',
        description: '发现、收藏与分类好用的国内外 AI 工具',
        path: '/studio/ai-navigation',
        engine: 'tool',
      },
    ],
  },
  {
    id: 'public-traffic',
    label: '公域获客',
    icon: 'Globe',
    description: '在全网各大平台捕获流量',
    children: [
      {
        id: 'one-click-publish',
        label: '一键分发',
        icon: 'Send',
        description: '内容一键适配并发布到多平台',
        path: '/public/one-click-publish',
        legacyPath: '/publisher',
        engine: 'pipeline',
      },
      {
        id: 'smart-comment',
        label: '智能评论',
        icon: 'MessageSquarePlus',
        description: '自动高情商互动评论，引导关注',
        path: '/public/smart-comment',
        engine: 'state-machine',
        badge: 'new',
      },
      {
        id: 'viral-clone',
        label: '爆款复刻',
        icon: 'Copy',
        description: '拆解竞品爆款框架，生成专属版本',
        path: '/public/viral-clone',
        engine: 'pipeline',
      },
      {
        id: 'hotspot-ride',
        label: '热点借势',
        icon: 'TrendingUp',
        description: '实时追踪热点，生成蹭热点草案',
        path: '/public/hotspot-ride',
        engine: 'pipeline',
      },
    ],
  },
  {
    id: 'private-domain',
    label: '私域营销',
    icon: 'MessageCircleHeart',
    description: '盘活、转化你的微信/企微客户',
    children: [
      {
        id: 'lead-manager',
        label: '线索管家',
        icon: 'Tags',
        description: '自动打标签、识别意向，触发跟进话术',
        path: '/private/lead-manager',
        engine: 'state-machine',
        automationLevel: 'semi',
      },
      {
        id: 'moments',
        label: '朋友圈经营',
        icon: 'Camera',
        description: '周期性自动生成并发布朋友圈内容',
        path: '/private/moments',
        engine: 'pipeline',
        automationLevel: 'full',
      },
      {
        id: 'community',
        label: '社群运营',
        icon: 'Users',
        description: '按SOP执行入群欢迎、群发活动、答疑',
        path: '/private/community',
        engine: 'state-machine',
        automationLevel: 'semi',
      },
      {
        id: 'one-on-one',
        label: '1v1触达',
        icon: 'UserCheck',
        description: '邀约、关怀、回访的个性化话术',
        path: '/private/one-on-one',
        engine: 'pipeline',
        automationLevel: 'assist',
      },
    ],
  },
  {
    id: 'data-insight',
    label: '数据洞察',
    icon: 'BarChart3',
    description: '让营销效果看得见，决策有依据',
    children: [
      {
        id: 'account-diagnosis',
        label: '账号诊断',
        icon: 'Stethoscope',
        description: '分析账号内容表现，给出优化建议',
        path: '/insight/account-diagnosis',
        engine: 'tool',
      },
      {
        id: 'competitor-monitor',
        label: '竞品监控',
        icon: 'Eye',
        description: '定向追踪竞品账号动态与策略变化',
        path: '/insight/competitor-monitor',
        engine: 'tool',
      },
      {
        id: 'asset-dashboard',
        label: '资产看板',
        icon: 'LayoutDashboard',
        description: '展示数字员工产出、效率及线索增长',
        path: '/insight/asset-dashboard',
        engine: 'tool',
      },
      {
        id: 'auto-report',
        label: '自动周报',
        icon: 'Newspaper',
        description: '自动生成运营周报与下周行动建议',
        path: '/insight/auto-report',
        engine: 'pipeline',
        badge: 'beta',
      },
    ],
  },
  {
    id: 'toolbox',
    label: '工具箱',
    icon: 'Wrench',
    description: '原子能力集合，满足临时零散需求',
    children: [
      {
        id: 'copy-gen',
        label: '文案生成',
        icon: 'Pencil',
        description: '各类平台、各种风格的短文案',
        path: '/tools/copy-gen',
        engine: 'tool',
      },
      {
        id: 'image-process',
        label: '图片处理',
        icon: 'ImagePlus',
        description: '智能抠图、改尺寸、批量加水印',
        path: '/tools/image-process',
        engine: 'tool',
      },
      {
        id: 'format-convert',
        label: '格式转换',
        icon: 'ArrowLeftRight',
        description: '视频转GIF、PDF压缩、音频转文字',
        path: '/tools/format-convert',
        engine: 'tool',
      },
    ],
  },
]

/** 扁平化所有带 path 的节点，用于快速查找 */
export function flattenFeatures(nodes: FeatureNode[]): FeatureNode[] {
  const result: FeatureNode[] = []
  for (const node of nodes) {
    if (node.path) result.push(node)
    if (node.children) result.push(...flattenFeatures(node.children))
  }
  return result
}

/** 根据 path 查找节点 */
export function findFeatureByPath(path: string, nodes: FeatureNode[] = featureTree): FeatureNode | undefined {
  for (const node of nodes) {
    if (node.path === path) return node
    if (node.children) {
      const found = findFeatureByPath(path, node.children)
      if (found) return found
    }
  }
  return undefined
}

/** 根据 path 查找所属 L1 */
export function findL1ByPath(path: string, nodes: FeatureNode[] = featureTree): FeatureNode | undefined {
  for (const l1 of nodes) {
    if (l1.path === path) return l1
    if (l1.children) {
      const found = findFeatureByPath(path, l1.children)
      if (found) return l1
    }
  }
  return undefined
}
