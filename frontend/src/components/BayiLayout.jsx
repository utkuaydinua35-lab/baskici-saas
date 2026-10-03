/**
 * Bayi portali kabugu — yonetim Layout'undan AYRI.
 *
 * Bayi, yonetim menusunu (siparisler, kalip, stok...) asla gormemeli; ayni
 * Layout'a kosul eklemek yerine bagimsiz bir kabuk daha guvenli: yeni bir
 * yonetim menusu eklendiginde bayiye sizma ihtimali yok.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { SON_SURUM, bekleyenTanitimlar, yeniSayisi } from '../lib/bayiGuncellemeler'
import BayiTanitim from './BayiTanitim'

const MENU = [
  { yol: '/bayii', ad: 'Panel', tam: true, ikon: 'M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6v-9h-6v9Zm0-16v5h6V4h-6Z' },
  { yol: '/bayii/siparisler', ad: 'Siparişlerim', ikon: 'M4 6h16M4 12h16M4 18h10' },
  { yol: '/bayii/yeni', ad: 'Yeni Sipariş', ikon: 'M12 5v14M5 12h14' },
  { yol: '/bayii/cari', ad: 'Cari Hesap', ikon: 'M3 7h18v10H3zM3 11h18' },
  { yol: '/bayii/sohbet', ad: 'Sohbet', sohbet: true,
    ikon: 'M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.6-.7L3 21l1.8-5A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4Z' },
  { yol: '/bayii/yenilikler', ad: 'Yenilikler', yenilik: true,
    ikon: 'M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4L12 3ZM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z' },
]

/** Menü öğesinin yanındaki "yeni" sayısı. */
function YeniRozet({ sayi }) {
  if (!sayi) return null
  return (
    <span className="min-w-[18px] h-[18px] px-1 rounded-full bg-accent text-[10px] font-semibold
                     leading-[18px] text-center" style={{ color: 'var(--accent-fg)' }}>{sayi}</span>
  )
}

function Ikon({ d }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" className="w-[18px] h-[18px]">
      <path d={d} />
    </svg>
  )
}

export default function BayiLayout() {
  const { user, tenant, logout } = useAuth()
  const navigate = useNavigate()
  const konum = useLocation()
  const [menuAcik, setMenuAcik] = useState(false)
  const seritRef = useRef(null)
  const [serit, setSerit] = useState({ sol: 0, en: 0, gorunur: false })

  // Aktif sekmenin altindaki kayan serit — sekme degisince yumusak gecer.
  // Yazi tipi gec yuklenince ya da pencere boyu degisince sekme genislikleri
  // degisiyor; serit eski olcude kaliyordu. Olcu ayniysa durum ellenmez.
  useEffect(() => {
    const olc = () => {
      const kap = seritRef.current
      if (!kap) return
      const aktif = kap.querySelector('[data-aktif="1"]')
      if (!aktif) { setSerit((s) => (s.gorunur ? { ...s, gorunur: false } : s)); return }
      const sol = aktif.offsetLeft, en = aktif.offsetWidth
      setSerit((s) => (s.gorunur && s.sol === sol && s.en === en) ? s : { sol, en, gorunur: true })
    }
    olc()
    document.fonts?.ready?.then(olc).catch(() => {})
    window.addEventListener('resize', olc)
    return () => window.removeEventListener('resize', olc)
  }, [konum.pathname])

  // ── Güncelleme notları / tanıtım ──
  // Sunucu bayinin hangi sürüme kadar gördüğünü tutar. Giriş sonrası ilk
  // açılışta görülmemiş tanıtım varsa tur KENDİLİĞİNDEN açılır.
  const [goruldu, setGoruldu] = useState(undefined)   // undefined = henüz bilinmiyor
  const [tur, setTur] = useState(null)                // { liste, tekrar } — gösterilen güncellemeler
  useEffect(() => {
    let iptal = false
    api.get('/api/bayii/guncellemeler/durum').then((r) => {
      if (iptal) return
      setGoruldu(r.goruldu)
      const bekleyen = bekleyenTanitimlar(r.goruldu)
      if (bekleyen.length) setTur({ liste: bekleyen, tekrar: false })
    }).catch(() => {})
    return () => { iptal = true }
  }, [])
  const turKapat = useCallback(() => {
    setTur(null)
    // Kapatınca da görüldü: tanıtım zorla izletilmez, Yenilikler'den tekrar açılır.
    setGoruldu(SON_SURUM)
    api.post('/api/bayii/guncellemeler/goruldu', { surum: SON_SURUM }).catch(() => {})
  }, [])
  const yeni = goruldu === undefined ? 0 : yeniSayisi(goruldu)

  // Sohbette okunmamış mesaj sayısı — menüde rozet olarak görünür.
  // 30 sn'de bir tazelenir; sekme arkadayken de yeni mesaj fark edilsin.
  const [okunmamisSohbet, setOkunmamisSohbet] = useState(0)
  useEffect(() => {
    let durdu = false
    const bak = () => api.get('/api/bayii/sohbet?limit=1')
      .then((d) => { if (!durdu) setOkunmamisSohbet(d?.sohbet?.okunmamis_bayi || 0) })
      .catch(() => {})
    bak()
    const t = setInterval(bak, 30000)
    return () => { durdu = true; clearInterval(t) }
  }, [konum.pathname])

  useEffect(() => { setMenuAcik(false) }, [konum.pathname])
  useEffect(() => {
    if (!menuAcik) return
    const tus = (e) => { if (e.key === 'Escape') setMenuAcik(false) }
    document.addEventListener('keydown', tus)
    return () => document.removeEventListener('keydown', tus)
  }, [menuAcik])

  const cikis = async () => {
    await logout()
    navigate('/bayii/giris', { replace: true })
  }

  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-30 bayi-ustbar pt-[env(safe-area-inset-top)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="h-16 flex items-center gap-3">
            <div className="flex items-center gap-2.5 shrink-0">
              <span className="bayi-marka-nokta" />
              <div className="leading-none">
                <div className="text-[15px] font-semibold tracking-tight text-white">
                  {tenant?.app_name || 'BERNZ'}
                </div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-gray-500 mt-1">
                  Bayii Paneli
                </div>
              </div>
            </div>

            <nav ref={seritRef} className="hidden md:flex items-center gap-1 ml-6 relative">
              {MENU.map((m) => (
                <NavLink key={m.yol} to={m.yol} end={m.tam}
                  className={({ isActive }) =>
                    `bayi-sekme ${isActive ? 'bayi-sekme-aktif' : ''}`}>
                  {({ isActive }) => (
                    <span data-aktif={isActive ? '1' : '0'}
                          className="flex items-center gap-2 px-3.5 py-2">
                      <Ikon d={m.ikon} />
                      {m.ad}
                      {m.yenilik && <YeniRozet sayi={yeni} />}
                      {m.sohbet && <YeniRozet sayi={okunmamisSohbet} />}
                    </span>
                  )}
                </NavLink>
              ))}
              <span className="bayi-serit" style={{
                left: serit.sol, width: serit.en, opacity: serit.gorunur ? 1 : 0,
              }} />
            </nav>

            <div className="ml-auto flex items-center gap-2">
              <div className="hidden sm:block text-right leading-tight mr-1">
                <div className="text-[13px] text-gray-200">{user?.full_name || 'Bayi'}</div>
                <div className="text-[11px] text-gray-500">{user?.email}</div>
              </div>
              {/* Telefonda çıkış menünün İÇİNDE: ☰'nin hemen yanındaydı,
                  menüyü açmak isterken yanlışlıkla oturum kapanıyordu. */}
              <div className="hidden md:block">
                <button onClick={cikis} className="bayi-cikis" title="Çıkış yap" aria-label="Çıkış yap">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
                       strokeLinecap="round" className="w-[18px] h-[18px]">
                    <path d="M15 17l5-5-5-5M20 12H9M12 19H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h6" />
                  </svg>
                </button>
              </div>
              <button onClick={() => setMenuAcik((v) => !v)}
                      className="md:hidden bayi-cikis relative" aria-label="Menü" aria-expanded={menuAcik}>
                {yeni > 0 && !menuAcik && (
                  <span aria-hidden className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-accent
                                               shadow-[0_0_0_2px_rgb(10_6_19)]" />
                )}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
                     strokeLinecap="round" className="w-[18px] h-[18px]">
                  <path d={menuAcik ? 'M6 6l12 12M18 6L6 18' : 'M4 7h16M4 12h16M4 17h16'} />
                </svg>
              </button>
            </div>
          </div>

          {menuAcik && (
            <nav className="md:hidden pb-3 grid gap-1 animate-fadein">
              {MENU.map((m) => (
                <NavLink key={m.yol} to={m.yol} end={m.tam}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-3 rounded-xl text-sm transition-colors ${
                      isActive ? 'bg-accent/15 text-white' : 'text-gray-400 hover:bg-white/5'}`}>
                  <Ikon d={m.ikon} />{m.ad}
                  {m.yenilik && <span className="ml-auto"><YeniRozet sayi={yeni} /></span>}
                </NavLink>
              ))}
              <div className="border-t border-white/5 mt-1 pt-1">
                <div className="px-3 py-2 text-[11px] text-gray-500 truncate">{user?.full_name || 'Bayi'} · {user?.email}</div>
                <button onClick={cikis}
                  className="w-full flex items-center gap-2.5 px-3 py-3 rounded-xl text-sm text-red-300 hover:bg-red-500/10 active:bg-red-500/10">
                  <Ikon d="M15 17l5-5-5-5M20 12H9M12 19H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h6" />Çıkış yap
                </button>
              </div>
            </nav>
          )}
        </div>
      </header>

      <main key={konum.pathname} className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-7 bayi-sayfa">
        <Outlet context={{ goruldu, tanitimAc: (g) => setTur({ liste: g, tekrar: true }) }} />
      </main>
      {tur && <BayiTanitim guncellemeler={tur.liste} tekrar={tur.tekrar} onKapat={turKapat} />}

      <footer className="max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 text-[11px] text-gray-600">
        {tenant?.app_name || 'BERNZ'} · Bayii Paneli
      </footer>
    </div>
  )
}
