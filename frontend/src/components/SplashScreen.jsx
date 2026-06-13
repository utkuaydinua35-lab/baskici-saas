import { useEffect, useState } from 'react'
import { useAuth } from '../lib/auth'

export default function SplashScreen({ onDone }) {
  const { user, tenant } = useAuth()
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    const t1 = setTimeout(() => setLeaving(true), 1600)   // çıkış animasyonu başlasın
    const t2 = setTimeout(() => onDone?.(), 2100)          // tamamen kapansın
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [onDone])

  const skip = () => { setLeaving(true); setTimeout(() => onDone?.(), 400) }

  const name = (user?.full_name || '').split(' ')[0] || ''

  return (
    <div
      onClick={skip}
      className={`fixed inset-0 z-[200] flex flex-col items-center justify-center bg-brand-bg cursor-pointer transition-opacity duration-500 ${leaving ? 'opacity-0' : 'opacity-100'}`}
    >
      {/* Arka plan parlama */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="splash-glow" />
      </div>

      {/* Logo */}
      <div className={`relative z-10 transition-all duration-500 ${leaving ? 'scale-150 opacity-0' : 'scale-100 opacity-100'}`}>
        {tenant?.logo_url ? (
          <img src={tenant.logo_url} alt={tenant?.name || 'Logo'} className="h-24 max-w-[260px] object-contain rounded-2xl splash-pop" />
        ) : (
          <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-4xl font-bold splash-pop">
            {(tenant?.name || 'B').charAt(0).toUpperCase()}
          </div>
        )}
      </div>

      {/* Karşılama */}
      <div className={`relative z-10 mt-6 text-center transition-all duration-700 ${leaving ? 'opacity-0 translate-y-2' : 'opacity-100 translate-y-0'} splash-welcome`}>
        <div className="text-xl font-semibold text-gray-100">
          {name ? `Hoş geldin, ${name}` : 'Hoş geldin'}
        </div>
        <div className="text-sm text-gray-500 mt-1">{tenant?.name || 'Baskıcı'} paneli yükleniyor…</div>
      </div>

      {/* Yükleniyor noktaları */}
      <div className={`relative z-10 mt-5 flex gap-1.5 transition-opacity duration-300 ${leaving ? 'opacity-0' : 'opacity-100'}`}>
        <span className="splash-dot" style={{ animationDelay: '0s' }} />
        <span className="splash-dot" style={{ animationDelay: '0.15s' }} />
        <span className="splash-dot" style={{ animationDelay: '0.3s' }} />
      </div>
    </div>
  )
}
