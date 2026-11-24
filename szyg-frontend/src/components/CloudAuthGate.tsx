import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { product } from '@/lib/product'
import { fetchCloudSession, type CloudSession } from '@/lib/api'
import CloudLogin from '@/pages/CloudLogin'
import { translateCurrent, useI18n } from '@/lib/i18n'
import { CLOUD_SIGNED_OUT_KEY, CLOUD_LOGOUT_EVENT } from '@/lib/cloudSession'

const signedOut: CloudSession = { configured: true, authenticated: false }
function retainWorkspace(previous: CloudSession | null, next: CloudSession): CloudSession {
  return previous?.authenticated && next.unavailable
    ? { ...previous, unavailable: true, message: next.message }
    : next
}

const activeCheckInterval = 5 * 60_000
const recoveryInterval = 15_000

export default function CloudAuthGate({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const [session, setSession] = useState<CloudSession | null>(null)
  const pending = useRef<Promise<CloudSession> | null>(null)
  const nextCheck = useRef(0)

  const reload = useCallback(async () => {
    if (localStorage.getItem(CLOUD_SIGNED_OUT_KEY)) {
      nextCheck.current = Infinity
      setSession(signedOut)
      return
    }
    if (pending.current) return
    const request = fetchCloudSession()
    pending.current = request
    try {
      const next = await request
      if (pending.current !== request) return
      nextCheck.current = next.offline || next.unavailable ? Date.now() + recoveryInterval
        : next.authenticated ? Date.now() + activeCheckInterval : Infinity
      setSession(previous => retainWorkspace(previous, next))
    } catch {
      if (pending.current !== request) return
      nextCheck.current = Date.now() + recoveryInterval
      setSession(previous => retainWorkspace(previous, {
        ...signedOut, unavailable: true, message: translateCurrent('账户服务暂时不可用'),
      }))
    } finally {
      if (pending.current === request) pending.current = null
    }
  }, [])

  useEffect(() => {
    let lastActivity = Date.now()
    const checkIfDue = () => {
      if (!document.hidden && Date.now() >= nextCheck.current) void reload()
    }
    const handleActivity = () => {
      lastActivity = Date.now()
      checkIfDue()
    }
    const handleOnline = () => {
      if (nextCheck.current !== Infinity) void reload()
    }
    const handleLogout = () => {
      pending.current = null
      nextCheck.current = Infinity
      setSession(signedOut)
    }
    void reload()
    const timer = window.setInterval(() => {
      if (Date.now() - lastActivity <= 2 * activeCheckInterval) checkIfDue()
    }, recoveryInterval)
    document.addEventListener('visibilitychange', handleActivity)
    window.addEventListener('focus', handleActivity)
    window.addEventListener('pointerdown', handleActivity)
    window.addEventListener('keydown', handleActivity)
    window.addEventListener('online', handleOnline)
    window.addEventListener('szyg:cloud-session-expired', handleOnline)
    window.addEventListener(CLOUD_LOGOUT_EVENT, handleLogout)
    return () => {
      window.clearInterval(timer)
      pending.current = null
      document.removeEventListener('visibilitychange', handleActivity)
      window.removeEventListener('focus', handleActivity)
      window.removeEventListener('pointerdown', handleActivity)
      window.removeEventListener('keydown', handleActivity)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('szyg:cloud-session-expired', handleOnline)
      window.removeEventListener(CLOUD_LOGOUT_EVENT, handleLogout)
    }
  }, [reload])

  const handleLoginSuccess = useCallback(async () => {
    localStorage.removeItem(CLOUD_SIGNED_OUT_KEY)
    pending.current = null
    nextCheck.current = 0
    await reload()
  }, [reload])

  if (!session) {
    return <div role="status" aria-label={t('settings.loading')} className="grid min-h-screen place-items-center bg-background">
      <div className="loading-emblem"><img src={product.logoUrl} alt="" /></div>
    </div>
  }
  if (!session.unavailable && (!session.configured || !session.authenticated)) {
    const message = session.message || (!session.configured ? t("登录服务尚未配置，请联系管理员") : '')
    return <CloudLogin initialMessage={message} onSuccess={handleLoginSuccess} />
  }
  const waiting = !!session.unavailable && (!session.authenticated || Date.now() >= (session.verified_until ?? 0) * 1000)
  return <>
    {waiting && <div className="grid min-h-screen place-items-center bg-background text-foreground">
      <div role="status" className="space-y-4 text-center">
        <p>{session.message || t('账户服务暂时不可用')}</p>
        <button className="text-sm underline" onClick={() => void reload()}>{t('重试')}</button>
      </div>
    </div>}
    {session.authenticated && <div key={session.user?.id} className={waiting ? 'hidden' : 'contents'} inert={waiting}>{children}</div>}
  </>
}
