'use client'

import { useState, useRef, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Bot, User, Sparkles, Plus, Trash2, MessageSquare, X, Eraser, Search, FileText, Wand2 } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import { useChatStore } from '@/lib/chat-store'
import { findAgentById } from '@/lib/ai-agents'
import { cn } from '@/lib/utils'
import { MessageContent } from '@/components/chat-render'

export default function ChatContent() {
  const searchParams = useSearchParams()
  const agentId = searchParams.get('agent')
  const agent = findAgentById(agentId)
  const {
    conversations, active, activeId,
    newConversation, addMessage, updateLastAssistant,
    switchConversation, deleteConversation, clearCurrent,
  } = useChatStore()

  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const [quickLoading, setQuickLoading] = useState('')
  const msgBoxRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const resizeTextarea = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const newHeight = Math.min(el.scrollHeight, 200)
    if (newHeight > 0) {
      el.style.height = `${newHeight}px`
    }
  }

  useEffect(() => {
    resizeTextarea()
  }, [input])

  // Quick test functions
  async function quickTest(type: string) {
    setQuickLoading(type)
    try {
      if (type === 'lead') {
        const resp = await fetch('/api/leads/score-intent', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ platform: 'douyin', interaction_content: '这个多少钱？怎么买？方便加微信吗', context: '产品广告推广' }),
        })
        const data = await resp.json()
        addMessage('帮我分析这条评论的意向：\n"这个多少钱？怎么买？方便加微信吗"', 'user')
        addMessage(`✅ **意向评分结果**\n- 分数: ${data.intent_score}\n- 等级: ${data.intent_level}\n- 信号: ${(data.intent_signals || []).join(', ')}\n- 建议回复: ${data.suggested_reply}`, 'assistant')
      } else if (type === 'script') {
        const resp = await fetch('/api/scripts/generate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ industry: '零售', scenario: '价格咨询', product_info: '智能AI客服机器人，提升客服效率70%，降低成本35%' }),
        })
        const data = await resp.json()
        const steps = data.generated || {}
        const preview = Object.entries(steps).map(([k, v]) => `**${k}**: ${v}`).join('\n\n')
        addMessage('帮我生成一个零售行业的价格咨询话术，产品是智能客服机器人', 'user')
        addMessage(`✅ **${data.template?.title || '话术生成'}** (${data.persona})\n\n${preview}\n\n💡 技巧: ${(data.tips || []).join(' / ')}`, 'assistant')
      }
    } catch (e: any) {
      addMessage(`❌ 测试失败: ${e.message}`, 'assistant')
    }
    setQuickLoading('')
  }

  // Init: create first conversation if none
  useEffect(() => {
    if (conversations.length === 0) {
      newConversation(agentId || undefined)
    }
  }, [])

  // Scroll to bottom
  useEffect(() => {
    if (msgBoxRef.current) {
      msgBoxRef.current.scrollTo({ top: msgBoxRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [active?.messages, streamText])

  const messages = active?.messages || []

  async function send() {
    if (!input.trim() || streaming || !activeId) return
    const userMsg = input.trim()
    addMessage(userMsg, 'user')
    setInput('')
    setStreaming(true)
    setStreamText('')

    try {
      const resp = await fetch('/api/hermes/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [...messages, { role: 'user', content: userMsg }],
          system_prompt: agent?.systemPrompt,
          use_tools: agent ? !!agent.useTools : true,
        }),
      })
      const reader = resp.body?.getReader()
      const decoder = new TextDecoder()
      let done = false
      let fullText = ''
      let buffer = ''
      const thinkingBlocks: string[] = []
      const toolBlocks: string[] = []

      // 处理单条已完整接收的 SSE 事件
      const handleEvent = (event: any) => {
        switch (event.type) {
          case 'reasoning':
            thinkingBlocks.push(`\n🧠 **思考**\n> ${event.content}\n`)
            break
          case 'thinking':
            thinkingBlocks.push(`\n💭 ${event.content}\n`)
            break
          case 'tool_start':
            toolBlocks.push(`\n🔧 **调用工具** \`${event.tool}\`\n`)
            break
          case 'tool_result':
            toolBlocks.push(`📋 结果已返回\n`)
            break
          case 'text':
            fullText += event.content
            setStreamText(fullText)
            break
          case 'error':
            toolBlocks.push(`\n❌ 错误: ${event.content}\n`)
            break
          case 'start':
            thinkingBlocks.push(`⚡ **Hermes Agent 已启动**\n`)
            break
          case 'done':
            done = true
            break
        }
      }

      // 从缓冲区中切出所有以空行分隔的完整 SSE 帧，保留末尾不完整片段
      const drainBuffer = () => {
        let sep: number
        // 兼容 \n\n 与 \r\n\r\n 两种事件分隔符
        while ((sep = buffer.search(/\r?\n\r?\n/)) !== -1) {
          const frameEnd = sep + (buffer[sep] === '\r' ? 4 : 2)
          const frame = buffer.slice(0, sep)
          buffer = buffer.slice(frameEnd)
          for (const line of frame.split(/\r?\n/)) {
            if (!line.startsWith('data:')) continue
            const data = line.slice(line.startsWith('data: ') ? 6 : 5)
            try { handleEvent(JSON.parse(data)) } catch {}
          }
        }
      }

      while (!done && reader) {
        const { value, done: d } = await reader.read()
        if (value) {
          // stream:true 保证跨 chunk 的多字节 UTF-8（中文）不被截断
          buffer += decoder.decode(value, { stream: true })
          drainBuffer()
        }
        if (d) {
          // flush 解码器残留 + 处理最后一帧（可能没有结尾空行）
          buffer += decoder.decode()
          if (buffer.trim()) {
            buffer += '\n\n'
            drainBuffer()
          }
          break
        }
      }

      // 构建格式化的最终回复
      const parts: string[] = []
      if (thinkingBlocks.length > 0) parts.push(thinkingBlocks.join(''))
      if (toolBlocks.length > 0) parts.push(toolBlocks.join(''))
      if (fullText) parts.push(`\n---\n\n${fullText}`)

      const finalText = parts.join('') || fullText
      addMessage(finalText || '(empty response)', 'assistant')
      updateLastAssistant(finalText)
    } catch (e: any) {
      addMessage('❌ Error: ' + e.message, 'assistant')
    }
    setStreaming(false)
    setStreamText('')
  }

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto p-4 md:p-6 h-full flex gap-4">
        {/* History Sidebar */}
        <AnimatePresence>
          {showHistory && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 260, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              className="flex-shrink-0 overflow-hidden"
            >
              <div className="glass-card h-full flex flex-col">
                <div className="flex items-center justify-between px-3 py-3 border-b border-white/5">
                  <span className="text-sm font-medium text-white/70">历史对话</span>
                  <button onClick={() => setShowHistory(false)} className="text-white/30 hover:text-white">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                  {conversations.map(conv => (
                    <div
                      key={conv.id}
                      onClick={() => { switchConversation(conv.id); setShowHistory(false) }}
                      className={cn(
                        'group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all text-sm',
                        conv.id === activeId
                          ? 'bg-accent/10 text-white'
                          : 'text-white/50 hover:text-white/70 hover:bg-white/[0.03]'
                      )}
                    >
                      <MessageSquare className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="flex-1 truncate">{conv.title}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id) }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded text-white/30 hover:text-red-400 transition-all"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
                {activeId && (
                  <div className="p-2 border-t border-white/5">
                    <button
                      onClick={() => { clearCurrent(); }}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-white/40 hover:text-white hover:bg-white/[0.03] transition-all"
                    >
                      <Eraser className="w-3 h-3" /> 清空当前对话
                    </button>
                  </div>
                )}
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Main Chat */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-4">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={cn(
                'p-2 rounded-lg transition-all text-sm flex items-center gap-1.5',
                showHistory ? 'bg-accent/10 text-accent' : 'text-white/40 hover:text-white hover:bg-white/[0.03]'
              )}
            >
              <MessageSquare className="w-4 h-4" />
              {!showHistory && <span className="text-xs">历史</span>}
            </button>
            <button
              onClick={() => newConversation(agentId || undefined)}
              className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.03] transition-all flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span className="text-xs">新对话</span>
            </button>
            <div className="flex-1" />
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-accent" />
              {agent ? agent.name : 'AI 超级员工'}
            </h2>
            {agent && <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent">智能体</span>}
          </div>

          {/* Messages */}
          <div className="flex-1 flex flex-col overflow-hidden min-h-0">
            <div ref={msgBoxRef} className="flex-1 overflow-y-auto py-4 space-y-6 min-h-0">
              {messages.length === 0 && !streaming && agent && (
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
                          className="px-4 py-3 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm text-left hover:bg-accent/10 hover:border-accent/20 hover:text-accent transition-all flex items-center gap-2"
                        >
                          <Sparkles className="w-4 h-4 flex-shrink-0 opacity-50" />
                          <span>{q}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              {messages.length === 0 && !streaming && !agent && (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center space-y-6">
                    <div>
                      <Bot className="w-12 h-12 mx-auto mb-3 text-white/10" />
                      <p className="text-sm text-white/30">开始与 AI 对话，或点击下方快捷测试</p>
                    </div>
                    <div className="flex gap-3 justify-center flex-wrap">
                      <button
                        onClick={() => quickTest('lead')}
                        disabled={!!quickLoading}
                        className="px-4 py-3 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm hover:bg-emerald-500/10 hover:border-emerald-500/20 hover:text-emerald-400 transition-all flex items-center gap-2 disabled:opacity-30"
                      >
                        <Search className="w-4 h-4" />
                        {quickLoading === 'lead' ? '测试中...' : '🧪 意向评分测试'}
                      </button>
                      <button
                        onClick={() => quickTest('script')}
                        disabled={!!quickLoading}
                        className="px-4 py-3 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm hover:bg-amber-500/10 hover:border-amber-500/20 hover:text-amber-400 transition-all flex items-center gap-2 disabled:opacity-30"
                      >
                        <FileText className="w-4 h-4" />
                        {quickLoading === 'script' ? '测试中...' : '🧪 话术生成测试'}
                      </button>
                      <button
                        onClick={() => { setInput('帮我搜索高意向线索，生成跟进话术') }}
                        className="px-4 py-3 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm hover:bg-accent/10 hover:border-accent/20 hover:text-accent transition-all flex items-center gap-2"
                      >
                        <Wand2 className="w-4 h-4" />
                        📋 AI 销冠演示
                      </button>
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
                      send()
                    }
                  }}
                  placeholder="输入消息..."
                  disabled={streaming}
                  className="flex-1 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/50 transition-colors disabled:opacity-50 resize-none overflow-y-auto min-h-[46px] max-h-[200px]"
                />
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={send}
                  disabled={streaming || !input.trim()}
                  className="px-4 py-3 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white disabled:opacity-30 transition-opacity"
                >
                  <Send className="w-4 h-4" />
                </motion.button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
