import { createContext, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'
import { enUS as coreEnUS, zhCN as coreZhCN } from '@/locales/core'
import { digitalHumanEnUS, digitalHumanZhCN } from '@/locales/digitalHuman'

export type AppLocale = 'zh-CN' | 'en-US'
type InterpolationValues = Record<string, string | number>

interface I18nContextValue {
  locale: AppLocale
  setLocale: (locale: AppLocale) => void
  t: (key: string, values?: InterpolationValues) => string
}

const LOCALE_STORAGE_KEY = 'szyg-locale'

/** UI copy catalog. Chinese is the source locale; add every user-facing string here. */
const legacyEnUS: Record<string, string> = {
  '数字员工': 'Digital Employee', 'AI员工': 'AI Staff', '超级员工': 'Super Agent', 'AI人才市场': 'AI Talent',
  'AI工具导航': 'AI Tools', '内容发布': 'Content', '内容生成': 'Content Studio', '素材管理与发布': 'Assets & Publishing',
  '渠道账号': 'Channel Accounts', '发布看板': 'Publishing Board', '数字人': 'Digital Human', '营销获客': 'Marketing',
  '私域营销': 'Private-domain Sales', '市场情报': 'Market Intelligence', '智能截流': 'Smart Outreach',
  '舆情监听': 'Opportunity Monitor', '客户转化': 'Lead Conversion', '客户资产': 'Customer Assets',
  '工作流': 'Workflows', '工作流方案': 'Workflow Plans', '运行计划': 'Run Schedule', '数据洞察': 'Insights',
  '全局洞察': 'Overview', '内容洞察': 'Content Insights', '获客洞察': 'Acquisition Insights', '知识库': 'Knowledge Base',
  '知识管理': 'Knowledge', '技能市场': 'Skills', '系统设置': 'Settings', '系统配置': 'System Settings',
  '计费管理': 'Billing', '展开': 'Expand', '折叠': 'Collapse', '收起': 'Collapse', '搜索...': 'Search...',
  '个人资料': 'Profile', '退出登录': 'Sign out', '超级数字员工': 'Super Digital Workforce', '主导航': 'Main navigation',
  '有已完成的工作,点击查看': 'Completed work available. Click to view.', '展开侧边栏': 'Expand sidebar',
  '收起侧边栏': 'Collapse sidebar', '点击设置头像': 'Change avatar', '个人菜单': 'Account menu', '更换头像': 'Change avatar',
  '有未保存的更改': 'You have unsaved changes', '头像仅保存在本机，不会上传云端': 'Your avatar is stored locally and is never uploaded.',
  '由登录服务统一管理': 'Managed by your sign-in service', '管理你的个人资料信息。': 'Manage your personal profile.',
  '通用设置': 'General', 'AI 模型': 'AI Models', '账户管理': 'Account', '配置你的超级数字员工系统参数': 'Configure your Super Digital Workforce.',
  '外观': 'Appearance', '自定义超级数字员工系统的外观风格。': 'Customize the appearance of your workspace.',
  '主题选择': 'Theme', '选择你喜欢的配色方案': 'Choose your preferred color scheme.', '亮色': 'Light', '深色': 'Dark',
  '跟随系统': 'System', '语言': 'Language', '界面显示语言': 'Interface language', '中文': '中文', 'English': 'English',
  '切换语言': 'Switch language', '切换为中文': 'Switch to Chinese', '切换为 English': 'Switch to English',
  '通知': 'Notifications', '控制你如何接收系统更新通知。': 'Choose how you receive system updates.',
  'Email 通知': 'Email notifications', '接收任务完成、Agent 异常等邮件提醒': 'Receive emails about completed tasks and staff issues.',
  '接收任务完成、员工异常等邮件提醒': 'Receive emails about completed tasks and staff issues.', '浏览器通知': 'Browser notifications',
  '在桌面显示重要事件的浏览器推送通知': 'Show important events as desktop notifications.', '通知事件列表': 'Notification events',
  '任务执行完成': 'Task completed', '数字员工执行出错': 'AI staff error', '报告生成完毕': 'Report ready', '每日执行摘要': 'Daily activity summary',
  'AI 模型配置': 'AI model configuration', '配置驱动数字员工pipeline的大语言模型参数。': 'Configure the language models used by your AI staff.',
  'AI 模型选择': 'AI model', '选择驱动数字员工pipeline的大语言模型': 'Choose the primary language model for AI tasks.',
  '自定义 API URL': 'Custom API URL', 'AI 创意度 (Temperature)': 'Creativity (Temperature)', '精确': 'Precise', '创意': 'Creative',
  '数值越高输出越具创意，但一致性可能降低': 'Higher values are more creative but may be less consistent.', '最大输出长度': 'Maximum output length',
  '个人信息': 'Profile', '姓名': 'Name', '邮箱': 'Email', '角色': 'Role', '保存更改': 'Save changes', '恢复默认': 'Restore defaults',
  '当前页面暂时无法显示': 'This page is temporarily unavailable', '页面数据可能发生了变化。你可以重新加载，其他功能不会受到影响。': 'The page data may have changed. Reload this page to continue; other features are unaffected.',
  '重新加载': 'Reload', '返回首页': 'Back to home', '模块开发中': 'Coming soon', '骨架阶段占位页面': 'This feature is not available yet.',
  '套餐、用量与账单管理': 'Plans, usage, and billing management.', '日历视图与发布计划编排': 'Calendar view and publishing schedule.',
  '页面未找到': 'Page not found', '您访问的页面不存在或已被移动': 'The page does not exist or has moved', '返回超级员工': 'Back to Super Agent',
  '登录后继续使用智能服务': 'Sign in to continue using intelligent services', '注册账号后按需充值 Credits': 'Create an account and top up Credits as needed',
  '验证当前密码后设置新密码': 'Verify your current password to set a new one', '你的称呼': 'Your name', '密码（至少 10 个字符）': 'Password (at least 10 characters)',
  '当前密码': 'Current password', '6位邮箱验证码': '6-digit email code', '重新发送': 'Resend', '发送验证码': 'Send code', '{seconds}秒': '{seconds}s',
  '我已阅读并同意 ': 'I have read and agree to the ', '用户协议': 'Terms of Service', ' 和 ': ' and ', '隐私政策': 'Privacy Policy',
  '新密码（至少 10 个字符）': 'New password (at least 10 characters)', '再次输入新密码': 'Confirm new password', '登录': 'Sign in',
  '注册并登录': 'Create account', '确认修改': 'Confirm change', '注册账号': 'Create account', '修改密码': 'Change password', '返回登录': 'Back to sign in',
  '本机素材不会上传到云端': 'Local materials are not uploaded to the cloud', '请输入你的称呼': 'Enter your name', '密码至少需要 10 个字符': 'Password must be at least 10 characters.',
  '请先获取并填写6位邮箱验证码': 'Request and enter the 6-digit email code first.', '请先阅读并同意用户协议和隐私政策': 'Read and accept the Terms of Service and Privacy Policy first.',
  '新密码至少需要 10 个字符': 'New password must be at least 10 characters.', '两次输入的新密码不一致': 'The new passwords do not match.',
  '验证码已发送至 {email}，10分钟内有效': 'A code was sent to {email}. It is valid for 10 minutes.', '验证码发送失败，请稍后再试': 'Could not send the code. Try again shortly.',
  '登录未完成，请检查输入': 'Sign-in could not be completed. Check your details.', '请先登录': 'Please sign in', '登录状态已过期，请重新登录': 'Your session has expired. Sign in again.',
  '数字人形象库': 'Digital human library', '人物和声音绑定保存，后续作品可以直接复用。': 'Save linked character and voice references for reuse in future projects.',
  '新建形象': 'New profile', '形象名称': 'Profile name', '例如：品牌讲解员': 'For example: Brand presenter',
  '虚拟人物': 'Virtual person', '真人形象': 'Real-person profile', '人物参考': 'Character references', '拖入或点击上传': 'Drop files or click to upload',
  '图片 / 视频，可多次上传': 'Images or videos; multiple uploads supported', '松开即可加入人物参考': 'Release to add character references',
  '绑定声音': 'Voice reference', '上传单人清晰说话的音频或有声视频': 'Upload clear single-speaker audio or video', '松开即可绑定声音': 'Release to attach voice',
  '生成新台词时，以这段声音的音色和说话风格为参考。': 'New scripts use this voice’s tone and speaking style as a reference.',
  '保存': 'Save', '建立第一个数字人形象': 'Create your first digital human profile',
  '上传虚拟人物参考和声音，保存后可以在所有数字人口播作品中复用。': 'Upload virtual-person references and a voice to reuse across all digital-human videos.',
  '虚拟人物 · 可生成': 'Virtual person · Ready to generate', '真人形象 · 暂不可生成': 'Real-person profile · Generation unavailable',
  '声音：': 'Voice: ', '未绑定声音': 'No voice attached', '删除形象': 'Delete profile', '用此形象高仿复刻': 'Create a likeness with this profile',
}

const I18nContext = createContext<I18nContextValue | null>(null)

function readLocale(): AppLocale {
  if (typeof window === 'undefined') return 'zh-CN'
  try { return window.localStorage.getItem(LOCALE_STORAGE_KEY) === 'en-US' ? 'en-US' : 'zh-CN' } catch { return 'zh-CN' }
}

function interpolate(template: string, values?: InterpolationValues) {
  if (!values) return template
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? `{${key}}`))
}

function translate(locale: AppLocale, key: string, values?: InterpolationValues) {
  const coreMessages: Record<string, string> = locale === 'en-US'
    ? { ...coreEnUS, ...digitalHumanEnUS }
    : { ...coreZhCN, ...digitalHumanZhCN }
  const coreMessage = coreMessages[key as keyof typeof coreMessages]
  if (coreMessage) return interpolate(coreMessage, values)
  if (locale === 'en-US' && legacyEnUS[key]) return interpolate(legacyEnUS[key], values)
  return interpolate(key, values)
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>(readLocale)
  useLayoutEffect(() => {
    document.documentElement.lang = locale
    try { window.localStorage.setItem(LOCALE_STORAGE_KEY, locale) } catch { /* storage may be unavailable */ }
  }, [locale])
  const value = useMemo<I18nContextValue>(() => ({
    locale, setLocale: setLocaleState,
    t: (key, values) => translate(locale, key, values),
  }), [locale])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) throw new Error('useI18n must be used within I18nProvider')
  return context
}
