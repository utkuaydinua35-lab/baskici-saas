import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../lib/auth'

// Telifsiz, dosyasiz "whoosh" sesi — Web Audio ile uretilir. Varsayilan KAPALI.
function playWhoosh() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const now = ctx.currentTime

    // Master + yumusak reverb (convolver yerine kisa feedback delay zinciri ile derinlik)
    const master = ctx.createGain()
    master.gain.value = 0.0001
    master.gain.setValueAtTime(0.0001, now)
    master.gain.exponentialRampToValueAtTime(0.22, now + 0.25)
    master.gain.exponentialRampToValueAtTime(0.0001, now + 1.8)
    const lp = ctx.createBiquadFilter()
    lp.type = 'lowpass'
    lp.frequency.value = 5200
    master.connect(lp); lp.connect(ctx.destination)

    // Hafif "shimmer" gecikme (uzayan parlama hissi)
    const delay = ctx.createDelay()
    delay.delayTime.value = 0.18
    const fb = ctx.createGain()
    fb.gain.value = 0.28
    const wet = ctx.createGain()
    wet.gain.value = 0.35
    lp.connect(delay); delay.connect(fb); fb.connect(delay); delay.connect(wet); wet.connect(ctx.destination)

    // Yumusak sinus tonu uretici (nazik attack + uzun release)
    const tone = (freq, t0, dur, peak) => {
      const o = ctx.createOscillator()
      const g = ctx.createGain()
      o.type = 'sine'
      o.frequency.value = freq
      // hafif detune ile sicaklik
      const o2 = ctx.createOscillator()
      o2.type = 'sine'
      o2.frequency.value = freq * 1.005
      g.gain.setValueAtTime(0.0001, now + t0)
      g.gain.exponentialRampToValueAtTime(peak, now + t0 + 0.06)
      g.gain.exponentialRampToValueAtTime(0.0001, now + t0 + dur)
      o.connect(g); o2.connect(g); g.connect(master)
      o.start(now + t0); o.stop(now + t0 + dur + 0.05)
      o2.start(now + t0); o2.stop(now + t0 + dur + 0.05)
    }

    // Sicak major akor (C5 - E5 - G5) — arpejli, zarif yukselen giris
    tone(523.25, 0.00, 1.4, 0.5)   // C5
    tone(659.25, 0.09, 1.3, 0.42)  // E5
    tone(783.99, 0.18, 1.25, 0.4)  // G5
    // Ince parlama (yuksek oktav chime, shimmer ile senkron)
    tone(1046.50, 0.30, 1.0, 0.22) // C6

    setTimeout(() => ctx.close().catch(() => {}), 2200)
  } catch {}
}

const SOUND_KEY = 'splashSound'

export default function SplashScreen({ onDone }) {
  const { user, tenant } = useAuth()
  const [leaving, setLeaving] = useState(false)
  const [revealed, setRevealed] = useState(false)
  const [sound, setSound] = useState(() => {
    try { return localStorage.getItem(SOUND_KEY) === '1' } catch { return false }
  })
  const played = useRef(false)

  useEffect(() => {
    const tReveal = setTimeout(() => setRevealed(true), 120)     // logo reveal başlasın
    const t1 = setTimeout(() => setLeaving(true), 2100)          // sinematik çıkış
    const t2 = setTimeout(() => onDone?.(), 2700)               // tamamen kapansın
    if (sound && !played.current) { played.current = true; playWhoosh() }
    return () => { clearTimeout(tReveal); clearTimeout(t1); clearTimeout(t2) }
  }, [onDone, sound])

  const skip = () => { setLeaving(true); setTimeout(() => onDone?.(), 450) }
  const toggleSound = (e) => {
    e.stopPropagation()
    const nv = !sound
    setSound(nv)
    try { localStorage.setItem(SOUND_KEY, nv ? '1' : '0') } catch {}
    if (nv) playWhoosh()
  }

  const name = (user?.full_name || '').split(' ')[0] || ''

  return (
    <div
      onClick={skip}
      className={`splash-root fixed inset-0 z-[200] flex flex-col items-center justify-center cursor-pointer ${leaving ? 'splash-leaving' : ''}`}
    >
      {/* Sinematik letterbox bantlar */}
      <div className={`splash-bar splash-bar-top ${revealed ? 'open' : ''} ${leaving ? 'close' : ''}`} />
      <div className={`splash-bar splash-bar-bottom ${revealed ? 'open' : ''} ${leaving ? 'close' : ''}`} />

      {/* Arka plan parlama */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className={`splash-glow ${revealed ? 'on' : ''}`} />
      </div>

      {/* Logo + shimmer */}
      <div className={`relative z-10 transition-all duration-[600ms] ${leaving ? 'scale-[1.7] opacity-0 blur-sm' : revealed ? 'scale-100 opacity-100 blur-0' : 'scale-[0.7] opacity-0 blur-md'}`}>
        <div className="splash-logo-wrap">
          {tenant?.logo_url ? (
            <img src={tenant.logo_url} alt={tenant?.name || 'Logo'} className="h-28 max-w-[300px] object-contain rounded-2xl" />
          ) : (
            <div className="w-28 h-28 rounded-2xl bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white text-5xl font-bold">
              {(tenant?.name || 'B').charAt(0).toUpperCase()}
            </div>
          )}
          {revealed && <span className="splash-shimmer" />}
        </div>
      </div>

      {/* Karşılama */}
      <div className={`relative z-10 mt-7 text-center transition-all duration-700 ${leaving ? 'opacity-0 translate-y-3' : revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`} style={{ transitionDelay: revealed && !leaving ? '0.5s' : '0s' }}>
        <div className="text-2xl font-semibold text-gray-100 tracking-tight">
          {name ? `Hoş geldin, ${name}` : 'Hoş geldin'}
        </div>
        <div className="text-sm text-gray-500 mt-1.5">{tenant?.name || 'Baskıcı'}</div>
      </div>

      {/* Ses toggle (sağ üst) */}
      <button onClick={toggleSound} title={sound ? 'Sesi kapat' : 'Sesi aç'}
        className="absolute top-5 right-5 z-20 w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center text-gray-300 transition-colors">
        {sound ? '🔊' : '🔇'}
      </button>

      {/* Atla ipucu */}
      <div className={`absolute bottom-6 text-[11px] text-gray-600 transition-opacity duration-500 ${leaving ? 'opacity-0' : revealed ? 'opacity-100' : 'opacity-0'}`}>
        geçmek için dokun
      </div>
    </div>
  )
}
