import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { fetchCloudSession, type CloudSession } from '@/lib/api'
import CloudLogin from '@/pages/CloudLogin'

// 设备绑定策略:只要本机曾经登录成功过,云端瞬时故障(换 IP/超时/网络抖动)
// 一律不弹登录页,保持离线可用;只有从未登录过或明确退出才需要登录。
const KEEP_LOGIN_KEY = 'szyg.cloud.keep-login'

export default function CloudAuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<CloudSession | null>(null)
  const [reauthRequired, setReauthRequired] = useState(false)

  const reload = useCallback(async () => {
    try {
      const next = await fetchCloudSession()
      if (next.authenticated) {
        localStorage.setItem(KEEP_LOGIN_KEY, '1')
      }
      setSession(next)
    } catch {
      // 本地后端不可达:曾登录过的设备保持在场(离线可用)
      if (localStorage.getItem(KEEP_LOGIN_KEY) === '1') {
        setSession({ configured: true, authenticated: true, offline: true })
      } else {
        setSession({ configured: true, authenticated: false, message: '账户服务暂时不可用' })
      }
    }
  }, [])

  useEffect(() => {
    void reload()
    const handleExpired = () => setReauthRequired(true)
    window.addEventListener('szyg:cloud-session-expired', handleExpired)
    return () => window.removeEventListener('szyg:cloud-session-expired', handleExpired)
  }, [reload])

  const handleLoginSuccess = useCallback(async () => {
    setReauthRequired(false)
    localStorage.setItem(KEEP_LOGIN_KEY, '1')
    await reload()
  }, [reload])

  if (!session) {
    return <div className="grid min-h-screen place-items-center bg-[#0B0F1A]"><LoaderCircle className="h-6 w-6 animate-spin text-[#818CF8]" /></div>
  }
  if (!session.configured) return <>{children}</>
  if (reauthRequired || !session.authenticated) {
    return <CloudLogin initialMessage={reauthRequired ? '登录状态已过期，请重新登录' : session.message} onSuccess={handleLoginSuccess} />
  }
  return <>{children}</>
}