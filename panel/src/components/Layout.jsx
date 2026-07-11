import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { useStore } from '../lib/store'
import { BRAND, BRAND_SHORT } from '../lib/brand'

// Shopify yerleşim mantığı: koyu üst bar (marka + mağaza + vitrin linki),
// solda GRUPLU menü (Satış/Katalog/Müşteri/Pazarlama/Online Mağaza),
// Ayarlar en altta sabit. Route değişince içerik page-in ile belirir.
const NAV_GROUPS = [
  { label: null, items: [
    { to: '/', label: 'Ana Sayfa', icon: '🏠', end: true },
  ]},
  { label: 'Satış', items: [
    { to: '/siparisler', label: 'Siparişler', icon: '📦' },
    { to: '/terk-sepetler', label: 'Terk Sepetler', icon: '🛒' },
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
  const { user, logout } = useAuth()
  const { stores, store, setStoreId } = useStore()
  const location = useLocation()

  const storefrontUrl = store?.config?.storefront_url
    || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : null)

  return (
    <div className="min-h-screen flex flex-col">
      {/* Üst bar — koyu, Shopify tarzı */}
      <header className="h-12 shrink-0 bg-slate-900 flex items-center gap-3 px-3 text-white sticky top-0 z-30">
        <div className="flex items-center gap-2 pr-2">
          <div className="w-7 h-7 rounded-lg text-white flex items-center justify-center font-bold text-xs
            bg-gradient-to-br from-emerald-400 to-teal-600 shadow-[0_0_10px_rgba(16,185,129,0.45)]">
            {BRAND_SHORT}
          </div>
          <span className="font-semibold text-[13px] tracking-tight">{BRAND}</span>
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
          <div className="flex items-center gap-2 pl-2 border-l border-slate-700">
            <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center text-[11px] font-semibold uppercase">
              {(user?.full_name || user?.email || '?').slice(0, 1)}
            </div>
            <div className="hidden sm:block leading-tight">
              <div className="text-[11px] font-medium truncate max-w-32">{user?.full_name || user?.email}</div>
              <button onClick={logout} className="text-[10px] text-slate-400 hover:text-red-400 transition-colors">
                Çıkış yap
              </button>
            </div>
          </div>
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
