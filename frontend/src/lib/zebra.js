// Zebra Browser Print köprüsü — etiketi yazıcıya DOĞRUDAN ZPL olarak gönderir.
//
// Neden: tarayıcıdan yazdırınca hem onay penceresi çıkıyor hem de ölçekleme
// ayarları barkodu bozabiliyor. Browser Print (Zebra'nın ücretsiz aracı)
// bilgisayarda küçük bir servis çalıştırır; ona ZPL gönderince yazıcı
// doğrudan basar — tarayıcının yazdırma hattı hiç devreye girmez.
//
// Kurulu değilse her şey eskisi gibi çalışır (sayfa içi yazdırma).

const TABAN = 'http://localhost:9100'      // Browser Print yerel servisi
const ZAMAN_ASIMI = 2500

async function istek(yol, secenek = {}, ms = ZAMAN_ASIMI) {
  const iptal = new AbortController()
  const t = setTimeout(() => iptal.abort(), ms)
  try {
    return await fetch(`${TABAN}${yol}`, { ...secenek, signal: iptal.signal })
  } finally { clearTimeout(t) }
}

/** Browser Print kurulu ve çalışıyor mu. Hızlı, hata fırlatmaz. */
export async function zebraVarMi() {
  try {
    const r = await istek('/available')
    return r.ok
  } catch { return false }
}

/** Varsayılan yazıcıyı getir ({name, uid, ...}) ya da null. */
export async function zebraYazici() {
  try {
    const r = await istek('/default?type=printer')
    if (!r.ok) return null
    const t = (await r.text()).trim()
    if (!t) return null
    try { return JSON.parse(t) } catch { return { name: t, uid: t } }
  } catch { return null }
}

/** ZPL'i yazıcıya gönder. Döner: gönderildi mi. */
export async function zebraYazdir(zpl) {
  const yazici = await zebraYazici()
  if (!yazici) return false
  try {
    const r = await istek('/write', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
      body: JSON.stringify({ device: yazici, data: zpl }),
    }, 15000)
    return r.ok
  } catch { return false }
}
