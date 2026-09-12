import type { ReactNode } from 'react'
import { Loader2, Plus, Upload } from 'lucide-react'
import { useDragDropFiles } from './useDragDropFiles'

export type DropZoneSize = 'sm' | 'md' | 'lg'

interface DropZoneProps {
  accept?: string
  multiple?: boolean
  onFiles: (files: File[]) => void
  icon?: ReactNode
  title: string
  hint?: string
  size?: DropZoneSize
  variant?: 'dashed' | 'solid'
  busy?: boolean
  className?: string
  /**
   * Optional overlay content shown while files are dragged over the zone.
   * Defaults to a Chinese helper string.
   */
  overlayLabel?: string
  children?: ReactNode
}

const SIZE_CLASSES: Record<DropZoneSize, string> = {
  sm: 'min-h-[88px] py-3 px-3 text-xs',
  md: 'min-h-[120px] py-4 text-sm',
  lg: 'min-h-[160px] py-5 text-sm',
}

const ICON_WRAPPER: Record<DropZoneSize, string> = {
  sm: 'h-4 w-4 mr-1.5',
  md: 'h-5 w-5 mr-2',
  lg: 'h-6 w-6 mb-2',
}

export default function DropZone({
  accept,
  multiple = true,
  onFiles,
  icon,
  title,
  hint,
  size = 'md',
  variant = 'dashed',
  busy = false,
  className = '',
  overlayLabel = '松开即可上传',
  children,
}: DropZoneProps) {
  const { dragging, inputRef, handlers, onInputChange, openPicker } = useDragDropFiles({
    accept,
    multiple,
    onFiles,
  })

  const base =
    variant === 'dashed'
      ? 'border-dashed border-[#33425A] bg-[#0D1320] text-[#B9C4D5]'
      : 'border-solid border-[#2A3548] bg-[#0D1320] text-[#B9C4D5]'
  const draggingClass = dragging
    ? 'border-[#818CF8] bg-[#6366F1]/10 text-[#C7D2FE]'
    : ''
  const busyClass = busy ? 'cursor-wait opacity-70' : ''

  const iconNode =
    icon ?? (busy ? <Loader2 className="h-5 w-5 animate-spin" /> : size === 'lg' ? <Upload className={ICON_WRAPPER[size]} /> : <Plus className={ICON_WRAPPER[size]} />)

  return (
    <div
      {...handlers}
      className={`relative flex w-full flex-col items-center justify-center rounded-md border transition-colors ${SIZE_CLASSES[size]} ${base} ${draggingClass} ${busyClass} ${className}`}
    >
      {dragging && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-md bg-[#0B0F1A]/85 text-sm font-medium text-[#C4B5FD]">
          {overlayLabel}
        </div>
      )}
      <button
        type="button"
        onClick={openPicker}
        disabled={busy}
        className="flex h-full w-full flex-col items-center justify-center outline-none disabled:cursor-wait"
      >
        {iconNode}
        <span className="font-medium">{title}</span>
        {hint && <span className="mt-1 text-[11px] text-[#7F8DA5]">{hint}</span>}
        {children}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={onInputChange}
        className="hidden"
      />
    </div>
  )
}
