import { useState } from 'react'
import { ArrowLeft, KeyRound, LoaderCircle } from 'lucide-react'
import { changeCloudPassword, getErrorMessage, loginCloud, logoutCloud } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function CloudLogin({ initialMessage = '', onSuccess }: { initialMessage?: string; onSuccess: () => void | Promise<void> }) {
  const [mode, setMode] = useState<'login' | 'change-password'>('login')
  const [account, setAccount] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [message, setMessage] = useState(initialMessage === '请先登录' ? '' : initialMessage)
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (!account.trim() || !password || loading) return
    if (mode === 'change-password') {
      if (newPassword.length < 10) {
        setMessage('新密码至少需要 10 个字符')
        return
      }
      if (newPassword !== confirmPassword) {
        setMessage('两次输入的新密码不一致')
        return
      }
    }
    setLoading(true)
    setMessage('')
    let authenticatedForPasswordChange = false
    try {
      await loginCloud(account.trim(), password)
      if (mode === 'change-password') {
        authenticatedForPasswordChange = true
        await changeCloudPassword(password, newPassword)
      }
      await onSuccess()
    } catch (error) {
      if (authenticatedForPasswordChange) {
        try { await logoutCloud() } catch { /* Keep the original password-change error. */ }
      }
      setMessage(getErrorMessage(error, '登录未完成，请检查输入'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="relative flex min-h-screen items-center overflow-hidden bg-[#0B0F1A] px-5 py-10 text-[#F8FAFC] md:justify-end md:px-12 xl:px-24">
      <div aria-hidden="true" className="absolute inset-0 bg-[url('/login-digital-team.png')] bg-cover bg-[position:34%_center] md:bg-center" />
      <div aria-hidden="true" className="absolute inset-0 bg-black/25 md:bg-black/10" />
      <section className="relative z-10 mx-auto w-full max-w-[420px] md:mx-0">
        <div className="mb-7 flex items-center gap-3 drop-shadow-lg">
          <div className="grid h-11 w-11 place-items-center rounded-lg border border-white/15 bg-[#0B1220]/80 p-1"><img src="/logo1.png" alt="数字员工" className="h-full w-full object-contain" /></div>
          <div><h1 className="text-xl font-semibold">数字员工</h1><p className="mt-1 text-sm text-[#CBD5E1]">{mode === 'login' ? '登录后继续使用智能服务' : '验证当前密码后设置新密码'}</p></div>
        </div>
        <form className="rounded-lg border border-white/15 bg-[#0B1220]/90 p-6 shadow-2xl backdrop-blur-md" onSubmit={(event) => { event.preventDefault(); void submit() }}>
            <div className="space-y-4">
              <Input value={account} onChange={(e) => setAccount(e.target.value)} placeholder="账号" autoComplete="username" autoFocus className="border-[#475569] bg-[#0D1321]/90" />
              <Input value={password} onChange={(e) => setPassword(e.target.value)} placeholder={mode === 'login' ? '密码' : '当前密码'} type="password" autoComplete="current-password" className="border-[#475569] bg-[#0D1321]/90" />
              {mode === 'change-password' && <>
                <Input value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="新密码（至少 10 个字符）" type="password" autoComplete="new-password" className="border-[#475569] bg-[#0D1321]/90" />
                <Input value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="再次输入新密码" type="password" autoComplete="new-password" className="border-[#475569] bg-[#0D1321]/90" />
              </>}
              {message && <p className="rounded-md border border-[#7F1D1D] bg-[#450A0A]/40 px-3 py-2 text-sm text-[#FCA5A5]">{message}</p>}
              <Button type="submit" className="w-full bg-[#6366F1] hover:bg-[#818CF8]" disabled={loading || !password || !account.trim() || (mode === 'change-password' && (!newPassword || !confirmPassword))}>
                {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}{mode === 'login' ? '登录' : '确认修改'}
              </Button>
              {mode === 'login' ? (
                <button type="button" onClick={() => { setMode('change-password'); setMessage('') }} className="w-full text-sm text-[#A5B4FC] transition-colors hover:text-[#C7D2FE]">修改密码</button>
              ) : (
                <button type="button" onClick={() => { setMode('login'); setNewPassword(''); setConfirmPassword(''); setMessage('') }} className="flex w-full items-center justify-center gap-1.5 text-sm text-[#94A3B8] transition-colors hover:text-[#E2E8F0]"><ArrowLeft className="h-4 w-4" />返回登录</button>
              )}
            </div>
        </form>
        <p className="mt-5 text-center text-xs text-[#CBD5E1] drop-shadow-md">本机素材不会上传到云端</p>
      </section>
    </main>
  )
}
