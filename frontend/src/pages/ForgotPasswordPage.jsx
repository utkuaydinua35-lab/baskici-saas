import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await api.post('/api/auth/forgot-password', { email: email.trim() })
      setSent(true)
    } catch (err) {
      setError(err.detail || 'Bir hata oluştu, tekrar deneyin.')
    } finally { setLoading(false) }
  }

  return (
    <div className="h-full flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 mx-auto mb-3 rounded-xl bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-2xl font-bold">B</div>
          <h1 className="text-xl font-semibold text-gray-100">Şifre Sıfırlama</h1>
          <p className="text-sm text-gray-500 mt-1">E-posta adresine sıfırlama bağlantısı gönderelim</p>
        </div>

        {sent ? (
          <div className="card text-center space-y-3 animate-fadein">
            <div className="text-3xl">📧</div>
            <p className="text-sm text-gray-200">E-posta adresin kayıtlıysa, şifre sıfırlama bağlantısı gönderildi.</p>
            <p className="text-xs text-gray-500">Gelen kutunu (ve spam klasörünü) kontrol et. Bağlantı 1 saat geçerli.</p>
            <Link to="/login" className="btn-primary w-full inline-block">Girişe dön</Link>
          </div>
        ) : (
          <form onSubmit={submit} className="card space-y-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">E-posta</label>
              <input type="email" required autoFocus value={email} onChange={e => setEmail(e.target.value)}
                className="input w-full" placeholder="ornek@firma.com" />
            </div>
            {error && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
            )}
            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? 'Gönderiliyor...' : 'Sıfırlama Bağlantısı Gönder'}
            </button>
            <div className="text-center text-xs text-gray-500 pt-2">
              <Link to="/login" className="text-accent hover:underline">← Girişe dön</Link>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
