import { useEffect, useState } from 'react'
import { CircleAlert, Clock3, Film, LoaderCircle } from 'lucide-react'
import { apiGet } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { DirectorAssetPreview } from './DirectorMedia'

type OpenClaw = NonNullable<NonNullable<Window['electronAPI']>['openClaw']>
export type DirectorRender = {
  job_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'interrupted'
  url?: string
  error?: string
}

const uuid = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i
const completed = (job: DirectorRender) => job.status !== 'queued' && job.status !== 'running'

export function useDirectorRenders(api: OpenClaw | undefined, sessionKey: string, agentId: string, active: boolean, watchingTurn: boolean) {
  const [cache, setCache] = useState<Record<string, DirectorRender[]>>({})
  useEffect(() => {
    if (!api?.sessions.directorRenders || !sessionKey || !active) return
    let disposed = false
    let timer: number
    const known = new Map<string,DirectorRender>()
    let settlingReads = 3

    async function refresh() {
      try {
        const response = await api!.sessions.directorRenders({sessionKey,agentId})
        if (disposed) return
        const keys = Array.isArray(response.jobs)
          ? response.jobs.filter((id): id is string => typeof id === 'string' && uuid.test(id)).slice(0,16)
          : []
        const receipts = await Promise.all(keys.map(async id => {
          const previous = known.get(id)
          if (previous && completed(previous)) return previous
          try { return await apiGet<DirectorRender>('/api/director/jobs/' + id + '/render') }
          catch { return previous }
        }))
        if (disposed) return
        const jobs = receipts.filter((item): item is DirectorRender => Boolean(item))
        for (const job of jobs) known.set(job.job_id,job)
        setCache(current => {
          const previous = current[sessionKey]
          if ((!previous && !jobs.length) || JSON.stringify(previous) === JSON.stringify(jobs)) return current
          return {...current,[sessionKey]:jobs}
        })
      } catch {
        // Leave any previous status visible until the transcript can be read again.
      } finally {
        // Allow the final tool receipt to reach the transcript a moment
        // after the model turn completes, then stop polling an idle chat.
        if (!disposed && (watchingTurn || Array.from(known.values()).some(job => !completed(job)) || settlingReads-- > 0)) {
          timer = window.setTimeout(refresh,2000)
        }
      }
    }
    void refresh()
    return () => { disposed = true; clearTimeout(timer) }
  }, [api,sessionKey,agentId,active,watchingTurn])
  return active ? cache[sessionKey] ?? [] : []
}

export default function DirectorRenderStatus({jobs, delivered}: {jobs: DirectorRender[]; delivered: (url: string) => boolean}) {
  const { t } = useI18n()
  const current = jobs.filter(job => !completed(job))
  const mostRecent = jobs[0]
  const finished = mostRecent && completed(mostRecent) && (!mostRecent.url || !delivered(mostRecent.url)) ? mostRecent : undefined
  const visible = finished ? [finished,...current] : current
  return visible.map(job => {
    const Icon = job.status === 'running' ? LoaderCircle : job.status === 'queued' ? Clock3 : job.url ? Film : CircleAlert
    const label = {
      queued:'director.renderQueued', running:'director.renderRunning', succeeded:job.url ? 'director.renderReady' : 'director.renderUnavailable',
      failed:'director.renderFailed', interrupted:'director.renderInterrupted',
    } as const
    return <div key={job.job_id} className="max-w-lg rounded-xl border bg-card px-3 py-2.5">
      <div role="status" className="flex items-center gap-2 text-sm">
        <Icon className={'h-4 w-4 shrink-0 ' + (job.status === 'running' ? 'animate-spin text-accent-ink' : 'text-muted-foreground')} />
        {t(label[job.status])}
      </div>
      {job.status === 'succeeded' && job.url && <DirectorAssetPreview url={job.url}/>}
      {job.error &&
        <p className="mt-1 break-words text-xs text-muted-foreground">{job.error}</p>}
    </div>
  })
}
