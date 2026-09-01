/**
 * Yonetim → Bayi → Bayi Siparisleri.
 *
 * Bayi portalinden gelen ONAY ve IPTAL kuyruklari burada. Onceden Bayiler
 * sayfasinin tepesindeydi; cari listesiyle ayni ekrani paylasmasi is akisini
 * karistiriyordu.
 */
import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import BayiOnayKuyrugu from '../components/BayiOnayKuyrugu'
import BayiIptalKuyrugu from '../components/BayiIptalKuyrugu'
import BayiDuzeltmeKuyrugu from '../components/BayiDuzeltmeKuyrugu'

export default function BayiSiparisleriPage() {
  // Kuyruklardan biri islem yapinca digeri de tazelensin (ayni siparis
  // ikisinde birden gorunebilir: onay bekleyen bir siparis iptal edilebilir).
  const [tazele, setTazele] = useState(0)
  const degisti = useCallback(() => setTazele((n) => n + 1), [])

  return (
    <div className="mx-auto max-w-5xl animate-fadein">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-5">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🧾 Bayi Siparişleri</h1>
          <p className="text-sm text-gray-500 mt-1">
            Portaldan gelen siparişlerin onayı, iptal talepleri ve onay sonrası düzeltme
          </p>
        </div>
        <Link to="/bayiler" className="text-xs text-gray-500 hover:text-gray-300">
          🤝 Bayiler ve cari →
        </Link>
      </div>

      <div key={tazele}>
        <BayiOnayKuyrugu onOnaylandi={degisti} />
        <BayiIptalKuyrugu onDegisti={degisti} />
        <BayiDuzeltmeKuyrugu onDegisti={degisti} />
      </div>

      <BosDurum />
    </div>
  )
}

/** Iki kuyruk da bossa kuyruk bilesenleri hic render etmiyor — ekran bos
 *  kalmasin diye acikayici bir not. */
function BosDurum() {
  return (
    <div className="card text-center py-10 text-gray-500 text-sm">
      Bekleyen bir şey varsa yukarıda listelenir.
      <div className="text-xs text-gray-600 mt-1.5">
        Bayiler siparişlerini <span className="text-gray-400">/bayii/giris</span> üzerinden girer.
      </div>
    </div>
  )
}
