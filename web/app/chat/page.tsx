'use client'

import { Suspense } from 'react'
import ChatContent from './ChatContent'

export default function ChatPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-main)]">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    }>
      <ChatContent />
    </Suspense>
  )
}
