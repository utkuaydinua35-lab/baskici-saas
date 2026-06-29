import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const navigate = useNavigate()

  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [show, setShow] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (pw.length < 8) { setError('Şifre en az 8 karakter olmalı'); return }
    if (pw !== pw2) { setError('Şifreler eşleşmiyor'); return }
    setLoading(true)
    try {
      await api.post('/api/auth/reset-password', { token, new_password: pw })
      setDone(true)
      setTimeout(() => navigate('/login', { replace: true }), 2200)
    } catch (err) {
      setError(err.detail || 'Şifre güncellenemedi.')
    } finally { setLoading(false) }
  }

  return (
    <div className="h-full flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 mx-auto mb-3 rounded-xl bg-gradient-to-br from-accent to-teal-600 flex items-center justify-center text-white text-2xl font-bold">B</div>
          <h1 className="text-xl font-semibold text-gray-100">Yeni Şifre Belirle</h1>
        </div>

        {!token ? (
          <div className="card text-center space-y-3">
            <div className="text-3xl">⚠️</div>
            <p className="text-sm text-gray-300">Geçersiz bağlantı. Lütfen yeni bir sıfırlama talebi oluştur.</p>
            <Link to="/sifre-unuttum" className="btn-primary w-full inline-block">Sıfırlama Talebi</Link>
          </div>
        ) : done ? (
          <div className="card text-center space-y-2 animate-fadein">
            <div className="text-3xl">✅</div>
            <p className="text-sm text-gray-200">Şifren güncellendi! Girişe yönlendiriliyorsun…</p>
          </div>
        ) : (
          <form onSubmit={submit} className="card space-y-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Yeni şifre (en az 8 karakter)</label>
              <div className="relative">
                <input type={show ? 'text' : 'password'} required autoFocus value={pw} onChange={e => setPw(e.target.value)}
                  className="input w-full pr-10" placeholder="••••••••" />
                <button type="button" onClick={() => setShow(s => !s)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                  {show ? '🙈' : '👁'}
                </button>
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Yeni şifre (tekrar)</label>
              <input type={show ? 'text' : 'password'} required value={pw2} onChange={e => setPw2(e.target.value)}
                className="input w-full" placeholder="••••••••" />
            </div>
            {error && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
            )}
            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? 'Kaydediliyor...' : 'Şifreyi Güncelle'}
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
