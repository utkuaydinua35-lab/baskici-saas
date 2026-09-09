/**
 * Platform seçici — YALNIZ uygulamada (Capacitor kabuğu).
 *
 * Uygulamanın içinde iki ayrı web uygulaması paketli:
 *   /          → BERNZ Commerce (mağaza paneli, bu paket)
 *   /studio/   → Baskıcı Paneli (Studio, frontend/ derlemesi)
 *
 * İkisi de AYNI origin'de (`capacitor://localhost`) durduğu için seçim
 * localStorage'ta saklanabiliyor ve geçiş tek bir sayfa yüklemesi.
 *
 * Web'de bu ekran HİÇ görünmez: `nativeMi()` false döner, mağaza paneli
 * bugünkü gibi doğrudan açılır.
 */
import { nativeMi } from './lib/kamera'

const ANAHTAR = 'platform_secimi'

/**
 * Studio'nun paket içindeki TAM adresi.
 *
 * `/studio/` (dizin) yazmak yetmiyor: Capacitor'ün yerel sunucusu uzantısız
 * yolları KÖKTEKİ index.html'e düşürüyor, yani mağaza paneli yeniden açılıp
 * seçimi görüyor ve tekrar buraya yönleniyordu — sonsuz döngü, boş ekran.
 * Dosyayı açıkça adresliyoruz.
 */
export const STUDIO_ADRES = '/studio/index.html'

/** '' (seçilmemiş) | 'magaza' | 'studio'. Web'de her zaman 'magaza'. */
export function secilenPlatform() {
  if (!nativeMi()) return 'magaza'
  try {
    return localStorage.getItem(ANAHTAR) || ''
  } catch {
    return ''
  }
}

/** Seçimi unut ve seçiciye dön — iki uygulamadan da çağrılır. */
export function platformSifirla() {
  try {
    localStorage.removeItem(ANAHTAR)
  } catch { /* özel mod */ }
  location.replace('/')
}

function sec(deger) {
  try {
    localStorage.setItem(ANAHTAR, deger)
  } catch { /* özel mod — seçim kalıcı olmaz, akış yine de çalışır */ }
}

function Kart({ ikon, ad, aciklama, onClick, vurgu }) {
  return (
    <button type="button" onClick={onClick}
      className={`w-full text-left rounded-2xl border p-4 flex items-center gap-4
        transition-colors active:scale-[0.99] ${vurgu
          ? 'border-panel-accent/60 bg-panel-accent/10'
          : 'border-panel-border bg-white/5'}`}>
      <span className="text-3xl leading-none shrink-0">{ikon}</span>
      <span className="min-w-0">
        <span className="block text-base font-semibold text-white">{ad}</span>
        <span className="block text-xs text-panel-muted mt-0.5">{aciklama}</span>
      </span>
      <span className="ml-auto text-panel-muted text-lg shrink-0">›</span>
    </button>
  )
}

export default function PlatformSecici({ onSec }) {
  const magaza = () => { sec('magaza'); onSec('magaza') }
  const studio = () => { sec('studio'); location.replace(STUDIO_ADRES) }

  return (
    <div className="min-h-screen flex flex-col justify-center px-5 py-10 gap-6">
      <div className="text-center">
        <div className="text-lg font-semibold text-white">Hangi paneli açalım?</div>
        <div className="text-xs text-panel-muted mt-1">
          Seçimin hatırlanır; sonra hesap menüsünden değiştirebilirsin.
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <Kart ikon="🛍️" ad="BERNZ Commerce" vurgu
          aciklama="Mağaza paneli — ürünler, siparişler, vitrin"
          onClick={magaza} />
        <Kart ikon="🖨️" ad="Studio"
          aciklama="Baskıcı paneli — kalıplar, üretim, bayiler"
          onClick={studio} />
      </div>
    </div>
  )
}
