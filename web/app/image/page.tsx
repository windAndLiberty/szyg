'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Wand2, ImageIcon, Download, Loader2 } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'

export default function ImageGenPage() {
  const [prompt, setPrompt] = useState('')
  const [style, setStyle] = useState('')
  const [styles, setStyles] = useState<string[]>([])
  const [generating, setGenerating] = useState(false)
  const [imageUrl, setImageUrl] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/api/image/styles').then(({ data }) => setStyles(data.styles || [])).catch(() => {})
  }, [])

  async function generate() {
    if (!prompt.trim()) return
    setGenerating(true)
    setError('')
    try {
      const { data } = await api.post('/api/image/generate', { prompt, style })
      setImageUrl(data.image_url || data.image_paths?.[0] || '')
    } catch {
      setError('生成失败，请稍后重试')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto p-4 md:p-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
          <h2 className="text-2xl font-bold text-white mb-2">🎨 AI 图像生成</h2>
          <p className="text-white/40 text-sm">用文字描述你的想象，AI 为你绘制</p>
        </motion.div>

        <div className="grid lg:grid-cols-2 gap-6">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>
            <div className="glass-card p-6 space-y-4">
              <div>
                <label className="text-xs text-white/30 mb-1.5 block">提示词</label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={4}
                  placeholder="描述你想生成的图像，例如：一只穿着宇航服的猫在月球上弹吉他..."
                  className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/50 resize-none"
                />
              </div>
              <div>
                <label className="text-xs text-white/30 mb-1.5 block">风格</label>
                <select
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50"
                >
                  <option value="" className="bg-[var(--header-bg)]">默认风格</option>
                  {styles.map((s) => (
                    <option key={s} value={s} className="bg-[var(--header-bg)]">{s}</option>
                  ))}
                </select>
              </div>
              {error && <p className="text-red-400 text-sm">{error}</p>}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={generate}
                disabled={generating || !prompt.trim()}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white font-medium flex items-center justify-center gap-2 shadow-lg shadow-accent/25 disabled:opacity-50"
              >
                {generating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    生成中...
                  </>
                ) : (
                  <>
                    <Wand2 className="w-4 h-4" />
                    生成图像
                  </>
                )}
              </motion.button>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
            <div className="glass-card p-6 h-full min-h-[400px] flex items-center justify-center relative overflow-hidden">
              {imageUrl ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="relative w-full"
                >
                  <img src={imageUrl} alt="Generated" className="w-full rounded-xl border border-white/10" />
                  <a
                    href={imageUrl}
                    download
                    className="absolute bottom-3 right-3 p-2 rounded-xl bg-black/50 backdrop-blur text-white hover:bg-black/70 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                  </a>
                </motion.div>
              ) : (
                <div className="text-center text-white/20">
                  <ImageIcon className="w-16 h-16 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">生成的图像将显示在这里</p>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </AppLayout>
  )
}
