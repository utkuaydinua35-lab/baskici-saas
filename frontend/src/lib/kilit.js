/**
 * Arka plandan dönüşte kilit — Studio tarafı.
 *
 * Kilit ekranının kendisi mağaza panelinin kabuğunda (panel/src/KabukAkisi.jsx)
 * duruyor; Studio ayrı bir belge olduğu için burada yalnız SÜREYİ ölçüp
 * gerektiğinde köke dönüyoruz. Kabuk orada Face ID'yi sorar; açıldıktan sonra
 * platform seçimi hâlâ 'studio' olduğu için kullanıcı Studio'ya geri gelir.
 *
 * Anahtar adları ve süre iki uygulamada AYNI olmak zorunda — origin ortak
 * olduğu için depolama da ortak.
 *
 * NOT: eklenti `@capacitor/app` paketinden değil, native köprünün global
 * nesnesinden alınıyor. Sebep: Studio'nun WEB derlemesine Capacitor bağımlılığı
 * eklemek istemiyoruz; eklenti zaten uygulamanın native tarafında kayıtlı ve
 * aynı pakette çalışıyor.
 *
 * Web'de hiç çalışmaz: `nativeMi()` false döner.
 */
import { nativeMi } from './taban'

const ARKA_PLAN_ANAHTARI = 'kilit_arka_plan'
const KILIT_ANAHTARI = 'kilit_acildi'
const KILIT_SURESI_MS = 5 * 60 * 1000

export function kilidiKur() {
  if (!nativeMi()) return
  const App = window.Capacitor?.Plugins?.App
  if (!App?.addListener) return   // eklenti yoksa kilit yalnız soğuk açılışta

  App.addListener('appStateChange', ({ isActive }) => {
    if (!isActive) {
      try { localStorage.setItem(ARKA_PLAN_ANAHTARI, String(Date.now())) } catch { /* özel mod */ }
      return
    }
    let t = 0
    try { t = Number(localStorage.getItem(ARKA_PLAN_ANAHTARI) || 0) } catch { return }
    if (!t || Date.now() - t < KILIT_SURESI_MS) return
    try {
      sessionStorage.removeItem(KILIT_ANAHTARI)
      localStorage.removeItem(ARKA_PLAN_ANAHTARI)
    } catch { /* özel mod */ }
    location.replace('/')      // kabuk kilidi sorsun
  })
}
