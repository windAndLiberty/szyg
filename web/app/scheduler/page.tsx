'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Plus, Play, Pause, CheckCircle, XCircle, Clock, RotateCcw } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'

interface Job {
  id: string
  name: string
  trigger_type: string
  trigger_config?: { cron?: string; minutes?: number }
  action: string
  status: string
  priority: number
  next_run_at?: string
}

interface History {
  id: string
  job_name: string
  status: string
  started_at?: string
  error?: string
  result?: string
}

const triggerLabels: Record<string, string> = { cron: 'Cron定时', interval: '固定间隔', once: '一次性', manual: '手动', event: '事件触发' }
const actionLabels: Record<string, string> = {
  publish_content: '发布内容', generate_content: 'AI生成内容', run_workflow: '执行工作流',
  send_notification: '发送通知', execute_tool: '执行工具', custom: '自定义',
}
const statusLabels: Record<string, string> = { active: '运行中', paused: '已暂停', running: '执行中', completed: '已完成', failed: '失败', disabled: '已禁用' }
const statusColors: Record<string, string> = { active: 'bg-emerald-500/10 text-emerald-400', paused: 'bg-amber-500/10 text-amber-400', running: 'bg-accent/10 text-accent', completed: 'bg-white/5 text-white/40', failed: 'bg-red-500/10 text-red-400', disabled: 'bg-white/5 text-white/30' }

export default function SchedulerPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [history, setHistory] = useState<History[]>([])
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', trigger_type: 'manual', cron: '', interval_minutes: 60, at_time: '', action: 'custom', priority: 5, tags: '' })

  const [stats, setStats] = useState([
    { label: '总任务', value: 0, color: 'text-white/50' },
    { label: '运行中', value: 0, color: 'text-emerald-400' },
    { label: '已暂停', value: 0, color: 'text-amber-400' },
    { label: '已完成', value: 0, color: 'text-blue-400' },
    { label: '失败', value: 0, color: 'text-red-400' },
    { label: '今日执行', value: 0, color: 'text-purple-400' },
  ])

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [jRes, hRes, sRes] = await Promise.all([
        api.get('/api/scheduler/jobs'),
        api.get('/api/scheduler/history', { params: { limit: 20 } }),
        api.get('/api/scheduler/stats'),
      ])
      setJobs(jRes.data)
      setHistory(hRes.data)
      const s = sRes.data
      setStats([
        { label: '总任务', value: s.total_jobs || 0, color: 'text-white/50' },
        { label: '运行中', value: s.active || 0, color: 'text-emerald-400' },
        { label: '已暂停', value: s.paused || 0, color: 'text-amber-400' },
        { label: '已完成', value: s.completed || 0, color: 'text-blue-400' },
        { label: '失败', value: s.failed || 0, color: 'text-red-400' },
        { label: '今日执行', value: s.recent_executions || 0, color: 'text-purple-400' },
      ])
    } catch {}
    setLoading(false)
  }

  async function createJob() {
    if (!form.name) return
    try {
      const params: any = { name: form.name, description: form.description, trigger_type: form.trigger_type, action: form.action, priority: form.priority, tags: form.tags }
      if (form.cron) params.cron = form.cron
      if (form.interval_minutes) params.interval_minutes = form.interval_minutes
      if (form.at_time) params.at_time = form.at_time
      await api.post('/api/scheduler/jobs', null, { params })
      setShowCreate(false)
      loadData()
    } catch {}
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-white">⚡ 智能调度引擎</h2>
            <p className="text-white/40 text-sm mt-1">自动化任务调度与管理</p>
          </div>
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white text-sm font-medium flex items-center gap-2 shadow-lg shadow-accent/25">
            <Plus className="w-4 h-4" />新建任务
          </motion.button>
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

        {/* Jobs Table */}
        <div className="glass-card overflow-hidden mb-6">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5 text-xs text-white/30">
                  <th className="text-left px-4 py-3 font-medium">任务名称</th>
                  <th className="text-left px-4 py-3 font-medium w-24">触发方式</th>
                  <th className="text-left px-4 py-3 font-medium w-32">触发配置</th>
                  <th className="text-left px-4 py-3 font-medium w-28">动作</th>
                  <th className="text-left px-4 py-3 font-medium w-20">状态</th>
                  <th className="text-left px-4 py-3 font-medium w-20">优先级</th>
                  <th className="text-left px-4 py-3 font-medium w-36">下次执行</th>
                  <th className="text-left px-4 py-3 font-medium w-40">操作</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((row) => (
                  <tr key={row.id} className="border-b border-white/[0.02] hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3 text-sm text-white font-medium">{row.name}</td>
                    <td className="px-4 py-3 text-sm text-white/50">{triggerLabels[row.trigger_type]}</td>
                    <td className="px-4 py-3">
                      {row.trigger_config?.cron ? (
                        <span className="text-xs px-2 py-1 rounded bg-white/5 text-white/40">{row.trigger_config.cron}</span>
                      ) : row.trigger_config?.minutes ? (
                        <span className="text-xs px-2 py-1 rounded bg-white/5 text-white/40">每{row.trigger_config.minutes}分钟</span>
                      ) : (
                        <span className="text-xs text-white/20">手动</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-white/50">{actionLabels[row.action]}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-1 rounded-full ${statusColors[row.status] || ''}`}>{statusLabels[row.status] || row.status}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-white/40">{row.priority}/10</td>
                    <td className="px-4 py-3 text-sm text-white/30">{row.next_run_at?.slice(0, 16) || '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1.5">
                        <button onClick={() => api.post(`/api/scheduler/jobs/${row.id}/execute`).then(() => loadData())} className="p-1.5 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors">
                          <Play className="w-3.5 h-3.5" />
                        </button>
                        {row.status === 'active' && (
                          <button onClick={() => api.post(`/api/scheduler/jobs/${row.id}/pause`).then(() => loadData())} className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors">
                            <Pause className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {row.status === 'paused' && (
                          <button onClick={() => api.post(`/api/scheduler/jobs/${row.id}/resume`).then(() => loadData())} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors">
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {jobs.length === 0 && !loading && (
              <div className="text-center py-12 text-white/20 text-sm">暂无任务</div>
            )}
          </div>
        </div>

        {/* History */}
        <div className="glass-card p-5">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-accent" /> 📜 执行历史
          </h3>
          <div className="space-y-3">
            {history.map((h) => (
              <div key={h.id} className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5">
                <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${h.status === 'success' ? 'bg-emerald-400' : 'bg-red-400'}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm text-white font-medium">{h.job_name}</span>
                    {h.status === 'success' ? <CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                  </div>
                  <div className="text-xs text-white/20 mb-1">{h.started_at?.slice(0, 19)}</div>
                  {h.error && <div className="text-xs text-red-400">{h.error}</div>}
                  {h.result && <div className="text-xs text-emerald-400">{h.result}</div>}
                </div>
              </div>
            ))}
            {history.length === 0 && (
              <div className="text-center py-8 text-white/20 text-sm">暂无执行记录</div>
            )}
          </div>
        </div>

        {/* Create Dialog */}
        {showCreate && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => setShowCreate(false)}>
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl border border-white/10 bg-[var(--header-bg)]/95 backdrop-blur-xl p-6 shadow-2xl">
              <h3 className="text-lg font-semibold text-white mb-5">新建调度任务</h3>
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-white/30 mb-1.5 block">任务名称</label>
                  <input value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
                </div>
                <div>
                  <label className="text-xs text-white/30 mb-1.5 block">描述</label>
                  <textarea value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} rows={2} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 resize-none" />
                </div>
                <div>
                  <label className="text-xs text-white/30 mb-1.5 block">触发方式</label>
                  <select value={form.trigger_type} onChange={(e) => setForm(f => ({ ...f, trigger_type: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50">
                    {Object.entries(triggerLabels).map(([k, v]) => <option key={k} value={k} className="bg-[var(--header-bg)]">{v}</option>)}
                  </select>
                </div>
                {form.trigger_type === 'cron' && (
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">Cron表达式</label>
                    <input value={form.cron} onChange={(e) => setForm(f => ({ ...f, cron: e.target.value }))} placeholder="0 9 * * *" className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 placeholder:text-white/20" />
                    <p className="text-[11px] text-white/20 mt-1">分 时 日 月 星期 (如: 0 8 * * * = 每天8点)</p>
                  </div>
                )}
                {form.trigger_type === 'interval' && (
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">间隔(分钟)</label>
                    <input type="number" min={1} max={1440} value={form.interval_minutes} onChange={(e) => setForm(f => ({ ...f, interval_minutes: Number(e.target.value) }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
                  </div>
                )}
                {form.trigger_type === 'once' && (
                  <div>
                    <label className="text-xs text-white/30 mb-1.5 block">执行时间</label>
                    <input type="datetime-local" value={form.at_time} onChange={(e) => setForm(f => ({ ...f, at_time: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 [color-scheme:dark]" />
                  </div>
                )}
                <div>
                  <label className="text-xs text-white/30 mb-1.5 block">动作</label>
                  <select value={form.action} onChange={(e) => setForm(f => ({ ...f, action: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50">
                    {Object.entries(actionLabels).map(([k, v]) => <option key={k} value={k} className="bg-[var(--header-bg)]">{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-white/30 mb-1.5 block">优先级 (1-10)</label>
                  <input type="number" min={1} max={10} value={form.priority} onChange={(e) => setForm(f => ({ ...f, priority: Number(e.target.value) }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
                </div>
                <div>
                  <label className="text-xs text-white/30 mb-1.5 block">标签</label>
                  <input value={form.tags} onChange={(e) => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="逗号分隔" className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 placeholder:text-white/20" />
                </div>
                <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={createJob}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white text-sm font-medium shadow-lg shadow-accent/25">
                  创建任务
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </div>
    </AppLayout>
  )
}
