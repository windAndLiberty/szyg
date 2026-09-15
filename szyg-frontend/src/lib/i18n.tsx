import { createContext, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'

export type AppLocale = 'zh-CN' | 'en-US'

interface I18nContextValue {
  locale: AppLocale
  setLocale: (locale: AppLocale) => void
  t: (text: string) => string
}

const LOCALE_STORAGE_KEY = 'szyg-locale'

const enUS: Record<string, string> = {
  '数字员工': 'Digital Employee',
  'AI员工': 'AI Staff',
  '超级员工': 'Super Agent',
  'AI人才市场': 'AI Talent',
  'AI工具导航': 'AI Tools',
  '内容发布': 'Content',
  '内容生成': 'Content Studio',
  '素材管理与发布': 'Assets & Publishing',
  '渠道账号': 'Channel Accounts',
  '发布看板': 'Publishing Board',
  '数字人': 'Digital Human',
  '营销获客': 'Marketing',
  '私域营销': 'Private-domain Sales',
  '市场情报': 'Market Intelligence',
  '智能截流': 'Smart Outreach',
  '舆情监听': 'Opportunity Monitor',
  '客户转化': 'Lead Conversion',
  '客户资产': 'Customer Assets',
  '工作流': 'Workflows',
  '工作流方案': 'Workflow Plans',
  '运行计划': 'Run Schedule',
  '数据洞察': 'Insights',
  '全局洞察': 'Overview',
  '内容洞察': 'Content Insights',
  '获客洞察': 'Acquisition Insights',
  '知识库': 'Knowledge Base',
  '知识管理': 'Knowledge',
  '技能市场': 'Skills',
  '系统设置': 'Settings',
  '系统配置': 'System Settings',
  '计费管理': 'Billing',
  '展开': 'Expand',
  '折叠': 'Collapse',
  '收起': 'Collapse',
  '搜索...': 'Search...',
  '个人资料': 'Profile',
  '退出登录': 'Sign out',
  '超级数字员工': 'Super Digital Workforce',
  '© 2026 数字员工. All rights reserved.': '© 2026 Digital Employee. All rights reserved.',

  '通用设置': 'General',
  'AI 模型': 'AI Models',
  '账户管理': 'Account',
  '配置你的超级数字员工系统参数': 'Configure your Super Digital Workforce.',
  '外观': 'Appearance',
  '自定义超级数字员工系统的外观风格。': 'Customize the appearance of your workspace.',
  '主题选择': 'Theme',
  '选择你喜欢的配色方案': 'Choose your preferred color scheme.',
  '亮色': 'Light',
  '深色': 'Dark',
  '跟随系统': 'System',
  '语言': 'Language',
  '界面显示语言': 'Interface language',
  '中文': '中文',
  '通知': 'Notifications',
  '控制你如何接收系统更新通知。': 'Choose how you receive system updates.',
  'Email 通知': 'Email notifications',
  '接收任务完成、Agent 异常等邮件提醒': 'Receive emails about completed tasks and staff issues.',
  '接收任务完成、员工异常等邮件提醒': 'Receive emails about completed tasks and staff issues.',
  '浏览器通知': 'Browser notifications',
  '在桌面显示重要事件的浏览器推送通知': 'Show important events as desktop notifications.',
  '通知事件列表': 'Notification events',
  '任务执行完成': 'Task completed',
  '数字员工执行出错': 'AI staff error',
  '报告生成完毕': 'Report ready',
  '每日执行摘要': 'Daily activity summary',
  'AI 模型配置': 'AI model configuration',
  '配置驱动数字员工pipeline的大语言模型参数。': 'Configure the language models used by your AI staff.',
  'AI 模型选择': 'AI model',
  '选择驱动数字员工pipeline的大语言模型': 'Choose the primary language model for AI tasks.',
  '自定义 API URL': 'Custom API URL',
  'AI 创意度 (Temperature)': 'Creativity (Temperature)',
  '精确': 'Precise',
  '创意': 'Creative',
  '数值越高输出越具创意，但一致性可能降低': 'Higher values are more creative but may be less consistent.',
  '最大输出长度': 'Maximum output length',
  '本地小模型': 'Local lightweight model',
  '用于摘要、分类、改写等简单任务，主力对话仍由云端 API 模型完成。': 'Used for summaries, classification, and rewriting. Primary conversations continue to use cloud models.',
  '基础模式': 'Basic model',
  '增强模型': 'Enhanced model',
  '已就绪': 'Ready',
  '未启动': 'Stopped',
  '已安装': 'Installed',
  '未安装': 'Not installed',
  '启用': 'Start',
  '停止': 'Stop',
  '测试': 'Test',
  '下载增强模型': 'Download enhanced model',
  '下载中': 'Downloading',
  '删除增强模型': 'Remove enhanced model',
  '输入一句话测试本地小模型': 'Enter a sentence to test the local model',
  '本地运行组件已安装': 'Local runtime installed',
  '本地运行组件未安装': 'Local runtime not installed',
  '适合更长文本和更复杂的分类、改写任务，可按需下载。': 'Designed for longer text and more complex classification or rewriting tasks. Download it when needed.',
  '显卡加速': 'GPU accelerated',
  '自动选择': 'Automatic',
  '查看高级信息': 'Show technical details',
  '收起高级信息': 'Hide technical details',
  '数字员工开关': 'AI staff availability',
  '启用或禁用各类 Agent。禁用的 Agent 将在pipeline中被跳过。': 'Enable or disable AI staff roles. Disabled roles are skipped during execution.',
  'AI 员工（可启用/禁用）': 'AI staff role',
  '数据库与存储后端连接配置。': 'Configure database and storage connections.',
  'Supabase 连接': 'Supabase connection',
  '已连接': 'Connected',
  '未连接': 'Not connected',
  '测试连接': 'Test connection',
  '网络搜索集成，增强数字员工的信息获取能力。': 'Connect web search services for external information.',
  'Web Search 集成': 'Web Search integration',
  '联网搜索服务': 'Web search',
  '允许数字员工实时搜索网络信息': 'Allow AI staff to search the web.',
  '第三方 API Key': 'Third-party API keys',
  '其他外部服务的 API Key 配置。': 'Configure credentials for other external services.',
  '通用 API Key': 'Generic API key',
  '第三方服务': 'External services',
  '配置其他外部服务的访问凭证。': 'Configure access credentials for external services.',
  '通用服务凭证': 'Service credential',
  '个人信息': 'Profile',
  '管理你的个人资料信息。': 'Manage your profile information.',
  '姓名': 'Name',
  '邮箱': 'Email',
  '由 OAuth 提供商管理': 'Managed by your sign-in provider',
  '由登录服务统一管理': 'Managed by your sign-in service',
  '角色': 'Role',
  '系统管理员': 'Administrator',
  '数字员工配置员': 'AI Staff Manager',
  '数据分析师': 'Data Analyst',
  '普通用户': 'Member',
  '添加成员': 'Add member',
  '活跃': 'Active',
  '待激活': 'Pending',
  '普通成员': 'Member',
  '未命名成员': 'Unnamed member',
  '未设置邮箱': 'No email',
  '恢复默认': 'Restore defaults',
  '有未保存的更改': 'You have unsaved changes',
  '保存更改': 'Save changes',

  '当前页面暂时无法显示': 'This page is temporarily unavailable',
  '页面数据可能发生了变化。你可以重新加载，其他功能不会受到影响。': 'The page data may have changed. Reload this page to continue; other features are unaffected.',
  '重新加载': 'Reload',
  '返回首页': 'Back to home',
  '模块开发中': 'Coming soon',
  '骨架阶段占位页面': 'This feature is not available yet.',
  '套餐、用量与账单管理': 'Plans, usage, and billing management.',
  '日历视图与发布计划编排': 'Calendar view and publishing schedule.',
  '页面未找到': 'Page not found',
  '您访问的页面不存在或已被移动': 'The page does not exist or has moved.',
  '返回超级员工': 'Back to Super Agent',
}

const I18nContext = createContext<I18nContextValue | null>(null)

function readLocale(): AppLocale {
  if (typeof window === 'undefined') return 'zh-CN'
  try {
    return window.localStorage.getItem(LOCALE_STORAGE_KEY) === 'en-US' ? 'en-US' : 'zh-CN'
  } catch {
    return 'zh-CN'
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>(readLocale)

  useLayoutEffect(() => {
    document.documentElement.lang = locale
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale)
    } catch {
      // The interface still switches even when browser storage is unavailable.
    }
  }, [locale])

  const value = useMemo<I18nContextValue>(() => ({
    locale,
    setLocale: setLocaleState,
    t: (text: string) => locale === 'en-US' ? enUS[text] || text : text,
  }), [locale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) throw new Error('useI18n must be used within I18nProvider')
  return context
}
