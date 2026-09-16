import { useEffect, useState } from 'react'
import { ArrowLeft, KeyRound, LoaderCircle, MailCheck } from 'lucide-react'
import { changeCloudPassword, getErrorMessage, loginCloud, logoutCloud, registerCloud, requestRegistrationCode } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import { useI18n } from '@/lib/i18n'
import { product } from '@/lib/product'

export default function CloudLogin({ initialMessage = '', onSuccess }: { initialMessage?: string; onSuccess: () => void | Promise<void> }) {
  const { t } = useI18n()
  const [mode, setMode] = useState<'login' | 'register' | 'change-password'>('login')
  const [account, setAccount] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [verificationId, setVerificationId] = useState('')
  const [codeLoading, setCodeLoading] = useState(false)
  const [resendIn, setResendIn] = useState(0)
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [message, setMessage] = useState(initialMessage === '请先登录' ? '' : initialMessage)
  const [loading, setLoading] = useState(false)
  const codeSent = message.startsWith('验证码已发送')
  const isRegistering = product.allowSelfRegistration && mode === 'register'

  useEffect(() => {
    if (resendIn <= 0) return
    const timer = window.setInterval(() => setResendIn((value) => Math.max(0, value - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [resendIn])

  const sendRegistrationCode = async () => {
    if (!account.trim() || codeLoading || resendIn > 0) return
    setCodeLoading(true)
    setMessage('')
    try {
      const challenge = await requestRegistrationCode(account.trim())
      setVerificationId(challenge.verification_id)
      setResendIn(challenge.retry_after_seconds || 60)
      setMessage(`验证码已发送至 ${challenge.email}，10分钟内有效`)
    } catch (error) {
      setMessage(getErrorMessage(error, '验证码发送失败，请稍后再试'))
    } finally {
      setCodeLoading(false)
    }
  }

  const submit = async () => {
    if (!account.trim() || !password || loading) return
    if (isRegistering && !displayName.trim()) {
      setMessage('请输入你的称呼')
      return
    }
    if (isRegistering && password.length < 10) {
      setMessage('密码至少需要 10 个字符')
      return
    }
    if (isRegistering && (!verificationId || !/^\d{6}$/.test(verificationCode))) {
      setMessage('请先获取并填写6位邮箱验证码')
      return
    }
    if (isRegistering && !acceptedTerms) {
      setMessage('请先阅读并同意用户协议和隐私政策')
      return
    }
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
      if (isRegistering) {
        await registerCloud(account.trim(), displayName.trim(), password, verificationId, verificationCode)
      } else {
        await loginCloud(account.trim(), password)
      }
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
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-cover bg-[position:34%_center] md:bg-center"
        style={{ backgroundImage: `url(${product.loginBackgroundUrl})` }}
      />
      <div aria-hidden="true" className="absolute inset-0 bg-black/25 md:bg-black/10" />
      <LanguageSwitcher className="absolute right-5 top-5 z-20 md:right-8 md:top-8" />
      <section className="relative z-10 mx-auto w-full max-w-[420px] md:mx-0">
        <div className="mb-7 flex items-center gap-3 drop-shadow-lg">
          <div className="grid h-11 w-11 place-items-center overflow-hidden rounded-lg border border-white/15 bg-[#0B1220]/80"><img src={product.logoUrl} alt={product.name} className="h-full w-full object-cover" /></div>
          <div><h1 className="text-xl font-semibold">{product.name}</h1><p className="mt-1 text-sm text-[#CBD5E1]">{t(mode === 'login' ? '登录后继续使用智能服务' : mode === 'register' ? '注册账号后按需充值 Credits' : '验证当前密码后设置新密码')}</p></div>
        </div>
        <form className="rounded-lg border border-white/15 bg-[#0B1220]/90 p-6 shadow-2xl backdrop-blur-md" onSubmit={(event) => { event.preventDefault(); void submit() }}>
            <div className="space-y-4">
              {isRegistering && <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder={t('你的称呼')} autoComplete="name" autoFocus className="border-[#475569] bg-[#0D1321]/90" />}
              <Input value={account} onChange={(e) => { setAccount(e.target.value); if (isRegistering) { setVerificationId(''); setVerificationCode(''); setResendIn(0) } }} placeholder={t('邮箱')} type="email" autoComplete="username" autoFocus={mode !== 'register'} className="border-[#475569] bg-[#0D1321]/90" />
              <Input value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t(mode === 'change-password' ? '当前密码' : '密码（至少 10 个字符）')} type="password" autoComplete={isRegistering ? 'new-password' : 'current-password'} className="border-[#475569] bg-[#0D1321]/90" />
              {isRegistering && <>
                <div className="flex gap-2">
                  <Input
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder={t('6位邮箱验证码')}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    className="border-[#475569] bg-[#0D1321]/90"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    className="w-[132px] shrink-0 border border-[#475569] bg-[#172033] text-[#E2E8F0] hover:bg-[#25314A]"
                    disabled={codeLoading || resendIn > 0 || !account.trim()}
                    onClick={() => void sendRegistrationCode()}
                  >
                    {codeLoading ? <LoaderCircle className="mr-1.5 h-4 w-4 animate-spin" /> : <MailCheck className="mr-1.5 h-4 w-4" />}
                    {resendIn > 0 ? `${resendIn}s` : verificationId ? t('重新发送') : t('发送验证码')}
                  </Button>
                </div>
                <label className="flex items-start gap-2 text-xs leading-5 text-[#CBD5E1]">
                  <input type="checkbox" checked={acceptedTerms} onChange={(e) => setAcceptedTerms(e.target.checked)} className="mt-1 accent-[#6366F1]" />
                  <span>我已阅读并同意 <a href={product.termsUrl} target="_blank" rel="noreferrer" className="text-[#A5B4FC] hover:text-[#C7D2FE]">用户协议</a> 和 <a href={product.privacyUrl} target="_blank" rel="noreferrer" className="text-[#A5B4FC] hover:text-[#C7D2FE]">隐私政策</a></span>
                </label>
              </>}
              {mode === 'change-password' && <>
                <Input value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder={t('新密码（至少 10 个字符）')} type="password" autoComplete="new-password" className="border-[#475569] bg-[#0D1321]/90" />
                <Input value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder={t('再次输入新密码')} type="password" autoComplete="new-password" className="border-[#475569] bg-[#0D1321]/90" />
              </>}
              {message && <p className={`rounded-md border px-3 py-2 text-sm ${codeSent ? 'border-[#065F46] bg-[#064E3B]/35 text-[#A7F3D0]' : 'border-[#7F1D1D] bg-[#450A0A]/40 text-[#FCA5A5]'}`}>{message}</p>}
              <Button type="submit" className="w-full bg-[#6366F1] hover:bg-[#818CF8]" disabled={loading || !password || !account.trim() || (isRegistering && (!displayName.trim() || !verificationId || verificationCode.length !== 6 || !acceptedTerms)) || (mode === 'change-password' && (!newPassword || !confirmPassword))}>
                {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}{t(mode === 'login' ? '登录' : mode === 'register' ? '注册并登录' : '确认修改')}
              </Button>
              {mode === 'login' ? (
                <div className="flex items-center justify-center gap-5 text-sm">{product.allowSelfRegistration && <button type="button" onClick={() => { setMode('register'); setMessage('') }} className="text-[#A5B4FC] transition-colors hover:text-[#C7D2FE]">{t('注册账号')}</button>}<button type="button" onClick={() => { setMode('change-password'); setMessage('') }} className="text-[#94A3B8] transition-colors hover:text-[#E2E8F0]">{t('修改密码')}</button></div>
              ) : (
                <button type="button" onClick={() => { setMode('login'); setDisplayName(''); setNewPassword(''); setConfirmPassword(''); setVerificationCode(''); setVerificationId(''); setAcceptedTerms(false); setMessage('') }} className="flex w-full items-center justify-center gap-1.5 text-sm text-[#94A3B8] transition-colors hover:text-[#E2E8F0]"><ArrowLeft className="h-4 w-4" />{t('返回登录')}</button>
              )}
            </div>
        </form>
        <p className="mt-5 text-center text-xs text-[#CBD5E1] drop-shadow-md">{t('本机素材不会上传到云端')}</p>
      </section>
    </main>
  )
}
