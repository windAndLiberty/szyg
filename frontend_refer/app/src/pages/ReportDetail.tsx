import { useState, useRef } from 'react'
import { useParams, Link } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  Share2,
  Download,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Pencil,
  Target,
  Clock,
  CheckCircle2,
  HelpCircle,
  ListTodo,
  Heart,
  Send,
  Calendar,
  TrendingUp,
  AlertTriangle,
  PlusCircle,
  Kanban,
  UploadCloud,
  Mail,
  User,
  RefreshCw,
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { cn } from '@/lib/utils'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  deals,
  visitRecords,
  meetingMinutes,
  getStageColor,
  getStageLabel,
  getStageGlow,
} from '@/data/mockData'
import { DealStage } from '@/types'

// --- Types ---
type MinutesSection = {
  id: string
  title: string
  icon: React.ReactNode
  borderColor: string
  count: number
  content: React.ReactNode
}

// --- Helpers ---
const easeOutExpo = [0.16, 1, 0.3, 1] as [number, number, number, number]
const easeSpring = [0.34, 1.56, 0.64, 1] as [number, number, number, number]

function getPriorityColor(priority: string) {
  switch (priority) {
    case 'high':
      return { bg: 'rgba(239,68,68,0.15)', text: '#EF4444', border: '#EF4444' }
    case 'medium':
      return { bg: 'rgba(245,158,11,0.15)', text: '#F59E0B', border: '#F59E0B' }
    default:
      return { bg: 'rgba(59,130,246,0.15)', text: '#3B82F6', border: '#3B82F6' }
  }
}

function getPriorityLabel(priority: string) {
  switch (priority) {
    case 'high':
      return '高'
    case 'medium':
      return '中'
    default:
      return '低'
  }
}

// --- Collapsible Section Component ---
function CollapsibleSection({
  section,
  isOpen,
  onToggle,
  isEditing,
}: {
  section: MinutesSection
  isOpen: boolean
  onToggle: () => void
  isEditing: boolean
}) {
  const contentRef = useRef<HTMLDivElement>(null)

  return (
    <div
      className="rounded-[12px] border border-[#1E293B] overflow-hidden transition-all duration-200"
      style={{ borderLeftWidth: 4, borderLeftColor: section.borderColor }}
    >
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-[rgba(255,255,255,0.02)] transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-[#64748B]">{section.icon}</span>
          <span className="text-heading-sm text-[#F1F5F9]">{section.title}</span>
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[#1A2235] text-[#64748B]">
            {section.count} items
          </span>
        </div>
        <motion.div
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="w-4 h-4 text-[#64748B]" />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: [0.45, 0.05, 0.55, 0.95] as [number, number, number, number] }}
            className="overflow-hidden"
          >
            <div
              ref={contentRef}
              className={cn(
                'px-4 pb-4 pt-1',
                isEditing && 'bg-[rgba(245,158,11,0.05)]'
              )}
            >
              {section.content}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// --- Editable Text Component ---
function EditableText({
  content,
  isEditing,
  className,
  isTextarea = false,
}: {
  content: string
  isEditing: boolean
  className?: string
  isTextarea?: boolean
}) {
  if (isEditing) {
    if (isTextarea) {
      return (
        <textarea
          defaultValue={content}
          className={cn(
            'w-full bg-[#0D1321] border border-[#334155] rounded-[8px] p-3 text-[#F1F5F9] text-sm focus:outline-none focus:border-[#6366F1] resize-none min-h-[120px]',
            className
          )}
        />
      )
    }
    return (
      <input
        type="text"
        defaultValue={content}
        className={cn(
          'w-full bg-[#0D1321] border border-[#334155] rounded-[8px] px-3 py-2 text-[#F1F5F9] text-sm focus:outline-none focus:border-[#6366F1]',
          className
        )}
      />
    )
  }
  return <span className={className}>{content}</span>
}

// --- Circular Progress ---
function CircularProgress({ percentage, size = 80 }: { percentage: number; size?: number }) {
  const strokeWidth = 6
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (percentage / 100) * circumference

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#0D1321"
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#6366F1"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: easeOutExpo, delay: 0.3 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-heading-sm text-[#F1F5F9]">{percentage}%</span>
      </div>
    </div>
  )
}

// --- Main Component ---
export default function ReportDetail() {
  const { id } = useParams<{ id: string }>()
  const [isEditing, setIsEditing] = useState(false)
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    background: true,
    process: true,
    consensus: true,
    openQuestions: true,
    actionItems: true,
  })
  const [winRate, setWinRate] = useState(72)
  const [activeTab, setActiveTab] = useState('thanks')
  const [copiedMinutes, setCopiedMinutes] = useState(false)
  const [copiedEmail, setCopiedEmail] = useState(false)
  const [copiedCRM, setCopiedCRM] = useState(false)
  const [syncedCRM, setSyncedCRM] = useState(false)
  const [emailEditMode, setEmailEditMode] = useState(false)
  const [checkedActions, setCheckedActions] = useState<Record<string, boolean>>({})

  // Get deal data - use first deal as default if ID doesn't match
  const deal = deals.find((d) => d.id === id?.replace('r-', 'd')) || deals[0]
  const customerName = deal?.customerName || 'Acme Corp'
  const stageColor = getStageColor(deal.stage)
  const stageLabel = getStageLabel(deal.stage)
  const visit = visitRecords.find((v) => v.customerId === deal.customerId) || visitRecords[0]

  const toggleSection = (id: string) => {
    setOpenSections((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const handleCopyMinutes = () => {
    const text = `[拜访背景]\n${meetingMinutes.keyPoints.join('\n')}\n\n[拜访过程]\n${meetingMinutes.transcript}\n\n[达成共识]\n${meetingMinutes.decisions.join('\n')}\n\n[遗留问题]\n待补充\n\n[下一步待办]\n${meetingMinutes.actionItems.map((a) => `- [${a.completed ? 'x' : ' '}] ${a.text} (${a.assignee}, ${a.dueDate})`).join('\n')}`
    navigator.clipboard.writeText(text)
    setCopiedMinutes(true)
    setTimeout(() => setCopiedMinutes(false), 2000)
  }

  const handleCopyEmail = (subject: string, body: string) => {
    navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`)
    setCopiedEmail(true)
    setTimeout(() => setCopiedEmail(false), 2000)
  }

  const handleCopyCRM = () => {
    const crmJson = JSON.stringify(
      {
        companyName: customerName,
        contact: visitRecords.find((v) => v.customerId === deal.customerId)?.purpose || '',
        amount: deal.amount,
        closeDate: deal.expectedCloseDate,
        stage: stageLabel,
        winRate,
        nextFollowUp: format(new Date(Date.now() + 3 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd'),
      },
      null,
      2
    )
    navigator.clipboard.writeText(crmJson)
    setCopiedCRM(true)
    setTimeout(() => setCopiedCRM(false), 2000)
  }

  const handleSyncCRM = () => {
    setSyncedCRM(true)
  }

  const toggleActionCheck = (id: string) => {
    setCheckedActions((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  // --- Meeting Minutes Sections ---
  const minutesSections: MinutesSection[] = [
    {
      id: 'background',
      title: '拜访背景',
      icon: <Target className="w-4 h-4" />,
      borderColor: '#6366F1',
      count: 3,
      content: (
        <div className="space-y-3">
          {isEditing ? (
            <>
              <EditableText
                isEditing={true}
                content="拜访目的：首次方案演示，针对 Acme Corp 报表优化项目。"
                isTextarea
              />
              <EditableText
                isEditing={true}
                content="客户背景：Acme Corp 是中型制造企业（约800人），目前使用传统报表工具。"
                isTextarea
              />
              <EditableText
                isEditing={true}
                content="我方目标：展示报表加速能力，挖掘扩展机会。"
                isTextarea
              />
            </>
          ) : (
            <>
              <div className="flex gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-[#6366F1] mt-2 shrink-0" />
                <p className="text-body-md text-[#94A3B8]">
                  <span className="text-[#F1F5F9] font-medium">拜访目的：</span>
                  首次方案演示，针对 {customerName} 报表优化项目。
                </p>
              </div>
              <div className="flex gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-[#6366F1] mt-2 shrink-0" />
                <p className="text-body-md text-[#94A3B8]">
                  <span className="text-[#F1F5F9] font-medium">客户背景：</span>
                  {customerName} 是中型制造企业（约800人），目前使用传统报表工具。
                </p>
              </div>
              <div className="flex gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-[#6366F1] mt-2 shrink-0" />
                <p className="text-body-md text-[#94A3B8]">
                  <span className="text-[#F1F5F9] font-medium">我方目标：</span>
                  展示报表加速能力，挖掘扩展机会。
                </p>
              </div>
            </>
          )}
        </div>
      ),
    },
    {
      id: 'process',
      title: '拜访过程',
      icon: <Clock className="w-4 h-4" />,
      borderColor: '#3B82F6',
      count: 4,
      content: (
        <div className="relative pl-4">
          {/* Timeline line */}
          <div className="absolute left-[7px] top-2 bottom-2 w-px bg-[#1E293B]" />
          <div className="space-y-4">
            {[
              { time: '14:00', text: '开场交流现状痛点。张总确认月末报表需要3整天时间。' },
              { time: '14:20', text: '演示实时仪表板。张总："这正是我们需要的。"' },
              { time: '14:45', text: '讨论与SAP系统集成。技术可行性已确认。' },
              { time: '15:10', text: '预算讨论。张总透露今年IT预算约50万，我们的方案在范围内。' },
            ].map((item, i) => (
              <div key={i} className="relative flex gap-3">
                <div className="absolute left-[-9px] w-2 h-2 rounded-full bg-[#3B82F6] mt-1.5 ring-4 ring-[#0B0F1A]" />
                <span className="text-mono-md text-[#64748B] w-12 shrink-0">{item.time}</span>
                {isEditing ? (
                  <textarea
                    defaultValue={item.text}
                    className="flex-1 bg-[#0D1321] border border-[#334155] rounded-[8px] p-2 text-[#F1F5F9] text-sm focus:outline-none focus:border-[#6366F1] resize-none min-h-[60px]"
                  />
                ) : (
                  <p className="text-body-md text-[#94A3B8]">{item.text}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      id: 'consensus',
      title: '达成共识',
      icon: <CheckCircle2 className="w-4 h-4" />,
      borderColor: '#10B981',
      count: 2,
      content: (
        <div className="space-y-3">
          {[
            '双方一致认为报表速度是首要解决的痛点',
            `${customerName} 将在收到正式方案后进行内部评估`,
          ].map((item, i) => (
            <div key={i} className="flex gap-3">
              <CheckCircle2 className="w-4 h-4 text-[#10B981] mt-0.5 shrink-0" />
              {isEditing ? (
                <input
                  type="text"
                  defaultValue={item}
                  className="flex-1 bg-[#0D1321] border border-[#334155] rounded-[8px] px-3 py-2 text-[#F1F5F9] text-sm focus:outline-none focus:border-[#6366F1]"
                />
              ) : (
                <p className="text-body-md text-[#94A3B8]">{item}</p>
              )}
            </div>
          ))}
        </div>
      ),
    },
    {
      id: 'openQuestions',
      title: '遗留问题',
      icon: <HelpCircle className="w-4 h-4" />,
      borderColor: '#F59E0B',
      count: 2,
      content: (
        <div className="space-y-3">
          {[
            'SAP集成测试的具体时间节点？',
            '对方数据安全政策是否允许云端部署？',
          ].map((item, i) => (
            <div key={i} className="flex gap-3">
              <HelpCircle className="w-4 h-4 text-[#F59E0B] mt-0.5 shrink-0" />
              {isEditing ? (
                <input
                  type="text"
                  defaultValue={item}
                  className="flex-1 bg-[#0D1321] border border-[#334155] rounded-[8px] px-3 py-2 text-[#F1F5F9] text-sm focus:outline-none focus:border-[#6366F1]"
                />
              ) : (
                <p className="text-body-md text-[#94A3B8]">{item}</p>
              )}
            </div>
          ))}
        </div>
      ),
    },
    {
      id: 'actionItems',
      title: '下一步待办',
      icon: <ListTodo className="w-4 h-4" />,
      borderColor: '#6366F1',
      count: 3,
      content: (
        <div className="space-y-3">
          {[
            { text: '发送正式方案（含SAP集成计划）', assignee: '我', due: '1月18日' },
            { text: '提供制造业参考客户联系方式', assignee: '我', due: '1月20日' },
            { text: '确认云安全合规要求', assignee: '张总', due: '1月22日' },
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={checkedActions[`action-${i}`] || false}
                onChange={() => toggleActionCheck(`action-${i}`)}
                className="mt-1 w-4 h-4 rounded border-[#334155] bg-[#0D1321] text-[#6366F1] accent-[#6366F1] cursor-pointer"
              />
              {isEditing ? (
                <div className="flex-1 flex gap-2">
                  <input
                    type="text"
                    defaultValue={item.text}
                    className="flex-1 bg-[#0D1321] border border-[#334155] rounded-[8px] px-3 py-2 text-[#F1F5F9] text-sm focus:outline-none focus:border-[#6366F1]"
                  />
                  <input
                    type="text"
                    defaultValue={item.assignee}
                    className="w-16 bg-[#0D1321] border border-[#334155] rounded-[8px] px-2 py-2 text-[#F1F5F9] text-sm text-center focus:outline-none focus:border-[#6366F1]"
                  />
                  <input
                    type="text"
                    defaultValue={item.due}
                    className="w-20 bg-[#0D1321] border border-[#334155] rounded-[8px] px-2 py-2 text-[#F1F5F9] text-sm text-center focus:outline-none focus:border-[#6366F1]"
                  />
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span
                    className={cn(
                      'text-body-md',
                      checkedActions[`action-${i}`]
                        ? 'text-[#64748B] line-through'
                        : 'text-[#F1F5F9]'
                    )}
                  >
                    {item.text}
                  </span>
                  <span className="text-body-sm text-[#64748B]">
                    — {item.assignee} · 截止 {item.due}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      ),
    },
  ]

  // --- Email draft data ---
  const emailTabs = [
    {
      id: 'thanks',
      label: '感谢信',
      icon: <Heart className="w-4 h-4" />,
      timing: '拜访当天发送',
      tone: '专业、温暖、感激',
      subject: `感谢今天的演示 — ${customerName} 报表解决方案`,
      body: `您好张总，\n\n感谢您今天抽出时间与我见面。很高兴深入了解 ${customerName} 的报表挑战，并讨论我们的解决方案如何帮助简化月末流程。\n\n感谢您坦率地反馈目前的3天报表周期 — 这正是我们擅长解决的痛点。我有信心可以将其缩短到2小时以内。\n\n如讨论所述，我将在1月18日前发送包含SAP集成细节的正式方案。在此期间，如有任何问题请随时联系。\n\n此致敬礼，\n[您的名字]`,
    },
    {
      id: 'proposal',
      label: '方案推送',
      icon: <Send className="w-4 h-4" />,
      timing: '拜访后2-3天发送',
      tone: '专业、详细、价值导向',
      subject: `方案：${customerName} 报表优化 — 内含ROI分析`,
      body: `您好张总，\n\n根据我们上周的深入交流，我为您准备了这份定制方案。\n\n核心亮点：\n• 报表生成时间：从3天缩短至2小时（提升36倍）\n• SAP无缝集成：零停机迁移，保留所有历史数据\n• 投资回报率：预计6个月内收回成本\n• 制造业标杆案例：参考同行成功经验\n\n附件中包含详细的技术实施路线图和报价。期待您的反馈。\n\n此致敬礼，\n[您的名字]`,
    },
    {
      id: 'next',
      label: '约下次',
      icon: <Calendar className="w-4 h-4" />,
      timing: '发送方案后，或拜访1周后',
      tone: '友好、低压力、具体',
      subject: `下一步：与CTO的技术深度交流`,
      body: `您好张总，\n\n希望您已经收到并查看了我们的方案。我想安排一次与贵司CTO李总的技术深度交流，重点讨论SAP集成架构和数据安全合规。\n\n建议时间：\n• 下周二下午2:00\n• 下周四下午2:00\n\n会议预计60分钟，我将携带解决方案架构师一同参加。\n\n期待您的确认。\n\n此致敬礼，\n[您的名字]`,
    },
  ]

  // --- Strategy actions ---
  const strategyActions = [
    {
      id: 'sa1',
      title: '安排技术Demo',
      description:
        '安排60分钟技术演示，重点展示SAP集成功能。解决主要技术顾虑，与决策者建立直接关系。',
      timeline: '3个工作日内',
      priority: 'high',
      button: '立即安排',
    },
    {
      id: 'sa2',
      title: '输出正式方案',
      description:
        '准备包含SAP集成时间线、数据迁移计划和ROI计算的综合方案。参考制造业客户案例。',
      timeline: '1月18日前',
      priority: 'high',
      button: '开始起草',
    },
    {
      id: 'sa3',
      title: '介绍参考客户',
      description: '联系2位已完成类似报表转型的制造业客户，安排经验分享交流。',
      timeline: '1月20日前',
      priority: 'medium',
      button: '查找联系人',
    },
  ]

  // --- CRM fields ---
  const crmFields = [
    { field: '客户名称', value: customerName },
    { field: '联系人', value: '张总（IT总监）' },
    { field: '商机金额', value: `¥${(deal.amount / 1000).toFixed(0)}K` },
    { field: '预计成交日期', value: deal.expectedCloseDate },
    { field: '商机阶段', value: stageLabel },
    { field: '赢率', value: `${winRate}%` },
    { field: '下次跟进日期', value: format(new Date(Date.now() + 3 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd') },
    { field: '跟进内容摘要', value: '发送正式方案，安排技术Demo' },
    { field: '竞争对手', value: 'CompetitorX' },
    { field: '痛点', value: '报表速度慢、月末延迟' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: easeOutExpo }}
      className="max-w-[1400px] mx-auto space-y-6"
    >
      {/* ====== REPORT HEADER ====== */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: easeOutExpo }}
        className="gradient-card border border-[#1E293B] rounded-[16px] p-5"
      >
        {/* Back + Actions row */}
        <div className="flex items-center justify-between mb-4">
          <Link
            to="/reports"
            className="flex items-center gap-2 text-[#94A3B8] hover:text-[#F1F5F9] transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            返回报告列表
          </Link>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-4 py-2 rounded-[10px] border border-[#1E293B] text-[#94A3B8] text-sm hover:border-[#334155] hover:text-[#F1F5F9] transition-colors">
              <Share2 className="w-4 h-4" />
              分享
            </button>
            <button className="flex items-center gap-2 px-4 py-2 rounded-[10px] border border-[#1E293B] text-[#94A3B8] text-sm hover:border-[#334155] hover:text-[#F1F5F9] transition-colors">
              <Download className="w-4 h-4" />
              导出PDF
            </button>
          </div>
        </div>

        {/* Title row */}
        <div className="flex items-center flex-wrap gap-3 mb-4">
          <h1 className="text-heading-lg text-[#F1F5F9] font-display">{customerName}</h1>
          <span className="text-[#64748B]">·</span>
          <span className="text-body-md text-[#94A3B8]">
            {format(parseISO(visit.visitDate), 'yyyy年M月d日')}
          </span>
          <span className="text-[#64748B]">·</span>
          <span
            className="px-3 py-1 rounded-full text-xs font-medium"
            style={{ backgroundColor: `${stageColor}20`, color: stageColor }}
          >
            方案演示
          </span>
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium"
            style={{ backgroundColor: 'rgba(16,185,129,0.15)', color: '#10B981' }}
          >
            <CheckCircle2 className="w-3 h-3" />
            已就绪
          </motion.span>
        </div>

        {/* Key info chips */}
        <div className="flex flex-wrap gap-2">
          {[
            { label: '¥500K 预算', color: '#10B981' },
            { label: 'CTO 李总 — 决策人', color: '#3B82F6' },
            { label: 'CompetitorX 提及', color: '#F59E0B' },
            { label: 'Q3 时间线', color: '#06B6D4' },
          ].map((chip, i) => (
            <motion.span
              key={i}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: 0.1 + i * 0.06, ease: easeOutExpo }}
              className="px-3 py-1 rounded-full text-xs font-medium"
              style={{ backgroundColor: `${chip.color}15`, color: chip.color }}
            >
              {chip.label}
            </motion.span>
          ))}
        </div>
      </motion.div>

      {/* ====== TWO COLUMN LAYOUT ====== */}
      <div className="grid grid-cols-1 xl:grid-cols-[55%_45%] gap-6">
        {/* --- LEFT: Meeting Minutes --- */}
        <motion.div
          initial={{ opacity: 0, x: -15 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.2, ease: easeOutExpo }}
          className="gradient-card border border-[#1E293B] rounded-[16px] p-6"
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-heading-md text-[#F1F5F9] font-display">拜访纪要</h2>
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyMinutes}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-sm text-[#94A3B8] hover:text-[#6366F1] hover:bg-[rgba(99,102,241,0.08)] transition-colors"
              >
                {copiedMinutes ? (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    已复制
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    复制纪要
                  </>
                )}
              </button>
              <button
                onClick={() => setIsEditing(!isEditing)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-sm transition-colors',
                  isEditing
                    ? 'text-[#F59E0B] bg-[rgba(245,158,11,0.08)]'
                    : 'text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)]'
                )}
              >
                <Pencil className="w-3.5 h-3.5" />
                {isEditing ? '保存' : '编辑'}
              </button>
            </div>
          </div>

          {/* Sections */}
          <div className="space-y-3">
            {minutesSections.map((section, i) => (
              <motion.div
                key={section.id}
                initial={{ opacity: 0, x: -15 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.35, delay: 0.25 + i * 0.08, ease: easeOutExpo }}
              >
                <CollapsibleSection
                  section={section}
                  isOpen={openSections[section.id] ?? true}
                  onToggle={() => toggleSection(section.id)}
                  isEditing={isEditing}
                />
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* --- RIGHT: Deal Panel --- */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.3, ease: easeSpring }}
          className="space-y-4"
        >
          {/* Deal Card */}
          <div
            className="rounded-[16px] bg-[#1A2235] border border-[#1E293B] p-5"
            style={{ borderLeftWidth: 4, borderLeftColor: stageColor }}
          >
            {/* Stage badge + edit */}
            <div className="flex items-center justify-between mb-4">
              <span
                className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium"
                style={{
                  backgroundColor: `${stageColor}20`,
                  color: stageColor,
                  boxShadow: `0 0 8px ${getStageGlow(deal.stage)}`,
                }}
              >
                {stageLabel}
              </span>
              <button className="p-1.5 rounded-lg text-[#64748B] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)] transition-colors">
                <Pencil className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Amount */}
            <div className="mb-5">
              <p className="font-display text-[36px] font-bold text-[#F1F5F9] leading-none">
                ¥{(deal.amount / 1000).toFixed(0)}K
              </p>
              <p className="text-body-sm text-[#64748B] mt-1">基于 ¥500K 预算范围估算</p>
            </div>

            {/* Win Rate */}
            <div className="flex items-center gap-4 mb-5">
              <CircularProgress percentage={winRate} size={80} />
              <div className="flex-1">
                <p className="text-label text-[#64748B] mb-2">赢率调整</p>
                <Slider
                  value={[winRate]}
                  onValueChange={(v) => setWinRate(v[0])}
                  max={100}
                  step={1}
                  className="w-full"
                />
                <div className="flex justify-between mt-1">
                  <span className="text-[11px] text-[#64748B]">0%</span>
                  <span className="text-[11px] text-[#64748B]">100%</span>
                </div>
              </div>
            </div>

            {/* Close date + assigned */}
            <div className="space-y-2.5 pt-4 border-t border-[#1E293B]">
              <div className="flex items-center gap-2 text-body-sm">
                <Calendar className="w-4 h-4 text-[#64748B]" />
                <span className="text-[#64748B]">预计成交：</span>
                <span className="text-[#F1F5F9]">
                  {format(parseISO(deal.expectedCloseDate), 'yyyy年M月d日')}
                </span>
              </div>
              <div className="flex items-center gap-2 text-body-sm">
                <User className="w-4 h-4 text-[#64748B]" />
                <span className="text-[#64748B]">负责人：</span>
                <span className="text-[#F1F5F9]">{deal.assignedTo}</span>
              </div>
            </div>
          </div>

          {/* Profile Updates Card */}
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.4, ease: easeOutExpo }}
            className="rounded-[16px] bg-[#1A2235] border border-[#1E293B] p-5"
          >
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-heading-sm text-[#F1F5F9]">客户画像更新</h3>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[#1A2235] text-[#64748B]">
                3 changes
              </span>
            </div>
            <div className="space-y-3">
              {[
                {
                  icon: <PlusCircle className="w-4 h-4 text-[#10B981]" />,
                  text: '新增痛点：报表速度（紧急）',
                  color: '#10B981',
                },
                {
                  icon: <RefreshCw className="w-4 h-4 text-[#F59E0B]" />,
                  text: '更新预算：¥300K → ¥500K',
                  color: '#F59E0B',
                },
                {
                  icon: <User className="w-4 h-4 text-[#10B981]" />,
                  text: '新增联系人：李总（CTO）— 决策人',
                  color: '#10B981',
                },
              ].map((item, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: 0.45 + i * 0.1, ease: easeOutExpo }}
                  className="flex items-center gap-3"
                >
                  {item.icon}
                  <span className="text-body-sm" style={{ color: item.color }}>
                    {item.text}
                  </span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      </div>

      {/* ====== BOTTOM TWO COLUMN: Strategy + Emails ====== */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Follow-up Strategy */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.5, ease: easeOutExpo }}
          className="gradient-card border border-[#1E293B] rounded-[16px] p-6"
        >
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-heading-md text-[#F1F5F9] font-display">跟进策略</h2>
            <span
              className="px-2.5 py-0.5 rounded-full text-xs font-bold"
              style={{
                backgroundColor: getPriorityColor('high').bg,
                color: getPriorityColor('high').text,
              }}
            >
              高优先级
            </span>
          </div>

          {/* Strategy text */}
          <div className="mb-5 p-4 rounded-[12px] bg-[#1A2235] border border-[#1E293B]">
            <p className="text-body-lg text-[#94A3B8] leading-relaxed">
              {customerName} 表现出强烈意向，预算明确（
              <span className="bg-[rgba(16,185,129,0.2)] text-[#10B981] px-1 rounded">¥500K</span>
              ）且时间紧迫（
              <span className="bg-[rgba(6,182,212,0.2)] text-[#06B6D4] px-1 rounded">Q3</span>
              ）。
              <span className="bg-[rgba(245,158,11,0.2)] text-[#F59E0B] px-1 rounded">CompetitorX</span>
              也在评估中，但我们的演示获得了积极反馈。
              <strong className="text-[#6366F1]">3天内加速方案交付</strong>
              以保持势头。安排与CTO李总的技术深度交流以锁定技术认可。
            </p>
          </div>

          {/* Conditional strategy tips */}
          <div className="mb-5 space-y-2">
            {winRate < 50 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="flex items-start gap-2 p-3 rounded-[8px] bg-[rgba(245,158,11,0.08)] border border-[rgba(245,158,11,0.2)]"
              >
                <AlertTriangle className="w-4 h-4 text-[#F59E0B] mt-0.5 shrink-0" />
                <p className="text-body-sm text-[#F59E0B]">
                  赢率较低 — 建议以培育为主，发送行业案例，两周后回访
                </p>
              </motion.div>
            )}
            <div className="flex items-start gap-2 p-3 rounded-[8px] bg-[rgba(99,102,241,0.08)] border border-[rgba(99,102,241,0.2)]">
              <TrendingUp className="w-4 h-4 text-[#6366F1] mt-0.5 shrink-0" />
              <p className="text-body-sm text-[#818CF8]">
                决策链复杂 — 推动与拍板人（CTO李总）直接会面
              </p>
            </div>
          </div>

          {/* Action checklist */}
          <h4 className="text-heading-sm text-[#F1F5F9] mb-3">建议行动</h4>
          <div className="space-y-3">
            {strategyActions.map((action, i) => {
              const pColor = getPriorityColor(action.priority)
              return (
                <motion.div
                  key={action.id}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: 0.55 + i * 0.12, ease: easeOutExpo }}
                  className="rounded-[12px] bg-[#1A2235] border border-[#1E293B] p-4"
                  style={{ borderLeftWidth: 3, borderLeftColor: pColor.border }}
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2">
                      <h5 className="text-body-md font-semibold text-[#F1F5F9]">
                        {action.title}
                      </h5>
                      <span
                        className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                        style={{ backgroundColor: pColor.bg, color: pColor.text }}
                      >
                        {getPriorityLabel(action.priority)}
                      </span>
                    </div>
                  </div>
                  <p className="text-body-sm text-[#94A3B8] mb-2">{action.description}</p>
                  <div className="flex items-center justify-between">
                    <span className="text-body-sm text-[#64748B]">
                      <Clock className="w-3.5 h-3.5 inline mr-1" />
                      {action.timeline}
                    </span>
                    <button className="px-3 py-1.5 rounded-[8px] text-xs font-medium bg-[#6366F1] text-white hover:bg-[#818CF8] transition-colors">
                      {action.button}
                    </button>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </motion.div>

        {/* Email Drafts */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6, ease: easeOutExpo }}
          className="gradient-card border border-[#1E293B] rounded-[16px] p-6"
        >
          <h2 className="text-heading-md text-[#F1F5F9] font-display mb-4">邮件草稿</h2>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="w-full bg-[#0D1321] border border-[#1E293B] rounded-[10px] p-1 mb-4">
              {emailTabs.map((tab) => (
                <TabsTrigger
                  key={tab.id}
                  value={tab.id}
                  className={cn(
                    'flex-1 flex items-center justify-center gap-1.5 py-2 rounded-[8px] text-sm transition-all',
                    activeTab === tab.id
                      ? 'bg-[#1A2235] text-[#F1F5F9] shadow-sm'
                      : 'text-[#64748B] hover:text-[#94A3B8]'
                  )}
                >
                  {tab.icon}
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {emailTabs.map((tab) => (
              <TabsContent key={tab.id} value={tab.id} className="mt-0">
                <AnimatePresence mode="wait">
                  {activeTab === tab.id && (
                    <motion.div
                      key={tab.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      {/* Meta info */}
                      <div className="flex flex-wrap items-center gap-3 mb-3">
                        <span className="px-2.5 py-1 rounded-full text-[11px] bg-[rgba(99,102,241,0.1)] text-[#818CF8]">
                          {tab.timing}
                        </span>
                        <span className="px-2.5 py-1 rounded-full text-[11px] bg-[rgba(16,185,129,0.1)] text-[#10B981]">
                          {tab.tone}
                        </span>
                      </div>

                      {/* Subject */}
                      <div className="mb-3">
                        <label className="text-label text-[#64748B] mb-1.5 block">主题</label>
                        {emailEditMode ? (
                          <input
                            type="text"
                            defaultValue={tab.subject}
                            className="w-full bg-[#0D1321] border border-[#334155] rounded-[8px] px-3 py-2 text-[#F1F5F9] text-sm italic focus:outline-none focus:border-[#6366F1]"
                          />
                        ) : (
                          <p className="text-body-md text-[#94A3B8] italic">{tab.subject}</p>
                        )}
                      </div>

                      {/* Email body */}
                      <div className="mb-4">
                        <label className="text-label text-[#64748B] mb-1.5 block">正文</label>
                        <div className="rounded-[12px] bg-[#0D1321] border border-[#1E293B] p-4">
                          {emailEditMode ? (
                            <textarea
                              defaultValue={tab.body}
                              className="w-full bg-transparent text-[#F1F5F9] text-sm font-mono leading-relaxed focus:outline-none resize-none min-h-[200px]"
                            />
                          ) : (
                            <p className="text-sm font-mono text-[#94A3B8] leading-relaxed whitespace-pre-line">
                              {tab.body}
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleCopyEmail(tab.subject, tab.body)}
                          className="flex items-center gap-1.5 px-3 py-2 rounded-[8px] text-sm text-[#94A3B8] hover:text-[#6366F1] hover:bg-[rgba(99,102,241,0.08)] transition-colors"
                        >
                          {copiedEmail && activeTab === tab.id ? (
                            <>
                              <Check className="w-3.5 h-3.5" />
                              已复制
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" />
                              一键复制
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => setEmailEditMode(!emailEditMode)}
                          className={cn(
                            'flex items-center gap-1.5 px-3 py-2 rounded-[8px] text-sm transition-colors',
                            emailEditMode
                              ? 'text-[#F59E0B] bg-[rgba(245,158,11,0.08)]'
                              : 'text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)]'
                          )}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                          {emailEditMode ? '完成' : '编辑'}
                        </button>
                        <button className="flex items-center gap-1.5 px-3 py-2 rounded-[8px] text-sm text-[#94A3B8] hover:text-[#10B981] hover:bg-[rgba(16,185,129,0.08)] transition-colors">
                          <Mail className="w-3.5 h-3.5" />
                          邮件发送
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </TabsContent>
            ))}
          </Tabs>
        </motion.div>
      </div>

      {/* ====== CRM SYNC SECTION ====== */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.7, ease: easeOutExpo }}
        className="gradient-card border border-[#1E293B] rounded-[16px] p-6"
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <h2 className="text-heading-md text-[#F1F5F9] font-display">CRM 同步</h2>
            <span
              className={cn(
                'flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium',
                syncedCRM
                  ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981]'
                  : 'bg-[rgba(245,158,11,0.15)] text-[#F59E0B]'
              )}
            >
              {syncedCRM ? (
                <>
                  <CheckCircle2 className="w-3 h-3" />
                  已同步
                </>
              ) : (
                <>
                  <AlertTriangle className="w-3 h-3" />
                  待同步
                </>
              )}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyCRM}
              className="flex items-center gap-2 px-4 py-2 rounded-[10px] border border-[#1E293B] text-[#94A3B8] text-sm hover:border-[#334155] hover:text-[#F1F5F9] transition-colors"
            >
              {copiedCRM ? (
                <>
                  <Check className="w-4 h-4" />
                  已复制
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  一键复制CRM数据
                </>
              )}
            </button>
            <button
              onClick={handleSyncCRM}
              disabled={syncedCRM}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-[10px] text-sm font-medium transition-all',
                syncedCRM
                  ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981] cursor-default'
                  : 'bg-[#6366F1] text-white hover:bg-[#818CF8] hover:scale-105 active:scale-[0.97]'
              )}
            >
              {syncedCRM ? (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  已标记为已录入
                </>
              ) : (
                <>
                  <UploadCloud className="w-4 h-4" />
                  标记为已录入CRM
                </>
              )}
            </button>
          </div>
        </div>

        {/* CRM Data Table */}
        <div className="rounded-[12px] border border-[#1E293B] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-[#0D1321]">
                  <th className="text-left px-4 py-3 text-label text-[#64748B] font-medium w-1/3">
                    字段
                  </th>
                  <th className="text-left px-4 py-3 text-label text-[#64748B] font-medium">
                    值
                  </th>
                </tr>
              </thead>
              <tbody>
                {crmFields.map((row, i) => (
                  <motion.tr
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.75 + i * 0.04, ease: easeOutExpo }}
                    className={cn(
                      'border-t border-[#1E293B]',
                      i % 2 === 0 ? 'bg-transparent' : 'bg-[rgba(17,24,39,0.5)]'
                    )}
                  >
                    <td className="px-4 py-3 text-body-sm text-[#64748B] text-right">
                      {row.field}
                    </td>
                    <td className="px-4 py-3 text-body-md text-[#F1F5F9]">{row.value}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>

      {/* ====== BOTTOM ACTION BAR ====== */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.8, ease: easeOutExpo }}
        className="sticky bottom-0 left-0 right-0 bg-[#111827]/95 backdrop-blur-md border-t border-[#1E293B] rounded-t-[16px] px-6 py-4 -mx-2"
      >
        <div className="flex items-center justify-between flex-wrap gap-4">
          {/* Back */}
          <Link
            to="/reports"
            className="flex items-center gap-2 px-4 py-2 rounded-[10px] text-[#94A3B8] text-sm hover:bg-[rgba(255,255,255,0.03)] hover:text-[#F1F5F9] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            返回报告列表
          </Link>

          {/* Pipeline Stage Indicator */}
          <div className="flex items-center gap-1">
            {['InitialContact', 'NeedsConfirmed', 'SolutionEval', 'Negotiation', 'Won'].map(
              (stage, i) => {
                const s = stage as DealStage
                const isCurrent = deal.stage === s
                const isPast =
                  ['InitialContact', 'NeedsConfirmed', 'SolutionEval', 'Negotiation', 'Won'].indexOf(
                    deal.stage
                  ) >= i
                const color = getStageColor(s)
                return (
                  <div key={stage} className="flex items-center">
                    {i > 0 && (
                      <ChevronRight className="w-3.5 h-3.5 text-[#64748B] mx-0.5" />
                    )}
                    <span
                      className={cn(
                        'px-2.5 py-1 rounded-full text-[11px] font-medium transition-all',
                        isCurrent
                          ? 'text-white'
                          : isPast
                            ? 'text-[#64748B]'
                            : 'text-[#334155]'
                      )}
                      style={
                        isCurrent
                          ? {
                              backgroundColor: `${color}30`,
                              color,
                              boxShadow: `0 0 12px ${getStageGlow(s)}`,
                            }
                          : {}
                      }
                    >
                      {getStageLabel(s)}
                    </span>
                  </div>
                )
              }
            )}
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-2">
            <Link
              to="/input"
              className="flex items-center gap-2 px-4 py-2 rounded-[10px] border border-[#1E293B] text-[#94A3B8] text-sm hover:border-[#334155] hover:text-[#F1F5F9] transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              新建拜访
            </Link>
            <Link
              to="/pipeline"
              className="flex items-center gap-2 px-4 py-2 rounded-[10px] bg-[#6366F1] text-white text-sm font-medium hover:bg-[#818CF8] hover:scale-105 active:scale-[0.97] transition-all"
            >
              <Kanban className="w-4 h-4" />
              查看Pipeline
            </Link>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}
