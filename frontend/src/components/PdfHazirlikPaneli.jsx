import { useEffect, useRef, useState } from 'react'
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

export default function PdfHazirlikPaneli({ araAt = 3000, bosAraAt = 15000 }) {
  const [isler, setIsler] = useState([])
  const [hata, setHata] = useState('')
  const ustUsteRef = useRef(0)   // arka arkaya kaç yoklama düştü (çizimi etkilemez)
  const [geciciMi, setGeciciMi] = useState(false)
  // Kuyruk BOŞKEN de 3 sn'de bir sorulunuyordu: açık her sekme sunucuya günde
  // ~28.000 istek atıyordu ve her biri JWT çözüp kullanıcıyı veritabanından
  // okuyor. İş varken sık, boştayken seyrek sor. "Hazırla" anlık tetiklediği
  // için gecikme hissedilmiyor.
  const dolu = isler.length > 0

  useEffect(() => {
    let durduruldu = false
    const sor = async () => {
      try {
        const r = await api.get('/api/molds/pdf/kuyruk')
        if (durduruldu) return
        const gelen = r.items || []
        setIsler(gelen)
        setHata(''); ustUsteRef.current = 0
        // Liste rozetleri bunu dinliyor — kuyruk boşaldığı anı da görsün.
        window.dispatchEvent(new CustomEvent(PDF_KUYRUK_OLAYI, { detail: { isler: gelen } }))
      } catch (e) {
        if (durduruldu) return
        // Yutma: kutu hiç görünmezse sebebini bilmek gerekir.
        // Ama geçici kesintide (deploy) İLK hatada bağırma — üst üste 2 kez
        // başarısız olursa göster. api katmanı zaten bir kez tekrar deniyor.
        ustUsteRef.current += 1
        if (!e?.gecici || ustUsteRef.current >= 2) {
          setHata(e?.detail || e?.message || 'Durum alınamadı')
          setGeciciMi(!!e?.gecici)
        }
      }
    }
    sor()
    const t = setInterval(sor, dolu ? araAt : bosAraAt)
    // "Hazırla"dan gelen anlık tetik
    const hemen = () => sor()
    // Sekme arka planda kısıtlanıyor; öne gelince bayat kutu kalmasın.
    const gorunurluk = () => { if (!document.hidden) sor() }
    window.addEventListener(PDF_YENILE_OLAYI, hemen)
    document.addEventListener('visibilitychange', gorunurluk)
    window.addEventListener('focus', gorunurluk)
    return () => {
      durduruldu = true; clearInterval(t)
      window.removeEventListener(PDF_YENILE_OLAYI, hemen)
      document.removeEventListener('visibilitychange', gorunurluk)
      window.removeEventListener('focus', gorunurluk)
    }
  }, [araAt, bosAraAt, dolu])

  if (hata) {
    return (
      <div className={`fixed bottom-4 right-4 z-[120] w-72 card !p-3 ${
        geciciMi ? 'border-amber-500/40' : 'border-red-500/40'}`}>
        <div className={`text-xs ${geciciMi ? 'text-amber-300' : 'text-red-300'}`}>
          {geciciMi ? 'Sunucuya ulaşılamıyor' : 'PDF durumu alınamadı'}
        </div>
        <div className="text-[10px] text-gray-500 mt-1 break-words">{hata}</div>
        {geciciMi && (
          <div className="text-[10px] text-gray-600 mt-1">
            Kendiliğinden yeniden denenecek — PDF üretimi sunucuda devam ediyor.
          </div>
        )}
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
