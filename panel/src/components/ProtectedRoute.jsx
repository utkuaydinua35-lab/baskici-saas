import { Navigate, Outlet } from 'react-router-dom'
import { canUsePanel, useAuth } from '../lib/auth'
import { useStore } from '../lib/store'

export default function ProtectedRoute() {
  const { user, loading, logout } = useAuth()
  const storeCtx = useStore()

  if (loading || (user && storeCtx.loading)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 rounded-full border-2 border-panel-border border-t-panel-accent animate-spin" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />

  if (!canUsePanel(user)) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="card max-w-md text-center !p-8">
          <div className="text-4xl">🔒</div>
          <h1 className="mt-3 font-semibold">Bu panele erişim yetkiniz yok</h1>
          <p className="mt-2 text-sm text-panel-muted">
            Mağaza Paneli için hesabınızda <b>vitrin</b> yetkisi olmalı.
            Yöneticinizden Baskıcı Paneli üzerinden yetki isteyebilirsiniz.
          </p>
          <button onClick={logout} className="btn-ghost mt-4">Başka hesapla gir</button>
        </div>
      </div>
    )
  }

  if (storeCtx.stores.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="card max-w-md text-center !p-8">
          <div className="text-4xl">🏬</div>
          <h1 className="mt-3 font-semibold">Henüz vitrin mağazanız yok</h1>
          <p className="mt-2 text-sm text-panel-muted">
            Baskıcı Paneli → <b>Atölyeler</b> sayfasından platformu
            &quot;Kendi Mağazam (Vitrin)&quot; olan bir mağaza oluşturun;
            panel otomatik bağlanır.
          </p>
          <button onClick={logout} className="btn-ghost mt-4">Çıkış yap</button>
        </div>
      </div>
    )
  }

  return <Outlet />
}
