'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Tags, Search, Filter, Plus, ChevronDown, X, Sparkles,
  TrendingUp, Users, Target, Phone, MessageCircle, ExternalLink,
  Flame, ThermometerSun, Snowflake, UserPlus, BarChart3, RefreshCw,
} from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

// ── Types ───────────────────────────────────────────────

interface Interaction {
  timestamp: string
  platform: string
  content: string
  interaction_type: string
  ai_responded: boolean
  ai_response?: string
}

interface Lead {
  id: string
  name?: string
  platform: string
  platform_account: string
  company?: string
  industry?: string
  tags: string[]
  intent_score: number
  intent_level: 'high' | 'medium' | 'low' | 'cold'
  conversion_stage: string
  interactions: Interaction[]
  source_content?: string
  recommended_action?: string
  followup_deadline?: string
  notes?: string
  created_at: string
}

interface Stats {
  total: number
  today_new: number
  by_intent: Record<string, number>
  by_stage: Record<string, number>
}

// ── Config ──────────────────────────────────────────────

const intentConfig: Record<string, { label: string; icon: React.ReactNode; color: string; bg: string }> = {
  high: { label: '高意向', icon: <Flame className="w-3.5 h-3.5" />, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
  medium: { label: '中意向', icon: <ThermometerSun className="w-3.5 h-3.5" />, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
  low: { label: '低意向', icon: <Snowflake className="w-3.5 h-3.5" />, color: 'text-sky-400', bg: 'bg-sky-500/10 border-sky-500/20' },
  cold: { label: '冷线索', icon: <Snowflake className="w-3.5 h-3.5" />, color: 'text-slate-400', bg: 'bg-slate-500/10 border-slate-500/20' },
}

const stageConfig: Record<string, string> = {
  discovered: '发现', engaged: '已互动', contacted: '已触达',
  qualified: '已确认', negotiating: '洽谈中', won: '已成交', lost: '已流失',
}

const platformLabels: Record<string, string> = {
  douyin: '抖音', xiaohongshu: '小红书', kuaishou: '快手',
  shipinhao: '视频号', wechat: '微信', wecom: '企微', manual: '手动', api: 'API',
}

// ── Page ────────────────────────────────────────────────

export default function LeadManagerPage() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterIntent, setFilterIntent] = useState('')
  const [filterStage, setFilterStage] = useState('')
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [showScoring, setShowScoring] = useState(false)
  const [scoreInput, setScoreInput] = useState('')
  const [scoreResult, setScoreResult] = useState<any>(null)
  const [scoring, setScoring] = useState(false)

  const fetchLeads = useCallback(async () => {
    try {
      const params: Record<string, string> = { limit: '50' }
      if (filterIntent) params.intent_level = filterIntent
      if (filterStage) params.stage = filterStage
      const { data } = await api.get('/api/leads', { params })
      setLeads(data.items)
      setStats(data.stats)
    } catch (e) {
      console.error('Failed to fetch leads', e)
    } finally {
      setLoading(false)
    }
  }, [filterIntent, filterStage])

  useEffect(() => { fetchLeads() }, [fetchLeads])

  // Create dummy leads for demo
  const createDemoLeads = async () => {
    const demos = [
      { platform: 'douyin', account: '张老板', content: '这个多少钱？怎么买？', intent: 'high' },
      { platform: 'xiaohongshu', account: '小李爱吃', content: '在哪里可以买到', intent: 'high' },
      { platform: 'douyin', account: '创业小王', content: '看起来不错，了解一下', intent: 'medium' },
      { platform: 'kuaishou', account: '老张头', content: '收藏了', intent: 'low' },
    ]
    for (const d of demos) {
      try {
        await api.post('/api/leads', {
          platform: d.platform,
          platform_account: d.account,
          source_content: d.content,
          tags: ['demo'],
          intent_level: d.intent,
          intent_score: d.intent === 'high' ? 0.8 : d.intent === 'medium' ? 0.5 : 0.2,
        })
      } catch {}
    }
    fetchLeads()
  }

  const handleScoreIntent = async () => {
    if (!scoreInput.trim()) return
    setScoring(true)
    try {
      const { data } = await api.post('/api/leads/score-intent', {
        platform: 'douyin',
        interaction_content: scoreInput,
        context: '产品营销内容',
      })
      setScoreResult(data)
    } catch {} finally { setScoring(false) }
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Tags className="w-5 h-5 text-emerald-400" />
              线索管家
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                AI拓客引擎
              </span>
            </h1>
            <p className="text-sm text-white/40 mt-1">发现 → AI评估 → 触达 → 跟进 → 转化</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={createDemoLeads}
              className="px-3 py-2 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm hover:text-white hover:bg-white/[0.06] transition-all flex items-center gap-2"
            >
              <UserPlus className="w-4 h-4" /> 生成演示数据
            </button>
            <button
              onClick={() => setShowScoring(true)}
              className="px-3 py-2 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm hover:text-white hover:bg-white/[0.06] transition-all flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4" /> AI意向评分
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-sm font-medium flex items-center gap-2 hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
            >
              <Plus className="w-4 h-4" /> 添加线索
            </button>
          </div>
        </div>

        {/* Stats Bar */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard icon={<Users className="w-4 h-4" />} label="总线索" value={stats.total} color="from-blue-500/20 to-cyan-500/20" />
            <StatCard icon={<TrendingUp className="w-4 h-4" />} label="今日新增" value={stats.today_new} color="from-emerald-500/20 to-teal-500/20" />
            <StatCard icon={<Flame className="w-4 h-4" />} label="高意向" value={stats.by_intent?.high || 0} color="from-red-500/20 to-orange-500/20" />
            <StatCard icon={<Target className="w-4 h-4" />} label="已成交" value={stats.by_stage?.won || 0} color="from-purple-500/20 to-pink-500/20" />
          </div>
        )}

        {/* Filters + Search */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20" />
            <input
              type="text" placeholder="搜索线索..."
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-emerald-500/50 transition-all"
            />
          </div>
          <select
            value={filterIntent} onChange={e => setFilterIntent(e.target.value)}
            className="px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm focus:outline-none focus:border-emerald-500/50"
          >
            <option value="">全部意向</option>
            <option value="high">🔥 高意向</option>
            <option value="medium">🔶 中意向</option>
            <option value="low">🔹 低意向</option>
            <option value="cold">❄️ 冷线索</option>
          </select>
          <select
            value={filterStage} onChange={e => setFilterStage(e.target.value)}
            className="px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm focus:outline-none focus:border-emerald-500/50"
          >
            <option value="">全部阶段</option>
            {Object.entries(stageConfig).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <button onClick={fetchLeads} className="p-2.5 rounded-xl bg-white/[0.03] border border-white/10 text-white/40 hover:text-white transition-all">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Lead List */}
        <div className="grid gap-3">
          {loading ? (
            <div className="glass-card p-8 text-center text-white/30">加载中...</div>
          ) : leads.length === 0 ? (
            <div className="glass-card p-12 text-center">
              <Users className="w-12 h-12 text-white/10 mx-auto mb-4" />
              <p className="text-white/40 mb-4">暂无线索数据</p>
              <button
                onClick={createDemoLeads}
                className="px-4 py-2 rounded-xl bg-emerald-500/10 text-emerald-400 text-sm hover:bg-emerald-500/20 transition-all"
              >
                生成演示数据开始体验
              </button>
            </div>
          ) : (
            leads.map((lead) => {
              const intent = intentConfig[lead.intent_level] || intentConfig.cold
              return (
                <motion.div
                  key={lead.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  onClick={() => setSelectedLead(lead)}
                  className={cn(
                    'glass-card p-4 cursor-pointer hover:border-emerald-500/20 transition-all',
                    selectedLead?.id === lead.id && 'border-emerald-500/30 bg-emerald-500/[0.02]'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className={cn('px-2.5 py-1 rounded-lg text-xs font-medium border', intent.bg, intent.color)}>
                      {intent.icon} {intent.label}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-white text-sm font-medium truncate">
                        {lead.name || lead.platform_account || '未知'}
                      </div>
                      <div className="text-white/30 text-xs flex items-center gap-2">
                        <span>{platformLabels[lead.platform] || lead.platform}</span>
                        {lead.company && <><span>·</span><span>{lead.company}</span></>}
                        {lead.industry && <><span>·</span><span>{lead.industry}</span></>}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-white/40 text-xs">{stageConfig[lead.conversion_stage] || lead.conversion_stage}</div>
                      <div className="text-white/20 text-[10px]">{new Date(lead.created_at).toLocaleDateString('zh-CN')}</div>
                    </div>
                    <ChevronDown className="w-4 h-4 text-white/20" />
                  </div>
                </motion.div>
              )
            })
          )}
        </div>

        {/* Lead Detail Panel */}
        <AnimatePresence>
          {selectedLead && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="glass-card p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-semibold">
                  {selectedLead.name || selectedLead.platform_account || '线索详情'}
                </h3>
                <button onClick={() => setSelectedLead(null)} className="text-white/30 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="grid md:grid-cols-3 gap-4 mb-4">
                <DetailItem label="平台" value={platformLabels[selectedLead.platform] || selectedLead.platform} />
                <DetailItem label="意向评分" value={`${(selectedLead.intent_score * 100).toFixed(0)}分 — ${intentConfig[selectedLead.intent_level]?.label}`} />
                <DetailItem label="转化阶段" value={stageConfig[selectedLead.conversion_stage]} />
                {selectedLead.company && <DetailItem label="公司" value={selectedLead.company} />}
                {selectedLead.industry && <DetailItem label="行业" value={selectedLead.industry} />}
                <DetailItem label="创建时间" value={new Date(selectedLead.created_at).toLocaleString('zh-CN')} />
              </div>

              {selectedLead.tags.length > 0 && (
                <div className="flex gap-2 mb-4 flex-wrap">
                  {selectedLead.tags.map(tag => (
                    <span key={tag} className="px-2 py-1 rounded-lg bg-white/[0.03] border border-white/5 text-white/50 text-xs">
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {selectedLead.recommended_action && (
                <div className="p-4 rounded-xl bg-emerald-500/[0.03] border border-emerald-500/10 mb-4">
                  <div className="text-xs text-emerald-400/60 mb-1">🤖 AI 建议行动</div>
                  <div className="text-sm text-white/70">{selectedLead.recommended_action}</div>
                </div>
              )}

              {selectedLead.source_content && (
                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
                  <div className="text-xs text-white/30 mb-1">触发内容</div>
                  <div className="text-sm text-white/50">{selectedLead.source_content}</div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* AI Scoring Modal */}
        <AnimatePresence>
          {showScoring && (
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
              onClick={() => setShowScoring(false)}
            >
              <motion.div
                initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }}
                onClick={e => e.stopPropagation()}
                className="w-full max-w-lg rounded-2xl border border-white/10 bg-[var(--header-bg)]/95 backdrop-blur-xl p-6 shadow-2xl"
              >
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-accent" /> AI 意向评分
                </h3>
                <textarea
                  value={scoreInput}
                  onChange={e => setScoreInput(e.target.value)}
                  placeholder="输入用户评论/私信内容，AI自动判断意向等级..."
                  className="w-full h-28 px-4 py-3 rounded-xl bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/50 resize-none mb-4"
                />
                <div className="flex gap-2 mb-4">
                  <button
                    onClick={handleScoreIntent}
                    disabled={scoring || !scoreInput.trim()}
                    className="px-4 py-2 rounded-xl bg-accent text-white text-sm disabled:opacity-30 flex items-center gap-2"
                  >
                    {scoring ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                    分析意向
                  </button>
                  <button
                    onClick={() => { setShowScoring(false); setScoreResult(null); setScoreInput('') }}
                    className="px-4 py-2 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm"
                  >
                    关闭
                  </button>
                </div>

                {scoreResult && (
                  <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                    <div className="flex items-center gap-3">
                      <div className={cn('px-3 py-1.5 rounded-lg text-sm font-medium border', intentConfig[scoreResult.intent_level]?.bg, intentConfig[scoreResult.intent_level]?.color)}>
                        {intentConfig[scoreResult.intent_level]?.icon} {intentConfig[scoreResult.intent_level]?.label} — {Math.round(scoreResult.intent_score * 100)}分
                      </div>
                      {scoreResult.should_follow_up && (
                        <span className="text-xs text-emerald-400">✓ 需要跟进</span>
                      )}
                    </div>
                    {scoreResult.intent_signals?.length > 0 && (
                      <div className="text-xs text-white/40">
                        识别信号：{scoreResult.intent_signals.join('、')}
                      </div>
                    )}
                    {scoreResult.suggested_reply && (
                      <div className="p-3 rounded-xl bg-emerald-500/[0.05] border border-emerald-500/10">
                        <div className="text-xs text-emerald-400/60 mb-1">💬 建议回复</div>
                        <div className="text-sm text-white/70">{scoreResult.suggested_reply}</div>
                      </div>
                    )}
                  </motion.div>
                )}
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  )
}

// ── Sub-components ──────────────────────────────────────

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
  return (
    <div className="glass-card p-4 relative overflow-hidden">
      <div className={cn('absolute -right-4 -top-4 w-20 h-20 rounded-full bg-gradient-to-br blur-2xl opacity-30', color)} />
      <div className="relative z-10">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-white/10 to-white/5 flex items-center justify-center text-emerald-400 mb-2">
          {icon}
        </div>
        <div className="text-xl font-bold text-white">{value}</div>
        <div className="text-xs text-white/40">{label}</div>
      </div>
    </div>
  )
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-white/30 mb-1">{label}</div>
      <div className="text-sm text-white/70">{value}</div>
    </div>
  )
}
