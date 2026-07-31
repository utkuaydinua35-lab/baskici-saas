import { useCallback, useEffect, useState } from 'react'
import { api, getToken } from '../lib/api'
import { useStore } from '../lib/store'

// Mağaza analitiği — ciro, en çok satanlar, checkout hunisi.
const RANGES = [
  { key: '7', label: '7 Gün', days: 7 },
  { key: '30', label: '30 Gün', days: 30 },
  { key: '90', label: '90 Gün', days: 90 },
  { key: '365', label: '1 Yıl', days: 365 },
]
const isoDaysAgo = (d) => new Date(Date.now() - (d - 1) * 86400000).toISOString().slice(0, 10)
const today = () => new Date().toISOString().slice(0, 10)

export default function AnalitikPage() {
  const { storeId } = useStore()
  const [range, setRange] = useState('30')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!storeId) return
    const r = RANGES.find(r => r.key === range)
    setLoading(true); setError('')
    try {
      setData(await api.get(
        `/api/analytics/summary?start=${isoDaysAgo(r.days)}&end=${today()}&store_id=${storeId}`))
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Analitik yüklenemedi')
    } finally { setLoading(false) }
  }, [storeId, range])
  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <h1 className="text-xl font-semibold mr-2">Analitik</h1>
        <button onClick={async () => {
          const r = RANGES.find(x => x.key === range)
          try {
            const res = await fetch(
              `/api/analytics/export.csv?start=${isoDaysAgo(r.days)}&end=${today()}&store_id=${storeId}`,
              { headers: { Authorization: `Bearer ${getToken()}` } })
            if (!res.ok) throw new Error()
            const blob = await res.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url; a.download = 'satis-raporu.csv'; a.click()
            URL.revokeObjectURL(url)
          } catch { setError('Rapor indirilemedi') }
        }} className="btn-ghost text-xs ml-auto">⬇ Rapor (CSV)</button>
        {RANGES.map(r => (
          <button key={r.key} onClick={() => setRange(r.key)}
            className={`px-3 py-1.5 rounded-xl text-xs border transition ${range === r.key
              ? 'border-panel-accent bg-emerald-50 text-emerald-700 font-medium'
              : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
            {r.label}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className={`space-y-4 transition-opacity ${loading ? 'opacity-50' : ''}`}>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Kpi label="Ciro" value={fmtTl(data.revenue)} />
            <Kpi label="Sipariş" value={fmtNum(data.orders_count)} />
            <Kpi label="Ortalama Sepet" value={fmtTl(data.aov)} />
            <Kpi label="Dönüşüm" value={data.funnel.created > 0 ? `%${data.funnel.conversion}` : '—'}
              hint={data.funnel.created > 0 ? `${data.funnel.paid}/${data.funnel.created} checkout` : ''} />
          </div>

          <RevenueChart daily={data.daily} />

          <div className="grid lg:grid-cols-2 gap-4">
            <BarCard title="En Çok Satan Ürünler"
              rows={data.top_products.map(p => ({ label: p.title, value: p.quantity, suffix: ' adet' }))} />
            <BarCard title="En Çok Satan Modeller"
              rows={data.top_models.map(m => ({ label: m.model, value: m.quantity, suffix: ' adet' }))} />
          </div>

          <FunnelCard funnel={data.funnel} />
        </div>
      )}
    </div>
  )
}

const fmtTl = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(n || 0)
const fmtNum = (n) => new Intl.NumberFormat('tr-TR').format(n || 0)

function Kpi({ label, value, hint }) {
  return (
    <div className="card">
      <div className="text-[11px] text-panel-muted uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold mt-1 tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-panel-muted mt-0.5">{hint}</div>}
    </div>
  )
}

function RevenueChart({ daily }) {
  const [hover, setHover] = useState(null)
  if (!daily?.length) return null
  const W = 700, H = 120, P = 6
  const vals = daily.map(d => d.tutar || 0)
  const max = Math.max(...vals, 1)
  const n = daily.length
  const x = (i) => n > 1 ? P + (i / (n - 1)) * (W - 2 * P) : W / 2
  const y = (v) => H - P - (v / max) * (H - 2 * P)
  const pts = daily.map((d, i) => `${x(i)},${y(d.tutar || 0)}`).join(' ')

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-panel-muted uppercase tracking-wide">Günlük Ciro</span>
        {hover != null && daily[hover] && (
          <span className="text-[11px] tabular-nums">
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
        <polygon points={`${P},${H - P} ${pts} ${W - P},${H - P}`} fill="rgb(5 150 105 / 0.10)" />
        <polyline points={pts} fill="none" stroke="#059669" strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round" />
        {hover != null && daily[hover] && (
          <>
            <line x1={x(hover)} y1={P} x2={x(hover)} y2={H - P} stroke="rgb(0 0 0 / 0.12)" strokeWidth="1" />
            <circle cx={x(hover)} cy={y(daily[hover].tutar || 0)} r="3.5" fill="#059669" />
          </>
        )}
      </svg>
    </div>
  )
}

function BarCard({ title, rows }) {
  const max = Math.max(...rows.map(r => r.value), 1)
  return (
    <div className="card">
      <div className="text-[11px] text-panel-muted uppercase tracking-wide mb-3">{title}</div>
      {rows.length === 0 && <div className="text-sm text-panel-muted">Veri yok.</div>}
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i}>
            <div className="flex justify-between text-xs mb-0.5">
              <span className="truncate pr-2">{r.label}</span>
              <span className="text-panel-muted tabular-nums whitespace-nowrap">
                {fmtNum(r.value)}{r.suffix || ''}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-panel-input overflow-hidden">
              <div className="h-full rounded-full bg-panel-accent/70"
                style={{ width: `${(r.value / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const FUNNEL_LABELS = {
  paid: ['Ödendi', 'bg-panel-accent/70'],
  pending: ['Beklemede', 'bg-amber-400/70'],
  expired: ['Süresi Doldu', 'bg-slate-400/60'],
  failed: ['Başarısız', 'bg-red-400/70'],
  cancelled: ['İptal', 'bg-slate-500/60'],
}

function FunnelCard({ funnel }) {
  const entries = Object.entries(funnel.by_status || {})
  const total = funnel.created || 1
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] text-panel-muted uppercase tracking-wide">Checkout Hunisi</span>
        {funnel.abandoned_count > 0 && (
          <span className="text-[11px] text-amber-700">
            terk edilen: {funnel.abandoned_count} sepet · {fmtTl(funnel.abandoned_amount)}
          </span>
        )}
      </div>
      {entries.length === 0 && <div className="text-sm text-panel-muted">Bu aralıkta checkout yok.</div>}
      <div className="space-y-2">
        {entries.sort((a, b) => b[1].count - a[1].count).map(([status, v]) => {
          const [label, cls] = FUNNEL_LABELS[status] || [status, 'bg-slate-400/60']
          return (
            <div key={status}>
              <div className="flex justify-between text-xs mb-0.5">
                <span>{label}</span>
                <span className="text-panel-muted tabular-nums">{v.count} · {fmtTl(v.amount)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-panel-input overflow-hidden">
                <div className={`h-full rounded-full ${cls}`} style={{ width: `${(v.count / total) * 100}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
