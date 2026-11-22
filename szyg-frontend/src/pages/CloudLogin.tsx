import { useEffect, useState } from 'react'
import { ArrowLeft, KeyRound, LoaderCircle, MailCheck } from 'lucide-react'
import {
  getErrorMessage,
  loginCloud,
  registerCloud,
  requestPasswordResetCode,
  requestRegistrationCode,
  resetCloudPassword,
} from '@/lib/api'
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
  const [codeSent, setCodeSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const isRegistering = product.allowSelfRegistration && mode === 'register'
  const isPasswordReset = mode === 'change-password'
  const needsVerificationCode = isRegistering || isPasswordReset

  useEffect(() => {
    if (resendIn <= 0) return
    const timer = window.setInterval(() => setResendIn((value) => Math.max(0, value - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [resendIn])

  const sendVerificationCode = async () => {
    if (!account.trim() || codeLoading || resendIn > 0) return
    setCodeLoading(true)
    setMessage('')
    try {
      const challenge = isPasswordReset
        ? await requestPasswordResetCode(account.trim())
        : await requestRegistrationCode(account.trim())
      setVerificationId(challenge.verification_id)
      setResendIn(challenge.retry_after_seconds || 60)
      setCodeSent(true)
      setMessage(t("验证码已发送至 {v0}，10分钟内有效", { v0: challenge.email }))
    } catch (error) {
      setCodeSent(false)
      setMessage(getErrorMessage(error, t("验证码发送失败，请稍后再试")))
    } finally {
      setCodeLoading(false)
    }
  }

  const submit = async () => {
    if (!account.trim() || (!isPasswordReset && !password) || loading) return
    setCodeSent(false)
    if (isRegistering && !displayName.trim()) {
      setMessage(t("请输入你的称呼"))
      return
    }
    if (isRegistering && Array.from(password).length < 6) {
      setMessage(t("密码至少需要 6 个字符"))
      return
    }
    if (needsVerificationCode && (!verificationId || !/^\d{6}$/.test(verificationCode))) {
      setMessage(t("请先获取并填写6位邮箱验证码"))
      return
    }
    if (isRegistering && !acceptedTerms) {
      setMessage(t("请先阅读并同意用户协议和隐私政策"))
      return
    }
    if (isPasswordReset) {
      if (Array.from(newPassword).length < 6) {
        setMessage(t("新密码至少需要 6 个字符"))
        return
      }
      if (newPassword !== confirmPassword) {
        setMessage(t("两次输入的新密码不一致"))
        return
      }
    }
    setLoading(true)
    setMessage('')
    try {
      if (isRegistering) {
        await registerCloud(account.trim(), displayName.trim(), password, verificationId, verificationCode)
      } else if (isPasswordReset) {
        await resetCloudPassword(account.trim(), newPassword, verificationId, verificationCode)
        await loginCloud(account.trim(), newPassword)
      } else {
        await loginCloud(account.trim(), password)
      }
      await onSuccess()
    } catch (error) {
      const errorMessage = getErrorMessage(error, t("登录未完成，请检查输入"))
      setMessage(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-shell">
      <LanguageSwitcher className="absolute right-5 top-5" />
      <section className="auth-panel">
        <img src={product.logoUrl} alt="" className="mb-5 h-12 w-12 rounded-xl object-cover" />
        <h1 className="text-2xl font-semibold tracking-tight">{t(product.name)}</h1>
        <p className="mb-7 mt-2 text-sm text-muted-foreground">{t(mode === 'login' ? 'auth.loginSubtitle' : mode === 'register' ? 'auth.registerSubtitle' : 'auth.changePasswordSubtitle')}</p>
        <form onSubmit={event => { event.preventDefault(); void submit() }}>
            <div className="space-y-4">
              {isRegistering && <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder={t('auth.displayName')} autoComplete="name" autoFocus className="border-border bg-background text-foreground" />}
              <Input disabled={codeLoading || loading} value={account} onChange={(e) => { setAccount(e.target.value); if (needsVerificationCode) { setVerificationId(''); setVerificationCode(''); setResendIn(0) } }} placeholder={t('auth.email')} type="email" autoComplete="username" autoFocus={mode !== 'register'} className="border-border bg-background text-foreground" />
              {!isPasswordReset && <Input value={password} onChange={(e) => setPassword(e.target.value)} aria-label={t('auth.password')} placeholder={t(isRegistering ? 'auth.passwordHint' : 'auth.password')} type="password" autoComplete={isRegistering ? 'new-password' : 'current-password'} className="border-border bg-background text-foreground" />}
              {needsVerificationCode && <>
                <div className="flex gap-2">
                  <Input
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder={t('auth.verificationCode')}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    className="border-border bg-background text-foreground"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    className="w-[132px] shrink-0 border border-border bg-muted text-foreground hover:bg-muted/80"
                    disabled={codeLoading || resendIn > 0 || !account.trim()}
                    onClick={() => void sendVerificationCode()}
                  >
                    {codeLoading ? <LoaderCircle className="mr-1.5 h-4 w-4 animate-spin" /> : <MailCheck className="mr-1.5 h-4 w-4" />}
                    {resendIn > 0 ? `${resendIn}s` : verificationId ? t('auth.resendCode') : t('auth.sendCode')}
                  </Button>
                </div>
                {isRegistering && <label className="flex items-start gap-2 text-xs leading-5 text-muted-foreground">
                  <input type="checkbox" checked={acceptedTerms} onChange={(e) => setAcceptedTerms(e.target.checked)} className="mt-1 accent-[#6366F1]" />
                  <span>{t('auth.termsPrefix')} <a href={product.termsUrl} target="_blank" rel="noreferrer" className="text-foreground underline underline-offset-2">{t('auth.terms')}</a> {t('auth.termsJoiner')} <a href={product.privacyUrl} target="_blank" rel="noreferrer" className="text-foreground underline underline-offset-2">{t('auth.privacy')}</a></span>
                </label>}
              </>}
              {isPasswordReset && <>
                <Input value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder={t('auth.newPasswordHint')} type="password" autoComplete="new-password" className="border-border bg-background text-foreground" />
                <Input value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder={t('auth.confirmPassword')} type="password" autoComplete="new-password" className="border-border bg-background text-foreground" />
              </>}
              {message && <p className={`rounded-md border px-3 py-2 text-sm ${codeSent ? 'border-[#065F46] bg-[#064E3B]/35 text-[#A7F3D0]' : 'border-[#7F1D1D] bg-[#450A0A]/40 text-[#FCA5A5]'}`}>{message}</p>}
              <Button type="submit" className="w-full bg-foreground text-background hover:bg-foreground/90" disabled={loading || !account.trim() || (!isPasswordReset && !password) || (isRegistering && (!displayName.trim() || !verificationId || verificationCode.length !== 6 || !acceptedTerms)) || (isPasswordReset && (!verificationId || verificationCode.length !== 6 || !newPassword || !confirmPassword))}>
                {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}{t(mode === 'login' ? 'auth.signIn' : mode === 'register' ? 'auth.createAndSignIn' : 'auth.confirmChange')}
              </Button>
              {mode === 'login' ? (
                <div className="flex items-center justify-center gap-5 text-sm">{product.allowSelfRegistration && <button type="button" onClick={() => { setMode('register'); setMessage('') }} className="text-foreground hover:underline">{t('auth.createAccount')}</button>}<button type="button" onClick={() => { setMode('change-password'); setMessage('') }} className="text-muted-foreground hover:text-foreground">{t('auth.changePassword')}</button></div>
              ) : (
                <button type="button" onClick={() => { setMode('login'); setDisplayName(''); setNewPassword(''); setConfirmPassword(''); setVerificationCode(''); setVerificationId(''); setAcceptedTerms(false); setMessage('') }} className="flex w-full items-center justify-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />{t('auth.backToSignIn')}</button>
              )}
            </div>
        </form>
        <p className="mt-5 text-center text-xs text-muted-foreground">{t('auth.localFilesNotice')}</p>
      </section>
    </main>
  )
}
