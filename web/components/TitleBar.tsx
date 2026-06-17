'use client'

import { useState, useEffect } from 'react'
import { Minus, Square, X } from 'lucide-react'

declare global {
  interface Window {
    electronAPI?: {
      minimize: () => void
      maximize: () => void
      close: () => void
      isMaximized: () => Promise<boolean>
    }
  }
}

export default function TitleBar() {
  const [isElectron, setIsElectron] = useState(false)

  useEffect(() => {
    setIsElectron(!!window.electronAPI)
  }, [])

  if (!isElectron) return null

  return (
    <div
      className="fixed top-0 left-0 right-0 z-[200] h-8 flex items-center justify-between bg-[var(--header-bg)]/95 backdrop-blur-xl border-b border-white/5 select-none"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      <div className="flex items-center gap-2 px-3">
        <div className="w-3 h-3 rounded-full bg-accent/60" />
        <span className="text-[11px] text-white/40 font-medium tracking-wide">szyg</span>
      </div>

      <div className="flex" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
        <button
          onClick={() => window.electronAPI?.minimize()}
          className="w-10 h-8 flex items-center justify-center text-white/40 hover:text-white hover:bg-white/[0.06] transition-colors"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => window.electronAPI?.maximize()}
          className="w-10 h-8 flex items-center justify-center text-white/40 hover:text-white hover:bg-white/[0.06] transition-colors"
        >
          <Square className="w-3 h-3" />
        </button>
        <button
          onClick={() => window.electronAPI?.close()}
          className="w-10 h-8 flex items-center justify-center text-white/40 hover:text-white hover:bg-red-500/80 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}
