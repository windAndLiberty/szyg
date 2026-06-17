'use client'

import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Send, Bot, User, ArrowLeft, Plus } from 'lucide-react'
import type { AIAgent } from '@/lib/ai-agents'
import type { AgentSession } from '@/lib/use-agent-sessions'
import { MessageContent } from '@/components/chat-render'
import { cn } from '@/lib/utils'

interface Props {
  agent: AIAgent
  session: AgentSession
  onSend: (text: string) => void
  onNewChat: () => void
  onBack: () => void
}

export default function AgentChatView({ agent, session, onSend, onNewChat, onBack }: Props) {
  const [input, setInput] = useState('')
  const msgBoxRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { messages, streaming, streamText } = session

  const resizeTextarea = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const newHeight = Math.min(el.scrollHeight, 200)
    if (newHeight > 0) el.style.height = `${newHeight}px`
  }

  useEffect(() => {
    resizeTextarea()
  }, [input])

  useEffect(() => {
    if (msgBoxRef.current) {
      msgBoxRef.current.scrollTo({ top: msgBoxRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages, streamText])

  const submit = () => {
    if (!input.trim() || streaming) return
    onSend(input.trim())
    setInput('')
  }

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6 h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={onBack}
          className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.03] transition-all flex items-center gap-1.5"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-xs">返回</span>
        </button>
        <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${agent.color} flex items-center justify-center font-bold text-white text-base shadow-md`}>
          {agent.letter}
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-bold text-white truncate">{agent.name}</h2>
          <p className="text-xs text-white/30 truncate">{agent.desc}</p>
        </div>
        <button
          onClick={onNewChat}
          disabled={streaming}
          className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.03] transition-all flex items-center gap-1.5 disabled:opacity-30"
        >
          <Plus className="w-4 h-4" />
          <span className="text-xs">新对话</span>
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 flex flex-col overflow-hidden min-h-0">
        <div ref={msgBoxRef} className="flex-1 overflow-y-auto py-4 space-y-6 min-h-0">
          {messages.length === 0 && !streaming && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-6 max-w-lg">
                <div>
                  <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${agent.color} flex items-center justify-center font-bold text-white text-2xl shadow-lg mx-auto mb-3`}>
                    {agent.letter}
                  </div>
                  <h3 className="text-base font-bold text-white mb-1">{agent.name}</h3>
                  <p className="text-sm text-white/40 leading-relaxed">{agent.desc}</p>
                  {agent.needsApi && (
                    <p className="text-xs text-amber-400/60 mt-2">提示：该智能体需要先在知识库导入相关资料才能发挥全部能力。</p>
                  )}
                </div>
                <div className="flex flex-col gap-2 items-stretch">
                  {agent.suggestions.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(q)}
                      className="px-4 py-3 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm text-left hover:bg-accent/10 hover:border-accent/20 hover:text-accent transition-all"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`flex gap-3 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-accent/20 text-accent' : 'bg-purple-500/20 text-purple-400'}`}>
                  {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>
                <div className={cn(
                  'text-sm leading-relaxed',
                  msg.role === 'user'
                    ? 'px-4 py-3 rounded-2xl bg-gradient-to-r from-accent to-purple-500 text-white rounded-tr-sm'
                    : 'px-1 py-1 text-white/85'
                )}>
                  <MessageContent content={msg.content} role={msg.role} />
                </div>
              </div>
            </motion.div>
          ))}

          {streaming && (
            <div className="flex justify-start">
              <div className="flex gap-3 max-w-[80%]">
                <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 bg-purple-500/20 text-purple-400">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="px-1 py-1 text-sm leading-relaxed text-white/85">
                  {streamText}
                  <span className="inline-block w-0.5 h-4 bg-accent ml-0.5 animate-pulse align-middle" />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-white/5">
          <div className="flex gap-2 items-end">
            <textarea
              ref={textareaRef}
              value={input}
              rows={1}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  submit()
                }
              }}
              placeholder={`和「${agent.name}」对话...`}
              disabled={streaming}
              className="flex-1 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/50 transition-colors disabled:opacity-50 resize-none overflow-y-auto min-h-[46px] max-h-[200px]"
            />
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={submit}
              disabled={streaming || !input.trim()}
              className="px-4 py-3 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white disabled:opacity-30 transition-opacity"
            >
              <Send className="w-4 h-4" />
            </motion.button>
          </div>
        </div>
      </div>
    </div>
  )
}
