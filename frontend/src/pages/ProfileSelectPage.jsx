import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function ProfileSelectPage() {
  const navigate = useNavigate()
  const { selectProfile, tenant } = useAuth()
  const [profiles, setProfiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [pinFor, setPinFor] = useState(null)   // PIN istenen profil
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [picked, setPicked] = useState(null)   // secilen (zoom animasyonu)

  useEffect(() => {
    (async () => {
      try {
        const list = await api.get('/api/auth/profiles')
        setProfiles(Array.isArray(list) ? list : [])
      } catch (e) { setErr('Profiller yüklenemedi') }
      finally { setLoading(false) }
    })()
  }, [])

  const enter = async (p, pinVal) => {
    setBusy(true); setErr('')
    try {
      await selectProfile(p.id, pinVal || null)
      setPicked(p.id)
      try { sessionStorage.setItem('freshLogin', '1') } catch {}
      setTimeout(() => navigate('/', { replace: true }), 650)  // zoom geçiş sonrası
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Giriş başarısız')
      setBusy(false)
      if (pinFor) setPin('')
    }
  }

  const onPick = (p) => {
    if (busy) return
    if (p.has_pin) { setPinFor(p); setPin(''); setErr('') }
    else enter(p)
  }

  const submitPin = () => {
    if (pin.length < 4) { setErr('PIN en az 4 hane'); return }
    enter(pinFor, pin)
  }

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0910]">
      <div className="text-gray-500 text-sm">Yükleniyor…</div>
    </div>
  )

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-[#15131f] via-[#0a0910] to-[#060509] px-4 py-10">
      <h1 className="text-3xl md:text-4xl font-semibold text-gray-100 mb-2 animate-fadein">Kim kullanıyor?</h1>
      <p className="text-sm text-gray-500 mb-10 animate-fadein">{tenant?.name || 'Baskıcı'}</p>

      {err && !pinFor && <div className="text-sm text-red-300 mb-6">{err}</div>}

      <div className="flex flex-wrap items-start justify-center gap-6 md:gap-8 max-w-4xl">
        {profiles.map((p, i) => (
          <button key={p.id} onClick={() => onPick(p)}
            className={`profile-card group flex flex-col items-center gap-3 transition-all duration-500 ${picked && picked !== p.id ? 'opacity-0 scale-90' : ''} ${picked === p.id ? 'scale-150 opacity-0' : ''}`}
            style={{ animation: `fade-in-up 0.5s ease-out ${i * 0.08}s both` }}>
            <div className="profile-avatar relative w-24 h-24 md:w-32 md:h-32 rounded-2xl overflow-hidden bg-brand-input border-2 border-transparent group-hover:border-accent transition-all duration-300 flex items-center justify-center">
              {p.avatar_url
                ? <img src={p.avatar_url} alt="" className="w-full h-full object-cover" />
                : <span className="text-4xl md:text-5xl font-bold text-gray-300">{(p.full_name || '?').charAt(0).toUpperCase()}</span>}
              {p.has_pin && (
                <span className="absolute bottom-1.5 right-1.5 w-6 h-6 rounded-full bg-black/60 backdrop-blur flex items-center justify-center text-xs">🔒</span>
              )}
            </div>
            <span className="text-sm md:text-base text-gray-400 group-hover:text-gray-100 transition-colors">{p.full_name}</span>
            <span className="text-[10px] text-gray-600 -mt-2">{p.role}</span>
          </button>
        ))}
      </div>

      {/* PIN modal */}
      {pinFor && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onMouseDown={e => e.target === e.currentTarget && !busy && setPinFor(null)}>
          <div className="bg-brand-card border border-brand-border rounded-2xl w-full max-w-xs p-6 animate-popin text-center">
            <div className="w-16 h-16 mx-auto rounded-2xl overflow-hidden bg-brand-input border border-brand-border flex items-center justify-center mb-3">
              {pinFor.avatar_url ? <img src={pinFor.avatar_url} alt="" className="w-full h-full object-cover" />
                : <span className="text-2xl font-bold text-gray-300">{(pinFor.full_name || '?').charAt(0).toUpperCase()}</span>}
            </div>
            <h3 className="text-base font-semibold text-gray-100 mb-1">{pinFor.full_name}</h3>
            <p className="text-xs text-gray-500 mb-4">PIN gir</p>
            <input autoFocus type="password" inputMode="numeric" value={pin}
              onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))}
              onKeyDown={e => e.key === 'Enter' && submitPin()}
              className="input w-full text-center text-2xl tracking-[0.4em] mb-3" placeholder="••••" />
            {err && <div className="text-xs text-red-300 mb-3">{err}</div>}
            <div className="flex gap-2">
              <button onClick={() => !busy && setPinFor(null)} className="btn-secondary !text-sm flex-1">İptal</button>
              <button onClick={submitPin} disabled={busy} className="btn-primary !text-sm flex-1">{busy ? '…' : 'Gir'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
