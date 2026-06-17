'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Calendar, Edit3, Wand2, X, CheckCircle, Clock, AlertCircle, Send } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'

interface Content {
  id: string
  title: string
  content_type: string
  status: string
  ai_generated?: boolean
  scheduled_at?: string
  body?: string
  platforms?: string[]
  tags?: string[]
}

const typeLabels: Record<string, string> = { post: '短帖', article: '长文', video: '视频脚本', image: '图文' }
const statusLabels: Record<string, string> = { draft: '草稿', pending: '待审核', approved: '已批准', published: '已发布', rejected: '已拒绝' }
const statusColors: Record<string, string> = { draft: 'bg-white/10 text-white/50', pending: 'bg-amber-500/10 text-amber-400', approved: 'bg-emerald-500/10 text-emerald-400', published: 'bg-accent/10 text-accent', rejected: 'bg-red-500/10 text-red-400' }
const statusIcons: Record<string, React.ReactNode> = { draft: <Edit3 className="w-3 h-3" />, pending: <Clock className="w-3 h-3" />, approved: <CheckCircle className="w-3 h-3" />, published: <Send className="w-3 h-3" />, rejected: <AlertCircle className="w-3 h-3" /> }

const platformsList = [
  { value: 'all', label: '全平台' }, { value: 'wechat_mp', label: '公众号' },
  { value: 'wecom', label: '企微' }, { value: 'douyin', label: '抖音' },
  { value: 'xhs', label: '小红书' }, { value: 'kuaishou', label: '快手' },
  { value: 'bilibili', label: 'B站' }, { value: 'weibo', label: '微博' },
]

export default function PublisherPage() {
  const [contents, setContents] = useState<Content[]>([])
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [showCalendar, setShowCalendar] = useState(false)
  const [showAiGen, setShowAiGen] = useState(false)
  const [editingId, setEditingId] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [currentMonth] = useState(new Date().toISOString().slice(0, 7))
  const [calendarEvents, setCalendarEvents] = useState<Content[]>([])
  const [aiTopic, setAiTopic] = useState('')
  const [aiAgent, setAiAgent] = useState('copywriter')
  const [aiLoading, setAiLoading] = useState(false)
  const [form, setForm] = useState({ title: '', body: '', content_type: 'post', platforms: ['all'], tags: '', scheduled_at: '' })

  const [stats, setStats] = useState([
    { label: '总计', value: 0, color: 'text-white/50' },
    { label: '草稿', value: 0, color: 'text-blue-400' },
    { label: '待审', value: 0, color: 'text-amber-400' },
    { label: '批准', value: 0, color: 'text-emerald-400' },
    { label: '已发布', value: 0, color: 'text-purple-400' },
    { label: '已拒绝', value: 0, color: 'text-red-400' },
  ])

  useEffect(() => { loadContents(); loadStats() }, [filterStatus])

  async function loadContents() {
    setLoading(true)
    try {
      const { data } = await api.get('/api/publisher/contents', { params: { status: filterStatus, limit: 50 } })
      setContents(data)
    } catch {}
    setLoading(false)
  }

  async function loadStats() {
    try {
      const { data } = await api.get('/api/publisher/stats')
      setStats([
        { label: '总计', value: data.total || 0, color: 'text-white/50' },
        { label: '草稿', value: data.drafts || 0, color: 'text-blue-400' },
        { label: '待审', value: data.pending_review || 0, color: 'text-amber-400' },
        { label: '批准', value: data.approved || 0, color: 'text-emerald-400' },
        { label: '已发布', value: data.published || 0, color: 'text-purple-400' },
        { label: '已拒绝', value: data.by_status?.rejected || 0, color: 'text-red-400' },
      ])
      const calRes = await api.get('/api/publisher/calendar', { params: { month: currentMonth } })
      setCalendarEvents(calRes.data)
    } catch {}
  }

  async function saveContent() {
    if (!form.title) return
    try {
      if (editingId) {
        await api.put(`/api/publisher/contents/${editingId}`, null, { params: form })
      } else {
        await api.post('/api/publisher/contents', null, { params: form })
      }
      setShowCreate(false)
      loadContents(); loadStats()
    } catch {}
  }

  function openContent(row: Content) {
    setForm({
      title: row.title, body: row.body || '', content_type: row.content_type,
      platforms: row.platforms || ['all'], tags: (row.tags || []).join(','), scheduled_at: row.scheduled_at || ''
    })
    setEditingId(row.id)
    setShowCreate(true)
  }

  async function doAiGenerate() {
    setAiLoading(true)
    try {
      await api.post('/api/publisher/ai-generate', null, { params: { topic: aiTopic, agent_id: aiAgent } })
      setShowAiGen(false)
      loadContents(); loadStats()
    } catch {}
    setAiLoading(false)
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-white">📝 内容发布管道</h2>
            <p className="text-white/40 text-sm mt-1">管理和发布你的内容到各个平台</p>
          </div>
          <div className="flex gap-2">
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
              onClick={() => setShowCreate(true)}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white text-sm font-medium flex items-center gap-2 shadow-lg shadow-accent/25">
              <Plus className="w-4 h-4" />新建内容
            </motion.button>
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
              onClick={() => setShowCalendar(!showCalendar)}
              className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-sm flex items-center gap-2 hover:bg-white/10 transition-colors">
              <Calendar className="w-4 h-4" />{showCalendar ? '列表' : '日历'}
            </motion.button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-6">
          {stats.map((s) => (
            <motion.div key={s.label} whileHover={{ y: -2 }} className="glass-card p-3 text-center">
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-[10px] text-white/30 mt-1">{s.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Content / Calendar */}
        {!showCalendar ? (
          <div className="glass-card overflow-hidden">
            <div className="flex border-b border-white/5">
              {['', 'draft', 'pending', 'approved', 'published'].map((s) => (
                <button
                  key={s || 'all'}
                  onClick={() => setFilterStatus(s)}
                  className={`px-4 py-3 text-sm transition-all relative ${filterStatus === s ? 'text-white' : 'text-white/30 hover:text-white/60'}`}
                >
                  {s ? statusLabels[s] : '全部'}
                  {filterStatus === s && <motion.div layoutId="pub-tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent" />}
                </button>
              ))}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5 text-xs text-white/30">
                    <th className="text-left px-4 py-3 font-medium">标题</th>
                    <th className="text-left px-4 py-3 font-medium w-24">类型</th>
                    <th className="text-left px-4 py-3 font-medium w-24">状态</th>
                    <th className="text-left px-4 py-3 font-medium w-36">定时发布</th>
                    <th className="text-left px-4 py-3 font-medium w-52">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {contents.map((row) => (
                    <tr key={row.id} className="border-b border-white/[0.02] hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-3">
                        <span onClick={() => openContent(row)} className="text-sm text-accent hover:underline cursor-pointer">{row.title}</span>
                        {row.ai_generated && <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-white/30">AI</span>}
                      </td>
                      <td className="px-4 py-3 text-sm text-white/50">{typeLabels[row.content_type] || row.content_type}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 w-fit ${statusColors[row.status] || ''}`}>
                          {statusIcons[row.status]} {statusLabels[row.status] || row.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-white/30">{row.scheduled_at?.slice(0, 16) || '—'}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1.5">
                          {row.status === 'draft' && (
                            <button onClick={() => api.post(`/api/publisher/contents/${row.id}/submit`).then(() => { loadContents(); loadStats() })} className="px-2 py-1 rounded-lg bg-amber-500/10 text-amber-400 text-xs hover:bg-amber-500/20 transition-colors">提交审核</button>
                          )}
                          {row.status === 'pending' && (
                            <button onClick={() => api.post(`/api/publisher/contents/${row.id}/approve`).then(() => { loadContents(); loadStats() })} className="px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 text-xs hover:bg-emerald-500/20 transition-colors">通过</button>
                          )}
                          {row.status === 'approved' && (
                            <button onClick={() => api.post(`/api/publisher/contents/${row.id}/publish`).then(() => { loadContents(); loadStats() })} className="px-2 py-1 rounded-lg bg-accent/10 text-accent text-xs hover:bg-accent/20 transition-colors">立即发布</button>
                          )}
                          <button onClick={() => openContent(row)} className="px-2 py-1 rounded-lg bg-white/5 text-white/50 text-xs hover:bg-white/10 transition-colors">编辑</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {contents.length === 0 && !loading && (
                <div className="text-center py-12 text-white/20 text-sm">暂无内容</div>
              )}
            </div>
          </div>
        ) : (
          <div className="glass-card p-6">
            <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-accent" /> 📅 内容日历 — {currentMonth}
            </h3>
            {calendarEvents.length === 0 ? (
              <div className="text-center py-12 text-white/20 text-sm">暂无定时发布内容</div>
            ) : (
              <div className="space-y-2">
                {calendarEvents.map((e) => (
                  <div key={e.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5">
                    <span className="text-xs text-accent bg-accent/10 px-2 py-1 rounded">{e.scheduled_at?.slice(0, 16)}</span>
                    <span className="text-sm text-white">{e.title}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Create/Edit Dialog */}
        <AnimatePresence>
          {showCreate && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
              onClick={() => setShowCreate(false)}>
              <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
                onClick={(e) => e.stopPropagation()}
                className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-white/10 bg-[var(--header-bg)]/95 backdrop-blur-xl p-6 shadow-2xl">
                <div className="flex items-center justify-between mb-5">
                  <h3 className="text-lg font-semibold text-white">{editingId ? '编辑内容' : '新建内容'}</h3>
                  <button onClick={() => setShowCreate(false)} className="p-1 rounded-lg hover:bg-white/5 text-white/40 hover:text-white"><X className="w-5 h-5" /></button>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">标题</label>
                    <input value={form.title} onChange={(e) => setForm(f => ({ ...f, title: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
                  </div>
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">类型</label>
                    <select value={form.content_type} onChange={(e) => setForm(f => ({ ...f, content_type: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50">
                      {Object.entries(typeLabels).map(([k, v]) => <option key={k} value={k} className="bg-[var(--header-bg)]">{v}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">正文</label>
                    <textarea value={form.body} onChange={(e) => setForm(f => ({ ...f, body: e.target.value }))} rows={6} placeholder="Markdown格式正文" className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 placeholder:text-white/20 resize-none" />
                  </div>
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">平台</label>
                    <div className="flex flex-wrap gap-2">
                      {platformsList.map((p) => (
                        <label key={p.value} className="flex items-center gap-1.5 text-sm text-white/50 cursor-pointer">
                          <input type="checkbox" checked={form.platforms.includes(p.value)} onChange={(e) => {
                            if (e.target.checked) setForm(f => ({ ...f, platforms: [...f.platforms, p.value] }))
                            else setForm(f => ({ ...f, platforms: f.platforms.filter(x => x !== p.value) }))
                          }} className="rounded border-white/20 bg-white/5 text-accent" />
                          {p.label}
                        </label>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">标签</label>
                    <input value={form.tags} onChange={(e) => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="逗号分隔" className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 placeholder:text-white/20" />
                  </div>
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">定时发布</label>
                    <input type="datetime-local" value={form.scheduled_at} onChange={(e) => setForm(f => ({ ...f, scheduled_at: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 [color-scheme:dark]" />
                  </div>
                  <div className="flex gap-3 pt-2">
                    <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={() => setShowAiGen(true)} className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm hover:bg-white/10 transition-colors flex items-center gap-2">
                      <Wand2 className="w-4 h-4 text-accent" /> AI生成草稿
                    </motion.button>
                    <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={saveContent} className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white text-sm font-medium shadow-lg shadow-accent/25">
                      保存
                    </motion.button>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* AI Generate Dialog */}
        <AnimatePresence>
          {showAiGen && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 z-[101] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
              onClick={() => setShowAiGen(false)}>
              <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
                onClick={(e) => e.stopPropagation()}
                className="w-full max-w-md rounded-2xl border border-white/10 bg-[var(--header-bg)]/95 backdrop-blur-xl p-6 shadow-2xl">
                <h3 className="text-lg font-semibold text-white mb-4">AI生成内容</h3>
                <div className="space-y-4">
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">主题</label>
                    <input value={aiTopic} onChange={(e) => setAiTopic(e.target.value)} placeholder="输入主题" className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 placeholder:text-white/20" />
                  </div>
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">Agent</label>
                    <select value={aiAgent} onChange={(e) => setAiAgent(e.target.value)} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50">
                      <option className="bg-[var(--header-bg)]" value="copywriter">营销文案师</option>
                      <option className="bg-[var(--header-bg)]" value="video-script-writer">视频脚本生成器</option>
                      <option className="bg-[var(--header-bg)]" value="general-assistant">通用助手</option>
                    </select>
                  </div>
                  <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={doAiGenerate} disabled={aiLoading}
                    className="w-full py-2.5 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white text-sm font-medium shadow-lg shadow-accent/25 disabled:opacity-50 flex items-center justify-center gap-2">
                    {aiLoading && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                    生成
                  </motion.button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  )
}
