import React from 'react'
import { motion } from 'framer-motion'
import {
  Wrench,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Film,
  Download,
  Paperclip,
} from 'lucide-react'
import UserAvatar from '@/components/ui/UserAvatar'
import type { ChatMessage } from '@/types'
import { cn } from '@/lib/utils'
import RobotAvatar from '@/components/ui/RobotAvatar'
import { translateCurrent, useI18n } from '@/lib/i18n'

type ChatMessageViewProps = {
  message: ChatMessage
  statusText?: string
  userName?: string
}

function toolActionLabel(name: string): string {
  if (/image|video|audio|tts|content|copy|pipeline/i.test(name)) return translateCurrent("内容生成")
  if (/search|browser|web|intelligence/i.test(name)) return translateCurrent("信息查找")
  if (/knowledge|memory|document|file/i.test(name)) return translateCurrent("资料整理")
  if (/workflow|scheduler|task/i.test(name)) return translateCurrent("工作流执行")
  if (/publish|upload|platform/i.test(name)) return translateCurrent("内容发布")
  if (/lead|customer|comment|acquisition/i.test(name)) return translateCurrent("客户跟进")
  return translateCurrent("执行任务")
}

function toolStatusLabel(status: string): string {
  if (status === 'success') return translateCurrent("已完成")
  if (status === 'error') return translateCurrent("需要处理")
  return translateCurrent("正在执行")
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
          <strong key={key++} className="font-semibold text-foreground">
            {token.slice(2, -2)}
          </strong>,
        )
      } else if (token.startsWith('`')) {
        parts.push(
          <code
            key={key++}
            className="px-1.5 py-0.5 rounded bg-background border border-border text-[12px] font-mono text-accent-ink"
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
  const { t } = useI18n()
  // system 角色（工具调用卡片）不显示头像，但保留占位以对齐
  if (role === 'system') return <div className="w-8 h-8 shrink-0" />
  if (role === 'user') {
    return <UserAvatar className="h-8 w-8 shrink-0" />
  }
  return <span role="img" aria-label={t("小妤")} className="inline-flex h-8 w-8 shrink-0"><RobotAvatar identity="main" primary className="h-full w-full rounded-lg" /></span>
}

// === ChatMessageView component body ===
const ChatMessageView: React.FC<ChatMessageViewProps> = ({ message, statusText, userName }) => {
  const { t } = useI18n()
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
        {isUser && (message.skill_name || (message.attachments?.length || 0) > 0) && (
          <div className="mb-2 flex flex-wrap items-center justify-end gap-1.5">
            {message.skill_name && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[#4F46E5]/50 bg-accent-soft/30 px-2.5 py-1 text-[11px] text-accent-ink">
                <span className="text-xs leading-none" aria-hidden="true">{message.skill_icon || '🧩'}</span>
                {message.skill_name}
              </span>
            )}
            {message.attachments?.map((attachment) => (
              <span
                key={attachment.id}
                className="inline-flex max-w-[230px] items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-[11px] text-foreground"
                title={attachment.name}
              >
                <Paperclip className="h-3 w-3 shrink-0 text-muted-foreground" />
                <span className="truncate">{attachment.name}</span>
              </span>
            ))}
          </div>
        )}

        {/* Text message */}
        {message.type === 'text' && (
          message.content ? (
            <div
              className={cn(
                'inline-block rounded-card px-4 py-2.5 text-body-md leading-relaxed',
                isUser
                  ? 'ml-auto max-w-[70%] bg-[rgba(99,102,241,0.15)] border border-[rgba(99,102,241,0.25)] text-foreground shadow-[0_0_12px_rgba(99,102,241,0.08)]'
                  : 'mr-auto max-w-[75%] bg-card/50 border-l-2 border-[rgba(99,102,241,0.2)] rounded-r-card px-4 py-2.5 text-muted-foreground',
              )}
            >
              <span className="whitespace-pre-wrap break-words">{renderRichText(message.content)}</span>
              {message.isStreaming && (
                <span className="inline-block w-[7px] h-[14px] bg-[#818CF8] ml-0.5 align-middle animate-pulse" />
              )}
            </div>
          ) : message.isStreaming ? (
            <div className="flex items-center gap-2 py-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-accent-ink" />
              <span className="text-[13px] text-muted-foreground">{statusText || t("思考中…")}</span>
            </div>
          ) : null
        )}

        {/* Tool result */}
        {message.type === 'tool_result' && message.toolCall && (
          <div className="inline-flex items-center gap-2 rounded-lg bg-background/60 border border-border px-3 py-2">
            {message.toolCall.status === 'success' ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-success-ink" />
            ) : message.toolCall.status === 'error' ? (
              <AlertCircle className="w-3.5 h-3.5 text-danger-ink" />
            ) : (
              <Loader2 className="w-3.5 h-3.5 text-warning-ink animate-spin" />
            )}
            <Wrench className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-[12px] font-medium text-muted-foreground">{toolActionLabel(message.toolCall.tool)}</span>
            <span className="text-[12px] text-muted-foreground">{toolStatusLabel(message.toolCall.status)}</span>
          </div>
        )}

        {/* Image (real backend image_url) */}
        {message.type === 'image' && message.image_url && (
          <div className="max-w-md rounded-card overflow-hidden border border-border bg-card">
            <img src={message.image_url} alt={message.prompt || t("生成图片")} className="w-full h-auto block" />
            {message.prompt && (
              <p className="px-3 py-2 text-[12px] text-muted-foreground border-t border-border">{message.prompt}</p>
            )}
          </div>
        )}

        {/* Video pending (real backend task progress) */}
        {message.type === 'video_pending' && (
          <div className="max-w-md rounded-card border border-border bg-background p-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-[rgba(99,102,241,0.15)] flex items-center justify-center shrink-0">
                <Loader2 className="w-5 h-5 text-accent-ink animate-spin" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-[13px] font-medium text-foreground">
                  <Film className="w-3.5 h-3.5 text-info-ink" />

                  {t("视频生成中…")}
                </div>
                <p className="mt-0.5 text-[12px] text-muted-foreground line-clamp-2">{message.prompt}</p>
                <div className="mt-2 flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-[#6366F1] transition-all"
                      style={{ width: `${message.progress || 0}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-muted-foreground tabular-nums">
                    {message.status || t("排队中")}
                    {message.progress ? ` · ${message.progress}%` : ''}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Video ready (real backend video_url) */}
        {message.type === 'video' && message.video_url && (
          <div className="max-w-lg rounded-card overflow-hidden border border-border bg-card">
            <video src={message.video_url} controls preload="metadata" className="w-full h-auto block" />
            <div className="flex items-center justify-between px-3 py-2 border-t border-border">
              <span className="text-[12px] text-muted-foreground line-clamp-1">{message.prompt}</span>
              <a
                href={message.video_url}
                download
                className="inline-flex items-center gap-1 text-[12px] text-accent-ink hover:text-accent-ink shrink-0"
              >
                <Download className="w-3.5 h-3.5" />  {t("下载")}
              </a>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default React.memo(ChatMessageView)
