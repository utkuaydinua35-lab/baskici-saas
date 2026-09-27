/**
 * Kargo/adres etiketi YAZDIRMA — tek kaynak.
 *
 * Paketleme ekranı ile sipariş detayındaki telafi kargosu AYNI yolu kullanır:
 * önce yazıcıya doğrudan ZPL (QZ Tray / Zebra Browser Print), olmazsa sayfa
 * içinde gizli iframe'den yazdırma. Bu kod iki yere kopyalansaydı biri
 * düzeltilip diğeri eskide kalırdı (ölçü/oran ayarları burada saklı).
 *
 * `ctx` (hepsi isteğe bağlı): { etiketMm, doldur, qz, zebra, onMesaj }
 *   • etiketMm/doldur verilmezse tarayıcıdaki ayar (localStorage) kullanılır.
 *   • qz/zebra verilmezse köprüler burada sorgulanır.
 *   • onMesaj(mesaj) kullanıcıya gösterilecek uyarıları alır.
 *   • uclar: { zpl(id), label(id) } — hangi uçtan alınacağı. Varsayılan
 *     paketleme uçları; sipariş detayındaki telafi barkodu telafi uçlarını
 *     verir (paketleme yetkisi olmayan personel de yazdırabilsin).
 */
import { fetchYetkili } from './api'
import { mutlak } from './taban'
import { qzDurum, qzYazdir } from './qz'
import { zebraDurum, zebraTaban, zebraYazdir } from './zebra'

/** Tarayıcıda saklı etiket ölçüsü/doldurma ayarı (Paketleme ekranından gelir). */
export function etiketAyarlari() {
  let etiketMm = { w: 100, h: 150 }
  let doldur = true
  try {
    const v = JSON.parse(localStorage.getItem('etiket_mm') || 'null')
    if (v && v.w > 20 && v.h > 20) etiketMm = v
  } catch { /* bozuk kayıt */ }
  try { doldur = localStorage.getItem('etiket_doldur') !== '0' } catch { /* özel mod */ }
  return { etiketMm, doldur }
}

const PAKETLEME_UCLARI = {
  zpl: (id) => `/api/packaging/order/${encodeURIComponent(id)}/zpl`,
  label: (id) => `/api/packaging/order/${encodeURIComponent(id)}/kargo-label`,
}

export const TELAFI_UCLARI = {
  zpl: (id) => `/api/telafiler/${encodeURIComponent(id)}/zpl`,
  label: (id) => `/api/telafiler/${encodeURIComponent(id)}/kargo-label`,
}

async function _koprular(ctx) {
  const ayar = etiketAyarlari()
  const qz = ctx.qz !== undefined ? ctx.qz : await qzDurum()
  const zebra = ctx.zebra !== undefined ? ctx.zebra : await zebraDurum()
  return {
    etiketMm: ctx.etiketMm || ayar.etiketMm,
    doldur: ctx.doldur !== undefined ? ctx.doldur : ayar.doldur,
    qz, zebra,
    uclar: ctx.uclar || PAKETLEME_UCLARI,
    onMesaj: ctx.onMesaj || (() => {}),
  }
}

/**
 * Etiketi ÖNCE Zebra'ya doğrudan ZPL olarak göndermeyi dene.
 * Başarılıysa hiç yazdırma penceresi çıkmaz. Döner: gönderildi mi.
 * Hata YUTULMAZ: sessizce tarayıcıya düşünce "neden hâlâ onay çıkıyor?"
 * sorusunu cevaplayacak hiçbir iz kalmıyordu.
 */
export async function zplDene(orderId, tip = 'kargo', ctx = {}) {
  const k = await _koprular(ctx)
  if (!(k.qz?.yazici || k.zebra?.yazici)) return false   // hiçbir köprü hazır değil
  let zpl
  try {
    const q = new URLSearchParams({
      tip, w_mm: String(k.etiketMm.w), h_mm: String(k.etiketMm.h),
      doldur: k.doldur ? 'true' : 'false',
    })
    const res = await fetchYetkili(mutlak(`${k.uclar.zpl(orderId)}?${q}`))
    if (!res.ok) {
      let d = ''
      try { d = (await res.json())?.detail || '' } catch { /* json değil */ }
      const t = `ZPL alınamadı (HTTP ${res.status}) ${d}`.trim()
      console.warn('[zebra]', t)
      k.onMesaj({ ok: false, text: t + ' — tarayıcıdan yazdırılacak' })
      return false
    }
    zpl = await res.text()
  } catch (e) {
    console.warn('[zebra] ZPL isteği patladı:', e)
    k.onMesaj({ ok: false, text: `ZPL isteği başarısız: ${e?.message || e}` })
    return false
  }
  // Önce QZ Tray (yazıcı kuyruğu), sonra Zebra Browser Print (USB keşfi)
  if (k.qz?.yazici) {
    const r = await qzYazdir(zpl)
    if (r.ok) return true
    console.warn('[qz] yazılamadı:', r.hata, { boyut: zpl.length })
    k.onMesaj({ ok: false, text: `QZ Tray'e gönderilemedi: ${r.hata} — tarayıcıdan yazdırılacak` })
  }
  if (k.zebra?.yazici) {
    try {
      const ok = await zebraYazdir(zpl)
      if (ok) return true
      console.warn('[zebra] yazıcıya yazılamadı', { taban: zebraTaban(), boyut: zpl.length })
      k.onMesaj({ ok: false,
        text: `Zebra'ya gönderilemedi (${(zpl.length / 1024).toFixed(0)} KB) — tarayıcıdan yazdırılacak` })
    } catch (e) {
      console.warn('[zebra] yazma hatası:', e)
      k.onMesaj({ ok: false, text: `Zebra yazma hatası: ${e?.message || e}` })
    }
  }
  return false
}

// ── Sayfa içinde yazdırma ───────────────────────────────────
// Yeni sekme açmak yerine gizli bir iframe'e yazıp oradan yazdırıyoruz:
//  • ikinci sekme açılmıyor, popup engelleyici devreye girmiyor
//  • yeni sekmedeki "yazdır" adımı gitti
export function yazdirGomulu(html, baslik = '', olcu = null) {
  return new Promise((resolve) => {
    const cerceve = document.createElement('iframe')
    cerceve.setAttribute('aria-hidden', 'true')
    // GUVENLIK: etiket SVG'si KARGO FIRMASINDAN geliyor ve icinde musterinin
    // adi/adresi var. Firma kacirmayi atlarsa "</svg><script>" panelin
    // ORIGIN'inde calisir (src'siz iframe ayni origin) ve localStorage'daki
    // JWT'yi okur. sandbox'ta allow-scripts YOK: icerideki script hic
    // calismaz. allow-same-origin duruyor cunku yazdirmayi EBEVEYN tetikliyor
    // (contentWindow.print). Cizim etkilenmez — sanitizer riski de yok.
    cerceve.setAttribute('sandbox', 'allow-same-origin allow-modals')
    cerceve.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden'
    document.body.appendChild(cerceve)
    let bitti = false
    const temizle = () => {
      if (bitti) return
      bitti = true
      setTimeout(() => cerceve.remove(), 800)
      resolve(true)
    }
    try {
      const d = cerceve.contentWindow.document
      d.open()
      // @page size ŞART: verilmezse tarayıcı A4 varsayıp etiketi "sayfaya
      // sığdır" ile küçültüyor — barkod okunamayacak kadar ufalıyor.
      const o = olcu || { w: 100, h: 150 }
      d.write(`<!doctype html><html><head><meta charset="utf-8"><title>${baslik}</title>` +
        `<style>@page{size:${o.w}mm ${o.h}mm;margin:0}` +
        `html,body{margin:0;padding:0;width:${o.w}mm;height:${o.h}mm}` +
        `body{display:flex;align-items:center;justify-content:center;overflow:hidden}` +
        // max-* + auto: oran korunur ve HİÇBİR yönde taşmaz.
        `svg,img{max-width:${o.w}mm;max-height:${o.h}mm;width:auto;height:auto}` +
        `*{break-inside:avoid;page-break-inside:avoid}` +
        `</style></head><body>${html}</body></html>`)
      d.close()
      const bas = () => {
        try {
          cerceve.contentWindow.focus()
          cerceve.contentWindow.onafterprint = temizle
          cerceve.contentWindow.print()
        } catch { /* yazdırma engellendi */ }
        setTimeout(temizle, 4000)   // onafterprint gelmezse de temizlensin
      }
      if (d.readyState === 'complete') setTimeout(bas, 120)
      else cerceve.onload = () => setTimeout(bas, 120)
    } catch {
      cerceve.remove()
      resolve(false)
    }
  })
}

/** PDF etiketi — blob URL'i iframe'e verip yazdır. */
export function yazdirPdfGomulu(blobUrl) {
  return new Promise((resolve) => {
    const cerceve = document.createElement('iframe')
    cerceve.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden'
    cerceve.src = blobUrl
    let bitti = false
    const temizle = (ok) => { if (bitti) return; bitti = true; setTimeout(() => cerceve.remove(), 800); resolve(ok) }
    cerceve.onload = () => {
      try {
        cerceve.contentWindow.focus()
        cerceve.contentWindow.print()
        setTimeout(() => temizle(true), 4000)
      } catch { temizle(false) }
    }
    cerceve.onerror = () => temizle(false)
    document.body.appendChild(cerceve)
    setTimeout(() => temizle(false), 12000)   // PDF hiç yüklenmezse
  })
}

/** SVG kargo etiketi → SAYFA İÇİNDE yazdır (yeni sekme yok). */
export async function openLabelSvg(svg, takipNo, ctx = {}) {
  const k = await _koprular(ctx)
  const ok = await yazdirGomulu(svg, `Kargo Etiketi ${takipNo || ''}`, k.etiketMm)
  if (ok) return true
  // Gömülü yazdırma engellenirse eski yol (sekme) yedek kalsın
  try {
    const w = window.open('', '_blank')
    if (!w) return false
    // SVG'yi HAM gommek yerine <img> ile gosteriyoruz: <img> ile yuklenen
    // SVG'de tarayici script'i ASLA calistirmaz (SVG-as-image kurali).
    const svgData = 'data:image/svg+xml;base64,'
      + btoa(unescape(encodeURIComponent(svg)))
    const baslikGuvenli = String(takipNo || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    w.document.write(
      `<!doctype html><html><head><title>Kargo Etiketi ${baslikGuvenli}</title>` +
      `<style>@page{margin:0}body{margin:0;display:flex;justify-content:center;padding:8px}img{max-width:100%;height:auto}</style>` +
      `</head><body><img alt="" src="${svgData}"><scr` + `ipt>window.onload=function(){setTimeout(function(){window.print()},300)}</scr` + `ipt></body></html>`
    )
    w.document.close()
    return true
  } catch { return false }
}

/**
 * Kargo etiketini yeniden çek (kargo-gonder boş dönerse / re-print).
 * Basit Kargo SVG, Sürat (doğrudan) PDF döndürür — Content-Type'a bakılır.
 */
export async function fetchKargoEtiket(orderId, ctx = {}) {
  try {
    const uclar = ctx.uclar || PAKETLEME_UCLARI
    const res = await fetchYetkili(mutlak(uclar.label(orderId)))
    if (!res.ok) return null
    const tip = res.headers.get('content-type') || ''
    if (tip.includes('pdf')) return { tip: 'pdf', url: URL.createObjectURL(await res.blob()) }
    return { tip: 'svg', svg: await res.text() }
  } catch { return null }
}

/** PDF etiketi yazdır: gizli iframe'e yükleyip yazdırma penceresini aç. */
export async function openLabelPdf(url) {
  try {
    const f = document.createElement('iframe')
    f.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0'
    f.src = url
    document.body.appendChild(f)
    await new Promise((r) => { f.onload = r; setTimeout(r, 2500) })
    f.contentWindow.focus(); f.contentWindow.print()
    // Yazdırma penceresi kapanana kadar iframe dursun
    setTimeout(() => { f.remove(); URL.revokeObjectURL(url) }, 60000)
    return true
  } catch { return false }
}

/**
 * Barkodu yazdır: svg verilmişse onu; yoksa kargo-label'dan kısa retry ile çek
 * (Basit Kargo etiket üretimi yavaş olabiliyor). Döner: yazdırma penceresi açıldı mı.
 */
export async function printKargoLabel(orderId, svg, takipNo, ctx = {}) {
  // Zebra varsa doğrudan ZPL — pencere yok, ölçek sorunu yok.
  // (Sürat'ın PDF barkodu da bu yoldan geçer; sunucu pdf_to_zpl uyguluyor.)
  if (await zplDene(orderId, 'kargo', ctx)) return true
  if (svg) return await openLabelSvg(svg, takipNo, ctx)
  // Etiket üretimi gecikebiliyor — kısa aralıklarla tekrar dene
  for (let i = 0; i < 3; i++) {
    await new Promise(r => setTimeout(r, 1200))
    const et = await fetchKargoEtiket(orderId, ctx)
    if (et?.tip === 'pdf') return await openLabelPdf(et.url)
    if (et?.tip === 'svg' && et.svg) return await openLabelSvg(et.svg, takipNo, ctx)
  }
  return false
}
