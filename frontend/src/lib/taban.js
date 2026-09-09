/**
 * API ve varlık adreslerinin TABANI (Baskıcı Paneli / Studio).
 *
 * NEDEN VAR: web'de Studio API ile AYNI origin'de duruyor, bu yüzden her yerde
 * `/api/...` gibi göreli yollar kullanılıyor ve bu doğru. Ama Studio native
 * kabuğa (Capacitor) paketlendiğinde sayfanın origin'i `capacitor://localhost`
 * (iOS) ya da `http://localhost` (Android) oluyor — göreli `/api/...` orada
 * SUNUCUYA DEĞİL, kabuğun kendi paketine gider ve her istek 404 olur.
 *
 * Çözüm tek yerde: build sırasında VITE_API_TABAN verilirse tüm göreli yollar
 * onun önüne eklenir. Web derlemesinde bu değişken YOK, taban boş kalır ve
 * davranış bugünküyle birebir aynıdır — yani bu dosya web'i etkilemez.
 *
 *   Web       :  npm run build                       → taban ""    → /api/...
 *   Uygulama  :  VITE_API_TABAN=https://... build     → taban dolu  → https://.../api/...
 *
 * Mağaza panelindeki `panel/src/lib/taban.js` ile aynı sözleşme; ikisi ayrı
 * uygulama olduğu için bilinçli olarak kopyalandı, paylaşılan paket kurulmadı.
 */
const HAM = (import.meta.env?.VITE_API_TABAN || '').trim()

/** Sondaki eğik çizgi taşımaz; boşsa boş string. */
export const API_TABAN = HAM.replace(/\/+$/, '')

/** Native kabukta mıyız? (tarayıcıda her zaman false) */
let _native = null
export function nativeMi() {
  if (_native !== null) return _native
  try {
    _native = !!(window.Capacitor && window.Capacitor.isNativePlatform
                 && window.Capacitor.isNativePlatform())
  } catch {
    _native = false
  }
  return _native
}

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
 * Görseller (`/storage/...`) yanıtın İÇİNDEN geliyor ve pek çok yerde
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

/**
 * Uygulamanın SAYFA kökü (API değil).
 *
 * Web'de Studio alan adının kökünde durur → ''. Native kabukta ise mağaza
 * paneliyle AYNI pakette, `/studio/` alt klasöründe duruyor → '/studio'.
 * Değeri Vite'ın `base` ayarından gelir (import.meta.env.BASE_URL), yani tek
 * kaynak vardır ve build ile kendiliğinden tutarlıdır.
 */
export const TEMEL = (import.meta.env?.BASE_URL || '/').replace(/\/+$/, '')

/**
 * Uygulama içi bir yolu (ör. '/login') TAM adrese çevirir.
 *
 * Web'de kökten yol tabanlı: '/login'.
 * Uygulamada Studio `/studio/` altında ve hash tabanlı yönlendirici
 * kullanıyor (bkz. main.jsx): '/studio/index.html#/login'.
 */
export function uygulamaYolu(yol) {
  const y = yol.startsWith('/') ? yol : '/' + yol
  return TEMEL ? `${TEMEL}/index.html#${y}` : y
}

/** location.pathname + hash'in bu yolda olup olmadığı (yönlendirme döngüsü koruması). */
export function buYoldaMiyiz(yol) {
  const y = yol.startsWith('/') ? yol : '/' + yol
  return TEMEL ? location.hash.startsWith('#' + y) : location.pathname.startsWith(y)
}

/**
 * Uygulamada iki panel tek pakette duruyor (bkz. panel/src/PlatformSecici.jsx).
 * Seçimi unutup köke dönmek seçiciyi yeniden açar. Anahtar adı iki uygulamada
 * AYNI olmak zorunda — origin ortak olduğu için localStorage da ortak.
 */
export function platformSifirla() {
  try {
    localStorage.removeItem('platform_secimi')
  } catch { /* özel mod */ }
  location.replace('/')
}
