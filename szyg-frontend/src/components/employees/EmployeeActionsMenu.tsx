import { useLayoutEffect, useRef, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { Clapperboard, Clock3, History, ImageIcon, Info, Laptop } from 'lucide-react'
import { useI18n } from '@/lib/i18n'

type Props = {
  name: string
  position: { x: number; y: number }
  onClose: (restoreFocus?: boolean) => void
  onDetails?: () => void
  onAvatar?: () => void
  onHistory: () => void
  onRoutines?: () => void
  onComputer?: () => void
  onDirectorEngine?: () => void
}

const itemClass = 'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm text-popover-foreground outline-none hover:bg-muted focus-visible:bg-muted'

export default function EmployeeActionsMenu({ name, position, onClose, onDetails, onAvatar, onHistory, onRoutines, onComputer, onDirectorEngine }: Props) {
  const { t } = useI18n()
  const menu = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const element = menu.current
    if (!element) return
    const { width, height } = element.getBoundingClientRect()
    const margin = 6
    element.style.left = Math.max(margin, Math.min(position.x, window.innerWidth - width - margin)) + 'px'
    element.style.top = Math.max(margin, Math.min(position.y, window.innerHeight - height - margin)) + 'px'
    element.querySelector('button')?.focus({ preventScroll: true })
    function dismissOutside(event: Event) {
      if (event.target instanceof Node && !element?.contains(event.target)) onClose()
    }
    const dismiss = () => onClose()
    document.addEventListener('pointerdown', dismissOutside, true)
    document.addEventListener('focusin', dismissOutside)
    document.addEventListener('scroll', dismiss, true)
    window.addEventListener('resize', dismiss)
    window.addEventListener('blur', dismiss)
    return () => {
      document.removeEventListener('pointerdown', dismissOutside, true)
      document.removeEventListener('focusin', dismissOutside)
      document.removeEventListener('scroll', dismiss, true)
      window.removeEventListener('resize', dismiss)
      window.removeEventListener('blur', dismiss)
    }
  }, [position, onClose])

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape' || event.key === 'Tab') {
      if (event.key === 'Escape') event.preventDefault()
      event.stopPropagation()
      onClose(true)
      return
    }
    const buttons = Array.from(event.currentTarget.querySelectorAll('button'))
    const index = buttons.findIndex(button => button === document.activeElement)
    const next = {
      ArrowDown: (index + 1) % buttons.length,
      ArrowUp: (index - 1 + buttons.length) % buttons.length,
      Home: 0, End: buttons.length - 1,
    }[event.key as 'ArrowDown' | 'ArrowUp' | 'Home' | 'End']
    if (next === undefined) return
    event.preventDefault()
    buttons[next]?.focus()
  }

  function choose(action: () => void) {
    onClose(true)
    action()
  }

  return createPortal(
    <div ref={menu} role="menu" aria-label={t('employee.actions', { name })}
      className="fixed z-[120] w-44 rounded-xl border bg-popover p-1 shadow-lg"
      onContextMenu={event => event.preventDefault()} onKeyDown={onKeyDown}>
      {onDetails && <button type="button" role="menuitem" className={itemClass} onClick={() => choose(onDetails)}>
        <Info size={16} aria-hidden="true" />{t('employee.detailsAction')}
      </button>}
      <button type="button" role="menuitem" className={itemClass} onClick={() => choose(onHistory)}>
        <History size={16} aria-hidden="true"/>{t('employee.history')}
      </button>
      {onAvatar && <button type="button" role="menuitem" className={itemClass} onClick={() => choose(onAvatar)}>
        <ImageIcon size={16} aria-hidden="true"/>{t('common.changeAvatar')}
      </button>}
      {onRoutines && <button type="button" role="menuitem" className={itemClass} onClick={() => choose(onRoutines)}>
        <Clock3 size={16} aria-hidden="true"/>{t('后台任务')}
      </button>}
      {onComputer && <button type="button" role="menuitem" className={itemClass} onClick={() => choose(onComputer)}>
        <Laptop size={16} aria-hidden="true"/>{t('工作电脑')}
      </button>}
      {onDirectorEngine && <button type="button" role="menuitem" className={itemClass} onClick={() => choose(onDirectorEngine)}>
        <Clapperboard size={16} aria-hidden="true" />{t('director.engine')}
      </button>}
    </div>,
    document.body,
  )
}
