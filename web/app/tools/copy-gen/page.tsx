'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Pencil, Sparkles, Copy, Check, RefreshCw, BookOpen,
  MessageCircle, Lightbulb, ChevronDown, Wand2,
} from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

// ── Types ───────────────────────────────────────────────

interface ScriptTemplate {
  id: string
  industry: string
  scenario: string
  title: string
  persona: string
  trigger_keywords: string[]
  template: Record<string, string>
  tips: string[]
}

interface GeneratedScript {
  template: ScriptTemplate
  generated: Record<string, string>
  tips: string[]
  persona: string
}

// ── Config ──────────────────────────────────────────────

const industries = ['零售', 'B2B', '本地服务', '教育', '健康']
const industryScenarios: Record<string, string[]> = {
  '零售': ['价格咨询', '质量疑虑'],
  'B2B': ['合作咨询'],
  '本地服务': ['服务预约'],
  '教育': ['课程咨询'],
  '健康': ['健康咨询'],
}

// ── Page ────────────────────────────────────────────────

export default function CopyGenPage() {
  const [templates, setTemplates] = useState<ScriptTemplate[]>([])
  const [industry, setIndustry] = useState('零售')
  const [scenario, setScenario] = useState('')
  const [productInfo, setProductInfo] = useState('')
  const [customerContext, setCustomerContext] = useState('')
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<GeneratedScript | null>(null)
  const [copiedKey, setCopiedKey] = useState('')

  useEffect(() => {
    api.get('/api/scripts').then(({ data }) => {
      setTemplates(data.templates || [])
    }).catch(() => {})
  }, [])

  const filteredScenarios = industryScenarios[industry] || []

  const handleGenerate = async () => {
    setGenerating(true)
    setResult(null)
    try {
      const { data } = await api.post('/api/scripts/generate', {
        industry,
        scenario: scenario || filteredScenarios[0],
        product_info: productInfo,
        customer_context: customerContext,
      })
      setResult(data)
    } catch (e: any) {
      console.error('Generate failed', e)
    } finally {
      setGenerating(false)
    }
  }

  const handleCopy = async (text: string, key: string) => {
    await navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(''), 2000)
  }

  // Get template previews for current industry
  const industryTemplates = templates.filter(t => t.industry === industry)

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Pencil className="w-5 h-5 text-amber-400" />
            文案生成
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
              销冠话术库
            </span>
          </h1>
          <p className="text-sm text-white/40 mt-1">对标销氪AIsales / 探迹销售Agent — 6大行业话术模板，一键生成个性化销售话术</p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left: Config Panel */}
          <div className="lg:col-span-1 space-y-4">
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-white font-medium flex items-center gap-2">
                <Wand2 className="w-4 h-4 text-accent" /> 话术配置
              </h3>

              <div>
                <label className="text-xs text-white/40 mb-2 block">行业</label>
                <div className="flex flex-wrap gap-2">
                  {industries.map(ind => (
                    <button
                      key={ind}
                      onClick={() => { setIndustry(ind); setScenario('') }}
                      className={cn(
                        'px-3 py-1.5 rounded-lg text-xs border transition-all',
                        industry === ind
                          ? 'bg-accent/20 border-accent/30 text-accent'
                          : 'bg-white/[0.03] border-white/10 text-white/50 hover:text-white/70'
                      )}
                    >
                      {ind}
                    </button>
                  ))}
                </div>
              </div>

              {filteredScenarios.length > 0 && (
                <div>
                  <label className="text-xs text-white/40 mb-2 block">场景</label>
                  <div className="flex flex-wrap gap-2">
                    {filteredScenarios.map(sc => (
                      <button
                        key={sc}
                        onClick={() => setScenario(sc)}
                        className={cn(
                          'px-3 py-1.5 rounded-lg text-xs border transition-all',
                          scenario === sc
                            ? 'bg-amber-500/20 border-amber-500/30 text-amber-400'
                            : 'bg-white/[0.03] border-white/10 text-white/50 hover:text-white/70'
                        )}
                      >
                        {sc}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <label className="text-xs text-white/40 mb-2 block">产品/服务信息</label>
                <textarea
                  value={productInfo}
                  onChange={e => setProductInfo(e.target.value)}
                  placeholder="简要描述产品核心卖点、目标客户..."
                  className="w-full h-20 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/50 resize-none"
                />
              </div>

              <button
                onClick={handleGenerate}
                disabled={generating || !productInfo.trim()}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white font-medium flex items-center justify-center gap-2 hover:shadow-lg hover:shadow-amber-500/25 transition-all disabled:opacity-30"
              >
                {generating ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                生成话术
              </button>
            </div>

            {/* Template Library */}
            <div className="glass-card p-5 space-y-3">
              <h3 className="text-white font-medium flex items-center gap-2 text-sm">
                <BookOpen className="w-4 h-4 text-white/40" /> 话术模板库 ({industryTemplates.length})
              </h3>
              <div className="space-y-2">
                {industryTemplates.map(t => (
                  <div
                    key={t.id}
                    onClick={() => setScenario(t.scenario)}
                    className="p-3 rounded-xl bg-white/[0.02] border border-white/5 hover:border-amber-500/20 cursor-pointer transition-all"
                  >
                    <div className="text-white/70 text-sm">{t.title}</div>
                    <div className="text-white/30 text-xs mt-1">
                      {t.persona} · {t.trigger_keywords.slice(0, 3).join('、')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right: Results */}
          <div className="lg:col-span-2">
            <AnimatePresence mode="wait">
              {!result && !generating && (
                <motion.div
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="glass-card p-12 text-center min-h-[400px] flex flex-col items-center justify-center"
                >
                  <MessageCircle className="w-16 h-16 text-white/5 mx-auto mb-4" />
                  <h3 className="text-white/40 text-lg mb-2">选择一个行业，输入产品信息</h3>
                  <p className="text-white/20 text-sm max-w-md">
                    AI 将根据行业最佳话术模板，自动生成个性化的销售话术，包含开场白、价值陈述、异议处理和成交引导。
                  </p>
                </motion.div>
              )}

              {generating && (
                <motion.div
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="glass-card p-12 text-center min-h-[400px] flex items-center justify-center"
                >
                  <div className="space-y-4">
                    <RefreshCw className="w-8 h-8 text-accent animate-spin mx-auto" />
                    <p className="text-white/40">AI 正在生成话术...</p>
                  </div>
                </motion.div>
              )}

              {result && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  className="space-y-4"
                >
                  {/* Persona & Tips */}
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="px-3 py-1 rounded-lg bg-accent/10 border border-accent/20 text-accent text-sm">
                      🎭 {result.persona}
                    </span>
                    {result.tips.map((tip, i) => (
                      <span key={i} className="text-xs text-white/40 flex items-center gap-1">
                        <Lightbulb className="w-3 h-3 text-amber-400" /> {tip}
                      </span>
                    ))}
                  </div>

                  {/* Generated Script Cards */}
                  {Object.entries(result.generated).map(([key, text]) => (
                    <motion.div
                      key={key}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: Object.keys(result.generated).indexOf(key) * 0.1 }}
                      className="glass-card p-5 group"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-white/30 uppercase tracking-wider">{key}</span>
                        <button
                          onClick={() => handleCopy(text, key)}
                          className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg bg-white/[0.05] text-white/40 hover:text-white transition-all"
                        >
                          {copiedKey === key ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                      <p className="text-white/80 text-sm leading-relaxed whitespace-pre-wrap">{text}</p>
                    </motion.div>
                  ))}

                  {/* Copy All */}
                  <button
                    onClick={() => {
                      const full = Object.values(result.generated).join('\n\n')
                      navigator.clipboard.writeText(full)
                    }}
                    className="w-full py-3 rounded-xl bg-white/[0.03] border border-white/10 text-white/60 text-sm hover:text-white hover:bg-white/[0.06] transition-all flex items-center justify-center gap-2"
                  >
                    <Copy className="w-4 h-4" /> 一键复制全部话术
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
