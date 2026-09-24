import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Bell, Loader2, Plus, Radar, Signal, Target, Users } from 'lucide-react'
import {
  acquisitionAddMonitorTarget,
  acquisitionLeads,
  acquisitionMonitorTargets,
  type LeadItem,
  type MonitorTarget,
} from '@/lib/api'
import {
  EmptyState,
  FieldLabel,
  MetricCard,
  PLATFORM_OPTIONS,
  PageShell,
  Panel,
  StatusPill,
  buttonPrimary,
  formatDateTime,
  inputClass,
  platformLabel,
} from './MarketingShared'
import { useI18n } from '@/lib/i18n'

export default function Listen() {
  const { t } = useI18n()
  const [targets, setTargets] = useState<MonitorTarget[]>([])
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [platform, setPlatform] = useState('douyin')
  const [videoUrl, setVideoUrl] = useState('')
  const [videoTitle, setVideoTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const highIntent = useMemo(
    () => leads.filter((item) => ['a', 's', '高', 'high'].includes(String(item.grade || '').toLowerCase())).length,
    [leads],
  )

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [targetData, leadData] = await Promise.all([
        acquisitionMonitorTargets(),
        acquisitionLeads({ limit: 20 }),
      ])
      setTargets(targetData.targets || [])
      setLeads(leadData.leads || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : t("机会监听数据加载失败"))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const addTarget = async () => {
    if (!videoUrl.trim() && !videoTitle.trim()) {
      setError(t("请输入目标链接或标题"))
      return
    }
    setSaving(true)
    setError('')
    try {
      await acquisitionAddMonitorTarget({
        platform,
        video_url: videoUrl.trim(),
        video_title: videoTitle.trim(),
        owner: 'own',
        poll_interval: 300,
      })
      setVideoUrl('')
      setVideoTitle('')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("新增监听目标失败"))
    } finally {
      setSaving(false)
    }
  }

  return (
    <PageShell title={t("机会监听")} subtitle={t("持续监听目标内容和评论互动，把高意向评论沉淀为线索。")} icon={Radar}>
      {error && <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#FCA5A5]">{error}</div>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label={t("监听目标")} value={targets.length} icon={Target} />
        <MetricCard label={t("识别线索")} value={leads.length} icon={Users} tone="green" />
        <MetricCard label={t("高意向机会")} value={highIntent} icon={Bell} tone="amber" />
        <MetricCard label={t("异常目标")} value={targets.filter((item) => String(item.status || '').includes('error')).length} icon={AlertTriangle} tone="red" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
        <Panel title={t("新增监听目标")} description={t("添加视频、笔记或关键词目标，后续评论会进入线索识别。")}>
          <div className="space-y-4">
            <div>
              <FieldLabel>{t("平台")}</FieldLabel>
              <select value={platform} onChange={(e) => setPlatform(e.target.value)} className={inputClass}>
                {PLATFORM_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </div>
            <div>
              <FieldLabel>{t("目标标题")}</FieldLabel>
              <input value={videoTitle} onChange={(e) => setVideoTitle(e.target.value)} className={inputClass} placeholder={t("例如：同城装修避坑分享")} />
            </div>
            <div>
              <FieldLabel>{t("目标链接")}</FieldLabel>
              <input value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} className={inputClass} placeholder={t("视频或笔记链接")} />
            </div>
            <button onClick={addTarget} disabled={saving} className={`${buttonPrimary} w-full`}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}

              {t("加入监听")}
            </button>
          </div>
        </Panel>

        <Panel title={t("监听目标列表")} description={t("关注最近检查时间、平台状态和异常目标。")}>
          {loading ? (
            <div className="flex h-40 items-center justify-center text-[#64748B]"><Loader2 className="h-6 w-6 animate-spin" /></div>
          ) : targets.length === 0 ? (
            <EmptyState title={t("暂无监听目标")} description={t("从智能截流页选择高质量目标，或在这里手动添加目标链接。")} />
          ) : (
            <div className="space-y-3">
              {targets.map((item, index) => (
                <div key={item.target_id || item.id || index} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-[#F1F5F9]">{item.video_title || item.video_url || item.video_id || t("未命名目标")}</p>
                      <p className="mt-1 text-xs text-[#64748B]">{platformLabel(item.platform)}  {t("· 最近检查")} {formatDateTime(item.last_poll_at || item.last_checked_at)}</p>
                    </div>
                    <StatusPill status={item.status || 'active'} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title={t("新机会流")} description={t("由监听评论识别出的潜在线索，高意向优先处理。")}>
        {leads.length === 0 ? (
          <EmptyState title={t("暂无新线索")} description={t("监听目标产生互动后，高意向评论会在这里出现。")} />
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {leads.map((item, index) => (
              <div key={item.id || item.lead_id || index} className="rounded-lg border border-[#1E293B] bg-[#0B0F1A] p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-[#F1F5F9]">{item.user_name || item.author_name || t("潜在线索")}</p>
                  <span className="rounded-full border border-[#F59E0B]/25 bg-[#F59E0B]/10 px-2 py-1 text-xs text-[#FCD34D]">
                    {item.grade || item.lead_score || item.score || t("待评分")}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-sm text-[#CBD5E1]">{item.comment_text || item.content || t("暂无评论内容")}</p>
                <p className="mt-2 text-xs text-[#64748B]"><Signal className="mr-1 inline h-3 w-3" />{platformLabel(item.platform)} · {item.status || t("待跟进")}</p>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </PageShell>
  )
}
