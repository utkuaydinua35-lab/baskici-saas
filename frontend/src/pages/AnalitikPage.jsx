import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

// Satış Analitiği — ciro serisi, AOV, en çok satanlar, kanal kırılımı,
// checkout hunisi. Grafikler el yapımı SVG/CSS (DashboardPage deseni).

const RANGES = [
  { key: '7', label: '7 Gün', days: 7 },
  { key: '30', label: '30 Gün', days: 30 },
  { key: '90', label: '90 Gün', days: 90 },
  { key: '365', label: '1 Yıl', days: 365 },
]

function isoDaysAgo(days) {
  const d = new Date()
  d.setDate(d.getDate() - days + 1)
  return d.toISOString().slice(0, 10)
}
const today = () => new Date().toISOString().slice(0, 10)

export default function AnalitikPage() {
  const [range, setRange] = useState('30')
  const [custom, setCustom] = useState({ start: '', end: '' })
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get('/api/stores?include_bayii=true')
      .then(s => setStores(Array.isArray(s) ? s : []))
      .catch(() => {})
  }, [])

  const load = useCallback(async () => {
    let start, end
    if (range === 'custom') {
      if (!custom.start || !custom.end) return
      start = custom.start; end = custom.end
    } else {
      const r = RANGES.find(r => r.key === range)
      start = isoDaysAgo(r.days); end = today()
    }
    setLoading(true); setError('')
    try {
      const params = new URLSearchParams({ start, end })
      if (storeId) params.set('store_id', storeId)
      setData(await api.get(`/api/analytics/summary?${params}`))
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Analitik yüklenemedi')
    } finally { setLoading(false) }
  }, [range, custom, storeId])

  useEffect(() => { load() }, [load])

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <h1 className="text-xl font-semibold mr-2">Analitik</h1>
        {RANGES.map(r => (
          <button key={r.key} onClick={() => setRange(r.key)}
            className={`px-3 py-1.5 rounded-lg text-xs border ${range === r.key
              ? 'bg-white/10 border-gray-400 text-white'
              : 'bg-brand-input border-brand-border text-gray-400 hover:text-gray-200'}`}>
            {r.label}
          </button>
        ))}
        <button onClick={() => setRange('custom')}
          className={`px-3 py-1.5 rounded-lg text-xs border ${range === 'custom'
            ? 'bg-white/10 border-gray-400 text-white'
            : 'bg-brand-input border-brand-border text-gray-400 hover:text-gray-200'}`}>
          Özel
        </button>
        {range === 'custom' && (
          <span className="flex items-center gap-1.5">
            <input type="date" value={custom.start} onChange={e => setCustom(c => ({ ...c, start: e.target.value }))}
              className="bg-brand-input border border-brand-border rounded-lg px-2 py-1 text-xs" />
            <span className="text-gray-500 text-xs">→</span>
            <input type="date" value={custom.end} onChange={e => setCustom(c => ({ ...c, end: e.target.value }))}
              className="bg-brand-input border border-brand-border rounded-lg px-2 py-1 text-xs" />
          </span>
        )}
        <select value={storeId} onChange={e => setStoreId(e.target.value)}
          className="ml-auto bg-brand-input border border-brand-border rounded-lg px-3 py-1.5 text-xs">
          <option value="">Tüm mağazalar</option>
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>

      {error && <div className="text-sm text-red-400">{error}</div>}
      {loading && !data && <div className="text-sm text-gray-400">Yükleniyor…</div>}

      {data && (
        <div className={`space-y-4 transition-opacity ${loading ? 'opacity-50' : ''}`}>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {/* USD bayi siparişleri TL'ye ÇEVRİLMEZ (kur kaynağı yok) — yanında ayrı */}
            <Kpi label="Ciro" value={fmtTl(data.revenue) + (data.revenue_usd > 0 ? ` + ${fmtUsd(data.revenue_usd)}` : '')} />
            <Kpi label="Sipariş" value={fmtNum(data.orders_count)} />
            <Kpi label="Ortalama Sepet" value={fmtTl(data.aov)} />
            <Kpi label="Dönüşüm (Vitrin)" value={data.funnel.created > 0 ? `%${data.funnel.conversion}` : '—'}
              hint={data.funnel.created > 0 ? `${data.funnel.paid}/${data.funnel.created} checkout` : 'checkout yok'} />
          </div>

          <RevenueChart daily={data.daily} />

          <div className="grid lg:grid-cols-2 gap-4">
            <BarCard title="En Çok Satan Ürünler" rows={data.top_products.map(p => ({
              label: p.title, value: p.quantity, suffix: ' adet' }))} />
            <BarCard title="En Çok Satan Modeller" rows={data.top_models.map(m => ({
              label: m.model, value: m.quantity, suffix: ' adet' }))} />
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <BarCard title="Kanal Bazında Ciro" money rows={data.by_store.map(s => ({
              label: `${s.store} (${platformLabel(s.platform)})`, value: s.revenue,
              hint: `${s.orders} sipariş${s.revenue_usd > 0 ? ` · + ${fmtUsd(s.revenue_usd)}` : ''}` }))} />
            <FunnelCard funnel={data.funnel} />
          </div>
        </div>
      )}
    </div>
  )
}

const fmtTl = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(n || 0)
const fmtNum = (n) => new Intl.NumberFormat('tr-TR').format(n || 0)
const fmtUsd = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n || 0)
const platformLabel = (p) => ({ shopify: 'Shopify', ikas: 'İkas', bayii: 'Bayii', storefront: 'Vitrin' }[p] || p)

function Kpi({ label, value, hint }) {
  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-4">
      <div className="text-[11px] text-gray-500 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold mt-1 tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-gray-500 mt-0.5">{hint}</div>}
    </div>
  )
}

function RevenueChart({ daily }) {
  if (!daily || daily.length === 0) return null
  const W = 700, H = 120, P = 6
  const vals = daily.map(d => d.tutar || 0)
  const max = Math.max(...vals, 1)
  const n = daily.length
  const x = (i) => n > 1 ? P + (i / (n - 1)) * (W - 2 * P) : W / 2
  const y = (v) => H - P - (v / max) * (H - 2 * P)
  const linePts = daily.map((d, i) => `${x(i)},${y(d.tutar || 0)}`).join(' ')
  const areaPts = `${P},${H - P} ${linePts} ${W - P},${H - P}`
  const [hover, setHover] = useState(null)

  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-gray-500 font-medium tracking-wide">GÜNLÜK CİRO</span>
        {hover != null && daily[hover] && (
          <span className="text-[11px] text-gray-300 tabular-nums">
            {new Date(daily[hover].gun).toLocaleDateString('tr-TR')} — {fmtTl(daily[hover].tutar)} ({daily[hover].adet} sipariş)
          </span>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none" style={{ height: 120 }}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const i = Math.round(((e.clientX - rect.left) / rect.width) * (n - 1))
          setHover(Math.max(0, Math.min(n - 1, i)))
        }}>
        <defs>
          <linearGradient id="anaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(52,211,153)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="rgb(52,211,153)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={areaPts} fill="url(#anaFill)" />
        <polyline points={linePts} fill="none" stroke="rgb(52,211,153)" strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round" />
        {hover != null && daily[hover] && (
          <>
            <line x1={x(hover)} y1={P} x2={x(hover)} y2={H - P} stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
            <circle cx={x(hover)} cy={y(daily[hover].tutar || 0)} r="3.5" fill="rgb(52,211,153)" />
          </>
        )}
      </svg>
    </div>
  )
}

function BarCard({ title, rows, money = false }) {
  const max = Math.max(...rows.map(r => r.value), 1)
  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-4">
      <div className="text-[11px] text-gray-500 font-medium tracking-wide mb-3">{title.toUpperCase()}</div>
      {rows.length === 0 && <div className="text-sm text-gray-500">Veri yok.</div>}
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i}>
            <div className="flex justify-between text-xs mb-0.5">
              <span className="text-gray-300 truncate pr-2">{r.label}</span>
              <span className="text-gray-400 tabular-nums whitespace-nowrap">
                {money ? fmtTl(r.value) : fmtNum(r.value) + (r.suffix || '')}
                {r.hint && <span className="text-gray-600"> · {r.hint}</span>}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-brand-input overflow-hidden">
              <div className="h-full rounded-full bg-emerald-500/70"
                style={{ width: `${(r.value / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const FUNNEL_LABELS = {
  paid: ['Ödendi', 'bg-emerald-500/70'],
  pending: ['Beklemede', 'bg-amber-500/60'],
  expired: ['Süresi Doldu', 'bg-gray-500/60'],
  failed: ['Başarısız', 'bg-red-500/60'],
  cancelled: ['İptal', 'bg-gray-600/60'],
}

function FunnelCard({ funnel }) {
  const entries = Object.entries(funnel.by_status || {})
  const total = funnel.created || 1
  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] text-gray-500 font-medium tracking-wide">CHECKOUT HUNİSİ (VİTRİN)</span>
        {funnel.abandoned_count > 0 && (
          <span className="text-[11px] text-amber-400">
            terk edilen: {funnel.abandoned_count} sepet · {fmtTl(funnel.abandoned_amount)}
          </span>
        )}
      </div>
      {entries.length === 0 && <div className="text-sm text-gray-500">Bu aralıkta checkout yok.</div>}
      <div className="space-y-2">
        {entries.sort((a, b) => b[1].count - a[1].count).map(([status, v]) => {
          const [label, cls] = FUNNEL_LABELS[status] || [status, 'bg-gray-500/60']
          return (
            <div key={status}>
              <div className="flex justify-between text-xs mb-0.5">
                <span className="text-gray-300">{label}</span>
                <span className="text-gray-400 tabular-nums">{v.count} · {fmtTl(v.amount)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-brand-input overflow-hidden">
                <div className={`h-full rounded-full ${cls}`} style={{ width: `${(v.count / total) * 100}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
