import { useI18n } from '@/lib/i18n'
import { product } from '@/lib/product'

export default function Footer() {
  const { t } = useI18n()
  return (
    <footer className="px-8 py-4 border-t border-border bg-background">
      <div className="flex items-center justify-center text-xs text-muted-foreground">
        <span>© 2026 {t(product.name)}. {t('版权所有。')}</span>
      </div>
    </footer>
  )
}
