import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { worklistGetir } from '../lib/worklist'

// ── Worklist yardımcıları ─────────────────────────────────────────────────────
const WL_KEY = 'wl_state'

function wlGetState() {
  try {
    const s = JSON.parse(localStorage.getItem(WL_KEY) || '{}')
    const today = new Date().toISOString().slice(0, 10)
    if (s.date !== today) return { date: today, count: 0, dismissed: false }
    return s
  } catch { return { date: new Date().toISOString().slice(0, 10), count: 0, dismissed: false } }
}

function wlSave(s) { localStorage.setItem(WL_KEY, JSON.stringify(s)) }

function isMorning() {
  const h = parseInt(
    new Intl.DateTimeFormat('tr-TR', { hour: 'numeric', hour12: false, timeZone: 'Europe/Istanbul' })
      .format(new Date()), 10,
  )
  return h >= 6 && h < 12
}

function WorklistBanner({ data, onDismiss }) {
  const colors = {
    urgent: 'border-red-500/40 bg-red-500/10 text-red-300',
    warning: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
    normal: 'border-brand-border bg-brand-input text-gray-200',
  }
  return (
    <div className="card mb-5 border-l-4 border-accent animate-fadein">
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="text-base font-semibold text-gray-100">{data.greeting}</div>
          <div className="text-xs text-gray-500 mt-0.5">{data.role_label} · Bugünün görev listesi</div>
        </div>
        <button onClick={onDismiss} className="text-gray-500 hover:text-gray-300 text-sm leading-none ml-3">✕</button>
      </div>
      {data.items.length === 0 ? (
        <p className="text-sm text-emerald-400">✓ Her şey yolunda, bugün bekleyen görev yok!</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {data.items.map(item => (
            <a key={item.key} href={item.link}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm transition-opacity hover:opacity-80 ${colors[item.severity] || colors.normal}`}
            >
              <span className="text-xl shrink-0">{item.icon}</span>
              <div className="min-w-0">
                <div className="font-bold text-lg leading-none">{item.count}</div>
                <div className="text-[10px] leading-tight opacity-80 mt-0.5">{item.label}</div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
// ─────────────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user, tenant } = useAuth()
  const navigate = useNavigate()
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showCiro, setShowCiro] = useState(() => localStorage.getItem('dash_show_ciro') !== '0')
  const [worklist, setWorklist] = useState(null)
  const [showWorklist, setShowWorklist] = useState(false)

  useEffect(() => {
    (async () => {
      try { const s = await api.get('/api/stores'); setStores(Array.isArray(s) ? s : []) } catch {}
    })()
  }, [])

  // Sabah worklist — ilk 5 dashboard ziyaretinde banner göster
  useEffect(() => {
    // Zil bildiriminden gelindiyse (?worklist=1) sayaçtan bağımsız zorla göster
    const forced = new URLSearchParams(window.location.search).get('worklist') === '1'
    if (forced) {
      worklistGetir().then(wl => { setWorklist(wl); setShowWorklist(true) }).catch(() => {})
      window.history.replaceState({}, '', '/')
      return
    }
    const state = wlGetState()
    if (!state.dismissed && state.count < 5) {
      // Zil de aynı açılışta istiyor — ortak söz, tek istek (lib/worklist)
      worklistGetir().then(wl => {
        setWorklist(wl)
        setShowWorklist(true)
        const newState = { ...state, count: state.count + 1 }
        wlSave(newState)
        // 5. görüntülemede bell'e sinyal ver
        if (newState.count >= 5) {
          window.dispatchEvent(new CustomEvent('worklist:ready', { detail: wl }))
        }
      }).catch(() => {})
    }
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.get(`/api/dashboard/summary${storeId ? `?store_id=${storeId}` : ''}`)
      setData(r)
    } catch { setData(null) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [storeId])

  const k = data?.kpis || {}
  const maxFunnel = Math.max(1, ...(data?.funnel || []).map(f => f.count))

  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">
            Hoş geldin, {user?.full_name?.split(' ')[0] || 'sen'} 👋
          </h1>
          <p className="text-sm text-gray-500 mt-1">{tenant?.name}</p>
        </div>
        <select value={storeId} onChange={e => setStoreId(e.target.value)} className="input !text-sm">
          <option value="">Tüm mağazalar</option>
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>

      {showWorklist && worklist && (
        <WorklistBanner
          data={worklist}
          onDismiss={() => { setShowWorklist(false); wlSave({ ...wlGetState(), dismissed: true }) }}
        />
      )}

      {loading && (
        <div className="animate-fadein">
          <div className="mb-6">
            <div className="skeleton h-4 w-24 mb-3 rounded" />
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[0,1,2].map(i => <div key={i} className="card !py-4"><div className="skeleton h-3 w-16 mb-3 rounded" /><div className="skeleton h-6 w-28 rounded" /></div>)}
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[0,1,2,3,4,5,6,7].map(i => <div key={i} className="card !py-4"><div className="skeleton h-3 w-20 mb-3 rounded" /><div className="skeleton h-7 w-12 rounded" /></div>)}
          </div>
        </div>
      )}

      {!loading && data && (
        <>
          <div className="mb-6 animate-fadein">
            <div className="flex items-center gap-2 mb-2">
              <h2 className="text-sm font-semibold text-gray-300">💰 Ciro</h2>
              <span className="text-[10px] text-gray-600">(iptal + iade hariç)</span>
              <button onClick={() => setShowCiro(v => { const nv = !v; localStorage.setItem('dash_show_ciro', nv ? '1' : '0'); return nv })} className="ml-auto text-xs text-gray-400 hover:text-gray-200 flex items-center gap-1">
                {showCiro ? '🙈 Gizle' : '👁️ Göster'}
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <CiroCard label="BUGÜN" value={data?.ciro?.bugun} usd={data?.ciro?.usd?.bugun} show={showCiro} />
              <CiroCard label="BU HAFTA" value={data?.ciro?.hafta} usd={data?.ciro?.usd?.hafta} show={showCiro} />
              <CiroCard label="BU AY" value={data?.ciro?.ay} usd={data?.ciro?.usd?.ay} show={showCiro} accent />
            </div>
            <CiroChart data={data?.ciro?.gunluk} show={showCiro} />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <Kpi label="AÇIK SİPARİŞ" value={k.acik_siparis} onClick={() => navigate('/orders')} />
            <Kpi label="BUGÜN GELEN" value={k.bugun_gelen} color="accent" onClick={() => navigate('/orders')} />
            <Kpi label="ACİL" value={k.acil} color={k.acil > 0 ? 'red' : 'gray'} onClick={() => navigate('/orders')} />
            <Kpi label="AÇIK KALIP" value={k.acik_kalip} onClick={() => navigate('/kalip-olustur')} />
            <Kpi label="PAKETLEME BEKLEYEN" value={k.paketleme_bekleyen} color="amber" onClick={() => navigate('/paketleme')} />
            <Kpi label="KARGO BEKLEYEN" value={k.kargo_bekleyen} color="amber" />
            <Kpi label="ASKIDA (ADET)" value={k.aski_adet} onClick={() => navigate('/aski')} />
            <Kpi label="DÜŞÜK STOK" value={k.dusuk_stok} color={k.dusuk_stok > 0 ? 'red' : 'gray'} onClick={() => navigate('/stok')} />
            <Kpi label="AÇIK TELAFİ" value={k.telafi_acik} color={k.telafi_acik > 0 ? 'amber' : 'gray'} onClick={() => navigate('/telafiler')} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Üretim hattı */}
            <div className="card">
              <h2 className="text-sm font-semibold text-gray-200 mb-3">Üretim Hattı</h2>
              <div className="space-y-1.5">
                {(data.funnel || []).map(f => (
                  <div key={f.no} className="flex items-center gap-2">
                    <div className="w-28 text-xs text-gray-400 shrink-0 truncate">{f.no}. {f.label}</div>
                    <div className="flex-1 bg-brand-input rounded-full h-5 overflow-hidden relative">
                      <div className="h-full bg-gradient-to-r from-accent to-teal-600 rounded-full transition-all"
                           style={{ width: `${(f.count / maxFunnel) * 100}%`, minWidth: f.count > 0 ? '8px' : '0' }} />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[11px] text-gray-300">{f.count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Düşük stok */}
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-gray-200">Düşük Stok</h2>
                <button onClick={() => navigate('/stok')} className="text-[11px] text-accent hover:underline">Stok →</button>
              </div>
              {(data.low_stock || []).length === 0 ? (
                <div className="text-xs text-gray-500 py-6 text-center">Eşik altı stok yok 👍</div>
              ) : (
                <div className="space-y-1.5 max-h-72 overflow-y-auto">
                  {data.low_stock.map(s => (
                    <div key={s.id} className="flex items-center justify-between text-sm py-1 border-b border-brand-border/40">
                      <div className="min-w-0">
                        <span className="font-mono text-[11px] text-accent">{s.sku}</span>
                        <span className="text-gray-300 ml-2">{s.name}</span>
                        {(s.variation || s.model) && (
                          <span className="text-[10px] text-gray-500 ml-1">
                            {[s.variation, s.model].filter(Boolean).join(' · ')}
                          </span>
                        )}
                      </div>
                      <span className="text-red-400 font-semibold shrink-0 ml-2">{s.quantity}/{s.threshold}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Telafi sebepleri */}
          {(data.telafi?.sebepler || []).length > 0 && (
            <div className="card mt-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-gray-200">♻️ En Sık Telafi Sebepleri</h2>
                <button onClick={() => navigate('/telafiler')} className="text-[11px] text-accent hover:underline">Telafiler →</button>
              </div>
              <div className="space-y-1.5">
                {(() => {
                  const maxS = Math.max(1, ...data.telafi.sebepler.map(s => s.adet))
                  return data.telafi.sebepler.map((s, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div className="w-40 text-xs text-gray-300 shrink-0 truncate">{s.sebep}</div>
                      <div className="flex-1 bg-brand-input rounded-full h-5 overflow-hidden relative">
                        <div className="h-full bg-gradient-to-r from-amber-500 to-amber-600 rounded-full transition-all"
                             style={{ width: `${(s.adet / maxS) * 100}%`, minWidth: '8px' }} />
                        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[11px] text-gray-200">{s.adet}</span>
                      </div>
                    </div>
                  ))
                })()}
              </div>
            </div>
          )}

          {/* Son hareketler */}
          <div className="card mt-4">
            <h2 className="text-sm font-semibold text-gray-200 mb-3">Son Hareketler</h2>
            {(data.recent || []).length === 0 ? (
              <div className="text-xs text-gray-500 py-4 text-center">Henüz hareket yok</div>
            ) : (
              <div className="space-y-2">
                {data.recent.map(n => (
                  <div key={n.id} className="flex gap-2 text-sm">
                    <span className="shrink-0">{n.kind === 'error' ? '⚠' : n.kind === 'info' ? 'ℹ' : '🔄'}</span>
                    <div className="min-w-0 flex-1">
                      <div className="text-gray-300 leading-snug">{n.title}</div>
                      {n.body && <div className="text-[11px] text-gray-500 truncate">{n.body}</div>}
                    </div>
                    <span className="text-[10px] text-gray-600 shrink-0">{fmt(n.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso), now = new Date(), diff = (now - d) / 1000
  if (diff < 60) return 'az önce'
  if (diff < 3600) return `${Math.floor(diff / 60)} dk`
  if (diff < 86400) return `${Math.floor(diff / 3600)} sa`
  return d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' })
}

function useCountUp(target, active, duration = 850) {
  const [val, setVal] = useState(0)
  const ref = useRef({ raf: 0, from: 0 })
  useEffect(() => {
    if (!active || target == null) { setVal(target || 0); return }
    const start = performance.now()
    const from = ref.current.from
    const ease = (t) => 1 - Math.pow(1 - t, 3)  // easeOutCubic
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1)
      setVal(from + (target - from) * ease(p))
      if (p < 1) ref.current.raf = requestAnimationFrame(tick)
      else ref.current.from = target
    }
    cancelAnimationFrame(ref.current.raf)
    ref.current.raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(ref.current.raf)
  }, [target, active, duration])
  return val
}

function CiroChart({ data, show }) {
  if (!Array.isArray(data) || data.length === 0) return null
  const W = 700, H = 90, P = 4
  const vals = data.map(d => d.tutar || 0)
  const max = Math.max(...vals, 1)
  const n = data.length
  const x = (i) => P + (i / (n - 1)) * (W - 2 * P)
  const y = (v) => H - P - (v / max) * (H - 2 * P)
  const linePts = data.map((d, i) => `${x(i)},${y(d.tutar || 0)}`).join(' ')
  const areaPts = `${P},${H - P} ${linePts} ${W - P},${H - P}`
  const fmt = (n) => new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 0 }).format(n)
  const toplam = vals.reduce((a, b) => a + b, 0)
  const son = data[n - 1]
  return (
    <div className={`card !py-4 mt-3 transition-all ${!show ? 'blur-sm select-none' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-gray-500 font-medium tracking-wide">SON 30 GÜN</span>
        <span className="text-[11px] text-gray-400">Toplam: <span className="text-gray-200 font-semibold tabular-nums">₺{show ? fmt(toplam) : '•••'}</span></span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none" style={{ height: 90 }}>
        <defs>
          <linearGradient id="ciroFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(124,92,255)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="rgb(124,92,255)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={areaPts} fill="url(#ciroFill)" className="ciro-area" />
        <polyline points={linePts} fill="none" stroke="rgb(124,92,255)" strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round" className="ciro-line" />
        {son && <circle cx={x(n - 1)} cy={y(son.tutar || 0)} r="3.5" fill="rgb(124,92,255)" className="ciro-dot" />}
      </svg>
    </div>
  )
}

// `usd`: USD bayilerinin ürün bedeli. TL'ye ÇEVRİLMEZ (sistemde kur kaynağı yok,
// uydurma kur yanlış toplamdan daha tehlikeli) — ayrı satırda gösterilir.
function CiroCard({ label, value, usd, show, accent }) {
  const animated = useCountUp(value, show)
  const fmt = (n) => {
    if (n == null) return '—'
    return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', minimumFractionDigits: 2 }).format(n)
  }
  return (
    <div className={`card !py-4 transition-all ${accent ? 'border-accent/30 bg-accent/5' : ''}`}>
      <div className="text-[11px] text-gray-500 font-medium tracking-wide">{label}</div>
      <div className={`text-xl font-bold mt-1 tabular-nums ${accent ? 'text-accent' : 'text-gray-100'} ${!show ? 'blur-sm select-none' : ''}`}>
        {show ? fmt(animated) : '₺ ••••••'}
      </div>
      {show && usd > 0 && (
        <div className="text-[11px] text-gray-400 mt-0.5 tabular-nums" title="USD bayi siparişleri — TL'ye çevrilmez">
          + {new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'USD' }).format(usd)} bayi
        </div>
      )}
    </div>
  )
}

function Kpi({ label, value, color = 'gray', onClick }) {
  const colors = { gray: 'text-gray-100', accent: 'text-accent', red: 'text-red-400', amber: 'text-amber-400' }
  return (
    <div onClick={onClick}
         className={`bg-brand-card border border-brand-border rounded-lg p-3 ${onClick ? 'cursor-pointer hover:border-accent/40 transition-colors' : ''}`}>
      <div className="text-[10px] uppercase text-gray-500">{label}</div>
      <div className={`text-2xl font-semibold ${colors[color]}`}>{value ?? '—'}</div>
    </div>
  )
}
