import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Type,
  Camera,
  Mic,
  Upload,
  X,
  Paperclip,
  ChevronDown,
  Plus,
  Calendar,
  Target,
  FileText,
  ArrowLeft,
  Sparkles,
  Search,
  Circle,
  Image,
  StopCircle,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { customers } from '@/data/mockData'
import { cn } from '@/lib/utils'
import { format } from 'date-fns'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type InputTab = 'text' | 'ocr' | 'voice'

interface UploadedFile {
  id: string
  file: File
  name: string
  size: string
  preview?: string
  status: 'uploading' | 'processing' | 'extracted' | 'failed'
}

interface NewCustomerForm {
  companyName: string
  industry: string
  companySize: string
  contactName: string
  contactTitle: string
}

const easeOutExpo = [0.16, 1, 0.3, 1] as [number, number, number, number]

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const tabs: { id: InputTab; label: string; icon: typeof Type }[] = [
  { id: 'text', label: 'Text Input', icon: Type },
  { id: 'ocr', label: 'OCR Upload', icon: Camera },
  { id: 'voice', label: 'Voice Transcript', icon: Mic },
]

const purposeOptions = [
  'First Contact / Discovery',
  'Needs Assessment',
  'Solution Demo',
  'Proposal Review',
  'Negotiation',
  'Relationship Building',
  'Other',
]

const industryOptions = [
  'SaaS',
  'Manufacturing',
  'Consulting',
  'Consumer Goods',
  'Other',
]

const companySizeOptions = ['1-50', '51-200', '201-1000', '1000+']

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function QuickInput() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const ocrInputRef = useRef<HTMLInputElement>(null)

  /* -- state -- */
  const [activeTab, setActiveTab] = useState<InputTab>('text')
  const [textContent, setTextContent] = useState('')
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [isDragging, setIsDragging] = useState(false)

  /* customer */
  const [selectedCustomer, setSelectedCustomer] = useState<typeof customers[0] | null>(null)
  const [customerDropdownOpen, setCustomerDropdownOpen] = useState(false)
  const [customerSearch, setCustomerSearch] = useState('')
  const [showNewCustomer, setShowNewCustomer] = useState(false)
  const [newCustomer, setNewCustomer] = useState<NewCustomerForm>({
    companyName: '',
    industry: industryOptions[0],
    companySize: companySizeOptions[1],
    contactName: '',
    contactTitle: '',
  })

  /* visit details */
  const [visitDate, setVisitDate] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [visitPurpose, setVisitPurpose] = useState(purposeOptions[0])
  const [visitNotes, setVisitNotes] = useState('')

  /* voice */
  const [isRecording, setIsRecording] = useState(false)
  const [recordTime, setRecordTime] = useState(0)
  const [voiceText, setVoiceText] = useState('')

  /* -- derived -- */
  const filteredCustomers = customers.filter((c) =>
    c.name.toLowerCase().includes(customerSearch.toLowerCase())
  )

  const hasContent = textContent.length > 0 || uploadedFiles.length > 0 || voiceText.length > 0

  /* -- handlers -- */
  const handleTabChange = (tab: InputTab) => {
    setActiveTab(tab)
  }

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return
    Array.from(files).forEach((file) => {
      const id = Math.random().toString(36).slice(2)
      const uploaded: UploadedFile = {
        id,
        file,
        name: file.name,
        size: formatFileSize(file.size),
        preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
        status: 'processing',
      }
      setUploadedFiles((prev) => [...prev, uploaded])
      // Simulate processing
      setTimeout(() => {
        setUploadedFiles((prev) =>
          prev.map((f) => (f.id === id ? { ...f, status: 'extracted' as const } : f))
        )
      }, 2000)
    })
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      handleFileSelect(e.dataTransfer.files)
    },
    [handleFileSelect]
  )

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const removeFile = (id: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== id))
  }

  const handleAddNewCustomer = () => {
    if (!newCustomer.companyName.trim()) return
    setShowNewCustomer(false)
    setSelectedCustomer({
      id: `new-${Date.now()}`,
      name: newCustomer.companyName,
      industry: newCustomer.industry,
      contactName: newCustomer.contactName,
      email: '',
      phone: '',
      dealCount: 0,
      totalValue: 0,
      lastVisitDate: undefined,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    })
    setCustomerDropdownOpen(false)
  }

  /* -- animation variants -- */
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0 },
    },
  }

  const fadeUp = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.4, ease: easeOutExpo },
    },
  }

  const fadeUp15 = {
    hidden: { opacity: 0, y: 15 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.4, ease: easeOutExpo },
    },
  }

  const slideFromRight = {
    hidden: { opacity: 0, x: 20 },
    visible: {
      opacity: 1,
      x: 0,
      transition: { duration: 0.4, ease: easeOutExpo },
    },
  }

  const staggerField = {
    hidden: { opacity: 0, y: 10 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: { duration: 0.4, ease: easeOutExpo, delay: i * 0.06 },
    }),
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="max-w-[1200px] mx-auto pb-24"
    >
      {/* ========== PAGE HEADER ========== */}
      <motion.div variants={fadeUp} className="mb-8">
        <h1 className="text-display-md font-display text-[#F1F5F9] mb-2">
          Capture Visit
        </h1>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <Circle className="w-2 h-2 text-[#6366F1] fill-[#6366F1]" />
            <div className="w-4 h-[2px] bg-[#6366F1]" />
            <Circle className="w-2 h-2 text-[#8B5CF6]" />
            <div className="w-4 h-[2px] bg-[#8B5CF6] opacity-50" />
            <Circle className="w-2 h-2 text-[#818CF8]" />
          </div>
          <p className="text-body-lg text-[#94A3B8]">
            Paste your notes, upload screenshots, or record — AI will extract key business intelligence.
          </p>
        </div>
      </motion.div>

      {/* ========== MAIN CONTENT ========== */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* ===== LEFT COLUMN (65%) ===== */}
        <motion.div variants={fadeUp15} className="lg:w-[65%] flex flex-col gap-4">
          {/* -- Input Tabs -- */}
          <div className="flex items-center gap-2 p-1 bg-[#1A2235] rounded-xl border border-[#1E293B] w-fit">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={cn(
                    'relative flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'text-[#F1F5F9]'
                      : 'text-[#64748B] hover:text-[#94A3B8]'
                  )}
                >
                  {isActive && (
                    <motion.div
                      layoutId="inputTabIndicator"
                      className="absolute inset-0 bg-[#1A2235] border border-[#334155] rounded-lg"
                      transition={{ duration: 0.2, ease: [0.45, 0.05, 0.55, 0.95] as [number, number, number, number] }}
                    />
                  )}
                  <Icon className="w-4 h-4 relative z-10" />
                  <span className="relative z-10">{tab.label}</span>
                </button>
              )
            })}
          </div>

          {/* -- Tab Content -- */}
          <div className="glass-card rounded-[16px] border border-[#1E293B] overflow-hidden">
            <AnimatePresence mode="wait">
              {/* --- Text Input Tab --- */}
              {activeTab === 'text' && (
                <motion.div
                  key="text"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  transition={{ duration: 0.3, ease: easeOutExpo }}
                  className="p-4"
                >
                  <Textarea
                    value={textContent}
                    onChange={(e) => setTextContent(e.target.value)}
                    placeholder={`Paste your voice transcript, meeting notes, or any raw text from your visit here...\n\nExample: "Met with Zhang from Acme Corp. He said their current reporting system is too slow, takes 3 days to generate month-end reports. IT budget this year is around 500K. Decision maker is their CTO Li Wei. They're also looking at CompetitorX. Hope to go live by Q3."`}
                    className="min-h-[360px] bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50 rounded-[10px] resize-none focus:border-[#6366F1] focus:ring-[3px] focus:ring-[rgba(99,102,241,0.15)] text-base leading-relaxed"
                  />
                  <div className="flex items-center justify-between mt-3">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-[#64748B] hover:text-[#94A3B8]"
                        onClick={() => fileInputRef.current?.click()}
                      >
                        <Paperclip className="w-4 h-4 mr-1.5" />
                        Attach Files
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-[#64748B] hover:text-[#94A3B8]"
                        onClick={() => setTextContent('')}
                      >
                        <X className="w-4 h-4 mr-1.5" />
                        Clear
                      </Button>
                      <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        className="hidden"
                        onChange={(e) => handleFileSelect(e.target.files)}
                      />
                    </div>
                    <span className="text-body-sm text-[#64748B]">
                      {textContent.length.toLocaleString()} characters
                    </span>
                  </div>
                </motion.div>
              )}

              {/* --- OCR Upload Tab --- */}
              {activeTab === 'ocr' && (
                <motion.div
                  key="ocr"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  transition={{ duration: 0.3, ease: easeOutExpo }}
                  className="p-4"
                >
                  {/* Drop Zone */}
                  <div
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onClick={() => ocrInputRef.current?.click()}
                    className={cn(
                      'min-h-[360px] rounded-[16px] border-2 border-dashed flex flex-col items-center justify-center cursor-pointer transition-all duration-200 relative overflow-hidden',
                      isDragging
                        ? 'border-[#6366F1] bg-[rgba(99,102,241,0.05)]'
                        : 'border-[#1E293B] bg-[#0D1321] hover:border-[#334155]'
                    )}
                    style={{
                      backgroundImage: !isDragging
                        ? 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(255,255,255,0.01) 10px, rgba(255,255,255,0.01) 20px)'
                        : undefined,
                    }}
                  >
                    {isDragging && (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: [0.3, 0.6, 0.3] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                        className="absolute inset-0 border-2 border-[#6366F1] rounded-[16px]"
                      />
                    )}
                    <Upload
                      className={cn(
                        'w-12 h-12 mb-4 transition-colors',
                        isDragging ? 'text-[#6366F1]' : 'text-[#64748B]'
                      )}
                    />
                    <p className="text-heading-sm text-[#94A3B8] mb-2">
                      Drop WeChat screenshots here
                    </p>
                    <p className="text-body-md text-[#64748B] mb-2">or click to browse</p>
                    <p className="text-body-sm text-[#64748B]">
                      PNG, JPG, WEBP · Max 10MB each
                    </p>
                    <input
                      ref={ocrInputRef}
                      type="file"
                      multiple
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => handleFileSelect(e.target.files)}
                    />
                  </div>

                  {/* Uploaded Files List */}
                  <AnimatePresence>
                    {uploadedFiles.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-4 space-y-2"
                      >
                        {uploadedFiles.map((file) => (
                          <motion.div
                            key={file.id}
                            initial={{ opacity: 0, y: -10, scale: 0.9 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: -10 }}
                            transition={{ duration: 0.4, ease: easeOutExpo }}
                            className="flex items-center gap-3 p-3 bg-[#0D1321] rounded-xl border border-[#1E293B]"
                          >
                            {file.preview ? (
                              <img
                                src={file.preview}
                                alt={file.name}
                                className="w-12 h-12 rounded-xl object-cover"
                              />
                            ) : (
                              <div className="w-12 h-12 rounded-xl bg-[#1A2235] flex items-center justify-center">
                                <Image className="w-5 h-5 text-[#64748B]" />
                              </div>
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="text-body-sm text-[#F1F5F9] truncate">{file.name}</p>
                              <p className="text-body-sm text-[#64748B]">{file.size}</p>
                            </div>
                            <Badge
                              variant="outline"
                              className={cn(
                                'text-xs',
                                file.status === 'extracted' &&
                                  'border-[#10B981] text-[#10B981] bg-[rgba(16,185,129,0.1)]',
                                file.status === 'processing' &&
                                  'border-[#6366F1] text-[#6366F1] bg-[rgba(99,102,241,0.1)]',
                                file.status === 'failed' &&
                                  'border-[#EF4444] text-[#EF4444] bg-[rgba(239,68,68,0.1)]'
                              )}
                            >
                              {file.status === 'processing' && (
                                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                              )}
                              {file.status === 'extracted'
                                ? 'Extracted'
                                : file.status === 'processing'
                                  ? 'Processing...'
                                  : 'Failed'}
                            </Badge>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                removeFile(file.id)
                              }}
                              className="p-1.5 rounded-lg text-[#64748B] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.1)] transition-colors"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </motion.div>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              )}

              {/* --- Voice Transcript Tab --- */}
              {activeTab === 'voice' && (
                <motion.div
                  key="voice"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  transition={{ duration: 0.3, ease: easeOutExpo }}
                  className="p-4"
                >
                  {/* Recording Bar */}
                  <div className="flex items-center gap-4 mb-4 p-4 bg-[#0D1321] rounded-xl border border-[#1E293B]">
                    {/* Record Button */}
                    <button
                      onClick={() => {
                        if (isRecording) {
                          setIsRecording(false)
                        } else {
                          setIsRecording(true)
                          setRecordTime(0)
                        }
                      }}
                      className="relative"
                    >
                      {isRecording && (
                        <motion.div
                          initial={{ scale: 1, opacity: 0.5 }}
                          animate={{ scale: 1.5, opacity: 0 }}
                          transition={{ duration: 1.5, repeat: Infinity }}
                          className="absolute inset-0 rounded-full bg-[#EF4444]"
                        />
                      )}
                      <div
                        className={cn(
                          'w-16 h-16 rounded-full flex items-center justify-center transition-colors relative z-10',
                          isRecording
                            ? 'bg-[#EF4444]'
                            : 'bg-[#6366F1] hover:bg-[#818CF8]'
                        )}
                      >
                        {isRecording ? (
                          <StopCircle className="w-7 h-7 text-white" />
                        ) : (
                          <Mic className="w-7 h-7 text-white" />
                        )}
                      </div>
                    </button>

                    {/* Waveform Visualization */}
                    <div className="flex-1 flex items-center gap-1 h-10">
                      {Array.from({ length: 40 }).map((_, i) => (
                        <motion.div
                          key={i}
                          className="flex-1 bg-[#6366F1] rounded-full"
                          animate={
                            isRecording
                              ? {
                                  height: [
                                    4 + Math.random() * 32,
                                    4 + Math.random() * 32,
                                  ],
                                }
                              : { height: 4 }
                          }
                          transition={{
                            duration: 0.3,
                            repeat: isRecording ? Infinity : 0,
                            repeatType: 'reverse',
                            delay: i * 0.02,
                          }}
                          style={{ width: 2, borderRadius: 999 }}
                        />
                      ))}
                    </div>

                    {/* Timer */}
                    <div className="text-mono-md text-[#F1F5F9] min-w-[70px] text-right">
                      {format(new Date(0, 0, 0, 0, 0, recordTime), 'HH:mm:ss')}
                    </div>
                  </div>

                  {/* Transcribe Button */}
                  {!isRecording && recordTime > 0 && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mb-4"
                    >
                      <Button
                        className="bg-gradient-to-r from-[#6366F1] to-[#8B5CF6] hover:from-[#818CF8] hover:to-[#A78BFA] text-white"
                        onClick={() => {
                          setVoiceText(
                            '[Voice transcript would appear here after AI processing...]'
                          )
                        }}
                      >
                        <Sparkles className="w-4 h-4 mr-2" />
                        Transcribe with AI
                      </Button>
                    </motion.div>
                  )}

                  {/* Voice Textarea */}
                  <Textarea
                    value={voiceText}
                    onChange={(e) => setVoiceText(e.target.value)}
                    placeholder="Paste or transcribe your voice recording here..."
                    className="min-h-[280px] bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50 rounded-[10px] resize-none focus:border-[#6366F1] focus:ring-[3px] focus:ring-[rgba(99,102,241,0.15)] text-base leading-relaxed"
                  />
                  <div className="flex items-center justify-between mt-3">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-[#64748B] hover:text-[#94A3B8]"
                        onClick={() => setVoiceText('')}
                      >
                        <X className="w-4 h-4 mr-1.5" />
                        Clear
                      </Button>
                    </div>
                    <span className="text-body-sm text-[#64748B]">
                      {voiceText.length.toLocaleString()} characters
                    </span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* ===== RIGHT COLUMN (35%) ===== */}
        <motion.div
          variants={slideFromRight}
          className="lg:w-[35%] flex flex-col gap-5"
        >
          {/* -- Customer Selector -- */}
          <div className="glass-card rounded-[16px] border border-[#1E293B] p-5">
            <Label className="text-label text-[#64748B] block mb-3">Customer</Label>

            {/* Customer Dropdown Trigger */}
            <div className="relative">
              <button
                onClick={() => setCustomerDropdownOpen(!customerDropdownOpen)}
                className={cn(
                  'w-full flex items-center justify-between p-3 rounded-xl border transition-all duration-200',
                  customerDropdownOpen
                    ? 'bg-[#1A2235] border-[#334155]'
                    : 'bg-[#1A2235] border-[#1E293B] hover:border-[#334155]'
                )}
              >
                {selectedCustomer ? (
                  <div className="flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold text-white"
                      style={{
                        background: `linear-gradient(135deg, #6366F1, #8B5CF6)`,
                      }}
                    >
                      {selectedCustomer.name.charAt(0)}
                    </div>
                    <div className="text-left">
                      <p className="text-body-md font-semibold text-[#F1F5F9]">
                        {selectedCustomer.name}
                      </p>
                      <Badge
                        variant="outline"
                        className="text-[10px] border-[#334155] text-[#94A3B8]"
                      >
                        {selectedCustomer.industry}
                      </Badge>
                    </div>
                  </div>
                ) : (
                  <span className="text-body-md text-[#64748B]">
                    Search or select customer...
                  </span>
                )}
                <ChevronDown
                  className={cn(
                    'w-4 h-4 text-[#64748B] transition-transform',
                    customerDropdownOpen && 'rotate-180'
                  )}
                />
              </button>

              {/* Dropdown Panel */}
              <AnimatePresence>
                {customerDropdownOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.2, ease: easeOutExpo }}
                    className="absolute top-full left-0 right-0 mt-2 bg-[#1A2235] border border-[#1E293B] rounded-xl shadow-xl z-50 overflow-hidden"
                  >
                    {/* Search */}
                    <div className="p-3 border-b border-[#1E293B]">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
                        <input
                          type="text"
                          value={customerSearch}
                          onChange={(e) => setCustomerSearch(e.target.value)}
                          placeholder="Search customers..."
                          className="w-full h-9 pl-9 pr-3 rounded-lg bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] placeholder:text-[#64748B] focus:outline-none focus:border-[#334155]"
                        />
                      </div>
                    </div>

                    {/* Customer List */}
                    <div className="max-h-[220px] overflow-y-auto">
                      {filteredCustomers.map((customer) => (
                        <button
                          key={customer.id}
                          onClick={() => {
                            setSelectedCustomer(customer)
                            setCustomerDropdownOpen(false)
                            setShowNewCustomer(false)
                          }}
                          className={cn(
                            'w-full flex items-center gap-3 px-3 py-2.5 hover:bg-[rgba(255,255,255,0.03)] transition-colors text-left',
                            selectedCustomer?.id === customer.id &&
                              'bg-[rgba(99,102,241,0.08)]'
                          )}
                        >
                          <div
                            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold text-white shrink-0"
                            style={{
                              background: `linear-gradient(135deg, #6366F1, #8B5CF6)`,
                            }}
                          >
                            {customer.name.charAt(0)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-body-md text-[#F1F5F9] truncate">
                              {customer.name}
                            </p>
                            <p className="text-body-sm text-[#64748B]">
                              {customer.lastVisitDate
                                ? `Last visit: ${customer.lastVisitDate}`
                                : 'No visits yet'}
                            </p>
                          </div>
                        </button>
                      ))}
                    </div>

                    {/* New Customer Option */}
                    <div className="p-3 border-t border-[#1E293B]">
                      <button
                        onClick={() => {
                          setShowNewCustomer(true)
                          setCustomerDropdownOpen(false)
                          setSelectedCustomer(null)
                        }}
                        className="w-full flex items-center gap-2 text-[#6366F1] hover:text-[#818CF8] transition-colors"
                      >
                        <Plus className="w-4 h-4" />
                        <span className="text-body-md font-medium">Add new customer...</span>
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* New Customer Form */}
            <AnimatePresence>
              {showNewCustomer && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.4, ease: easeOutExpo }}
                  className="overflow-hidden"
                >
                  <div className="mt-4 p-4 bg-[#0D1321] rounded-xl border border-[#1E293B] space-y-3">
                    <div>
                      <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">
                        Company Name *
                      </Label>
                      <Input
                        value={newCustomer.companyName}
                        onChange={(e) =>
                          setNewCustomer((p) => ({ ...p, companyName: e.target.value }))
                        }
                        placeholder="Enter company name"
                        className="bg-[#1A2235] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50 focus:border-[#6366F1]"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">
                          Industry
                        </Label>
                        <select
                          value={newCustomer.industry}
                          onChange={(e) =>
                            setNewCustomer((p) => ({ ...p, industry: e.target.value }))
                          }
                          className="w-full h-10 px-3 rounded-[10px] bg-[#1A2235] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1]"
                        >
                          {industryOptions.map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">
                          Company Size
                        </Label>
                        <select
                          value={newCustomer.companySize}
                          onChange={(e) =>
                            setNewCustomer((p) => ({ ...p, companySize: e.target.value }))
                          }
                          className="w-full h-10 px-3 rounded-[10px] bg-[#1A2235] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1]"
                        >
                          {companySizeOptions.map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">
                          Primary Contact
                        </Label>
                        <Input
                          value={newCustomer.contactName}
                          onChange={(e) =>
                            setNewCustomer((p) => ({ ...p, contactName: e.target.value }))
                          }
                          placeholder="Contact name"
                          className="bg-[#1A2235] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50 focus:border-[#6366F1]"
                        />
                      </div>
                      <div>
                        <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">
                          Contact Title
                        </Label>
                        <Input
                          value={newCustomer.contactTitle}
                          onChange={(e) =>
                            setNewCustomer((p) => ({ ...p, contactTitle: e.target.value }))
                          }
                          placeholder="e.g. CTO, VP Sales"
                          className="bg-[#1A2235] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50 focus:border-[#6366F1]"
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-2 pt-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setShowNewCustomer(false)
                          setSelectedCustomer(null)
                        }}
                        className="text-[#64748B] hover:text-[#94A3B8]"
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        onClick={handleAddNewCustomer}
                        disabled={!newCustomer.companyName.trim()}
                        className="bg-[#6366F1] hover:bg-[#818CF8] text-white"
                      >
                        Add Customer
                      </Button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* -- Visit Details -- */}
          <motion.div
            variants={staggerField}
            custom={0}
            initial="hidden"
            animate="visible"
            className="glass-card rounded-[16px] border border-[#1E293B] p-5 space-y-4"
          >
            <Label className="text-label text-[#64748B] block">Visit Details</Label>

            {/* Visit Date */}
            <motion.div variants={staggerField} custom={1}>
              <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Visit Date</Label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                <Input
                  type="date"
                  value={visitDate}
                  onChange={(e) => setVisitDate(e.target.value)}
                  className="pl-10 bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] focus:border-[#6366F1]"
                />
              </div>
            </motion.div>

            {/* Visit Purpose */}
            <motion.div variants={staggerField} custom={2}>
              <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">Visit Purpose</Label>
              <div className="relative">
                <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                <select
                  value={visitPurpose}
                  onChange={(e) => setVisitPurpose(e.target.value)}
                  className="w-full h-10 pl-10 pr-8 rounded-[10px] bg-[#0D1321] border border-[#1E293B] text-sm text-[#F1F5F9] focus:outline-none focus:border-[#6366F1] appearance-none"
                >
                  {purposeOptions.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
              </div>
            </motion.div>

            {/* Additional Notes */}
            <motion.div variants={staggerField} custom={3}>
              <Label className="text-body-sm text-[#94A3B8] mb-1.5 block">
                Additional Notes
              </Label>
              <div className="relative">
                <FileText className="absolute left-3 top-3 w-4 h-4 text-[#64748B] pointer-events-none" />
                <Textarea
                  value={visitNotes}
                  onChange={(e) => setVisitNotes(e.target.value)}
                  placeholder="Any additional context..."
                  rows={3}
                  className="pl-10 bg-[#0D1321] border-[#1E293B] text-[#F1F5F9] placeholder:text-[#64748B]/50 rounded-[10px] resize-none focus:border-[#6366F1] focus:ring-[3px] focus:ring-[rgba(99,102,241,0.15)]"
                />
              </div>
            </motion.div>
          </motion.div>
        </motion.div>
      </div>

      {/* ========== BOTTOM ACTION BAR ========== */}
      <motion.div
        initial={{ y: 100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.4, ease: easeOutExpo, delay: 0.6 }}
        className="fixed bottom-0 right-0 left-0 lg:left-[260px] bg-[#111827]/95 backdrop-blur-md border-t border-[#1E293B] px-6 py-4 z-40"
      >
        <div className="flex items-center justify-between max-w-[1200px] mx-auto">
          <Button
            variant="ghost"
            onClick={() => navigate('/')}
            className="text-[#94A3B8] hover:text-[#F1F5F9]"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>

          <motion.button
            whileHover={{ scale: hasContent ? 1.03 : 1 }}
            whileTap={{ scale: hasContent ? 0.97 : 1 }}
            disabled={!hasContent}
            onClick={() => navigate('/processing')}
            className={cn(
              'relative flex items-center gap-2 h-12 px-8 rounded-[10px] text-base font-semibold transition-all duration-200 overflow-hidden',
              hasContent
                ? 'text-white cursor-pointer'
                : 'bg-[#1A2235] text-[#64748B] cursor-not-allowed opacity-40'
            )}
            style={
              hasContent
                ? {
                    background: 'linear-gradient(135deg, #6366F1, #8B5CF6)',
                    boxShadow: '0 0 30px rgba(99,102,241,0.3)',
                  }
                : undefined
            }
          >
            {/* Glow pulse animation */}
            {hasContent && (
              <motion.div
                animate={{
                  boxShadow: [
                    '0 0 30px rgba(99,102,241,0.3)',
                    '0 0 40px rgba(99,102,241,0.5)',
                    '0 0 30px rgba(99,102,241,0.3)',
                  ],
                }}
                transition={{ duration: 3, repeat: Infinity }}
                className="absolute inset-0 rounded-[10px]"
              />
            )}
            <Sparkles className="w-5 h-5 relative z-10" />
            <span className="relative z-10">Start AI Processing</span>
            <ArrowLeft className="w-4 h-4 relative z-10 rotate-180" />
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
  )
}
