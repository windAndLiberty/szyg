import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { Search } from 'lucide-react'
import { navGroups } from '@/lib/navConfig'
import { useI18n } from '@/lib/i18n'

export default function PageSearch() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const trigger = useRef<HTMLButtonElement>(null)
  const container = useRef<HTMLDivElement>(null)
  const words = query.toLocaleLowerCase().trim().split(/\s+/)
  const results = navGroups.flatMap(group => group.children.map(child => ({
    ...child, label: t(child.label), group: t(group.label),
  }))).filter(child => {
    const searchable = [child.group, child.label, child.keywords || '', child.path].join(' ').toLocaleLowerCase()
    return words.every(word => searchable.includes(word))
  })
  const activeIndex = Math.min(selected, results.length - 1)

  const close = () => {
    setOpen(false)
    setQuery('')
    setSelected(0)
  }

  useEffect(() => { close() }, [location.pathname, location.search])
  useEffect(() => {
    if (!open) return
    function outside(event: PointerEvent) {
      if (!container.current?.contains(event.target as Node)) close()
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])

  useEffect(() => {
    if (open && activeIndex >= 0) container.current?.querySelector(`#page-search-option-${activeIndex}`)?.scrollIntoView({ block: 'nearest' })
  }, [open, activeIndex])

  return <div ref={container} className="relative mx-2 min-w-0 max-w-md flex-1 md:mx-8"
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) close() }}>
    {open ? <>
      <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
      <input autoFocus role="combobox" aria-label={t('navigation.pageSearch')} aria-expanded="true"
        aria-controls="page-search-results" aria-autocomplete="list"
        aria-activedescendant={activeIndex >= 0 ? `page-search-option-${activeIndex}` : undefined}
        placeholder={t('navigation.pageSearch')} value={query}
        onChange={event => { setQuery(event.target.value); setSelected(0) }}
        onKeyDown={event => {
          if (event.nativeEvent.isComposing) return
          if (event.key === 'Escape') { close(); requestAnimationFrame(() => trigger.current?.focus()); return }
          if (!results.length) return
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            setSelected((activeIndex + (event.key === 'ArrowDown' ? 1 : -1) + results.length) % results.length)
          }
          if (event.key === 'Enter') { event.preventDefault(); navigate(results[activeIndex].path); close() }
        }}
        className="h-10 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none" />
      <div className="absolute left-0 top-full z-50 mt-2 max-h-[52vh] w-max min-w-full max-w-[70vw] overflow-y-auto rounded-xl border bg-popover p-1 text-popover-foreground shadow-lg">
        <div role="listbox" id="page-search-results" aria-label={t('navigation.pageSearch')}>
          {results.map((child, index) => <Link key={child.path} to={child.path} role="option"
            id={`page-search-option-${index}`} aria-selected={index === activeIndex} tabIndex={-1}
            onMouseDown={event => event.preventDefault()} onClick={close}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-muted ${index === activeIndex ? 'bg-muted' : ''}`}>
            <child.icon aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="flex-1">{child.label}</span><span className="text-xs text-muted-foreground">{child.group}</span>
          </Link>)}
        </div>
        {!results.length && <p role="status" className="px-3 py-2 text-sm text-muted-foreground">{t('navigation.noPages')}</p>}
      </div>
    </> : <button ref={trigger} type="button" onClick={() => setOpen(true)} aria-label={t('navigation.pageSearch')}
      className="flex h-10 items-center gap-2 rounded-lg border bg-background px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">
      <Search aria-hidden="true" className="h-4 w-4" /><span className="hidden sm:inline">{t('common.search')}</span>
    </button>}
  </div>
}
