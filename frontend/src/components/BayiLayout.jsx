/**
 * Bayi portali kabugu — yonetim Layout'undan AYRI.
 *
 * Bayi, yonetim menusunu (siparisler, kalip, stok...) asla gormemeli; ayni
 * Layout'a kosul eklemek yerine bagimsiz bir kabuk daha guvenli: yeni bir
 * yonetim menusu eklendiginde bayiye sizma ihtimali yok.
 */
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

const MENU = [
  { yol: '/bayii', ad: 'Panel', tam: true, ikon: 'M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6v-9h-6v9Zm0-16v5h6V4h-6Z' },
  { yol: '/bayii/siparisler', ad: 'Siparişlerim', ikon: 'M4 6h16M4 12h16M4 18h10' },
  { yol: '/bayii/yeni', ad: 'Yeni Sipariş', ikon: 'M12 5v14M5 12h14' },
  { yol: '/bayii/cari', ad: 'Cari Hesap', ikon: 'M3 7h18v10H3zM3 11h18' },
]

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
  useEffect(() => {
    const kap = seritRef.current
    if (!kap) return
    const aktif = kap.querySelector('[data-aktif="1"]')
    if (!aktif) { setSerit((s) => ({ ...s, gorunur: false })); return }
    setSerit({ sol: aktif.offsetLeft, en: aktif.offsetWidth, gorunur: true })
  }, [konum.pathname])

  useEffect(() => { setMenuAcik(false) }, [konum.pathname])

  const cikis = async () => {
    await logout()
    navigate('/bayii/giris', { replace: true })
  }

  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-30 bayi-ustbar">
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
              <button onClick={cikis} className="bayi-cikis" title="Çıkış yap">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
                     strokeLinecap="round" className="w-[18px] h-[18px]">
                  <path d="M15 17l5-5-5-5M20 12H9M12 19H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h6" />
                </svg>
              </button>
              <button onClick={() => setMenuAcik((v) => !v)}
                      className="md:hidden bayi-cikis" aria-label="Menü">
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
                    `flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-colors ${
                      isActive ? 'bg-accent/15 text-white' : 'text-gray-400 hover:bg-white/5'}`}>
                  <Ikon d={m.ikon} />{m.ad}
                </NavLink>
              ))}
            </nav>
          )}
        </div>
      </header>

      <main key={konum.pathname} className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-7 bayi-sayfa">
        <Outlet />
      </main>

      <footer className="max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 text-[11px] text-gray-600">
        {tenant?.app_name || 'BERNZ'} · Bayii Paneli
      </footer>
    </div>
  )
}
