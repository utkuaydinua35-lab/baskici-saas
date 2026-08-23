// Zebra Browser Print köprüsü — etiketi yazıcıya DOĞRUDAN ZPL olarak gönderir.
//
// Neden: tarayıcıdan yazdırınca hem onay penceresi çıkıyor hem de ölçekleme
// ayarları barkodu bozabiliyor. Browser Print (Zebra'nın ücretsiz aracı)
// bilgisayarda küçük bir servis çalıştırır; ona ZPL gönderince yazıcı
// doğrudan basar — tarayıcının yazdırma hattı hiç devreye girmez.
//
// Kurulu değilse her şey eskisi gibi çalışır (sayfa içi yazdırma).

// Browser Print İKİ uçta dinliyor: http 9100, https 9101.
// Panel HTTPS'ten servis edildiği için bazı tarayıcılar http://localhost'u
// karışık içerik sayıp engelleyebiliyor (Chrome localhost'a izin verir,
// Safari/Firefox vermeyebilir). İkisini de deneyip çalışanı hatırlıyoruz.
const TABANLAR = ['http://localhost:9100', 'https://localhost:9101']
let _calisanTaban = null
const ZAMAN_ASIMI = 2500

async function _dene(taban, yol, secenek, ms) {
  const iptal = new AbortController()
  const t = setTimeout(() => iptal.abort(), ms)
  try {
    return await fetch(`${taban}${yol}`, { ...secenek, signal: iptal.signal })
  } finally { clearTimeout(t) }
}

async function istek(yol, secenek = {}, ms = ZAMAN_ASIMI) {
  if (_calisanTaban) return _dene(_calisanTaban, yol, secenek, ms)
  let sonHata = null
  for (const taban of TABANLAR) {
    try {
      const r = await _dene(taban, yol, secenek, ms)
      _calisanTaban = taban          // çalışanı hatırla, her istekte deneme
      return r
    } catch (e) { sonHata = e }
  }
  throw sonHata || new Error('Browser Print bulunamadı')
}

/** Hangi uçtan bağlandık (tanı için). */
export function zebraTaban() { return _calisanTaban }

/** Durum: {servis, yazici, yaziciAdi}.
 *
 * servis=true ama yazici=false olabiliyor — Browser Print çalışıyor ama
 * yazıcıyı görmüyor demektir. Yalnızca servise bakmak yanıltıcıydı: rozet
 * yeşil görünüp baskı yine tarayıcıya düşüyordu.
 */
export async function zebraDurum() {
  let servis = false
  try {
    const r = await istek('/available')
    servis = r.ok
  } catch { return { servis: false, yazici: false, yaziciAdi: null } }
  if (!servis) return { servis: false, yazici: false, yaziciAdi: null }
  const y = await zebraYazici()
  return { servis: true, yazici: !!y, yaziciAdi: y?.name || y?.uid || null }
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

/** ZPL'i yazıcıya gönder. Döner: gönderildi mi.
 *  Hata sebebini konsola yazar — sessiz başarısızlık teşhis edilemiyordu. */
export async function zebraYazdir(zpl) {
  const yazici = await zebraYazici()
  if (!yazici) { console.warn('[zebra] varsayılan yazıcı yok'); return false }
  try {
    const r = await istek('/write', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
      body: JSON.stringify({ device: yazici, data: zpl }),
    }, 20000)
    if (!r.ok) console.warn('[zebra] /write HTTP', r.status, (await r.text()).slice(0, 200))
    return r.ok
  } catch (e) {
    console.warn('[zebra] /write patladı:', e?.name, e?.message)
    return false
  }
}
