// QZ Tray köprüsü — Windows'un YAZICI KUYRUĞUNA ham ZPL gönderir.
//
// Neden Browser Print değil: Browser Print USB cihazlarını kendi keşfetmeye
// çalışıyor ve bu makinede yazıcıyı bulamadı. QZ Tray keşif yapmaz; işletim
// sisteminde kurulu yazıcıya kuyruk üzerinden basar. Windows test sayfası
// bastığına göre o yol çalışıyor.
//
// Kurulu değilse her şey eskisi gibi: sayfa içi yazdırma devreye girer.
import qz from 'qz-tray'

let _baglaniyor = null
const YAZICI_ANAHTAR = 'qz_yazici'

// İmzasız kullanım: QZ ilk isteğinde tarayıcıda "İzin ver" sorar ve
// "bu kararı hatırla" seçilince bir daha sormaz. İmza sertifikası ücretli
// olduğu için bilerek imzasız gidiyoruz.
qz.security.setCertificatePromise((resolve, reject) => reject(new Error('imzasiz')))

async function baglan() {
  if (qz.websocket.isActive()) return true
  if (!_baglaniyor) {
    _baglaniyor = qz.websocket
      .connect({ retries: 1, delay: 0 })
      .then(() => true)
      .catch(() => false)
      .finally(() => { _baglaniyor = null })
  }
  return _baglaniyor
}

/** Durum: {servis, yazici, yaziciAdi}. Hata fırlatmaz. */
export async function qzDurum() {
  const servis = await baglan()
  if (!servis) return { servis: false, yazici: false, yaziciAdi: null }
  const ad = await qzYazici()
  return { servis: true, yazici: !!ad, yaziciAdi: ad }
}

/** Kullanılacak yazıcı adı. Elle seçilmişse o, yoksa Windows varsayılanı. */
export async function qzYazici() {
  try {
    const secili = localStorage.getItem(YAZICI_ANAHTAR)
    if (secili) return secili
  } catch { /* depolama kapalı */ }
  try {
    if (!(await baglan())) return null
    const v = await qz.printers.getDefault()
    return (typeof v === 'string' && v.trim()) ? v.trim() : null
  } catch { return null }
}

/** Kurulu yazıcıların listesi (kullanıcı seçsin diye). */
export async function qzYazicilar() {
  try {
    if (!(await baglan())) return []
    const l = await qz.printers.find()
    return Array.isArray(l) ? l : (l ? [l] : [])
  } catch { return [] }
}

export function qzYaziciSec(ad) {
  try {
    if (ad) localStorage.setItem(YAZICI_ANAHTAR, ad)
    else localStorage.removeItem(YAZICI_ANAHTAR)
  } catch { /* depolama kapalı */ }
}

/** ZPL'i HAM olarak yazıcıya gönder. Döner: {ok, hata}. */
export async function qzYazdir(zpl) {
  const ad = await qzYazici()
  if (!ad) return { ok: false, hata: 'Yazıcı seçili değil' }
  try {
    if (!(await baglan())) return { ok: false, hata: 'QZ Tray bağlantısı yok' }
    // raw + ZPL: sürücü dönüşümü YAPILMAZ, bayt bayt yazıcıya gider
    const cfg = qz.configs.create(ad, { encoding: 'UTF-8' })
    await qz.print(cfg, [{ type: 'raw', format: 'command', flavor: 'plain', data: zpl }])
    return { ok: true }
  } catch (e) {
    return { ok: false, hata: e?.message || String(e) }
  }
}
