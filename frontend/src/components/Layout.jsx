import { useEffect, useMemo, useRef, useState } from 'react'
import SplashScreen from './SplashScreen'
import { createPortal } from 'react-dom'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'

export default function Layout() {
  const { user, tenant, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const location = useLocation()
  const [mobileMenu, setMobileMenu] = useState(false)
  const [cmdOpen, setCmdOpen] = useState(false)
  const [showSplash, setShowSplash] = useState(() => {
    try { return sessionStorage.getItem('freshLogin') === '1' } catch { return false }
  })
  useEffect(() => {
    if (showSplash) { try { sessionStorage.removeItem('freshLogin') } catch {} }
  }, [])
  // ⌘K / Ctrl+K -> komut paleti
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault(); setCmdOpen(o => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="h-full flex flex-col">
      <AppBackground />
      {showSplash && <SplashScreen onDone={() => setShowSplash(false)} />}
      {cmdOpen && <CommandPalette onClose={() => setCmdOpen(false)} />}

      {/* ÜST MENÜ — yatay, bölüm dropdown'lı */}
      <header className="sticky top-0 z-[60] border-b border-brand-border/70 bg-brand-bg/95 pt-[env(safe-area-inset-top)]">
        <div className="px-3 md:px-5 h-14 flex items-center gap-2 md:gap-3">
          <button onClick={() => setMobileMenu(true)} className="md:hidden text-gray-300 hover:text-white p-1 -ml-1" aria-label="Menü">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>

          <div className="flex items-center gap-2 shrink-0">
            {tenant?.logo_url ? (
              <img src={tenant.logo_url} alt={tenant?.name || 'Logo'} className="h-9 max-w-[150px] object-contain rounded-lg" />
            ) : (
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-teal-600 flex items-center justify-center text-[#04130d] text-sm font-bold shrink-0"
                   style={{ boxShadow: '0 6px 18px -6px rgb(var(--accent-rgb) / 0.6)' }}>
                {(tenant?.name || 'B').charAt(0).toUpperCase()}
              </div>
            )}
            <span className="hidden lg:block text-sm font-semibold text-gray-100 tracking-tight">{tenant?.app_name || tenant?.name || 'Baskıcı'}</span>
          </div>

          <DesktopNav />

          <div className="ml-auto flex items-center gap-1 shrink-0">
            <button onClick={() => setCmdOpen(true)} title="Ara (⌘K)"
              className="hidden md:flex items-center gap-2 px-2.5 h-9 rounded-full bg-brand-input/60 border border-brand-border text-gray-400 hover:text-gray-200 text-xs transition-colors">
              <span>🔍</span><span className="hidden lg:inline">Ara</span>
              <kbd className="hidden lg:inline text-[10px] px-1.5 py-0.5 rounded bg-brand-bg/70 border border-brand-border text-gray-500">⌘K</kbd>
            </button>
            <SyncButton />
            <NotificationBell />
            <ProfileDropdown user={user} onLogout={handleLogout} />
          </div>
        </div>
      </header>

      {mobileMenu && <MobileNav onClose={() => setMobileMenu(false)} />}

      <main className="flex-1 overflow-y-auto p-4 md:p-6">
        <div key={location.pathname} className="mx-auto w-full max-w-[1400px] page-enter">
          <Outlet />
        </div>
      </main>
      <InstallPrompt />
    </div>
  )
}

function InstallPrompt() {
  const [deferred, setDeferred] = useState(null)   // Android beforeinstallprompt eventi
  const [showIos, setShowIos] = useState(false)
  const [hidden, setHidden] = useState(() => {
    try { return localStorage.getItem('pwa_install_dismissed') === '1' } catch { return false }
  })

  useEffect(() => {
    // Zaten standalone (yüklü) ise hiç gösterme
    const standalone = window.matchMedia?.('(display-mode: standalone)').matches
      || window.navigator.standalone === true
    if (standalone) { setHidden(true); return }

    const onBip = (e) => { e.preventDefault(); setDeferred(e) }
    window.addEventListener('beforeinstallprompt', onBip)

    // iOS Safari: beforeinstallprompt yok, elle ipucu göster
    const ua = window.navigator.userAgent || ''
    const isIos = /iphone|ipad|ipod/i.test(ua)
    const isSafari = isIos && /safari/i.test(ua) && !/crios|fxios/i.test(ua)
    if (isSafari) setShowIos(true)

    return () => window.removeEventListener('beforeinstallprompt', onBip)
  }, [])

  const dismiss = () => {
    setHidden(true)
    try { localStorage.setItem('pwa_install_dismissed', '1') } catch {}
  }

  const install = async () => {
    if (!deferred) return
    deferred.prompt()
    try { await deferred.userChoice } catch {}
    setDeferred(null)
    dismiss()
  }

  if (hidden) return null
  if (!deferred && !showIos) return null

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[90] w-[92%] max-w-md animate-fadein">
      <div className="bg-brand-card border border-brand-border rounded-xl shadow-2xl p-3 flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent to-teal-600 flex items-center justify-center text-white text-lg shrink-0">⚡</div>
        <div className="min-w-0 flex-1">
          {deferred ? (
            <>
              <div className="text-sm text-gray-100 font-medium">Uygulamayı ana ekrana ekle</div>
              <div className="text-[11px] text-gray-500">Hızlı erişim için telefonuna kur</div>
            </>
          ) : (
            <>
              <div className="text-sm text-gray-100 font-medium">Ana ekrana ekle</div>
              <div className="text-[11px] text-gray-500">Paylaş <span className="font-semibold">⎙</span> → "Ana Ekrana Ekle"</div>
            </>
          )}
        </div>
        {deferred && (
          <button onClick={install} className="btn-primary !text-xs px-3 shrink-0">Kur</button>
        )}
        <button onClick={dismiss} className="text-gray-500 hover:text-gray-300 text-sm leading-none shrink-0 px-1">✕</button>
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

const WL_BELL_KEY = 'wl_bell'  // {date, shown, dismissed} — dashboard ziyaretinden bagimsiz

function wlBellState() {
  try {
    const s = JSON.parse(localStorage.getItem(WL_BELL_KEY) || '{}')
    const today = new Date().toISOString().slice(0, 10)
    return s.date === today && s.shown && !s.dismissed
  } catch { return false }
}

function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const [wlBadge, setWlBadge] = useState(() => wlBellState())
  const ref = useRef(null)
  const seenSupportIds = useRef(null)

  const playBeep = () => {
    try {
      const AC = window.AudioContext || window.webkitAudioContext
      if (!AC) return
      const ctx = new AC()
      const o = ctx.createOscillator(), g = ctx.createGain()
      o.type = 'sine'; o.frequency.value = 880
      o.connect(g); g.connect(ctx.destination)
      g.gain.setValueAtTime(0.0001, ctx.currentTime)
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.02)
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35)
      o.start(); o.stop(ctx.currentTime + 0.36)
      o.onended = () => ctx.close()
    } catch {}
  }

  const load = async () => {
    try {
      const r = await api.get('/api/notifications?limit=30')
      const list = r.items || []
      setItems(list)
      setUnread(r.unread_count || 0)
      const supportIds = list
        .filter(n => (n.title || '').toLowerCase().includes('destek mesaj'))
        .map(n => n.id)
      if (seenSupportIds.current === null) {
        seenSupportIds.current = new Set(supportIds)
      } else {
        const fresh = supportIds.some(id => !seenSupportIds.current.has(id))
        seenSupportIds.current = new Set(supportIds)
        if (fresh) playBeep()
      }
    } catch {}
  }

  useEffect(() => { load() }, [])
  // Worklist zili — dashboard ziyaretinden BAGIMSIZ: gun icinde ilk yuklemede
  // worklist'i cek; yapilacak is varsa (items>0) zili goster. Gun basina 1 kez.
  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10)
    let st = {}
    try { st = JSON.parse(localStorage.getItem(WL_BELL_KEY) || '{}') } catch {}
    if (st.date === today && st.dismissed) return        // bugun kullanici kapatti
    if (st.date === today && st.shown) { setWlBadge(true); return }  // bugun zaten gosterildi
    api.get('/api/dashboard/worklist').then(wl => {
      if (((wl && wl.items) || []).length > 0) {
        setWlBadge(true)
        localStorage.setItem(WL_BELL_KEY, JSON.stringify({ date: today, shown: true, dismissed: false }))
      }
    }).catch(() => {})
  }, [])
  // 60 sn'de bir + senk sonrası tazele
  useEffect(() => {
    const t = setInterval(load, 20000)
    const onRefresh = () => load()
    const onWl = () => setWlBadge(true)
    window.addEventListener('notifications:refresh', onRefresh)
    window.addEventListener('worklist:ready', onWl)
    return () => {
      clearInterval(t)
      window.removeEventListener('notifications:refresh', onRefresh)
      window.removeEventListener('worklist:ready', onWl)
    }
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

  const icon = k => k === 'error' ? '⚠' : k === 'info' ? 'ℹ' : k === 'worklist' ? '📋' : '🔄'

  const dismissWlBadge = () => {
    setWlBadge(false)
    try {
      const today = new Date().toISOString().slice(0, 10)
      localStorage.setItem(WL_BELL_KEY, JSON.stringify({ date: today, shown: true, dismissed: true }))
    } catch {}
  }

  const totalUnread = unread + (wlBadge ? 1 : 0)

  return (
    <div className="relative" ref={ref}>
      <button onClick={openPanel} title="Bildirimler"
        className="relative p-2 rounded-lg hover:bg-brand-input text-gray-400 hover:text-gray-200">
        <span className="text-lg">🔔</span>
        {totalUnread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-semibold flex items-center justify-center">
            {totalUnread > 9 ? '9+' : totalUnread}
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
            {wlBadge && (
              <button onClick={() => { dismissWlBadge(); window.location.href = '/?worklist=1' }}
                className="w-full text-left px-3 py-2.5 border-b border-brand-border/50 hover:bg-brand-input flex gap-2 bg-accent/5">
                <span className="text-base shrink-0">📋</span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-gray-100 leading-snug font-medium">☀️ Günaydın! Bugünün worklist'i hazır</div>
                  <div className="text-[11px] text-gray-400 mt-0.5">Dashboard'a git →</div>
                </div>
              </button>
            )}
            {items.length === 0 && !wlBadge ? (
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
  const _nav = useNavigate()
  const can = usePerm()
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
        {user?.avatar_url ? (
          <img src={user.avatar_url} alt="" className="w-8 h-8 rounded-full object-cover" />
        ) : (
          <span className="w-8 h-8 rounded-full bg-gradient-to-br from-accent to-teal-600 flex items-center justify-center text-white text-sm font-semibold">{initial}</span>
        )}
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
          <button onClick={() => { _nav('/ayarlar'); setOpen(false) }} className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-brand-input flex items-center gap-2">
            <span className="w-5 text-center">⚙</span> Ayarlar
          </button>
          {can('ayarlar') && (
            <button onClick={() => { _nav('/stores'); setOpen(false) }} className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-brand-input flex items-center gap-2">
              <span className="w-5 text-center">🏬</span> Atölyeler
            </button>
          )}
          {can('ayarlar') && (
            <button onClick={() => { _nav('/denetim'); setOpen(false) }} className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-brand-input flex items-center gap-2">
              <span className="w-5 text-center">📜</span> Denetim Kaydı
            </button>
          )}
          <div className="border-t border-brand-border my-1" />
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
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 p-4"
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

// ─── Üst menü verisi: bölümler + öğeler (perm bazlı) ───
const NAV = [
  { label: 'Dashboard', to: '/', icon: '📊', perm: 'dashboard', end: true },
  { label: 'Analitik', icon: '📈', items: [
    { to: '/analitik', label: 'Analitik', icon: '📈', perm: 'dashboard' },
    { to: '/pazarlama', label: 'Pazarlama', icon: '📣', perm: 'pazarlama' },
    { to: '/musteriler', label: 'Müşteriler', icon: '👥', perm: 'musteri' },
  ] },
  { label: 'Sipariş', icon: '📦', items: [
    { to: '/orders', label: 'Siparişler', icon: '📦', perm: 'siparisler' },
    { to: '/paketleme', label: 'Paketleme', icon: '🏷️', perm: 'paketleme' },
    { to: '/destek', label: 'Destek', icon: '🎧', perm: 'destek' },
    { to: '/notlar', label: 'Notlar', icon: '📝', perm: 'siparisler' },
    { to: '/telafiler', label: 'Telafiler', icon: '♻️', perm: 'siparisler' },
  ] },
  { label: 'Bayi', icon: '🤝', items: [
    { to: '/bayiler', label: 'Bayiler', icon: '🤝', perm: 'bayii' },
  ] },
  { label: 'Tasarım', icon: '🎨', items: [
    { to: '/designs', label: 'Tasarımlar', icon: '🎨', perm: 'tasarim' },
    { to: '/varyantli-urunler', label: 'Varyantlı Ürünler', icon: '🎭', perm: 'tasarim' },
    { to: '/urun-studyosu', label: 'Ürün Stüdyosu', icon: '🎨', perm: 'tasarim' },
    { to: '/kisiye-ozel', label: 'Kişiye Özel', icon: '✨', perm: 'kisiye_ozel' },
    { to: '/aksesuarlar', label: 'Aksesuarlar', icon: '🧷', perm: 'aksesuar' },
    { to: '/couple', label: 'Couple Ürünler', icon: '👫', perm: 'couple' },
  ] },
  { label: 'Kalıp', icon: '🧩', items: [
    { to: '/kalip-sablon', label: 'Kalıp Şablonu', icon: '🧩', perm: 'kalip' },
    { to: '/kalip-olustur', label: 'Kalıp Oluşturucu', icon: '🎯', perm: 'kalip' },
    { to: '/kalip-olustur?tab=existing', label: 'Oluşturulan Kalıplar', icon: '📦', perm: 'kalip' },
    { to: '/kalip-olustur?tab=old', label: 'Eski Kalıplar', icon: '🗄️', perm: 'kalip' },
    { to: '/baskici-paneli', label: 'Baskıcı Paneli', icon: '🖨️', perm: 'kalip' },
    // Stok + Telefon Modelleri — kalıp iş akışının alt kalemleri
    { to: '/stok', label: 'Stok', icon: '🗃️', perm: 'stok' },
    { to: '/aski', label: 'Askıda Bekleyenler', icon: '🎁', perm: 'stok' },
    { to: '/telefon-modelleri', label: 'Telefon Modelleri', icon: '📱', perm: 'telefon_modelleri' },
  ] },
  // Not: "Denetim Kaydı" ve "Atölyeler" üst menüde değil — profil menüsünde (sağ üst).
]

function usePerm() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'yonetici' || user?.role === 'owner'
  const perms = isAdmin ? null : (user?.permissions || [])
  return (perm) => isAdmin || !perm || (perms || []).includes(perm)
}

// Görünür menü: perm filtresi; tek öğeli bölüm doğrudan linke iner; boş bölüm gizlenir.
function visibleNav(can) {
  const out = []
  for (const sec of NAV) {
    if (sec.to) { if (can(sec.perm)) out.push(sec); continue }
    const its = (sec.items || []).filter(it => can(it.perm))
    if (its.length === 0) continue
    if (its.length === 1) out.push({ ...its[0] })
    else out.push({ ...sec, items: its })
  }
  return out
}

// Tüm pencerelerde yumuşak hareketli yeşil/teal ışıma (içerik arkasında, etkileşimsiz)
function AppBackground() {
  // Not: 'blur-3xl' (filter) + sürekli transform animasyonu çok pahalıydı (her karede
  // yeniden raster). Radial gradient'in kendisi zaten yumuşak; blur yok → animasyon
  // sadece GPU-compositing (ucuz). Akıcılık korunur.
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden="true">
      <div className="login-blob absolute -top-40 -left-32 w-[40rem] h-[40rem] rounded-full opacity-[0.18]"
        style={{ background: 'radial-gradient(circle, rgb(var(--accent-rgb) / 0.9) 0%, transparent 68%)' }} />
      <div className="login-blob absolute top-1/3 -right-48 w-[44rem] h-[44rem] rounded-full opacity-[0.13]"
        style={{ background: 'radial-gradient(circle, #22d3ee 0%, transparent 68%)', animationDelay: '6s' }} />
      <div className="login-blob absolute -bottom-48 left-1/4 w-[36rem] h-[36rem] rounded-full opacity-[0.14]"
        style={{ background: 'radial-gradient(circle, rgb(var(--accent-rgb) / 0.9) 0%, transparent 68%)', animationDelay: '11s' }} />
    </div>
  )
}

// ⌘K komut paleti — sayfalar + sipariş no + kalıp kodu araması
function CommandPalette({ onClose }) {
  const can = usePerm()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [idx, setIdx] = useState(0)
  const [remote, setRemote] = useState({ orders: [], molds: [] })
  const [loading, setLoading] = useState(false)

  const pages = useMemo(() => {
    const items = []
    for (const e of visibleNav(can)) {
      if (e.to) items.push({ to: e.to, label: e.label, icon: e.icon, group: 'Sayfa' })
      else for (const it of e.items) items.push({ to: it.to, label: it.label, icon: it.icon, group: e.label })
    }
    if (can('ayarlar')) items.push(
      { to: '/ayarlar', label: 'Ayarlar', icon: '⚙', group: 'Sistem' },
      { to: '/denetim', label: 'Denetim Kaydı', icon: '📜', group: 'Sistem' },
    )
    return items
  }, [])  // eslint-disable-line

  // Sipariş no + kalıp kodu için backend araması (debounced)
  useEffect(() => {
    const s = q.trim()
    if (s.length < 2) { setRemote({ orders: [], molds: [] }); setLoading(false); return }
    setLoading(true)
    const t = setTimeout(async () => {
      try { setRemote(await api.get(`/api/search?q=${encodeURIComponent(s)}`)) }
      catch { setRemote({ orders: [], molds: [] }) }
      finally { setLoading(false) }
    }, 250)
    return () => clearTimeout(t)
  }, [q])

  const results = useMemo(() => {
    const s = q.trim().toLowerCase()
    const pageHits = s ? pages.filter(i => (i.label + ' ' + i.group).toLowerCase().includes(s)) : pages
    const orderHits = (remote.orders || []).map(o => ({
      to: `/orders/${o.id}`, icon: '📦', group: 'Sipariş',
      label: o.name || `#${o.order_number}`, sub: o.customer || '',
    }))
    const moldHits = (remote.molds || []).map(m => ({
      to: `/kalip/${m.id}`, icon: '🧩', group: 'Kalıp',
      label: m.kod, sub: m.variation || '',
    }))
    return [...pageHits, ...orderHits, ...moldHits]
  }, [q, pages, remote])

  useEffect(() => { setIdx(0) }, [q, remote])
  const go = (i) => { const r = results[i]; if (r) { navigate(r.to); onClose() } }
  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setIdx(i => Math.min(i + 1, results.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setIdx(i => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); go(idx) }
    else if (e.key === 'Escape') { onClose() }
  }

  let lastGroup = null
  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-start justify-center pt-[12vh] px-4 bg-black/60"
      onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="w-full max-w-lg bg-brand-card border border-brand-border rounded-2xl shadow-2xl overflow-hidden menu-pop">
        <div className="flex items-center gap-2 px-4 border-b border-brand-border">
          <span className="text-gray-500">🔍</span>
          <input autoFocus value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey}
            placeholder="Sayfa, sipariş no veya kalıp kodu ara…"
            className="flex-1 bg-transparent py-3 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none" />
          {loading && <span className="text-[11px] text-gray-500 animate-pulse">…</span>}
          <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-brand-input border border-brand-border text-gray-500">esc</kbd>
        </div>
        <div className="max-h-80 overflow-y-auto p-1.5">
          {results.length === 0 ? (
            <div className="px-3 py-6 text-center text-sm text-gray-500">{q.trim() ? 'Sonuç yok' : 'Aramaya başla…'}</div>
          ) : results.map((r, i) => {
            const showGroup = r.group !== lastGroup; lastGroup = r.group
            return (
              <div key={r.to + r.label + i}>
                {showGroup && <div className="text-[9px] uppercase tracking-wider text-gray-600 px-2.5 pt-2 pb-1">{r.group}</div>}
                <button onMouseEnter={() => setIdx(i)} onClick={() => go(i)}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-left text-[13px] transition-colors ${
                    i === idx ? 'bg-accent/15 text-accent' : 'text-gray-300 hover:bg-brand-input/70'
                  }`}>
                  <span className="w-7 h-7 rounded-lg bg-brand-input/70 flex items-center justify-center shrink-0">{r.icon}</span>
                  <span className="flex-1 truncate">{r.label}</span>
                  {r.sub && <span className="text-[10px] text-gray-500 truncate max-w-[40%]">{r.sub}</span>}
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>, document.body)
}

// Üst yatay menü (masaüstü)
function DesktopNav() {
  const can = usePerm()
  const items = visibleNav(can)
  return (
    <nav className="hidden md:flex items-center gap-0.5 overflow-x-auto no-scrollbar flex-1 min-w-0 px-1">
      {items.map(e => e.items
        ? <NavDropdown key={e.label} entry={e} />
        : <TopLink key={e.to} to={e.to} label={e.label} icon={e.icon} end={e.end} />)}
    </nav>
  )
}

function TopLink({ to, label, icon, end }) {
  return (
    <NavLink to={to} end={end}
      className={({ isActive }) => `flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] whitespace-nowrap shrink-0 transition-colors ${
        isActive ? 'bg-accent/15 text-accent font-medium' : 'text-gray-400 hover:text-gray-100 hover:bg-brand-input/60'
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

  // Menü, üst menünün overflow'una takılmasın diye portal + sabit konum (button rect'ten)
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
  useEffect(() => { setOpen(false) }, [loc.pathname, loc.search])

  return (
    <>
      <button ref={btnRef} onClick={toggle} onMouseEnter={hoverOpen} onMouseLeave={hoverClose}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] whitespace-nowrap shrink-0 transition-colors ${
          active || open ? 'bg-accent/15 text-accent font-medium' : 'text-gray-400 hover:text-gray-100 hover:bg-brand-input/60'
        }`}>
        <span className="text-[13px]">{entry.icon}</span>{entry.label}
        <span className={`text-[8px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>
      {open && pos && createPortal(
        <div ref={menuRef} style={{ position: 'fixed', left: pos.left, top: pos.top }}
          onMouseEnter={() => clearTimeout(closeTimer.current)} onMouseLeave={hoverClose}
          className="w-56 bg-brand-card border border-brand-border rounded-2xl shadow-2xl p-1.5 z-[200] menu-pop">
          {entry.items.map(it => <DropItem key={it.to} {...it} onClick={() => setOpen(false)} />)}
        </div>, document.body)}
    </>
  )
}

function DropItem({ to, label, icon, end, legacy, onClick }) {
  return (
    <NavLink to={to} end={end} onClick={onClick}
      className={({ isActive }) => `group flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-[13px] transition-colors ${
        isActive ? 'bg-accent/15 text-accent' : 'text-gray-300 hover:bg-brand-input/70 hover:text-gray-100'
      }`}>
      {({ isActive }) => (
        <>
          <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-[13px] shrink-0 transition-colors ${
            isActive ? 'bg-accent/20' : 'bg-brand-input/70 group-hover:bg-brand-input'
          }`}>{icon}</span>
          <span className={legacy ? 'italic' : ''}>{label}</span>
        </>
      )}
    </NavLink>
  )
}

// Mobil çekmece (dikey, bölümlü)
function MobileNav({ onClose }) {
  const can = usePerm()
  const items = visibleNav(can)
  return (
    <div className="fixed inset-0 z-[80] md:hidden">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <aside className="absolute left-0 top-0 bottom-0 w-72 max-w-[82vw] bg-brand-card border-r border-brand-border px-3 pb-3 pt-[calc(0.75rem_+_env(safe-area-inset-top))] overflow-y-auto animate-slidein">
        <div className="flex items-center justify-between mb-3 px-1">
          <span className="text-sm font-semibold text-gray-100">Menü</span>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        <nav className="space-y-1">
          {items.map(e => e.items ? (
            <div key={e.label} className="mb-1">
              <SectionLabel>{e.label}</SectionLabel>
              {e.items.map(it => <DropItem key={it.to} {...it} onClick={onClose} />)}
            </div>
          ) : (
            <DropItem key={e.to} {...e} onClick={onClose} />
          ))}
        </nav>
      </aside>
    </div>
  )
}
