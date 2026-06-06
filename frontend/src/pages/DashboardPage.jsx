import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function DashboardPage() {
  const { user, tenant } = useAuth()
  const navigate = useNavigate()
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    (async () => {
      try { const s = await api.get('/api/stores'); setStores(Array.isArray(s) ? s : []) } catch {}
    })()
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
    <div className="max-w-[1400px]">
      <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">
            Hoş geldin, {user?.full_name?.split(' ')[0] || 'sen'} 👋
          </h1>
          <p className="text-sm text-gray-500 mt-1">{tenant?.name} · {tenant?.plan} plan</p>
        </div>
        <select value={storeId} onChange={e => setStoreId(e.target.value)} className="input !text-sm">
          <option value="">Tüm mağazalar</option>
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>

      {loading && <div className="text-gray-500 text-sm text-center py-12">Yükleniyor...</div>}

      {!loading && data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <Kpi label="AÇIK SİPARİŞ" value={k.acik_siparis} onClick={() => navigate('/orders')} />
            <Kpi label="BUGÜN GELEN" value={k.bugun_gelen} color="accent" onClick={() => navigate('/orders')} />
            <Kpi label="ACİL" value={k.acil} color={k.acil > 0 ? 'red' : 'gray'} onClick={() => navigate('/orders')} />
            <Kpi label="AÇIK KALIP" value={k.acik_kalip} onClick={() => navigate('/kalip-olustur')} />
            <Kpi label="PAKETLEME BEKLEYEN" value={k.paketleme_bekleyen} color="amber" onClick={() => navigate('/paketleme')} />
            <Kpi label="KARGO BEKLEYEN" value={k.kargo_bekleyen} color="amber" />
            <Kpi label="ASKIDA (ADET)" value={k.aski_adet} onClick={() => navigate('/aski')} />
            <Kpi label="DÜŞÜK STOK" value={k.dusuk_stok} color={k.dusuk_stok > 0 ? 'red' : 'gray'} onClick={() => navigate('/stok')} />
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
                      <div className="h-full bg-gradient-to-r from-accent to-purple-600 rounded-full transition-all"
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
