import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { fetchCloudSession, type CloudSession } from '@/lib/api'
import CloudLogin from '@/pages/CloudLogin'

export default function CloudAuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<CloudSession | null>(null)

  const reload = useCallback(async () => {
    try {
      setSession(await fetchCloudSession())
    } catch {
      setSession({ configured: true, authenticated: false, message: '账户服务暂时不可用' })
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

  if (!session) {
    return <div className="grid min-h-screen place-items-center bg-[#0B0F1A]"><LoaderCircle className="h-6 w-6 animate-spin text-[#818CF8]" /></div>
  }
  if (!session.configured) return <>{children}</>
  if (!session.authenticated) return <CloudLogin initialMessage={session.message} onSuccess={reload} />
  return <>{children}</>
}
