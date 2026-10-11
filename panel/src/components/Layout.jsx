import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api, setToken } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useStore } from '../lib/store'
import { useToast } from './Toast'
import BrandMark from './BrandMark'
import KomutPaleti from './KomutPaleti'
import { vitrinAdresi } from '../lib/vitrin'
import { BRAND } from '../lib/brand'
import { nativeMi } from '../lib/kamera'
import { platformSifirla } from '../PlatformSecici'

// Shopify yerleşim mantığı: koyu üst bar (marka + mağaza + vitrin linki +
// profil menüsü), solda GRUPLU menü, Ayarlar en altta sabit.
export const NAV_GROUPS = [
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
    { to: '/kilif-sablonlari', label: 'Kılıf Şablonları', icon: '📱' },
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
    { to: '/canli', label: 'Canlı Görünüm', icon: '🌐' },
  ]},
  { label: 'Online Mağaza', items: [
    { to: '/tema', label: 'Tema', icon: '🎨' },
    { to: '/sayfalar', label: 'Sayfalar', icon: '📄' },
    { to: '/blog', label: 'Blog', icon: '✍️' },
    { to: '/uygulamalar', label: 'Uygulamalar', icon: '🧩' },
  ]},
  { label: 'Yönetim', items: [
    { to: '/aktivite', label: 'Aktivite', icon: '🕘' },
    { to: '/abonelik', label: 'Abonelik', icon: '💳' },
  ]},
]

export default function Layout() {
  const { user, tenant, logout, refresh } = useAuth()
  const { stores, store, setStoreId } = useStore()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)  // mobil çekmece
  const [paletAcik, setPaletAcik] = useState(false)

  // ⌘K / Ctrl+K — panelde en sık yapılan iş sipariş aramak
  useEffect(() => {
    const tus = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        setPaletAcik(o => !o)
      }
    }
    window.addEventListener('keydown', tus)
    return () => window.removeEventListener('keydown', tus)
  }, [])

  // Sayfa değişince mobil menü kapansın
  useEffect(() => { setMenuOpen(false) }, [location.pathname])

  // Mobil çekmece: Escape ve telefonun GERİ tuşu menüyü kapatır (sayfadan
  // çıkarmaz) — açılışta geçmişe bir kayıt eklenir, menüden gidilen sayfa
  // `replace` ile o kaydın yerine yazılır. Açıkken arkadaki sayfa kaymaz.
  const menuKapat = () => {
    if (window.history.state?.mobilMenu) window.history.back()
    else setMenuOpen(false)
  }
  useEffect(() => {
    if (!menuOpen) return
    if (!window.history.state?.mobilMenu) {
      window.history.pushState({ ...window.history.state, mobilMenu: true }, '')
    }
    const geri = () => setMenuOpen(false)
    const tus = (e) => { if (e.key === 'Escape') menuKapat() }
    const kok = document.documentElement
    const eskiTasma = kok.style.overflow
    kok.style.overflow = 'hidden'
    window.addEventListener('popstate', geri)
    document.addEventListener('keydown', tus)
    return () => {
      kok.style.overflow = eskiTasma
      window.removeEventListener('popstate', geri)
      document.removeEventListener('keydown', tus)
    }
  }, [menuOpen])  // eslint-disable-line

  const storefrontUrl = vitrinAdresi(store)
  // Beyaz etiket: kiracı kendi adını görür (eskiden herkese "BERNZ Commerce")
  const markaAdi = tenant?.app_name || tenant?.name || BRAND

  return (
    <div className="min-h-screen flex flex-col">
      {/* Üst bar. Cam (bulanıklık) YALNIZ geniş ekranda: telefonda sayfa
          kaydıkça arkası her karede 40px yeniden bulanıklaştırılıyordu —
          kaydırmadaki takılmanın bir kaynağı. Telefonda zemin neredeyse opak.
          box-content: çentik dolgusu 48px'lik yüksekliğin İÇİNDEN yemesin. */}
      {/* Üst bar OPAK, bulanıklık YOK. Eskiden masaüstünde yarı saydam +
          backdrop-blur idi: altındaki aurora sürekli hareket ettiği için
          filtre her karede yeniden hesaplanıyor, menüde "karıncalanma /
          dalgalanma" olarak görünüyordu (2026-10, özellikle Windows). */}
      <header className="box-content h-12 pt-[env(safe-area-inset-top)] shrink-0 flex items-center gap-3 px-3 text-white sticky top-0 z-40
        bg-[#070c2b] border-b border-panel-border">
        {/* Mobil menü düğmesi */}
        <button onClick={() => (menuOpen ? menuKapat() : setMenuOpen(true))} aria-label="Menü" aria-expanded={menuOpen}
          className="lg:hidden w-10 h-10 rounded-lg border border-panel-border flex items-center justify-center text-panel-muted active:bg-white/10">
          {menuOpen ? '✕' : '☰'}
        </button>
        <div className="flex items-center gap-2 pr-2">
          <BrandMark />
          <span className="text-[13px] tracking-tight hidden sm:inline font-bold truncate max-w-[14rem]">
            {markaAdi}
          </span>
        </div>

        {stores.length > 1 ? (
          <select value={store?.id || ''} onChange={e => setStoreId(e.target.value)}
            className="bg-[#0f1535] border border-panel-border text-white/80 text-xs rounded-[10px] px-2 py-1.5
              focus:outline-none focus:border-panel-accent transition-colors">
            {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        ) : (
          <span className="text-xs text-panel-muted bg-white/5 border border-panel-border rounded-[10px] px-2.5 py-1.5">
            🏪 {store?.name || 'Mağaza'}
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => setPaletAcik(true)} aria-label="Ara (⌘K)"
            className="flex items-center gap-2 text-xs text-panel-muted hover:text-white
              border border-panel-border hover:border-white/25 bg-white/5 hover:bg-white/10
              rounded-[10px] px-2.5 py-1.5 transition-all">
            <span aria-hidden="true">🔍</span>
            <span className="hidden md:inline">Ara</span>
            <kbd className="hidden md:inline text-[9px] px-1 py-0.5 rounded bg-white/10
              border border-panel-border">⌘K</kbd>
          </button>
          {storefrontUrl && (
            <a href={storefrontUrl} target="_blank" rel="noopener noreferrer"
              aria-label="Vitrini Gör"
              className="text-xs text-white/80 hover:text-white border border-panel-border
                hover:border-white/25 hover:bg-white/5 rounded-[10px] px-2.5 py-1.5 transition-all
                whitespace-nowrap">
              {/* Telefonda yazı iki satıra kırılıp 48px'lik üst çubuğu taşırıyordu;
                  dar ekranda yalnız ok kalır, erişilebilir ad aria-label'da. */}
              <span className="hidden sm:inline">Vitrini Gör </span>↗
            </a>
          )}
          <ProfileMenu user={user} logout={logout} refresh={refresh} />
        </div>
      </header>

      <KomutPaleti acik={paletAcik} kapat={() => setPaletAcik(false)} />
      <AbonelikBandi abonelik={tenant?.abonelik} />

      <div className="flex-1 flex min-h-0">
        {/* Mobil çekmece örtüsü */}
        {menuOpen && (
          <div className="fixed inset-0 top-[calc(3rem_+_1px_+_env(safe-area-inset-top))] bg-black/40 z-20 lg:hidden"
            onClick={menuKapat} />
        )}
        {/* Sol menü — gruplu; mobilde soldan kayan çekmece.
            Bulanıklık kaldırıldı: arkası sürekli hareket eden aurora olduğu
            için 224px × tam boy, 40px'lik filtre HER KAREDE yeniden hesaplanıyordu.
            Mobilde yükseklik 100vh DEĞİL top+bottom: iOS Safari'de 100vh alt
            araç çubuğunun arkasına uzanıp en alttaki "Ayarlar"ı gizliyordu. */}
        <aside aria-label="Menü" className={`w-56 shrink-0 border-r border-panel-border flex flex-col
          bg-[#070c2b]
          fixed lg:sticky top-[calc(3rem_+_1px_+_env(safe-area-inset-top))] bottom-0 lg:bottom-auto
          lg:h-[calc(100vh_-_3rem_-_1px_-_env(safe-area-inset-top))] z-30
          transition-transform duration-200 lg:translate-x-0
          ${menuOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full'}`}>
          <nav className="flex-1 px-2 py-2 overflow-y-auto overscroll-contain">
            {NAV_GROUPS.map((g, gi) => (
              <div key={gi}>
                {g.label && <div className="nav-group-label">{g.label}</div>}
                {g.items.map(item => (
                  <NavLink key={item.to} to={item.to} end={item.end} replace={menuOpen}
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <span className="nav-icon">{item.icon}</span>
                    {item.label}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          {/* Ayarlar — Shopify gibi en altta sabit */}
          <div className="p-2 pb-[calc(0.5rem_+_env(safe-area-inset-bottom))] lg:pb-2 border-t border-panel-border">
            <NavLink to="/ayarlar" replace={menuOpen}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <span className="nav-icon">⚙️</span>
              Ayarlar
            </NavLink>
          </div>
        </aside>

        {/* İçerik */}
        <main className="flex-1 min-w-0 p-5 pb-[calc(1.25rem_+_env(safe-area-inset-bottom))] overflow-y-auto">
          <div key={location.pathname} className="page-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

// ── Profil menüsü — hesap bilgileri + güvenlik (2FA) + şifre + çıkış ──
function Avatar({ user, size = 'w-7 h-7', ring = true }) {
  const initial = (user?.full_name || user?.email || '?').slice(0, 1).toUpperCase()
  if (user?.avatar_url) {
    return <img src={user.avatar_url} alt="" className={`${size} rounded-full object-cover ${
      ring ? 'ring-1 ring-white/20 group-hover:ring-emerald-500' : ''} transition-all`} />
  }
  return (
    <div className={`${size} rounded-full flex items-center justify-center text-[11px] font-semibold
      bg-gradient-to-br from-slate-600 to-slate-700 ${ring
        ? 'group-hover:from-emerald-600 group-hover:to-teal-700 ring-1 ring-white/20 group-hover:ring-emerald-500'
        : ''} transition-all duration-200 text-white`}>
      {initial}
    </div>
  )
}

function ProfileMenu({ user, logout, refresh }) {
  const [open, setOpen] = useState(false)
  const [modal, setModal] = useState(null)   // null | 'hesap' | 'sifre' | 'guvenlik'
  const ref = useRef(null)

  // Yalnız AÇIKKEN dinle (eskiden her tıklamada kapalı menü için de çalışıyordu);
  // Escape kapatır, pointerdown dokunmatikte gecikmesiz.
  useEffect(() => {
    if (!open) return
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const tus = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', onDoc)
    document.addEventListener('keydown', tus)
    return () => {
      document.removeEventListener('pointerdown', onDoc)
      document.removeEventListener('keydown', tus)
    }
  }, [open])

  const item = (icon, label, onClick, cls = '') => (
    <button onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded-xl hover:bg-panel-input transition-colors flex items-center gap-2.5 ${cls}`}>
      <span>{icon}</span> {label}
    </button>
  )

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)} aria-label="Profil menüsü" aria-expanded={open}
        className="flex items-center gap-2 pl-2 py-1.5 border-l border-panel-border group">
        <Avatar user={user} />
        <span className="hidden sm:block text-[11px] font-medium truncate max-w-32 text-white/80 group-hover:text-white transition-colors">
          {user?.full_name || user?.email}
        </span>
        <span className={`text-panel-muted text-[9px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▼</span>
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
            {item('👤', 'Hesap bilgileri', () => { setModal('hesap'); setOpen(false) })}
            {item('🛡️', <>Güvenlik (2FA) {user?.totp_enabled &&
              <span className="text-[10px] text-emerald-300 bg-emerald-500/10 px-1.5 py-0.5 rounded-full">aktif</span>}</>,
              () => { setModal('guvenlik'); setOpen(false) })}
            {item('🔑', 'Şifre değiştir', () => { setModal('sifre'); setOpen(false) })}
            {/* Uygulamada Studio da aynı pakette; seçiciye dönmenin yolu. */}
            {nativeMi() && item('🔀', 'Platform değiştir', platformSifirla)}
            <div className="my-1 border-t border-panel-border" />
            {item('🚪', 'Çıkış yap', logout, 'text-red-300 hover:!bg-red-500/10')}
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
              className="block text-xs text-red-400 hover:underline">Fotoğrafı kaldır</button>
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
          {error && <p className="text-xs text-red-300">{error}</p>}
          <button disabled={busy} className="w-full px-4 py-2 rounded-xl text-sm font-medium
            bg-red-500/10 text-red-300 border border-red-500/30 hover:bg-red-500/20 disabled:opacity-50">
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
          {error && <p className="text-xs text-red-300">{error}</p>}
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
          {error && <p className="text-xs text-red-300">{error}</p>}
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
      // Parola degisince sunucu ESKI oturumlari dusuruyor; taze token'i
      // saklamazsak kullanici kendi kendini cikartir.
      const _r = await api.post('/api/auth/change-password', { current_password: current, new_password: next })
      if (_r?.access_token) setToken(_r.access_token)
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
        {error && <p className="text-xs text-red-300">{error}</p>}
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

// Kiralama: abonelik uyarı bandı.
//
// Sunucu ödeme durumunu /api/auth/me ile bildiriyor (services/abonelik.py).
// Bant yalnız söylenecek bir şey varsa çıkar: bitişe 5 gün kala nazik
// hatırlatma, sonra giderek sertleşen üç aşama. Salt-okunur dönemde
// panel değişiklikleri sunucu tarafında zaten 402 ile reddediliyor —
// bant, müşteri o hatayı görmeden NEDENİNİ söylemek için.
const BANT_TONU = {
  aktif:       'bg-sky-500/10 border-sky-500/30 text-sky-300',
  ek_sure:     'bg-amber-500/10 border-amber-500/30 text-amber-300',
  salt_okunur: 'bg-orange-500/15 border-orange-500/40 text-orange-300',
  askida:      'bg-red-500/15 border-red-500/40 text-red-300',
}
const BANT_IKONU = { aktif: '🗓️', ek_sure: '⏳', salt_okunur: '🔒', askida: '⛔' }

function AbonelikBandi({ abonelik }) {
  if (!abonelik?.mesaj) return null
  const asama = abonelik.asama in BANT_TONU ? abonelik.asama : 'ek_sure'
  return (
    <div role="status"
      className={`shrink-0 border-b px-4 py-2 text-xs flex items-center gap-2 ${BANT_TONU[asama]}`}>
      <span aria-hidden="true">{BANT_IKONU[asama]}</span>
      <span className="flex-1">{abonelik.mesaj}</span>
      <NavLink to="/abonelik" className="underline underline-offset-2 whitespace-nowrap hover:opacity-80">
        Ödeme bilgileri →
      </NavLink>
    </div>
  )
}
