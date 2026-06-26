import { useEffect, useRef, useState } from 'react'
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

  const [mobileMenu, setMobileMenu] = useState(false)
  const [showSplash, setShowSplash] = useState(() => {
    try { return sessionStorage.getItem('freshLogin') === '1' } catch { return false }
  })
  useEffect(() => {
    if (showSplash) { try { sessionStorage.removeItem('freshLogin') } catch {} }
  }, [])

  return (
    <div className="h-full flex flex-col">
      {showSplash && <SplashScreen onDone={() => setShowSplash(false)} />}
      <header className="border-b border-brand-border bg-brand-card/50 backdrop-blur-md relative z-[60]">
        <div className="px-4 md:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2 md:gap-3">
            <button onClick={() => setMobileMenu(true)} className="md:hidden text-gray-300 hover:text-white p-1 -ml-1" aria-label="Menü">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            </button>
            {tenant?.logo_url ? (
              <img src={tenant.logo_url} alt={tenant?.name || 'Logo'} className="h-11 max-w-[190px] object-contain rounded-lg" />
            ) : (
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-sm font-bold">
                {(tenant?.name || 'B').charAt(0).toUpperCase()}
              </div>
            )}
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
          <NavLinks />


        </aside>

        {mobileMenu && (
          <div className="fixed inset-0 z-[80] md:hidden">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileMenu(false)} />
            <aside className="absolute left-0 top-0 bottom-0 w-64 max-w-[80vw] bg-brand-card border-r border-brand-border p-3 overflow-y-auto">
              <div className="flex items-center justify-between mb-3 px-1">
                <span className="text-sm font-semibold text-gray-200">Menü</span>
                <button onClick={() => setMobileMenu(false)} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
              </div>
              <NavLinks onNavigate={() => setMobileMenu(false)} />
            </aside>
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
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
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-lg shrink-0">⚡</div>
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

function wlBellState() {
  try {
    const s = JSON.parse(localStorage.getItem('wl_state') || '{}')
    const today = new Date().toISOString().slice(0, 10)
    return s.date === today && s.count >= 5 && !s.bellDismissed
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
      const s = JSON.parse(localStorage.getItem('wl_state') || '{}')
      localStorage.setItem('wl_state', JSON.stringify({ ...s, bellDismissed: true }))
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
          <span className="w-8 h-8 rounded-full bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-sm font-semibold">{initial}</span>
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

function NavLinks({ onNavigate }) {
  const { user } = useAuth()
  const role = user?.role || ''
  const isAdmin = role === 'yonetici' || role === 'owner'
  const myPerms = isAdmin ? null : (user?.permissions || [])  // null = hepsi
  const can = (perm) => isAdmin || !perm || myPerms.includes(perm)
  const I = (props) => can(props.perm) ? <NavItem {...props} onNavigate={onNavigate} /> : null

  // Bolum: en az 1 gorunur link varsa basligi goster
  const Section = ({ label, perms }) => (perms.some(can) ? <SectionLabel>{label}</SectionLabel> : null)

  return (
    <nav className="space-y-1 text-sm">
      {user?.is_platform_admin && (
        <>
          <SectionLabel>PLATFORM</SectionLabel>
          <NavItem to="/platform" label="Atölyeler" icon="🏢" onNavigate={onNavigate} />
        </>
      )}
      <I to="/" label="Dashboard" icon="📊" perm="dashboard" end />

      <Section label="SİPARİŞ YÖNETİMİ" perms={['siparisler', 'paketleme', 'destek']} />
      <I to="/orders" label="Siparişler" icon="📦" perm="siparisler" />
      <I to="/paketleme" label="Paketleme" icon="🏷️" perm="paketleme" />
      <I to="/destek" label="Destek" icon="🎧" perm="destek" />
      <I to="/notlar" label="Notlar" icon="📝" perm="siparisler" />
      <I to="/telafiler" label="Telafiler" icon="♻️" perm="siparisler" />

      <Section label="BAYİ YÖNETİMİ" perms={['bayii']} />
      <I to="/bayiler" label="Bayiler" icon="🤝" perm="bayii" />

      <Section label="TASARIM YÖNETİMİ" perms={['tasarim', 'kisiye_ozel', 'aksesuar', 'couple']} />
      <I to="/designs" label="Tasarımlar" icon="🎨" perm="tasarim" />
      <I to="/kisiye-ozel" label="Kişiye Özel" icon="✨" perm="kisiye_ozel" />
      <I to="/aksesuarlar" label="Aksesuarlar" icon="🧷" perm="aksesuar" />
      <I to="/couple" label="Couple Ürünler" icon="👫" perm="couple" />

      <Section label="KALIP YÖNETİMİ" perms={['kalip']} />
      <I to="/kalip-sablon" label="Kalıp Şablonu" icon="🧩" perm="kalip" />
      <I to="/kalip-olustur" label="Kalıp Oluşturucu" icon="🎯" perm="kalip" />
      <I to="/kalip-olustur?tab=existing" label="Oluşturulan Kalıplar" icon="📦" perm="kalip" />
      <I to="/kalip-olustur?tab=old" label="Eski Kalıplar" icon="🗄️" perm="kalip" />
      <I to="/baskici-paneli" label="Baskıcı Paneli" icon="🖨️" perm="kalip" />

      <Section label="STOK YÖNETİMİ" perms={['stok']} />
      <I to="/stok" label="Stok" icon="🗃️" perm="stok" />
      <I to="/aski" label="Askıda Bekleyenler" icon="🎁" perm="stok" />

      <Section label="KATALOG" perms={['telefon_modelleri']} />
      <I to="/telefon-modelleri" label="Telefon Modelleri" icon="📱" perm="telefon_modelleri" />

      <Section label="SİSTEM" perms={['ayarlar']} />
      <I to="/denetim" label="Denetim Kaydı" icon="📜" perm="ayarlar" />
    </nav>
  )
}

function NavItem({ to, label, icon, end = false, disabled = false, legacy = false, onNavigate }) {
  const _loc = useLocation()
  const _toPath = to.split('?')[0]
  const _toTab = (to.split('?')[1] || '').includes('tab=existing')
  const _curTab = new URLSearchParams(_loc.search).get('tab') === 'existing'
  const _tabAware = to.includes('?tab=') || (_toPath === '/kalip-olustur')
  const _forceActive = _tabAware && _loc.pathname === _toPath && (_toTab === _curTab)
  const _forceInactive = _tabAware && _loc.pathname === _toPath && (_toTab !== _curTab)
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
      onClick={() => onNavigate?.()}
      className={({ isActive: _ia }) => { const isActive = _forceInactive ? false : (_forceActive ? true : _ia); return (
        `flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
          isActive
            ? 'bg-accent/15 text-accent'
            : legacy
              ? 'text-gray-500 hover:bg-brand-input hover:text-gray-300'
              : 'text-gray-400 hover:bg-brand-input hover:text-gray-200'
        }` ) }}
    >
      <span className="w-5 text-center">{icon}</span>
      <span className={legacy ? 'italic' : ''}>{label}</span>
    </NavLink>
  )
}
