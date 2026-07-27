import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useStore } from '../lib/store'
import { useToast } from './Toast'
import BrandMark from './BrandMark'

// BİRLEŞİK MENÜ — baskıcı paneliyle aynı dil: üst yatay bar + "hap" (pill)
// bölümler + dropdown. Tek öğeli bölüm doğrudan linke iner, boş bölüm gizlenir.
// (Ayarlar üst menüde değil — sağ üstteki profil menüsünde.)
const NAV = [
  { label: 'Ana Sayfa', to: '/', icon: '🏠', end: true },
  { label: 'Satış', icon: '📦', items: [
    { to: '/siparisler', label: 'Siparişler', icon: '📦' },
    { to: '/terk-sepetler', label: 'Terk Sepetler', icon: '🛒' },
  ] },
  { label: 'Katalog', icon: '🛍️', items: [
    { to: '/urunler', label: 'Ürünler', icon: '🛍️' },
    { to: '/koleksiyonlar', label: 'Koleksiyonlar', icon: '🗂️' },
    { to: '/envanter', label: 'Envanter', icon: '📋' },
  ] },
  { label: 'Müşteri', icon: '👥', items: [
    { to: '/musteriler', label: 'Müşteriler', icon: '👥' },
    { to: '/yorumlar', label: 'Yorumlar', icon: '⭐' },
    { to: '/tasarim-talepleri', label: 'Tasarım Talepleri', icon: '🖌️' },
  ] },
  { label: 'Pazarlama', icon: '📣', items: [
    { to: '/kuponlar', label: 'İndirimler', icon: '🎟️' },
    { to: '/analitik', label: 'Analitik', icon: '📈' },
  ] },
  { label: 'Online Mağaza', icon: '🎨', items: [
    { to: '/tema', label: 'Tema', icon: '🎨' },
    { to: '/sayfalar', label: 'Sayfalar', icon: '📄' },
    { to: '/blog', label: 'Blog', icon: '✍️' },
    { to: '/uygulamalar', label: 'Uygulamalar', icon: '🧩' },
  ] },
]

// Tek öğeli bölümü doğrudan linke indir (ana paneldeki visibleNav ile aynı mantık)
function flatNav() {
  return NAV.map(sec => (sec.to || (sec.items || []).length > 1)
    ? sec
    : { ...(sec.items || [])[0] })
}

export default function Layout() {
  const { user, logout, refresh } = useAuth()
  const { stores, store, setStoreId } = useStore()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)  // mobil çekmece

  // Sayfa değişince mobil menü kapansın
  useEffect(() => { setMenuOpen(false) }, [location.pathname])

  const storefrontUrl = store?.config?.storefront_url
    || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : null)

  return (
    <div className="min-h-screen flex flex-col">
      {/* ÜST MENÜ — baskıcı paneliyle aynı: yatay, bölüm dropdown'lı */}
      <header className="sticky top-0 z-[60] border-b border-panel-border/70 bg-panel-bg/95 backdrop-blur pt-[env(safe-area-inset-top)]">
        <div className="px-3 md:px-5 h-14 flex items-center gap-2 md:gap-3">
          <button onClick={() => setMenuOpen(true)} aria-label="Menü"
            className="md:hidden text-panel-muted hover:text-panel-ink p-1 -ml-1">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>

          <div className="flex items-center gap-2 shrink-0">
            <BrandMark />
            <span className="hidden lg:block text-sm font-semibold tracking-tight text-panel-ink">
              BERNZ <span className="text-panel-accent font-light">Commerce</span>
            </span>
          </div>

          <DesktopNav />

          <div className="ml-auto flex items-center gap-2 shrink-0">
            {stores.length > 1 ? (
              <select value={store?.id || ''} onChange={e => setStoreId(e.target.value)}
                className="bg-panel-input/60 border border-panel-border text-panel-ink text-xs rounded-full px-2.5 h-9
                  focus:outline-none focus:border-panel-accent">
                {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            ) : (
              <span className="hidden sm:flex items-center h-9 text-xs text-panel-muted bg-panel-input/60 border border-panel-border rounded-full px-3">
                🏪 {store?.name || 'Mağaza'}
              </span>
            )}
            {storefrontUrl && (
              <a href={storefrontUrl} target="_blank" rel="noopener noreferrer" title="Vitrini yeni sekmede aç"
                className="hidden sm:flex items-center h-9 text-xs text-panel-muted hover:text-panel-ink bg-panel-input/60 border border-panel-border hover:border-panel-accent/50 rounded-full px-3 transition-colors">
                Vitrini Gör ↗
              </a>
            )}
            <ProfileMenu user={user} logout={logout} refresh={refresh} />
          </div>
        </div>
      </header>

      {menuOpen && <MobileNav onClose={() => setMenuOpen(false)} />}

      {/* İçerik */}
      <main className="flex-1 overflow-y-auto p-4 md:p-6">
        <div key={location.pathname} className="mx-auto w-full max-w-[1400px] page-in">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

// ── Üst yatay menü (masaüstü) ──
function DesktopNav() {
  return (
    <nav className="hidden md:flex items-center gap-0.5 overflow-x-auto no-scrollbar flex-1 min-w-0 px-1">
      {flatNav().map(e => e.items
        ? <NavDropdown key={e.label} entry={e} />
        : <TopLink key={e.to} {...e} />)}
    </nav>
  )
}

function TopLink({ to, label, icon, end }) {
  return (
    <NavLink to={to} end={end}
      className={({ isActive }) => `flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] whitespace-nowrap shrink-0 transition-colors ${
        isActive ? 'bg-panel-accent/15 text-panel-accent font-medium' : 'text-panel-muted hover:text-panel-ink hover:bg-panel-input/60'
      }`}>
      <span className="text-[13px]">{icon}</span>{label}
    </NavLink>
  )
}

function NavDropdown({ entry }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState(null)
  const btnRef = useRef(null)
  const menuRef = useRef(null)
  const loc = useLocation()
  const active = entry.items.some(it => loc.pathname === it.to.split('?')[0])
  const closeTimer = useRef(null)

  const place = () => {
    const b = btnRef.current?.getBoundingClientRect()
    if (b) setPos({ left: Math.max(8, Math.min(b.left, window.innerWidth - 232)), top: b.bottom + 8 })
  }
  const toggle = () => { if (!open) place(); setOpen(o => !o) }
  const hoverOpen = () => { clearTimeout(closeTimer.current); place(); setOpen(true) }
  const hoverClose = () => { closeTimer.current = setTimeout(() => setOpen(false), 130) }

  useEffect(() => {
    if (!open) return
    const onDoc = e => {
      if (btnRef.current?.contains(e.target) || menuRef.current?.contains(e.target)) return
      setOpen(false)
    }
    const onReposition = () => place()
    document.addEventListener('mousedown', onDoc)
    window.addEventListener('resize', onReposition)
    window.addEventListener('scroll', onReposition, true)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      window.removeEventListener('resize', onReposition)
      window.removeEventListener('scroll', onReposition, true)
    }
  }, [open])
  useEffect(() => { setOpen(false) }, [loc.pathname])

  return (
    <>
      <button ref={btnRef} onClick={toggle} onMouseEnter={hoverOpen} onMouseLeave={hoverClose}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] whitespace-nowrap shrink-0 transition-colors ${
          active || open ? 'bg-panel-accent/15 text-panel-accent font-medium' : 'text-panel-muted hover:text-panel-ink hover:bg-panel-input/60'
        }`}>
        <span className="text-[13px]">{entry.icon}</span>{entry.label}
        <span className={`text-[8px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>
      {open && pos && createPortal(
        <div ref={menuRef} style={{ position: 'fixed', left: pos.left, top: pos.top }}
          onMouseEnter={() => clearTimeout(closeTimer.current)} onMouseLeave={hoverClose}
          className="w-56 bg-panel-card border border-panel-border rounded-2xl shadow-2xl p-1.5 z-[200] menu-pop">
          {entry.items.map(it => <DropItem key={it.to} {...it} onClick={() => setOpen(false)} />)}
        </div>, document.body)}
    </>
  )
}

function DropItem({ to, label, icon, end, onClick }) {
  return (
    <NavLink to={to} end={end} onClick={onClick}
      className={({ isActive }) => `group flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-[13px] transition-colors ${
        isActive ? 'bg-panel-accent/15 text-panel-accent' : 'text-panel-muted hover:bg-panel-input/70 hover:text-panel-ink'
      }`}>
      {({ isActive }) => (
        <>
          <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-[13px] shrink-0 transition-colors ${
            isActive ? 'bg-panel-accent/20' : 'bg-panel-input/70 group-hover:bg-panel-input'
          }`}>{icon}</span>
          <span>{label}</span>
        </>
      )}
    </NavLink>
  )
}

// ── Mobil çekmece (dikey, bölümlü) — ana panelle aynı ──
function MobileNav({ onClose }) {
  return (
    <div className="fixed inset-0 z-[80] md:hidden">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <aside className="absolute left-0 top-0 bottom-0 w-72 max-w-[82vw] bg-panel-card border-r border-panel-border px-3 pb-3 pt-[calc(0.75rem_+_env(safe-area-inset-top))] overflow-y-auto animate-slidein">
        <div className="flex items-center justify-between mb-3 px-1">
          <span className="text-sm font-semibold text-panel-ink">Menü</span>
          <button onClick={onClose} className="text-panel-muted hover:text-panel-ink text-2xl leading-none">×</button>
        </div>
        <nav className="space-y-1">
          {flatNav().map(e => e.items ? (
            <div key={e.label} className="mb-1">
              <div className="nav-group-label">{e.label}</div>
              {e.items.map(it => <DropItem key={it.to} {...it} onClick={onClose} />)}
            </div>
          ) : (
            <DropItem key={e.to} {...e} onClick={onClose} />
          ))}
          <div className="mt-2 pt-2 border-t border-panel-border">
            <DropItem to="/ayarlar" label="Ayarlar" icon="⚙️" onClick={onClose} />
          </div>
        </nav>
      </aside>
    </div>
  )
}

// ── Profil menüsü — hesap bilgileri + güvenlik (2FA) + şifre + çıkış ──
function Avatar({ user, size = 'w-7 h-7', ring = true }) {
  const initial = (user?.full_name || user?.email || '?').slice(0, 1).toUpperCase()
  if (user?.avatar_url) {
    return <img src={user.avatar_url} alt="" className={`${size} rounded-full object-cover ${
      ring ? 'ring-1 ring-slate-600 group-hover:ring-emerald-500' : ''} transition-all`} />
  }
  return (
    <div className={`${size} rounded-full flex items-center justify-center text-[11px] font-semibold
      bg-gradient-to-br from-slate-600 to-slate-700 ${ring
        ? 'group-hover:from-emerald-600 group-hover:to-teal-700 ring-1 ring-slate-600 group-hover:ring-emerald-500'
        : ''} transition-all duration-200 text-white`}>
      {initial}
    </div>
  )
}

function ProfileMenu({ user, logout, refresh }) {
  const [open, setOpen] = useState(false)
  const [modal, setModal] = useState(null)   // null | 'hesap' | 'sifre' | 'guvenlik'
  const ref = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const item = (icon, label, onClick, cls = '') => (
    <button onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded-xl hover:bg-panel-input transition-colors flex items-center gap-2.5 ${cls}`}>
      <span>{icon}</span> {label}
    </button>
  )

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 pl-2 border-l border-slate-700 group">
        <Avatar user={user} />
        <span className="hidden sm:block text-[11px] font-medium truncate max-w-32 text-slate-300 group-hover:text-white transition-colors">
          {user?.full_name || user?.email}
        </span>
        <span className={`text-slate-500 text-[9px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-64 bg-panel-card text-panel-ink rounded-2xl
          border border-panel-border shadow-xl overflow-hidden toast-in z-50">
          <div className="px-4 py-3 bg-panel-input/60 border-b border-panel-border flex items-center gap-2.5">
            <Avatar user={user} size="w-9 h-9" ring={false} />
            <div className="min-w-0">
              <div className="text-sm font-semibold truncate">{user?.full_name || '—'}</div>
              <div className="text-xs text-panel-muted truncate">{user?.email}</div>
            </div>
          </div>
          <div className="p-1.5 text-sm">
            {/* Ayarlar artık sol menüde değil — ana paneldeki gibi profil menüsünde */}
            {item('⚙️', 'Mağaza ayarları', () => { navigate('/ayarlar'); setOpen(false) })}
            <div className="my-1 border-t border-panel-border" />
            {item('👤', 'Hesap bilgileri', () => { setModal('hesap'); setOpen(false) })}
            {item('🛡️', <>Güvenlik (2FA) {user?.totp_enabled &&
              <span className="text-[10px] text-emerald-300 bg-emerald-500/10 px-1.5 py-0.5 rounded-full">aktif</span>}</>,
              () => { setModal('guvenlik'); setOpen(false) })}
            {item('🔑', 'Şifre değiştir', () => { setModal('sifre'); setOpen(false) })}
            <div className="my-1 border-t border-panel-border" />
            {item('🚪', 'Çıkış yap', logout, 'text-red-400 hover:!bg-red-500/10')}
          </div>
        </div>
      )}

      {modal === 'hesap' && (
        <AccountModal user={user} refresh={refresh} onClose={() => setModal(null)} />
      )}
      {modal === 'sifre' && <PasswordModal user={user} onClose={() => setModal(null)} />}
      {modal === 'guvenlik' && (
        <SecurityModal user={user} refresh={refresh} onClose={() => setModal(null)} />
      )}
    </div>
  )
}

function ModalShell({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-6"
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-panel-card text-panel-ink rounded-2xl shadow-xl w-full max-w-sm p-5 toast-in">
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

  const uploadAvatar = async (file) => {
    if (!file) return
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      await api.postForm('/api/tenant/avatar', fd)
      await refresh?.()
      toast.success('Profil fotoğrafı güncellendi')
    } catch (e2) {
      toast.error(typeof e2?.detail === 'string' ? e2.detail : 'Fotoğraf yüklenemedi')
    } finally { setBusy(false) }
  }

  const removeAvatar = async () => {
    setBusy(true)
    try { await api.del('/api/tenant/avatar'); await refresh?.() }
    catch { toast.error('Kaldırılamadı') }
    finally { setBusy(false) }
  }

  return (
    <ModalShell title="👤 Hesap Bilgileri" onClose={onClose}>
      {/* Profil fotoğrafı */}
      <div className="flex items-center gap-3 mb-4">
        <Avatar user={user} size="w-14 h-14" ring={false} />
        <div className="space-y-1">
          <label className="btn-ghost !py-1.5 text-xs cursor-pointer inline-block">
            {busy ? 'Yükleniyor…' : '📷 Fotoğraf seç'}
            <input type="file" accept="image/*" className="hidden" disabled={busy}
              onChange={e => uploadAvatar(e.target.files?.[0])} />
          </label>
          {user?.avatar_url && (
            <button onClick={removeAvatar} disabled={busy}
              className="block text-xs text-red-500 hover:underline">Fotoğrafı kaldır</button>
          )}
        </div>
      </div>
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

// 2FA (authenticator) kurulum/kapatma — backend: /api/auth/2fa/*
function SecurityModal({ user, refresh, onClose }) {
  const toast = useToast()
  const [setup, setSetup] = useState(null)     // {qr, secret} — kurulum adımı
  const [code, setCode] = useState('')
  const [backupCodes, setBackupCodes] = useState(null)
  const [disablePw, setDisablePw] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const start = async () => {
    setBusy(true); setError('')
    try { setSetup(await api.post('/api/auth/2fa/setup', {})) }
    catch (e) { setError(typeof e?.detail === 'string' ? e.detail : 'Kurulum başlatılamadı') }
    finally { setBusy(false) }
  }

  const enable = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const r = await api.post('/api/auth/2fa/enable', { code: code.trim() })
      setBackupCodes(r.backup_codes || [])
      await refresh?.()
      toast.success('2FA aktif 🛡️')
    } catch (e2) {
      setError(typeof e2?.detail === 'string' ? e2.detail : 'Kod doğrulanamadı')
    } finally { setBusy(false) }
  }

  const disable = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await api.post('/api/auth/2fa/disable', { password: disablePw })
      await refresh?.()
      toast.success('2FA kapatıldı')
      onClose()
    } catch (e2) {
      setError(typeof e2?.detail === 'string' ? e2.detail : 'Kapatılamadı')
    } finally { setBusy(false) }
  }

  return (
    <ModalShell title="🛡️ Güvenlik" onClose={onClose}>
      {backupCodes ? (
        <div className="space-y-3">
          <p className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-xl px-3 py-2">
            Yedek kodlarınızı güvenli bir yere kaydedin — telefonunuza erişemezseniz
            bu kodlarla giriş yaparsınız. <b>Bir daha gösterilmez.</b>
          </p>
          <div className="grid grid-cols-2 gap-1.5 font-mono text-sm bg-panel-input rounded-xl p-3">
            {backupCodes.map(c => <span key={c}>{c}</span>)}
          </div>
          <button onClick={() => { navigator.clipboard?.writeText(backupCodes.join('\n')); toast.success('Kopyalandı') }}
            className="btn-ghost w-full !py-2 text-xs">📋 Kodları Kopyala</button>
          <button onClick={onClose} className="btn-primary w-full">Tamam, kaydettim</button>
        </div>
      ) : user?.totp_enabled ? (
        <form onSubmit={disable} className="space-y-3">
          <p className="text-sm text-emerald-300 bg-emerald-500/10 rounded-xl px-3 py-2">
            ✓ İki adımlı doğrulama <b>aktif</b> — girişte authenticator kodu isteniyor.
          </p>
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Kapatmak için şifreniz</span>
            <input className="input mt-1" type="password" value={disablePw} required
              onChange={e => setDisablePw(e.target.value)} />
          </label>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button disabled={busy} className="w-full px-4 py-2 rounded-xl text-sm font-medium
            bg-red-500/10 text-red-300 border border-red-500/30 hover:bg-red-500/150/20 disabled:opacity-50">
            {busy ? '…' : '2FA\'yı Kapat'}
          </button>
        </form>
      ) : setup ? (
        <form onSubmit={enable} className="space-y-3">
          <p className="text-xs text-panel-muted">
            1. Google Authenticator / Authy ile QR'ı okutun. 2. Uygulamadaki 6 haneli kodu girin.
          </p>
          <img src={setup.qr} alt="2FA QR" className="w-40 h-40 mx-auto rounded-xl border border-panel-border" />
          <p className="text-[10px] text-panel-muted text-center font-mono break-all">
            Elle kurulum: {setup.secret}
          </p>
          <input className="input font-mono text-center tracking-widest" value={code}
            required maxLength={6} placeholder="000000" autoFocus
            onChange={e => setCode(e.target.value.replace(/\D/g, ''))} />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button disabled={busy || code.length !== 6} className="btn-primary w-full">
            {busy ? 'Doğrulanıyor…' : 'Doğrula ve Aktifleştir'}
          </button>
        </form>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-panel-muted">
            İki adımlı doğrulama (2FA), şifreniz çalınsa bile hesabınızı korur —
            girişte telefonunuzdaki authenticator uygulamasının kodu istenir.
          </p>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button onClick={start} disabled={busy} className="btn-primary w-full">
            {busy ? 'Hazırlanıyor…' : '🛡️ 2FA Kurulumunu Başlat'}
          </button>
        </div>
      )}
    </ModalShell>
  )
}

function PasswordModal({ user, onClose }) {
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [next2, setNext2] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [mailSent, setMailSent] = useState(false)

  // Mevcut şifreyi hatırlamayanlar için: e-postaya sıfırlama bağlantısı
  const sendResetMail = async () => {
    setBusy(true); setError('')
    try {
      await api.post('/api/auth/forgot-password', { email: user?.email })
      setMailSent(true)
      toast.success('Sıfırlama bağlantısı e-postanıza gönderildi 📧')
    } catch {
      setError('E-posta gönderilemedi — SMTP ayarlarını kontrol edin')
    } finally { setBusy(false) }
  }

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
        {error && <p className="text-xs text-red-400">{error}</p>}
        <button disabled={busy} className="btn-primary w-full">
          {busy ? 'Güncelleniyor…' : 'Şifreyi Güncelle'}
        </button>
        <div className="text-center pt-1 border-t border-panel-border">
          {mailSent ? (
            <p className="text-xs text-emerald-300 pt-2">
              📧 Bağlantı gönderildi — gelen kutunuzu kontrol edin (1 saat geçerli).
            </p>
          ) : (
            <button type="button" onClick={sendResetMail} disabled={busy}
              className="text-xs text-panel-muted hover:text-panel-ink underline pt-2">
              Mevcut şifremi hatırlamıyorum — e-postama sıfırlama bağlantısı gönder
            </button>
          )}
        </div>
      </form>
    </ModalShell>
  )
}
