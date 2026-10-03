/**
 * "Geçiş anahtarı" teklifi — bayi parolayla uğraşmasın.
 *
 * Passkey altyapısı zaten vardı ama bayiler varlığından habersizdi; bu kart
 * panelin ana ekranında bir kez teklif eder, kurulunca kendini gizler.
 * "Daha sonra" diyen bir daha görmez (tarayıcıda saklanır) — ısrarcı değil.
 */
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { passkeySupported, registerPasskey } from '../lib/webauthn'

const ERTELE_ANAHTAR = 'bayi_gecis_anahtari_ertelendi'

export default function BayiGecisAnahtari() {
  const [durum, setDurum] = useState('yukleniyor')   // yukleniyor | teklif | kuruldu | gizli
  const [hata, setHata] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!passkeySupported()) { setDurum('gizli'); return }
    let ertelendi = false
    try { ertelendi = localStorage.getItem(ERTELE_ANAHTAR) === '1' } catch { /* özel mod */ }
    api.get('/api/auth/passkey')
      .then((liste) => {
        const varMi = Array.isArray(liste) && liste.length > 0
        setDurum(varMi ? 'kuruldu' : (ertelendi ? 'gizli' : 'teklif'))
      })
      .catch(() => setDurum('gizli'))
  }, [])

  const kur = async () => {
    setBusy(true); setHata('')
    try {
      await registerPasskey(cihazAdi())
      setDurum('kuruldu')
    } catch (e) {
      // Kullanıcı sistem penceresini kapattıysa hata değil, vazgeçmedir
      const m = String(e?.message || e?.detail || '')
      setHata(/NotAllowed|AbortError|iptal/i.test(m)
        ? 'Vazgeçildi — istediğin zaman tekrar deneyebilirsin.'
        : (e?.detail || 'Geçiş anahtarı kaydedilemedi'))
    } finally { setBusy(false) }
  }

  const ertele = () => {
    try { localStorage.setItem(ERTELE_ANAHTAR, '1') } catch { /* özel mod */ }
    setDurum('gizli')
  }

  if (durum === 'gizli' || durum === 'yukleniyor') return null

  if (durum === 'kuruldu') {
    return (
      <div className="card border-emerald-500/25 bg-emerald-500/5 flex items-center gap-3">
        <span className="text-xl">🔐</span>
        <div className="min-w-0">
          <div className="text-sm text-emerald-300">Geçiş anahtarın kurulu</div>
          <div className="text-[12px] text-emerald-400/75">
            Bir sonraki girişte parola yerine parmak izi / yüz tanıma ya da cihaz şifren yeterli.
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card border-accent/30 bg-accent/5">
      <div className="flex items-start gap-3">
        <span className="text-2xl">🔐</span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-white">Parola yazmadan gir</div>
          <p className="text-[12.5px] text-gray-400 mt-1 leading-relaxed">
            Bu cihaza bir <b>geçiş anahtarı</b> kaydet; bir daha parola yazmana gerek kalmaz.
            Girişte parmak izi, yüz tanıma ya da bilgisayarının şifresi yeterli olur.
            Anahtar yalnız bu cihazda durur, biz göremeyiz.
          </p>
          {hata && <div className="text-[12px] text-amber-300 mt-2">{hata}</div>}
          <div className="flex gap-2 mt-3">
            <button onClick={kur} disabled={busy} className="btn-primary !text-sm disabled:opacity-50">
              {busy ? 'Kaydediliyor…' : 'Geçiş anahtarı oluştur'}
            </button>
            <button onClick={ertele} className="btn-secondary !text-sm">Daha sonra</button>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Anahtara anlamlı bir ad: "Mac · Chrome" gibi. */
function cihazAdi() {
  const ua = navigator.userAgent || ''
  const sistem = /Windows/i.test(ua) ? 'Windows'
    : /Mac OS X|Macintosh/i.test(ua) ? 'Mac'
    : /Android/i.test(ua) ? 'Android'
    : /iPhone|iPad/i.test(ua) ? 'iPhone' : 'Bilgisayar'
  const tarayici = /Edg\//i.test(ua) ? 'Edge'
    : /Chrome\//i.test(ua) ? 'Chrome'
    : /Safari\//i.test(ua) ? 'Safari'
    : /Firefox\//i.test(ua) ? 'Firefox' : ''
  return [sistem, tarayici].filter(Boolean).join(' · ')
}
