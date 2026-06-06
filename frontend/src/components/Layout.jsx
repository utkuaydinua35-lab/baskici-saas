import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'

export default function Layout() {
  const { user, tenant, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="h-full flex flex-col">
      <header className="border-b border-brand-border bg-brand-card/50 backdrop-blur-md relative z-[60]">
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-sm font-bold">
              B
            </div>
            <div>
              <div className="text-sm font-semibold text-gray-100">{tenant?.name || 'Baskıcı'}</div>
              <div className="text-[10px] text-gray-500">baskıcı paneli · {tenant?.plan || 'trial'}</div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <SyncButton />
          <NotificationBell />
          <ProfileDropdown user={user} onLogout={handleLogout} />
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-56 border-r border-brand-border bg-brand-card/30 p-3 hidden md:block overflow-y-auto">
          <nav className="space-y-1 text-sm">
            <NavItem to="/" label="Dashboard" icon="📊" end />

            <SectionLabel>SİPARİŞ YÖNETİMİ</SectionLabel>
            <NavItem to="/stores" label="Mağazalar" icon="🏪" />
            <NavItem to="/orders" label="Siparişler" icon="📦" />

            <SectionLabel>TASARIM YÖNETİMİ</SectionLabel>
            <NavItem to="/designs" label="Tasarımlar" icon="🎨" />
            <NavItem to="/kisiye-ozel" label="Kişiye Özel" icon="✨" />

            <SectionLabel>KALIP YÖNETİMİ</SectionLabel>
            <NavItem to="/kalip-sablon" label="Kalıp Şablonu" icon="🧩" />
            <NavItem to="/kalip-olustur" label="Kalıp Oluşturucu" icon="🎯" />

            <SectionLabel>STOK YÖNETİMİ</SectionLabel>
            <NavItem to="/aski" label="Askıda Bekleyenler" icon="🎁" />

            <SectionLabel>KATALOG</SectionLabel>
            <NavItem to="/telefon-modelleri" label="Telefon Modelleri" icon="📱" />

            <SectionLabel>ESKİ SİSTEM</SectionLabel>
            <NavItem to="/shortcuts" label="Kısayollar" icon="🔗" legacy />
            <NavItem to="/pipeline" label="Pipeline" icon="⚙️" legacy />
          </nav>

          <div className="mt-6 px-2 text-[10px] text-gray-600 leading-relaxed">
            Soluk olanlar yapım aşamasında. "Eski sistem" kısmı yeni mimariye geçiş bitince kaldırılır.
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function SectionLabel({ children }) {
  return (
    <div className="text-[9px] uppercase tracking-wider text-gray-600 mt-4 mb-1 px-2">
      {children}
    </div>
  )
}

function SyncButton() {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const run = async () => {
    if (busy) return
    setBusy(true); setMsg(null)
    try {
      const r = await api.post('/api/notifications/sync-all', {})
      setMsg({ ok: true, text: `${r.new_count} yeni · ${r.updated_count} güncellendi (${r.ok}/${r.stores} mağaza)` })
      window.dispatchEvent(new Event('notifications:refresh'))
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Senkronizasyon hatası' })
    } finally {
      setBusy(false)
      setTimeout(() => setMsg(null), 5000)
    }
  }
  return (
    <div className="relative">
      <button onClick={run} disabled={busy} title="Tüm mağazaları senkronize et"
        className="p-2 rounded-lg hover:bg-brand-input text-gray-400 hover:text-gray-200 disabled:opacity-50">
        <span className={`inline-block text-lg ${busy ? 'animate-spin' : ''}`}>🔄</span>
      </button>
      {msg && (
        <div className={`absolute right-0 mt-1 w-64 text-xs rounded-lg px-3 py-2 shadow-2xl z-[70] border ${
          msg.ok ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-200' : 'bg-red-500/15 border-red-500/30 text-red-300'
        }`}>
          {msg.ok ? '✓ Senkronizasyon tamamlandı' : '✗ Hata'}
          <div className="opacity-80 mt-0.5">{msg.text}</div>
        </div>
      )}
    </div>
  )
}

function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const ref = useRef(null)

  const load = async () => {
    try {
      const r = await api.get('/api/notifications?limit=30')
      setItems(r.items || [])
      setUnread(r.unread_count || 0)
    } catch {}
  }

  useEffect(() => { load() }, [])
  // 60 sn'de bir + senk sonrası tazele
  useEffect(() => {
    const t = setInterval(load, 60000)
    const onRefresh = () => load()
    window.addEventListener('notifications:refresh', onRefresh)
    return () => { clearInterval(t); window.removeEventListener('notifications:refresh', onRefresh) }
  }, [])
  useEffect(() => {
    if (!open) return
    const onClick = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const openPanel = () => { setOpen(o => !o); if (!open) load() }

  const markRead = async (id) => {
    try { await api.patch(`/api/notifications/${id}/read`, {}) ; load() } catch {}
  }
  const markAll = async () => {
    try { await api.post('/api/notifications/read-all', {}); load() } catch {}
  }

  const icon = k => k === 'error' ? '⚠' : k === 'info' ? 'ℹ' : '🔄'

  return (
    <div className="relative" ref={ref}>
      <button onClick={openPanel} title="Bildirimler"
        className="relative p-2 rounded-lg hover:bg-brand-input text-gray-400 hover:text-gray-200">
        <span className="text-lg">🔔</span>
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-semibold flex items-center justify-center">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-80 bg-brand-card border border-brand-border rounded-lg shadow-2xl z-[70] overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-brand-border">
            <span className="text-sm font-medium text-gray-200">Bildirimler</span>
            {unread > 0 && (
              <button onClick={markAll} className="text-[11px] text-accent hover:underline">Tümünü okundu işaretle</button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-3 py-8 text-center text-xs text-gray-500">Bildirim yok</div>
            ) : items.map(n => (
              <button key={n.id} onClick={() => markRead(n.id)}
                className={`w-full text-left px-3 py-2 border-b border-brand-border/50 hover:bg-brand-input flex gap-2 ${
                  n.is_read ? 'opacity-55' : ''
                }`}>
                <span className="text-base shrink-0">{icon(n.kind)}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-gray-200 leading-snug">{n.title}</div>
                  {n.body && <div className="text-[11px] text-gray-500 mt-0.5 truncate">{n.body}</div>}
                  <div className="text-[10px] text-gray-600 mt-0.5">{fmtTime(n.created_at)}</div>
                </div>
                {!n.is_read && <span className="w-2 h-2 rounded-full bg-accent shrink-0 mt-1" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso), now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return 'az önce'
  if (diff < 3600) return `${Math.floor(diff/60)} dk önce`
  if (diff < 86400) return `${Math.floor(diff/3600)} saat önce`
  return d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function ProfileDropdown({ user, onLogout }) {
  const [open, setOpen] = useState(false)
  const [showPw, setShowPw] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return
    const onClick = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])
  const initial = (user?.full_name || user?.email || '?').charAt(0).toUpperCase()
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-brand-input transition-colors">
        <span className="w-8 h-8 rounded-full bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-sm font-semibold">{initial}</span>
        <span className="text-xs text-gray-300 hidden sm:block">{user?.full_name || user?.email}</span>
        <span className="text-gray-500 text-xs">⌄</span>
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-56 bg-brand-card border border-brand-border rounded-lg shadow-2xl z-[70] py-1">
          <div className="px-3 py-2 border-b border-brand-border">
            <div className="text-sm text-gray-200">{user?.full_name || '—'}</div>
            <div className="text-[11px] text-gray-500">{user?.email}</div>
            <div className="text-[10px] text-gray-600 mt-0.5">{user?.role}</div>
          </div>
          <button onClick={() => { setShowPw(true); setOpen(false) }} className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-brand-input flex items-center gap-2">
            <span className="w-5 text-center">⚙</span> Ayarlar
          </button>
          <button onClick={onLogout} className="w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-red-500/10 flex items-center gap-2">
            <span className="w-5 text-center">⎋</span> Çıkış Yap
          </button>
        </div>
      )}
      {showPw && <ChangePasswordModal onClose={() => setShowPw(false)} />}
    </div>
  )
}

function ChangePasswordModal({ onClose }) {
  const [step, setStep] = useState('verify')  // verify | change
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [newPw2, setNewPw2] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const verify = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await api.post('/api/auth/verify-password', { password: currentPw })
      setStep('change')
    } catch (err) {
      setError(typeof err?.detail === 'string' ? err.detail : 'Şifre yanlış')
    } finally { setBusy(false) }
  }

  const change = async (e) => {
    e.preventDefault()
    if (newPw !== newPw2) { setError('Yeni şifreler eşleşmiyor'); return }
    if (newPw.length < 8) { setError('Yeni şifre en az 8 karakter olmalı'); return }
    setBusy(true); setError('')
    try {
      await api.post('/api/auth/change-password', { current_password: currentPw, new_password: newPw })
      setDone(true)
    } catch (err) {
      setError(typeof err?.detail === 'string' ? err.detail : 'Değiştirilemedi')
    } finally { setBusy(false) }
  }

  return createPortal(
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-sm p-5">
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-lg font-semibold text-gray-100">Şifre Değiştir</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
        </div>

        {done ? (
          <div className="text-center py-4">
            <div className="text-3xl mb-2">✓</div>
            <p className="text-sm text-emerald-400">Şifren güncellendi.</p>
            <button onClick={onClose} className="btn-primary !text-sm mt-3">Kapat</button>
          </div>
        ) : step === 'verify' ? (
          <form onSubmit={verify} className="space-y-3">
            <p className="text-xs text-gray-500">Devam etmek için mevcut şifreni gir.</p>
            <input type="password" value={currentPw} onChange={e => setCurrentPw(e.target.value)}
                   placeholder="Mevcut şifre" className="input w-full" autoFocus required />
            {error && <div className="text-xs text-red-400 bg-red-500/10 rounded p-2">{error}</div>}
            <button type="submit" disabled={busy || !currentPw} className="btn-primary w-full">
              {busy ? 'Kontrol...' : 'Devam'}
            </button>
          </form>
        ) : (
          <form onSubmit={change} className="space-y-3">
            <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)}
                   placeholder="Yeni şifre (min 8)" className="input w-full" autoFocus required />
            <input type="password" value={newPw2} onChange={e => setNewPw2(e.target.value)}
                   placeholder="Yeni şifre (tekrar)" className="input w-full" required />
            {error && <div className="text-xs text-red-400 bg-red-500/10 rounded p-2">{error}</div>}
            <button type="submit" disabled={busy} className="btn-primary w-full">
              {busy ? 'Kaydediliyor...' : 'Şifreyi Güncelle'}
            </button>
          </form>
        )}
      </div>
    </div>,
    document.body
  )
}

function NavItem({ to, label, icon, end = false, disabled = false, legacy = false }) {
  if (disabled) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-700 cursor-not-allowed">
        <span className="w-5 text-center opacity-40">{icon}</span>
        <span>{label}</span>
      </div>
    )
  }
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
          isActive
            ? 'bg-accent/15 text-accent'
            : legacy
              ? 'text-gray-500 hover:bg-brand-input hover:text-gray-300'
              : 'text-gray-400 hover:bg-brand-input hover:text-gray-200'
        }`
      }
    >
      <span className="w-5 text-center">{icon}</span>
      <span className={legacy ? 'italic' : ''}>{label}</span>
    </NavLink>
  )
}
