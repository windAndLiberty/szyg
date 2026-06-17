'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Save, Palette, Type, Link, FileText } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'

const themes = [
  { label: '🔵 经典蓝', value: 'default' },
  { label: '🌙 暗夜黑', value: 'dark' },
  { label: '🌿 自然绿', value: 'green' },
  { label: '🌅 日落橙', value: 'sunset' },
  { label: '⭐ 星空紫', value: 'starry' },
]

export default function OEMPage() {
  const [form, setForm] = useState({
    name: 'szyg', logo_url: '', copyright: '© 2024', disclaimer: '', theme: 'default',
    support_url: '', support_name: '', website_url: '', website_name: '',
  })
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.get('/api/oem/config/default').then(({ data }) => {
      setForm(prev => ({ ...prev, ...data }))
      document.documentElement.setAttribute('data-theme', data.theme || 'default')
    }).catch(() => {})
  }, [])

  async function save() {
    try {
      await api.post('/api/oem/config', form)
      setSaved(true)
      document.documentElement.setAttribute('data-theme', form.theme)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      alert('保存失败')
    }
  }

  return (
    <AppLayout>
      <div className="max-w-2xl mx-auto p-4 md:p-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
          <h2 className="text-2xl font-bold text-white mb-2">🏷️ OEM 品牌管理</h2>
          <p className="text-white/40 text-sm">自定义系统品牌信息和主题风格</p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <div className="glass-card p-6 space-y-5">
            <div>
              <label className="text-xs text-white/30 mb-1.5 flex items-center gap-1.5">
                <Type className="w-3.5 h-3.5" /> 系统名称
              </label>
              <input
                value={form.name}
                onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))}
                className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50"
              />
            </div>

            <div>
              <label className="text-xs text-white/30 mb-1.5 flex items-center gap-1.5">
                <Link className="w-3.5 h-3.5" /> Logo URL
              </label>
              <input
                value={form.logo_url}
                onChange={(e) => setForm(f => ({ ...f, logo_url: e.target.value }))}
                placeholder="https://..."
                className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 placeholder:text-white/20"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-white/30 mb-1.5 block">支持链接名称</label>
                <input value={form.support_name} onChange={(e) => setForm(f => ({ ...f, support_name: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
              </div>
              <div>
                <label className="text-xs text-white/30 mb-1.5 block">支持链接 URL</label>
                <input value={form.support_url} onChange={(e) => setForm(f => ({ ...f, support_url: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
              </div>
              <div>
                <label className="text-xs text-white/30 mb-1.5 block">官网名称</label>
                <input value={form.website_name} onChange={(e) => setForm(f => ({ ...f, website_name: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
              </div>
              <div>
                <label className="text-xs text-white/30 mb-1.5 block">官网 URL</label>
                <input value={form.website_url} onChange={(e) => setForm(f => ({ ...f, website_url: e.target.value }))} className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
              </div>
            </div>

            <div>
              <label className="text-xs text-white/30 mb-1.5 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" /> 版权信息
              </label>
              <input
                value={form.copyright}
                onChange={(e) => setForm(f => ({ ...f, copyright: e.target.value }))}
                className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50"
              />
            </div>

            <div>
              <label className="text-xs text-white/30 mb-1.5 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" /> 免责声明
              </label>
              <textarea
                value={form.disclaimer}
                onChange={(e) => setForm(f => ({ ...f, disclaimer: e.target.value }))}
                rows={4}
                className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50 resize-none"
              />
            </div>

            <div>
              <label className="text-xs text-white/30 mb-2 flex items-center gap-1.5">
                <Palette className="w-3.5 h-3.5" /> 主题皮肤
              </label>
              <div className="flex flex-wrap gap-2">
                {themes.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => {
                      setForm(f => ({ ...f, theme: t.value }))
                      document.documentElement.setAttribute('data-theme', t.value)
                    }}
                    className={`px-4 py-2 rounded-xl text-sm transition-all ${form.theme === t.value ? 'bg-accent text-white shadow-lg shadow-accent/25' : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white'}`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={save}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white font-medium flex items-center justify-center gap-2 shadow-lg shadow-accent/25"
            >
              <Save className="w-4 h-4" />
              {saved ? '保存成功！' : '保存配置'}
            </motion.button>
          </div>
        </motion.div>
      </div>
    </AppLayout>
  )
}
