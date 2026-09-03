import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Settings as SettingsIcon,
  Building2,
  Database,
  Bot,
  Plug,
  User,
  Cloud,
  Factory,
  Briefcase,
  ShoppingBag,
  Hexagon,
  Code,
  Clipboard,
  Save,
  RotateCcw,
  Check,
  AlertTriangle,
  Sparkles,
  ChevronDown,
  Plus,
  Trash2,
  Upload,
  Globe,
  Sun,
  Moon,
  Monitor,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

 type SettingsTab = 'general' | 'industry' | 'crm' | 'ai' | 'integrations' | 'account'

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

const settingsTabs: { id: SettingsTab; label: string; icon: typeof SettingsIcon }[] = [
  { id: 'general', label: 'General', icon: SettingsIcon },
  { id: 'industry', label: 'Industry', icon: Building2 },
  { id: 'crm', label: 'CRM', icon: Database },
  { id: 'ai', label: 'AI Agents', icon: Bot },
  { id: 'integrations', label: 'Integrations', icon: Plug },
  { id: 'account', label: 'Account', icon: User },
]

const industries = [
  {
    id: 'saas',
    name: 'SaaS',
    icon: Cloud,
    description: 'Subscription pricing, trial-to-paid conversion',
    color: '#6366F1',
  },
  {
    id: 'manufacturing',
    name: 'Manufacturing',
    icon: Factory,
    description: 'Long sales cycles, procurement processes',
    color: '#F59E0B',
  },
  {
    id: 'consulting',
    name: 'Consulting',
    icon: Briefcase,
    description: 'Project-based, relationship-driven',
    color: '#3B82F6',
  },
  {
    id: 'consumer',
    name: 'Consumer Goods',
    icon: ShoppingBag,
    description: 'Volume-focused, retailer relationships',
    color: '#10B981',
  },
]

const crmTypes = [
  { id: 'salesforce', name: 'Salesforce', icon: Cloud },
  { id: 'hubspot', name: 'HubSpot', icon: Hexagon },
  { id: 'fxiaoke', name: '纷享销客', icon: Building2 },
  { id: 'custom', name: 'Custom / Self-built', icon: Code },
  { id: 'none', name: 'None (manual)', icon: Clipboard },
]

const llmModels = [
  'GPT-4o',
  'GPT-4o-mini',
  'Claude 3.5 Sonnet',
  'ERNIE 4.0',
  'Custom Endpoint',
]

const salesCycleOptions = [
  '< 1 month',
  '1-3 months',
  '3-6 months',
  '6-12 months',
  '> 1 year',
]

const notificationEvents = [
  { id: 'followup', label: 'A follow-up is due', checked: true },
  { id: 'stage_change', label: 'A deal stage changes', checked: true },
  { id: 'ai_report', label: 'AI report is ready', checked: true },
  { id: 'team_update', label: 'A team member updates a shared deal', checked: false },
  { id: 'daily_summary', label: 'Daily summary', checked: true },
]

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')
  const [unsaved, setUnsaved] = useState(false)

  /* General */
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('dark')
  const [language, setLanguage] = useState('中文')
  const [emailNotifs, setEmailNotifs] = useState(true)
  const [browserNotifs, setBrowserNotifs] = useState(true)
  const [notifEvents, setNotifEvents] = useState(notificationEvents)

  /* Industry */
  const [selectedIndustry, setSelectedIndustry] = useState('saas')
  const [dealSizeMin, setDealSizeMin] = useState(100000)
  const [dealSizeMax, setDealSizeMax] = useState(2000000)
  const [salesCycle, setSalesCycle] = useState('3-6 months')

  /* CRM */
  const [crmType, setCrmType] = useState('salesforce')
  const [crmUrl, setCrmUrl] = useState('')
  const [crmApiKey, setCrmApiKey] = useState('')
  const [crmConnected, setCrmConnected] = useState(false)
  const [autoSync, setAutoSync] = useState(false)

  /* AI Agents */
  const [selectedModel, setSelectedModel] = useState('GPT-4o')
  const [customEndpoint, setCustomEndpoint] = useState('')
  const [customApiKey, setCustomApiKey] = useState('')
  const [aiTemperature, setAiTemperature] = useState(0.3)
  const [maxTokens, setMaxTokens] = useState(4000)
  const [agents, setAgents] = useState<AgentToggle[]>([
    { id: 'extract', name: 'Info Extract Agent', description: 'Extracts key business information from raw notes', enabled: true },
    { id: 'structure', name: 'Note Structure Agent', description: 'Structures meeting minutes into standard format', enabled: true },
    { id: 'rate', name: 'Deal Rating Agent', description: 'Evaluates deal potential and assigns stage', enabled: true },
    { id: 'profile', name: 'Profile Update Agent', description: 'Updates customer profile with new intelligence', enabled: true },
    { id: 'compete', name: 'Compete Analysis Agent', description: 'Analyzes competitive threats and differentiation', enabled: true },
    { id: 'followup', name: 'Follow-up Strategy Agent', description: 'Generates next-step recommendations', enabled: true },
    { id: 'email', name: 'Email Draft Agent', description: 'Drafts follow-up emails', enabled: true },
    { id: 'sync', name: 'CRM Sync Agent', description: 'Prepares CRM-compatible data structure', enabled: true },
  ])

  /* Integrations */
  const [supabaseUrl, setSupabaseUrl] = useState('')
  const [supabaseKey, setSupabaseKey] = useState('')
  const [supabaseServiceKey, setSupabaseServiceKey] = useState('')
  const [supabaseConnected, setSupabaseConnected] = useState(false)
  const [miaodaEndpoint, setMiaodaEndpoint] = useState('')
  const [miaodaProjectId, setMiaodaProjectId] = useState('')
  const [miaodaApiKey, setMiaodaApiKey] = useState('')
  const [webSearchEnabled, setWebSearchEnabled] = useState(false)
  const [webSearchProvider, setWebSearchProvider] = useState('Serper.dev')
  const [webSearchKey, setWebSearchKey] = useState('')

  /* Account */
  const [profileName, setProfileName] = useState('Zhang Wei')
  const [profileEmail] = useState('zhang.wei@dealflow.com')
  const [profileRole, setProfileRole] = useState('Sales Manager')
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([
    { id: '1', name: 'Zhang Wei', email: 'zhang.wei@dealflow.com', role: 'Sales Manager', status: 'active' },
    { id: '2', name: 'Li Hua', email: 'li.hua@dealflow.com', role: 'Sales Rep', status: 'active' },
    { id: '3', name: 'Wang Fang', email: 'wang.fang@dealflow.com', role: 'Sales Rep', status: 'active' },
  ])

  /* -- handlers -- */
  const toggleAgent = (id: string) => {
    setAgents((prev) =>
      prev.map((a) => (a.id === id ? { ...a, enabled: !a.enabled } : a))
    )
    setUnsaved(true)
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

  const formatCurrency = (v: number) => {
    if (v >= 1000000) return `¥${(v / 1000000).toFixed(1)}M`
    if (v >= 1000) return `¥${(v / 1000).toFixed(0)}K`
    return `¥${v}`
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
        <h1 className="text-display-md font-display text-[#F1F5F9] mb-2">Settings</h1>
        <p className="text-body-lg text-[#94A3B8]">
          Configure your DealFlow workspace to match your workflow.
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
        {/* ==================== TAB 1: GENERAL ==================== */}
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
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Appearance</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                Customize how DealFlow looks for you.
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-5">
                {/* Theme */}
                <div>
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-1">Theme</Label>
                  <p className="text-body-sm text-[#64748B] mb-3">Choose your preferred color scheme</p>
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
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-1">Language</Label>
                  <p className="text-body-sm text-[#64748B] mb-3">Interface language</p>
                  <div className="relative max-w-[240px]">
                    <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                    <select
                      value={language}
                      onChange={(e) => { setLanguage(e.target.value); setUnsaved(true) }}
                      className="w-full h-10 pl-10 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                    >
                      <option>English</option>
                      <option>中文</option>
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Notifications */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Notifications</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                Control how you receive updates.
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-5">
                {/* Email Notifications */}
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                      Email Notifications
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      Receive email alerts for follow-up reminders and deal updates
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
                      Browser Notifications
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      Show desktop notifications for important events
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
                    Notify me when...
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

        {/* ==================== TAB 2: INDUSTRY ==================== */}
        {activeTab === 'industry' && (
          <motion.div
            key="industry"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Industry Selection</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                This affects how AI agents evaluate deals, suggest strategies, and calculate win rates.
              </p>

              {/* Industry Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                {industries.map((ind) => {
                  const Icon = ind.icon
                  const isSelected = selectedIndustry === ind.id
                  return (
                    <motion.button
                      key={ind.id}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => { setSelectedIndustry(ind.id); setUnsaved(true) }}
                      className={cn(
                        'relative p-5 rounded-[16px] border text-left transition-all duration-200',
                        isSelected
                          ? 'border-[#6366F1] bg-[rgba(99,102,241,0.08)]'
                          : 'border-[#1E293B] bg-[#111827] hover:border-[#334155]'
                      )}
                      style={
                        isSelected
                          ? { boxShadow: `0 0 20px ${ind.color}20` }
                          : undefined
                      }
                    >
                      {isSelected && (
                        <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-[#6366F1] flex items-center justify-center">
                          <Check className="w-3 h-3 text-white" />
                        </div>
                      )}
                      <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                        style={{ background: `${ind.color}15` }}
                      >
                        <Icon className="w-5 h-5" style={{ color: ind.color }} />
                      </div>
                      <h3 className="text-heading-sm text-[#F1F5F9] mb-1">{ind.name}</h3>
                      <p className="text-body-sm text-[#64748B]">{ind.description}</p>
                    </motion.button>
                  )
                })}
              </div>

              {/* Deal Size */}
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 mb-5">
                <Label className="text-heading-sm text-[#F1F5F9] block mb-1">
                  Typical Deal Size
                </Label>
                <p className="text-body-sm text-[#64748B] mb-4">
                  Used to calibrate AI deal estimation
                </p>
                <div className="flex items-center gap-4 mb-3">
                  <div className="flex-1">
                    <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Min</Label>
                    <Input
                      type="number"
                      value={dealSizeMin}
                      onChange={(e) => { setDealSizeMin(Number(e.target.value)); setUnsaved(true) }}
                      className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                    />
                  </div>
                  <div className="pt-6 text-[#64748B]">—</div>
                  <div className="flex-1">
                    <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Max</Label>
                    <Input
                      type="number"
                      value={dealSizeMax}
                      onChange={(e) => { setDealSizeMax(Number(e.target.value)); setUnsaved(true) }}
                      className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between text-body-sm text-[#64748B]">
                  <span>{formatCurrency(dealSizeMin)}</span>
                  <span>{formatCurrency(dealSizeMax)}</span>
                </div>
              </div>

              {/* Sales Cycle */}
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5">
                <Label className="text-heading-sm text-[#F1F5F9] block mb-1">
                  Average Sales Cycle
                </Label>
                <p className="text-body-sm text-[#64748B] mb-3">
                  Typical duration from first contact to close
                </p>
                <div className="relative max-w-[280px]">
                  <select
                    value={salesCycle}
                    onChange={(e) => { setSalesCycle(e.target.value); setUnsaved(true) }}
                    className="w-full h-10 px-3 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                  >
                    {salesCycleOptions.map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* ==================== TAB 3: CRM ==================== */}
        {activeTab === 'crm' && (
          <motion.div
            key="crm"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">CRM Connection</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                Choose your CRM system for data synchronization.
              </p>

              {/* CRM Type Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
                {crmTypes.map((crm) => {
                  const Icon = crm.icon
                  const isSelected = crmType === crm.id
                  return (
                    <motion.button
                      key={crm.id}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => { setCrmType(crm.id); setUnsaved(true) }}
                      className={cn(
                        'flex flex-col items-center gap-2 p-4 rounded-xl border transition-all',
                        isSelected
                          ? 'border-[#6366F1] bg-[rgba(99,102,241,0.08)]'
                          : 'border-[#1E293B] bg-[#111827] hover:border-[#334155]'
                      )}
                    >
                      <Icon
                        className={cn(
                          'w-6 h-6',
                          isSelected ? 'text-[#6366F1]' : 'text-[#64748B]'
                        )}
                      />
                      <span
                        className={cn(
                          'text-body-sm font-medium',
                          isSelected ? 'text-[#F1F5F9]' : 'text-[#94A3B8]'
                        )}
                      >
                        {crm.name}
                      </span>
                    </motion.button>
                  )
                })}
              </div>

              {/* Connection Config */}
              {crmType !== 'none' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4 mb-5"
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-heading-sm text-[#F1F5F9]">
                      {crmTypes.find((c) => c.id === crmType)?.name} Connection
                    </h3>
                    {crmConnected && (
                      <Badge className="bg-[rgba(16,185,129,0.15)] text-[#10B981] border-[#10B981]">
                        <Check className="w-3 h-3 mr-1" /> Connected
                      </Badge>
                    )}
                  </div>

                  {/* Instance URL */}
                  <div>
                    <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">
                      {crmType === 'salesforce' ? 'Instance URL' : 'API Endpoint'}
                    </Label>
                    <Input
                      value={crmUrl}
                      onChange={(e) => { setCrmUrl(e.target.value); setUnsaved(true) }}
                      placeholder={
                        crmType === 'salesforce'
                          ? 'https://your-instance.salesforce.com'
                          : 'https://api.example.com'
                      }
                      className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50"
                    />
                  </div>

                  {/* API Key */}
                  <div>
                    <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">
                      {crmType === 'salesforce' ? 'Consumer Key' : 'API Key'}
                    </Label>
                    <Input
                      type="password"
                      value={crmApiKey}
                      onChange={(e) => { setCrmApiKey(e.target.value); setUnsaved(true) }}
                      placeholder="Enter your API key"
                      className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50"
                    />
                  </div>

                  <Button
                    onClick={() => setCrmConnected(true)}
                    className="bg-[#6366F1] hover:bg-[#818CF8] text-white"
                  >
                    {crmConnected ? 'Reconnect' : 'Test Connection'}
                  </Button>
                </motion.div>
              )}

              {/* Sync Preferences */}
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                      Auto-sync to CRM
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      Automatically push data to CRM when report is finalized
                    </p>
                  </div>
                  <Switch
                    checked={autoSync}
                    onCheckedChange={(v) => { setAutoSync(v); setUnsaved(true) }}
                    className="data-[state=checked]:bg-[#6366F1]"
                  />
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* ==================== TAB 4: AI AGENTS ==================== */}
        {activeTab === 'ai' && (
          <motion.div
            key="ai"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {/* AI Model */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Agent Behavior</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                Configure the AI model powering the agent pipeline.
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                {/* Model Selector */}
                <div>
                  <Label className="text-heading-sm text-[#F1F5F9] block mb-1">AI Model</Label>
                  <p className="text-body-sm text-[#64748B] mb-3">
                    Choose the LLM powering the agent pipeline
                  </p>
                  <div className="relative max-w-[320px]">
                    <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6366F1] pointer-events-none" />
                    <select
                      value={selectedModel}
                      onChange={(e) => { setSelectedModel(e.target.value); setUnsaved(true) }}
                      className="w-full h-10 pl-10 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                    >
                      {llmModels.map((m) => (
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
                      <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">API Endpoint URL</Label>
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
                      Test Connection
                    </Button>
                  </motion.div>
                )}

                <Separator className="bg-[#1E293B]" />

                {/* Temperature */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-heading-sm text-[#F1F5F9]">AI Creativity Level</Label>
                    <span className="text-body-sm text-[#6366F1] font-mono">{aiTemperature.toFixed(1)}</span>
                  </div>
                  <p className="text-body-sm text-[#64748B] mb-3">
                    Higher values produce more creative but potentially less consistent output
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
                    <span>Precise</span>
                    <span>Creative</span>
                  </div>
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Max Tokens */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-heading-sm text-[#F1F5F9]">Max Output Length</Label>
                    <span className="text-body-sm text-[#6366F1] font-mono">{maxTokens.toLocaleString()}</span>
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

            {/* Agent Toggles */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Agent Toggles</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                Enable or disable individual agents. Disabled agents are skipped in the pipeline.
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

        {/* ==================== TAB 5: INTEGRATIONS ==================== */}
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
                Database and storage backend configuration.
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-[#3ECF8E]" />
                    <span className="text-heading-sm text-[#F1F5F9]">Supabase Connection</span>
                  </div>
                  {supabaseConnected ? (
                    <Badge className="bg-[rgba(16,185,129,0.15)] text-[#10B981] border-[#10B981]">
                      <Check className="w-3 h-3 mr-1" /> Connected
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[#64748B] border-[#334155]">
                      Disconnected
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
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">
                    Service Key <span className="text-[#64748B]">(optional)</span>
                  </Label>
                  <Input
                    type="password"
                    value={supabaseServiceKey}
                    onChange={(e) => { setSupabaseServiceKey(e.target.value); setUnsaved(true) }}
                    placeholder="eyJhbGciOiJIUzI1NiIs..."
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50"
                  />
                </div>
                <Button
                  onClick={() => setSupabaseConnected(true)}
                  className="bg-[#3ECF8E] hover:bg-[#4EE99D] text-black font-medium"
                >
                  Test Connection
                </Button>
              </div>
            </motion.div>

            {/* miaoda SDK */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">miaoda-react-devkit</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                Flow orchestration and agent management SDK.
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                <div className="flex items-center gap-2 mb-2">
                  <Code className="w-5 h-5 text-[#6366F1]" />
                  <span className="text-heading-sm text-[#F1F5F9]">SDK Configuration</span>
                </div>
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">API Endpoint</Label>
                  <Input
                    value={miaodaEndpoint}
                    onChange={(e) => { setMiaodaEndpoint(e.target.value); setUnsaved(true) }}
                    placeholder="https://api.miaoda.ai"
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                  />
                </div>
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Project ID</Label>
                  <Input
                    value={miaodaProjectId}
                    onChange={(e) => { setMiaodaProjectId(e.target.value); setUnsaved(true) }}
                    placeholder="proj_..."
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                  />
                </div>
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">API Key</Label>
                  <Input
                    type="password"
                    value={miaodaApiKey}
                    onChange={(e) => { setMiaodaApiKey(e.target.value); setUnsaved(true) }}
                    placeholder="md_..."
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                  />
                </div>
                <Button
                  variant="outline"
                  className="border-[#334155] text-[#94A3B8] hover:text-[#F1F5F9]"
                >
                  Verify
                </Button>
              </div>
            </motion.div>

            {/* Third-Party APIs */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Third-Party APIs</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                External API integrations for enhanced AI capabilities.
              </p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-heading-sm text-[#F1F5F9] block mb-0.5">
                      Web Search Integration
                    </Label>
                    <p className="text-body-sm text-[#64748B]">
                      Enable AI agents to search for customer company news and updates
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
          </motion.div>
        )}

        {/* ==================== TAB 6: ACCOUNT ==================== */}
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
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Profile</h2>
              <p className="text-body-sm text-[#64748B] mb-4">Manage your personal information.</p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-5">
                {/* Avatar */}
                <div className="flex items-center gap-4">
                  <div className="relative group">
                    <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-2xl font-bold text-white">
                      {profileName.charAt(0)}
                    </div>
                    <div className="absolute inset-0 rounded-full bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                      <Upload className="w-5 h-5 text-white" />
                    </div>
                  </div>
                  <div>
                    <p className="text-heading-sm text-[#F1F5F9]">{profileName}</p>
                    <p className="text-body-sm text-[#64748B]">{profileEmail}</p>
                  </div>
                </div>

                <Separator className="bg-[#1E293B]" />

                {/* Name */}
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Name</Label>
                  <Input
                    value={profileName}
                    onChange={(e) => { setProfileName(e.target.value); setUnsaved(true) }}
                    className="bg-[#0D1321] border-[#1E293B] text-[#F1F5F9]"
                  />
                </div>

                {/* Email */}
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Email</Label>
                  <Input
                    value={profileEmail}
                    disabled
                    className="bg-[#0D1321] border-[#1E293B] text-[#64748B] cursor-not-allowed"
                  />
                  <p className="text-body-sm text-[#64748B] mt-1">Managed by OAuth provider</p>
                </div>

                {/* Role */}
                <div>
                  <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Role</Label>
                  <div className="relative max-w-[240px]">
                    <select
                      value={profileRole}
                      onChange={(e) => { setProfileRole(e.target.value); setUnsaved(true) }}
                      className="w-full h-10 px-3 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                    >
                      <option>Sales Rep</option>
                      <option>Sales Manager</option>
                      <option>Admin</option>
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
                  <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Team</h2>
                  <p className="text-body-sm text-[#64748B]">Manage team members and access.</p>
                </div>
                <Button
                  size="sm"
                  className="bg-[#6366F1] hover:bg-[#818CF8] text-white"
                  onClick={() => {
                    setTeamMembers((prev) => [
                      ...prev,
                      {
                        id: `new-${Date.now()}`,
                        name: 'New Member',
                        email: 'pending@dealflow.com',
                        role: 'Sales Rep',
                        status: 'pending',
                      },
                    ])
                    setUnsaved(true)
                  }}
                >
                  <Plus className="w-4 h-4 mr-1.5" />
                  Invite Member
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
                          {member.status}
                        </Badge>
                        <span className="text-body-sm text-[#94A3B8]">{member.role}</span>
                        <button
                          onClick={() => {
                            setTeamMembers((prev) => prev.filter((m) => m.id !== member.id))
                            setUnsaved(true)
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

            {/* Data Management */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#F1F5F9] mb-1">Data Management</h2>
              <p className="text-body-sm text-[#64748B] mb-4">Export or manage your data.</p>
              <div className="glass-card rounded-[16px] border border-[#1E293B] p-5">
                <Button
                  variant="outline"
                  className="border-[#334155] text-[#94A3B8] hover:text-[#F1F5F9]"
                >
                  Export all data as JSON
                </Button>
              </div>
            </motion.div>

            {/* Danger Zone */}
            <motion.div variants={cardVariant}>
              <h2 className="text-heading-sm text-[#EF4444] mb-1">Danger Zone</h2>
              <p className="text-body-sm text-[#64748B] mb-4">
                Destructive actions that cannot be undone.
              </p>
              <div className="rounded-[16px] border border-[#EF4444]/30 p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-body-md font-medium text-[#F1F5F9]">
                      Delete All Visit Records
                    </p>
                    <p className="text-body-sm text-[#64748B]">
                      Permanently remove all visit history
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    className="border-[#EF4444] text-[#EF4444] hover:bg-[rgba(239,68,68,0.1)]"
                  >
                    <Trash2 className="w-4 h-4 mr-1.5" />
                    Delete
                  </Button>
                </div>
                <Separator className="bg-[#EF4444]/20" />
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-body-md font-medium text-[#F1F5F9]">Reset All Settings</p>
                    <p className="text-body-sm text-[#64748B]">Restore default configuration</p>
                  </div>
                  <Button
                    variant="outline"
                    className="border-[#EF4444] text-[#EF4444] hover:bg-[rgba(239,68,68,0.1)]"
                  >
                    <RotateCcw className="w-4 h-4 mr-1.5" />
                    Reset
                  </Button>
                </div>
                <Separator className="bg-[#EF4444]/20" />
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-body-md font-medium text-[#F1F5F9]">Delete Account</p>
                    <p className="text-body-sm text-[#64748B]">
                      Permanently delete your account and all data
                    </p>
                  </div>
                  <Button className="bg-[#EF4444] hover:bg-[#DC2626] text-white">
                    <AlertTriangle className="w-4 h-4 mr-1.5" />
                    Delete Account
                  </Button>
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
                Reset to Defaults
              </Button>
              <div className="flex items-center gap-3">
                <span className="text-body-sm text-[#F59E0B]">Unsaved changes</span>
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
                    Save Changes
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
