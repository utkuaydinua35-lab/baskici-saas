import { useEffect, useState } from 'react'
import { api } from '../lib/api'

// Sağ altta sabit ilerleme kutusu — PDF üretimi dakikalar sürdüğü için
// "çalışıyor mu?" sorusu ekranda cevaplanmalı.
//
// Kuyruğu SUNUCUDAN sorar: hangi kalıpları soracağını bilmesi gerekmez, bu
// yüzden her sayfada aynı şekilde çalışır. (Önceki hali yalnızca listedeki
// kalıplara soruyordu ve hatayı sessizce yutuyordu.)
export const PDF_KUYRUK_OLAYI = 'pdf-kuyruk'        // {isler} — her yoklamada
export const PDF_YENILE_OLAYI = 'pdf-kuyruk-yenile'  // hemen yokla

/** "Hazırla"ya basınca panel BEKLEMEDEN açılsın diye. */
export function pdfKuyrugunuYenile() {
  window.dispatchEvent(new CustomEvent(PDF_YENILE_OLAYI))
}

export default function PdfHazirlikPaneli({ araAt = 3000 }) {
  const [isler, setIsler] = useState([])
  const [hata, setHata] = useState('')

  useEffect(() => {
    let durduruldu = false
    const sor = async () => {
      try {
        const r = await api.get('/api/molds/pdf/kuyruk')
        if (durduruldu) return
        const gelen = r.items || []
        setIsler(gelen)
        setHata('')
        // Liste rozetleri bunu dinliyor — kuyruk boşaldığı anı da görsün.
        window.dispatchEvent(new CustomEvent(PDF_KUYRUK_OLAYI, { detail: { isler: gelen } }))
      } catch (e) {
        if (durduruldu) return
        // Yutma: kutu hiç görünmezse sebebini bilmek gerekir
        setHata(e?.detail || e?.message || 'Durum alınamadı')
      }
    }
    sor()
    const t = setInterval(sor, araAt)
    // "Hazırla"dan gelen anlık tetik
    const hemen = () => sor()
    window.addEventListener(PDF_YENILE_OLAYI, hemen)
    return () => {
      durduruldu = true; clearInterval(t)
      window.removeEventListener(PDF_YENILE_OLAYI, hemen)
    }
  }, [araAt])

  if (hata) {
    return (
      <div className="fixed bottom-4 right-4 z-[120] w-72 card !p-3 border-red-500/40">
        <div className="text-xs text-red-300">PDF durumu alınamadı</div>
        <div className="text-[10px] text-gray-500 mt-1 break-words">{hata}</div>
      </div>
    )
  }
  if (!isler.length) return null

  const sure = (sn) => sn >= 60 ? `${Math.floor(sn / 60)} dk ${sn % 60} sn` : `${sn} sn`
  return (
    <div className="fixed bottom-4 right-4 z-[120] w-72 card !p-3 shadow-2xl border-accent/30">
      <div className="text-xs font-medium text-gray-200 mb-2">
        📄 PDF hazırlanıyor ({isler.length})
      </div>
      <div className="space-y-1.5 max-h-48 overflow-y-auto">
        {isler.map(i => (
          <div key={i.anahtar} className="flex items-center gap-2 text-[11px]">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse shrink-0" />
            <span className="font-mono text-gray-300 truncate flex-1">{i.kod || '—'}</span>
            <span className="text-gray-500 tabular-nums shrink-0">{sure(i.gecen_sn || 0)}</span>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-gray-500 mt-2 leading-snug">
        Sıra ile üretiliyor · kalıp başına birkaç dakika. Sayfadan ayrılabilirsin,
        üretim sunucuda sürer.
      </p>
    </div>
  )
}
