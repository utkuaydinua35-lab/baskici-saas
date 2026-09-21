import { useEffect, useMemo, useRef, useState } from 'react'
import SplashScreen from './SplashScreen'
import { createPortal } from 'react-dom'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { api, setToken } from '../lib/api'
import { nativeMi, platformSifirla, uygulamaYolu, kabugaDon } from '../lib/taban'
import { worklistGetir } from '../lib/worklist'

export default function Layout() {
  const { user, tenant, logout } = useAuth()
  // Senkron TUM magazalari cekiyor (agir is + Shopify kotasi); ucu artik
  // "siparisler" izni istiyor. Dugmeyi de ayni izne bagliyoruz ki izinsiz
  // kullanici gorup 403 almasin.
  const _yonetici = user?.role === 'yonetici' || user?.role === 'owner'
  const canSync = _yonetici || (user?.permissions || []).includes('siparisler')
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    // Uygulamada giriş kabuğun ortak adımı — Studio'nun kendi login'i değil.
    if (nativeMi()) { kabugaDon(); return }
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
          {/* 30×30'du — telefonda menüyü açmanın TEK yolu, 44×44 olmalı */}
          <button onClick={() => setMobileMenu(true)} aria-label="Menü" aria-expanded={mobileMenu}
            className="md:hidden -ml-2 w-11 h-11 flex items-center justify-center rounded-xl text-gray-300 hover:text-white active:bg-brand-input/70">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>

          <div className="flex items-center gap-2 shrink-0">
            {tenant?.logo_url ? (
              <img src={tenant.logo_url} alt={tenant?.name || 'Logo'} className="h-9 max-w-[150px] object-contain rounded-lg" />
            ) : (
              <div style={{ color: 'var(--accent-fg)' }}
                   className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-accent/55 flex items-center justify-center text-sm font-bold shrink-0"
                   style={{ boxShadow: '0 6px 18px -6px rgb(var(--accent-rgb) / 0.6)' }}>
                {(tenant?.name || 'B').charAt(0).toUpperCase()}
              </div>
            )}
            <span className="hidden lg:block text-sm font-semibold text-gray-100 tracking-tight">{tenant?.app_name || tenant?.name || 'Baskıcı'}</span>
          </div>

          <DesktopNav />

          <div className="ml-auto flex items-center gap-1 shrink-0">
            {/* Telefonda arama HİÇ yoktu (⌘K klavye ister) — dar ekranda yalnız ikon */}
            <button onClick={() => setCmdOpen(true)} title="Ara (⌘K)" aria-label="Ara"
              className="flex items-center justify-center gap-2 w-10 h-11 rounded-lg active:bg-brand-input/70 md:w-auto md:h-9 md:px-2.5 md:rounded-full md:bg-brand-input/60 md:border md:border-brand-border text-gray-400 hover:text-gray-200 text-xs transition-colors">
              <span>🔍</span><span className="hidden lg:inline">Ara</span>
              <kbd className="hidden lg:inline text-[10px] px-1.5 py-0.5 rounded bg-brand-bg/70 border border-brand-border text-gray-500">⌘K</kbd>
            </button>
            {canSync && <SyncButton />}
            <NotificationBell />
            <ProfileDropdown user={user} onLogout={handleLogout} />
          </div>
        </div>
      </header>

      {mobileMenu && <MobileNav onClose={() => setMobileMenu(false)} onSearch={() => setCmdOpen(true)} />}

      <main className="flex-1 overflow-y-auto p-4 md:p-6 pb-[calc(1rem_+_env(safe-area-inset-bottom))] md:pb-[calc(1.5rem_+_env(safe-area-inset-bottom))]">
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
    <div className="fixed bottom-[calc(1rem_+_env(safe-area-inset-bottom))] left-1/2 -translate-x-1/2 z-[90] w-[92%] max-w-md animate-fadein">
      <div className="bg-brand-card border border-brand-border rounded-xl shadow-2xl p-3 flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent to-accent/55 flex items-center justify-center text-white text-lg shrink-0">⚡</div>
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
        <button onClick={dismiss} aria-label="Kapat" className="w-9 h-9 -mr-1 flex items-center justify-center text-gray-500 hover:text-gray-300 text-sm leading-none shrink-0">✕</button>
      </div>
    </div>
  )
}

// Üst çubuktaki açılır paneller (bildirim, senkron sonucu).
// Sağa hizalı 320px'lik panel telefonda ekranın SOLUNDAN taşıyordu (-24px);
// dar ekranda başlığın altına tam genişlik yayılır, sm ve üstünde düğmeye hizalı.
const ACILIR_PANEL = 'fixed inset-x-2 top-[calc(env(safe-area-inset-top)_+_3.75rem)] sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-1'

// Açılır panel: dışarı dokununca, Escape'e basınca ve sayfa değişince kapanır.
// mousedown yerine pointerdown — dokunmatikte gecikmesiz.
function useAcilirKapat(ref, open, setOpen) {
  const loc = useLocation()
  useEffect(() => { setOpen(false) }, [loc.pathname, loc.search])  // eslint-disable-line
  useEffect(() => {
    if (!open) return
    const disari = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const tus = e => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', disari)
    document.addEventListener('keydown', tus)
    return () => {
      document.removeEventListener('pointerdown', disari)
      document.removeEventListener('keydown', tus)
    }
  }, [open])  // eslint-disable-line
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
      <button onClick={run} disabled={busy} title="Tüm mağazaları senkronize et" aria-label="Senkronize et"
        className="w-10 h-11 flex items-center justify-center rounded-lg hover:bg-brand-input active:bg-brand-input text-gray-400 hover:text-gray-200 disabled:opacity-50">
        <span className={`inline-block text-lg ${busy ? 'animate-spin' : ''}`}>🔄</span>
      </button>
      {msg && (
        <div className={`${ACILIR_PANEL} sm:w-64 text-xs rounded-lg px-3 py-2 shadow-2xl z-[70] border bg-brand-card ${
          msg.ok ? 'border-emerald-500/30 text-emerald-200' : 'border-red-500/30 text-red-300'
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

  const imza = useRef('')
  const istekte = useRef(false)
  const load = async () => {
    if (istekte.current) return          // önceki istek dönmeden yenisini atma
    istekte.current = true
    try {
      const r = await api.get('/api/notifications?limit=30')
      const list = r.items || []
      // Her turda yeni dizi = zil ve açık panel boşuna yeniden çiziliyordu.
      // Liste aynıysa (id + okundu + sayaç) durum hiç ellenmez.
      const yeniImza = `${r.unread_count || 0}|${list.map(n => `${n.id}:${n.is_read ? 1 : 0}`).join(',')}`
      if (yeniImza !== imza.current) {
        imza.current = yeniImza
        setItems(list)
        setUnread(r.unread_count || 0)
      }
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
    } catch {} finally { istekte.current = false }
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
    worklistGetir().then(wl => {
      if (((wl && wl.items) || []).length > 0) {
        setWlBadge(true)
        localStorage.setItem(WL_BELL_KEY, JSON.stringify({ date: today, shown: true, dismissed: false }))
      }
    }).catch(() => {})
  }, [])
  // Görünür sekmede 30 sn'de bir, arka plandaki sekmede 2 dk'da bir tazele —
  // eskiden gizli sekmede de 20 sn'de bir istek atıyordu. Sekmeye dönünce
  // hemen tazeler; destek mesajı sesi bu sayede gecikmez. + senk sonrası.
  useEffect(() => {
    let t = null
    const kur = () => {
      clearInterval(t)
      t = setInterval(load, document.hidden ? 120000 : 30000)
    }
    const gorunurluk = () => { if (!document.hidden) load(); kur() }
    kur()
    const onRefresh = () => load()
    const onWl = () => setWlBadge(true)
    document.addEventListener('visibilitychange', gorunurluk)
    window.addEventListener('notifications:refresh', onRefresh)
    window.addEventListener('worklist:ready', onWl)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', gorunurluk)
      window.removeEventListener('notifications:refresh', onRefresh)
      window.removeEventListener('worklist:ready', onWl)
    }
  }, [])
  useAcilirKapat(ref, open, setOpen)

  const openPanel = () => { setOpen(o => !o); if (!open) load() }

  const markRead = async (id) => {
    try { await api.patch(`/api/notifications/${id}/read`, {}) ; load() } catch {}
  }
  // Bildirime tıkla → okundu işaretle + ilgili sayfaya git (revizyon/onay → kişiye özel,
  // destek mesajı → o talep). link yoksa sadece okundu olur.
  const openNotif = (n) => {
    markRead(n.id)
    if (n.link) { setOpen(false); window.location.href = uygulamaYolu(n.link) }
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
      <button onClick={openPanel} title="Bildirimler" aria-label="Bildirimler" aria-expanded={open}
        className="relative w-10 h-11 flex items-center justify-center rounded-lg hover:bg-brand-input active:bg-brand-input text-gray-400 hover:text-gray-200">
        <span className="text-lg">🔔</span>
        {totalUnread > 0 && (
          <span className="absolute top-1 right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-semibold flex items-center justify-center">
            {totalUnread > 9 ? '9+' : totalUnread}
          </span>
        )}
      </button>
      {open && (
        <div className={`${ACILIR_PANEL} sm:w-80 bg-brand-card border border-brand-border rounded-lg shadow-2xl z-[70] overflow-hidden menu-pop`}>
          <div className="flex items-center justify-between px-3 py-2 border-b border-brand-border">
            <span className="text-sm font-medium text-gray-200">Bildirimler</span>
            {unread > 0 && (
              <button onClick={markAll} className="text-[11px] text-accent hover:underline py-1.5">Tümünü okundu işaretle</button>
            )}
          </div>
          <div className="max-h-[min(24rem,calc(100dvh_-_9rem))] overflow-y-auto overscroll-contain">
            {wlBadge && (
              <button onClick={() => { dismissWlBadge(); window.location.href = uygulamaYolu('/?worklist=1') }}
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
              <button key={n.id} onClick={() => openNotif(n)}
                title={n.link ? 'İlgili sayfaya git' : undefined}
                className={`w-full text-left px-3 py-2 border-b border-brand-border/50 hover:bg-brand-input flex gap-2 ${
                  n.is_read ? 'opacity-55' : ''
                }`}>
                <span className="text-base shrink-0">{icon(n.kind)}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-gray-200 leading-snug">{n.title}</div>
                  {n.body && <div className="text-[11px] text-gray-500 mt-0.5 truncate">{n.body}</div>}
                  <div className="text-[10px] text-gray-600 mt-0.5">
                    {fmtTime(n.created_at)}{n.link && <span className="text-accent ml-1.5">· aç →</span>}
                  </div>
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
  useAcilirKapat(ref, open, setOpen)
  const initial = (user?.full_name || user?.email || '?').charAt(0).toUpperCase()
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)} aria-label="Profil menüsü" aria-expanded={open}
        className="flex items-center gap-2 px-1.5 sm:px-2 h-11 rounded-lg hover:bg-brand-input active:bg-brand-input transition-colors">
        {user?.avatar_url ? (
          <img src={user.avatar_url} alt="" className="w-8 h-8 rounded-full object-cover" />
        ) : (
          <span className="w-8 h-8 rounded-full bg-gradient-to-br from-accent to-accent/55 flex items-center justify-center text-white text-sm font-semibold">{initial}</span>
        )}
        {/* Tablette (768-1024) isim menüyü sıkıştırıp öğeleri ekran dışına itiyordu */}
        <span className="text-xs text-gray-300 hidden lg:block max-w-[10rem] truncate">{user?.full_name || user?.email}</span>
        <span className="text-gray-500 text-xs">⌄</span>
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-56 bg-brand-card border border-brand-border rounded-lg shadow-2xl z-[70] py-1 menu-pop">
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
          {/* Uygulamada BERNZ Commerce de aynı pakette; seçiciye dönüş. */}
          {nativeMi() && (
            <button onClick={platformSifirla} className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-brand-input flex items-center gap-2">
              <span className="w-5 text-center">🔀</span> Platform değiştir
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
      // Parola degisince sunucu ESKI oturumlari dusuruyor; taze token'i
      // saklamazsak kullanici kendi kendini cikartir.
      const _r = await api.post('/api/auth/change-password', { current_password: currentPw, new_password: newPw })
      if (_r?.access_token) setToken(_r.access_token)
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
    { to: '/sosyal-medya', label: 'Sosyal Medya', icon: '📸', perm: 'pazarlama' },
    { to: '/musteriler', label: 'Müşteriler', icon: '👥', perm: 'musteri' },
  ] },
  { label: 'Sipariş', icon: '📦', items: [
    { to: '/orders', label: 'Siparişler', icon: '📦', perm: 'siparisler' },
    { to: '/paketleme', label: 'Paketleme', icon: '🏷️', perm: 'paketleme' },
    { to: '/destek', label: 'Destek', icon: '🎧', perm: 'destek' },
    { to: '/telafiler', label: 'Telafiler', icon: '♻️', perm: 'siparisler' },
  ] },
  { label: 'Bayi', icon: '🤝', items: [
    { to: '/bayiler', label: 'Bayiler', icon: '🤝', perm: 'bayii' },
    { to: '/bayi-siparisleri', label: 'Bayi Siparişleri', icon: '🧾', perm: 'bayii' },
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
    { to: '/ozel-seri-stok', label: 'BERNZ Special Stok', icon: '✨', perm: 'stok' },
  ] },
  // Not: "Denetim Kaydı" ve "Atölyeler" üst menüde değil — profil menüsünde (sağ üst).
]

function usePerm() {
  const { user } = useAuth()
  // Sunucu artık PLANA göre süzülmüş gerçek yetkileri gönderiyor. Onu esas
  // al: eskiden "owner ise her şeyi göster" deniyordu ve Basic planlı bir
  // kiracının owner'ı kalıp/üretim/bayi menülerini görüp tıklayınca 403
  // alıyordu. effective_permissions yoksa (eski sunucu) eski davranış.
  const etkin = user?.effective_permissions
  if (Array.isArray(etkin)) return (perm) => !perm || etkin.includes(perm)
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
      { to: '/ayarlar/etiket', label: 'Etiket Şablonu', icon: '🏷', group: 'Sistem' },
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
  const ref = useRef(null)
  const [kenar, setKenar] = useState('')
  // Tablet genişliğinde menü sığmıyor ve kaydırma çubuğu gizli — sağda öğe
  // olduğu hiç anlaşılmıyordu. Taşan kenar yumuşakça solar. Değer aynıysa
  // React yeniden çizmez; ölçüm kaydırma başına ucuz.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const olc = () => {
      const sol = el.scrollLeft > 2
      const sag = el.scrollLeft + el.clientWidth < el.scrollWidth - 2
      setKenar(sol && sag ? 'iki' : sol ? 'sol' : sag ? 'sag' : '')
    }
    olc()
    const ro = new ResizeObserver(olc)
    ro.observe(el)
    el.addEventListener('scroll', olc, { passive: true })
    return () => { ro.disconnect(); el.removeEventListener('scroll', olc) }
  }, [])
  // Fare tekerleği dikey döner; taşan menüde yatay kaydırmaya çevrilir.
  const tekerlek = (e) => {
    const el = ref.current
    if (el && e.deltaY && el.scrollWidth > el.clientWidth) el.scrollLeft += e.deltaY
  }
  return (
    <nav ref={ref} onWheel={tekerlek}
      className={`hidden md:flex items-center gap-0.5 overflow-x-auto no-scrollbar flex-1 min-w-0 px-1 ${kenar ? `ust-menu-solgun-${kenar}` : ''}`}>
      {items.map(e => e.items
        ? <NavDropdown key={e.label} entry={e} />
        : <TopLink key={e.to} to={e.to} label={e.label} icon={e.icon} end={e.end} />)}
    </nav>
  )
}

function TopLink({ to, label, icon, end }) {
  return (
    <NavLink to={to} end={end}
      className={({ isActive }) => `flex items-center gap-1.5 px-2.5 lg:px-3 py-1.5 rounded-full text-[13px] whitespace-nowrap shrink-0 transition-colors ${
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
  const closeTimer = useRef(null)
  const fareIleAcildi = useRef(false)
  const loc = useLocation()
  const active = entry.items.some(it => loc.pathname === it.to.split('?')[0])

  // Menü, üst menünün overflow'una takılmasın diye portal + sabit konum (button rect'ten).
  // Konum değişmediyse durum ellenmez: sayfa kaydırıldıkça her olayda yeniden
  // çizim yapılıyordu (dinleyici capture modunda TÜM kaydırmaları duyuyor).
  const place = () => {
    const b = btnRef.current?.getBoundingClientRect()
    if (!b) return
    const left = Math.round(Math.max(8, Math.min(b.left, window.innerWidth - 232)))
    const top = Math.round(b.bottom + 8)
    setPos(p => (p && p.left === left && p.top === top) ? p : { left, top })
  }
  // Aynı anda tek menü: fare bir bölümden ötekine geçerken eskisi beklemeden
  // kapanır, iki menü üst üste binmez.
  const ac = () => {
    clearTimeout(closeTimer.current)
    place()
    if (!open) window.dispatchEvent(new CustomEvent('ustmenu:acildi', { detail: entry.label }))
    setOpen(true)
  }
  // Üzerine gelince açılma YALNIZ FAREDE. Dokunmatikte parmak önce "enter"
  // (aç) sonra "click" (kapat) üretiyordu — menü açılıp anında kapanıyordu.
  const hoverOpen = (e) => {
    if (e.pointerType !== 'mouse') return
    if (!open) fareIleAcildi.current = true
    ac()
  }
  const hoverClose = (e) => {
    if (e.pointerType !== 'mouse') return
    clearTimeout(closeTimer.current)
    closeTimer.current = setTimeout(() => setOpen(false), 150)
  }
  const toggle = () => {
    // Fareyle üzerine gelip açılmış menüye tıklamak onu KAPATMASIN.
    if (open && fareIleAcildi.current) { fareIleAcildi.current = false; return }
    fareIleAcildi.current = false
    if (open) setOpen(false)
    else ac()
  }

  useEffect(() => {
    const baskasiAcildi = e => { if (e.detail !== entry.label) { clearTimeout(closeTimer.current); setOpen(false) } }
    window.addEventListener('ustmenu:acildi', baskasiAcildi)
    return () => { window.removeEventListener('ustmenu:acildi', baskasiAcildi); clearTimeout(closeTimer.current) }
  }, [entry.label])

  useEffect(() => {
    if (!open) { fareIleAcildi.current = false; return }
    const onDoc = e => {
      if (btnRef.current?.contains(e.target) || menuRef.current?.contains(e.target)) return
      setOpen(false)
    }
    const onKey = e => { if (e.key === 'Escape') { setOpen(false); btnRef.current?.focus() } }
    document.addEventListener('pointerdown', onDoc)
    document.addEventListener('keydown', onKey)
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      document.removeEventListener('pointerdown', onDoc)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [open])
  useEffect(() => { setOpen(false) }, [loc.pathname, loc.search])

  return (
    <>
      <button ref={btnRef} onClick={toggle} onPointerEnter={hoverOpen} onPointerLeave={hoverClose}
        aria-haspopup="menu" aria-expanded={open}
        className={`flex items-center gap-1.5 px-2.5 lg:px-3 py-1.5 rounded-full text-[13px] whitespace-nowrap shrink-0 transition-colors ${
          active || open ? 'bg-accent/15 text-accent font-medium' : 'text-gray-400 hover:text-gray-100 hover:bg-brand-input/60'
        }`}>
        <span className="text-[13px]">{entry.icon}</span>{entry.label}
        <span className={`text-[8px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>
      {open && pos && createPortal(
        <div ref={menuRef} style={{ position: 'fixed', left: pos.left, top: pos.top }}
          onPointerEnter={() => clearTimeout(closeTimer.current)} onPointerLeave={hoverClose}
          className="w-56 max-h-[calc(100dvh_-_5rem)] overflow-y-auto overscroll-contain bg-brand-card border border-brand-border rounded-2xl shadow-2xl p-1.5 z-[200] menu-pop">
          {entry.items.map(it => <DropItem key={it.to} {...it} onClick={() => setOpen(false)} />)}
        </div>, document.body)}
    </>
  )
}

function DropItem({ to, label, icon, end, legacy, replace, onClick }) {
  return (
    <NavLink to={to} end={end} replace={replace} onClick={onClick}
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

const MOBIL_BOLUM_KEY = 'mobil_menu_bolumler'

// Mobil çekmece (dikey, bölümlü)
function MobileNav({ onClose, onSearch }) {
  const can = usePerm()
  const items = visibleNav(can)
  const loc = useLocation()
  const [kapaniyor, setKapaniyor] = useState(false)
  const bitti = useRef(false)

  // Bölümler katlanabilir; kullanıcının açık bıraktıkları hatırlanır. İlk
  // kullanımda hepsi açık (bugünkü görünüm). Bulunulan sayfanın bölümü hep açık.
  const aktifBolum = items.find(e => e.items?.some(it => it.to.split('?')[0] === loc.pathname))?.label
  const [acik, setAcik] = useState(() => {
    let kayitli = null
    try { kayitli = JSON.parse(localStorage.getItem(MOBIL_BOLUM_KEY) || 'null') } catch {}
    const s = new Set(Array.isArray(kayitli) ? kayitli : items.filter(e => e.items).map(e => e.label))
    if (aktifBolum) s.add(aktifBolum)
    return s
  })
  const bolumDegistir = (ad) => setAcik(prev => {
    const s = new Set(prev)
    s.has(ad) ? s.delete(ad) : s.add(ad)
    try { localStorage.setItem(MOBIL_BOLUM_KEY, JSON.stringify([...s])) } catch {}
    return s
  })

  // Kapanış kısa bir kayma animasyonuyla — anında kaybolmak "takıldı" hissi veriyordu.
  const bitir = () => {
    if (bitti.current) return
    bitti.current = true
    setKapaniyor(true)
    setTimeout(onClose, 180)
  }
  // Telefonun GERİ tuşu menüyü kapatsın, sayfadan çıkarmasın: açılışta geçmişe
  // bir kayıt eklenir; ×/örtü/Escape o kaydı geri alır. Menüden bir sayfaya
  // gidilince bağlantı `replace` ile o kaydın YERİNE yazılır — geri tuşu yine
  // menüyü açtığın sayfaya döner.
  const kapatIste = () => {
    if (window.history.state?.mobilMenu) window.history.back()
    else bitir()
  }
  useEffect(() => {
    // Kayıt zaten varsa ikinci kez ekleme (geliştirmede efekt iki kez çalışır;
    // fazladan kayıt geri tuşunu bir kez "boşa" bastırırdı).
    if (!window.history.state?.mobilMenu) {
      window.history.pushState({ ...window.history.state, mobilMenu: true }, '')
    }
    const geri = () => bitir()
    const tus = e => { if (e.key === 'Escape') kapatIste() }
    window.addEventListener('popstate', geri)
    document.addEventListener('keydown', tus)
    return () => {
      window.removeEventListener('popstate', geri)
      document.removeEventListener('keydown', tus)
    }
  }, [])  // eslint-disable-line

  const ara = () => { kapatIste(); onSearch?.() }

  return (
    <div className="fixed inset-0 z-[80] md:hidden" role="dialog" aria-modal="true" aria-label="Menü">
      <div className={`absolute inset-0 bg-black/60 ${kapaniyor ? 'cekmece-ortu-cik' : 'cekmece-ortu-gir'}`} onClick={kapatIste} />
      <aside className={`absolute left-0 top-0 bottom-0 w-72 max-w-[82vw] flex flex-col bg-brand-card border-r border-brand-border shadow-2xl ${kapaniyor ? 'cekmece-cik' : 'cekmece-gir'}`}>
        <div className="flex items-center justify-between gap-2 pl-4 pr-2 pt-[calc(0.25rem_+_env(safe-area-inset-top))] pb-1 border-b border-brand-border/60">
          <span className="text-sm font-semibold text-gray-100">Menü</span>
          <button onClick={kapatIste} aria-label="Menüyü kapat"
            className="w-11 h-11 flex items-center justify-center rounded-xl text-gray-400 hover:text-gray-200 active:bg-brand-input/70 text-2xl leading-none">×</button>
        </div>
        <button onClick={ara}
          className="mx-3 mt-3 flex items-center gap-2 h-11 px-3 rounded-xl bg-brand-input/60 border border-brand-border text-sm text-gray-500 text-left">
          <span>🔍</span><span className="truncate">Sayfa, sipariş no veya kalıp ara…</span>
        </button>
        <nav className="flex-1 overflow-y-auto overscroll-contain px-3 pt-2 pb-[calc(0.75rem_+_env(safe-area-inset-bottom))]">
          {items.map(e => e.items ? (
            <div key={e.label} className="mt-1">
              <button onClick={() => bolumDegistir(e.label)} aria-expanded={acik.has(e.label)}
                className="w-full h-10 flex items-center justify-between px-2 rounded-lg text-[10px] font-medium uppercase tracking-wider text-gray-500 active:bg-brand-input/50">
                <span>{e.label}</span>
                <span className={`text-[8px] transition-transform duration-200 ${acik.has(e.label) ? 'rotate-180' : ''}`}>▼</span>
              </button>
              {acik.has(e.label) && (
                <div className="space-y-0.5 pb-1">
                  {e.items.map(it => <DropItem key={it.to} {...it} replace onClick={onClose} />)}
                </div>
              )}
            </div>
          ) : (
            <DropItem key={e.to} {...e} replace onClick={onClose} />
          ))}
        </nav>
      </aside>
    </div>
  )
}
