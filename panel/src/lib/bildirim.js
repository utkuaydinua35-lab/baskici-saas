/**
 * Uygulama bildirimleri (APNs / FCM) — yalnız native kabukta.
 *
 * NEDEN AYRI: panelde zaten Web Push var ama o tarayıcı içindir ve uygulamada
 * ÇALIŞMAZ (service worker yok, origin `capacitor://localhost`). Uygulamaya
 * bildirim işletim sistemi üzerinden gelir; cihaz bir JETON verir, backend de
 * bunu APNs'e gönderir. Sunucu tarafında tetikleyiciler AYNI — mevcut
 * bildirimlerin hepsi (yeni sipariş, bayi talebi, destek, günlük özet)
 * kendiliğinden uygulamaya da düşer.
 *
 * İZİN: Apple izni bir kez sorar. Reddedilirse bir daha sorulamaz, o yüzden
 * girişten hemen sonra değil, kullanıcı panele girdikten sonra soruyoruz.
 *
 * ÜCRETLİ HESAP GEREKİYOR: `register()` çağrısı, uygulamanın "Push
 * Notifications" yetkisiyle imzalanmış olmasını ister; ücretsiz kişisel Apple
 * takımları bu yetkiyi alamıyor. O durumda çağrı hata verir, biz de sessizce
 * geçeriz — uygulamanın geri kalanı etkilenmez.
 */
import { api } from './api'
import { nativeMi } from './kamera'

let _kuruldu = false

// Son alinan jeton. Cikista sunucudan dusurebilmek icin saklaniyor: aksi
// halde cikis yapan kullanicinin bildirimleri, bir sonraki girise kadar bu
// telefona dusmeye devam ederdi.
const JETON_ANAHTARI = 'cihaz_jetonu'

/**
 * Bildirimleri kur: izin iste, jetonu al, sunucuya kaydet, dokunuşu bağla.
 * Birden çok kez çağrılabilir; ilk başarılı kurulumdan sonra iş yapmaz.
 */
export async function bildirimleriKur() {
  if (!nativeMi() || _kuruldu) return
  _kuruldu = true

  let PushNotifications
  try {
    ({ PushNotifications } = await import('@capacitor/push-notifications'))
  } catch {
    return   // eklenti yok (web derlemesi) — sessizce çık
  }

  try {
    let { receive } = await PushNotifications.checkPermissions()
    if (receive === 'prompt' || receive === 'prompt-with-rationale') {
      ({ receive } = await PushNotifications.requestPermissions())
    }
    if (receive !== 'granted') return   // kullanıcı istemiyor; ısrar etme

    // Jeton geldiğinde sunucuya yaz. Jeton DEĞİŞEBİLİR (yeniden kurulum,
    // yedekten dönme); bu yüzden her açılışta yeniden kaydediyoruz.
    await PushNotifications.addListener('registration', async ({ value }) => {
      try {
        await api.post('/api/push/device', {
          token: value,
          platform: 'ios',
          device_name: navigator.userAgent.slice(0, 120),
        })
        try { localStorage.setItem(JETON_ANAHTARI, value) } catch { /* özel mod */ }
      } catch { /* ağ yoksa bir sonraki açılışta tekrar denenir */ }
    })

    await PushNotifications.addListener('registrationError', () => {
      // En sık sebep: uygulama "Push Notifications" yetkisi olmadan
      // imzalanmış (ücretsiz Apple takımı). Kullanıcıya gösterilecek bir şey
      // yok, bildirim sessizce kapalı kalır.
    })

    // Bildirime dokunulduğunda sunucunun verdiği adrese git.
    await PushNotifications.addListener('pushNotificationActionPerformed', (olay) => {
      bildirimeGit(olay?.notification?.data || {})
    })

    await PushNotifications.register()
  } catch { /* izin/kayıt başarısız — bildirim kapalı, akış bozulmaz */ }
}

/**
 * Bildirimin gösterdiği yere git.
 *
 * Sunucu `app` alanında hangi panelin açılacağını söylüyor (bkz. backend
 * services/push.py:hedef_uygulama) — `/orders/123` yalnızca Studio'da,
 * `/siparisler/123` yalnızca mağaza panelinde var.
 *
 * Platform seçimini de yazıyoruz: aksi halde kabuk açılışta seçiciyi gösterir
 * ve kullanıcının dokunduğu bildirim kaybolurdu.
 */
function bildirimeGit(veri) {
  const yol = typeof veri.url === 'string' && veri.url.startsWith('/') ? veri.url : '/'
  const studio = veri.app === 'studio'
  try {
    sessionStorage.setItem('platform_secimi', studio ? 'studio' : 'magaza')
  } catch { /* özel mod */ }
  location.href = studio ? `/studio/index.html#${yol}` : yol
}

/** Çıkışta cihazı sunucudan düşür ki eski kullanıcının bildirimi buraya gelmesin. */
export function bildirimleriBirak() {
  if (!nativeMi()) return
  let jeton = null
  try {
    jeton = localStorage.getItem(JETON_ANAHTARI)
    localStorage.removeItem(JETON_ANAHTARI)
  } catch { /* özel mod */ }
  if (!jeton) return
  // Beklemiyoruz: çıkış akışı ağ yüzünden gecikmesin. İstek başarısız olursa
  // jeton sunucuda kalır ama bir sonraki girişte yeni sahibine devredilir.
  api.del(`/api/push/device?token=${encodeURIComponent(jeton)}`).catch(() => {})
}
