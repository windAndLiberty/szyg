import React from 'react'
import { motion } from 'framer-motion'
import {
  Wrench,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Film,
  Download,
} from 'lucide-react'
import UserAvatar from '@/components/ui/UserAvatar'
import type { ChatMessage } from '@/types'
import { cn } from '@/lib/utils'

type ChatMessageViewProps = {
  message: ChatMessage
  statusText?: string
  userName?: string
}

function toolActionLabel(name: string): string {
  if (/image|video|audio|tts|content|copy|pipeline/i.test(name)) return '内容生成'
  if (/search|browser|web|intelligence/i.test(name)) return '信息查找'
  if (/knowledge|memory|document|file/i.test(name)) return '资料整理'
  if (/workflow|scheduler|task/i.test(name)) return '工作流执行'
  if (/publish|upload|platform/i.test(name)) return '内容发布'
  if (/lead|customer|comment|acquisition/i.test(name)) return '客户跟进'
  return '执行任务'
}

function toolStatusLabel(status: string): string {
  if (status === 'success') return '已完成'
  if (status === 'error') return '需要处理'
  return '正在执行'
}

// Lightweight rich-text renderer: **bold**, `code`, and line breaks
function renderRichText(text: string): React.ReactNode[] {
  const lines = text.split('\n')
  return lines.map((line, li) => {
    const parts: React.ReactNode[] = []
    const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g
    let lastIndex = 0
    let match: RegExpExecArray | null
    let key = 0
    while ((match = regex.exec(line)) !== null) {
      if (match.index > lastIndex) {
        parts.push(<React.Fragment key={key++}>{line.slice(lastIndex, match.index)}</React.Fragment>)
      }
      const token = match[0]
      if (token.startsWith('**')) {
        parts.push(
          <strong key={key++} className="font-semibold text-[#F1F5F9]">
            {token.slice(2, -2)}
          </strong>,
        )
      } else if (token.startsWith('`')) {
        parts.push(
          <code
            key={key++}
            className="px-1.5 py-0.5 rounded bg-[#0D1321] border border-[#1E293B] text-[12px] font-mono text-[#A78BFA]"
          >
            {token.slice(1, -1)}
          </code>,
        )
      }
      lastIndex = match.index + token.length
    }
    if (lastIndex < line.length) {
      parts.push(<React.Fragment key={key++}>{line.slice(lastIndex)}</React.Fragment>)
    }
    return (
      <React.Fragment key={li}>
        {parts}
        {li < lines.length - 1 && <br />}
      </React.Fragment>
    )
  })
}

const Avatar: React.FC<{ role: string; userName?: string }> = ({ role, userName }) => {
  // system 角色（工具调用卡片）不显示头像，但保留占位以对齐
  if (role === 'system') return <div className="w-8 h-8 shrink-0" />
  if (role === 'user') {
    return <UserAvatar className="h-8 w-8 shrink-0" />
  }
  return (
    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center shrink-0 shadow-glow overflow-hidden">
      <img src="/logo1.png" alt="超级员工" className="w-full h-full object-cover" />
    </div>
  )
}

// === ChatMessageView component body ===
const ChatMessageView: React.FC<ChatMessageViewProps> = ({ message, statusText, userName }) => {
  const isUser = message.role === 'user'

  return (
    <motion.div
      className={cn('flex gap-3', isUser ? 'flex-row' : 'flex-row')}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
    >
      <Avatar role={message.role} userName={userName} />

      <div className="flex-1 min-w-0 pt-0.5">
        {/* Text message */}
        {message.type === 'text' && (
          message.content ? (
            <div
              className={cn(
                'inline-block rounded-card px-4 py-2.5 text-body-md leading-relaxed',
                isUser
                  ? 'ml-auto max-w-[70%] bg-[rgba(99,102,241,0.15)] border border-[rgba(99,102,241,0.25)] text-[#F1F5F9] shadow-[0_0_12px_rgba(99,102,241,0.08)]'
                  : 'mr-auto max-w-[75%] bg-[rgba(17,24,39,0.5)] border-l-2 border-[rgba(99,102,241,0.2)] rounded-r-card px-4 py-2.5 text-[#94A3B8]',
              )}
            >
              <span className="whitespace-pre-wrap break-words">{renderRichText(message.content)}</span>
              {message.isStreaming && (
                <span className="inline-block w-[7px] h-[14px] bg-[#818CF8] ml-0.5 align-middle animate-pulse" />
              )}
            </div>
          ) : message.isStreaming ? (
            <div className="flex items-center gap-2 py-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-[#818CF8]" />
              <span className="text-[13px] text-[#94A3B8]">{statusText || '思考中…'}</span>
            </div>
          ) : null
        )}

        {/* Tool result */}
        {message.type === 'tool_result' && message.toolCall && (
          <div className="inline-flex items-center gap-2 rounded-lg bg-[#0D1321]/60 border border-[#1E293B] px-3 py-2">
            {message.toolCall.status === 'success' ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981]" />
            ) : message.toolCall.status === 'error' ? (
              <AlertCircle className="w-3.5 h-3.5 text-[#EF4444]" />
            ) : (
              <Loader2 className="w-3.5 h-3.5 text-[#F59E0B] animate-spin" />
            )}
            <Wrench className="w-3.5 h-3.5 text-[#64748B]" />
            <span className="text-[12px] font-medium text-[#94A3B8]">{toolActionLabel(message.toolCall.tool)}</span>
            <span className="text-[12px] text-[#64748B]">{toolStatusLabel(message.toolCall.status)}</span>
          </div>
        )}

        {/* Image (real backend image_url) */}
        {message.type === 'image' && message.image_url && (
          <div className="max-w-md rounded-card overflow-hidden border border-[#1E293B] bg-[#111827]">
            <img src={message.image_url} alt={message.prompt || '生成图片'} className="w-full h-auto block" />
            {message.prompt && (
              <p className="px-3 py-2 text-[12px] text-[#94A3B8] border-t border-[#1E293B]">{message.prompt}</p>
            )}
          </div>
        )}

        {/* Video pending (real backend task progress) */}
        {message.type === 'video_pending' && (
          <div className="max-w-md rounded-card border border-[#1E293B] bg-[#0D1321] p-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-[rgba(99,102,241,0.15)] flex items-center justify-center shrink-0">
                <Loader2 className="w-5 h-5 text-[#6366F1] animate-spin" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-[13px] font-medium text-[#F1F5F9]">
                  <Film className="w-3.5 h-3.5 text-[#06B6D4]" />
                  视频生成中…
                </div>
                <p className="mt-0.5 text-[12px] text-[#64748B] line-clamp-2">{message.prompt}</p>
                <div className="mt-2 flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#1E293B]">
                    <div
                      className="h-full rounded-full bg-[#6366F1] transition-all"
                      style={{ width: `${message.progress || 0}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-[#94A3B8] tabular-nums">
                    {message.status || '排队中'}
                    {message.progress ? ` · ${message.progress}%` : ''}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Video ready (real backend video_url) */}
        {message.type === 'video' && message.video_url && (
          <div className="max-w-lg rounded-card overflow-hidden border border-[#1E293B] bg-[#111827]">
            <video src={message.video_url} controls preload="metadata" className="w-full h-auto block" />
            <div className="flex items-center justify-between px-3 py-2 border-t border-[#1E293B]">
              <span className="text-[12px] text-[#94A3B8] line-clamp-1">{message.prompt}</span>
              <a
                href={message.video_url}
                download
                className="inline-flex items-center gap-1 text-[12px] text-[#6366F1] hover:text-[#818CF8] shrink-0"
              >
                <Download className="w-3.5 h-3.5" /> 下载
              </a>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default React.memo(ChatMessageView)
