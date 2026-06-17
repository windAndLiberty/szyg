'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Users, Settings, Plus, Trash2 } from 'lucide-react'
import AppLayout from '@/components/AppLayout'
import api from '@/lib/api'

interface UserItem {
  id: string
  username: string
  role: string
  oem_id?: string
  is_active: boolean
}

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('users')
  const [users, setUsers] = useState<UserItem[]>([])
  const [configJson, setConfigJson] = useState('')
  const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user' })

  useEffect(() => {
    Promise.all([
      api.get('/api/auth/users').catch(() => ({ data: [] })),
      api.get('/api/config').catch(() => ({ data: {} })),
    ]).then(([uRes, cRes]) => {
      setUsers(uRes.data)
      setConfigJson(JSON.stringify(cRes.data, null, 2))
    })
  }, [])

  async function addUser() {
    if (!newUser.username || !newUser.password) return
    try {
      await api.post('/api/auth/users', null, { params: newUser })
      setNewUser({ username: '', password: '', role: 'user' })
      const { data } = await api.get('/api/auth/users')
      setUsers(data)
    } catch (e: any) {
      alert(e.response?.data?.detail || '创建失败')
    }
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
          <h2 className="text-2xl font-bold text-white">⚙️ 系统管理</h2>
          <p className="text-white/40 text-sm mt-1">用户管理和系统配置</p>
        </motion.div>

        <div className="glass-card overflow-hidden">
          <div className="flex border-b border-white/5">
            {[
              { key: 'users', label: '用户管理', icon: Users },
              { key: 'config', label: '系统配置', icon: Settings },
            ].map((t) => {
              const Icon = t.icon
              return (
                <button
                  key={t.key}
                  onClick={() => setActiveTab(t.key)}
                  className={`flex items-center gap-2 px-5 py-3 text-sm transition-all relative ${activeTab === t.key ? 'text-white' : 'text-white/30 hover:text-white/60'}`}
                >
                  <Icon className="w-4 h-4" />
                  {t.label}
                  {activeTab === t.key && <motion.div layoutId="admin-tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent" />}
                </button>
              )
            })}
          </div>

          <div className="p-5">
            {activeTab === 'users' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div className="overflow-x-auto mb-6">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/5 text-xs text-white/30">
                        <th className="text-left px-3 py-3 font-medium w-16">ID</th>
                        <th className="text-left px-3 py-3 font-medium">用户名</th>
                        <th className="text-left px-3 py-3 font-medium w-24">角色</th>
                        <th className="text-left px-3 py-3 font-medium">OEM ID</th>
                        <th className="text-left px-3 py-3 font-medium w-20">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((u) => (
                        <tr key={u.id} className="border-b border-white/[0.02] hover:bg-white/[0.02] transition-colors">
                          <td className="px-3 py-3 text-sm text-white/40">{u.id}</td>
                          <td className="px-3 py-3 text-sm text-white font-medium">{u.username}</td>
                          <td className="px-3 py-3">
                            <span className={`text-xs px-2 py-1 rounded-full ${u.role === 'admin' ? 'bg-red-500/10 text-red-400' : 'bg-white/5 text-white/40'}`}>
                              {u.role}
                            </span>
                          </td>
                          <td className="px-3 py-3 text-sm text-white/40">{u.oem_id || '—'}</td>
                          <td className="px-3 py-3">
                            <span className={`text-xs px-2 py-1 rounded-full ${u.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                              {u.is_active ? '启用' : '禁用'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {users.length === 0 && (
                    <div className="text-center py-8 text-white/20 text-sm">暂无用户数据</div>
                  )}
                </div>

                <div className="border-t border-white/5 pt-5">
                  <h4 className="text-sm font-medium text-white mb-3">添加用户</h4>
                  <div className="flex flex-wrap items-end gap-3">
                    <div>
                      <label className="text-xs text-white/30 mb-1 block">用户名</label>
                      <input value={newUser.username} onChange={(e) => setNewUser(u => ({ ...u, username: e.target.value }))} className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
                    </div>
                    <div>
                      <label className="text-xs text-white/30 mb-1 block">密码</label>
                      <input type="password" value={newUser.password} onChange={(e) => setNewUser(u => ({ ...u, password: e.target.value }))} className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50" />
                    </div>
                    <div>
                      <label className="text-xs text-white/30 mb-1 block">角色</label>
                      <select value={newUser.role} onChange={(e) => setNewUser(u => ({ ...u, role: e.target.value }))} className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-accent/50">
                        <option className="bg-[var(--header-bg)]" value="user">user</option>
                        <option className="bg-[var(--header-bg)]" value="admin">admin</option>
                      </select>
                    </div>
                    <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                      onClick={addUser}
                      className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent to-purple-500 text-white text-sm font-medium flex items-center gap-2 shadow-lg shadow-accent/25">
                      <Plus className="w-4 h-4" />添加用户
                    </motion.button>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === 'config' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <pre className="p-4 rounded-xl bg-white/5 border border-white/5 text-sm text-white/60 overflow-x-auto leading-relaxed">
                  {configJson}
                </pre>
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
