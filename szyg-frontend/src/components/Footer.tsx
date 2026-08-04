import { useI18n } from '@/lib/i18n'

export default function Footer() {
  const { t } = useI18n()
  return (
    <footer className="px-8 py-4 border-t border-[#1E293B] bg-[#0B0F1A]">
      <div className="flex items-center justify-center text-xs text-[#64748B]">
        <span>{t('© 2026 领鹿员工. All rights reserved.')}</span>
      </div>
    </footer>
  )
}
