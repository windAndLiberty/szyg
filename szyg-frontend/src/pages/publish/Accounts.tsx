import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus, KeyRound, Music2, BookOpen, Play, Tv, MessageCircle,
  MoreHorizontal, RefreshCw, Trash2, X, QrCode, Smartphone,
  Cookie, ChevronDown, ChevronUp, AlertCircle, CheckCircle2,
  Clock, Users, Calendar, BarChart3, Loader2, Wifi, WifiOff,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent } from '@/components/ui/empty'
import {
  fetchPlatforms, triggerPlatformLogin, deletePlatformSession,
  type PlatformInfo,
} from '@/lib/api'

// ── Platform visual config ────────────────────────────────────

const PLATFORM_CONFIG: Record<string, {
  label: string
  icon: typeof Music2
  color: string
  bg: string
  border: string
}> = {
  douyin:    { label: '抖音',   icon: Music2,          color: '#22D3EE', bg: 'rgba(34,211,238,0.12)',  border: 'rgba(34,211,238,0.3)' },
  xhs:       { label: '小红书', icon: BookOpen,        color: '#FF2442', bg: 'rgba(255,36,66,0.12)',   border: 'rgba(255,36,66,0.3)' },
  kuaishou:  { label: '快手',   icon: Play,            color: '#FF6B00', bg: 'rgba(255,107,0,0.12)',   border: 'rgba(255,107,0,0.3)' },
  bilibili:  { label: 'B站',    icon: Tv,              color: '#FB7299', bg: 'rgba(251,114,153,0.12)',  border: 'rgba(251,114,153,0.3)' },
  wechat_mp: { label: '微信',   icon: MessageCircle,   color: '#07C160', bg: 'rgba(7,193,96,0.12)',    border: 'rgba(7,193,96,0.3)' },
}

const LOGIN_METHODS = [
  { id: 'qr', label: '扫码登录', icon: QrCode, desc: '打开浏览器窗口，用手机 App 扫描二维码' },
  { id: 'phone', label: '手机号登录', icon: Smartphone, desc: '在浏览器中输入手机号 + 验证码登录' },
  { id: 'cookie', label: 'Cookie 导入', icon: Cookie, desc: '从浏览器开发者工具导出 Cookie 粘贴导入' },
] as const

// ── Status helpers ────────────────────────────────────────────

type StatusKind = 'online' | 'logging' | 'expired' | 'offline'

function getStatusKind(p: PlatformInfo): StatusKind {
  if (p.session?.valid) return 'online'
  if (p.session?.has_session && !p.session.valid) return 'expired'
  return 'offline'
}

const STATUS_CONFIG: Record<StatusKind, { label: string; variant: 'success' | 'warning' | 'error' | 'muted'; icon: typeof Wifi }> = {
  online:  { label: '在线',   variant: 'success', icon: Wifi },
  logging: { label: '登录中', variant: 'warning', icon: Loader2 },
  expired: { label: '已过期', variant: 'error',   icon: WifiOff },
  offline: { label: '未连接', variant: 'muted',   icon: WifiOff },
}

// ── Format helpers ────────────────────────────────────────────

function fmtNumber(n: number | undefined | null): string {
  if (!n) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return '—'
  }
}

function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return '—'
  }
}

// ── Toast ─────────────────────────────────────────────────────

function Toast({ message, type, onClose }: { message: string; type: 'success' | 'error'; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -20, x: '-50%' }}
      animate={{ opacity: 1, y: 0, x: '-50%' }}
      exit={{ opacity: 0, y: -20, x: '-50%' }}
      className="fixed top-4 left-1/2 z-50 flex items-center gap-3 rounded-card-lg px-5 py-3 shadow-lg"
      style={{
        background: type === 'success'
          ? 'linear-gradient(135deg, rgba(16,185,129,0.2) 0%, rgba(16,185,129,0.1) 100%)'
          : 'linear-gradient(135deg, rgba(239,68,68,0.2) 0%, rgba(239,68,68,0.1) 100%)',
        border: `1px solid ${type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
      }}
    >
      {type === 'success'
        ? <CheckCircle2 className="w-5 h-5 text-[#10B981] shrink-0" />
        : <AlertCircle className="w-5 h-5 text-[#EF4444] shrink-0" />
      }
      <span className="text-sm text-[#F1F5F9]">{message}</span>
      <button onClick={onClose} className="ml-2 text-[#64748B] hover:text-[#94A3B8]">
        <X className="w-4 h-4" />
      </button>
    </motion.div>
  )
}

// ── Account Card ──────────────────────────────────────────────

function AccountCard({
  platform,
  onRelogin,
  onDelete,
  isLoggingIn,
}: {
  platform: PlatformInfo
  onRelogin: (id: string) => void
  onDelete: (id: string) => void
  isLoggingIn: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const cfg = PLATFORM_CONFIG[platform.id] || {
    label: platform.name || platform.id,
    icon: KeyRound,
    color: '#6366F1',
    bg: 'rgba(99,102,241,0.12)',
    border: 'rgba(99,102,241,0.3)',
  }
  const Icon = cfg.icon
  const status = getStatusKind(platform)
  const stCfg = STATUS_CONFIG[status]
  const StatusIcon = status === 'logging' ? Loader2 : stCfg.icon

  // Close menu on click outside
  useEffect(() => {
    if (!showMenu) return
    const handler = () => setShowMenu(false)
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [showMenu])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="relative rounded-card border group"
      style={{
        background: 'linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)',
        borderColor: '#1E293B',
      }}
      onMouseEnter={() => {}}
      onMouseLeave={() => setShowMenu(false)}
    >
      {/* ── Card header ── */}
      <div
        className="flex items-center gap-4 p-5 cursor-pointer"
        onClick={() => platform.session?.has_session && setExpanded(!expanded)}
      >
        {/* Platform icon */}
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}
        >
          <Icon className="w-6 h-6" style={{ color: cfg.color }} />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-[15px] font-semibold text-[#F1F5F9] truncate">
              {platform.nickname || cfg.label}
            </h3>
            <Badge variant={stCfg.variant}>
              <StatusIcon className={`w-3 h-3 mr-1 ${status === 'logging' ? 'animate-spin' : ''}`} />
              {stCfg.label}
            </Badge>
          </div>
          <div className="flex items-center gap-3 mt-1.5 text-xs text-[#64748B]">
            <span className="flex items-center gap-1">
              <Users className="w-3 h-3" />
              粉丝 {fmtNumber(platform.followers)}
            </span>
            {platform.session?.saved_at && (
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {fmtDate(platform.session.saved_at)}
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
          {/* Expand indicator — only for connected accounts */}
          {platform.session?.has_session && (
            <button className="w-8 h-8 flex items-center justify-center rounded-lg text-[#64748B] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)] transition-colors">
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          )}

          {/* [...] menu */}
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-[#64748B] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)] transition-colors"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
            <AnimatePresence>
              {showMenu && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: -4 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full mt-1 w-36 rounded-card-lg border py-1 z-20"
                  style={{
                    background: 'rgba(17,24,39,0.98)',
                    borderColor: '#1E293B',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                  }}
                >
                  {!confirmDelete ? (
                    <button
                      onClick={() => { setConfirmDelete(true); setShowMenu(false) }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[#EF4444] hover:bg-[rgba(239,68,68,0.1)] transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                      删除账号
                    </button>
                  ) : null}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* ── Expanded details ── */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div
              className="px-5 pb-5 pt-0 mx-5 rounded-card-sm mb-5 space-y-3"
              style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}
            >
              <div className="pt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                <DetailItem icon={Calendar} label="最后登录" value={fmtDateTime(platform.session?.saved_at)} />
                <DetailItem icon={Clock} label="Cookie 有效期" value={fmtDate(platform.session?.cookie_expiry)} />
                <DetailItem icon={Cookie} label="Cookie 数量" value={String(platform.session?.cookie_count ?? 0)} />
                <DetailItem icon={BarChart3} label="本周发布" value="—" />
              </div>

              {/* Re-login button */}
              {(status === 'expired' || status === 'offline') && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full mt-2"
                  onClick={(e) => { e.stopPropagation(); onRelogin(platform.id) }}
                  disabled={isLoggingIn}
                >
                  {isLoggingIn
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> 登录中…</>
                    : <><RefreshCw className="w-4 h-4" /> 重新登录</>
                  }
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Re-login for expired (collapsed) ── */}
      {!expanded && (status === 'expired') && (
        <div className="px-5 pb-4">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={(e) => { e.stopPropagation(); onRelogin(platform.id) }}
            disabled={isLoggingIn}
          >
            {isLoggingIn
              ? <><Loader2 className="w-4 h-4 animate-spin" /> 登录中…</>
              : <><RefreshCw className="w-4 h-4" /> 重新登录</>
            }
          </Button>
        </div>
      )}

      {/* ── Confirm delete dialog ── */}
      <AnimatePresence>
        {confirmDelete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 rounded-card flex flex-col items-center justify-center gap-3 z-10 px-6"
            style={{ background: 'rgba(11,15,26,0.95)' }}
          >
            <p className="text-sm text-[#F1F5F9] text-center">
              确定要删除 <span className="font-semibold">{platform.nickname || cfg.label}</span> 的登录态吗？
            </p>
            <p className="text-xs text-[#64748B]">删除后需要重新登录才能使用</p>
            <div className="flex gap-3 mt-1">
              <Button variant="outline" size="sm" onClick={() => setConfirmDelete(false)}>
                取消
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => { onDelete(platform.id); setConfirmDelete(false) }}
              >
                <Trash2 className="w-4 h-4" /> 确认删除
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function DetailItem({ icon: Icon, label, value }: { icon: typeof Clock; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2">
      <Icon className="w-3.5 h-3.5 text-[#64748B] mt-0.5 shrink-0" />
      <div className="flex flex-col min-w-0">
        <span className="text-[11px] text-[#64748B]">{label}</span>
        <span className="text-sm text-[#F1F5F9]">{value}</span>
      </div>
    </div>
  )
}

// ── Add Account Modal ─────────────────────────────────────────

function AddModal({ isOpen, onClose, onAdd, loadingPlatform }: {
  isOpen: boolean
  onClose: () => void
  onAdd: (platformId: string, method: string) => void
  loadingPlatform: string | null
}) {
  const [step, setStep] = useState<'platform' | 'method'>('platform')
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null)
  const [selectedMethod, setSelectedMethod] = useState<string>('qr')

  const handlePlatformSelect = (id: string) => {
    setSelectedPlatform(id)
    setStep('method')
  }

  const handleBack = () => {
    setStep('platform')
    setSelectedMethod('qr')
  }

  const handleConfirm = () => {
    if (selectedPlatform) {
      onAdd(selectedPlatform, selectedMethod)
      onClose()
    }
  }

  // Reset on open
  useEffect(() => {
    if (isOpen) {
      setStep('platform')
      setSelectedPlatform(null)
      setSelectedMethod('qr')
    }
  }, [isOpen])

  if (!isOpen) return null

  const availablePlatforms = Object.entries(PLATFORM_CONFIG)

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-40 flex items-center justify-center p-4"
        style={{ background: 'rgba(0,0,0,0.6)' }}
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          onClick={e => e.stopPropagation()}
          className="w-full max-w-md rounded-card-lg border overflow-hidden"
          style={{
            background: 'linear-gradient(180deg, rgba(26,34,53,0.98) 0%, rgba(17,24,39,0.98) 100%)',
            borderColor: '#1E293B',
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: '#1E293B' }}>
            <div className="flex items-center gap-3">
              {step === 'method' && (
                <button onClick={handleBack} className="text-[#64748B] hover:text-[#F1F5F9] transition-colors">
                  <ChevronDown className="w-5 h-5 rotate-90" />
                </button>
              )}
              <h2 className="text-[16px] font-semibold text-[#F1F5F9]">
                {step === 'platform' ? '选择平台' : '选择登录方式'}
              </h2>
            </div>
            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-[#64748B] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.05)] transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-5">
            {step === 'platform' ? (
              <div className="grid grid-cols-2 gap-3">
                {availablePlatforms.map(([id, cfg]) => {
                  const Icon = cfg.icon
                  return (
                    <button
                      key={id}
                      onClick={() => handlePlatformSelect(id)}
                      className="flex flex-col items-center gap-3 p-4 rounded-card-sm border transition-all hover:scale-[1.02]"
                      style={{
                        background: 'rgba(255,255,255,0.02)',
                        borderColor: '#1E293B',
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = cfg.border }}
                      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = '#1E293B' }}
                    >
                      <div
                        className="w-12 h-12 rounded-xl flex items-center justify-center"
                        style={{ background: cfg.bg }}
                      >
                        <Icon className="w-6 h-6" style={{ color: cfg.color }} />
                      </div>
                      <span className="text-sm font-medium text-[#F1F5F9]">{cfg.label}</span>
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className="space-y-3">
                {LOGIN_METHODS.map(method => {
                  const MIcon = method.icon
                  const isSelected = selectedMethod === method.id
                  return (
                    <button
                      key={method.id}
                      onClick={() => setSelectedMethod(method.id)}
                      className="w-full flex items-start gap-4 p-4 rounded-card-sm border text-left transition-all"
                      style={{
                        background: isSelected ? 'rgba(99,102,241,0.08)' : 'rgba(255,255,255,0.02)',
                        borderColor: isSelected ? '#6366F1' : '#1E293B',
                      }}
                    >
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                        style={{ background: 'rgba(99,102,241,0.12)' }}
                      >
                        <MIcon className="w-5 h-5 text-[#6366F1]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-[#F1F5F9]">{method.label}</div>
                        <div className="text-xs text-[#64748B] mt-0.5">{method.desc}</div>
                      </div>
                      {isSelected && (
                        <CheckCircle2 className="w-5 h-5 text-[#6366F1] shrink-0 mt-2" />
                      )}
                    </button>
                  )
                })}

                <Button
                  className="w-full mt-4"
                  onClick={handleConfirm}
                  disabled={!!loadingPlatform}
                >
                  {loadingPlatform ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> 启动登录…</>
                  ) : (
                    <>开始登录</>
                  )}
                </Button>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

// ── Main Page ─────────────────────────────────────────────────

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
}

export default function Accounts() {
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [loggingInPlatform, setLoggingInPlatform] = useState<string | null>(null)
  const loginPollRef = useRef<number | null>(null)

  const loadPlatforms = useCallback(async () => {
    try {
      setError(null)
      const data = await fetchPlatforms()
      setPlatforms(data.platforms || [])
    } catch (e: any) {
      setError(e?.message || '加载平台列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPlatforms()
  }, [loadPlatforms])

  useEffect(() => {
    const refreshOnFocus = () => loadPlatforms()
    const refreshOnVisible = () => {
      if (document.visibilityState === 'visible') loadPlatforms()
    }
    window.addEventListener('focus', refreshOnFocus)
    document.addEventListener('visibilitychange', refreshOnVisible)
    return () => {
      window.removeEventListener('focus', refreshOnFocus)
      document.removeEventListener('visibilitychange', refreshOnVisible)
      if (loginPollRef.current !== null) {
        window.clearInterval(loginPollRef.current)
      }
    }
  }, [loadPlatforms])

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 4000)
  }

  const pollLoginUntilReady = useCallback((platformId: string) => {
    if (loginPollRef.current !== null) {
      window.clearInterval(loginPollRef.current)
      loginPollRef.current = null
    }

    let attempts = 0
    loginPollRef.current = window.setInterval(async () => {
      attempts += 1
      try {
        const data = await fetchPlatforms()
        const nextPlatforms = data.platforms || []
        setPlatforms(nextPlatforms)
        const target = nextPlatforms.find(p => p.id === platformId)
        if (target?.session?.valid) {
          if (loginPollRef.current !== null) {
            window.clearInterval(loginPollRef.current)
            loginPollRef.current = null
          }
          setLoggingInPlatform(null)
          showToast(`${PLATFORM_CONFIG[platformId]?.label || platformId} login synced`, 'success')
        }
      } catch {
        // Login opens an external browser window; transient failures are expected.
      }

      if (attempts >= 120) {
        if (loginPollRef.current !== null) {
          window.clearInterval(loginPollRef.current)
          loginPollRef.current = null
        }
        setLoggingInPlatform(null)
        loadPlatforms()
      }
    }, 5000)
  }, [loadPlatforms])

  const handleAddAccount = async (platformId: string, _method: string) => {
    setLoggingInPlatform(platformId)
    try {
      const result = await triggerPlatformLogin(platformId)
      if (result.ok) {
        showToast(`已启动 ${PLATFORM_CONFIG[platformId]?.label || platformId} 登录流程，请在浏览器中完成登录`, 'success')
        // Refresh after a delay to give login time
        pollLoginUntilReady(platformId)
      } else {
        showToast(result.message || '启动登录失败', 'error')
      }
    } catch (e: any) {
      showToast(e?.message || '启动登录失败，请重试', 'error')
    } finally {
      setLoggingInPlatform(null)
    }
  }

  const handleRelogin = async (platformId: string) => {
    setLoggingInPlatform(platformId)
    try {
      const result = await triggerPlatformLogin(platformId)
      if (result.ok) {
        showToast(`已启动重新登录流程，请在浏览器中完成`, 'success')
        pollLoginUntilReady(platformId)
      } else {
        showToast(result.message || '重新登录失败', 'error')
      }
    } catch (e: any) {
      showToast(e?.message || '重新登录失败', 'error')
    } finally {
      setLoggingInPlatform(null)
    }
  }

  const handleDelete = async (platformId: string) => {
    try {
      await deletePlatformSession(platformId)
      showToast(`已删除 ${PLATFORM_CONFIG[platformId]?.label || platformId} 登录态`, 'success')
      loadPlatforms()
    } catch (e: any) {
      showToast(e?.message || '删除失败，请重试', 'error')
    }
  }

  const hasConnected = platforms.some(p => p.session?.has_session)

  // ── Loading state ──
  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="h-10 w-48 rounded-lg mb-8" style={{ background: 'rgba(255,255,255,0.03)' }} />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div
              key={i}
              className="rounded-card border p-5 h-40 animate-pulse"
              style={{ background: 'rgba(255,255,255,0.02)', borderColor: '#1E293B' }}
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl" style={{ background: 'rgba(255,255,255,0.05)' }} />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-24 rounded" style={{ background: 'rgba(255,255,255,0.05)' }} />
                  <div className="h-3 w-32 rounded" style={{ background: 'rgba(255,255,255,0.03)' }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // ── Error state ──
  if (error && platforms.length === 0) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <Empty>
          <EmptyHeader>
            <AlertCircle className="w-12 h-12 text-[#EF4444]" />
            <EmptyTitle>加载失败</EmptyTitle>
            <EmptyDescription>{error}</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button onClick={loadPlatforms}>
              <RefreshCw className="w-4 h-4" /> 重新加载
            </Button>
          </EmptyContent>
        </Empty>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Toast */}
      <AnimatePresence>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      </AnimatePresence>

      {/* ── Header ── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-8"
      >
        <div>
          <h1 className="text-[22px] font-semibold text-[#F1F5F9]">平台账号管理</h1>
          <p className="text-sm text-[#64748B] mt-1">
            管理已连接的社会化媒体账号
            {hasConnected && <span className="text-[#10B981]"> · {platforms.filter(p => p.session?.valid).length} 个在线</span>}
          </p>
        </div>
        <Button onClick={() => setShowAddModal(true)}>
          <Plus className="w-4 h-4" /> 添加账号
        </Button>
      </motion.div>

      {/* ── Empty state ── */}
      {!hasConnected && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          <Empty>
            <EmptyHeader>
              <div className="relative mb-2">
                <div
                  className="absolute inset-0 rounded-2xl blur-2xl opacity-40"
                  style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.5) 0%, transparent 70%)' }}
                />
                <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center">
                  <KeyRound className="w-8 h-8 text-white" />
                </div>
              </div>
              <EmptyTitle>暂无平台账号</EmptyTitle>
              <EmptyDescription>点击上方按钮添加第一个社交媒体账号</EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button onClick={() => setShowAddModal(true)} size="lg">
                <Plus className="w-4 h-4" /> 添加账号
              </Button>
            </EmptyContent>
          </Empty>
        </motion.div>
      )}

      {/* ── Account card grid ── */}
      {hasConnected && (
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
        >
          <AnimatePresence mode="popLayout">
            {platforms.map(p => (
              <AccountCard
                key={p.id}
                platform={p}
                onRelogin={handleRelogin}
                onDelete={handleDelete}
                isLoggingIn={loggingInPlatform === p.id}
              />
            ))}
          </AnimatePresence>
        </motion.div>
      )}

      {/* ── Add account modal ── */}
      <AddModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={handleAddAccount}
        loadingPlatform={loggingInPlatform}
      />
    </div>
  )
}
