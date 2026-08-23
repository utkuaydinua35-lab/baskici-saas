/**
 * Bayi portali kapisi.
 *
 * Iki yonlu koruma:
 *   • bayi olmayan (yonetici/operator) /bayii altina GIREMEZ — kendi paneline doner
 *   • bayi kullanicisi yonetim rotalarina GIREMEZ (AdminRoute asagida)
 * Bu ikisi ayrilmazsa bayi hesabi yonetim sayfalarini acabilir; backend zaten
 * 403 doner ama kullaniciya bos/kirik ekran gosterilmemeli.
 */
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { bayiMi } from '../lib/bayii'

function Bekle() {
  return (
    <div className="h-full min-h-[50vh] flex items-center justify-center">
      <div className="w-6 h-6 rounded-full border-2 border-brand-border border-t-accent animate-spin" />
    </div>
  )
}

export default function BayiRoute() {
  const { user, loading } = useAuth()
  const konum = useLocation()
  if (loading) return <Bekle />
  if (!user) return <Navigate to="/bayii/giris" replace state={{ from: konum }} />
  if (!bayiMi(user)) return <Navigate to="/" replace />
  return <Outlet />
}

/** Yonetim rotalari: bayi kullanicisi buraya giremez. */
export function BayiOlmayan() {
  const { user, loading } = useAuth()
  if (loading) return <Bekle />
  if (user && bayiMi(user)) return <Navigate to="/bayii" replace />
  return <Outlet />
}
