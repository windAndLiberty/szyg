import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, Home, RefreshCw } from 'lucide-react'
import { useI18n } from '@/lib/i18n'

interface AppErrorBoundaryProps {
  children: ReactNode
  t: (text: string) => string
}

interface AppErrorBoundaryState {
  hasError: boolean
}

class AppErrorBoundaryCore extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Page rendering failed', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
        <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 text-center shadow-card-lift">
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-lg bg-[#F59E0B]/10 text-warning-ink">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <h1 className="mt-4 text-lg font-semibold">{this.props.t('errors.pageUnavailable')}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{this.props.t('errors.pageUnavailableDescription')}</p>
          <div className="mt-6 flex justify-center gap-3">
            <button type="button" onClick={() => window.location.reload()} className="inline-flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-sm text-muted-foreground transition-colors hover:text-foreground">
              <RefreshCw className="h-4 w-4" />{this.props.t('common.reload')}
            </button>
            <button type="button" onClick={() => { window.location.href = '/' }} className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-3 text-sm text-primary-foreground transition-colors hover:brightness-90">
              <Home className="h-4 w-4" />{this.props.t('common.backHome')}
            </button>
          </div>
        </div>
      </div>
    )
  }
}

export default function AppErrorBoundary({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  return <AppErrorBoundaryCore t={t}>{children}</AppErrorBoundaryCore>
}
