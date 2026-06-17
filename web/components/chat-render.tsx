'use client'

import { Wrench, ChevronRight } from 'lucide-react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

type Block =
  | { type: 'markdown'; content: string }
  | { type: 'tool-start'; text: string }
  | { type: 'tool-result'; text: string }
  | { type: 'thinking'; text: string }
  | { type: 'start'; text: string }
  | { type: 'error'; text: string }
  | { type: 'divider' }

export const markdownComponents: Components = {
  h1: ({ children }) => <h1 className="text-lg font-bold text-white mb-3 mt-4 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-base font-bold text-white mb-2 mt-3 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-bold text-white mb-2 mt-3 first:mt-0">{children}</h3>,
  p: ({ children }) => <p className="text-sm text-white/85 leading-relaxed mb-3 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
  li: ({ children }) => <li className="text-sm text-white/85 leading-relaxed">{children}</li>,
  code: ({ className, children, ...props }) => {
    const isInline = !className
    if (isInline) {
      return (
        <code className="px-1.5 py-0.5 rounded-md bg-white/10 text-accent text-xs font-mono" {...props}>
          {children}
        </code>
      )
    }
    return (
      <pre className="p-3 rounded-xl bg-black/30 border border-white/5 overflow-x-auto mb-3">
        <code className="text-xs font-mono text-white/90" {...props}>
          {children}
        </code>
      </pre>
    )
  },
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-accent/50 pl-3 italic text-white/60 mb-3">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => (
    <a href={href} className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <table className="w-full text-sm text-left text-white/85 border border-white/10 rounded-lg overflow-hidden mb-3">
      {children}
    </table>
  ),
  thead: ({ children }) => <thead className="bg-white/5 text-white">{children}</thead>,
  th: ({ children }) => <th className="px-3 py-2 font-medium border-b border-white/10">{children}</th>,
  td: ({ children }) => <td className="px-3 py-2 border-b border-white/5">{children}</td>,
  hr: () => <div className="my-4 border-t border-white/10" />,
  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
  em: ({ children }) => <em className="italic text-white/90">{children}</em>,
}

export function parseAssistantContent(content: string): Block[] {
  const lines = content.split('\n')
  const blocks: Block[] = []
  let currentMarkdownLines: string[] = []

  const flushMarkdown = () => {
    if (currentMarkdownLines.length > 0) {
      let start = 0
      let end = currentMarkdownLines.length
      while (start < end && currentMarkdownLines[start].trim() === '') start++
      while (end > start && currentMarkdownLines[end - 1].trim() === '') end--
      if (start < end) {
        blocks.push({ type: 'markdown', content: currentMarkdownLines.slice(start, end).join('\n') })
      }
      currentMarkdownLines = []
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line.startsWith('🔧') || line.includes('**调用工具**')) {
      flushMarkdown()
      blocks.push({ type: 'tool-start', text: line.replace(/^\s*🔧\s*/, '').replace(/\*\*/g, '') })
    } else if (line.startsWith('📋') || line.includes('结果已返回')) {
      flushMarkdown()
      blocks.push({ type: 'tool-result', text: line.replace(/^\s*📋\s*/, '') })
    } else if (line.startsWith('💭') || line.startsWith('🧠')) {
      flushMarkdown()
      blocks.push({ type: 'thinking', text: line })
    } else if (line.includes('Hermes Agent 已启动')) {
      flushMarkdown()
      blocks.push({ type: 'start', text: line })
    } else if (line.startsWith('❌')) {
      flushMarkdown()
      blocks.push({ type: 'error', text: line })
    } else if (line.trim() === '---') {
      flushMarkdown()
      blocks.push({ type: 'divider' })
    } else {
      currentMarkdownLines.push(line)
    }
  }
  flushMarkdown()
  return blocks
}

export function AssistantContent({ content }: { content: string }) {
  const blocks = parseAssistantContent(content)
  return (
    <div className="space-y-3">
      {blocks.map((block, idx) => {
        if (block.type === 'markdown') {
          return (
            <div key={idx}>
              <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
                {block.content}
              </ReactMarkdown>
            </div>
          )
        }
        if (block.type === 'tool-start') {
          return (
            <div key={idx} className="flex items-center gap-2 py-1.5 px-2 -mx-2 my-1 rounded-lg bg-white/[0.03] border border-white/5">
              <Wrench className="w-3 h-3 text-sky-400 flex-shrink-0" />
              <span className="text-xs text-sky-300/80 font-mono">{block.text}</span>
            </div>
          )
        }
        if (block.type === 'tool-result') {
          return (
            <div key={idx} className="flex items-center gap-2 py-1 px-2 -mx-2 my-1">
              <ChevronRight className="w-3 h-3 text-emerald-400 flex-shrink-0" />
              <span className="text-xs text-emerald-400/60">{block.text}</span>
            </div>
          )
        }
        if (block.type === 'thinking') {
          return (
            <div key={idx} className="text-xs text-white/30 italic py-0.5 leading-relaxed">
              {block.text}
            </div>
          )
        }
        if (block.type === 'start') {
          return (
            <div key={idx} className="text-xs text-accent/60 py-1">
              {block.text}
            </div>
          )
        }
        if (block.type === 'error') {
          return (
            <div key={idx} className="text-xs text-red-400 py-1">
              {block.text}
            </div>
          )
        }
        if (block.type === 'divider') {
          return <div key={idx} className="my-2 border-t border-white/5" />
        }
        return null
      })}
    </div>
  )
}

export function MessageContent({ content, role }: { content: string; role: string }) {
  if (role === 'user') {
    return <div className="whitespace-pre-wrap">{content}</div>
  }
  return <AssistantContent content={content} />
}
