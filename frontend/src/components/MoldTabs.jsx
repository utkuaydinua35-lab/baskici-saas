import { useNavigate, useLocation } from 'react-router-dom'

// Kalip yonetimi ortak sekme cubugu.
// active: 'sablon' | 'olustur' | 'olusturulan' (opsiyonel — verilmezse route'tan cikarilir)
export default function MoldTabs({ active }) {
  const navigate = useNavigate()
  const location = useLocation()
  const params = new URLSearchParams(location.search)

  // Aktif sekmeyi belirle
  let cur = active
  if (!cur) {
    if (location.pathname === '/kalip-sablon') cur = 'sablon'
    else if (location.pathname === '/kalip-olustur') {
      cur = params.get('tab') === 'existing' ? 'olusturulan' : 'olustur'
    }
  }

  const tabs = [
    { key: 'sablon', label: '🧩 Kalıp Şablonu', to: '/kalip-sablon' },
    { key: 'olustur', label: '🎯 Kalıp Oluşturucu', to: '/kalip-olustur' },
    { key: 'olusturulan', label: '📦 Oluşturulan Kalıplar', to: '/kalip-olustur?tab=existing' },
  ]

  return (
    <div className="flex items-center gap-1 mb-5 border-b border-brand-border">
      {tabs.map(t => (
        <button
          key={t.key}
          onClick={() => navigate(t.to)}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            cur === t.key
              ? 'border-accent text-accent'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}>
          {t.label}
        </button>
      ))}
    </div>
  )
}
