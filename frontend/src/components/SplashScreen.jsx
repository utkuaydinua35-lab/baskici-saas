import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../lib/auth'

// Telifsiz, dosyasiz "whoosh" sesi — Web Audio ile uretilir. Varsayilan KAPALI.
function playWhoosh() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const now = ctx.currentTime
    // Yukselen suzgecli gurultu + alcalan ton (sinematik "whoosh")
    const o = ctx.createOscillator()
    const g = ctx.createGain()
    const f = ctx.createBiquadFilter()
    o.type = 'sawtooth'
    o.frequency.setValueAtTime(120, now)
    o.frequency.exponentialRampToValueAtTime(420, now + 0.5)
    f.type = 'lowpass'
    f.frequency.setValueAtTime(300, now)
    f.frequency.exponentialRampToValueAtTime(2400, now + 0.5)
    g.gain.setValueAtTime(0.0001, now)
    g.gain.exponentialRampToValueAtTime(0.18, now + 0.18)
    g.gain.exponentialRampToValueAtTime(0.0001, now + 0.7)
    o.connect(f); f.connect(g); g.connect(ctx.destination)
    o.start(now); o.stop(now + 0.72)
    setTimeout(() => ctx.close().catch(() => {}), 1000)
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
