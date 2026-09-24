import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { fetchCloudSession, type CloudSession } from '@/lib/api'
import CloudLogin from '@/pages/CloudLogin'
import { translateCurrent, useI18n } from '@/lib/i18n'
import { CLOUD_KEEP_LOGIN_KEY, CLOUD_LOGOUT_EVENT } from '@/lib/cloudSession'

// 设备绑定策略:只要本机曾经登录成功过,云端瞬时故障(换 IP/超时/网络抖动)
// 一律不弹登录页,保持离线可用;只有从未登录过或明确退出才需要登录。
export default function CloudAuthGate({ children }: { children: ReactNode }) {
  const { t } = useI18n();

  const [session, setSession] = useState<CloudSession | null>(null)
  const [reauthRequired, setReauthRequired] = useState(false)
  const locallyLoggedOut = useRef(false)

  const reload = useCallback(async () => {
    try {
      const next = await fetchCloudSession()
      if (locallyLoggedOut.current) {
        setSession({ configured: true, authenticated: false })
        return
      }
      if (next.authenticated) {
        localStorage.setItem(CLOUD_KEEP_LOGIN_KEY, '1')
      }
      setSession(next)
    } catch {
      // 本地后端不可达:曾登录过的设备保持在场(离线可用)
      if (!locallyLoggedOut.current && localStorage.getItem(CLOUD_KEEP_LOGIN_KEY) === '1') {
        setSession({ configured: true, authenticated: true, offline: true })
      } else {
        setSession({ configured: true, authenticated: false, get message() { return translateCurrent("账户服务暂时不可用") } })
      }
    }
  }, [])

  useEffect(() => {
    void reload()
    const handleExpired = () => setReauthRequired(true)
    const handleLogout = () => {
      locallyLoggedOut.current = true
      localStorage.removeItem(CLOUD_KEEP_LOGIN_KEY)
      setReauthRequired(false)
      setSession({ configured: true, authenticated: false })
    }
    window.addEventListener('szyg:cloud-session-expired', handleExpired)
    window.addEventListener(CLOUD_LOGOUT_EVENT, handleLogout)
    return () => {
      window.removeEventListener('szyg:cloud-session-expired', handleExpired)
      window.removeEventListener(CLOUD_LOGOUT_EVENT, handleLogout)
    }
  }, [reload])

  const handleLoginSuccess = useCallback(async () => {
    locallyLoggedOut.current = false
    setReauthRequired(false)
    localStorage.setItem(CLOUD_KEEP_LOGIN_KEY, '1')
    await reload()
  }, [reload])

  if (!session) {
    return <div className="grid min-h-screen place-items-center bg-[#0B0F1A]"><LoaderCircle className="h-6 w-6 animate-spin text-[#818CF8]" /></div>
  }
  // Both distributable editions require a cloud identity. Do not silently
  // unlock the application if a packaged/local service loses its cloud
  // configuration: that behaviour makes a fresh installation look as though
  // it has already been signed in.
  if (!session.configured || reauthRequired || !session.authenticated) {
    const message = reauthRequired
      ? t("登录状态已过期，请重新登录")
      : session.message || (!session.configured ? t("登录服务尚未配置，请联系管理员") : '')
    return <CloudLogin initialMessage={message} onSuccess={handleLoginSuccess} />
  }
  return <>{children}</>
}
