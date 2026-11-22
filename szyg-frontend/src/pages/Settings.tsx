import { useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router'
import { Check, CircleUserRound, Globe, Laptop, LogOut, Monitor, Moon, SlidersHorizontal, Sun, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import McpConnections from '@/components/McpConnections'
import UserAvatar from '@/components/ui/UserAvatar'
import AvatarSettingsDialog from '@/components/ui/AvatarSettingsDialog'
import { useAsync } from '@/lib/hooks'
import { useTheme } from '@/lib/theme'
import { useI18n } from '@/lib/i18n'
import { desktopAlertsEnabled, setDesktopAlerts, setWorkIndicators, workIndicatorsEnabled } from '@/lib/workNotifications'
import { logoutCloudSession } from '@/lib/cloudSession'
import { fetchCloudSession, fetchCloudDevices, loginCloud, requestPasswordResetCode, resetCloudPassword, revokeCloudDevice, getErrorMessage, type CloudDevice } from '@/lib/api'

const sections = [
  { id: 'general', label: '通用设置', icon: SlidersHorizontal },
  { id: 'account', label: '账户管理', icon: CircleUserRound },
  { id: 'mcp', label: 'mcp.title', icon: Globe },
] as const

function SettingRow({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <div className="settings-row">
    <div className="min-w-0"><p className="font-medium">{label}</p>{hint && <p className="mt-1 text-xs leading-5 text-muted-foreground">{hint}</p>}</div>
    {children}
  </div>
}

function General() {
  const { theme, setTheme } = useTheme()
  const { t, locale, setLocale } = useI18n()
  const [indicators, setIndicators] = useState(workIndicatorsEnabled)
  const [desktop, setDesktop] = useState(() => desktopAlertsEnabled() && 'Notification' in window && Notification.permission === 'granted')
  const [notice, setNotice] = useState('')
  async function toggleDesktop(next: boolean) {
    setNotice('')
    if (next) {
      try {
        if (!('Notification' in window) || await Notification.requestPermission() !== 'granted') {
          setNotice(t('settings.alertPermission'))
          return
        }
      } catch { setNotice(t('settings.alertPermission')); return }
    }
    setDesktopAlerts(next)
    setDesktop(next)
  }
  return <div className="space-y-8">
    <fieldset>
      <legend className="settings-title">{t('外观')}</legend>
      <div className="theme-choices">
        {([{ id: 'light', label: 'settings.light', icon: Sun }, { id: 'dark', label: '深色', icon: Moon }, { id: 'system', label: '跟随系统', icon: Monitor }] as const).map(({ id, label, icon: Icon }) =>
          <label key={id} className="theme-choice">
            <input type="radio" name="appearance" value={id} checked={theme === id} onChange={() => setTheme(id)} />
            <span aria-hidden="true" className={'theme-preview preview-' + id}><i /><b /><em /></span>
            <span className="flex items-center gap-2"><Icon size={15} aria-hidden="true" />{t(label)}{theme === id && <Check size={15} className="ml-auto" aria-hidden="true" />}</span>
          </label>)}
      </div>
    </fieldset>
    <section className="settings-group">
      <SettingRow label={t('语言')} hint={t('界面显示语言')}>
        <select aria-label={t('语言')} value={locale} onChange={e => setLocale(e.target.value === 'en-US' ? 'en-US' : 'zh-CN')} className="settings-select">
          <option value="zh-CN">{t('中文')}</option><option value="en-US">English</option>
        </select>
      </SettingRow>
    </section>
    <section><h2 className="settings-title">{t('通知')}</h2><div className="settings-group">
      <SettingRow label={t('settings.indicator')} hint={t('settings.indicatorHelp')}>
        <Switch aria-label={t('settings.indicator')} checked={indicators} onCheckedChange={v => { setWorkIndicators(v); setIndicators(v) }} />
      </SettingRow>
      <SettingRow label={t('settings.desktopAlerts')} hint={t('settings.desktopHelp')}>
        <Switch aria-label={t('settings.desktopAlerts')} checked={desktop} onCheckedChange={v => void toggleDesktop(v)} />
      </SettingRow>
    </div>{notice && <p role="status" className="mt-2 text-sm">{notice}</p>}</section>
  </div>
}

function Account() {
  const { t } = useI18n()
  const { data: cloudSession, loading, error, reload: reloadCloudSession } = useAsync(fetchCloudSession)
  const online = Boolean(cloudSession?.authenticated && !cloudSession.offline && cloudSession.user)
  const devices = useAsync(() => online ? fetchCloudDevices() : Promise.resolve({ items: [] as CloudDevice[] }), [online, cloudSession?.user?.id])
  const [avatarSettingsOpen, setAvatarSettingsOpen] = useState(false)
  const [notice, showNotice] = useState('')
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
    if (passwordResendIn <= 0) return
    const timer = window.setInterval(() => setPasswordResendIn((value) => Math.max(0, value - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [passwordResendIn])
  const handlePasswordChange = async () => {
    setPasswordError('')
    setPasswordMessage('')
    if (!passwordVerificationId || !/^\d{6}$/.test(passwordVerificationCode)) {
      setPasswordError(t("请先获取并填写6位邮箱验证码"))
      return
    }
    if (Array.from(newPassword).length < 6) {
      setPasswordError(t("新密码至少需要 6 个字符"))
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
      try {
        await loginCloud(email, newPassword)
      } catch {
        setPasswordError(t('settings.signInAgain'))
        setNewPassword('')
        setConfirmPassword('')
        setPasswordVerificationCode('')
        setPasswordVerificationId('')
        return
      }
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
    if (!window.confirm(t("确定移除设备“{v0}”吗？该设备会立即退出登录。", { v0: device.name || t('登录设备') }))) return
    setDeviceActionId(device.id)
    try {
      await revokeCloudDevice(device.id)
      devices.reload()
      showNotice(t("旧设备已移除"))
    } catch (error) {
      showNotice(getErrorMessage(error, t("设备移除失败")))
    } finally {
      setDeviceActionId('')
    }
  }


  if (loading) return <p role="status">{t('settings.loading')}</p>
  if (error || !cloudSession?.user) return <div role="alert">{error || t('settings.accountUnavailable')} <Button variant="outline" onClick={reloadCloudSession}>{t('重试')}</Button></div>
  const user = cloudSession.user
  return <div className="space-y-8">
    <section><h2 className="settings-title">{t('个人信息')}</h2>
      <div className="settings-group">
        <div className="settings-row"><div className="flex min-w-0 items-center gap-3"><UserAvatar alt={t('我的头像')} className="h-12 w-12" />
          <div className="min-w-0"><p className="truncate font-semibold">{user.display_name || user.email}</p><p className="break-all text-muted-foreground">{user.email}</p></div></div>
          <Button variant="outline" onClick={() => setAvatarSettingsOpen(true)}>{t('更换头像')}</Button></div>
        <SettingRow label={t('角色')}><span>{t(user.role === 'admin' ? '系统管理员' : 'settings.member')}</span></SettingRow>
        <SettingRow label={t('账户管理')}><Button variant="ghost" disabled={loggingOut} onClick={() => void handleLogout()}><LogOut size={15}/>{t('退出登录')}</Button></SettingRow>
      </div>
    </section>
    {!online && <p role="status">{t('settings.offline')}</p>}
    {online && <><section><h2 className="settings-title">{t('登录设备')}</h2>
      {devices.loading ? <p role="status">{t('settings.loading')}</p> : devices.error ? <div role="alert">{devices.error} <Button variant="outline" onClick={devices.reload}>{t('重试')}</Button></div>
        : <div className="settings-group">{devices.data?.items.filter(d => d.status === 'active').map(device =>
          <SettingRow key={device.id} label={device.name || t('登录设备')} hint={device.last_seen_at ? new Date(device.last_seen_at).toLocaleString() : device.app_version}>
            {device.id === cloudSession.device?.id ? <span className="inline-flex shrink-0 items-center gap-2 text-xs text-muted-foreground"><Laptop size={15}/>{t('当前设备')}</span>
              : <Button variant="ghost" disabled={Boolean(deviceActionId)} onClick={() => void handleRevokeDevice(device)}><Trash2 size={14}/>{t('移除')}</Button>}
          </SettingRow>)}{!devices.data?.items.some(d => d.status === 'active') && <p className="settings-row">{t('settings.noDevices')}</p>}</div>}
    </section><section><h2 className="settings-title">{t('账户安全')}</h2>
      <form className="settings-group space-y-4 p-5" onSubmit={e => { e.preventDefault(); void handlePasswordChange() }}>
        <div className="space-y-2"><label htmlFor="account-verification-code">{t('邮箱验证码')}</label><div className="flex gap-2">
          <Input id="account-verification-code" value={passwordVerificationCode} onChange={e => setPasswordVerificationCode(e.target.value.replace(/\D/g,'').slice(0,6))} inputMode="numeric" autoComplete="one-time-code" />
          <Button type="button" variant="outline" disabled={passwordCodeLoading || passwordResendIn > 0} onClick={() => void handleSendPasswordCode()}>{passwordResendIn ? passwordResendIn+'s' : t('发送验证码')}</Button>
        </div></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-2"><span>{t('新密码')}</span><Input type="password" autoComplete="new-password" placeholder={t('auth.passwordHint')} value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label>
          <label className="space-y-2"><span>{t('确认新密码')}</span><Input type="password" autoComplete="new-password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} /></label>
        </div>
        {passwordError && <p role="alert" className="text-destructive">{passwordError}</p>}{passwordMessage && <p role="status">{passwordMessage}</p>}
        <Button disabled={passwordSaving || !passwordVerificationId || passwordVerificationCode.length !== 6 || !newPassword || !confirmPassword}>{t('修改密码')}</Button>
      </form></section></>}
    {notice && <p role="status">{notice}</p>}
    <AvatarSettingsDialog open={avatarSettingsOpen} onClose={() => setAvatarSettingsOpen(false)} onError={showNotice}/>
  </div>
}

export default function SettingsPage() {
  const { t } = useI18n()
  const { hash } = useLocation()
  const active = sections.find(s => '#' + s.id === hash) || sections[0]
  return <div className="settings-shell">
    <nav aria-label={t('系统配置')} className="settings-nav">{sections.map(({ id, icon: Icon, label }) =>
      <Link key={id} to={id === 'general' ? '/settings' : '/settings#' + id} aria-current={id === active.id ? 'page' : undefined}><Icon size={16} aria-hidden="true"/>{t(label)}</Link>)}</nav>
    <div className="settings-panel">
      {active.id !== 'mcp' && <h1 className="settings-heading">{t(active.label)}</h1>}
      {active.id === 'general' ? <General/> : active.id === 'account' ? <Account/> : <McpConnections/>}
    </div>
  </div>
}
