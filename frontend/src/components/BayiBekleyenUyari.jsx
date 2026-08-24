/**
 * Kalıp oluşturucuda uyarı: onay bekleyen bayi siparişi var.
 *
 * Onay bekleyen sipariş kalıba GİRMEZ (mold_planner süzüyor). Yönetici bunu
 * bilmeden kalıp üretirse o siparişler dışarıda kalır ve ikinci bir kalıp
 * gerekir — uyarı burada, planı üretmeden önce çıkıyor.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

export default function BayiBekleyenUyari() {
  const [sayi, setSayi] = useState(0)
  const [adet, setAdet] = useState(0)

  useEffect(() => {
    api.get('/api/dealers/portal/onay-bekleyen')
      .then((d) => {
        const l = Array.isArray(d) ? d : []
        setSayi(l.length)
        setAdet(l.reduce((t, o) =>
          t + (o.kalemler || []).reduce((n, k) => n + (k.adet || 1), 0), 0))
      })
      .catch(() => {})   // yetkisi yoksa uyarı hiç çıkmasın
  }, [])

  if (!sayi) return null

  return (
    <div className="card mb-4 !py-3.5 !border-amber-500/30 animate-fadeinup
                    flex items-center gap-3 flex-wrap">
      <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0"
            style={{ animation: 'glow-pulse 2s ease-in-out infinite' }} />
      <div className="flex-1 min-w-[220px] text-[13px] text-amber-100/90">
        <span className="font-semibold">{sayi} bayi siparişi onay bekliyor</span>
        <span className="text-amber-100/60"> ({adet} adet) — onaylanmadan kalıba girmez.</span>
      </div>
      <Link to="/bayi-siparisleri" className="btn-primary !text-xs !py-1.5 !px-4">
        Onay ekranına git
      </Link>
    </div>
  )
}
