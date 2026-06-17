'use client'

import { useState, useCallback, useRef } from 'react'

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  agentId?: string
  createdAt: number
  updatedAt: number
}

const STORAGE_KEY = 'szyg_conversations'
const MAX_CONVERSATIONS = 15

function loadConversations(): Conversation[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveConversations(convs: Conversation[]) {
  if (typeof window === 'undefined') return
  const trimmed = convs.slice(0, MAX_CONVERSATIONS)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
}

function genId() {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export function useChatStore() {
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations)
  const [activeId, setActiveId] = useState<string | null>(() => {
    const convs = loadConversations()
    return convs.length > 0 ? convs[0].id : null
  })
  // Ref 始终持有最新数据，避免闭包陷阱
  const conversationsRef = useRef(conversations)
  conversationsRef.current = conversations

  const active = conversations.find(c => c.id === activeId) || null

  const persist = useCallback((convs: Conversation[]) => {
    setConversations(convs)
    conversationsRef.current = convs
    saveConversations(convs)
  }, [])

  const newConversation = useCallback((agentId?: string) => {
    const conv: Conversation = {
      id: genId(), title: '新对话', messages: [],
      agentId, createdAt: Date.now(), updatedAt: Date.now(),
    }
    const updated = [conv, ...conversationsRef.current]
    setActiveId(conv.id)
    persist(updated)
    return conv.id
  }, [persist])

  const addMessage = useCallback((content: string, role: 'user' | 'assistant') => {
    if (!activeId) return
    const current = conversationsRef.current
    const updated = current.map(c => {
      if (c.id !== activeId) return c
      const msg: Message = { role, content }
      const title = c.title === '新对话' && role === 'user'
        ? content.slice(0, 30) + (content.length > 30 ? '...' : '')
        : c.title
      return { ...c, title, messages: [...c.messages, msg], updatedAt: Date.now() }
    })
    persist(updated)
  }, [activeId, persist])

  const updateLastAssistant = useCallback((content: string) => {
    if (!activeId) return
    const current = conversationsRef.current
    const updated = current.map(c => {
      if (c.id !== activeId) return c
      const msgs = [...c.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, content }
      }
      return { ...c, messages: msgs, updatedAt: Date.now() }
    })
    persist(updated)
  }, [activeId, persist])

  const switchConversation = useCallback((id: string) => {
    setActiveId(id)
  }, [])

  const deleteConversation = useCallback((id: string) => {
    const updated = conversationsRef.current.filter(c => c.id !== id)
    persist(updated)
    if (activeId === id) {
      setActiveId(updated.length > 0 ? updated[0].id : null)
    }
  }, [activeId, persist])

  const clearCurrent = useCallback(() => {
    if (!activeId) return
    const updated = conversationsRef.current.map(c =>
      c.id === activeId ? { ...c, messages: [], title: '新对话', updatedAt: Date.now() } : c
    )
    persist(updated)
  }, [activeId, persist])

  return {
    conversations, active, activeId,
    newConversation, addMessage, updateLastAssistant,
    switchConversation, deleteConversation, clearCurrent,
  }
}
