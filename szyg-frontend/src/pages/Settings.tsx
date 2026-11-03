import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Settings,
  User,
  Sun,
  Moon,
  Monitor,
  Globe,
  Save,
  RotateCcw,
  Check,
  ChevronDown,
  Info,
  LogOut,
  Laptop,
  LoaderCircle,
  MailCheck,
  Trash2,
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
import { translateCurrent, useI18n } from '@/lib/i18n'
import { logoutCloudSession } from '@/lib/cloudSession'
import {
  getCurrentUser,
  fetchCloudSession,
  fetchCloudDevices,
  loginCloud,
  requestPasswordResetCode,
  resetCloudPassword,
  revokeCloudDevice,
  getErrorMessage,
  type CloudDevice,
  type CloudSession,
} from '@/lib/api'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type SettingsTab = 'general' | 'account'

const easeOutExpo = [0.16, 1, 0.3, 1] as [number, number, number, number]

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const settingsTabs: { id: SettingsTab; label: string; icon: typeof Settings }[] = [
  { id: 'general', get label() { return translateCurrent("通用设置") }, icon: Settings },
  { id: 'account', get label() { return translateCurrent("账户管理") }, icon: User },
]

const notificationEvents = [
  { id: 'task_complete', get label() { return translateCurrent("任务执行完成") }, checked: true },
  { id: 'agent_error', get label() { return translateCurrent("数字员工执行出错") }, checked: true },
  { id: 'report_ready', get label() { return translateCurrent("报告生成完毕") }, checked: true },
  { id: 'daily_summary', get label() { return translateCurrent("每日执行摘要") }, checked: true },
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

  /* Account */
  const currentUser = getCurrentUser()
  const [profileName, setProfileName] = useState(currentUser?.username ?? 'admin')
  const [profileEmail] = useState(`${currentUser?.username ?? 'admin'}@szyg.local`)
  const [profileRole, setProfileRole] = useState(t("系统管理员"))
  const { data: cloudSession, reload: reloadCloudSession } = useAsync<CloudSession>(fetchCloudSession)
  const [cloudDevices, setCloudDevices] = useState<CloudDevice[]>([])
  const [deviceActionId, setDeviceActionId] = useState('')
  const [passwordVerificationCode, setPasswordVerificationCode] = useState('')
  const [passwordVerificationId, setPasswordVerificationId] = useState('')
  const [passwordCodeLoading, setPasswordCodeLoading] = useState(false)
  const [passwordResendIn, setPasswordResendIn] = useState(0)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [loggingOut, setLoggingOut] = useState(false)
  useEffect(() => {
    if (cloudSession?.user) {
      setProfileName(cloudSession.user.display_name)
      setProfileRole(cloudSession.user.role === 'admin' ? t("系统管理员") : t("内测用户"))
    }
  }, [cloudSession])
  useEffect(() => {
    if (!cloudSession?.authenticated) {
      setCloudDevices([])
      return
    }
    void fetchCloudDevices().then((result) => setCloudDevices(result.items)).catch(() => setCloudDevices([]))
  }, [cloudSession?.authenticated, cloudSession?.device?.id])
  useEffect(() => {
    if (passwordResendIn <= 0) return
    const timer = window.setInterval(() => setPasswordResendIn((value) => Math.max(0, value - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [passwordResendIn])
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
    if (!passwordVerificationId || !/^\d{6}$/.test(passwordVerificationCode)) {
      setPasswordError(t("请先获取并填写6位邮箱验证码"))
      return
    }
    if (newPassword.length < 10) {
      setPasswordError(t("新密码至少需要 10 个字符"))
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError(t("两次输入的新密码不一致"))
      return
    }
    setPasswordSaving(true)
    try {
      const email = cloudSession?.user?.email || ''
      await resetCloudPassword(email, newPassword, passwordVerificationId, passwordVerificationCode)
      await loginCloud(email, newPassword)
      setPasswordVerificationCode('')
      setPasswordVerificationId('')
      setPasswordResendIn(0)
      setNewPassword('')
      setConfirmPassword('')
      setPasswordMessage(t("密码已更新"))
      await reloadCloudSession()
    } catch (error) {
      setPasswordError(getErrorMessage(error, t("密码修改失败")))
    } finally {
      setPasswordSaving(false)
    }
  }

  const handleSendPasswordCode = async () => {
    const email = cloudSession?.user?.email || ''
    if (!email || passwordCodeLoading || passwordResendIn > 0) return
    setPasswordCodeLoading(true)
    setPasswordError('')
    setPasswordMessage('')
    try {
      const challenge = await requestPasswordResetCode(email)
      setPasswordVerificationId(challenge.verification_id)
      setPasswordResendIn(challenge.retry_after_seconds || 60)
      setPasswordMessage(t("验证码已发送至 {v0}，10分钟内有效", { v0: challenge.email }))
    } catch (error) {
      setPasswordError(getErrorMessage(error, t("验证码发送失败，请稍后再试")))
    } finally {
      setPasswordCodeLoading(false)
    }
  }

  const handleLogout = async () => {
    if (loggingOut) return
    setLoggingOut(true)
    try {
      await logoutCloudSession()
    } finally {
      setLoggingOut(false)
    }
  }

  const handleRevokeDevice = async (device: CloudDevice) => {
    if (device.id === cloudSession?.device?.id || deviceActionId) return
    if (!window.confirm(t("确定移除设备“{v0}”吗？该设备会立即退出登录。", { v0: device.name || 'Windows PC' }))) return
    setDeviceActionId(device.id)
    try {
      await revokeCloudDevice(device.id)
      const result = await fetchCloudDevices()
      setCloudDevices(result.items)
      showNotice(t("旧设备已移除"))
    } catch (error) {
      showNotice(getErrorMessage(error, t("设备移除失败")))
    } finally {
      setDeviceActionId('')
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
                      { value: 'light', icon: Sun, label: t("亮色") },
                      { value: 'dark', icon: Moon, label: t("深色") },
                      { value: 'system', icon: Monitor, label: t("跟随系统") },
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
                      <option value="zh-CN">{t("中文")}</option>
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

        {/* ==================== TAB 2: 账户管理 ==================== */}
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
                      <div><p className="text-sm font-medium text-[#F1F5F9]">{t("当前设备已授权")}</p><p className="mt-1 text-xs text-[#64748B]">{cloudSession.device?.name || 'Windows PC'}</p></div>
                    </div>
                    <Badge className="border-[#10B981]/40 bg-[#10B981]/10 text-[#6EE7B7]">{t("在线")}</Badge>
                  </div>
                  {cloudDevices.some((device) => device.status === 'active') && <div className="mt-5 space-y-2 border-t border-[#26334B] pt-4">
                    <p className="mb-2 text-xs font-medium text-[#94A3B8]">{t("登录设备")}</p>
                    {cloudDevices.filter((device) => device.status === 'active').map((device) => {
                      const current = device.id === cloudSession.device?.id
                      return <div key={device.id} className="flex items-center gap-3 rounded-lg border border-[#26334B] bg-[#0D1321]/60 px-3 py-2.5">
                        <Laptop className="h-4 w-4 shrink-0 text-[#94A3B8]" />
                        <div className="min-w-0 flex-1"><p className="truncate text-sm text-[#E2E8F0]">{device.name || 'Windows PC'}</p><p className="mt-0.5 text-xs text-[#64748B]">{device.last_seen_at ? new Date(device.last_seen_at).toLocaleString() : device.app_version}</p></div>
                        {current ? <Badge className="border-[#10B981]/30 bg-[#10B981]/10 text-[#6EE7B7]">{t("当前设备")}</Badge> : <button type="button" onClick={() => void handleRevokeDevice(device)} disabled={Boolean(deviceActionId)} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[#FCA5A5] hover:bg-[#7F1D1D]/25 disabled:opacity-50">{deviceActionId === device.id ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}{t("移除")}</button>}
                      </div>
                    })}
                  </div>}
                  <button onClick={() => void handleLogout()} disabled={loggingOut} className="mt-5 inline-flex items-center gap-2 text-sm text-[#94A3B8] transition-colors hover:text-[#F1F5F9] disabled:cursor-not-allowed disabled:opacity-60"><LogOut className="h-4 w-4" />{loggingOut ? t("正在退出…") : t("退出登录")}</button>
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
                    alt={t("我的头像")}
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
                <h2 className="mb-1 text-heading-sm text-[#F1F5F9]">{t("账户安全")}</h2>
                <p className="mb-4 text-body-sm text-[#64748B]">{t("验证码将发送到账号邮箱；每个账号每天最多修改一次密码。")}</p>
                <form
                  className="glass-card space-y-4 rounded-[16px] border border-[#1E293B] p-5"
                  onSubmit={(event) => { event.preventDefault(); void handlePasswordChange() }}
                >
                  <div className="grid gap-4 md:grid-cols-3">
                    <div>
                      <Label className="mb-1.5 block text-body-sm text-[#94A3B8]">{t("邮箱验证码")}</Label>
                      <div className="flex gap-2">
                        <Input value={passwordVerificationCode} onChange={(event) => setPasswordVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" placeholder={t("6位邮箱验证码")} className="border-[#1E293B] bg-[#0D1321] text-[#F1F5F9]" />
                        <Button type="button" variant="secondary" className="shrink-0 border border-[#334155] bg-[#172033] text-[#E2E8F0] hover:bg-[#25314A]" disabled={passwordCodeLoading || passwordResendIn > 0} onClick={() => void handleSendPasswordCode()}>
                          {passwordCodeLoading ? <LoaderCircle className="mr-1.5 h-4 w-4 animate-spin" /> : <MailCheck className="mr-1.5 h-4 w-4" />}
                          {passwordResendIn > 0 ? `${passwordResendIn}s` : passwordVerificationId ? t("重新发送") : t("发送验证码")}
                        </Button>
                      </div>
                    </div>
                    <div>
                      <Label className="mb-1.5 block text-body-sm text-[#94A3B8]">{t("新密码")}</Label>
                      <Input value={newPassword} onChange={(event) => setNewPassword(event.target.value)} type="password" autoComplete="new-password" className="border-[#1E293B] bg-[#0D1321] text-[#F1F5F9]" />
                    </div>
                    <div>
                      <Label className="mb-1.5 block text-body-sm text-[#94A3B8]">{t("确认新密码")}</Label>
                      <Input value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} type="password" autoComplete="new-password" className="border-[#1E293B] bg-[#0D1321] text-[#F1F5F9]" />
                    </div>
                  </div>
                  {passwordError && <p className="text-sm text-[#FCA5A5]">{passwordError}</p>}
                  {passwordMessage && <p className="text-sm text-[#6EE7B7]">{passwordMessage}</p>}
                  <div className="flex justify-end">
                    <Button type="submit" disabled={passwordSaving || !passwordVerificationId || passwordVerificationCode.length !== 6 || !newPassword || !confirmPassword} className="bg-[#6366F1] text-white hover:bg-[#818CF8]">
                      {passwordSaving ? t("正在保存") : t("修改密码")}
                    </Button>
                  </div>
                </form>
              </motion.div>
            )}

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
