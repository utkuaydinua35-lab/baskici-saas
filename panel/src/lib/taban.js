/**
 * API ve varlık adreslerinin TABANI.
 *
 * NEDEN VAR: web'de panel API ile AYNI origin'de duruyor, bu yüzden her yerde
 * `/api/...` gibi göreli yollar kullanılıyor ve bu doğru. Ama uygulama bir
 * native kabuğa (Capacitor) sarıldığında sayfanın origin'i `capacitor://localhost`
 * (iOS) ya da `http://localhost` (Android) oluyor — göreli `/api/...` orada
 * SUNUCUYA DEĞİL, kabuğun kendi paketine gider ve her istek 404 olur.
 *
 * Çözüm tek yerde: build sırasında VITE_API_TABAN verilirse tüm göreli yollar
 * onun önüne eklenir. Web derlemesinde bu değişken YOK, taban boş kalır ve
 * davranış bugünküyle birebir aynıdır — yani bu dosya web'i etkilemez.
 *
 *   Web       :  npm run build                      → taban ""     → /api/...
 *   Uygulama  :  VITE_API_TABAN=https://... build    → taban dolu   → https://.../api/...
 */
const HAM = (import.meta.env?.VITE_API_TABAN || '').trim()

/** Sondaki eğik çizgi taşımaz; boşsa boş string. */
export const API_TABAN = HAM.replace(/\/+$/, '')

/** Native kabukta mıyız (taban tanımlıysa evet). */
export const NATIVE = API_TABAN !== ''

/**
 * Göreli bir yolu mutlak adrese çevirir. Zaten mutlak olan (http, data, blob)
 * ya da taban boşsa OLDUĞU GİBİ döner — yani web'de hiçbir şey değişmez.
 */
export function mutlak(yol) {
  if (!API_TABAN || typeof yol !== 'string' || !yol.startsWith('/')) return yol
  return API_TABAN + yol
}

/**
 * API yanıtındaki sunucu yollarını mutlaklaştırır.
 *
 * Görseller (`/storage/...`) yanıtın İÇİNDEN geliyor ve 21 ayrı yerde
 * <img src={...}> ile basılıyor. Hepsini tek tek sarmak yerine yanıtı
 * sınırda bir kez geçiriyoruz: hem tek nokta, hem de yarın eklenecek bir
 * alan kendiliğinden doğru çalışır. Taban boşken (web) fonksiyon veriyi
 * HİÇ dolaşmaz, maliyeti sıfırdır.
 */
export function yanitiMutlaklastir(veri) {
  if (!API_TABAN) return veri
  const gez = (d) => {
    if (typeof d === 'string') {
      return d.startsWith('/storage/') || d.startsWith('/uploads/') ? API_TABAN + d : d
    }
    if (Array.isArray(d)) return d.map(gez)
    if (d && typeof d === 'object') {
      const c = {}
      for (const k in d) c[k] = gez(d[k])
      return c
    }
    return d
  }
  return gez(veri)
}
