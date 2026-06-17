'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Film, Play, Wand2, Mic, Video, CheckCircle } from 'lucide-react'
import AppLayout from '@/components/AppLayout'

export default function VideoGenPage() {
  const [theme, setTheme] = useState('')
  const [duration, setDuration] = useState(60)
  const [step, setStep] = useState(0)
  const [output, setOutput] = useState('')
  const [processing, setProcessing] = useState(false)

  const steps = [
    { icon: <Wand2 className="w-5 h-5" />, title: '脚本生成', desc: 'AI 生成视频脚本' },
    { icon: <Mic className="w-5 h-5" />, title: '语音合成', desc: '文本转语音' },
    { icon: <Video className="w-5 h-5" />, title: '视频合成', desc: '生成最终视频' },
    { icon: <CheckCircle className="w-5 h-5" />, title: '完成', desc: '下载视频' },
  ]

  function startPipeline() {
    if (!theme.trim()) return
    setProcessing(true)
    setOutput('正在处理...')
    setStep(0)

    let currentStep = 0
    const interval = setInterval(() => {
      currentStep++
      setStep(currentStep)
      if (currentStep >= 3) {
        clearInterval(interval)
        setProcessing(false)
        setOutput('视频创作完成！')
      }
    }, 1500)
  }

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto p-4 md:p-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
          <h2 className="text-2xl font-bold text-white mb-2">🎬 AI 视频创作</h2>
          <p className="text-white/40 text-sm">LLM脚本 + 语音合成 + 视频合成 — 全流程视频制作</p>
        </motion.div>

        {/* Steps */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="mb-8">
          <div className="flex items-center justify-between relative">
            <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-white/5 -translate-y-1/2" />
            {steps.map((s, i) => (
              <div key={i} className="relative z-10 flex flex-col items-center">
                <motion.div
                  animate={{
                    backgroundColor: i <= step ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.03)',
                    borderColor: i <= step ? 'rgba(99,102,241,0.5)' : 'rgba(255,255,255,0.08)',
                  }}
                  className="w-12 h-12 rounded-2xl border flex items-center justify-center mb-2"
                >
                  <span className={i <= step ? 'text-accent' : 'text-white/20'}>{s.icon}</span>
                </motion.div>
                <span className={`text-xs font-medium ${i <= step ? 'text-white' : 'text-white/20'}`}>{s.title}</span>
                <span className="text-[10px] text-white/20">{s.desc}</span>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <div className="glass-card p-6">
            <div className="flex flex-wrap items-end gap-4 mb-6">
              <div className="flex-1 min-w-[200px]">
                <label className="text-xs text-white/30 mb-1.5 block">视频主题</label>
                <input
                  type="text"
                  value={theme}
                  onChange={(e) => setTheme(e.target.value)}
                  placeholder="输入视频主题..."
                  className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/50"
                />
              </div>
              <div>
                <label className="text-xs text-white/30 mb-1.5 block">时长(秒)</label>
                <input
                  type="number"
                  min={10}
                  max={300}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="w-28 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50"
                />
              </div>
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={startPipeline}
                disabled={processing || !theme.trim()}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white text-sm font-medium flex items-center gap-2 shadow-lg shadow-accent/25 disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                {processing ? '创作中...' : '开始创作'}
              </motion.button>
            </div>

            {output && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`p-4 rounded-xl border text-sm flex items-center gap-2 ${output.includes('完成') ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' : 'bg-white/5 border-white/5 text-white/60'}`}
              >
                <Film className="w-4 h-4" />
                {output}
              </motion.div>
            )}
          </div>
        </motion.div>
      </div>
    </AppLayout>
  )
}
