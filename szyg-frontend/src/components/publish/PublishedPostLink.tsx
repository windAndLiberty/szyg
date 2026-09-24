import { ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { translateCurrent, useI18n } from '@/lib/i18n'

type LinkExtraction = {
  status?: string
  method?: string
  message?: string
}

export type PublishedPostInfo = {
  url: string
  postId: string
  title: string
  status: string
  message: string
  method: string
  pending: boolean
  fallback: boolean
  label: string
  heading: string
}

function readString(record: Record<string, unknown>, key: string): string {
  const value = record[key]
  return typeof value === 'string' ? value : ''
}

const PLATFORM_LIST_URLS: Record<string, string> = {
  tencent: 'https://channels.weixin.qq.com/platform/post/list',
  weibo: 'https://weibo.com',
  xhs: 'https://creator.xiaohongshu.com/creator/notes',
  kuaishou: 'https://cp.kuaishou.com/article/manage/video',
  bilibili: 'https://member.bilibili.com/platform/upload-manager/article',
  youtube: 'https://studio.youtube.com/channel/UC/videos',
}

function fallbackUrlFor(platform: string, result: Record<string, unknown>): string {
  return (
    readString(result, 'post_list_url')
    || readString(result, 'profile_url')
    || PLATFORM_LIST_URLS[platform]
    || readString(result, 'publish_url')
    || ''
  )
}

export function getPublishedPostInfo(result?: Record<string, unknown> | null, platform = ''): PublishedPostInfo | null {
  if (!result) return null
  const extraction = (result.link_extraction || {}) as LinkExtraction
  const url = readString(result, 'post_url') || readString(result, 'canonical_url') || readString(result, 'share_url')
  const fallbackUrl = url ? '' : fallbackUrlFor(platform, result)
  const finalUrl = url || fallbackUrl
  const postId = readString(result, 'post_id') || readString(result, 'platform_post_id')
  const title = readString(result, 'published_title') || readString(result, 'title')
  const status = readString(result, 'publish_status') || extraction.status || ''
  const message = extraction.message || ''
  const method = extraction.method || ''
  const lookupStatus = (extraction.status || '').toLowerCase()
  const pending = ['pending', 'pending_review', 'running', 'lookup_running'].includes(lookupStatus)
  if (!finalUrl && ['not_found', 'failed', 'timeout', 'unsupported'].includes(lookupStatus)) return null
  if (!finalUrl && !pending) return null
  if (!finalUrl && !postId && !message) return null
  const fallback = Boolean(!url && finalUrl)
  return {
    url: finalUrl,
    postId,
    title,
    status,
    message,
    method,
    pending: pending && !finalUrl,
    fallback,
    get label() { return translateCurrent("打开") },
    heading: fallback ? translateCurrent("已提供作品列表入口") : translateCurrent("作品链接已回写"),
  }
}

export function PublishedPostLink({
  result,
  platform = '',
  compact = false,
}: {
  result?: Record<string, unknown> | null
  platform?: string
  compact?: boolean
}) {
  const { t } = useI18n()
  const info = getPublishedPostInfo(result, platform)
  if (!info) return null

  const open = () => {
    if (info.url) window.open(info.url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className={`rounded-md border border-[#164E63] bg-[#082F49]/35 ${compact ? 'p-3' : 'p-4'}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-[#E0F2FE]">
            {info.heading}
          </div>
          <div className="mt-1 truncate text-xs text-[#7DD3FC]">
            {info.title || info.postId || info.message || (info.fallback ? t("平台暂未返回单条公开链接") : t("已拿到公开链接"))}
          </div>
        </div>
        {info.url && (
          <Button type="button" size="sm" variant="outline" onClick={open}>
            <ExternalLink className="h-4 w-4" />
            {info.label}
          </Button>
        )}
      </div>
      {!compact && (
        <div className="mt-3 space-y-1 text-xs text-[#BAE6FD]">
          {info.url && <div className="break-all">{info.url}</div>}
          {info.status && <div>{t("状态：")}{info.status}</div>}
          {info.method && <div>{t("来源：")}{info.method}</div>}
          {info.fallback && <div>{t("平台没有稳定返回单条链接，已提供可核对的作品列表入口。")}</div>}
        </div>
      )}
    </div>
  )
}
