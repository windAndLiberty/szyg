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
      <div className="flex min-h-screen items-center justify-center bg-[#0B0F1A] px-6 text-[#F1F5F9]">
        <div className="w-full max-w-md rounded-lg border border-[#1E293B] bg-[#111827] p-6 text-center shadow-card-lift">
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-lg bg-[#F59E0B]/10 text-[#FBBF24]">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <h1 className="mt-4 text-lg font-semibold">{this.props.t('当前页面暂时无法显示')}</h1>
          <p className="mt-2 text-sm leading-6 text-[#64748B]">{this.props.t('页面数据可能发生了变化。你可以重新加载，其他功能不会受到影响。')}</p>
          <div className="mt-6 flex justify-center gap-3">
            <button type="button" onClick={() => window.location.reload()} className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#334155] px-3 text-sm text-[#94A3B8] transition-colors hover:text-[#F1F5F9]">
              <RefreshCw className="h-4 w-4" />{this.props.t('重新加载')}
            </button>
            <button type="button" onClick={() => { window.location.href = '/' }} className="inline-flex h-9 items-center gap-2 rounded-lg bg-[#6366F1] px-3 text-sm text-white transition-colors hover:bg-[#5558E6]">
              <Home className="h-4 w-4" />{this.props.t('返回首页')}
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
