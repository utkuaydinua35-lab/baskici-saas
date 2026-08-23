/**
 * Bayi portalinin paylasilan kucuk parcalari.
 * Tek dosyada tutuluyor: her biri 20-40 satir, ayri dosyalara bolmek
 * import gurultusunden baska bir sey getirmiyor.
 */
import { useEffect, useRef, useState } from 'react'
import { ROZET_SINIF, asamaRozet } from '../lib/bayii'

/** Sipariş durum rozeti. */
export function DurumRozet({ siparis, buyuk = false }) {
  const r = asamaRozet(siparis)
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-medium
                      ${buyuk ? 'text-xs px-3 py-1.5' : 'text-[11px] px-2.5 py-1'}
                      ${ROZET_SINIF[r.renk]}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      {r.etiket}
    </span>
  )
}

/** Sayıyı 0'dan hedefe akıtan sayaç — panel rakamları canlı hissettirir. */
export function Sayac({ deger, sure = 800, className = '', bicim }) {
  const [n, setN] = useState(0)
  const oncekiRef = useRef(0)
  useEffect(() => {
    const bas = oncekiRef.current
    const hedef = Number(deger || 0)
    oncekiRef.current = hedef
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { setN(hedef); return }
    let iptal = false
    const t0 = performance.now()
    const adim = (t) => {
      if (iptal) return
      const o = Math.min(1, (t - t0) / sure)
      const yumusak = 1 - Math.pow(1 - o, 3)
      setN(bas + (hedef - bas) * yumusak)
      if (o < 1) requestAnimationFrame(adim)
    }
    requestAnimationFrame(adim)
    return () => { iptal = true }
  }, [deger, sure])
  return <span className={className}>{bicim ? bicim(n) : Math.round(n)}</span>
}

/** Boş liste anlatımı. */
export function Bos({ baslik, aciklama, eylem }) {
  return (
    <div className="text-center py-14 px-6">
      <div className="inline-grid place-items-center w-14 h-14 rounded-2xl mb-4
                      border border-white/8 bg-white/[0.03]">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
             className="w-6 h-6 text-gray-600">
          <path d="M4 7h16v13H4zM4 7l2-3h12l2 3M9 12h6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="text-[15px] text-gray-300 font-medium">{baslik}</div>
      {aciklama && <div className="text-[13px] text-gray-500 mt-1.5 max-w-sm mx-auto">{aciklama}</div>}
      {eylem && <div className="mt-5">{eylem}</div>}
    </div>
  )
}

/** Yükleniyor iskeleti — hazır olmayan içerik yerine ışıldayan bloklar. */
export function Iskelet({ satir = 3, yukseklik = 76 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: satir }).map((_, i) => (
        <div key={i} className="rounded-2xl overflow-hidden bayi-sira"
             style={{ height: yukseklik, '--gecikme': `${i * 60}ms`,
                      background: 'rgb(255 255 255 / 0.035)' }}>
          <div className="w-full h-full" style={{
            background: 'linear-gradient(90deg, transparent, rgb(255 255 255 / 0.05), transparent)',
            backgroundSize: '200% 100%',
            animation: 'skeleton-shimmer 1.4s ease-in-out infinite',
          }} />
        </div>
      ))}
    </div>
  )
}

/** Hata kutusu. */
export function Hata({ mesaj, tekrar }) {
  if (!mesaj) return null
  return (
    <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 animate-popin
                    flex items-start gap-3">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
           className="w-[18px] h-[18px] text-red-400 shrink-0 mt-0.5" strokeLinecap="round">
        <circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" />
      </svg>
      <div className="flex-1 text-[13px] text-red-200">{String(mesaj)}</div>
      {tekrar && (
        <button onClick={tekrar} className="text-[12px] text-red-300 hover:text-red-100 underline">
          Tekrar dene
        </button>
      )}
    </div>
  )
}

/** Kısa bildirim (toast). */
export function Bildirim({ mesaj, tur = 'ok', onKapat }) {
  useEffect(() => {
    if (!mesaj) return
    const t = setTimeout(onKapat, 3600)
    return () => clearTimeout(t)
  }, [mesaj, onKapat])
  if (!mesaj) return null
  const ok = tur === 'ok'
  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 px-4 py-3 rounded-2xl glass
                    flex items-center gap-2.5 text-[13px] max-w-[90vw]"
         style={{ animation: 'toast-in .32s cubic-bezier(.22,.8,.28,1) both' }}>
      <span className={`w-6 h-6 rounded-full grid place-items-center shrink-0
                        ${ok ? 'bg-emerald-500/18 text-emerald-300' : 'bg-red-500/18 text-red-300'}`}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"
             strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
          {ok ? <path d="M4 12.5l5 5L20 7" /> : <path d="M6 6l12 12M18 6L6 18" />}
        </svg>
      </span>
      <span className="text-gray-200">{mesaj}</span>
    </div>
  )
}
