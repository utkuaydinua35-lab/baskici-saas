import { useEffect, useRef } from 'react'
import { karaNoktalari } from '../data/karaNoktalari'

// Dönen dünya küresi — ziyaretçilerin nerede olduğunu gösterir.
//
// Kara parçaları derleme zamanında üretilmiş nokta bulutundan gelir
// (scripts/dunya-maskesi.mjs); burada yalnız ortografik izdüşüm matematiği
// var — harita kütüphanesi yok, ağ isteği yok.
//
// Canvas tercih edildi: 5794 nokta + yıldızlar + yaylar SVG'de on binlerce
// DOM düğümü ve her karede yeniden düzen hesabı demekti.

const EGIM = 18 * Math.PI / 180     // kuzeye hafif eğim — Avrupa/TR görünsün
const HIZ = 0.045                   // derece/kare
const D2R = Math.PI / 180
const YILDIZ = 90

const RENK = {
  kara: [33, 212, 253],             // #21d4fd — Vision UI camgöbeği
  kara_kutup: [67, 24, 255],        // #4318ff — kutuplara doğru mora kayar
  isaret: '#ffffff',
  hale: '0, 117, 255',              // #0075ff
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
    const azHareket = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches

    // Yıldızlar bir kez üretilir — her karede rastgele üretilseydi titrerdi
    const yildizlar = Array.from({ length: YILDIZ }, () => ({
      x: Math.random(), y: Math.random(),
      r: 0.4 + Math.random() * 1.1,
      faz: Math.random() * Math.PI * 2,
      hiz: 0.6 + Math.random() * 1.4,
    }))

    const enCok = konumRef.current.find(k => k.lon != null)
    let lambda = enCok ? enCok.lon : 30
    let kare = 0
    let calisiyor = true
    let raf = 0

    let G = 0, Y = 0
    const olcule = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      G = canvas.clientWidth; Y = canvas.clientHeight
      canvas.width = Math.round(G * dpr); canvas.height = Math.round(Y * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    olcule()
    const gozlemci = new ResizeObserver(olcule)
    gozlemci.observe(canvas)

    /** (lat, lon) → ekran noktası; kürenin arka yüzündeyse null. */
    const izdusum = (lat, lon, cx, cy, R) => {
      const f = lat * D2R, d = (lon - lambda) * D2R
      const cosc = Math.sin(EGIM) * Math.sin(f) + Math.cos(EGIM) * Math.cos(f) * Math.cos(d)
      if (cosc <= 0) return null
      return {
        x: cx + R * Math.cos(f) * Math.sin(d),
        y: cy - R * (Math.cos(EGIM) * Math.sin(f) - Math.sin(EGIM) * Math.cos(f) * Math.cos(d)),
        derinlik: cosc,
      }
    }

    const ciz = () => {
      if (!calisiyor) return
      kare++
      const cx = G / 2, cy = Y / 2
      const R = Math.min(G, Y) / 2 - 26
      // Kap henüz ölçülmemişken (mount anında clientWidth 0) R negatif olur;
      // createRadialGradient negatif yarıçapta HATA fırlatır ve rAF geri
      // çağrısındaki hata döngüyü KALICI olarak öldürür — küre hiç çizilmez.
      // Kareyi atla, döngüyü yaşat.
      if (R < 10) { raf = requestAnimationFrame(ciz); return }
      ctx.clearRect(0, 0, G, Y)

      // ── Yıldızlar (kürenin arkasında) ──
      for (const y of yildizlar) {
        const p = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(kare * 0.02 * y.hiz + y.faz))
        ctx.globalAlpha = p * 0.55
        ctx.fillStyle = '#cbd5f5'
        ctx.beginPath(); ctx.arc(y.x * G, y.y * Y, y.r, 0, Math.PI * 2); ctx.fill()
      }
      ctx.globalAlpha = 1

      // ── Atmosfer halesi ──
      const hale = ctx.createRadialGradient(cx, cy, R * 0.86, cx, cy, R * 1.32)
      hale.addColorStop(0, `rgba(${RENK.hale}, 0.32)`)
      hale.addColorStop(0.55, `rgba(${RENK.hale}, 0.10)`)
      hale.addColorStop(1, 'rgba(0, 117, 255, 0)')
      ctx.fillStyle = hale
      ctx.beginPath(); ctx.arc(cx, cy, R * 1.32, 0, Math.PI * 2); ctx.fill()

      // ── Küre gövdesi ──
      const govde = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.4, R * 0.08, cx, cy, R)
      govde.addColorStop(0, 'rgba(28, 44, 110, 0.95)')
      govde.addColorStop(0.7, 'rgba(11, 20, 55, 0.92)')
      govde.addColorStop(1, 'rgba(6, 11, 40, 0.98)')
      ctx.fillStyle = govde
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill()

      // ── Kara noktaları ──
      for (let i = 0; i < noktalar.length; i += 2) {
        const lat = noktalar[i]
        const p = izdusum(lat, noktalar[i + 1], cx, cy, R)
        if (!p) continue
        // Ekvatordan kutba doğru camgöbeği → mor
        const t = Math.min(1, Math.abs(lat) / 75)
        const [r, g, b] = [0, 1, 2].map(j =>
          Math.round(RENK.kara[j] + (RENK.kara_kutup[j] - RENK.kara[j]) * t))
        ctx.fillStyle = `rgba(${r},${g},${b},${Math.min(1, 0.18 + p.derinlik * 1.05)})`
        const rad = R * 0.0055 * (0.55 + p.derinlik * 0.45)
        ctx.beginPath(); ctx.arc(p.x, p.y, rad, 0, Math.PI * 2); ctx.fill()
      }

      // ── Kenar ışığı (küreyi zeminden ayırır) ──
      ctx.strokeStyle = 'rgba(120, 190, 255, 0.28)'
      ctx.lineWidth = 1
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.stroke()

      const kon = konumRef.current.filter(k => k.lat != null)
      const enBuyuk = Math.max(1, ...kon.map(k => k.oturum))

      // ── Yaylar: en yoğun ülkeden diğerlerine akan ışık ──
      // Yalnız İKİ UCU DA görünür olanlar çizilir; yoksa yay kürenin
      // arkasından geçip yanlış yerde asılı kalırdı.
      if (kon.length > 1) {
        const kaynak = kon[0]
        const a = izdusum(kaynak.lat, kaynak.lon, cx, cy, R)
        for (let i = 1; i < kon.length; i++) {
          const b = izdusum(kon[i].lat, kon[i].lon, cx, cy, R)
          if (!a || !b) continue
          const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
          const uzak = Math.hypot(b.x - a.x, b.y - a.y)
          // Kontrol noktasını küre merkezinden DIŞARI it → yay havalanır
          const nx = mx - cx, ny = my - cy
          const n = Math.hypot(nx, ny) || 1
          const kx = mx + (nx / n) * uzak * 0.35
          const ky = my + (ny / n) * uzak * 0.35
          ctx.strokeStyle = 'rgba(33, 212, 253, 0.35)'
          ctx.lineWidth = 1.2
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(kx, ky, b.x, b.y); ctx.stroke()

          // Yay üzerinde koşan ışık damlası
          const t = ((kare * 0.006) + i * 0.27) % 1
          const u = 1 - t
          const px = u * u * a.x + 2 * u * t * kx + t * t * b.x
          const py = u * u * a.y + 2 * u * t * ky + t * t * b.y
          const isik = ctx.createRadialGradient(px, py, 0, px, py, 7)
          isik.addColorStop(0, 'rgba(255,255,255,0.95)')
          isik.addColorStop(1, 'rgba(33,212,253,0)')
          ctx.fillStyle = isik
          ctx.beginPath(); ctx.arc(px, py, 7, 0, Math.PI * 2); ctx.fill()
        }
      }

      // ── Ziyaretçi işaretleri (nabız atan) ──
      for (const k of kon) {
        const p = izdusum(k.lat, k.lon, cx, cy, R)
        if (!p) continue
        const olcek = 0.4 + 0.6 * Math.sqrt(k.oturum / enBuyuk)
        const r = Math.max(2.5, R * 0.017 * olcek)
        const nabiz = (kare * 0.012 + k.lon / 360) % 1
        ctx.globalAlpha = Math.min(1, 0.3 + p.derinlik)

        ctx.strokeStyle = `rgba(${RENK.hale}, ${(1 - nabiz) * 0.55})`
        ctx.lineWidth = 1.4
        ctx.beginPath(); ctx.arc(p.x, p.y, r * (1 + nabiz * 3), 0, Math.PI * 2); ctx.stroke()

        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 3)
        g.addColorStop(0, `rgba(${RENK.hale}, 0.5)`)
        g.addColorStop(1, `rgba(${RENK.hale}, 0)`)
        ctx.fillStyle = g
        ctx.beginPath(); ctx.arc(p.x, p.y, r * 3, 0, Math.PI * 2); ctx.fill()

        ctx.fillStyle = RENK.isaret
        ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill()
        ctx.globalAlpha = 1
      }

      if (!azHareket) lambda = (lambda + HIZ) % 360
      raf = requestAnimationFrame(ciz)
    }
    raf = requestAnimationFrame(ciz)

    // Sekme gizliyken çizme — boşuna CPU/pil yakmasın
    const gorunurluk = () => {
      if (document.visibilityState === 'visible') {
        if (!calisiyor) { calisiyor = true; raf = requestAnimationFrame(ciz) }
      } else { calisiyor = false; cancelAnimationFrame(raf) }
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
    <div className="absolute inset-0">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full block" role="img"
        aria-label={`Dünya küresi: bugün ${toplam} oturum, ${konumlar.length} ülke`} />
      {konumlar.length > 0 && (
        <div className="absolute bottom-4 right-4 flex items-center gap-2
          bg-white/[0.06] backdrop-blur-xl border border-panel-border rounded-full px-3.5 py-2 text-xs">
          <span className="relative flex w-2 h-2">
            <span className="absolute inset-0 rounded-full bg-panel-accent nabiz-halka" />
            <span className="relative w-2 h-2 rounded-full bg-white" />
          </span>
          <span className="text-panel-muted">Oturumlar</span>
          <span className="tabular-nums font-semibold text-white">{toplam}</span>
        </div>
      )}
    </div>
  )
}
