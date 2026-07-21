import { useState } from 'react'
import { KeyRound, LoaderCircle, ShieldCheck } from 'lucide-react'
import { activateCloud, getErrorMessage, loginCloud } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function CloudLogin({ initialMessage = '', onSuccess }: { initialMessage?: string; onSuccess: () => void | Promise<void> }) {
  const [mode, setMode] = useState<'login' | 'activate'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [totp, setTotp] = useState('')
  const [message, setMessage] = useState(initialMessage)
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setLoading(true)
    setMessage('')
    try {
      if (mode === 'login') await loginCloud(email.trim(), password, totp.trim())
      else await activateCloud(inviteCode.trim(), displayName.trim(), password)
      await onSuccess()
    } catch (error) {
      setMessage(getErrorMessage(error, '登录未完成，请检查输入'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0B0F1A] px-5 text-[#F8FAFC]">
      <section className="w-full max-w-[420px]">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-lg bg-[#6366F1]"><ShieldCheck className="h-6 w-6" /></div>
          <div><h1 className="text-xl font-semibold">SZYG</h1><p className="mt-1 text-sm text-[#94A3B8]">登录后继续使用智能服务</p></div>
        </div>
        <div className="rounded-lg border border-[#253047] bg-[#111827] p-6 shadow-2xl">
          <div className="mb-6 grid grid-cols-2 rounded-md bg-[#0B1220] p-1 text-sm">
            <button className={`rounded px-3 py-2 ${mode === 'login' ? 'bg-[#27324A] text-white' : 'text-[#94A3B8]'}`} onClick={() => setMode('login')}>登录</button>
            <button className={`rounded px-3 py-2 ${mode === 'activate' ? 'bg-[#27324A] text-white' : 'text-[#94A3B8]'}`} onClick={() => setMode('activate')}>首次激活</button>
          </div>
          <div className="space-y-4">
            {mode === 'activate' && <><Input value={inviteCode} onChange={(e) => setInviteCode(e.target.value)} placeholder="邀请码" className="border-[#334155] bg-[#0D1321]" /><Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="你的称呼" className="border-[#334155] bg-[#0D1321]" /></>}
            {mode === 'login' && <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="邮箱" type="email" className="border-[#334155] bg-[#0D1321]" />}
            <Input value={password} onChange={(e) => setPassword(e.target.value)} placeholder={mode === 'activate' ? '设置密码，至少 10 位' : '密码'} type="password" className="border-[#334155] bg-[#0D1321]" />
            {mode === 'login' && <Input value={totp} onChange={(e) => setTotp(e.target.value)} placeholder="动态验证码（如已启用）" className="border-[#334155] bg-[#0D1321]" />}
            {message && <p className="rounded-md border border-[#7F1D1D] bg-[#450A0A]/30 px-3 py-2 text-sm text-[#FCA5A5]">{message}</p>}
            <Button className="w-full bg-[#6366F1] hover:bg-[#818CF8]" disabled={loading || !password || (mode === 'login' ? !email : !inviteCode || !displayName)} onClick={submit}>
              {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}{mode === 'login' ? '登录' : '激活并登录'}
            </Button>
          </div>
        </div>
        <p className="mt-5 text-center text-xs text-[#64748B]">本机素材和平台登录信息不会上传到云端</p>
      </section>
    </main>
  )
}
