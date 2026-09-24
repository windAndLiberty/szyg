import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, LoaderCircle, RefreshCw, X } from 'lucide-react'
import {
  fetchCloudSession,
  loginCloud,
  refreshCloudSession,
  toUserFacingMessage,
  type CloudSession,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import CloudLogin from '@/pages/CloudLogin'
import { useI18n } from '@/lib/i18n'

const STORAGE_KEY = 'szyg.cloud.auth-expired.dismissed'
const AUTH_EXPIRED_EVENT = 'szyg:cloud-auth-expired'

export default function CloudAuthExpiredBanner() {
  const { t } = useI18n()
  const [message, setMessage] = useState('')
  const [visible, setVisible] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [loginOpen, setLoginOpen] = useState(false)
  const [error, setError] = useState('')

  const show = useCallback((detail?: string) => {
    setMessage(detail || t("服务授权已到期，智能服务暂不可用，请重新登录或联系管理员续期"))
    setVisible(true)
  }, [])

  const hide = useCallback(() => setVisible(false), [])

  // 监听全局事件 + 启动时拉取一次 session
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail
      // 一旦再次触发事件，撤销用户先前的 dismiss 选择，确保他能看到最新提示
      try { sessionStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
      show(detail)
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handler)

    let cancelled = false
    void (async () => {
      try {
        const next: CloudSession = await fetchCloudSession()
        if (cancelled) return
        if (next.authorization_error) show(next.authorization_error)
      } catch {
        /* 离线情况下拉取失败不展示 */
      }
    })()

    return () => {
      cancelled = true
      window.removeEventListener(AUTH_EXPIRED_EVENT, handler)
    }
  }, [show])

  const handleDismiss = useCallback(() => {
    try { sessionStorage.setItem(STORAGE_KEY, '1') } catch { /* ignore */ }
    hide()
  }, [hide])

  const handleRefresh = useCallback(async () => {
    if (refreshing) return
    setRefreshing(true)
    setError('')
    try {
      const result = await refreshCloudSession()
      if (!result.expired) {
        hide()
        // 状态恢复后重新拉取一次 session,确保 CloudAuthGate 等消费方拿到最新档案
        try { await fetchCloudSession() } catch { /* ignore */ }
      } else {
        setError(result.authorization_error || t("服务授权仍然到期，请联系管理员续期后再刷新"))
      }
    } catch (err) {
      setError(toUserFacingMessage(err as Error, t("刷新授权状态失败，请稍后重试")))
    } finally {
      setRefreshing(false)
    }
  }, [refreshing, hide])

  const handleLoginSuccess = useCallback(async () => {
    setLoginOpen(false)
    hide()
    try { await fetchCloudSession() } catch { /* ignore */ }
  }, [hide])

  if (!visible && !loginOpen) return null

  return (
    <>
      {visible && (
        <div
          role="alert"
          aria-live="assertive"
          className="fixed inset-x-0 bottom-0 z-[140] border-t-2 border-[#F59E0B] bg-[#1A1304]/95 backdrop-blur shadow-[0_-12px_40px_rgba(0,0,0,0.55)]"
        >
          <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
            <div className="flex flex-1 items-start gap-3 text-[#FCD34D] sm:items-center">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 sm:mt-0" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-[#FDE68A]">{t("服务授权已到期")}</p>
                <p className="mt-0.5 text-xs leading-5 text-[#FCD34D]/85">
                  {message}
                  {error && <span className="ml-2 text-[#FCA5A5]">· {error}</span>}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void handleRefresh()}
                disabled={refreshing}
                className="border border-[#3F2E0A] bg-[#221706] text-[#FDE68A] hover:bg-[#2D1F08]"
              >
                {refreshing ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}

                {t("我已续期，刷新状态")}
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => setLoginOpen(true)}
                className="bg-[#F59E0B] text-[#1A1304] hover:bg-[#FBBF24]"
              >

                {t("重新登录")}
              </Button>
              <button
                type="button"
                onClick={handleDismiss}
                aria-label={t("关闭提示")}
                className="rounded p-1.5 text-[#FCD34D]/70 transition-colors hover:bg-[#2A1D05] hover:text-[#FDE68A]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {loginOpen && (
        <div className="fixed inset-0 z-[160] bg-[#0B0F1A]">
          <CloudLogin
            initialMessage={t("服务授权已到期，请重新登录以恢复智能服务")}
            onSuccess={async () => {
              // 重新登录成功后再探测一次授权状态,把 banner 状态彻底拉回正常。
              try {
                const next = await fetchCloudSession()
                if (next.authorization_error) {
                  show(next.authorization_error)
                  setLoginOpen(false)
                  return
                }
                try { await refreshCloudSession() } catch { /* ignore */ }
              } catch { /* ignore */ }
              await handleLoginSuccess()
            }}
          />
        </div>
      )}
    </>
  )
}

// 复用的内部 hook：暴露提示能力给其它需要主动弹的组件
export function useCloudAuthExpiredHint() {
  return useCallback((detail?: string) => {
    if (typeof window === 'undefined') return
    window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, { detail: detail || '' }))
  }, [])
}
