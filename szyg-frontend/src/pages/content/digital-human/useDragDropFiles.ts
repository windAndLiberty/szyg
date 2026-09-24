import { useCallback, useRef, useState, type ChangeEvent, type DragEvent } from 'react'

const DEFAULT_ACCEPT_PREFIXES = ['image/', 'video/', 'audio/']

function fileMatchesAccept(file: File, accept?: string): boolean {
  if (!accept) return true
  const tokens = accept.split(',').map((value) => value.trim()).filter(Boolean)
  if (!tokens.length) return true
  return tokens.some((token) => {
    if (token.endsWith('/*')) {
      return file.type.startsWith(token.slice(0, -1))
    }
    if (token.startsWith('.')) {
      return file.name.toLowerCase().endsWith(token.toLowerCase())
    }
    return file.type === token
  })
}

function pickFiles(list: FileList | null | undefined, accept?: string): File[] {
  if (!list) return []
  return Array.from(list).filter((file) => fileMatchesAccept(file, accept))
}

interface UseDragDropFilesOptions {
  accept?: string
  multiple?: boolean
  onFiles: (files: File[]) => void
}

export function useDragDropFiles({ accept, multiple = true, onFiles }: UseDragDropFilesOptions) {
  const [dragging, setDragging] = useState(false)
  const dragCounter = useRef(0)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const onFilesRef = useRef(onFiles)
  onFilesRef.current = onFiles

  const handleDragEnter = useCallback((event: DragEvent<HTMLElement>) => {
    if (!event.dataTransfer.types.includes('Files')) return
    event.preventDefault()
    dragCounter.current += 1
    setDragging(true)
  }, [])

  const handleDragOver = useCallback((event: DragEvent<HTMLElement>) => {
    if (!event.dataTransfer.types.includes('Files')) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
  }, [])

  const handleDragLeave = useCallback((event: DragEvent<HTMLElement>) => {
    if (!event.dataTransfer.types.includes('Files')) return
    dragCounter.current = Math.max(0, dragCounter.current - 1)
    if (dragCounter.current === 0) setDragging(false)
    if (event.currentTarget === event.target && !event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setDragging(false)
    }
  }, [])

  const handleDrop = useCallback(
    (event: DragEvent<HTMLElement>) => {
      if (!event.dataTransfer.types.includes('Files')) return
      event.preventDefault()
      dragCounter.current = 0
      setDragging(false)
      const files = pickFiles(event.dataTransfer.files, accept)
      if (!files.length) return
      onFilesRef.current(multiple ? files : files.slice(0, 1))
    },
    [accept, multiple],
  )

  const handleInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const files = pickFiles(event.target.files, accept)
      if (files.length) onFilesRef.current(multiple ? files : files.slice(0, 1))
      event.target.value = ''
    },
    [accept, multiple],
  )

  const openPicker = useCallback(() => inputRef.current?.click(), [])

  return {
    dragging,
    inputRef,
    handlers: {
      onDragEnter: handleDragEnter,
      onDragOver: handleDragOver,
      onDragLeave: handleDragLeave,
      onDrop: handleDrop,
    },
    onInputChange: handleInputChange,
    openPicker,
  }
}

export const dragAndDropAcceptPattern = DEFAULT_ACCEPT_PREFIXES.join(',')
