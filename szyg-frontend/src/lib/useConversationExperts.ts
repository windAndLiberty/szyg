import { useCallback, useEffect, useRef, useState } from 'react'
import { apiGet, apiPost } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

export interface ConversationExpert {
  slug: string
  name: string
  description: string
  division: string
  emoji?: string
}

export interface ActiveConversationExpert extends ConversationExpert {
  source: 'manual' | 'auto'
}

interface Options {
  agentId?: string | null
  sessionKey?: string | null
  createSession: () => Promise<string | null | undefined>
  disabled?: boolean
}

type Snapshot = { active: ActiveConversationExpert[] }
const base = '/api/agency/conversation-experts'

export function useConversationExperts({ agentId, sessionKey, createSession, disabled = false }: Options) {
  const { locale } = useI18n()
  const [catalog, setCatalog] = useState<ConversationExpert[]>([])
  const [selection, setSelection] = useState<{ key: string; active: ActiveConversationExpert[] } | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const scope = useRef({ agentId, sessionKey, locale, disabled })
  scope.current = { agentId, sessionKey, locale, disabled }
  const mutation = useRef(false)
  const revision = useRef(0)
  const loadedLocale = useRef('')
  const catalogTask = useRef<{ lang: string; promise: Promise<void> } | null>(null)

  const loadCatalog = useCallback(() => {
    if (loadedLocale.current === locale) return Promise.resolve()
    if (catalogTask.current?.lang === locale) return catalogTask.current.promise
    setLoading(true)
    setError('')
    const promise = apiGet<ConversationExpert[]>(`${base}/catalog?locale=${encodeURIComponent(locale)}`)
      .then(rows => {
        if (scope.current.locale !== locale) return
        loadedLocale.current = locale
        setCatalog(rows)
      }).catch(reason => {
        if (scope.current.locale === locale) setError(String(reason?.message || reason))
      }).finally(() => {
        if (catalogTask.current?.lang === locale) {
          catalogTask.current = null
          setLoading(false)
        }
      })
    catalogTask.current = { lang: locale, promise }
    return promise
  }, [locale])

  const refresh = useCallback(async () => {
    const seq = ++revision.current
    if (!agentId || !sessionKey || disabled) return
    const query = new URLSearchParams({ agent_id: agentId, session_key: sessionKey, locale })
    try {
      const result = await apiGet<Snapshot>(`${base}?${query}`)
      if (seq === revision.current && scope.current.sessionKey === sessionKey) {
        setSelection({ key: sessionKey, active: result.active })
      }
    } catch (reason) {
      if (seq === revision.current) setError(reason instanceof Error ? reason.message : String(reason))
    }
  }, [agentId, sessionKey, disabled, locale])

  useEffect(() => {
    setError('')
    void refresh()
    const unsubscribe = window.electronAPI?.openClaw?.runs.subscribe(event => {
      if (event.type === 'experts.changed' && event.payload.sessionKey === sessionKey && event.payload.agentId === agentId) void refresh()
    })
    return () => { revision.current++; unsubscribe?.() }
  }, [agentId, sessionKey, refresh])

  const change = useCallback(async (action: 'attach' | 'detach', slug: string) => {
    if (disabled || !agentId || mutation.current) return
    mutation.current = true
    setBusy(true)
    setError('')
    try {
      const key = sessionKey || (action === 'attach' && await createSession())
      if (!key || scope.current.agentId !== agentId || scope.current.disabled) return
      const result = await apiPost<Snapshot>(`${base}/${action}`, { agent_id: agentId, session_key: key, slug, locale })
      if (scope.current.agentId === agentId && (!scope.current.sessionKey || scope.current.sessionKey === key)) {
        revision.current++
        setSelection({ key, active: result.active })
      }
    } catch (reason) {
      if (scope.current.agentId === agentId) setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      mutation.current = false
      setBusy(false)
    }
  }, [agentId, sessionKey, createSession, disabled, locale])

  return {
    catalog, active: !disabled && selection?.key === sessionKey ? selection?.active ?? [] : [],
    loading, busy, error, loadCatalog, refresh,
    attach: (slug: string) => change('attach', slug),
    detach: (slug: string) => change('detach', slug),
  }
}
