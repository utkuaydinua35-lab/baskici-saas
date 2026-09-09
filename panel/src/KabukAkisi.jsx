/**
 * Uygulama açılış akışı — YALNIZ native kabukta.
 *
 * Sıra:
 *   1. Oturum yoksa   → GİRİŞ   (panelin kendi login ekranı)
 *   2. Oturum varsa   → KİLİT   (Face ID / Touch ID; cihazda varsa)
 *   3.                → SEÇİM   (hangi panel açılacak)
 *   4.                → PANEL   (mağaza paneli çizilir ya da Studio'ya gidilir)
 *
 * Giriş bir kez yapılıyor; token iki panel için de geçerli (tek backend, tek
 * hesap — bkz. lib/api.js'teki eşleme). Bu yüzden "önce giriş, sonra platform"
 * sırası hem doğru hem de mümkün.
 *
 * Web'de bu dosya hiç çalışmaz: main.jsx `nativeMi()` false ise doğrudan
 * paneli çizer.
 */
import { useEffect, useState } from 'react'
import { getToken, setToken } from './lib/api'
import { biyometriDogrula, biyometriVarMi } from './lib/biyometri'
import PlatformSecici, { STUDIO_ADRES, secilenPlatform } from './PlatformSecici'

// Kilidin bu açılışta bir kez açıldığını işaretler. Girişin hemen ardından ya
// da panel içindeki bir sayfa yenilemesinde tekrar yüz/parmak sormamak için.
const KILIT_ANAHTARI = 'kilit_acildi'

function kilitAcikMi() {
  try {
    return sessionStorage.getItem(KILIT_ANAHTARI) === '1'
  } catch {
    return true   // sessionStorage yoksa kullanıcıyı kilitleme
  }
}

export function kilidiAcikIsaretle() {
  try {
    sessionStorage.setItem(KILIT_ANAHTARI, '1')
  } catch { /* özel mod */ }
}

/** Açılışta hangi aşamadayız? */
function baslangicAsamasi() {
  if (!getToken()) return 'giris'
  if (!kilitAcikMi()) return 'kilit'
  return secilenPlatform() ? 'panel' : 'secim'
}

function KilitEkrani({ onAcildi, onSifreyleGir }) {
  const [deneniyor, setDeneniyor] = useState(true)
  const [reddedildi, setReddedildi] = useState(false)

  const dene = async () => {
    setDeneniyor(true); setReddedildi(false)
    const oldu = await biyometriDogrula()
    setDeneniyor(false)
    if (oldu) { kilidiAcikIsaretle(); onAcildi() }
    else setReddedildi(true)
  }

  // Açılır açılmaz sor — kullanıcı fazladan bir düğmeye basmasın.
  useEffect(() => { dene() }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 gap-5 text-center">
      <div className="text-5xl">🔒</div>
      <div>
        <div className="text-base font-semibold text-white">Panel kilitli</div>
        <div className="text-xs text-panel-muted mt-1">
          {deneniyor ? 'Kimliğin doğrulanıyor…'
            : reddedildi ? 'Doğrulanamadı. Tekrar deneyebilirsin.'
              : 'Devam etmek için kimliğini doğrula.'}
        </div>
      </div>

      {!deneniyor && (
        <div className="flex flex-col gap-2 w-full max-w-xs">
          <button type="button" onClick={dene} className="btn-primary w-full !py-2.5 text-sm">
            Tekrar dene
          </button>
          <button type="button" onClick={onSifreyleGir}
            className="btn-ghost w-full !py-2.5 text-sm">
            Şifreyle giriş yap
          </button>
        </div>
      )}
    </div>
  )
}

/**
 * @param {() => JSX.Element} panel  Mağaza panelinin tamamı (router dahil).
 */
export default function KabukAkisi({ panel }) {
  const [asama, setAsama] = useState(baslangicAsamasi)

  // Cihazda biyometri YOKSA kilit ekranında takılı kalmayalım.
  useEffect(() => {
    if (asama !== 'kilit') return
    let iptal = false
    biyometriVarMi().then((var_mi) => {
      if (iptal || var_mi) return
      kilidiAcikIsaretle()
      setAsama(secilenPlatform() ? 'panel' : 'secim')
    })
    return () => { iptal = true }
  }, [asama])

  if (asama === 'kilit') {
    return (
      <KilitEkrani
        onAcildi={() => setAsama(secilenPlatform() ? 'panel' : 'secim')}
        onSifreyleGir={() => { setToken(null); setAsama('giris') }} />
    )
  }

  if (asama === 'secim') {
    // Seçim yapılana kadar panelin kendisi hiç kurulmaz; Studio seçilirse
    // PlatformSecici zaten sayfayı oraya taşır.
    return <PlatformSecici onSec={() => setAsama('panel')} />
  }

  // 'giris' ve 'panel' aynı ağacı çizer: panelin kendi yönlendiricisi oturum
  // yoksa /login'e düşürüyor. Girişten sonra LoginPage tam yükleme yapıyor
  // (bkz. lib/auth.jsx) ve akış baştan, bu kez token'lı olarak kuruluyor.
  if (asama === 'panel' && secilenPlatform() === 'studio') {
    location.replace(STUDIO_ADRES)
    return null
  }
  return panel()
}
