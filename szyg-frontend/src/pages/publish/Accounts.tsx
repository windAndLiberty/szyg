import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus, KeyRound, Music2, BookOpen, Play, Tv, MessageCircle,
  MoreHorizontal, RefreshCw, Trash2, X, QrCode, Smartphone,
  Cookie, ChevronDown, ChevronUp, AlertCircle, CheckCircle2,
  Clock, Users, Calendar, BarChart3, Loader2, Wifi, WifiOff,
  Youtube, MousePointerClick,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent } from '@/components/ui/empty'
import {
  createPlatformAccount,
  createPublishingProfile,
  deletePlatformAccountSession,
  deletePublishingProfile,
  fetchPlatformAccounts,
  fetchPublishingProfiles,
  loginPlatformAccount,
  openWechatDesktop,
  captureWechatInputClick,
  syncPlatformAccountProfile,
  type ChannelAccount,
  type PlatformInfo,
  type PublishingProfile,
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
  tencent:   { label: '视频号', icon: MessageCircle,   color: '#07C160', bg: 'rgba(7,193,96,0.12)',    border: 'rgba(7,193,96,0.3)' },
  youtube:   { label: 'YouTube', icon: Youtube,        color: '#FF0033', bg: 'rgba(255,0,51,0.12)',     border: 'rgba(255,0,51,0.3)' },
  weibo:     { label: '微博',   icon: MessageCircle,   color: '#F97316', bg: 'rgba(249,115,22,0.12)',  border: 'rgba(249,115,22,0.3)' },
}

const CHANNEL_CAPABILITIES: Record<string, { types: string[]; state: string; note: string }> = {
  douyin: { types: ['视频', '图文', '链接回写'], state: '可发布', note: '风控严格，建议低频稳定发布' },
  xhs: { types: ['视频', '图文'], state: '可发布', note: '适合种草内容，建议先预检文案' },
  kuaishou: { types: ['视频', '图文'], state: '可登录', note: '适合短视频和图文分发，资料同步会读取创作者中心' },
  bilibili: { types: ['视频'], state: '可管理', note: '使用 B站投稿工具登录态，适合知识内容和长视频' },
  tencent: { types: ['视频', '图文', '桌面辅助'], state: '桌面辅助', note: '打开真实浏览器视频号助手，支持图文和视频发布' },
  youtube: { types: ['视频'], state: '需配置', note: '适合海外渠道分发' },
  weibo: { types: ['视频', '图文', '桌面辅助'], state: '桌面辅助', note: '使用真实桌面浏览器发布微博内容' },
}

function fallbackPlatform(id: string): PlatformInfo {
  const cfg = PLATFORM_CONFIG[id] || { label: id, icon: KeyRound, color: '#6366F1', bg: '', border: '' }
  return {
    id,
    name: cfg.label,
    adapter: '',
    state: 'unavailable',
    initialized: false,
    nickname: '',
    followers: 0,
    session: {
      has_session: false,
      cookie_count: 0,
      valid: false,
      saved_at: '',
      cookie_expiry: null,
    },
    meta: {
      risk_level: '',
      risk_label: '',
      login_mode: '',
      publish_mode: '',
      description: CHANNEL_CAPABILITIES[id]?.note || '',
    },
  }
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

function accountAvatarUrl(account: ChannelAccount): string {
  if (!account.avatar_url) return ''
  if (account.platform === 'bilibili' || account.platform === 'weibo') {
    return `/api/platform-accounts/avatar?url=${encodeURIComponent(account.avatar_url)}`
  }
  return account.avatar_url
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

function fmtRelativeTimeShort(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const time = new Date(iso).getTime()
    if (Number.isNaN(time)) return '—'
    const diffMs = Math.max(0, Date.now() - time)
    const minute = 60 * 1000
    const hour = 60 * minute
    const day = 24 * hour
    const month = 30 * day
    if (diffMs < minute) return '刚刚'
    if (diffMs < hour) return `${Math.floor(diffMs / minute)}分`
    if (diffMs < day) return `${Math.floor(diffMs / hour)}时`
    if (diffMs < month) return `${Math.floor(diffMs / day)}天`
    return `${Math.floor(diffMs / month)}月`
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
  const capability = CHANNEL_CAPABILITIES[platform.id] || { types: ['发布'], state: '待确认', note: '该渠道能力待确认' }

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
          <div className="mt-3 flex flex-wrap gap-1.5">
            {capability.types.map((item) => (
              <span key={item} className="rounded-md bg-[#0D1321] px-2 py-0.5 text-[11px] text-[#94A3B8]">
                {item}
              </span>
            ))}
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
                <DetailItem icon={BarChart3} label="渠道能力" value={capability.state} />
              </div>
              <div className="rounded-lg border border-[#1E293B] bg-[#0D1321] px-3 py-2 text-xs leading-5 text-[#94A3B8]">
                {capability.note}
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

type WechatSetupStep = 'opening' | 'ready' | 'capturing' | 'success' | 'error'

type WechatSetupState = {
  open: boolean
  accountId: string | null
  step: WechatSetupStep
  message: string
}

export default function Accounts() {
  const [accounts, setAccounts] = useState<ChannelAccount[]>([])
  const [profiles, setProfiles] = useState<PublishingProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [addingPlatform, setAddingPlatform] = useState('douyin')
  const [loggingInAccount, setLoggingInAccount] = useState<string | null>(null)
  const [syncingAccount, setSyncingAccount] = useState<string | null>(null)
  const [deleteExpandedAccount, setDeleteExpandedAccount] = useState<string | null>(null)
  const [profileName, setProfileName] = useState('')
  const [profileAccountIds, setProfileAccountIds] = useState<string[]>([])
  const [expandedProfileId, setExpandedProfileId] = useState<string | null>(null)
  const [wechatSetup, setWechatSetup] = useState<WechatSetupState>({
    open: false,
    accountId: null,
    step: 'opening',
    message: '',
  })

  const loadAccounts = useCallback(async () => {
    try {
      setError(null)
      const [accountData, profileData] = await Promise.all([
        fetchPlatformAccounts(),
        fetchPublishingProfiles(),
      ])
      setAccounts(accountData.accounts || [])
      setProfiles(profileData.profiles || [])
    } catch (e: any) {
      setError(e?.message || '加载渠道账号失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAccounts()
  }, [loadAccounts])

  useEffect(() => {
    const refreshOnFocus = () => loadAccounts()
    window.addEventListener('focus', refreshOnFocus)
    return () => window.removeEventListener('focus', refreshOnFocus)
  }, [loadAccounts])

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadAccounts()
      }
    }, 10000)
    return () => window.clearInterval(timer)
  }, [loadAccounts])

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type })
    window.setTimeout(() => setToast(null), 3500)
  }

  const startWechatSetup = async (accountId: string) => {
    setLoggingInAccount(accountId)
    setWechatSetup({
      open: true,
      accountId,
      step: 'opening',
      message: '正在打开微信，请稍等…',
    })
    try {
      const result = await openWechatDesktop()
      setWechatSetup({
        open: true,
        accountId,
        step: result.ok ? 'ready' : 'error',
        message: result.user_prompt || result.message || (result.ok ? '微信已打开' : '微信打开失败'),
      })
    } catch (e: any) {
      setWechatSetup({
        open: true,
        accountId,
        step: 'error',
        message: e?.message || '打开微信失败，请确认电脑已安装并登录微信',
      })
    } finally {
      setLoggingInAccount(null)
    }
  }

  const handleWechatCapture = async () => {
    if (!wechatSetup.accountId) return
    setWechatSetup((prev) => ({
      ...prev,
      step: 'capturing',
      message: '请在微信聊天输入框点击一次，15 秒内完成。',
    }))
    try {
      const result = await captureWechatInputClick(15, wechatSetup.accountId)
      setWechatSetup((prev) => ({
        ...prev,
        step: 'success',
        message: result.message || '输入区已识别',
      }))
      showToast('微信输入区已识别', 'success')
      await loadAccounts()
    } catch (e: any) {
      setWechatSetup((prev) => ({
        ...prev,
        step: 'error',
        message: e?.message || '未能识别微信输入区，请重试',
      }))
      showToast(e?.message || '未能识别微信输入区', 'error')
    }
  }

  const createAccountAndStartLogin = async (platformId: string) => {
    const platformAccounts = accounts.filter((item) => item.platform === platformId)
    const cfg = PLATFORM_CONFIG[platformId]
    const result = await createPlatformAccount({
      platform: platformId,
      label: `${cfg?.label || platformId}账号${platformAccounts.length + 1}`,
    })
    setAccounts((prev) => [...prev, result.account])
    if (platformId === 'wechat_mp') {
      showToast('微信账号已创建，请完成输入区识别', 'success')
      await startWechatSetup(result.account.id)
      return
    }
    showToast('账号已创建，请完成登录', 'success')
    await handleLogin(result.account.id)
  }

  const handleCreateAccount = async () => {
    try {
      await createAccountAndStartLogin(addingPlatform)
    } catch (e: any) {
      showToast(e?.message || '创建账号失败', 'error')
    }
  }

  const handleLogin = async (accountId: string) => {
    const account = accounts.find((item) => item.id === accountId)
    if (account?.platform === 'wechat_mp') {
      await startWechatSetup(accountId)
      return
    }
    setLoggingInAccount(accountId)
    try {
      const result = await loginPlatformAccount(accountId)
      showToast(result.message || (result.ok ? '登录完成' : '登录未完成'), result.ok ? 'success' : 'error')
      await loadAccounts()
    } catch (e: any) {
      showToast(e?.message || '启动登录失败', 'error')
    } finally {
      setLoggingInAccount(null)
    }
  }

  const handleSyncProfile = async (accountId: string) => {
    setSyncingAccount(accountId)
    try {
      const result = await syncPlatformAccountProfile(accountId)
      showToast(result.message || (result.ok ? '账号资料已刷新' : '账号资料刷新失败'), result.ok ? 'success' : 'error')
      await loadAccounts()
    } catch (e: any) {
      showToast(e?.message || '刷新账号资料失败', 'error')
    } finally {
      setSyncingAccount(null)
    }
  }

  const handleDeleteSession = async (accountId: string) => {
    try {
      await deletePlatformAccountSession(accountId)
      setDeleteExpandedAccount(null)
      showToast('账号已删除', 'success')
      await loadAccounts()
    } catch (e: any) {
      showToast(e?.message || '删除账号失败', 'error')
    }
  }

  const handleCreateProfile = async () => {
    if (!profileName.trim() || profileAccountIds.length === 0) return
    try {
      await createPublishingProfile({ name: profileName.trim(), account_ids: profileAccountIds })
      setProfileName('')
      setProfileAccountIds([])
      showToast('发布配置档案已保存', 'success')
      await loadAccounts()
    } catch (e: any) {
      showToast(e?.message || '保存配置档案失败', 'error')
    }
  }

  const handleDeleteProfile = async (profileId: string) => {
    try {
      await deletePublishingProfile(profileId)
      showToast('发布配置档案已删除', 'success')
      await loadAccounts()
    } catch (e: any) {
      showToast(e?.message || '删除配置档案失败', 'error')
    }
  }

  const visibleAccounts = accounts.filter((item) => item.platform !== 'wechat_mp')
  const visibleProfiles = profiles
    .map((profile) => ({
      ...profile,
      account_ids: profile.account_ids.filter((id) => visibleAccounts.some((account) => account.id === id)),
      accounts: (profile.accounts || []).filter((account) => account.platform !== 'wechat_mp'),
    }))
    .filter((profile) => profile.account_ids.length > 0)
  const platformIds = Object.keys(CHANNEL_CAPABILITIES)
  const totalConnected = visibleAccounts.filter((item) => item.status === 'connected' && item.session?.valid).length
  const accountById = new Map(visibleAccounts.map((account) => [account.id, account]))
  const grouped = platformIds.map((platformId) => ({
    platformId,
    accounts: visibleAccounts.filter((item) => item.platform === platformId),
  }))

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="h-10 w-48 rounded-lg mb-8" style={{ background: 'rgba(255,255,255,0.03)' }} />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-40 animate-pulse rounded-card border border-[#1E293B] bg-white/[0.02]" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
      <AnimatePresence>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      </AnimatePresence>

      <AnimatePresence>
        {wechatSetup.open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 10 }}
              className="w-full max-w-lg rounded-xl border border-[#1E293B] bg-[#0D1422] shadow-2xl shadow-black/40"
            >
              <div className="flex items-center justify-between border-b border-[#1E293B] px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#07C160]/15 text-[#07C160]">
                    <MessageCircle className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="font-medium text-[#F8FAFC]">添加微信</div>
                    <div className="mt-0.5 text-xs text-[#64748B]">仅识别输入区位置，不写入、不发送消息</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setWechatSetup((prev) => ({ ...prev, open: false }))}
                  className="rounded-lg p-1.5 text-[#64748B] transition-colors hover:bg-white/5 hover:text-[#F8FAFC]"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-4 px-5 py-5">
                <div className="rounded-lg border border-[#1E293B] bg-[#020617] p-4">
                  <div className="flex items-start gap-3">
                    <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                      wechatSetup.step === 'success'
                        ? 'bg-[#10B981]/15 text-[#10B981]'
                        : wechatSetup.step === 'error'
                          ? 'bg-[#EF4444]/15 text-[#FCA5A5]'
                          : 'bg-[#6366F1]/15 text-[#A5B4FC]'
                    }`}>
                      {wechatSetup.step === 'capturing' || wechatSetup.step === 'opening'
                        ? <Loader2 className="h-4 w-4 animate-spin" />
                        : wechatSetup.step === 'success'
                          ? <CheckCircle2 className="h-4 w-4" />
                          : wechatSetup.step === 'error'
                            ? <AlertCircle className="h-4 w-4" />
                            : <MousePointerClick className="h-4 w-4" />
                      }
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-[#F8FAFC]">
                        {wechatSetup.step === 'opening' && '正在打开微信'}
                        {wechatSetup.step === 'ready' && '微信已就绪'}
                        {wechatSetup.step === 'capturing' && '等待你点击输入框'}
                        {wechatSetup.step === 'success' && '输入区已识别'}
                        {wechatSetup.step === 'error' && '需要重试'}
                      </div>
                      <div className="mt-2 text-sm leading-6 text-[#CBD5E1]">{wechatSetup.message}</div>
                    </div>
                  </div>
                </div>

              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[#1E293B] px-5 py-4">
                <Button variant="outline" onClick={() => setWechatSetup((prev) => ({ ...prev, open: false }))}>
                  {wechatSetup.step === 'success' ? '完成' : '稍后处理'}
                </Button>
                {(wechatSetup.step === 'ready' || wechatSetup.step === 'error') && (
                  <Button variant="outline" onClick={() => wechatSetup.accountId && startWechatSetup(wechatSetup.accountId)}>
                    <RefreshCw className="h-4 w-4" /> 重新打开微信
                  </Button>
                )}
                {(wechatSetup.step === 'ready' || wechatSetup.step === 'error') && (
                  <Button onClick={handleWechatCapture}>
                    <MousePointerClick className="h-4 w-4" /> 开始识别输入区
                  </Button>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-6 flex flex-col gap-4 rounded-md border border-[#1E293B] bg-[#0D1422] p-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm text-[#94A3B8]">
            管理各平台账号、登录态和发布配置档案
            <span className="text-[#10B981]"> · {totalConnected} 个在线</span>
            <span className="text-[#64748B]"> · 全部账号 {visibleAccounts.length}/50</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={addingPlatform}
            onChange={(event) => setAddingPlatform(event.target.value)}
            className="h-10 rounded-lg border border-[#334155] bg-[#020617] px-3 text-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
          >
            {platformIds.map((id) => (
              <option key={id} value={id}>{PLATFORM_CONFIG[id]?.label || id}</option>
            ))}
          </select>
          <Button onClick={handleCreateAccount}>
            <Plus className="w-4 h-4" /> 添加账号
          </Button>
        </div>
      </motion.div>

      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-md border border-[#7F1D1D] bg-[#450A0A]/35 px-4 py-3 text-sm text-[#FCA5A5]">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="font-medium text-[#FEE2E2]">渠道账号暂不可用</div>
            <div className="mt-1 text-xs leading-5 text-[#FCA5A5]">{error}</div>
          </div>
          <Button variant="outline" size="sm" onClick={loadAccounts}>
            <RefreshCw className="w-4 h-4" /> 重试
          </Button>
        </div>
      )}

      <section className="mb-6 grid gap-3 md:grid-cols-3">
        <div className="rounded-md border border-[#1E293B] bg-[#0D1422] px-4 py-3">
          <div className="text-xs text-[#64748B]">全部账号</div>
          <div className="mt-1 text-2xl font-semibold text-[#F8FAFC]">{visibleAccounts.length}/50</div>
        </div>
        <div className="rounded-md border border-[#1E293B] bg-[#0D1422] px-4 py-3">
          <div className="text-xs text-[#64748B]">在线账号</div>
          <div className="mt-1 text-2xl font-semibold text-[#22C55E]">{totalConnected}</div>
        </div>
        <div className="rounded-md border border-[#1E293B] bg-[#0D1422] px-4 py-3">
          <div className="text-xs text-[#64748B]">发布配置档案</div>
          <div className="mt-1 text-2xl font-semibold text-[#A78BFA]">{visibleProfiles.length}</div>
        </div>
      </section>

      <motion.div variants={containerVariants} initial="hidden" animate="visible" className="space-y-5">
        {grouped.map(({ platformId, accounts: platformAccounts }) => {
          const cfg = PLATFORM_CONFIG[platformId] || PLATFORM_CONFIG.douyin
          const Icon = cfg.icon
          const connected = platformAccounts.filter((item) => item.status === 'connected' && (platformId === 'tencent' || platformId === 'weibo' || item.session?.valid)).length
          return (
            <section key={platformId} className="rounded-md border border-[#1E293B] bg-[#0D1422]">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1E293B] px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ background: cfg.bg, color: cfg.color }}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="font-medium text-[#F8FAFC]">{cfg.label}</div>
                    <div className="text-xs text-[#64748B]">
                        {platformId === 'tencent' || platformId === 'weibo'
                          ? platformAccounts.length > 0
                            ? `${connected}/${platformAccounts.length} 在线 · 桌面辅助`
                            : `还未添加${cfg.label}`
                          : `${connected}/${platformAccounts.length || 10} 可用 · 单平台最多10个账号`}
                    </div>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    setAddingPlatform(platformId)
                    try {
                      await createAccountAndStartLogin(platformId)
                    } catch (e: any) {
                      showToast(e?.message || '创建账号失败', 'error')
                    }
                  }}
                >
                  <Plus className="h-4 w-4" /> 添加
                </Button>
              </div>
              <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
                {platformAccounts.length === 0 ? (
                  <div className="col-span-full rounded-lg border border-dashed border-[#334155] bg-[#020617] px-4 py-6 text-center text-sm text-[#64748B]">
                    暂无账号，添加后即可在素材管理与发布中选择。
                  </div>
                ) : platformAccounts.map((account) => {
                  const online = account.status === 'connected' && (account.platform === 'tencent' || account.platform === 'weibo' || Boolean(account.session?.valid))
                  const displayName = account.nickname || account.label || account.id
                  const metricItems = account.platform === 'weibo'
                    ? [
                        { label: '粉丝', value: account.followers },
                        { label: '关注', value: account.following },
                        { label: '微博', value: account.works_count },
                      ]
                    : [
                        { label: '粉丝', value: account.followers },
                        { label: '作品', value: account.works_count },
                        { label: '获赞', value: account.likes_count },
                      ]
                  return (
                    <div key={account.id} className={`relative rounded-lg border p-4 ${online ? 'border-[#10B981]/40 bg-[#10B981]/5' : 'border-[#334155] bg-[#020617]'}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-3">
                          {account.avatar_url ? (
                            <img src={accountAvatarUrl(account)} alt={displayName} className="h-10 w-10 shrink-0 rounded-full border border-[#334155] object-cover" />
                          ) : (
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[#334155] bg-[#111827] text-sm font-semibold text-[#94A3B8]">
                              {displayName.slice(0, 1)}
                            </div>
                          )}
                          <div className="min-w-0">
                            <div className="truncate font-medium text-[#F8FAFC]">{displayName}</div>
                            <div className="mt-1 text-xs text-[#64748B]">{account.label && account.label !== displayName ? account.label : (account.is_default ? '默认账号' : account.id)}</div>
                          </div>
                        </div>
                        <Badge variant={online ? 'success' : account.session?.has_session ? 'warning' : 'muted'}>
                          {online ? '在线' : account.session?.has_session ? '需重登' : '未登录'}
                        </Badge>
                      </div>
                      <div className="mt-4 grid grid-cols-4 gap-2 rounded-lg border border-[#1E293B] bg-[#0B1120] px-3 py-2 text-xs text-[#94A3B8]">
                        {metricItems.map((item) => (
                          <div key={item.label}>
                            <div className="text-[#64748B]">{item.label}</div>
                            <div className="mt-0.5 text-[#E2E8F0]">{fmtNumber(item.value)}</div>
                          </div>
                        ))}
                        <div>
                          <div className="text-[#64748B]">同步</div>
                          <div className="mt-0.5 truncate text-[#E2E8F0]" title={fmtDateTime(account.last_profile_sync_at)}>
                            {fmtRelativeTimeShort(account.last_profile_sync_at)}
                          </div>
                        </div>
                      </div>
                      {account.sync_status === 'failed' && account.sync_message && (
                        <div className="mt-3 rounded-md border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-3 py-2 text-xs leading-5 text-[#FCD34D]">
                          {account.sync_message}
                        </div>
                      )}
                      <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-[#94A3B8]">
                        <div>
                          <div className="text-[#64748B]">最近登录</div>
                          <div>{fmtDateTime(account.last_login_at || account.session?.saved_at)}</div>
                        </div>
                        <div>
                          <div className="text-[#64748B]">最近发布</div>
                          <div>{fmtDateTime(account.last_publish_at)}</div>
                        </div>
                      </div>
                      <div className="mt-4 flex items-center gap-2">
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" onClick={() => handleLogin(account.id)} disabled={loggingInAccount === account.id}>
                            {loggingInAccount === account.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <QrCode className="h-4 w-4" />}
                            {account.platform === 'tencent' ? '打开助手' : online ? '重新登录' : '登录'}
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handleSyncProfile(account.id)} disabled={!online || syncingAccount === account.id}>
                            {syncingAccount === account.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            刷新资料
                          </Button>
                        </div>
                        <div className="relative ml-auto">
                          <button
                            type="button"
                            onClick={() => setDeleteExpandedAccount((current) => current === account.id ? null : account.id)}
                            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition-colors ${
                              deleteExpandedAccount === account.id
                                ? 'border-[#EF4444]/50 bg-[#EF4444]/15 text-[#FCA5A5]'
                                : 'border-[#334155] bg-[#0B1120] text-[#64748B] hover:border-[#EF4444]/40 hover:text-[#FCA5A5]'
                            }`}
                            title="展开删除账号"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                          {deleteExpandedAccount === account.id && (
                            <div className="absolute right-0 top-11 z-30 w-64 rounded-lg border border-[#334155] bg-[#020617] p-2 shadow-2xl shadow-black/40">
                              <div className="px-2 pb-2 text-xs leading-5 text-[#94A3B8]">
                                删除本地账号槽位、登录态、Cookie 和已同步资料。
                              </div>
                              <button
                                type="button"
                                onClick={() => handleDeleteSession(account.id)}
                                className="flex w-full items-center justify-center gap-1.5 rounded-md bg-[#DC2626] px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-[#B91C1C]"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                                删除账号
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          )
        })}
      </motion.div>

      <section className="mt-6 rounded-md border border-[#1E293B] bg-[#0D1422]">
        <div className="border-b border-[#1E293B] px-4 py-3">
          <div className="font-medium text-[#F8FAFC]">发布配置档案</div>
          <div className="mt-1 text-xs text-[#64748B]">把常用账号保存为一组，发布时一键选择。</div>
        </div>
        <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="rounded-lg border border-[#1E293B] bg-[#020617] p-4">
            <div className="mb-3 text-sm font-medium text-[#E2E8F0]">新建档案</div>
            <input
              value={profileName}
              onChange={(event) => setProfileName(event.target.value)}
              placeholder="例如：品牌A全渠道"
              className="mb-3 h-10 w-full rounded-lg border border-[#334155] bg-[#0B1120] px-3 text-sm text-[#F1F5F9] outline-none focus:border-[#6366F1]"
            />
            <div className="grid max-h-[260px] gap-2 overflow-y-auto md:grid-cols-2">
              {visibleAccounts.length === 0 ? (
                <div className="text-sm text-[#64748B]">暂无账号可加入档案。</div>
              ) : visibleAccounts.map((account) => {
                const checked = profileAccountIds.includes(account.id)
                const profileAccountName = account.nickname?.trim() || '未同步昵称'
                return (
                  <button
                    key={account.id}
                    type="button"
                    onClick={() => setProfileAccountIds((prev) => checked ? prev.filter((id) => id !== account.id) : [...prev, account.id])}
                    className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left transition-colors ${checked ? 'border-[#6366F1] bg-[#6366F1]/15' : 'border-[#334155] hover:bg-[#111827]'}`}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm text-[#F8FAFC]">{profileAccountName}</div>
                      <div className="text-xs text-[#64748B]">{PLATFORM_CONFIG[account.platform]?.label || account.platform}</div>
                    </div>
                    {checked && <CheckCircle2 className="h-4 w-4 shrink-0 text-[#6366F1]" />}
                  </button>
                )
              })}
            </div>
            <div className="mt-4 flex justify-end">
              <Button onClick={handleCreateProfile} disabled={!profileName.trim() || profileAccountIds.length === 0}>
                保存档案
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            {visibleProfiles.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[#334155] bg-[#020617] p-6 text-center text-sm text-[#64748B]">
                暂无发布配置档案
              </div>
            ) : visibleProfiles.map((profile) => {
              const expanded = expandedProfileId === profile.id
              const profileAccounts = profile.account_ids
                .map((accountId) => accountById.get(accountId))
                .filter(Boolean) as ChannelAccount[]
              const onlineCount = profileAccounts.filter((account) => account.status === 'connected' && account.session?.valid).length
              return (
                <div
                  key={profile.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setExpandedProfileId((current) => current === profile.id ? null : profile.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      setExpandedProfileId((current) => current === profile.id ? null : profile.id)
                    }
                  }}
                  className={`w-full rounded-lg border bg-[#020617] p-3 text-left transition-all ${
                    expanded
                      ? 'border-[#6366F1]/60 shadow-lg shadow-[#6366F1]/10'
                      : 'border-[#1E293B] hover:border-[#6366F1]/35 hover:bg-[#0B1120]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-[#F8FAFC]">{profile.name}</div>
                      <div className="mt-1 text-xs text-[#64748B]">
                        {profile.account_ids.length} 个账号 · {onlineCount} 个在线 · {fmtDateTime(profile.updated_at)}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <span className="rounded-md border border-[#334155] bg-[#0B1120] px-2 py-1 text-[11px] text-[#94A3B8]">
                        {expanded ? '收起' : '详情'}
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(event) => {
                          event.stopPropagation()
                          handleDeleteProfile(profile.id)
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {expanded && (
                    <div className="mt-3 space-y-2 border-t border-[#1E293B] pt-3">
                      <div className="rounded-lg border border-[#1E293B] bg-[#0B1120] px-3 py-2 text-xs leading-5 text-[#94A3B8]">
                        发布时选择这个档案，会自动带上下面这些账号。
                      </div>
                      {profileAccounts.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-[#334155] bg-[#020617] px-3 py-3 text-xs text-[#64748B]">
                          这组里的账号已经被移除，可以重新创建一个新的档案。
                        </div>
                      ) : profileAccounts.map((account) => {
                        const displayName = account.nickname?.trim() || account.label || account.id
                        const platformLabel = PLATFORM_CONFIG[account.platform]?.label || account.platform
                        const online = account.status === 'connected' && Boolean(account.session?.valid)
                        return (
                          <div key={account.id} className="flex items-center justify-between gap-3 rounded-lg border border-[#1E293B] bg-[#020617] px-3 py-2">
                            <div className="flex min-w-0 items-center gap-2">
                              {account.avatar_url ? (
                                <img src={accountAvatarUrl(account)} alt={displayName} className="h-7 w-7 shrink-0 rounded-full border border-[#334155] object-cover" />
                              ) : (
                                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[#334155] bg-[#111827] text-xs font-semibold text-[#94A3B8]">
                                  {displayName.slice(0, 1)}
                                </div>
                              )}
                              <div className="min-w-0">
                                <div className="truncate text-sm text-[#F8FAFC]">{displayName}</div>
                                <div className="text-xs text-[#64748B]">{platformLabel}</div>
                              </div>
                            </div>
                            <Badge variant={online ? 'success' : account.session?.has_session ? 'warning' : 'muted'}>
                              {online ? '在线' : account.session?.has_session ? '需重登' : '未登录'}
                            </Badge>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </section>
    </div>
  )
}
