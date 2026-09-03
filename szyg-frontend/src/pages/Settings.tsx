import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Settings,
  Plug,
  User,
  Sun,
  Moon,
  Monitor,
  Globe,
  Save,
  RotateCcw,
  Check,
  ChevronDown,
  Plus,
  Trash2,
  Database,
  Info,
  LogOut,
  Laptop,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import UserAvatar from '@/components/ui/UserAvatar'
import AvatarSettingsDialog from '@/components/ui/AvatarSettingsDialog'
import { cn } from '@/lib/utils'
import { useAsync } from '@/lib/hooks'
import { useTheme } from '@/lib/theme'
import { useI18n } from '@/lib/i18n'
import {
  apiGet,
  apiDel,
  getCurrentUser,
  fetchCloudSession,
  changeCloudPassword,
  getErrorMessage,
  logoutCloud,
  type CloudSession,
} from '@/lib/api'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type SettingsTab = 'general' | 'integrations' | 'account'

interface TeamMember {
  id: string
  name: string
  email: string
  role: string
  status: 'active' | 'pending'
}

const easeOutExpo = [0.16, 1, 0.3, 1] as [number, number, number, number]

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const settingsTabs: { id: SettingsTab; label: string; icon: typeof Settings }[] = [
  { id: 'general', label: '通用设置', icon: Settings },
  { id: 'integrations', label: '集成配置', icon: Plug },
  { id: 'account', label: '账户管理', icon: User },
]

const notificationEvents = [
  { id: 'task_complete', label: '任务执行完成', checked: true },
  { id: 'agent_error', label: '数字员工执行出错', checked: true },
  { id: 'report_ready', label: '报告生成完毕', checked: true },
  { id: 'team_update', label: '团队成员更新配置', checked: false },
  { id: 'daily_summary', label: '每日执行摘要', checked: true },
]

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function SettingsPage() {
const [activeTab, setActiveTab] = useState<SettingsTab>('general')
  const [unsaved, setUnsaved] = useState(false)
  const [notice, setNotice] = useState('')
  const [avatarSettingsOpen, setAvatarSettingsOpen] = useState(false)
  const noticeTimerRef = useRef<number | null>(null)

  const showNotice = (message: string) => {
    if (noticeTimerRef.current) window.clearTimeout(noticeTimerRef.current)
    setNotice(message)
    noticeTimerRef.current = window.setTimeout(() => setNotice(''), 2800)
  }

  useEffect(() => () => {
    if (noticeTimerRef.current) window.clearTimeout(noticeTimerRef.current)
  }, [])

  /* General */
  const { theme, setTheme } = useTheme()
  const { locale, setLocale, t } = useI18n()
  const [emailNotifs, setEmailNotifs] = useState(true)
  const [browserNotifs, setBrowserNotifs] = useState(true)
  const [notifEvents, setNotifEvents] = useState(notificationEvents)

  /* Integrations */
  const [supabaseUrl, setSupabaseUrl] = useState('')
  const [supabaseKey, setSupabaseKey] = useState('')
  const supabaseConnected = false
  const [webSearchEnabled, setWebSearchEnabled] = useState(false)
  const [webSearchProvider, setWebSearchProvider] = useState('Serper.dev')
  const [webSearchKey, setWebSearchKey] = useState('')
  /* Account */
  const currentUser = getCurrentUser()
  const [profileName, setProfileName] = useState(currentUser?.username ?? 'admin')
  const [profileEmail] = useState(`${currentUser?.username ?? 'admin'}@szyg.local`)
  const [profileRole, setProfileRole] = useState('系统管理员')
  const { data: cloudSession, reload: reloadCloudSession } = useAsync<CloudSession>(fetchCloudSession)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState('')
  const [passwordError, setPasswordError] = useState('')
  useEffect(() => {
    if (cloudSession?.user) {
      setProfileName(cloudSession.user.display_name)
      setProfileRole(cloudSession.user.role === 'admin' ? '系统管理员' : '内测用户')
    }
  }, [cloudSession])
  const { data: teamData, reload: reloadTeam } = useAsync<{ data: { id: number | string; username?: string | null; name?: string | null; role?: string | null; email?: string | null; status?: string | null }[] }>(
    () => apiGet('/api/data/team/list'),
  )
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([])
  useEffect(() => {
    if (Array.isArray(teamData?.data)) {
      setTeamMembers(teamData.data.map((m) => ({
        id: String(m.id),
        name: String(m.name || m.username || '未命名成员').trim() || '未命名成员',
        email: String(m.email || '未设置邮箱'),
        role: m.role === 'admin' ? '系统管理员' : '普通成员',
        status: m.status === 'active' ? 'active' : 'pending',
      })))
    }
  }, [teamData])

  /* -- handlers -- */
  const handleNotifEventToggle = (id: string) => {
    setNotifEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, checked: !e.checked } : e))
    )
    setUnsaved(true)
  }

  const handleSave = () => {
    setUnsaved(false)
  }

  const handleReset = () => {
    setUnsaved(false)
  }

  const handlePasswordChange = async () => {
    setPasswordError('')
    setPasswordMessage('')
    if (newPassword.length < 10) {
      setPasswordError('新密码至少需要 10 个字符')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('两次输入的新密码不一致')
      return
    }
    setPasswordSaving(true)
    try {
      await changeCloudPassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setPasswordMessage('密码已更新')
      await reloadCloudSession()
    } catch (error) {
      setPasswordError(getErrorMessage(error, '密码修改失败'))
    } finally {
      setPasswordSaving(false)
    }
  }

  /* -- animation variants -- */
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
  }

  const cardVariant = {
    hidden: { opacity: 0, y: 15 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: easeOutExpo } },
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="w-full pb-28"
    >
      {/* Page Header */}
      <motion.div variants={cardVariant} className="mb-6">
        <p className="text-body-lg text-[#94A3B8]">
          {t('配置你的超级数字员工系统参数')}
        </p>
      </motion.div>

      <div className="grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)] lg:items-start">
        {/* Settings Navigation */}
        <motion.aside variants={cardVariant} className="min-w-0 lg:sticky lg:top-6">
          <nav
            className="flex items-center gap-1 overflow-x-auto border-b border-[#1E293B] pb-3 lg:flex-col lg:items-stretch lg:overflow-visible lg:border-b-0 lg:border-r lg:pb-0 lg:pr-5"
            aria-label={t('系统配置')}
          >
          {settingsTabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'group relative flex shrink-0 items-center gap-3 rounded-lg px-3.5 py-3 text-sm font-medium transition-all duration-200 lg:w-full',
                  isActive
                    ? 'bg-[#6366F1]/10 text-[#E0E7FF]'
                    : 'text-[#64748B] hover:bg-[#1A2235]/70 hover:text-[#CBD5E1]'
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="settingsTabIndicator"
                    className="absolute bottom-0 left-3 right-3 h-0.5 rounded-full bg-[#6366F1] lg:bottom-2 lg:left-0 lg:right-auto lg:top-2 lg:h-auto lg:w-0.5"
                    transition={{ duration: 0.2, ease: [0.45, 0.05, 0.55, 0.95] as [number, number, number, number] }}
                  />
                )}
                <Icon className={cn('relative z-10 h-4 w-4', isActive ? 'text-[#818CF8]' : 'text-[#64748B] group-hover:text-[#94A3B8]')} />
                <span className="relative z-10 whitespace-nowrap">{t(tab.label)}</span>
              </button>
            )
          })}
          </nav>
        </motion.aside>

        {/* Tab Content */}
        <motion.section variants={cardVariant} className="min-w-0 max-w-[900px]">
          <AnimatePresence mode="wait">
        {/* ==================== TAB 1: 通用设置 ==================== */}
        {activeTab === 'general' && (
          <motion.div
            key="general"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {/* Appearance */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">{t('外观')}</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                {t('自定义超级数字员工系统的外观风格。')}
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-5">
                {/* Theme */}
                <div>
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-1">{t('主题选择')}</Label>
                  <p className="text-body-sm text-[#64748B] mb-3">{t('选择你喜欢的配色方案')}</p>
                  <div className="flex items-center gap-2 p-1 bg-[#0D1321] rounded-xl border border-[#1E293B] w-fit">
                    {([
                      { value: 'light', icon: Sun, label: '亮色' },
                      { value: 'dark', icon: Moon, label: '深色' },
                      { value: 'system', icon: Monitor, label: '跟随系统' },
                    ] as const).map((option) => {
                      const Icon = option.icon
                      const isActive = theme === option.value
                      return (
                        <button
                          key={option.value}
                          onClick={() => setTheme(option.value)}
                          aria-pressed={isActive}
                          className={cn(
                            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6366F1]/30',
                            isActive
                              ? 'bg-[#1A2235] text-[#F1F5F9] border border-[#334155]'
                              : 'text-[#64748B] hover:text-[#94A3B8]'
                          )}
                        >
                          <Icon className="w-4 h-4" />
                          {t(option.label)}
                        </button>
                      )
                    })}
                  </div>
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Language */}
                <div>
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-1">{t('语言')}</Label>
                  <p className="text-body-sm text-[#64748B] mb-3">{t('界面显示语言')}</p>
                  <div className="relative max-w-[240px]">
                    <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                    <select
                      value={locale}
                      onChange={(e) => setLocale(e.target.value === 'en-US' ? 'en-US' : 'zh-CN')}
                      className="w-full h-10 pl-10 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                    >
                      <option value="zh-CN">中文</option>
                      <option value="en-US">English</option>
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Notifications */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">{t('通知')}</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                {t('控制你如何接收系统更新通知。')}
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-5">
                {/* Email Notifications */}
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                      {t('Email 通知')}
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      {t('接收任务完成、员工异常等邮件提醒')}
                    </p>
                  </div>
                  <Switch
                    checked={emailNotifs}
                    onCheckedChange={(v) => { setEmailNotifs(v); setUnsaved(true) }}
                    className="data-[state=checked]:bg-[#6366F1]"
                  />
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Browser Notifications */}
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                      {t('浏览器通知')}
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      {t('在桌面显示重要事件的浏览器推送通知')}
                    </p>
                  </div>
                  <Switch
                    checked={browserNotifs}
                    onCheckedChange={(v) => { setBrowserNotifs(v); setUnsaved(true) }}
                    className="data-[state=checked]:bg-[#6366F1]"
                  />
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Notification Events */}
                <div>
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                    {t('通知事件列表')}
                  </Label>
                  <div className="mt-3 space-y-2">
                    {notifEvents.map((evt) => (
                      <label
                        key={evt.id}
                        className="flex items-center gap-3 p-2 rounded-lg hover:bg-[rgba(255,255,255,0.02)] cursor-pointer transition-colors"
                      >
                        <div
                          className={cn(
                            'w-5 h-5 rounded border flex items-center justify-center transition-colors',
                            evt.checked
                              ? 'bg-[#6366F1] border-[#6366F1]'
                              : 'border-[#334155] bg-transparent'
                          )}
                          onClick={() => handleNotifEventToggle(evt.id)}
                        >
                          {evt.checked && <Check className="w-3 h-3 text-white" />}
                        </div>
                        <span className="text-body-md text-[#94A3B8]">{t(evt.label)}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* ==================== TAB 2: 集成配置 ==================== */}
        {activeTab === 'integrations' && (
          <motion.div
            key="integrations"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {/* Supabase */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Supabase</h2>
              <p className="text-body-sm text-[#64748B] mb-4">{t('数据库与存储后端连接配置。')}</p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-[#3ECF8E]" />
                    <span className="text-heading-sm text-[#F1F5F9]">{t('Supabase 连接')}</span>
                  </div>
                  {supabaseConnected ? (
                    <Badge className="bg-[rgba(16,185,129,0.15)] text-[#10B981] border-[#10B981]">
                      <Check className="w-3 h-3 mr-1" /> {t('已连接')}
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[#64748B] border-[#334155]">
                      {t('未连接')}
                    </Badge>
                  )}
                </div>

                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Project URL</Label>
                  <Input
                    value={supabaseUrl}
                    onChange={(e) => { setSupabaseUrl(e.target.value); setUnsaved(true) }}
                    placeholder="https://your-project.supabase.co"
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50"
                  />
                </div>
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Anon Key</Label>
                  <Input
                    type="password"
                    value={supabaseKey}
                    onChange={(e) => { setSupabaseKey(e.target.value); setUnsaved(true) }}
                    placeholder="eyJhbGciOiJIUzI1NiIs..."
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50"
                  />
                </div>
                <Button
                  onClick={() => showNotice(t('Supabase 连接配置尚未开放'))}
                  className="bg-[#3ECF8E] hover:bg-[#4EE99D] text-black font-medium"
                >
                  {t('测试连接')}
                </Button>
              </div>
            </motion.div>

            {/* Web Search */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">联网搜索</h2>
              <p className="text-body-sm text-[#64748B] mb-4">{t('网络搜索集成，增强数字员工的信息获取能力。')}</p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                      {t('联网搜索服务')}
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      {t('允许数字员工实时搜索网络信息')}
                    </p>
                  </div>
                  <Switch
                    checked={webSearchEnabled}
                    onCheckedChange={(v) => { setWebSearchEnabled(v); setUnsaved(true) }}
                    className="data-[state=checked]:bg-[#6366F1]"
                  />
                </div>

                {webSearchEnabled && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="space-y-3 pt-2"
                  >
                    <div>
                      <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">搜索服务</Label>
                      <div className="relative max-w-[240px]">
                        <select
                          value={webSearchProvider}
                          onChange={(e) => { setWebSearchProvider(e.target.value); setUnsaved(true) }}
                          className="w-full h-10 px-3 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                        >
                          <option value="Serper.dev">标准搜索</option>
                          <option value="Exa.ai">深度搜索</option>
                          <option value="Custom">企业自定义</option>
                        </select>
                        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                      </div>
                    </div>
                    <div>
                      <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">服务凭证</Label>
                      <Input
                        type="password"
                        value={webSearchKey}
                        onChange={(e) => { setWebSearchKey(e.target.value); setUnsaved(true) }}
                        placeholder="输入服务凭证"
                        className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                      />
                    </div>
                  </motion.div>
                )}
              </div>
            </motion.div>

          </motion.div>
        )}

        {/* ==================== TAB 3: 账户管理 ==================== */}
        {activeTab === 'account' && (
          <motion.div
            key="account"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {cloudSession?.configured && cloudSession.authenticated && (
              <motion.div variants={cardVariant}>
                <div className="glass-card rounded-[16px] border border-[#26334B] p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="grid h-11 w-11 place-items-center rounded-lg bg-[rgba(99,102,241,0.16)] text-[#A5B4FC]"><Laptop className="h-5 w-5" /></div>
                      <div><p className="text-sm font-medium text-[#F1F5F9]">当前设备已授权</p><p className="mt-1 text-xs text-[#64748B]">{cloudSession.device?.name || 'Windows PC'}</p></div>
                    </div>
                    <Badge className="border-[#10B981]/40 bg-[#10B981]/10 text-[#6EE7B7]">在线</Badge>
                  </div>
                  <button onClick={async () => { await logoutCloud(); await reloadCloudSession(); window.location.reload() }} className="mt-5 inline-flex items-center gap-2 text-sm text-[#94A3B8] transition-colors hover:text-[#F1F5F9]"><LogOut className="h-4 w-4" />退出登录</button>
                </div>
              </motion.div>
            )}
            {/* Profile */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">{t('个人信息')}</h2>
              <p className="text-body-sm text-[#64748B] mb-4">{t('管理你的个人资料信息。')}</p>
<div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-5">
                {/* Avatar + Name */}
                <div className="flex items-center gap-4">
                  <UserAvatar
                    alt="我的头像"
                    className="h-20 w-20 border-2 border-[#26334B]"
                    onClick={() => setAvatarSettingsOpen(true)}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-heading-sm text-[#F1F5F9]">{profileName}</p>
                    <p className="text-body-sm text-[#64748B]">{cloudSession?.user?.email || profileEmail}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2 border-[#1E293B] text-[#94A3B8] hover:text-[#F1F5F9] hover:border-[#334155]"
                      onClick={() => setAvatarSettingsOpen(true)}
                    >
                      <User className="w-3.5 h-3.5 mr-1.5" />
                      {t('更换头像')}
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-[#64748B] -mt-3">{t('头像仅保存在本机，不会上传云端')}</p>

                <Separator className="bg-[#1E293B]" />

                {/* Name */}
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">{t('姓名')}</Label>
                  <Input
                    value={profileName}
                    onChange={(e) => { setProfileName(e.target.value); setUnsaved(true) }}
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                  />
                </div>

                {/* Email */}
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">{t('邮箱')}</Label>
                  <Input
                    value={cloudSession?.user?.email || profileEmail}
                    disabled
                    className="bg-[#0D1321] border-[#1E293B] text-[#64748B] cursor-not-allowed"
                  />
                  <p className="text-body-sm text-[#64748B] mt-1">{t('由登录服务统一管理')}</p>
                </div>

                {/* Role */}
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">{t('角色')}</Label>
                  <div className="relative max-w-[240px]">
                    <select value={profileRole} disabled className="w-full h-10 px-3 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#94A3B8] appearance-none cursor-not-allowed">
                      <option value={profileRole}>{t(profileRole)}</option>
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                  </div>
                </div>
              </div>
            </motion.div>

            {cloudSession?.configured && cloudSession.authenticated && (
              <motion.div variants={cardVariant}>
                <h2 className="mb-1 text-heading-sm text-[#F1F5F9]">账户安全</h2>
                <p className="mb-4 text-body-sm text-[#64748B]">修改登录密码，每个账号每天最多修改一次。</p>
                <form
                  className="glass-card space-y-4 rounded-[16px] border border-[#1E293B] p-5"
                  onSubmit={(event) => { event.preventDefault(); void handlePasswordChange() }}
                >
                  <div className="grid gap-4 md:grid-cols-3">
                    <div>
                      <Label className="mb-1.5 block text-body-sm text-[#94A3B8]">当前密码</Label>
                      <Input value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} type="password" autoComplete="current-password" className="border-[#1E293B] bg-[#0D1321] text-[#F1F5F9]" />
                    </div>
                    <div>
                      <Label className="mb-1.5 block text-body-sm text-[#94A3B8]">新密码</Label>
                      <Input value={newPassword} onChange={(event) => setNewPassword(event.target.value)} type="password" autoComplete="new-password" className="border-[#1E293B] bg-[#0D1321] text-[#F1F5F9]" />
                    </div>
                    <div>
                      <Label className="mb-1.5 block text-body-sm text-[#94A3B8]">确认新密码</Label>
                      <Input value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} type="password" autoComplete="new-password" className="border-[#1E293B] bg-[#0D1321] text-[#F1F5F9]" />
                    </div>
                  </div>
                  {passwordError && <p className="text-sm text-[#FCA5A5]">{passwordError}</p>}
                  {passwordMessage && <p className="text-sm text-[#6EE7B7]">{passwordMessage}</p>}
                  <div className="flex justify-end">
                    <Button type="submit" disabled={passwordSaving || !currentPassword || !newPassword || !confirmPassword} className="bg-[#6366F1] text-white hover:bg-[#818CF8]">
                      {passwordSaving ? '正在保存' : '修改密码'}
                    </Button>
                  </div>
                </form>
              </motion.div>
            )}

            {/* Team */}
            <motion.div variants={cardVariant}>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-heading-sm text-[#F1F5F9] mb-1">{t('团队成员')}</h2>
                  <p className="text-body-sm text-[#64748B]">{t('管理团队成员与访问权限。')}</p>
                </div>
                <Button
                  size="sm"
                  className="bg-[#6366F1] hover:bg-[#818CF8] text-white"
                  onClick={() => showNotice(t('团队成员邀请功能尚未开放'))}
                >
                  <Plus className="w-4 h-4 mr-1.5" />
                  {t('添加成员')}
                </Button>
              </div>
              <div className="glass-card rounded-[16px] border border-[#1E293B] overflow-hidden">
                <div className="divide-y divide-[#1E293B]">
                  {teamMembers.map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between px-5 py-4 hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-sm font-semibold text-white">
                          {(member.name || '成员').trim().charAt(0) || '成'}
                        </div>
                        <div>
                          <p className="text-body-md font-medium text-[#F1F5F9]">{t(member.name)}</p>
                          <p className="text-body-sm text-[#64748B]">{member.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge
                          variant="outline"
                          className={cn(
                            'text-xs',
                            member.status === 'active'
                              ? 'border-[#10B981] text-[#10B981] bg-[rgba(16,185,129,0.1)]'
                              : 'border-[#F59E0B] text-[#F59E0B] bg-[rgba(245,158,11,0.1)]'
                          )}
                        >
                          {t(member.status === 'active' ? '活跃' : '待激活')}
                        </Badge>
                        <span className="text-body-sm text-[#94A3B8]">{t(member.role)}</span>
                        <button
                          onClick={async () => {
                            setTeamMembers((prev) => prev.filter((m) => m.id !== member.id))
                            setUnsaved(true)
                            try { await apiDel(`/api/data/team/${member.id}`) } catch { reloadTeam() }
                          }}
                          className="p-1.5 rounded-lg text-[#64748B] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.1)] transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
          </AnimatePresence>
        </motion.section>
      </div>

      <AnimatePresence>
        {notice && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            className="fixed right-6 top-20 z-50 flex max-w-sm items-center gap-2 rounded-lg border border-[#334155] bg-[#111827]/95 px-4 py-3 text-sm text-[#E2E8F0] shadow-card-lift backdrop-blur-md"
            role="status"
          >
            <Info className="h-4 w-4 shrink-0 text-[#818CF8]" />
            {notice}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ========== SAVE / RESET BAR ========== */}
      <AnimatePresence>
        {unsaved && (
          <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            transition={{ duration: 0.4, ease: easeOutExpo }}
            className="fixed bottom-0 right-0 left-0 lg:left-[260px] bg-[#111827]/95 backdrop-blur-md border-t border-[#1E293B] px-6 py-4 z-40"
          >
            <div className="flex items-center justify-between max-w-[1000px] mx-auto">
              <Button
                variant="ghost"
                onClick={handleReset}
                className="text-[#94A3B8] hover:text-[#F1F5F9]"
              >
                <RotateCcw className="w-4 h-4 mr-2" />
                {t('恢复默认')}
              </Button>
              <div className="flex items-center gap-3">
                <span className="text-body-sm text-[#F59E0B]">{t('有未保存的更改')}</span>
                <motion.div
                  animate={{
                    boxShadow: [
                      '0 0 20px rgba(99,102,241,0.2)',
                      '0 0 30px rgba(99,102,241,0.4)',
                      '0 0 20px rgba(99,102,241,0.2)',
                    ],
                  }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="rounded-lg"
                >
                  <Button
                    onClick={handleSave}
                    className="bg-[#6366F1] hover:bg-[#818CF8] text-white"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    {t('保存更改')}
                  </Button>
                </motion.div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AvatarSettingsDialog open={avatarSettingsOpen} onClose={() => setAvatarSettingsOpen(false)} onError={showNotice} />
    </motion.div>
  )
}
