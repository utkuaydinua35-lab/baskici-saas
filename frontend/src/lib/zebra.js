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
  return { servis: true, yazici: _gecerli(y), yaziciAdi: y?.name || y?.uid || null }
}

/** Cihaz gerçekten kullanılabilir mi.
 *  Browser Print /write çağrısında "name" bekliyor; boş nesne ({}) döndüğünde
 *  JS'te truthy olduğu için "yazıcı var" sanılıyor ve /write 500 veriyordu
 *  ("No value for name"). */
function _gecerli(d) {
  return !!(d && typeof d === 'object' && (d.name || d.uid))
}

/** Yanıtı cihaz nesnesine çevir (JSON ya da düz metin ad). */
function _cihaz(metin) {
  const t = (metin || '').trim()
  if (!t) return null
  try {
    const j = JSON.parse(t)
    if (_gecerli(j)) return j
    // {printer:[...]} / {device:{...}} gibi sarmalanmış biçimler
    for (const k of ['printer', 'device', 'devices', 'printers']) {
      const v = j?.[k]
      if (Array.isArray(v)) {
        const bulunan = v.find(_gecerli)
        if (bulunan) return bulunan
      } else if (_gecerli(v)) return v
    }
    return null
  } catch {
    return { name: t, uid: t }      // düz metin ad döndüyse
  }
}

/** Varsayılan yazıcı ({name, uid, ...}) ya da null.
 *  Önce /default, olmazsa /available listesinden ilk yazıcı. */
export async function zebraYazici() {
  for (const yol of ['/default?type=printer', '/available']) {
    try {
      const r = await istek(yol)
      if (!r.ok) continue
      const d = _cihaz(await r.text())
      if (_gecerli(d)) return d
    } catch { /* sonrakini dene */ }
  }
  return null
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
