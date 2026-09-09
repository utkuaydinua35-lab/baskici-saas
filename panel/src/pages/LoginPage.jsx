import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { BRAND, TAGLINE } from '../lib/brand'
import BrandMark from '../components/BrandMark'
import { loginPasskey, passkeySupported } from '../lib/webauthn'
import { setToken } from '../lib/api'
import { NATIVE } from '../lib/taban'
import { kilidiAcikIsaretle } from '../KabukAkisi'

/**
 * Animasyonlu dekoratif arka plan — Baskıcı Paneli'ndeki düzenin mağaza
 * paleti ile karşılığı: dolaşan ışık lekeleri, kayan nokta ızgara ve
 * yükselen zerrecikler. Süreler birbirine bölünmüyor ki döngüler aynı anda
 * başa sarıp tekrar hissi vermesin. Tamamı `prefers-reduced-motion` açıkken
 * durur (bkz. index.css).
 */

// Sabit liste — her render'da rastgele üretilseydi kullanıcı yazdıkça
// zerreler baştan başlardı.
const ZERRELER = [
  { sol: '6%',  boy: 5, sure: 9,  gecikme: 0,  opak: 0.8 },
  { sol: '14%', boy: 3, sure: 13, gecikme: 4,  opak: 0.6 },
  { sol: '23%', boy: 6, sure: 11, gecikme: 8,  opak: 0.75 },
  { sol: '31%', boy: 3, sure: 15, gecikme: 2,  opak: 0.55 },
  { sol: '42%', boy: 5, sure: 10, gecikme: 6,  opak: 0.8 },
  { sol: '50%', boy: 3, sure: 14, gecikme: 10, opak: 0.55 },
  { sol: '58%', boy: 6, sure: 12, gecikme: 1,  opak: 0.7 },
  { sol: '67%', boy: 3, sure: 16, gecikme: 7,  opak: 0.6 },
  { sol: '75%', boy: 5, sure: 10, gecikme: 11, opak: 0.75 },
  { sol: '83%', boy: 3, sure: 13, gecikme: 3,  opak: 0.55 },
  { sol: '91%', boy: 6, sure: 11, gecikme: 9,  opak: 0.7 },
  { sol: '97%', boy: 3, sure: 15, gecikme: 5,  opak: 0.5 },
]

function GirisArkaPlan() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="giris-blob-a absolute -top-32 -left-32 w-[28rem] h-[28rem] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, #0075ff 0%, transparent 70%)' }} />
      <div className="giris-blob-b absolute top-1/4 -right-40 w-[34rem] h-[34rem] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, #4318ff 0%, transparent 70%)' }} />
      <div className="giris-blob-c absolute -bottom-40 left-1/5 w-[26rem] h-[26rem] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, #21d4fd 0%, transparent 70%)' }} />
      <div className="giris-blob-d absolute top-[-6rem] right-1/4 w-[22rem] h-[22rem] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, #9f7aea 0%, transparent 70%)' }} />

      {/* Ekranı boydan boya geçen huzmeler — hareketin asıl okunduğu katman. */}
      <div className="giris-huzme" style={{
        left: 0, background: 'linear-gradient(90deg, transparent, rgba(0,117,255,0.34), transparent)',
        animationDuration: '17s' }} />
      <div className="giris-huzme" style={{
        left: 0, background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.10), transparent)',
        animationDuration: '26s', animationDelay: '-9s' }} />
      <div className="giris-huzme" style={{
        left: 0, background: 'linear-gradient(90deg, transparent, rgba(33,212,253,0.30), transparent)',
        animationDuration: '21s', animationDelay: '-14s' }} />

      <div className="giris-izgara absolute inset-0 opacity-[0.05]"
        style={{ backgroundImage: 'radial-gradient(rgb(255 255 255) 1px, transparent 1px)', backgroundSize: '28px 28px' }} />

      {ZERRELER.map((z, i) => (
        <span key={i} className="giris-zerre absolute bottom-[-6vh] rounded-full bg-white"
          style={{
            left: z.sol, width: z.boy, height: z.boy, opacity: z.opak,
            boxShadow: '0 0 6px rgba(255,255,255,0.6)',
            animationDuration: `${z.sure}s`,
            animationDelay: `-${z.gecikme}s`,   // negatif: sayfa açılır açılmaz dolu görünsün
          }} />
      ))}
    </div>
  )
}

// Giriş — Baskıcı ile aynı hesaplar (2FA destekli).
export default function LoginPage() {
  const { login, verifyTwoFactor } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mfaToken, setMfaToken] = useState(null)   // dolu → kod adımı
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pkBusy, setPkBusy] = useState(false)

  /**
   * Giriş başarılı — nereye gidilecek?
   *
   * Web'de her şey aynı: panelin köküne git. UYGULAMADA ise girişten sonra
   * PLATFORM SEÇİMİ geliyor; kabuk akışının (KabukAkisi.jsx) yeni token'la
   * baştan kurulması için tam yükleme yapılır. Ayrıca kilit bu açılışta
   * zaten aşılmış sayılır — kullanıcı az önce şifresini girdi, hemen
   * ardından yüz/parmak istemek gereksiz olurdu.
   */
  const girisTamam = () => {
    if (!NATIVE) { navigate('/', { replace: true }); return }
    kilidiAcikIsaretle()
    window.location.replace('/')
  }

  // Geçiş anahtarı (passkey) ile giriş — şifre/2FA gerekmez, phishing-dirençli.
  // Aynı anahtar Baskıcı panelinde de geçerlidir (ortak RP ID).
  const passkeyLogin = async () => {
    setPkBusy(true); setError('')
    try {
      const data = await loginPasskey()
      setToken(data.access_token)
      if (NATIVE) kilidiAcikIsaretle()
      window.location.replace('/')   // auth context'i taze token'la kursun
    } catch (e2) {
      const msg = typeof e2?.detail === 'string' ? e2.detail
        : e2?.name === 'NotAllowedError' ? 'Geçiş anahtarı iptal edildi'
        : 'Geçiş anahtarıyla giriş yapılamadı'
      setError(msg)
    } finally { setPkBusy(false) }
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      if (mfaToken) {
        await verifyTwoFactor(mfaToken, code.trim())
        girisTamam()
        return
      }
      const r = await login(email.trim(), password)
      if (r?.requires_2fa) { setMfaToken(r.mfa_token); return }
      girisTamam()
    } catch (e2) {
      setError(typeof e2?.detail === 'string' ? e2.detail : 'Giriş başarısız')
    } finally { setBusy(false) }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center p-6 bg-panel-bg overflow-hidden">
      <GirisArkaPlan />
      <div className="relative w-full max-w-sm">
        <div className="giris-kademe-1 flex items-center gap-2.5 justify-center mb-6">
          <span className="giris-logo relative inline-flex">
            <span className="giris-hale" aria-hidden="true" />
            <BrandMark size={40} />
          </span>
          <div>
            <div className="font-semibold leading-tight">{BRAND}</div>
            <div className="text-xs text-panel-muted leading-tight">{TAGLINE}</div>
          </div>
        </div>

        <form onSubmit={submit} className="giris-kart giris-kademe-2 card !p-6 space-y-3">
          {!mfaToken ? (
            <>
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">E-posta</span>
                <input className="input mt-1" type="email" value={email} required
                  autoComplete="email" onChange={e => setEmail(e.target.value)} />
              </label>
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">Şifre</span>
                <input className="input mt-1" type="password" value={password} required
                  autoComplete="current-password" onChange={e => setPassword(e.target.value)} />
              </label>
            </>
          ) : (
            <label className="block text-sm">
              <span className="text-panel-muted text-xs">Doğrulama kodu (authenticator)</span>
              <input className="input mt-1 font-mono text-center tracking-widest" value={code}
                required autoFocus maxLength={10} onChange={e => setCode(e.target.value)} />
            </label>
          )}
          {error && <p className="text-xs text-red-300">{error}</p>}
          <button disabled={busy} className="giris-parla btn-primary relative overflow-hidden w-full">
            {busy ? 'Giriş yapılıyor…' : mfaToken ? 'Doğrula' : 'Giriş Yap'}
          </button>

          {!mfaToken && passkeySupported() && (
            <>
              <div className="flex items-center gap-2 pt-1">
                <div className="h-px flex-1 bg-panel-border" />
                <span className="text-[11px] text-panel-muted">veya</span>
                <div className="h-px flex-1 bg-panel-border" />
              </div>
              <button type="button" onClick={passkeyLogin} disabled={pkBusy}
                className="giris-parla btn-ghost relative overflow-hidden w-full !py-2.5 text-sm">
                {pkBusy ? 'Bekleniyor…' : '🔑 Geçiş anahtarı ile giriş'}
              </button>
            </>
          )}
        </form>
        <p className="mt-4 text-center text-xs text-panel-muted">
          Hesaplar Baskıcı Paneli ile ortaktır.
        </p>
      </div>
    </div>
  )
}
