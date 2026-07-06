import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Settings,
  Bot,
  Brain,
  Plug,
  User,
  Sun,
  Moon,
  Monitor,
  Globe,
  Save,
  RotateCcw,
  Check,
  ChevronDown,
  Plus,
  Trash2,
  Database,
  Code,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useAsync } from '@/lib/hooks'
import { apiGet, apiPut, apiDel, getCurrentUser } from '@/lib/api'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type SettingsTab = 'general' | 'ai' | 'agents' | 'integrations' | 'account'

interface AgentToggle {
  id: string
  name: string
  description: string
  enabled: boolean
}

interface TeamMember {
  id: string
  name: string
  email: string
  role: string
  status: 'active' | 'pending'
}

const easeOutExpo = [0.16, 1, 0.3, 1] as [number, number, number, number]

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const settingsTabs: { id: SettingsTab; label: string; icon: typeof Settings }[] = [
  { id: 'general', label: '通用设置', icon: Settings },
  { id: 'ai', label: 'AI 模型', icon: Brain },
  { id: 'agents', label: '数字员工', icon: Bot },
  { id: 'integrations', label: '集成配置', icon: Plug },
  { id: 'account', label: '账户管理', icon: User },
]

const llmModels: string[] = []

const notificationEvents = [
  { id: 'task_complete', label: '任务执行完成', checked: true },
  { id: 'agent_error', label: '数字员工执行出错', checked: true },
  { id: 'report_ready', label: '报告生成完毕', checked: true },
  { id: 'team_update', label: '团队成员更新配置', checked: false },
  { id: 'daily_summary', label: '每日执行摘要', checked: true },
]

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')
  const [unsaved, setUnsaved] = useState(false)

  /* General */
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('dark')
  const [language, setLanguage] = useState('中文')
  const [emailNotifs, setEmailNotifs] = useState(true)
  const [browserNotifs, setBrowserNotifs] = useState(true)
  const [notifEvents, setNotifEvents] = useState(notificationEvents)

  /* AI Model */
  const { data: cfgData } = useAsync<{ llm?: { default_backend?: string; volcengine?: { default_model?: string; endpoints?: Record<string, string> }; ollama?: { default_model?: string } } }>(
    () => apiGet('/api/config'),
  )
  const realModels: string[] = (() => {
    const llm = cfgData?.llm
    if (!llm) return []
    const list: string[] = []
    const eps = llm.volcengine?.endpoints
    if (eps) list.push(...Object.values(eps).filter(Boolean))
    if (llm.volcengine?.default_model) list.push(llm.volcengine.default_model)
    if (llm.ollama?.default_model) list.push(llm.ollama.default_model)
    return Array.from(new Set(list))
  })()
  const [selectedModel, setSelectedModel] = useState('')
  useEffect(() => {
    if (realModels.length && !selectedModel) setSelectedModel(realModels[0])
  }, [realModels, selectedModel])
  const [customEndpoint, setCustomEndpoint] = useState('')
  const [customApiKey, setCustomApiKey] = useState('')
  const [aiTemperature, setAiTemperature] = useState(0.5)
  const [maxTokens, setMaxTokens] = useState(4000)

  /* Digital Agents */
  const { data: agentsData, reload: reloadAgents } = useAsync<{ data: { id: string; name: string; emoji: string; color: string; enabled: boolean }[] }>(
    () => apiGet('/api/data/agents/list'),
  )
  const [agents, setAgents] = useState<AgentToggle[]>([])
  useEffect(() => {
    if (agentsData?.data) {
      setAgents(agentsData.data.map((a) => ({
        id: a.id,
        name: `${a.emoji ?? ''} ${a.name}`,
        description: 'AI 员工（可启用/禁用）',
        enabled: a.enabled,
      })))
    }
  }, [agentsData])

  /* Integrations */
  const [supabaseUrl, setSupabaseUrl] = useState('')
  const [supabaseKey, setSupabaseKey] = useState('')
  const [supabaseConnected, setSupabaseConnected] = useState(false)
  const [webSearchEnabled, setWebSearchEnabled] = useState(false)
  const [webSearchProvider, setWebSearchProvider] = useState('Serper.dev')
  const [webSearchKey, setWebSearchKey] = useState('')
  const [thirdPartyApiKey, setThirdPartyApiKey] = useState('')

  /* Account */
  const currentUser = getCurrentUser()
  const [profileName, setProfileName] = useState(currentUser?.username ?? 'admin')
  const [profileEmail] = useState(`${currentUser?.username ?? 'admin'}@szyg.local`)
  const [profileRole, setProfileRole] = useState('系统管理员')
  const { data: teamData, reload: reloadTeam } = useAsync<{ data: { id: number; username: string; role: string; email: string; status: string }[] }>(
    () => apiGet('/api/data/team/list'),
  )
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([])
  useEffect(() => {
    if (teamData?.data) {
      setTeamMembers(teamData.data.map((m) => ({
        id: String(m.id),
        name: m.username,
        email: m.email,
        role: m.role === 'admin' ? '系统管理员' : '普通成员',
        status: m.status === 'active' ? 'active' : 'pending',
      })))
    }
  }, [teamData])

  /* -- handlers -- */
  const toggleAgent = async (id: string) => {
    const target = agents.find((a) => a.id === id)
    if (!target) return
    const nextEnabled = !target.enabled
    setAgents((prev) => prev.map((a) => (a.id === id ? { ...a, enabled: nextEnabled } : a)))
    setUnsaved(true)
    try {
      await apiPut(`/api/data/agents/${id}`, { enabled: nextEnabled })
    } catch {
      /* 回滚由下次 reload 修正 */
      reloadAgents()
    }
  }

  const handleNotifEventToggle = (id: string) => {
    setNotifEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, checked: !e.checked } : e))
    )
    setUnsaved(true)
  }

  const handleSave = () => {
    setUnsaved(false)
  }

  const handleReset = () => {
    setUnsaved(false)
  }

  /* -- animation variants -- */
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
  }

  const cardVariant = {
    hidden: { opacity: 0, y: 15 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: easeOutExpo } },
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="max-w-[1000px] mx-auto pb-28"
    >
      {/* Page Header */}
      <motion.div variants={cardVariant} className="mb-8">
        <h1 className="text-display-md font-display text-[#F1F5F9] mb-2">系统设置</h1>
        <p className="text-body-lg text-[#94A3B8]">
          配置你的超级数字员工系统参数
        </p>
      </motion.div>

      {/* Settings Navigation */}
      <motion.div variants={cardVariant} className="mb-8">
        <div className="flex items-center gap-1 p-1 bg-[#1A2235] rounded-xl border border-[#1E293B] overflow-x-auto">
          {settingsTabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'relative flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 shrink-0',
                  isActive ? 'text-[#F1F5F9]' : 'text-[#64748B] hover:text-[#94A3B8]'
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="settingsTabIndicator"
                    className="absolute inset-0 bg-[#1A2235] border border-[#334155] rounded-lg"
                    transition={{ duration: 0.2, ease: [0.45, 0.05, 0.55, 0.95] as [number, number, number, number] }}
                  />
                )}
                <Icon className="w-4 h-4 relative z-10" />
                <span className="relative z-10 whitespace-nowrap">{tab.label}</span>
              </button>
            )
          })}
        </div>
      </motion.div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        {/* ==================== TAB 1: 通用设置 ==================== */}
        {activeTab === 'general' && (
          <motion.div
            key="general"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {/* Appearance */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">外观</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                自定义超级数字员工系统的外观风格。
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-5">
                {/* Theme */}
                <div>
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-1">主题选择</Label>
                  <p className="text-body-sm text-[#64748B] mb-3">选择你喜欢的配色方案</p>
                  <div className="flex items-center gap-2 p-1 bg-[#0D1321] rounded-xl border border-[#1E293B] w-fit">
                    {([
                      { value: 'light', icon: Sun, label: 'Light' },
                      { value: 'dark', icon: Moon, label: 'Dark' },
                      { value: 'system', icon: Monitor, label: 'System' },
                    ] as const).map((t) => {
                      const Icon = t.icon
                      const isActive = theme === t.value
                      return (
                        <button
                          key={t.value}
                          onClick={() => { setTheme(t.value); setUnsaved(true) }}
                          className={cn(
                            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                            isActive
                              ? 'bg-[#1A2235] text-[#F1F5F9] border border-[#334155]'
                              : 'text-[#64748B] hover:text-[#94A3B8]'
                          )}
                        >
                          <Icon className="w-4 h-4" />
                          {t.label}
                        </button>
                      )
                    })}
                  </div>
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Language */}
                <div>
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-1">语言</Label>
                  <p className="text-body-sm text-[#64748B] mb-3">界面显示语言</p>
                  <div className="relative max-w-[240px]">
                    <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                    <select
                      value={language}
                      onChange={(e) => { setLanguage(e.target.value); setUnsaved(true) }}
                      className="w-full h-10 pl-10 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                    >
                      <option>中文</option>
                      <option>English</option>
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Notifications */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">通知</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                控制你如何接收系统更新通知。
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-5">
                {/* Email Notifications */}
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                      Email 通知
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      接收任务完成、Agent 异常等邮件提醒
                    </p>
                  </div>
                  <Switch
                    checked={emailNotifs}
                    onCheckedChange={(v) => { setEmailNotifs(v); setUnsaved(true) }}
                    className="data-[state=checked]:bg-[#6366F1]"
                  />
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Browser Notifications */}
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                      浏览器通知
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      在桌面显示重要事件的浏览器推送通知
                    </p>
                  </div>
                  <Switch
                    checked={browserNotifs}
                    onCheckedChange={(v) => { setBrowserNotifs(v); setUnsaved(true) }}
                    className="data-[state=checked]:bg-[#6366F1]"
                  />
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Notification Events */}
                <div>
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                    通知事件列表
                  </Label>
                  <div className="mt-3 space-y-2">
                    {notifEvents.map((evt) => (
                      <label
                        key={evt.id}
                        className="flex items-center gap-3 p-2 rounded-lg hover:bg-[rgba(255,255,255,0.02)] cursor-pointer transition-colors"
                      >
                        <div
                          className={cn(
                            'w-5 h-5 rounded border flex items-center justify-center transition-colors',
                            evt.checked
                              ? 'bg-[#6366F1] border-[#6366F1]'
                              : 'border-[#334155] bg-transparent'
                          )}
                          onClick={() => handleNotifEventToggle(evt.id)}
                        >
                          {evt.checked && <Check className="w-3 h-3 text-white" />}
                        </div>
                        <span className="text-body-md text-[#94A3B8]">{evt.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* ==================== TAB 2: AI 模型 ==================== */}
        {activeTab === 'ai' && (
          <motion.div
            key="ai"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {/* AI Model Config */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">AI 模型配置</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                配置驱动数字员工pipeline的大语言模型参数。
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                {/* Model Selector */}
                <div>
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-1">AI 模型选择</Label>
                  <p className="text-body-sm text-[#64748B] mb-3">
                    选择驱动数字员工pipeline的大语言模型
                  </p>
                  <div className="relative max-w-[320px]">
                    <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6366F1] pointer-events-none" />
                    <select
                      value={selectedModel}
                      onChange={(e) => { setSelectedModel(e.target.value); setUnsaved(true) }}
                      className="w-full h-10 pl-10 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                    >
                      {(realModels.length ? realModels : llmModels).map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                  </div>
                </div>

                {/* Custom Endpoint (conditional) */}
                {selectedModel === 'Custom Endpoint' && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="space-y-3 pt-2"
                  >
                    <div>
                      <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">自定义 API URL</Label>
                      <Input
                        value={customEndpoint}
                        onChange={(e) => { setCustomEndpoint(e.target.value); setUnsaved(true) }}
                        placeholder="https://api.custom-llm.com/v1"
                        className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                      />
                    </div>
                    <div>
                      <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">API Key</Label>
                      <Input
                        type="password"
                        value={customApiKey}
                        onChange={(e) => { setCustomApiKey(e.target.value); setUnsaved(true) }}
                        placeholder="sk-..."
                        className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                      />
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-[#334155] text-[#94A3B8] hover:text-[#F1F5F9]"
                    >
                      测试连接
                    </Button>
                  </motion.div>
                )}

                <Separator className="bg-[#1E293B]" />

                {/* Temperature */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-heading-sm text-[#F1F5F9]">AI 创意度 (Temperature)</Label>
                    <span className="text-body-sm text-[#6366F1] font-mono">{aiTemperature.toFixed(1)}</span>
                  </div>
                  <p className="text-body-sm text-[#64748B] mb-3">
                    数值越高输出越具创意，但一致性可能降低
                  </p>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.1}
                    value={aiTemperature}
                    onChange={(e) => { setAiTemperature(Number(e.target.value)); setUnsaved(true) }}
                    className="w-full accent-[#6366F1]"
                  />
                  <div className="flex justify-between text-body-sm text-[#64748B] mt-1">
                    <span>精确</span>
                    <span>创意</span>
                  </div>
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Max Tokens */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-heading-sm text-[#F1F5F9]">最大输出长度</Label>
                    <span className="text-body-sm text-[#6366F1] font-mono">{maxTokens.toLocaleString()} tokens</span>
                  </div>
                  <input
                    type="range"
                    min={1000}
                    max={8000}
                    step={500}
                    value={maxTokens}
                    onChange={(e) => { setMaxTokens(Number(e.target.value)); setUnsaved(true) }}
                    className="w-full accent-[#6366F1]"
                  />
                  <div className="flex justify-between text-body-sm text-[#64748B] mt-1">
                    <span>1,000</span>
                    <span>8,000</span>
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* ==================== TAB 3: 数字员工 ==================== */}
        {activeTab === 'agents' && (
          <motion.div
            key="agents"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {/* Agent Toggles */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">数字员工开关</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                启用或禁用各类 Agent。禁用的 Agent 将在pipeline中被跳过。
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 divide-y divide-[#1E293B]">
                {agents.map((agent) => (
                  <div
                    key={agent.id}
                    className="flex items-center justify-between py-4 first:pt-0 last:pb-0"
                  >
                    <div className="mr-4">
                      <p className="text-body-md font-medium text-[#F1F5F9]">{agent.name}</p>
                      <p className="text-body-sm text-[#64748B]">{agent.description}</p>
                    </div>
                    <Switch
                      checked={agent.enabled}
                      onCheckedChange={() => toggleAgent(agent.id)}
                      className="data-[state=checked]:bg-[#6366F1] shrink-0"
                    />
                  </div>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* ==================== TAB 4: 集成配置 ==================== */}
        {activeTab === 'integrations' && (
          <motion.div
            key="integrations"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {/* Supabase */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Supabase</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                数据库与存储后端连接配置。
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-[#3ECF8E]" />
                    <span className="text-heading-sm text-[#F1F5F9]">Supabase 连接</span>
                  </div>
                  {supabaseConnected ? (
                    <Badge className="bg-[rgba(16,185,129,0.15)] text-[#10B981] border-[#10B981]">
                      <Check className="w-3 h-3 mr-1" /> 已连接
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[#64748B] border-[#334155]">
                      未连接
                    </Badge>
                  )}
                </div>

                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Project URL</Label>
                  <Input
                    value={supabaseUrl}
                    onChange={(e) => { setSupabaseUrl(e.target.value); setUnsaved(true) }}
                    placeholder="https://your-project.supabase.co"
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50"
                  />
                </div>
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Anon Key</Label>
                  <Input
                    type="password"
                    value={supabaseKey}
                    onChange={(e) => { setSupabaseKey(e.target.value); setUnsaved(true) }}
                    placeholder="eyJhbGciOiJIUzI1NiIs..."
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50"
                  />
                </div>
                <Button
                  onClick={() => setSupabaseConnected(true)}
                  className="bg-[#3ECF8E] hover:bg-[#4EE99D] text-black font-medium"
                >
                  测试连接
                </Button>
              </div>
            </motion.div>

            {/* Web Search */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Web Search</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                网络搜索集成，增强数字员工的信息获取能力。
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                      Web Search 集成
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      允许数字员工实时搜索网络信息
                    </p>
                  </div>
                  <Switch
                    checked={webSearchEnabled}
                    onCheckedChange={(v) => { setWebSearchEnabled(v); setUnsaved(true) }}
                    className="data-[state=checked]:bg-[#6366F1]"
                  />
                </div>

                {webSearchEnabled && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="space-y-3 pt-2"
                  >
                    <div>
                      <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Provider</Label>
                      <div className="relative max-w-[240px]">
                        <select
                          value={webSearchProvider}
                          onChange={(e) => { setWebSearchProvider(e.target.value); setUnsaved(true) }}
                          className="w-full h-10 px-3 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                        >
                          <option>Serper.dev</option>
                          <option>Exa.ai</option>
                          <option>Custom</option>
                        </select>
                        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                      </div>
                    </div>
                    <div>
                      <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">API Key</Label>
                      <Input
                        type="password"
                        value={webSearchKey}
                        onChange={(e) => { setWebSearchKey(e.target.value); setUnsaved(true) }}
                        placeholder="Enter API key"
                        className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                      />
                    </div>
                  </motion.div>
                )}
              </div>
            </motion.div>

            {/* Third-Party API Key */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">第三方 API Key</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                其他外部服务的 API Key 配置。
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                <div className="flex items-center gap-2 mb-2">
                  <Code className="w-5 h-5 text-[#6366F1]" />
                  <span className="text-heading-sm text-[#F1F5F9]">通用 API Key</span>
                </div>
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">API Key</Label>
                  <Input
                    type="password"
                    value={thirdPartyApiKey}
                    onChange={(e) => { setThirdPartyApiKey(e.target.value); setUnsaved(true) }}
                    placeholder="sk-..."
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                  />
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* ==================== TAB 5: 账户管理 ==================== */}
        {activeTab === 'account' && (
          <motion.div
            key="account"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {/* Profile */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">个人信息</h2>
              <p className="text-body-sm text-[#64748B] mb-4">管理你的个人资料信息。</p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-5">
                {/* Avatar + Name */}
                <div className="flex items-center gap-4">
                  <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-2xl font-bold text-white">
                    {profileName.charAt(0)}
                  </div>
                  <div>
                    <p className="text-heading-sm text-[#F1F5F9]">{profileName}</p>
                    <p className="text-body-sm text-[#64748B]">{profileEmail}</p>
                  </div>
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Name */}
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">姓名</Label>
                  <Input
                    value={profileName}
                    onChange={(e) => { setProfileName(e.target.value); setUnsaved(true) }}
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                  />
                </div>

                {/* Email */}
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">邮箱</Label>
                  <Input
                    value={profileEmail}
                    disabled
                    className="bg-[#0D1321] border-[#1E293B] text-[#64748B] cursor-not-allowed"
                  />
                  <p className="text-body-sm text-[#64748B] mt-1">由 OAuth 提供商管理</p>
                </div>

                {/* Role */}
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">角色</Label>
                  <div className="relative max-w-[240px]">
                    <select
                      value={profileRole}
                      onChange={(e) => { setProfileRole(e.target.value); setUnsaved(true) }}
                      className="w-full h-10 px-3 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                    >
                      <option>系统管理员</option>
                      <option>数字员工配置员</option>
                      <option>数据分析师</option>
                      <option>普通用户</option>
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Team */}
            <motion.div variants={cardVariant}>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-heading-sm text-[#F1F5F9] mb-1">团队成员</h2>
                  <p className="text-body-sm text-[#64748B]">管理团队成员与访问权限。</p>
                </div>
                <Button
                  size="sm"
                  className="bg-[#6366F1] hover:bg-[#818CF8] text-white"
                  onClick={() => {
                    setTeamMembers((prev) => [
                      ...prev,
                      {
                        id: `new-${Date.now()}`,
                        name: '新成员',
                        email: 'pending@szyg.com',
                        role: '普通用户',
                        status: 'pending',
                      },
                    ])
                    setUnsaved(true)
                  }}
                >
                  <Plus className="w-4 h-4 mr-1.5" />
                  添加成员
                </Button>
              </div>
              <div className="glass-card rounded-[16px] border border-[#1E293B] overflow-hidden">
                <div className="divide-y divide-[#1E293B]">
                  {teamMembers.map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between px-5 py-4 hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-sm font-semibold text-white">
                          {member.name.charAt(0)}
                        </div>
                        <div>
                          <p className="text-body-md font-medium text-[#F1F5F9]">{member.name}</p>
                          <p className="text-body-sm text-[#64748B]">{member.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge
                          variant="outline"
                          className={cn(
                            'text-xs',
                            member.status === 'active'
                              ? 'border-[#10B981] text-[#10B981] bg-[rgba(16,185,129,0.1)]'
                              : 'border-[#F59E0B] text-[#F59E0B] bg-[rgba(245,158,11,0.1)]'
                          )}
                        >
                          {member.status === 'active' ? '活跃' : '待激活'}
                        </Badge>
                        <span className="text-body-sm text-[#94A3B8]">{member.role}</span>
                        <button
                          onClick={async () => {
                            setTeamMembers((prev) => prev.filter((m) => m.id !== member.id))
                            setUnsaved(true)
                            try { await apiDel(`/api/data/team/${member.id}`) } catch { reloadTeam() }
                          }}
                          className="p-1.5 rounded-lg text-[#64748B] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.1)] transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ========== SAVE / RESET BAR ========== */}
      <AnimatePresence>
        {unsaved && (
          <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            transition={{ duration: 0.4, ease: easeOutExpo }}
            className="fixed bottom-0 right-0 left-0 lg:left-[260px] bg-[#111827]/95 backdrop-blur-md border-t border-[#1E293B] px-6 py-4 z-40"
          >
            <div className="flex items-center justify-between max-w-[1000px] mx-auto">
              <Button
                variant="ghost"
                onClick={handleReset}
                className="text-[#94A3B8] hover:text-[#F1F5F9]"
              >
                <RotateCcw className="w-4 h-4 mr-2" />
                恢复默认
              </Button>
              <div className="flex items-center gap-3">
                <span className="text-body-sm text-[#F59E0B]">有未保存的更改</span>
                <motion.div
                  animate={{
                    boxShadow: [
                      '0 0 20px rgba(99,102,241,0.2)',
                      '0 0 30px rgba(99,102,241,0.4)',
                      '0 0 20px rgba(99,102,241,0.2)',
                    ],
                  }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="rounded-lg"
                >
                  <Button
                    onClick={handleSave}
                    className="bg-[#6366F1] hover:bg-[#818CF8] text-white"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    保存更改
                  </Button>
                </motion.div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
