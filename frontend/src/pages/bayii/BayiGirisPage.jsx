/**
 * "BERNZ — Bayii Giriş Paneli"
 *
 * Yonetim giris ekranindan ayri: bayiye kayit / gecis anahtari / sifremi
 * unuttum akislari gosterilmez, hesaplari biz aciyoruz.
 */
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../lib/auth'
import { bayiMi } from '../../lib/bayii'

export default function BayiGirisPage() {
  const { login, verifyTwoFactor, user, loading: yukleniyor } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [sifre, setSifre] = useState('')
  const [gorunur, setGorunur] = useState(false)
  const [hata, setHata] = useState('')
  const [bekle, setBekle] = useState(false)
  const [mfa, setMfa] = useState('')
  const [kod, setKod] = useState('')
  const emailRef = useRef(null)

  useEffect(() => { emailRef.current?.focus() }, [])

  // Zaten girisli bayi giris ekranini gormesin
  useEffect(() => {
    if (!yukleniyor && user) navigate(bayiMi(user) ? '/bayii' : '/', { replace: true })
  }, [yukleniyor, user, navigate])

  const sonra = (me) => {
    // Yonetici bu ekrandan girdiyse kendi paneline gitsin — /bayii onu geri atardi.
    navigate(bayiMi(me?.user) ? '/bayii' : '/', { replace: true })
  }

  const gonder = async (e) => {
    e.preventDefault()
    setHata(''); setBekle(true)
    try {
      const res = await login(email.trim(), sifre)
      if (res?.requires_2fa) setMfa(res.mfa_token)
      else sonra(res)
    } catch (err) {
      setHata(err.detail || 'E-posta veya şifre hatalı')
    } finally { setBekle(false) }
  }

  const kodGonder = async (e) => {
    e.preventDefault()
    setHata(''); setBekle(true)
    try { sonra(await verifyTwoFactor(mfa, kod.trim())) }
    catch (err) { setHata(err.detail || 'Kod doğrulanamadı') }
    finally { setBekle(false) }
  }

  return (
    <div className="min-h-full flex items-center justify-center px-4 py-10 relative overflow-hidden">
      {/* Zemin lekeleri — sayfa arka planinin ustune yavas suzulur */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[560px] h-[560px] rounded-full blur-3xl"
             style={{ background: 'rgb(var(--accent-rgb) / 0.16)', animation: 'blob-drift 18s ease-in-out infinite' }} />
        <div className="absolute bottom-0 right-[8%] w-[380px] h-[380px] rounded-full blur-3xl"
             style={{ background: 'rgb(99 102 241 / 0.12)', animation: 'blob-drift 24s ease-in-out infinite reverse' }} />
      </div>

      <div className="w-full max-w-[400px] relative">
        <div className="text-center mb-7 animate-fadeinup">
          <div className="inline-grid place-items-center w-14 h-14 rounded-2xl mb-4"
               style={{
                 background: 'linear-gradient(145deg, rgb(var(--accent-rgb)), rgb(var(--accent-rgb) / 0.5))',
                 boxShadow: '0 14px 40px -12px rgb(var(--accent-rgb) / 0.9), inset 0 1px 0 rgb(255 255 255 / 0.35)',
               }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-fg)" strokeWidth="1.9"
                 strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
              <path d="M3 9h18M3 9l1.6-4.2A2 2 0 0 1 6.5 3.5h11a2 2 0 0 1 1.9 1.3L21 9M5 9v9.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V9M10 13h4" />
            </svg>
          </div>
          <h1 className="text-[22px] font-semibold text-white tracking-tight">BERNZ</h1>
          <p className="text-[13px] text-gray-400 mt-1.5">Bayii Giriş Paneli</p>
        </div>

        <div className="glass rounded-2xl p-6 animate-fadeinup" style={{ animationDelay: '80ms' }}>
          {hata && (
            <div className="mb-4 text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5 animate-popin">
              {hata}
            </div>
          )}

          {mfa ? (
            <form onSubmit={kodGonder} className="space-y-4">
              <p className="text-[13px] text-gray-400">Doğrulama kodunu gir.</p>
              <input value={kod} onChange={(e) => setKod(e.target.value)} autoFocus
                     inputMode="numeric" maxLength={8} placeholder="000000"
                     className="input w-full text-center tracking-[0.4em] text-lg" />
              <button className="btn-primary w-full" disabled={bekle || kod.length < 6}>
                {bekle ? 'Doğrulanıyor…' : 'Doğrula'}
              </button>
            </form>
          ) : (
            <form onSubmit={gonder} className="space-y-4">
              <div>
                <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-1.5">
                  E-posta
                </label>
                <input ref={emailRef} type="email" value={email} required
                       onChange={(e) => setEmail(e.target.value)}
                       autoComplete="username" placeholder="bayi@ornek.com"
                       className="input w-full" />
              </div>
              <div>
                <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-1.5">
                  Şifre
                </label>
                <div className="relative">
                  <input type={gorunur ? 'text' : 'password'} value={sifre} required
                         onChange={(e) => setSifre(e.target.value)}
                         autoComplete="current-password" placeholder="••••••••"
                         className="input w-full pr-11" />
                  <button type="button" onClick={() => setGorunur((v) => !v)} tabIndex={-1}
                          className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 grid place-items-center
                                     text-gray-500 hover:text-gray-300 transition-colors"
                          aria-label={gorunur ? 'Şifreyi gizle' : 'Şifreyi göster'}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
                         strokeLinecap="round" className="w-[17px] h-[17px]">
                      {gorunur
                        ? <><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z" /><circle cx="12" cy="12" r="2.6" /><path d="M3 3l18 18" /></>
                        : <><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z" /><circle cx="12" cy="12" r="2.6" /></>}
                    </svg>
                  </button>
                </div>
              </div>
              <button className="btn-primary w-full !py-2.5" disabled={bekle}>
                {bekle ? 'Giriş yapılıyor…' : 'Giriş yap'}
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-[11.5px] text-gray-600 mt-5 animate-fadeinup"
           style={{ animationDelay: '160ms' }}>
          Hesabın yok mu? Bayi hesapları bizim tarafımızdan oluşturulur.
        </p>
      </div>
    </div>
  )
}
