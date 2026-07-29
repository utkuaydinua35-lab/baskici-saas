import { useEffect, useState } from 'react'
import { passkeySupported } from '../lib/webauthn'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

// Animasyonlu dekoratif arka plan — drift eden renkli blob'lar + ince nokta ızgara
function AuthBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="login-blob absolute -top-24 -left-24 w-[26rem] h-[26rem] rounded-full opacity-30 blur-3xl"
        style={{ background: 'radial-gradient(circle, rgb(var(--accent-rgb)) 0%, transparent 70%)' }} />
      <div className="login-blob absolute top-1/3 -right-32 w-[30rem] h-[30rem] rounded-full opacity-25 blur-3xl"
        style={{ background: 'radial-gradient(circle, #9b5cff 0%, transparent 70%)', animationDelay: '4s' }} />
      <div className="login-blob absolute -bottom-32 left-1/4 w-[24rem] h-[24rem] rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, #2dd4bf 0%, transparent 70%)', animationDelay: '8s' }} />
      <div className="absolute inset-0 opacity-[0.05]"
        style={{ backgroundImage: 'radial-gradient(rgb(255 255 255) 1px, transparent 1px)', backgroundSize: '28px 28px' }} />
    </div>
  )
}

function Logo({ emoji }) {
  return (
    <div className="login-logo relative w-16 h-16 mx-auto mb-4 rounded-2xl bg-brand-card border border-white/10 flex items-center justify-center overflow-hidden"
      style={{ boxShadow: '0 12px 44px -8px rgb(var(--accent-rgb) / 0.55)' }}>
      {emoji
        ? <span className="text-3xl">{emoji}</span>
        : <img src="/favicon.svg" alt="BERNZ" className="w-9 h-9" draggable="false" />}
      <span className="login-sheen" aria-hidden="true" />
    </div>
  )
}

const IconMail = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 7-10 6L2 7" />
  </svg>
)
const IconLock = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
)

// Modül seviyesinde — render içinde tanımlanırsa her tuşta remount olup input focus'u kaybolur
function AuthShell({ children }) {
  return (
    <div className="relative min-h-screen flex items-center justify-center p-6 overflow-hidden">
      <AuthBackground />
      <div className="relative w-full max-w-sm animate-fadeinup">{children}</div>
    </div>
  )
}

const CARD_CLS = "rounded-2xl border border-white/10 bg-brand-card/70 backdrop-blur-xl p-6 shadow-2xl"

export default function LoginPage() {
  const { login, loginWithPasskey, verifyTwoFactor } = useAuth()
  const navigate = useNavigate()

  // Self-servis kayıt kapalıysa "Kayıt ol" bağlantısı hiç gösterilmez.
  // Varsayılan false -> kapalıyken bir an bile görünüp kaybolmaz.
  const [signupAllowed, setSignupAllowed] = useState(false)
  useEffect(() => {
    fetch('/api/auth/public-config')
      .then(r => r.ok ? r.json() : null)
      .then(d => setSignupAllowed(!!d?.signup_allowed))
      .catch(() => {})
  }, [])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // 2FA adımı — login "requires_2fa" dönerse mfaToken set edilir, kod sorulur.
  const [mfaToken, setMfaToken] = useState('')
  const [code, setCode] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const res = await login(email, password)
      if (res?.requires_2fa) setMfaToken(res.mfa_token)
      else navigate('/profil-sec', { replace: true })
    } catch (err) {
      setError(err.detail || 'Giriş başarısız')
    } finally { setLoading(false) }
  }

  const handleVerify = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await verifyTwoFactor(mfaToken, code.trim())
      navigate('/profil-sec', { replace: true })
    } catch (err) {
      setError(err.detail || 'Kod doğrulanamadı')
    } finally { setLoading(false) }
  }

  const handlePasskey = async () => {
    setError(''); setLoading(true)
    try {
      await loginWithPasskey()
      navigate('/profil-sec', { replace: true })
    } catch (err) {
      const m = err?.detail || err?.message || ''
      if (/aborterror|notallowed|cancel/i.test(m)) setError('')  // kullanıcı vazgeçti
      else setError(m || 'Geçiş anahtarı ile giriş başarısız')
    } finally { setLoading(false) }
  }

  const errBox = error && (
    <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
  )

  if (mfaToken) {
    return (
      <AuthShell>
        <div className="text-center mb-6">
          <Logo emoji="🔐" />
          <h1 className="text-xl font-semibold text-gray-100">İki Adımlı Doğrulama</h1>
          <p className="text-sm text-gray-500 mt-1">Authenticator uygulamandaki 6 haneli kodu gir</p>
        </div>
        <form onSubmit={handleVerify} className={`${CARD_CLS} space-y-4`}>
          <div>
            <label className="text-xs text-gray-400 block mb-1.5">Doğrulama kodu</label>
            <input type="text" inputMode="numeric" autoComplete="one-time-code" required autoFocus
              value={code} onChange={e => setCode(e.target.value)}
              className="input w-full text-center tracking-[0.5em] text-lg" placeholder="000000" />
            <p className="text-[11px] text-gray-600 mt-1.5">Telefonuna erişemiyorsan yedek kodunu da girebilirsin.</p>
          </div>
          {errBox}
          <button type="submit" disabled={loading} className="btn-primary w-full !py-2.5">
            {loading ? 'Doğrulanıyor…' : 'Doğrula ve gir'}
          </button>
          <div className="text-center">
            <button type="button" onClick={() => { setMfaToken(''); setCode(''); setError('') }}
              className="text-xs text-gray-500 hover:text-accent transition-colors">← Geri dön</button>
          </div>
        </form>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div className="text-center mb-6">
        <Logo />
        <h1 className="text-2xl font-semibold text-gray-100 tracking-tight">Baskıcı Paneli</h1>
        <p className="text-sm text-gray-500 mt-1">Hesabınla giriş yap, üretime devam et</p>
      </div>

      <form onSubmit={handleSubmit} className={`${CARD_CLS} space-y-4`}>
        <div>
          <label className="text-xs text-gray-400 block mb-1.5">E-posta</label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
              <IconMail />
            </span>
            <input type="email" required autoFocus autoComplete="username" value={email} onChange={e => setEmail(e.target.value)}
              className="input w-full !pl-10" placeholder="ornek@firma.com" />
          </div>
        </div>

        <div>
          <label className="text-xs text-gray-400 block mb-1.5">Şifre</label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
              <IconLock />
            </span>
            <input type={showPw ? 'text' : 'password'} required autoComplete="current-password" value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyUp={e => setCapsLock(typeof e.getModifierState === 'function' && e.getModifierState('CapsLock'))}
              className="input w-full !pl-10 !pr-12" placeholder="••••••••" />
            <button type="button" onClick={() => setShowPw(s => !s)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[11px] text-gray-500 hover:text-accent px-2 py-1 transition-colors"
              tabIndex={-1}>
              {showPw ? 'Gizle' : 'Göster'}
            </button>
          </div>
          {capsLock && (
            <p className="text-[11px] text-amber-400 mt-1.5 flex items-center gap-1">⇪ Caps Lock açık</p>
          )}
        </div>

        {errBox}

        <button type="submit" disabled={loading} className="btn-primary w-full !py-2.5 relative overflow-hidden">
          {loading ? 'Giriş yapılıyor…' : 'Giriş Yap'}
        </button>

        {passkeySupported() && (
          <button type="button" onClick={handlePasskey} disabled={loading}
            className="btn-secondary w-full !py-2.5 flex items-center justify-center gap-2">
            🔑 Geçiş anahtarı ile giriş
          </button>
        )}

        <div className="text-center">
          <Link to="/sifre-unuttum" className="text-xs text-gray-500 hover:text-accent transition-colors">
            Şifremi unuttum
          </Link>
        </div>

        {signupAllowed && (
          <div className="text-center text-xs text-gray-500 pt-3 border-t border-brand-border/70">
            <span className="block pt-3">Hesabın yok mu?{' '}
              <Link to="/register" className="text-accent hover:underline font-medium">Kayıt ol</Link>
            </span>
          </div>
        )}
      </form>

      <p className="text-center text-[11px] text-gray-600 mt-5 tracking-wide">
        BERNZ Company · Baskıcı Paneli
      </p>
      <img
        src="/bernz-company.png"
        alt="BERNZ Company"
        draggable="false"
        onError={e => { e.currentTarget.style.display = 'none' }}
        className="mx-auto mt-4 w-14 rounded-lg border border-white/10 opacity-90 shadow-lg"
      />
    </AuthShell>
  )
}
