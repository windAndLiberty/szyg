'use client'

import { useState, useRef, useCallback } from 'react'
import type { AIAgent } from '@/lib/ai-agents'

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

export interface AgentSession {
  messages: Message[]
  streaming: boolean
  streamText: string
}

const EMPTY: AgentSession = { messages: [], streaming: false, streamText: '' }

/**
 * 内存级、按智能体隔离的会话管理（不持久化历史记录）。
 *
 * - 每个 agentId 维护独立 session（messages / streaming / streamText）。
 * - 使用函数式 setState 按 agentId 更新，多个智能体可并发流式而互不干扰。
 * - 流式逻辑挂在调用方组件（AI智能体页面，始终挂载），因此切换智能体 / 返回列表
 *   都不会中断已发起的流式请求，也不会丢失各自的对话内容。
 * - 仅在调用 newSession 时清空对应智能体的会话。
 */
export function useAgentSessions() {
  const [sessions, setSessions] = useState<Record<string, AgentSession>>({})
  const sessionsRef = useRef(sessions)
  sessionsRef.current = sessions

  const update = useCallback(
    (agentId: string, fn: (s: AgentSession) => AgentSession) => {
      setSessions((prev) => {
        const cur = prev[agentId] ?? EMPTY
        const next = { ...prev, [agentId]: fn(cur) }
        sessionsRef.current = next
        return next
      })
    },
    [],
  )

  const getSession = useCallback((agentId: string): AgentSession => {
    return sessionsRef.current[agentId] ?? EMPTY
  }, [])

  const newSession = useCallback(
    (agentId: string) => {
      // 流式进行中不允许重置，避免悬挂的请求写回已清空的会话。
      if (getSession(agentId).streaming) return
      update(agentId, () => ({ ...EMPTY }))
    },
    [getSession, update],
  )

  const send = useCallback(
    async (agent: AIAgent, text: string) => {
      const userMsg = text.trim()
      if (!userMsg) return
      const cur = getSession(agent.id)
      if (cur.streaming) return

      const baseMessages: Message[] = [...cur.messages, { role: 'user', content: userMsg }]
      update(agent.id, (s) => ({ ...s, messages: baseMessages, streaming: true, streamText: '' }))

      try {
        const resp = await fetch('/api/hermes/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: baseMessages,
            system_prompt: agent.systemPrompt,
            use_tools: !!agent.useTools,
          }),
        })

        const reader = resp.body?.getReader()
        const decoder = new TextDecoder()
        let done = false
        let fullText = ''
        let buffer = ''
        const thinkingBlocks: string[] = []
        const toolBlocks: string[] = []

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
              update(agent.id, (s) => ({ ...s, streamText: fullText }))
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

        const drainBuffer = () => {
          let sep: number
          while ((sep = buffer.search(/\r?\n\r?\n/)) !== -1) {
            const frameEnd = sep + (buffer[sep] === '\r' ? 4 : 2)
            const frame = buffer.slice(0, sep)
            buffer = buffer.slice(frameEnd)
            for (const line of frame.split(/\r?\n/)) {
              if (!line.startsWith('data:')) continue
              const data = line.slice(line.startsWith('data: ') ? 6 : 5)
              try {
                handleEvent(JSON.parse(data))
              } catch {}
            }
          }
        }

        while (!done && reader) {
          const { value, done: d } = await reader.read()
          if (value) {
            buffer += decoder.decode(value, { stream: true })
            drainBuffer()
          }
          if (d) {
            buffer += decoder.decode()
            if (buffer.trim()) {
              buffer += '\n\n'
              drainBuffer()
            }
            break
          }
        }

        const parts: string[] = []
        if (thinkingBlocks.length > 0) parts.push(thinkingBlocks.join(''))
        if (toolBlocks.length > 0) parts.push(toolBlocks.join(''))
        if (fullText) parts.push(`\n---\n\n${fullText}`)
        const finalText = parts.join('') || fullText || '(empty response)'

        update(agent.id, (s) => ({
          ...s,
          messages: [...s.messages, { role: 'assistant', content: finalText }],
          streaming: false,
          streamText: '',
        }))
      } catch (e: any) {
        update(agent.id, (s) => ({
          ...s,
          messages: [...s.messages, { role: 'assistant', content: '❌ Error: ' + e.message }],
          streaming: false,
          streamText: '',
        }))
      }
    },
    [getSession, update],
  )

  return { getSession, send, newSession }
}
