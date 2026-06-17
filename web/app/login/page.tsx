'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { User, Lock, ArrowRight, Sparkles } from 'lucide-react'
import api from '@/lib/api'
import { useAuth, useBrand } from '@/stores'

export default function LoginPage() {
  const router = useRouter()
  const { token: savedToken, login: doLogin } = useAuth()
  const { brand } = useBrand()
  const [form, setForm] = useState({ username: '', password: '', remember: true })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (savedToken) router.push('/dashboard')

    const saved = localStorage.getItem('saved_credentials')
    if (saved) {
      try {
        const creds = JSON.parse(saved)
        setForm(f => ({ ...f, username: creds.username, password: creds.password, remember: true }))
      } catch {}
    }
  }, [router, savedToken])

  async function handleLogin() {
    if (!form.username || !form.password) {
      setError('请填写用户名和密码')
      return
    }
    setLoading(true)
    setError('')
    try {
      const { data } = await api.post('/api/auth/login', {
        username: form.username,
        password: form.password,
      })
      doLogin(data.access_token, data.user)
      if (form.remember) {
        localStorage.setItem('saved_credentials', JSON.stringify({ username: form.username, password: form.password }))
      } else {
        localStorage.removeItem('saved_credentials')
      }
      router.push('/dashboard')
    } catch (e: any) {
      setError(e.response?.status === 401 ? '用户名或密码错误' : '服务器连接失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-950" />
      <div className="absolute inset-0 opacity-30">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/20 rounded-full blur-[120px] animate-pulse-glow" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-purple-500/20 rounded-full blur-[100px] animate-pulse-glow" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-500/10 rounded-full blur-[150px]" />
      </div>

      {/* Grid pattern */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
        backgroundSize: '60px 60px'
      }} />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
        className="relative z-10 w-full max-w-md mx-4"
      >
        <div className="glass-card p-8 md:p-10">
          <div className="text-center mb-8">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
              className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-accent to-purple-500 flex items-center justify-center shadow-lg shadow-accent/30"
            >
              <Sparkles className="w-8 h-8 text-white" />
            </motion.div>
            <h1 className="text-2xl font-bold text-white mb-2">{brand.name || 'szyg'}</h1>
            <p className="text-white/40 text-sm">智能矩阵运营系统</p>
          </div>

          <div className="space-y-4">
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
              <input
                type="text"
                placeholder="用户名"
                value={form.username}
                onChange={(e) => setForm(f => ({ ...f, username: e.target.value }))}
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/50 transition-all"
              />
            </div>

            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
              <input
                type="password"
                placeholder="密码"
                value={form.password}
                onChange={(e) => setForm(f => ({ ...f, password: e.target.value }))}
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/50 transition-all"
              />
            </div>

            {error && (
              <motion.p
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="text-red-400 text-sm text-center"
              >
                {error}
              </motion.p>
            )}

            <label className="flex items-center gap-2 text-sm text-white/40 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.remember}
                onChange={(e) => setForm(f => ({ ...f, remember: e.target.checked }))}
                className="rounded border-white/20 bg-white/5 text-accent focus:ring-accent/50"
              />
              记住密码
            </label>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleLogin}
              disabled={loading}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-accent to-purple-500 text-white font-medium flex items-center justify-center gap-2 shadow-lg shadow-accent/25 hover:shadow-accent/40 transition-shadow disabled:opacity-50"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  登 录
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </motion.button>
          </div>

          <div className="mt-6 text-center text-xs text-white/20">
            {brand.copyright || '© 2024 szyg'}
          </div>
        </div>
      </motion.div>
    </div>
  )
}
