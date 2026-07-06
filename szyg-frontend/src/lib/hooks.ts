import { useEffect, useState, useCallback } from 'react'
import { apiGet, getErrorMessage } from './api'

/**
 * 通用异步数据加载 Hook — 从后端真实接口拉取数据。
 * 返回 { data, loading, error, reload }。
 */
export function useAsync<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): { data: T | null; loading: boolean; error: string | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    let alive = true
    setLoading(true)
    fetcher()
      .then((d) => {
        if (alive) {
          setData(d)
          setError(null)
        }
      })
      .catch((e) => {
        if (alive) setError(getErrorMessage(e))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { data, loading, error, reload }
}

/** 加载仪表盘数字员工（真实 AI 员工聚合）。 */
export function useDigitalHumans() {
  return useAsync<{ digitalHumans: import('@/types').DigitalHuman[] }>(
    () => apiGet('/api/dashboard/digital-humans'),
  )
}

/** 加载仪表盘真实任务队列。 */
export function useDashboardTasks() {
  return useAsync<{ tasks: import('@/types').TaskQueueItem[] }>(
    () => apiGet('/api/dashboard/tasks'),
  )
}

/** 加载真实近期动态流。 */
export function useActivities() {
  return useAsync<{ activities: import('@/types').ActivityItem[] }>(
    () => apiGet('/api/dashboard/activities'),
  )
}

/** 加载真实交互趋势。 */
export function useInteractionTrend(range: '7D' | '30D' | '90D') {
  return useAsync<{ chartData: { date: string; interactions: number; successRate: number }[] }>(
    () => apiGet(`/api/dashboard/interaction-trend?range=${range}`),
    [range],
  )
}

/** 加载真实数字员工分布。 */
export function useDistribution() {
  return useAsync<{ distribution: { name: string; value: number; color: string }[] }>(
    () => apiGet('/api/dashboard/distribution'),
  )
}
