import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { BRAND, TAGLINE } from '../lib/brand'
import BrandMark from '../components/BrandMark'
import { loginPasskey, passkeySupported } from '../lib/webauthn'
import { setToken } from '../lib/api'

// Giriş — Baskıcı ile aynı hesaplar (2FA destekli).
export default function LoginPage() {
  const { login, verifyTwoFactor } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mfaToken, setMfaToken] = useState(null)   // dolu → kod adımı
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pkBusy, setPkBusy] = useState(false)

  // Geçiş anahtarı (passkey) ile giriş — şifre/2FA gerekmez, phishing-dirençli.
  // Aynı anahtar Baskıcı panelinde de geçerlidir (ortak RP ID).
  const passkeyLogin = async () => {
    setPkBusy(true); setError('')
    try {
      const data = await loginPasskey()
      setToken(data.access_token)
      window.location.href = '/'   // auth context'i taze token'la kursun
    } catch (e2) {
      const msg = typeof e2?.detail === 'string' ? e2.detail
        : e2?.name === 'NotAllowedError' ? 'Geçiş anahtarı iptal edildi'
        : 'Geçiş anahtarıyla giriş yapılamadı'
      setError(msg)
    } finally { setPkBusy(false) }
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      if (mfaToken) {
        await verifyTwoFactor(mfaToken, code.trim())
        navigate('/', { replace: true })
        return
      }
      const r = await login(email.trim(), password)
      if (r?.requires_2fa) { setMfaToken(r.mfa_token); return }
      navigate('/', { replace: true })
    } catch (e2) {
      setError(typeof e2?.detail === 'string' ? e2.detail : 'Giriş başarısız')
    } finally { setBusy(false) }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-panel-bg">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 justify-center mb-6 pop-in">
          <BrandMark size={40} />
          <div>
            <div className="font-semibold leading-tight">{BRAND}</div>
            <div className="text-xs text-panel-muted leading-tight">{TAGLINE}</div>
          </div>
        </div>

        <form onSubmit={submit} className="card !p-6 space-y-3">
          {!mfaToken ? (
            <>
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">E-posta</span>
                <input className="input mt-1" type="email" value={email} required
                  autoComplete="email" onChange={e => setEmail(e.target.value)} />
              </label>
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">Şifre</span>
                <input className="input mt-1" type="password" value={password} required
                  autoComplete="current-password" onChange={e => setPassword(e.target.value)} />
              </label>
            </>
          ) : (
            <label className="block text-sm">
              <span className="text-panel-muted text-xs">Doğrulama kodu (authenticator)</span>
              <input className="input mt-1 font-mono text-center tracking-widest" value={code}
                required autoFocus maxLength={10} onChange={e => setCode(e.target.value)} />
            </label>
          )}
          {error && <p className="text-xs text-red-300">{error}</p>}
          <button disabled={busy} className="btn-primary w-full">
            {busy ? 'Giriş yapılıyor…' : mfaToken ? 'Doğrula' : 'Giriş Yap'}
          </button>

          {!mfaToken && passkeySupported() && (
            <>
              <div className="flex items-center gap-2 pt-1">
                <div className="h-px flex-1 bg-panel-border" />
                <span className="text-[11px] text-panel-muted">veya</span>
                <div className="h-px flex-1 bg-panel-border" />
              </div>
              <button type="button" onClick={passkeyLogin} disabled={pkBusy}
                className="btn-ghost w-full !py-2.5 text-sm">
                {pkBusy ? 'Bekleniyor…' : '🔑 Geçiş anahtarı ile giriş'}
              </button>
            </>
          )}
        </form>
        <p className="mt-4 text-center text-xs text-panel-muted">
          Hesaplar Baskıcı Paneli ile ortaktır.
        </p>
      </div>
    </div>
  )
}
