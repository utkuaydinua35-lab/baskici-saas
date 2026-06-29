import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    email: '',
    password: '',
    full_name: '',
    tenant_name: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [pending, setPending] = useState('')

  const setField = (k, v) => setForm(prev => ({ ...prev, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (form.password.length < 8) {
      setError('Şifre en az 8 karakter olmalı')
      return
    }
    setLoading(true)
    try {
      const res = await register(form)
      if (res?.pending) {
        setPending(res.message || 'Kaydınız alındı. Hesabınız onay aşamasında — onay için yöneticiyle iletişime geçiniz.')
        return
      }
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.detail || 'Kayıt başarısız')
    } finally {
      setLoading(false)
    }
  }

  if (pending) {
    return (
      <div className="h-full flex items-center justify-center p-6">
        <div className="w-full max-w-sm text-center card">
          <div className="w-14 h-14 mx-auto mb-3 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-3xl">⏳</div>
          <h1 className="text-lg font-semibold text-gray-100">Onay bekleniyor</h1>
          <p className="text-sm text-gray-400 mt-2 leading-relaxed">{pending}</p>
          <Link to="/login" className="btn-secondary !text-sm inline-block mt-4">Giriş ekranına dön</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="w-14 h-14 mx-auto mb-3 rounded-xl bg-gradient-to-br from-accent to-emerald-600 flex items-center justify-center text-white text-2xl font-bold">
            B
          </div>
          <h1 className="text-xl font-semibold text-gray-100">Yeni Hesap Oluştur</h1>
          <p className="text-sm text-gray-500 mt-1">İlk kullanıcı otomatik olarak yönetici olur</p>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Firma adı</label>
            <input
              type="text"
              required
              autoFocus
              value={form.tenant_name}
              onChange={e => setField('tenant_name', e.target.value)}
              className="input w-full"
              placeholder="Örn: BERNZ Company"
            />
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">Adın</label>
            <input
              type="text"
              required
              value={form.full_name}
              onChange={e => setField('full_name', e.target.value)}
              className="input w-full"
              placeholder="Adın Soyadın"
            />
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">E-posta</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={e => setField('email', e.target.value)}
              className="input w-full"
              placeholder="ornek@firma.com"
            />
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">Şifre</label>
            <input
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={e => setField('password', e.target.value)}
              className="input w-full"
              placeholder="En az 8 karakter"
            />
          </div>

          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? 'Hesap oluşturuluyor...' : 'Kayıt Ol'}
          </button>

          <div className="text-center text-xs text-gray-500 pt-2">
            Zaten hesabın var mı?{' '}
            <Link to="/login" className="text-accent hover:underline">
              Giriş yap
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}
