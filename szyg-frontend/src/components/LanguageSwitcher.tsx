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
      className={cn('inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-background/80 px-2.5 text-xs font-semibold text-foreground transition-colors hover:border-[#6366F1]/70 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6366F1]', className)}
      aria-label={t(locale === 'zh-CN' ? 'common.switchToEnglish' : 'common.switchToChinese')}
      title={t('common.switchLanguage')}
    >
      <Languages className="h-4 w-4" aria-hidden="true" />
      <span>{nextLabel}</span>
    </button>
  )
}
