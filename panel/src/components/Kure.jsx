import { useEffect, useRef } from 'react'
import { karaNoktalari } from '../data/karaNoktalari'

// Dönen dünya küresi — canlı görünümdeki ziyaretçilerin nerede olduğunu
// gösterir. Kara parçaları derleme zamanında üretilmiş nokta bulutundan
// çizilir (bkz. scripts/dunya-maskesi.mjs); burada yalnız ortografik
// izdüşüm matematiği var, hiçbir harita kütüphanesi yok.
//
// Canvas tercih edildi: ~4000 nokta SVG'de 4000 DOM düğümü demek ve her
// karede yeniden düzen hesaplanır; canvas'ta tek çizim geçişi.

const EGIM = 18 * Math.PI / 180     // kuzeye hafif eğim — Avrupa/TR görünsün
const HIZ = 0.04                    // derece/kare (~2.4°/sn)
const D2R = Math.PI / 180

const RENK = {
  okyanus_ic: '#eaf7f4',
  okyanus_dis: '#cfe9f5',
  kara: '#5ecfb6',
  isaret: '#2c6ecb',
  isaret_halka: 'rgba(44,110,203,0.25)',
}

export default function Kure({ konumlar = [] }) {
  const canvasRef = useRef(null)
  const konumRef = useRef(konumlar)
  konumRef.current = konumlar

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const noktalar = karaNoktalari()

    // Başlangıç açısı: en çok oturumun geldiği ülke ekranın ortasına gelsin
    const enCok = konumRef.current.find(k => k.lon !== null && k.lon !== undefined)
    let lambda = enCok ? enCok.lon : 30

    let calisiyor = true
    let raf = 0
    const azHareket = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches

    let G = 0, Y = 0, dpr = 1
    const olcule = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      G = canvas.clientWidth
      Y = canvas.clientHeight
      canvas.width = Math.round(G * dpr)
      canvas.height = Math.round(Y * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    olcule()
    const gozlemci = new ResizeObserver(olcule)
    gozlemci.observe(canvas)

    /** (lat, lon) → ekran noktası; küreye arkadaysa null. */
    const izdusum = (lat, lon, cx, cy, R) => {
      const f = lat * D2R
      const d = (lon - lambda) * D2R
      const cosc = Math.sin(EGIM) * Math.sin(f) + Math.cos(EGIM) * Math.cos(f) * Math.cos(d)
      if (cosc <= 0) return null            // kürenin arka yüzü
      return {
        x: cx + R * Math.cos(f) * Math.sin(d),
        y: cy - R * (Math.cos(EGIM) * Math.sin(f) - Math.sin(EGIM) * Math.cos(f) * Math.cos(d)),
        derinlik: cosc,                      // 1 = tam karşımızda, 0 = kenar
      }
    }

    const ciz = () => {
      if (!calisiyor) return
      const cx = G / 2, cy = Y / 2
      const R = Math.min(G, Y) / 2 - 12
      ctx.clearRect(0, 0, G, Y)

      // Okyanus
      const gr = ctx.createRadialGradient(cx - R * 0.3, cy - R * 0.35, R * 0.1, cx, cy, R)
      gr.addColorStop(0, RENK.okyanus_ic)
      gr.addColorStop(1, RENK.okyanus_dis)
      ctx.fillStyle = gr
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill()

      // Kara noktaları
      ctx.fillStyle = RENK.kara
      for (let i = 0; i < noktalar.length; i += 2) {
        const p = izdusum(noktalar[i], noktalar[i + 1], cx, cy, R)
        if (!p) continue
        // Kenara yaklaşınca sönümle — kürenin yuvarlaklığı okunur olsun
        ctx.globalAlpha = Math.min(1, 0.25 + p.derinlik * 1.1)
        const r = R * 0.0055 * (0.55 + p.derinlik * 0.45)
        ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill()
      }
      ctx.globalAlpha = 1

      // Ziyaretçi işaretleri
      const kon = konumRef.current.filter(k => k.lat !== null && k.lat !== undefined)
      const enBuyuk = Math.max(1, ...kon.map(k => k.oturum))
      for (const k of kon) {
        const p = izdusum(k.lat, k.lon, cx, cy, R)
        if (!p) continue
        const olcek = 0.35 + 0.65 * Math.sqrt(k.oturum / enBuyuk)
        const r = Math.max(3, R * 0.022 * olcek)
        ctx.globalAlpha = Math.min(1, 0.35 + p.derinlik)
        ctx.fillStyle = RENK.isaret_halka
        ctx.beginPath(); ctx.arc(p.x, p.y, r * 2.1, 0, Math.PI * 2); ctx.fill()
        ctx.fillStyle = RENK.isaret
        ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill()
        ctx.globalAlpha = 1
      }

      if (!azHareket) lambda = (lambda + HIZ) % 360
      raf = requestAnimationFrame(ciz)
    }
    raf = requestAnimationFrame(ciz)

    // Sekme gizliyken çizme — boşuna CPU yakmasın
    const gorunurluk = () => {
      if (document.visibilityState === 'visible') {
        if (!calisiyor) { calisiyor = true; raf = requestAnimationFrame(ciz) }
      } else {
        calisiyor = false
        cancelAnimationFrame(raf)
      }
    }
    document.addEventListener('visibilitychange', gorunurluk)

    return () => {
      calisiyor = false
      cancelAnimationFrame(raf)
      gozlemci.disconnect()
      document.removeEventListener('visibilitychange', gorunurluk)
    }
  }, [])

  const toplam = konumlar.reduce((s, k) => s + k.oturum, 0)
  return (
    <div className="w-full h-full relative bg-gradient-to-b from-white to-[#f2fbfa]">
      <canvas ref={canvasRef} className="w-full h-full block" role="img"
        aria-label={`Dünya küresi: bugün ${toplam} oturum, ${konumlar.length} ülke`} />
      {konumlar.length > 0 && (
        <div className="absolute bottom-3 right-3 flex items-center gap-1.5
          bg-white/85 backdrop-blur border border-panel-border rounded-full px-3 py-1.5 text-xs">
          <span className="w-2 h-2 rounded-full" style={{ background: RENK.isaret }} />
          <span className="text-panel-muted">Oturumlar</span>
        </div>
      )}
    </div>
  )
}
