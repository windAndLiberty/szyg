import { useEffect, useRef, useState } from 'react'
import { useI18n } from '@/lib/i18n'

type Resource = {name: string; description: string; title?: string; domain?: string}
type Selection = {selected: string[]; titles?: Record<string, string>}
type Options = {
  agentId: string
  sessionKey: string
  disabled: boolean
  createSession: () => Promise<string | null>
}

const labels = {
  skills: {loadFailed:'composer.skillLoadFailed', changeFailed:'composer.skillChangeFailed'},
  capabilities: {loadFailed:'composer.capabilityLoadFailed', changeFailed:'composer.capabilityChangeFailed'},
} as const

export function useConversationResources(kind: keyof typeof labels, {agentId, sessionKey, disabled, createSession}: Options) {
  const { t } = useI18n()
  const {loadFailed, changeFailed} = labels[kind]
  const api = window.electronAPI?.openClaw?.[kind]
  const [catalog, setCatalog] = useState<Resource[]>([])
  const [selection, setSelection] = useState<{key: string; result: Selection}>()
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [error, setError] = useState('')
  const catalogRequest = useRef(false)
  const mutation = useRef(false)
  const revision = useRef(0)

  useEffect(() => {
    if (!api?.selection || !sessionKey || !agentId) return
    const request = ++revision.current
    void api.selection({agentId,sessionKey}).then(result => {
      if (revision.current === request) setSelection({key:sessionKey,result})
    }).catch(() => {
      if (revision.current === request && !disabled) setError(t(loadFailed))
    })
    return () => { revision.current++ }
  }, [api,agentId,sessionKey,disabled,t,loadFailed])

  async function loadCatalog() {
    if (!agentId || catalogRequest.current) return
    if (!api?.catalog) { setLoadError(true); return }
    catalogRequest.current = true
    setLoading(true)
    setLoadError(false)
    try {
      const result = await api.catalog({agentId, sessionKey: sessionKey || undefined})
      setCatalog('skills' in result ? result.skills : result.capabilities)
    } catch {
      setLoadError(true)
    } finally {
      catalogRequest.current = false
      setLoading(false)
    }
  }

  async function change(action: 'attach' | 'detach', name: string) {
    if (disabled || !agentId || !api?.[action] || mutation.current || (!sessionKey && action === 'detach')) return
    mutation.current = true
    setBusy(true)
    setError('')
    try {
      const key = sessionKey || await createSession()
      if (!key) throw new Error()
      const result = await api[action]({agentId,sessionKey:key,name})
      revision.current++
      setSelection({key,result})
    } catch {
      setError(t(changeFailed))
    } finally {
      mutation.current = false
      setBusy(false)
    }
  }

  const active = selection?.key === sessionKey ? selection.result : undefined
  return {
    catalog, selected:active?.selected ?? [], titles:active?.titles ?? {},
    loading,busy,loadError,error,loadCatalog,change,
  }
}
