'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus, Play, Pause, Trash2, Eye, MessageSquarePlus, Activity,
  CheckCircle2, AlertCircle, Clock, XCircle, RefreshCw,
  Globe, ChevronDown, Filter, Search, BarChart3,
} from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

// ── Types ─────────────────────────────────────────────

interface CommentTask {
  id: string
  name: string
  target_platform: 'douyin' | 'xiaohongshu' | 'kuaishou' | 'shipinhao'
  target_account: string
  trigger_type: string
  trigger_keywords: string[]
  status: string
  status_message: string | null
  risk_level: 'conservative' | 'standard' | 'aggressive'
  daily_limit: number
  cooldown_seconds: number
  persona: string
  comment_style: string
  max_length: number
  require_approval: boolean
  total_executed: number
  total_failed: number
  total_deleted: number
  created_at: string
  updated_at: string
  auto_start: boolean
}

interface DashboardStats {
  total_tasks: number
  active_tasks: number
  paused_tasks: number
  failed_tasks: number
  today_executed: number
  platform_distribution: Record<string, number>
}

// ── Status Config ─────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  monitoring: { label: '监控中', color: 'bg-sky-500/15 text-sky-300 border-sky-500/20', icon: <Activity className="w-3.5 h-3.5" /> },
  analyzing: { label: '分析中', color: 'bg-violet-500/15 text-violet-300 border-violet-500/20', icon: <Eye className="w-3.5 h-3.5" /> },
  generating: { label: '生成中', color: 'bg-orange-500/15 text-orange-300 border-orange-500/20', icon: <RefreshCw className="w-3.5 h-3.5" /> },
  reviewing: { label: '待审核', color: 'bg-amber-500/15 text-amber-300 border-amber-500/20', icon: <Clock className="w-3.5 h-3.5" /> },
  queued: { label: '排队中', color: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/20', icon: <Clock className="w-3.5 h-3.5" /> },
  executed: { label: '已执行', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20', icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
  follow_up: { label: '需跟进', color: 'bg-pink-500/15 text-pink-300 border-pink-500/20', icon: <MessageSquarePlus className="w-3.5 h-3.5" /> },
  deleted: { label: '已删除', color: 'bg-slate-500/15 text-slate-300 border-slate-500/20', icon: <Trash2 className="w-3.5 h-3.5" /> },
  paused: { label: '已暂停', color: 'bg-red-500/15 text-red-300 border-red-500/20', icon: <Pause className="w-3.5 h-3.5" /> },
  failed: { label: '失败', color: 'bg-rose-700/20 text-rose-300 border-rose-700/30', icon: <XCircle className="w-3.5 h-3.5" /> },
}

const PLATFORM_LABELS: Record<string, string> = {
  douyin: '抖音',
  xiaohongshu: '小红书',
  kuaishou: '快手',
  shipinhao: '视频号',
}

const RISK_LABELS: Record<string, { label: string; color: string }> = {
  conservative: { label: '保守', color: 'bg-emerald-500/15 text-emerald-300' },
  standard: { label: '标准', color: 'bg-amber-500/15 text-amber-300' },
  aggressive: { label: '激进', color: 'bg-red-500/15 text-red-300' },
}

// ── Components ────────────────────────────────────────

export default function SmartCommentPage() {
  const router = useRouter()
  const [tasks, setTasks] = useState<CommentTask[]>([])
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [detailTask, setDetailTask] = useState<CommentTask | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [tasksRes, dashRes] = await Promise.all([
        api.get('/api/comment/tasks', { params: { status: filterStatus || undefined, limit: 100 } }),
        api.get('/api/comment/dashboard'),
      ])
      setTasks(tasksRes.data)
      setStats(dashRes.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [filterStatus])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const filteredTasks = tasks.filter((t) =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.target_account.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handlePause = async (id: string) => {
    await api.post(`/api/comment/tasks/${id}/pause`)
    fetchData()
  }

  const handleResume = async (id: string) => {
    await api.post(`/api/comment/tasks/${id}/resume`)
    fetchData()
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此任务？')) return
    await api.delete(`/api/comment/tasks/${id}`)
    fetchData()
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <MessageSquarePlus className="w-5 h-5 text-sky-400" />
              智能评论
            </h1>
            <p className="text-sm text-white/40 mt-1">
              在指定账号或视频组下自动进行高情商互动评论，引导关注
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent text-white text-sm font-medium hover:bg-accent-dark transition-colors shadow-lg shadow-accent/20"
          >
            <Plus className="w-4 h-4" />
            新建任务
          </button>
        </div>

        {/* Dashboard Cards */}
        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <StatCard label="总任务" value={stats.total_tasks} color="from-sky-500/20 to-blue-500/20" />
            <StatCard label="活跃中" value={stats.active_tasks} color="from-emerald-500/20 to-teal-500/20" />
            <StatCard label="已暂停" value={stats.paused_tasks} color="from-amber-500/20 to-orange-500/20" />
            <StatCard label="今日执行" value={stats.today_executed} color="from-violet-500/20 to-purple-500/20" />
            <StatCard label="异常" value={stats.failed_tasks} color="from-red-500/20 to-rose-500/20" />
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <input
              type="text"
              placeholder="搜索任务名称或目标账号..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-xl bg-white/[0.03] border border-white/5 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/30 transition-colors"
            />
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="pl-10 pr-8 py-2 rounded-xl bg-white/[0.03] border border-white/5 text-white text-sm focus:outline-none focus:border-accent/30 appearance-none cursor-pointer"
            >
              <option value="">全部状态</option>
              <option value="monitoring">监控中</option>
              <option value="analyzing">分析中</option>
              <option value="queued">排队中</option>
              <option value="executed">已执行</option>
              <option value="paused">已暂停</option>
              <option value="failed">失败</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/30 pointer-events-none" />
          </div>
        </div>

        {/* Task List */}
        <div className="glass-card overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-white/30 text-sm">加载中...</div>
          ) : filteredTasks.length === 0 ? (
            <div className="p-12 text-center">
              <MessageSquarePlus className="w-12 h-12 text-white/10 mx-auto mb-3" />
              <p className="text-white/30 text-sm">暂无任务</p>
              <button
                onClick={() => setShowCreate(true)}
                className="mt-3 text-accent text-sm hover:underline"
              >
                创建第一个智能评论任务
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-white/30">
                    <th className="text-left px-4 py-3 font-medium">任务</th>
                    <th className="text-left px-4 py-3 font-medium">目标</th>
                    <th className="text-left px-4 py-3 font-medium">状态</th>
                    <th className="text-left px-4 py-3 font-medium">风控</th>
                    <th className="text-left px-4 py-3 font-medium">统计</th>
                    <th className="text-right px-4 py-3 font-medium">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredTasks.map((task) => {
                    const status = STATUS_CONFIG[task.status] || STATUS_CONFIG.monitoring
                    const risk = RISK_LABELS[task.risk_level] || RISK_LABELS.standard
                    return (
                      <tr key={task.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-4 py-3">
                          <div className="font-medium text-white">{task.name}</div>
                          <div className="text-xs text-white/30 mt-0.5">{task.persona.slice(0, 20)}...</div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-white/70">{PLATFORM_LABELS[task.target_platform]}</div>
                          <div className="text-xs text-white/30 truncate max-w-[120px]">{task.target_account}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border', status.color)}>
                            {status.icon}
                            {status.label}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn('inline-flex px-2 py-0.5 rounded text-xs', risk.color)}>
                            {risk.label}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-xs text-white/40 space-y-0.5">
                            <div>成功 {task.total_executed}</div>
                            <div>失败 {task.total_failed}</div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => setDetailTask(task)}
                              className="p-1.5 rounded-lg text-white/30 hover:text-white hover:bg-white/5 transition-colors"
                              title="详情"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                            {task.status === 'paused' ? (
                              <button
                                onClick={() => handleResume(task.id)}
                                className="p-1.5 rounded-lg text-white/30 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                                title="恢复"
                              >
                                <Play className="w-4 h-4" />
                              </button>
                            ) : (
                              <button
                                onClick={() => handlePause(task.id)}
                                className="p-1.5 rounded-lg text-white/30 hover:text-amber-400 hover:bg-amber-500/10 transition-colors"
                                title="暂停"
                              >
                                <Pause className="w-4 h-4" />
                              </button>
                            )}
                            <button
                              onClick={() => handleDelete(task.id)}
                              className="p-1.5 rounded-lg text-white/30 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                              title="删除"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      <AnimatePresence>
        {showCreate && <CreateTaskModal onClose={() => setShowCreate(false)} onCreated={fetchData} />}
      </AnimatePresence>

      {/* Detail Modal */}
      <AnimatePresence>
        {detailTask && <TaskDetailModal task={detailTask} onClose={() => setDetailTask(null)} onRefresh={fetchData} />}
      </AnimatePresence>
    </AppLayout>
  )
}

// ── Sub-components ────────────────────────────────────

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className={cn('glass-card p-4 relative overflow-hidden', 'shadow-lg')}
    >
      <div className={cn('absolute -right-4 -top-4 w-20 h-20 rounded-full bg-gradient-to-br blur-2xl opacity-50', color)} />
      <div className="relative z-10">
        <div className="text-2xl font-bold text-white">{value}</div>
        <div className="text-xs text-white/40 mt-1">{label}</div>
      </div>
    </motion.div>
  )
}

function CreateTaskModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    name: '',
    target_platform: 'xiaohongshu' as const,
    target_account: '',
    trigger_type: 'new_video' as const,
    trigger_keywords: '',
    risk_level: 'standard' as const,
    daily_limit: 10,
    cooldown_seconds: 300,
    persona: '专业但友好的行业从业者',
    comment_style: 'casual' as const,
    max_length: 100,
    require_approval: false,
    auto_start: false,
  })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await api.post('/api/comment/tasks', {
        ...form,
        trigger_keywords: form.trigger_keywords.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      })
      onCreated()
      onClose()
    } catch (err) {
      alert('创建失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-white/10 bg-[var(--header-bg)]/95 backdrop-blur-xl p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">新建智能评论任务</h2>
          <button onClick={onClose} className="text-white/30 hover:text-white transition-colors">
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="任务名称">
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="如：小红书美妆号互动"
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/30"
              />
            </Field>
            <Field label="目标平台">
              <select
                value={form.target_platform}
                onChange={(e) => setForm({ ...form, target_platform: e.target.value as any })}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm focus:outline-none focus:border-accent/30"
              >
                <option value="xiaohongshu">小红书</option>
                <option value="douyin">抖音</option>
                <option value="kuaishou">快手</option>
                <option value="shipinhao">视频号</option>
              </select>
            </Field>
          </div>

          <Field label="目标账号">
            <input
              required
              value={form.target_account}
              onChange={(e) => setForm({ ...form, target_account: e.target.value })}
              placeholder="博主ID 或 主页链接"
              className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/30"
            />
          </Field>

          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="触发类型">
              <select
                value={form.trigger_type}
                onChange={(e) => setForm({ ...form, trigger_type: e.target.value as any })}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm focus:outline-none focus:border-accent/30"
              >
                <option value="new_video">新视频发布</option>
                <option value="keyword">关键词触发</option>
                <option value="hot_comment">热评出现</option>
              </select>
            </Field>
            <Field label="触发关键词（用逗号分隔）">
              <input
                value={form.trigger_keywords}
                onChange={(e) => setForm({ ...form, trigger_keywords: e.target.value })}
                placeholder="如：推荐,种草,测评"
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/30"
              />
            </Field>
          </div>

          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="风控等级">
              <select
                value={form.risk_level}
                onChange={(e) => setForm({ ...form, risk_level: e.target.value as any })}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm focus:outline-none focus:border-accent/30"
              >
                <option value="conservative">保守（低频长冷却）</option>
                <option value="standard">标准</option>
                <option value="aggressive">激进（高频短冷却）</option>
              </select>
            </Field>
            <Field label="每日上限">
              <input
                type="number"
                min={1}
                max={100}
                value={form.daily_limit}
                onChange={(e) => setForm({ ...form, daily_limit: parseInt(e.target.value) })}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm focus:outline-none focus:border-accent/30"
              />
            </Field>
            <Field label="冷却间隔（秒）">
              <input
                type="number"
                min={60}
                value={form.cooldown_seconds}
                onChange={(e) => setForm({ ...form, cooldown_seconds: parseInt(e.target.value) })}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm focus:outline-none focus:border-accent/30"
              />
            </Field>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="评论人格">
              <input
                value={form.persona}
                onChange={(e) => setForm({ ...form, persona: e.target.value })}
                placeholder="如：专业但友好的行业从业者"
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/30"
              />
            </Field>
            <Field label="评论风格">
              <select
                value={form.comment_style}
                onChange={(e) => setForm({ ...form, comment_style: e.target.value as any })}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm focus:outline-none focus:border-accent/30"
              >
                <option value="professional">专业严谨</option>
                <option value="casual">轻松随意</option>
                <option value="humorous">幽默风趣</option>
                <option value="emotional">情感共鸣</option>
              </select>
            </Field>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="最大字数">
              <input
                type="number"
                min={10}
                max={500}
                value={form.max_length}
                onChange={(e) => setForm({ ...form, max_length: parseInt(e.target.value) })}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-white text-sm focus:outline-none focus:border-accent/30"
              />
            </Field>
          </div>

          <div className="flex items-center gap-6 pt-2">
            <label className="flex items-center gap-2 text-sm text-white/60 cursor-pointer">
              <input
                type="checkbox"
                checked={form.require_approval}
                onChange={(e) => setForm({ ...form, require_approval: e.target.checked })}
                className="rounded border-white/20 bg-white/5 text-accent"
              />
              发送前需人工审核
            </label>
            <label className="flex items-center gap-2 text-sm text-white/60 cursor-pointer">
              <input
                type="checkbox"
                checked={form.auto_start}
                onChange={(e) => setForm({ ...form, auto_start: e.target.checked })}
                className="rounded border-white/20 bg-white/5 text-accent"
              />
              创建后立即启动
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-white/60 hover:text-white hover:bg-white/5 text-sm transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-dark transition-colors disabled:opacity-50"
            >
              {submitting ? '创建中...' : '创建任务'}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  )
}

function TaskDetailModal({ task, onClose, onRefresh }: { task: CommentTask; onClose: () => void; onRefresh: () => void }) {
  const [transitions, setTransitions] = useState<any[]>([])
  const [records, setRecords] = useState<any[]>([])
  const [activeTab, setActiveTab] = useState<'overview' | 'transitions' | 'records'>('overview')

  useEffect(() => {
    Promise.all([
      api.get(`/api/comment/tasks/${task.id}/transitions`),
      api.get(`/api/comment/tasks/${task.id}/records`),
    ]).then(([tRes, rRes]) => {
      setTransitions(tRes.data)
      setRecords(rRes.data)
    })
  }, [task.id])

  const status = STATUS_CONFIG[task.status] || STATUS_CONFIG.monitoring
  const risk = RISK_LABELS[task.risk_level] || RISK_LABELS.standard

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-3xl max-h-[85vh] overflow-y-auto rounded-2xl border border-white/10 bg-[var(--header-bg)]/95 backdrop-blur-xl p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border', status.color)}>
              {status.icon}
              {status.label}
            </span>
            <h2 className="text-lg font-semibold text-white">{task.name}</h2>
          </div>
          <button onClick={onClose} className="text-white/30 hover:text-white transition-colors">
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-4 border-b border-white/5 pb-1">
          {[
            { key: 'overview', label: '概览' },
            { key: 'transitions', label: '状态流转' },
            { key: 'records', label: '执行记录' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm transition-colors',
                activeTab === tab.key ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/70'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'overview' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <InfoItem label="目标平台" value={PLATFORM_LABELS[task.target_platform]} />
              <InfoItem label="目标账号" value={task.target_account} />
              <InfoItem label="风控等级" value={<span className={cn('px-2 py-0.5 rounded text-xs', risk.color)}>{risk.label}</span>} />
              <InfoItem label="每日上限" value={`${task.daily_limit} 条`} />
              <InfoItem label="冷却间隔" value={`${task.cooldown_seconds} 秒`} />
              <InfoItem label="最大字数" value={`${task.max_length} 字`} />
              <InfoItem label="评论人格" value={task.persona} />
              <InfoItem label="触发类型" value={task.trigger_type === 'new_video' ? '新视频' : task.trigger_type === 'keyword' ? '关键词' : '热评'} />
            </div>
            {task.trigger_keywords.length > 0 && (
              <div>
                <div className="text-xs text-white/30 mb-1">触发关键词</div>
                <div className="flex flex-wrap gap-1.5">
                  {task.trigger_keywords.map((kw) => (
                    <span key={kw} className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5 text-xs text-white/60">
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div className="grid grid-cols-3 gap-3 pt-2">
              <div className="glass-card p-3 text-center">
                <div className="text-xl font-bold text-emerald-400">{task.total_executed}</div>
                <div className="text-xs text-white/30">成功</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className="text-xl font-bold text-red-400">{task.total_failed}</div>
                <div className="text-xs text-white/30">失败</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className="text-xl font-bold text-slate-400">{task.total_deleted}</div>
                <div className="text-xs text-white/30">被删</div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'transitions' && (
          <div className="space-y-2">
            {transitions.length === 0 ? (
              <div className="text-center py-8 text-white/20 text-sm">暂无状态流转记录</div>
            ) : (
              transitions.map((t) => (
                <div key={t.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5">
                  <div className="text-xs text-white/30 w-24">{new Date(t.created_at).toLocaleString('zh-CN')}</div>
                  <div className="flex items-center gap-2 flex-1">
                    <span className="text-xs text-white/50">{STATUS_CONFIG[t.from_status]?.label || t.from_status}</span>
                    <span className="text-white/20">→</span>
                    <span className="text-xs text-white">{STATUS_CONFIG[t.to_status]?.label || t.to_status}</span>
                  </div>
                  <div className="text-xs text-white/30">{t.reason}</div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'records' && (
          <div className="space-y-2">
            {records.length === 0 ? (
              <div className="text-center py-8 text-white/20 text-sm">暂无执行记录</div>
            ) : (
              records.map((r) => (
                <div key={r.id} className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded',
                      r.status === 'sent' ? 'bg-emerald-500/15 text-emerald-300' :
                      r.status === 'deleted' ? 'bg-slate-500/15 text-slate-300' :
                      'bg-amber-500/15 text-amber-300'
                    )}>
                      {r.status === 'sent' ? '已发' : r.status === 'deleted' ? '已删' : '待发'}
                    </span>
                    <span className="text-xs text-white/30">{new Date(r.created_at).toLocaleString('zh-CN')}</span>
                  </div>
                  <div className="text-sm text-white/70">{r.final_text || r.generated_text}</div>
                </div>
              ))
            )}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-white/40 mb-1.5">{label}</label>
      {children}
    </div>
  )
}

function InfoItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
      <div className="text-xs text-white/30 mb-1">{label}</div>
      <div className="text-sm text-white/80">{value}</div>
    </div>
  )
}
