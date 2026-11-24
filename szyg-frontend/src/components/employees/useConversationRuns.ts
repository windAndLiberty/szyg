import { useCallback, useEffect, useRef, useState } from 'react'

type OpenClaw = NonNullable<NonNullable<Window['electronAPI']>['openClaw']>
export type SessionRun = {
  sessionKey: string
  agentId: string
  runId: string | null
  status: string
}
const terminal = new Set(['completed', 'failed', 'cancelled'])
const scopedSessionKey = /^agent:([a-z0-9_-]+):/i

export function useConversationRuns(api: OpenClaw | undefined, ready: boolean, selectedKey: string, selectedAgent: string,
  refreshHistory: (key: string, agentId: string) => Promise<unknown>,
) {
  const [runs, setRuns] = useState<Record<string, SessionRun>>({})
  const current = useRef<Record<string, SessionRun>>({})
  const completed = useRef(new Set<string>())
  const lookups = useRef(new Set<string>())

  const update = useCallback((sessionKey: string, next?: SessionRun) => {
    const previous = current.current[sessionKey]
    if (next?.runId === previous?.runId && next?.status === previous?.status) return
    const updated = {...current.current}
    if (next) updated[sessionKey] = next
    else delete updated[sessionKey]
    current.current = updated
    setRuns(updated)
  }, [])

  const reconcile = useCallback(async (sessionKey: string, agentId: string) => {
    if (!api?.runs.status || !sessionKey || !agentId || lookups.current.has(sessionKey)) return
    const before = current.current[sessionKey]
    lookups.current.add(sessionKey)
    try {
      const result = await api.runs.status({sessionKey,agentId})
      if (current.current[sessionKey] !== before || result.status === 'unknown') return
      if (result.active) {
        const runId = typeof result.runId === 'string' && result.runId ? result.runId : null
        if (!runId || !completed.current.has(runId)) {
          update(sessionKey, {sessionKey,agentId,runId:runId ?? before?.runId ?? null,status:String(result.status || 'running')})
        }
      } else if (before) {
        update(sessionKey)
        void refreshHistory(sessionKey, agentId)
      }
    } catch {
      // A transient Gateway read cannot establish that a run has stopped.
    } finally {
      lookups.current.delete(sessionKey)
    }
  }, [api,refreshHistory,update])

  useEffect(() => {
    if (!api || !ready) return
    void reconcile(selectedKey,selectedAgent)
    const timer = window.setInterval(() => {
      const known = Object.values(current.current)
      for (const run of known) void reconcile(run.sessionKey,run.agentId)
      if (selectedKey && !current.current[selectedKey]) void reconcile(selectedKey,selectedAgent)
    }, 2500)
    return () => window.clearInterval(timer)
  }, [api,ready,reconcile,selectedKey,selectedAgent])

  const admit = useCallback((sessionKey: string, agentId: string, result: Record<string, unknown>) => {
    const runId = typeof result.runId === 'string' && result.runId ? result.runId : null
    if (runId && completed.current.has(runId)) return
    const observed = current.current[sessionKey]
    if (runId && observed?.runId === runId) return
    if (result.status === 'completed' || (!runId && result.status === 'ok')) {
      // Some runtimes return "ok" on an already completed, deduplicated turn.
      void reconcile(sessionKey,agentId)
      return
    }
    update(sessionKey,{sessionKey,agentId,runId,status:'running'})
    void reconcile(sessionKey,agentId)
  }, [reconcile,update])

  const onEvent = useCallback((event: {payload: Record<string, unknown>}) => {
    const {payload} = event
    const sessionKey = typeof payload.sessionKey === 'string' ? payload.sessionKey : ''
    const runId = typeof payload.runId === 'string' ? payload.runId : ''
    const status = typeof payload.runStatus === 'string' ? payload.runStatus : ''
    if (!runId || !status) return false
    const scopedAgent = scopedSessionKey.exec(sessionKey)?.[1] || ''
    const agentId = typeof payload.agentId === 'string' ? payload.agentId : scopedAgent
    if (terminal.has(status)) {
      completed.current.add(runId)
      if (completed.current.size > 150) completed.current.delete(completed.current.values().next().value!)
      if (!sessionKey || !scopedAgent || scopedAgent !== agentId) return false
      const tracked = current.current[sessionKey]?.runId
      if (tracked === runId) update(sessionKey)
      void refreshHistory(sessionKey,agentId)
      return !tracked || tracked === runId
    }
    if (!sessionKey || !scopedAgent || scopedAgent !== agentId || completed.current.has(runId)) return false
    const observed = current.current[sessionKey]
    if (observed?.runId && observed.runId !== runId) {
      void reconcile(sessionKey,agentId)
      return false
    }
    update(sessionKey,{sessionKey,agentId,runId,status})
    return true
  }, [reconcile,refreshHistory,update])

  const stop = useCallback(async (sessionKey: string, agentId: string) => {
    if (!api) return
    const target = current.current[sessionKey]
    if (!target?.runId || target.agentId !== agentId) {
      void reconcile(sessionKey,agentId)
      return
    }
    await api.runs.interrupt({key:sessionKey,agentId,runId:target.runId})
    await reconcile(sessionKey,agentId)
  }, [api,reconcile])

  return {runs,admit,onEvent,stop}
}
