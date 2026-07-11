import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { useStore } from '../lib/store'

const NAV = [
  { to: '/', label: 'Panel', icon: '🏠', end: true },
  { to: '/siparisler', label: 'Siparişler', icon: '📦' },
  { to: '/urunler', label: 'Ürünler', icon: '🛍️' },
  { to: '/koleksiyonlar', label: 'Koleksiyonlar', icon: '🗂️' },
  { to: '/envanter', label: 'Envanter', icon: '📋' },
  { to: '/kuponlar', label: 'Kuponlar', icon: '🎟️' },
  { to: '/terk-sepetler', label: 'Terk Sepetler', icon: '🛒' },
  { to: '/musteriler', label: 'Müşteriler', icon: '👥' },
  { to: '/yorumlar', label: 'Yorumlar', icon: '⭐' },
  { to: '/tasarim-talepleri', label: 'Tasarım Talepleri', icon: '🖌️' },
  { to: '/analitik', label: 'Analitik', icon: '📈' },
  { to: '/tema', label: 'Tema', icon: '🎨' },
  { to: '/sayfalar', label: 'Sayfalar', icon: '📄' },
  { to: '/blog', label: 'Blog', icon: '✍️' },
  { to: '/ayarlar', label: 'Ayarlar', icon: '⚙️' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const { stores, store, setStoreId } = useStore()

  const storefrontUrl = store?.config?.storefront_url
    || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : null)

  return (
    <div className="min-h-screen flex">
      {/* Sol menü */}
      <aside className="w-56 shrink-0 border-r border-panel-border bg-white flex flex-col">
        <div className="h-14 flex items-center gap-2 px-4 border-b border-panel-border">
          <div className="w-8 h-8 rounded-lg bg-panel-accent text-white flex items-center justify-center font-bold text-sm">
            M
          </div>
          <span className="font-semibold text-sm">Mağaza Paneli</span>
        </div>
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {NAV.map(item => (
            <NavLink key={item.to} to={item.to} end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm transition ${
                  isActive
                    ? 'bg-emerald-50 text-panel-accent font-medium'
                    : 'text-panel-muted hover:bg-panel-input hover:text-panel-ink'
                }`}>
              <span className="text-base leading-none">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-panel-border text-xs text-panel-muted">
          <div className="truncate font-medium text-panel-ink">{user?.full_name || user?.email}</div>
          <button onClick={logout} className="mt-1 text-panel-muted hover:text-red-600">
            Çıkış yap
          </button>
        </div>
      </aside>

      {/* İçerik */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 bg-white border-b border-panel-border flex items-center gap-3 px-5">
          {stores.length > 1 ? (
            <select value={store?.id || ''} onChange={e => setStoreId(e.target.value)}
              className="input !w-auto !py-1.5">
              {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          ) : (
            <span className="font-semibold text-sm">{store?.name || 'Mağaza'}</span>
          )}
          {storefrontUrl && (
            <a href={storefrontUrl} target="_blank" rel="noopener noreferrer"
              className="ml-auto btn-ghost !py-1.5 text-xs">
              Vitrini Gör ↗
            </a>
          )}
        </header>
        <main className="flex-1 p-5 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
