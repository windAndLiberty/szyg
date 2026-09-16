import { Languages } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useI18n } from '@/lib/i18n'

export default function LanguageSwitcher({ className }: { className?: string }) {
  const { locale, setLocale, t } = useI18n()
  const nextLocale = locale === 'zh-CN' ? 'en-US' : 'zh-CN'
  const nextLabel = locale === 'zh-CN' ? 'EN' : '中'
  return (
    <button
      type="button"
      onClick={() => setLocale(nextLocale)}
      className={cn('inline-flex h-9 items-center gap-1.5 rounded-lg border border-[#334155] bg-[#0B0F1A]/80 px-2.5 text-xs font-semibold text-[#CBD5E1] transition-colors hover:border-[#6366F1]/70 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6366F1]', className)}
      aria-label={t(locale === 'zh-CN' ? '切换为 English' : '切换为中文')}
      title={t('切换语言')}
    >
      <Languages className="h-4 w-4" aria-hidden="true" />
      <span>{nextLabel}</span>
    </button>
  )
}
