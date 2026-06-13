import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/profil-sec', { replace: true })
    } catch (err) {
      setError(err.detail || 'Giriş başarısız')
    } finally {
      setLoading(false)
    }
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

          <div className="text-center text-xs text-gray-500 pt-2">
            Hesabın yok mu?{' '}
            <Link to="/register" className="text-accent hover:underline">
              Kayıt ol
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}
