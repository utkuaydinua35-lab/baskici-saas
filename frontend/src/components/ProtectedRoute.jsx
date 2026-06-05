/**
 * Korumalı rota — login değilse /login'e yönlendir.
 *
 * Kullanım (App.jsx içinde):
 *   <Route element={<ProtectedRoute />}>
 *     <Route path="/" element={<Dashboard />} />
 *     <Route path="/settings" element={<Settings />} />
 *   </Route>
 */
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-gray-500 text-sm">Yükleniyor...</div>
      </div>
    )
  }

  if (!user) {
    // Geri dönüş için mevcut konumu state'te tut — login sonrası buraya gelinsin
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <Outlet />
}
