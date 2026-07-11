import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useStore } from '../lib/store'
import { useToast } from './Toast'
import BrandMark from './BrandMark'

// Shopify yerleşim mantığı: koyu üst bar (marka + mağaza + vitrin linki +
// profil menüsü), solda GRUPLU menü, Ayarlar en altta sabit.
const NAV_GROUPS = [
  { label: null, items: [
    { to: '/', label: 'Ana Sayfa', icon: '🏠', end: true },
  ]},
  { label: 'Satış', items: [
    { to: '/siparisler', label: 'Siparişler', icon: '📦' },
  ]},
  { label: 'Katalog', items: [
    { to: '/urunler', label: 'Ürünler', icon: '🛍️' },
    { to: '/koleksiyonlar', label: 'Koleksiyonlar', icon: '🗂️' },
    { to: '/envanter', label: 'Envanter', icon: '📋' },
  ]},
  { label: 'Müşteri', items: [
    { to: '/musteriler', label: 'Müşteriler', icon: '👥' },
    { to: '/yorumlar', label: 'Yorumlar', icon: '⭐' },
    { to: '/tasarim-talepleri', label: 'Tasarım Talepleri', icon: '🖌️' },
  ]},
  { label: 'Pazarlama', items: [
    { to: '/kuponlar', label: 'İndirimler', icon: '🎟️' },
    { to: '/terk-sepetler', label: 'Terk Sepetler', icon: '🛒' },
    { to: '/analitik', label: 'Analitik', icon: '📈' },
  ]},
  { label: 'Online Mağaza', items: [
    { to: '/tema', label: 'Tema', icon: '🎨' },
    { to: '/sayfalar', label: 'Sayfalar', icon: '📄' },
    { to: '/blog', label: 'Blog', icon: '✍️' },
    { to: '/uygulamalar', label: 'Uygulamalar', icon: '🧩' },
  ]},
]

export default function Layout() {
  const { user, logout, refresh } = useAuth()
  const { stores, store, setStoreId } = useStore()
  const location = useLocation()

  const storefrontUrl = store?.config?.storefront_url
    || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : null)

  return (
    <div className="min-h-screen flex flex-col">
      {/* Üst bar — koyu, Shopify tarzı */}
      <header className="h-12 shrink-0 bg-slate-900 flex items-center gap-3 px-3 text-white sticky top-0 z-30">
        <div className="flex items-center gap-2 pr-2">
          <BrandMark />
          <span className="text-[13px] tracking-tight">
            <span className="font-bold">BERNZ</span>
            <span className="text-emerald-300 font-light ml-1">Commerce</span>
          </span>
        </div>

        {stores.length > 1 ? (
          <select value={store?.id || ''} onChange={e => setStoreId(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1.5
              focus:outline-none focus:border-emerald-500">
            {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        ) : (
          <span className="text-xs text-slate-300 bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5">
            🏪 {store?.name || 'Mağaza'}
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          {storefrontUrl && (
            <a href={storefrontUrl} target="_blank" rel="noopener noreferrer"
              className="text-xs text-slate-300 hover:text-white border border-slate-700 hover:border-slate-500
                rounded-lg px-2.5 py-1.5 transition-colors">
              Vitrini Gör ↗
            </a>
          )}
          <ProfileMenu user={user} logout={logout} refresh={refresh} />
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Sol menü — gruplu */}
        <aside className="w-56 shrink-0 border-r border-panel-border bg-white flex flex-col
          sticky top-12 h-[calc(100vh-3rem)]">
          <nav className="flex-1 px-2 py-2 overflow-y-auto">
            {NAV_GROUPS.map((g, gi) => (
              <div key={gi}>
                {g.label && <div className="nav-group-label">{g.label}</div>}
                {g.items.map(item => (
                  <NavLink key={item.to} to={item.to} end={item.end}
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <span className="nav-icon">{item.icon}</span>
                    {item.label}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          {/* Ayarlar — Shopify gibi en altta sabit */}
          <div className="p-2 border-t border-panel-border">
            <NavLink to="/ayarlar"
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <span className="nav-icon">⚙️</span>
              Ayarlar
            </NavLink>
          </div>
        </aside>

        {/* İçerik */}
        <main className="flex-1 min-w-0 p-5 overflow-y-auto">
          <div key={location.pathname} className="page-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

// ── Profil menüsü — hesap bilgileri + şifre değiştirme + çıkış ──
function ProfileMenu({ user, logout, refresh }) {
  const [open, setOpen] = useState(false)
  const [modal, setModal] = useState(null)   // null | 'hesap' | 'sifre'
  const ref = useRef(null)

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const initial = (user?.full_name || user?.email || '?').slice(0, 1).toUpperCase()

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 pl-2 border-l border-slate-700 group">
        <div className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold
          bg-gradient-to-br from-slate-600 to-slate-700 group-hover:from-emerald-600 group-hover:to-teal-700
          transition-all duration-200 ring-1 ring-slate-600 group-hover:ring-emerald-500">
          {initial}
        </div>
        <span className="hidden sm:block text-[11px] font-medium truncate max-w-32 text-slate-300 group-hover:text-white transition-colors">
          {user?.full_name || user?.email}
        </span>
        <span className={`text-slate-500 text-[9px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-60 bg-white text-panel-ink rounded-2xl
          border border-panel-border shadow-xl overflow-hidden toast-in z-50">
          <div className="px-4 py-3 bg-panel-input/60 border-b border-panel-border">
            <div className="text-sm font-semibold truncate">{user?.full_name || '—'}</div>
            <div className="text-xs text-panel-muted truncate">{user?.email}</div>
          </div>
          <div className="p-1.5 text-sm">
            <button onClick={() => { setModal('hesap'); setOpen(false) }}
              className="w-full text-left px-3 py-2 rounded-xl hover:bg-panel-input transition-colors flex items-center gap-2.5">
              <span>👤</span> Hesap bilgileri
            </button>
            <button onClick={() => { setModal('sifre'); setOpen(false) }}
              className="w-full text-left px-3 py-2 rounded-xl hover:bg-panel-input transition-colors flex items-center gap-2.5">
              <span>🔑</span> Şifre değiştir
            </button>
            <div className="my-1 border-t border-panel-border" />
            <button onClick={logout}
              className="w-full text-left px-3 py-2 rounded-xl hover:bg-red-50 text-red-600 transition-colors flex items-center gap-2.5">
              <span>🚪</span> Çıkış yap
            </button>
          </div>
        </div>
      )}

      {modal === 'hesap' && (
        <AccountModal user={user} refresh={refresh} onClose={() => setModal(null)} />
      )}
      {modal === 'sifre' && <PasswordModal onClose={() => setModal(null)} />}
    </div>
  )
}

function ModalShell({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-6"
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-white text-panel-ink rounded-2xl shadow-xl w-full max-w-sm p-5 toast-in">
        <div className="flex items-center mb-3">
          <h2 className="text-base font-semibold">{title}</h2>
          <button onClick={onClose} className="ml-auto text-panel-muted hover:text-panel-ink">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function AccountModal({ user, refresh, onClose }) {
  const toast = useToast()
  const [name, setName] = useState(user?.full_name || '')
  const [busy, setBusy] = useState(false)

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.patch('/api/auth/me', { full_name: name.trim() })
      await refresh?.()
      toast.success('Hesap bilgileri güncellendi')
      onClose()
    } catch (e2) {
      toast.error(typeof e2?.detail === 'string' ? e2.detail : 'Güncellenemedi')
    } finally { setBusy(false) }
  }

  return (
    <ModalShell title="👤 Hesap Bilgileri" onClose={onClose}>
      <form onSubmit={save} className="space-y-3">
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Ad Soyad</span>
          <input className="input mt-1" value={name} required maxLength={200}
            onChange={e => setName(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">E-posta (değiştirilemez)</span>
          <input className="input mt-1 opacity-60" value={user?.email || ''} disabled />
        </label>
        <button disabled={busy || !name.trim()} className="btn-primary w-full">
          {busy ? 'Kaydediliyor…' : 'Kaydet'}
        </button>
      </form>
    </ModalShell>
  )
}

function PasswordModal({ onClose }) {
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [next2, setNext2] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async (e) => {
    e.preventDefault()
    if (next !== next2) { setError('Yeni şifreler eşleşmiyor'); return }
    if (next.length < 8) { setError('Yeni şifre en az 8 karakter olmalı'); return }
    setBusy(true); setError('')
    try {
      await api.post('/api/auth/change-password', { current_password: current, new_password: next })
      toast.success('Şifreniz güncellendi 🔒')
      onClose()
    } catch (e2) {
      setError(typeof e2?.detail === 'string' ? e2.detail : 'Şifre değiştirilemedi')
    } finally { setBusy(false) }
  }

  return (
    <ModalShell title="🔑 Şifre Değiştir" onClose={onClose}>
      <form onSubmit={save} className="space-y-3">
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Mevcut şifre</span>
          <input className="input mt-1" type="password" value={current} required
            autoComplete="current-password" onChange={e => setCurrent(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Yeni şifre (en az 8 karakter)</span>
          <input className="input mt-1" type="password" value={next} required minLength={8}
            autoComplete="new-password" onChange={e => setNext(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Yeni şifre (tekrar)</span>
          <input className="input mt-1" type="password" value={next2} required
            autoComplete="new-password" onChange={e => setNext2(e.target.value)} />
        </label>
        {error && <p className="text-xs text-red-600">{error}</p>}
        <button disabled={busy} className="btn-primary w-full">
          {busy ? 'Güncelleniyor…' : 'Şifreyi Güncelle'}
        </button>
      </form>
    </ModalShell>
  )
}
