import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function LoginPage() {
  const { login, verifyTwoFactor } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // 2FA adımı — login "requires_2fa" dönerse mfaToken set edilir, kod sorulur.
  const [mfaToken, setMfaToken] = useState('')
  const [code, setCode] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login(email, password)
      if (res?.requires_2fa) {
        setMfaToken(res.mfa_token)
      } else {
        navigate('/profil-sec', { replace: true })
      }
    } catch (err) {
      setError(err.detail || 'Giriş başarısız')
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await verifyTwoFactor(mfaToken, code.trim())
      navigate('/profil-sec', { replace: true })
    } catch (err) {
      setError(err.detail || 'Kod doğrulanamadı')
    } finally {
      setLoading(false)
    }
  }

  if (mfaToken) {
    return (
      <div className="h-full flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <div className="w-14 h-14 mx-auto mb-3 rounded-xl bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-2xl font-bold">🔐</div>
            <h1 className="text-xl font-semibold text-gray-100">İki Adımlı Doğrulama</h1>
            <p className="text-sm text-gray-500 mt-1">Authenticator uygulamandaki 6 haneli kodu gir</p>
          </div>
          <form onSubmit={handleVerify} className="card space-y-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Kod</label>
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                autoFocus
                value={code}
                onChange={e => setCode(e.target.value)}
                className="input w-full text-center tracking-[0.5em] text-lg"
                placeholder="000000"
              />
              <p className="text-[11px] text-gray-600 mt-1.5">Telefonuna erişemiyorsan yedek kodunu da girebilirsin.</p>
            </div>
            {error && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
            )}
            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? 'Doğrulanıyor...' : 'Doğrula ve Gir'}
            </button>
            <div className="text-center pt-1">
              <button type="button" onClick={() => { setMfaToken(''); setCode(''); setError('') }}
                className="text-xs text-gray-500 hover:text-accent">← Geri dön</button>
            </div>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 mx-auto mb-3 rounded-xl bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-2xl font-bold">
            B
          </div>
          <h1 className="text-xl font-semibold text-gray-100">Baskıcı Paneli</h1>
          <p className="text-sm text-gray-500 mt-1">Hesabınla giriş yap</p>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">E-posta</label>
            <input
              type="email"
              required
              autoFocus
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="input w-full"
              placeholder="ornek@firma.com"
            />
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">Şifre</label>
            <input
              type="password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="input w-full"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? 'Giriş yapılıyor...' : 'Giriş Yap'}
          </button>

          <div className="text-center pt-1">
            <Link to="/sifre-unuttum" className="text-xs text-gray-500 hover:text-accent">
              Şifremi unuttum
            </Link>
          </div>

          <div className="text-center text-xs text-gray-500 pt-1 border-t border-brand-border mt-1">
            <span className="block pt-2">Hesabın yok mu?{' '}
              <Link to="/register" className="text-accent hover:underline">Kayıt ol</Link>
            </span>
          </div>
        </form>
      </div>
    </div>
  )
}
